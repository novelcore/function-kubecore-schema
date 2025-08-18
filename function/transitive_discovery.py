"""Transitive Resource Discovery for KubeCore Platform Context Function.

This module implements multi-hop relationship traversal capabilities that discover
resources through indirect relationships across the KubeCore platform hierarchy.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .resource_resolver import ResourceRef


class CircuitBreaker:
    """Circuit breaker for API calls to handle failures gracefully."""
    
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open
        
    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self) -> None:
        """Record successful operation."""
        self.failure_count = 0
        self.state = "closed"
        
    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


@dataclass
class TransitiveDiscoveredResource:
    """Represents a resource discovered through transitive relationships."""
    name: str
    namespace: str
    kind: str
    api_version: str
    relationship_path: list[ResourceRef]  # Full discovery chain
    discovery_hops: int                   # Number of hops from source
    discovery_method: str                 # "direct" | "transitive-1" | "transitive-2" 
    intermediate_resources: list[ResourceRef]  # Resources in the chain
    summary: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of the transitive discovered resource."""
        chain = " → ".join(f"{ref.kind}({ref.name})" for ref in self.relationship_path)
        return f"{self.kind}({self.name}) via {self.discovery_hops}-hop: {chain}"


@dataclass
class TransitiveDiscoveryConfig:
    """Configuration for transitive discovery operations."""
    max_depth: int = 3
    max_resources_per_type: int = 50
    timeout_per_depth: float = 10.0  # seconds
    parallel_workers: int = 5
    cache_intermediate_results: bool = True
    enable_cycle_detection: bool = True
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0
    memory_limit_mb: int = 200
    early_termination_enabled: bool = True


# Transitive relationship chain definitions
TRANSITIVE_RELATIONSHIP_CHAINS: dict[str, list[tuple[str, list[str]]]] = {
    "XGitHubProject": [
        # 1-hop (direct)
        ("XKubeCluster", ["githubProjectRef"]),
        ("XGitHubApp", ["githubProjectRef"]),

        # 2-hop (indirect)
        ("XKubEnv", ["githubProjectRef", "kubeClusterRef"]),
        ("XKubeSystem", ["githubProjectRef", "kubeClusterRef"]),

        # 3-hop (transitive)  
        ("XApp", ["githubProjectRef", "kubeClusterRef", "kubenvRef"]),
    ],
    "XKubeCluster": [
        # 1-hop
        ("XKubEnv", ["kubeClusterRef"]),
        ("XKubeSystem", ["kubeClusterRef"]),

        # 2-hop
        ("XApp", ["kubeClusterRef", "kubenvRef"]),
    ],
    "XKubEnv": [
        # 1-hop
        ("XApp", ["kubenvRef"]),
        ("XQualityGate", ["qualityGates"]),
    ],
    "XApp": [
        # 1-hop
        ("XKubEnv", ["kubenvRef"]),  # reverse lookup
        ("XGitHubApp", ["githubProjectRef"]),  # via project reference
    ],
}


class TransitiveDiscoveryEngine:
    """Engine for performing transitive resource discovery operations."""

    def __init__(self, resource_resolver, config: TransitiveDiscoveryConfig | None = None):
        """Initialize transitive discovery engine.
        
        Args:
            resource_resolver: ResourceResolver instance for K8s operations
            config: Configuration for transitive discovery behavior
        """
        self.resource_resolver = resource_resolver
        self.config = config or TransitiveDiscoveryConfig()
        self.logger = logging.getLogger(__name__)
        
        # Cache for intermediate results
        self._intermediate_cache: dict[str, list[dict]] = {}
        self._cache_timestamps: dict[str, float] = {}
        
        # Performance monitoring
        self._memory_usage = 0
        self._total_api_calls = 0
        self._failed_api_calls = 0
        self._discovered_resources_count = 0
        
        # Circuit breakers for different API endpoints
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        if self.config.circuit_breaker_enabled:
            self._init_circuit_breakers()
        
        self.logger.debug(f"TransitiveDiscoveryEngine initialized with max_depth={self.config.max_depth}")

    def _init_circuit_breakers(self) -> None:
        """Initialize circuit breakers for API endpoints."""
        api_kinds = ["XKubeCluster", "XKubEnv", "XApp", "XGitHubApp", "XQualityGate", "XKubeSystem"]
        for kind in api_kinds:
            self._circuit_breakers[kind] = CircuitBreaker(
                failure_threshold=self.config.circuit_breaker_threshold,
                timeout=self.config.circuit_breaker_timeout
            )

    async def discover_transitive_relationships(
        self,
        target_ref: dict[str, Any],
        resource_type: str,
        context: dict[str, Any],
        max_depth: int | None = None
    ) -> dict[str, list[TransitiveDiscoveredResource]]:
        """
        Discover resources through multi-hop relationship traversal.
        
        Args:
            target_ref: Target resource reference (name, namespace, kind)
            resource_type: Type of the target resource  
            context: Request context
            max_depth: Maximum traversal depth (uses config default if None)
            
        Returns:
            Dictionary mapping schema types to discovered resources with path info
        """
        if max_depth is None:
            max_depth = self.config.max_depth
            
        start_time = time.time()
        self.logger.info(f"Starting transitive discovery for {resource_type}: {target_ref.get('name')} (max_depth={max_depth})")
        
        # Get relationship chains for the resource type
        relationship_chains = TRANSITIVE_RELATIONSHIP_CHAINS.get(resource_type, [])
        if not relationship_chains:
            self.logger.debug(f"No transitive relationship chains defined for {resource_type}")
            return {}
        
        discovered_resources: dict[str, list[TransitiveDiscoveredResource]] = {}
        
        # Check memory usage before starting
        if self.config.memory_limit_mb > 0:
            initial_memory = self._estimate_memory_usage()
            if initial_memory > self.config.memory_limit_mb * 1024 * 1024:  # Convert MB to bytes
                self.logger.warning(f"Memory usage {initial_memory / 1024 / 1024:.1f}MB exceeds limit {self.config.memory_limit_mb}MB")
                return {}
        
        # Process each relationship chain
        for target_kind, ref_chain in relationship_chains:
            self.logger.debug(f"Processing relationship chain: {target_kind} via {ref_chain}")
            
            if len(ref_chain) > max_depth:
                self.logger.debug(f"Skipping chain {target_kind} - depth {len(ref_chain)} > max_depth {max_depth}")
                continue
            
            # Check for early termination conditions
            if self.config.early_termination_enabled and len(discovered_resources) > 0:
                total_discovered = sum(len(resources) for resources in discovered_resources.values())
                if total_discovered >= self.config.max_resources_per_type * len(discovered_resources):
                    self.logger.info(f"Early termination: discovered {total_discovered} resources")
                    break
                
            chain_resources = await self._traverse_relationship_chain(
                target_ref, resource_type, target_kind, ref_chain, context
            )
            self.logger.debug(f"Traversal result for {target_kind}: {len(chain_resources)} resources")
            
            if chain_resources:
                schema_type = self._kind_to_schema_type(target_kind)
                if schema_type not in discovered_resources:
                    discovered_resources[schema_type] = []
                discovered_resources[schema_type].extend(chain_resources)
                
                self._discovered_resources_count += len(chain_resources)
        
        # Remove duplicates
        for schema_type in discovered_resources:
            discovered_resources[schema_type] = self._deduplicate_resources(
                discovered_resources[schema_type]
            )
        
        duration = time.time() - start_time
        total_found = sum(len(resources) for resources in discovered_resources.values())
        self.logger.info(f"Transitive discovery completed in {duration*1000:.1f}ms: found {total_found} resources across {len(discovered_resources)} types")
        
        return discovered_resources

    async def _traverse_relationship_chain(
        self,
        source_ref: dict[str, Any],
        source_type: str,
        target_kind: str,
        ref_chain: list[str],
        context: dict[str, Any]
    ) -> list[TransitiveDiscoveredResource]:
        """
        Traverse a specific relationship chain to find target resources.
        
        Args:
            source_ref: Source resource reference
            source_type: Type of source resource
            target_kind: Kind of target resource to find
            ref_chain: Chain of reference fields to follow
            context: Request context
            
        Returns:
            List of discovered resources at the end of the chain
        """
        if not ref_chain:
            return []
            
        hops = len(ref_chain)
        self.logger.debug(f"Traversing {hops}-hop chain: {source_type} → {target_kind} via {ref_chain}")
        
        # Start with source resource
        current_resources = [source_ref]
        relationship_path = [self._dict_to_resource_ref(source_ref)]
        self.logger.debug(f"Starting traversal with {len(current_resources)} resources: {[r.get('name') for r in current_resources]}")
        
        # Traverse each hop in the chain
        for hop_index, ref_field in enumerate(ref_chain):
            self.logger.debug(f"Hop {hop_index + 1}/{len(ref_chain)}: Looking for {ref_field} references in {len(current_resources)} resources")
            try:
                # Set timeout for this depth level
                next_resources = await asyncio.wait_for(
                    self._find_next_hop_resources(current_resources, ref_field, hop_index + 1),
                    timeout=self.config.timeout_per_depth
                )
                
                if not next_resources:
                    self.logger.debug(f"No resources found at hop {hop_index + 1} for chain {ref_chain}")
                    return []
                    
                current_resources = next_resources
                
                # Add intermediate resources to path
                if hop_index < len(ref_chain) - 1:  # Not the final hop
                    for resource in current_resources[:1]:  # Sample first resource for path
                        relationship_path.append(self._dict_to_resource_ref(resource))
                        
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout at hop {hop_index + 1} for chain {ref_chain}")
                return []
            except Exception as e:
                self.logger.warning(f"Error at hop {hop_index + 1} for chain {ref_chain}: {e}")
                return []
        
        # Convert final resources to TransitiveDiscoveredResource objects
        discovered = []
        for resource in current_resources:
            if len(discovered) >= self.config.max_resources_per_type:
                break
                
            transitive_resource = TransitiveDiscoveredResource(
                name=resource.get("name", "unknown"),
                namespace=resource.get("namespace", "default"),
                kind=target_kind,
                api_version=resource.get("apiVersion", "unknown"),
                relationship_path=relationship_path[:],  # Copy of path
                discovery_hops=hops,
                discovery_method=f"transitive-{hops}",
                intermediate_resources=relationship_path[1:-1],  # Exclude source and target
                summary=await self._create_transitive_summary(resource, target_kind)
            )
            discovered.append(transitive_resource)
        
        self.logger.debug(f"Found {len(discovered)} resources via {hops}-hop chain to {target_kind}")
        return discovered

    async def _find_next_hop_resources(
        self,
        current_resources: list[dict[str, Any]],
        ref_field: str,
        hop_number: int
    ) -> list[dict[str, Any]]:
        """
        Find resources at the next hop by following reference fields.
        
        Args:
            current_resources: Resources at current hop
            ref_field: Reference field to follow
            hop_number: Current hop number (for caching)
            
        Returns:
            Resources found at next hop
        """
        next_resources = []
        
        # Process current resources in parallel if configured
        if self.config.parallel_workers > 1 and len(current_resources) > 1:
            try:
                semaphore = asyncio.Semaphore(self.config.parallel_workers)
                
                async def process_resource(resource: dict[str, Any]) -> list[dict[str, Any]]:
                    async with semaphore:
                        return await self._find_resources_referencing(resource, ref_field)
                
                tasks = [process_resource(resource) for resource in current_resources]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        self.logger.warning(f"Parallel resource processing failed: {result}")
                        continue
                    next_resources.extend(result)
                    
            except Exception as e:
                self.logger.warning(f"Parallel processing failed at hop {hop_number}, falling back to sequential: {e}")
                # Fallback to sequential processing
                for resource in current_resources:
                    try:
                        refs = await self._find_resources_referencing(resource, ref_field)
                        next_resources.extend(refs)
                    except Exception as e:
                        self.logger.warning(f"Sequential resource processing failed: {e}")
        else:
            # Sequential processing
            for resource in current_resources:
                try:
                    refs = await self._find_resources_referencing(resource, ref_field)
                    next_resources.extend(refs)
                except Exception as e:
                    self.logger.warning(f"Resource processing failed at hop {hop_number}: {e}")
        
        return next_resources

    async def _find_resources_referencing(
        self,
        target_resource: dict[str, Any],
        ref_field: str
    ) -> list[dict[str, Any]]:
        """
        Find resources that reference the target resource through a specific field.
        
        Args:
            target_resource: Resource being referenced
            ref_field: Field name that should contain the reference
            
        Returns:
            List of resources that reference the target
        """
        target_name = target_resource.get("name")
        target_namespace = target_resource.get("namespace")
        
        if not target_name:
            return []
        
        # Generate cache key for intermediate results
        cache_key = f"{ref_field}:{target_name}:{target_namespace or 'None'}"
        
        # Check cache if enabled
        if self.config.cache_intermediate_results:
            cached_result = self._get_from_intermediate_cache(cache_key)
            if cached_result is not None:
                return cached_result
        
        # Determine what kinds of resources to search based on reference field
        search_configs = self._get_search_configs_for_ref_field(ref_field)
        found_resources = []
        
        self.logger.debug(f"Searching for resources with {ref_field} referencing {target_name}/{target_namespace}")
        self.logger.debug(f"Will search {len(search_configs)} resource types: {[kind for kind, _ in search_configs]}")
        
        for kind, api_version in search_configs:
            try:
                self.logger.debug(f"Searching {kind} resources with {ref_field} = {target_name}")
                resources = await self._search_resources_with_ref(
                    kind, api_version, ref_field, target_name, target_namespace
                )
                self.logger.debug(f"Found {len(resources)} {kind} resources")
                found_resources.extend(resources)
            except Exception as e:
                self.logger.warning(f"Failed to search {kind} for {ref_field} references: {e}")
        
        # Cache result if enabled
        if self.config.cache_intermediate_results:
            self._put_in_intermediate_cache(cache_key, found_resources)
        
        return found_resources

    async def _search_resources_with_ref(
        self,
        kind: str,
        api_version: str,
        ref_field: str,
        target_name: str,
        target_namespace: str | None
    ) -> list[dict[str, Any]]:
        """
        Search for resources of a specific kind that have a reference to the target.
        
        Args:
            kind: Kubernetes resource kind to search
            api_version: API version of the resources  
            ref_field: Reference field to check
            target_name: Name of target resource
            target_namespace: Namespace of target resource
            
        Returns:
            List of matching resources
        """
        # Check circuit breaker
        if self.config.circuit_breaker_enabled:
            circuit_breaker = self._circuit_breakers.get(kind)
            if circuit_breaker and not circuit_breaker.can_execute():
                self.logger.warning(f"Circuit breaker open for {kind}, skipping API call")
                return []
        
        try:
            self._total_api_calls += 1
            
            # List all resources of the specified kind
            list_result = await self.resource_resolver.k8s_client.list_resources(
                api_version=api_version,
                kind=kind,
                limit=100  # Reasonable limit
            )
            
            matching_resources = []
            items = list_result.get("items", [])
            
            for item in items:
                if self._resource_references_target(item, ref_field, target_name, target_namespace):
                    matching_resources.append({
                        "name": item.get("metadata", {}).get("name"),
                        "namespace": item.get("metadata", {}).get("namespace"),
                        "apiVersion": api_version,
                        "kind": kind,
                        "data": item  # Store full resource data
                    })
                    
                    # Check resource limit per API call
                    if len(matching_resources) >= self.config.max_resources_per_type:
                        self.logger.debug(f"Reached max resources limit for {kind}")
                        break
            
            # Record success in circuit breaker
            if self.config.circuit_breaker_enabled and kind in self._circuit_breakers:
                self._circuit_breakers[kind].record_success()
            
            self.logger.debug(f"Found {len(matching_resources)} {kind} resources referencing {target_name} via {ref_field}")
            return matching_resources
            
        except Exception as e:
            self._failed_api_calls += 1
            
            # Record failure in circuit breaker
            if self.config.circuit_breaker_enabled and kind in self._circuit_breakers:
                self._circuit_breakers[kind].record_failure()
                
            self.logger.warning(f"Search failed for {kind} resources: {e}")
            return []

    def _resource_references_target(
        self,
        resource: dict[str, Any],
        ref_field: str,
        target_name: str,
        target_namespace: str | None
    ) -> bool:
        """
        Check if a resource references the target through a specific field.
        
        Args:
            resource: Resource to check
            ref_field: Reference field name
            target_name: Target resource name
            target_namespace: Target resource namespace
            
        Returns:
            True if resource references the target
        """
        spec = resource.get("spec", {})
        
        # Handle single reference fields (e.g., githubProjectRef, kubeClusterRef)
        if ref_field.endswith("Ref"):
            ref_value = spec.get(ref_field, {})
            if isinstance(ref_value, dict):
                return (ref_value.get("name") == target_name and 
                       (target_namespace is None or ref_value.get("namespace") == target_namespace))
        
        # Handle reference arrays (e.g., qualityGates)
        elif ref_field in spec:
            ref_list = spec.get(ref_field, [])
            if isinstance(ref_list, list):
                for ref_item in ref_list:
                    if isinstance(ref_item, dict):
                        # Handle both direct refs and nested ref structures
                        ref_obj = ref_item.get("ref", ref_item)
                        if isinstance(ref_obj, dict):
                            if (ref_obj.get("name") == target_name and 
                               (target_namespace is None or ref_obj.get("namespace") == target_namespace)):
                                return True
        
        return False

    def _get_search_configs_for_ref_field(self, ref_field: str) -> list[tuple[str, str]]:
        """
        Get search configurations (kind, api_version) for a reference field.
        
        Args:
            ref_field: Reference field name
            
        Returns:
            List of (kind, api_version) tuples to search
        """
        # Mapping from reference fields to resource types that might contain them
        ref_field_mappings = {
            "githubProjectRef": [
                ("XKubeCluster", "platform.kubecore.io/v1alpha1"),
                ("XGitHubApp", "github.platform.kubecore.io/v1alpha1"),
                ("XApp", "app.kubecore.io/v1alpha1"),
                ("XQualityGate", "platform.kubecore.io/v1alpha1")
            ],
            "kubeClusterRef": [
                ("XKubEnv", "platform.kubecore.io/v1alpha1"),
                ("XKubeSystem", "platform.kubecore.io/v1alpha1")
            ],
            "kubenvRef": [
                ("XApp", "app.kubecore.io/v1alpha1")
            ],
            "qualityGates": [
                ("XKubEnv", "platform.kubecore.io/v1alpha1"),
                ("XApp", "app.kubecore.io/v1alpha1")
            ]
        }
        
        return ref_field_mappings.get(ref_field, [])

    def _dict_to_resource_ref(self, resource_dict: dict[str, Any]) -> ResourceRef:
        """Convert resource dictionary to ResourceRef object."""
        return ResourceRef(
            api_version=resource_dict.get("apiVersion", "unknown"),
            kind=resource_dict.get("kind", "unknown"),
            name=resource_dict.get("name", "unknown"),
            namespace=resource_dict.get("namespace")
        )

    def _kind_to_schema_type(self, kind: str) -> str:
        """Convert Kubernetes kind to schema type name."""
        kind_to_schema_map = {
            "XKubeCluster": "kubeCluster",
            "XKubEnv": "kubEnv", 
            "XApp": "app",
            "XGitHubApp": "githubApp",
            "XQualityGate": "qualityGate",
            "XKubeSystem": "kubeSystem"
        }
        return kind_to_schema_map.get(kind, kind.lower())

    async def _create_transitive_summary(self, resource: dict[str, Any], target_kind: str) -> dict[str, Any]:
        """Create summary for transitively discovered resource."""
        return {
            "name": resource.get("name", "unknown"),
            "kind": target_kind,
            "status": "discovered",
            "discoveredBy": "transitive-lookup",
            "discoverySource": "multi-hop-traversal"
        }

    def _deduplicate_resources(
        self,
        resources: list[TransitiveDiscoveredResource]
    ) -> list[TransitiveDiscoveredResource]:
        """Remove duplicate resources based on name and namespace."""
        seen = set()
        unique_resources = []
        
        for resource in resources:
            key = (resource.name, resource.namespace, resource.kind)
            if key not in seen:
                seen.add(key)
                unique_resources.append(resource)
        
        return unique_resources

    def _get_from_intermediate_cache(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get results from intermediate cache if not expired."""
        if cache_key not in self._intermediate_cache:
            return None
            
        timestamp = self._cache_timestamps.get(cache_key, 0)
        if time.time() - timestamp > 300:  # 5 minute TTL
            del self._intermediate_cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None
            
        return self._intermediate_cache[cache_key]

    def _put_in_intermediate_cache(self, cache_key: str, resources: list[dict[str, Any]]) -> None:
        """Store results in intermediate cache."""
        self._intermediate_cache[cache_key] = resources
        self._cache_timestamps[cache_key] = time.time()
        
        # Simple cleanup - remove oldest entries if cache gets too large
        if len(self._intermediate_cache) > 100:
            oldest_key = min(self._cache_timestamps.keys(), key=lambda k: self._cache_timestamps[k])
            del self._intermediate_cache[oldest_key]
            del self._cache_timestamps[oldest_key]

    def get_config(self) -> TransitiveDiscoveryConfig:
        """Get current configuration."""
        return self.config

    def update_config(self, **kwargs) -> None:
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                self.logger.debug(f"Updated config {key} = {value}")

    def clear_cache(self) -> None:
        """Clear intermediate result cache."""
        self._intermediate_cache.clear()
        self._cache_timestamps.clear()
        self.logger.info("Cleared transitive discovery cache")

    def _estimate_memory_usage(self) -> int:
        """Estimate current memory usage in bytes."""
        try:
            import sys
            
            total_size = 0
            
            # Estimate cache sizes
            for cache_data in self._intermediate_cache.values():
                total_size += sys.getsizeof(cache_data)
                for item in cache_data:
                    total_size += sys.getsizeof(item)
            
            total_size += sys.getsizeof(self._cache_timestamps)
            
            return total_size
        except Exception as e:
            self.logger.warning(f"Failed to estimate memory usage: {e}")
            return 0

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics for monitoring."""
        circuit_breaker_stats = {}
        if self.config.circuit_breaker_enabled:
            for kind, breaker in self._circuit_breakers.items():
                circuit_breaker_stats[kind] = {
                    "state": breaker.state,
                    "failure_count": breaker.failure_count,
                    "last_failure_time": breaker.last_failure_time
                }
        
        return {
            "total_api_calls": self._total_api_calls,
            "failed_api_calls": self._failed_api_calls,
            "success_rate": (self._total_api_calls - self._failed_api_calls) / max(self._total_api_calls, 1),
            "discovered_resources": self._discovered_resources_count,
            "cache_entries": len(self._intermediate_cache),
            "estimated_memory_mb": self._estimate_memory_usage() / 1024 / 1024,
            "circuit_breakers": circuit_breaker_stats
        }

    def reset_performance_stats(self) -> None:
        """Reset performance statistics."""
        self._total_api_calls = 0
        self._failed_api_calls = 0
        self._discovered_resources_count = 0
        self.logger.debug("Performance statistics reset")

    def is_healthy(self) -> bool:
        """Check if the discovery engine is healthy."""
        if self._total_api_calls == 0:
            return True
            
        success_rate = (self._total_api_calls - self._failed_api_calls) / self._total_api_calls
        
        # Consider unhealthy if success rate is below 50%
        if success_rate < 0.5:
            return False
            
        # Check if too many circuit breakers are open
        if self.config.circuit_breaker_enabled:
            open_breakers = sum(1 for breaker in self._circuit_breakers.values() if breaker.state == "open")
            if open_breakers > len(self._circuit_breakers) / 2:
                return False
        
        return True

    def _should_skip_resource_type(self, resource_type: str) -> bool:
        """Check if a resource type should be skipped due to performance concerns."""
        if not self.config.circuit_breaker_enabled:
            return False
            
        breaker = self._circuit_breakers.get(resource_type)
        if breaker and breaker.state == "open":
            return True
            
        return False

    async def _check_timeout_and_limits(self, start_time: float, discovered_count: int) -> bool:
        """Check if timeout or limits have been reached."""
        # Check timeout
        elapsed = time.time() - start_time
        if elapsed > self.config.timeout_per_depth:
            self.logger.warning(f"Timeout reached: {elapsed:.1f}s > {self.config.timeout_per_depth}s")
            return True
        
        # Check resource limits
        if discovered_count >= self.config.max_resources_per_type:
            self.logger.info(f"Resource limit reached: {discovered_count} >= {self.config.max_resources_per_type}")
            return True
        
        # Check memory usage
        if self.config.memory_limit_mb > 0:
            current_memory = self._estimate_memory_usage()
            if current_memory > self.config.memory_limit_mb * 1024 * 1024:
                self.logger.warning(f"Memory limit reached: {current_memory / 1024 / 1024:.1f}MB > {self.config.memory_limit_mb}MB")
                return True
        
        return False