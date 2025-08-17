"""Resource Resolution Engine for KubeCore Platform Context Function.

This module provides comprehensive resource resolution with relationship handling,
circular dependency detection, and performance optimizations.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .k8s_client import K8sClient, K8sPermissionError, K8sResourceNotFoundError
from .platform_relationships import RESOURCE_RELATIONSHIPS


@dataclass
class ResourceRef:
    """Represents a reference to a Kubernetes resource."""

    api_version: str
    kind: str
    name: str
    namespace: str | None = None

    def __str__(self) -> str:
        """String representation of the resource reference."""
        ns_str = f"/{self.namespace}" if self.namespace else ""
        return f"{self.kind}{ns_str}/{self.name}"

    def __hash__(self) -> int:
        """Hash for use in sets and dictionaries."""
        return hash((self.api_version, self.kind, self.name, self.namespace))


@dataclass
class ResolvedResource:
    """Represents a resolved Kubernetes resource with metadata."""

    ref: ResourceRef
    data: dict[str, Any]
    relationships: list[ResourceRef] = field(default_factory=list)
    resolution_time: float = field(default_factory=time.time)
    cached: bool = False

    @property
    def age(self) -> float:
        """Age of the resolved resource in seconds."""
        return time.time() - self.resolution_time


@dataclass
class ResolutionContext:
    """Context for resource resolution operations."""

    max_depth: int = 5
    max_resources: int = 100
    cache_ttl: float = 300.0  # 5 minutes
    visited: set[ResourceRef] = field(default_factory=set)
    resolution_path: list[ResourceRef] = field(default_factory=list)
    resolved_count: int = 0


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected in resource resolution."""


class ResourceResolutionError(Exception):
    """Raised when resource resolution fails."""


class ResourceCache:
    """Cache for resolved resources with TTL support."""

    def __init__(self, ttl: float = 300.0):
        """Initialize cache with TTL in seconds."""
        self.ttl = ttl
        self._cache: dict[ResourceRef, ResolvedResource] = {}
        self.logger = logging.getLogger(f"{__name__}.cache")

    def get(self, ref: ResourceRef) -> ResolvedResource | None:
        """Get a cached resource if it exists and is not expired."""
        resource = self._cache.get(ref)
        if resource and resource.age < self.ttl:
            self.logger.debug(f"Cache hit for {ref}")
            return resource
        elif resource:
            # Remove expired entry
            del self._cache[ref]
            self.logger.debug(f"Cache expired for {ref}")
        return None

    def put(self, resource: ResolvedResource) -> None:
        """Cache a resolved resource."""
        # Don't modify the original resource's cached flag
        self._cache[resource.ref] = resource
        self.logger.debug(f"Cached {resource.ref}")

    def invalidate(self, ref: ResourceRef) -> None:
        """Invalidate a cached resource."""
        if ref in self._cache:
            del self._cache[ref]
            self.logger.debug(f"Invalidated cache for {ref}")

    def clear(self) -> None:
        """Clear the entire cache."""
        count = len(self._cache)
        self._cache.clear()
        self.logger.debug(f"Cleared cache ({count} entries)")

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


class ResourceResolver:
    """Engine for resolving Kubernetes resources and their relationships."""

    def __init__(
        self,
        k8s_client: K8sClient,
        cache_ttl: float = 300.0,
        max_concurrent: int = 10,
    ):
        """Initialize the resource resolver.
        
        Args:
            k8s_client: Kubernetes client for resource fetching
            cache_ttl: Cache time-to-live in seconds
            max_concurrent: Maximum concurrent resolution operations
        """
        self.k8s_client = k8s_client
        self.cache = ResourceCache(cache_ttl)
        self.max_concurrent = max_concurrent
        self.logger = logging.getLogger(__name__)

        # Semaphore for controlling concurrent operations
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def resolve_resource(
        self,
        ref: ResourceRef,
        context: ResolutionContext | None = None,
    ) -> ResolvedResource:
        """Resolve a single resource by reference.
        
        Args:
            ref: Resource reference to resolve
            context: Resolution context for tracking state
            
        Returns:
            Resolved resource with data and metadata
            
        Raises:
            CircularDependencyError: If circular dependency detected
            ResourceResolutionError: If resolution fails
        """
        if context is None:
            context = ResolutionContext()

        # Check cache first
        cached = self.cache.get(ref)
        if cached:
            cached.cached = True  # Mark as cached when retrieved from cache
            return cached

        # Check for circular dependencies
        if ref in context.visited:
            path_str = " -> ".join(str(r) for r in context.resolution_path + [ref])
            raise CircularDependencyError(
                f"Circular dependency detected: {path_str}"
            )

        # Check resolution limits
        if len(context.resolution_path) >= context.max_depth:
            raise ResourceResolutionError(
                f"Maximum resolution depth ({context.max_depth}) exceeded"
            )

        if context.resolved_count >= context.max_resources:
            raise ResourceResolutionError(
                f"Maximum resource count ({context.max_resources}) exceeded"
            )

        # Add to visited set and resolution path
        context.visited.add(ref)
        context.resolution_path.append(ref)
        context.resolved_count += 1

        try:
            async with self._semaphore:
                # Fetch resource from Kubernetes
                self.logger.debug(f"Resolving resource: {ref}")

                try:
                    data = await self.k8s_client.get_resource(
                        ref.api_version,
                        ref.kind,
                        ref.name,
                        ref.namespace,
                    )
                except K8sResourceNotFoundError:
                    raise ResourceResolutionError(f"Resource not found: {ref}")
                except K8sPermissionError:
                    raise ResourceResolutionError(f"Permission denied for: {ref}")

                # Create resolved resource
                resolved = ResolvedResource(ref=ref, data=data)

                # Find relationships in the resource
                relationships = self._extract_relationships(resolved)
                resolved.relationships = relationships

                # Cache the resolved resource
                self.cache.put(resolved)

                self.logger.debug(
                    f"Resolved {ref} with {len(relationships)} relationships"
                )

                return resolved

        finally:
            # Clean up context
            context.resolution_path.pop()

    async def resolve_with_relationships(
        self,
        ref: ResourceRef,
        max_depth: int = 3,
        max_resources: int = 50,
        relationship_types: set[str] | None = None,
    ) -> dict[ResourceRef, ResolvedResource]:
        """Resolve a resource and its related resources.
        
        Args:
            ref: Root resource reference to resolve
            max_depth: Maximum depth for relationship traversal
            max_resources: Maximum number of resources to resolve
            relationship_types: Set of relationship types to follow
            
        Returns:
            Dictionary of resolved resources keyed by reference
            
        Raises:
            CircularDependencyError: If circular dependency detected
            ResourceResolutionError: If resolution fails
        """
        context = ResolutionContext(
            max_depth=max_depth,
            max_resources=max_resources,
        )

        if relationship_types is None:
            relationship_types = {"owns", "belongsTo", "uses", "supports", "runsOn", "appliesTo", "sources", "sourcedBy", "deploysTo", "hosts"}

        resolved_resources: dict[ResourceRef, ResolvedResource] = {}
        pending_refs: deque[ResourceRef] = deque([ref])

        while pending_refs and context.resolved_count < max_resources:
            current_ref = pending_refs.popleft()

            # Skip if already resolved
            if current_ref in resolved_resources:
                continue

            try:
                # Resolve current resource
                resolved = await self.resolve_resource(current_ref, context)
                resolved_resources[current_ref] = resolved

                # Add related resources to pending queue
                for rel_ref in resolved.relationships:
                    if rel_ref not in resolved_resources and rel_ref not in pending_refs:
                        # Check if we should follow this relationship type
                        rel_type = self._get_relationship_type(current_ref, rel_ref)
                        if rel_type and rel_type in relationship_types:
                            pending_refs.append(rel_ref)

            except (CircularDependencyError, ResourceResolutionError) as e:
                self.logger.warning(f"Failed to resolve {current_ref}: {e}")
                # Continue with other resources rather than failing completely
                continue

        self.logger.info(
            f"Resolved {len(resolved_resources)} resources starting from {ref}"
        )

        return resolved_resources

    async def resolve_parallel(
        self,
        refs: list[ResourceRef],
        max_concurrent: int | None = None,
    ) -> dict[ResourceRef, ResolvedResource | Exception]:
        """Resolve multiple resources in parallel.
        
        Args:
            refs: List of resource references to resolve
            max_concurrent: Override max concurrent operations
            
        Returns:
            Dictionary mapping refs to resolved resources or exceptions
        """
        if max_concurrent is None:
            max_concurrent = self.max_concurrent

        semaphore = asyncio.Semaphore(max_concurrent)

        async def resolve_one(ref: ResourceRef) -> tuple[ResourceRef, ResolvedResource | Exception]:
            async with semaphore:
                try:
                    result = await self.resolve_resource(ref)
                    return ref, result
                except Exception as e:
                    return ref, e

        # Execute all resolutions concurrently
        tasks = [resolve_one(ref) for ref in refs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert results to dictionary
        result_dict: dict[ResourceRef, ResolvedResource | Exception] = {}
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Task failed: {result}")
                continue
            ref, resolved_or_exception = result
            result_dict[ref] = resolved_or_exception

        success_count = sum(
            1 for r in result_dict.values()
            if isinstance(r, ResolvedResource)
        )

        self.logger.info(
            f"Parallel resolution completed: {success_count}/{len(refs)} successful"
        )

        return result_dict

    def _extract_relationships(self, resource: ResolvedResource) -> list[ResourceRef]:
        """Extract resource references from a resolved resource.
        
        This method looks for common reference patterns in Kubernetes resources
        and extracts them as ResourceRef objects.
        """
        relationships: list[ResourceRef] = []
        data = resource.data

        # Extract references from spec section
        spec = data.get("spec", {})
        relationships.extend(self._extract_refs_from_object(spec, resource.ref.namespace))

        # Extract references from status section (for observed state)
        status = data.get("status", {})
        relationships.extend(self._extract_refs_from_object(status, resource.ref.namespace))

        # Extract references from metadata (owner references, etc.)
        metadata = data.get("metadata", {})
        owner_refs = metadata.get("ownerReferences", [])
        for owner_ref in owner_refs:
            if isinstance(owner_ref, dict) and owner_ref.get("name") and owner_ref.get("kind"):
                relationships.append(ResourceRef(
                    api_version=owner_ref.get("apiVersion", "v1"),
                    kind=owner_ref.get("kind", ""),
                    name=owner_ref.get("name", ""),
                    namespace=resource.ref.namespace,  # Same namespace as owner
                ))

        # Remove duplicates and invalid refs
        unique_refs = []
        seen = set()
        for ref in relationships:
            if ref not in seen and ref.name and ref.kind and ref.api_version:
                unique_refs.append(ref)
                seen.add(ref)

        return unique_refs

    def _extract_refs_from_object(
        self,
        obj: Any,
        default_namespace: str | None = None,
    ) -> list[ResourceRef]:
        """Recursively extract resource references from an object."""
        refs: list[ResourceRef] = []

        if isinstance(obj, dict):
            # Look for common reference patterns
            for key, value in obj.items():
                if key.endswith("Ref") and isinstance(value, dict):
                    # Standard Kubernetes reference
                    ref = self._parse_object_reference(value, default_namespace)
                    if ref:
                        refs.append(ref)
                elif key.endswith("Refs") and isinstance(value, list):
                    # List of references
                    for item in value:
                        if isinstance(item, dict):
                            ref = self._parse_object_reference(item, default_namespace)
                            if ref:
                                refs.append(ref)
                elif isinstance(value, (dict, list)):
                    # Recurse into nested objects/arrays
                    refs.extend(self._extract_refs_from_object(value, default_namespace))

        elif isinstance(obj, list):
            for item in obj:
                refs.extend(self._extract_refs_from_object(item, default_namespace))

        return refs

    def _parse_object_reference(
        self,
        ref_obj: dict[str, Any],
        default_namespace: str | None = None,
    ) -> ResourceRef | None:
        """Parse a Kubernetes object reference."""
        name = ref_obj.get("name")
        if not name:
            return None

        # Try to determine API version and kind
        api_version = ref_obj.get("apiVersion")
        kind = ref_obj.get("kind")

        # If not explicitly specified, try to infer from reference field names
        if not api_version or not kind:
            # Look for common KubeCore platform references
            if "githubProviderRef" in str(ref_obj) or "githubProvider" in name.lower():
                api_version = "github.platform.kubecore.io/v1alpha1"
                kind = "XGitHubProvider"
            elif "githubProjectRef" in str(ref_obj) or "project" in name.lower():
                api_version = "github.platform.kubecore.io/v1alpha1"
                kind = "XGitHubProject"
            elif "kubeClusterRef" in str(ref_obj) or "cluster" in name.lower():
                api_version = "platform.kubecore.io/v1alpha1"
                kind = "XKubeCluster"
            elif "kubeNetRef" in str(ref_obj) or "network" in name.lower():
                api_version = "network.platform.kubecore.io/v1alpha1"
                kind = "XKubeNet"
            elif "kubenvRef" in str(ref_obj) or "env" in name.lower():
                api_version = "platform.kubecore.io/v1alpha1"
                kind = "XKubEnv"
            else:
                # Default fallback
                api_version = api_version or "v1"
                kind = kind or "ConfigMap"

        namespace = ref_obj.get("namespace", default_namespace)

        return ResourceRef(
            api_version=api_version,
            kind=kind,
            name=name,
            namespace=namespace,
        )

    def _get_relationship_type(
        self,
        from_ref: ResourceRef,
        to_ref: ResourceRef,
    ) -> str | None:
        """Get the relationship type between two resources."""
        from_relationships = RESOURCE_RELATIONSHIPS.get(from_ref.kind, {})

        for rel_type, targets in from_relationships.items():
            if to_ref.kind in targets:
                return rel_type

        return None

    def detect_circular_dependencies(
        self,
        resolved_resources: dict[ResourceRef, ResolvedResource],
    ) -> list[list[ResourceRef]]:
        """Detect circular dependencies in resolved resources.
        
        Returns a list of circular dependency paths.
        """
        cycles: list[list[ResourceRef]] = []
        visited: set[ResourceRef] = set()
        path: list[ResourceRef] = []

        def dfs(ref: ResourceRef) -> None:
            if ref in path:
                # Found a cycle
                cycle_start = path.index(ref)
                cycle = path[cycle_start:] + [ref]
                cycles.append(cycle)
                return

            if ref in visited:
                return

            visited.add(ref)
            path.append(ref)

            # Follow relationships
            resolved = resolved_resources.get(ref)
            if resolved:
                for rel_ref in resolved.relationships:
                    if rel_ref in resolved_resources:
                        dfs(rel_ref)

            path.pop()

        # Check all resources
        for ref in resolved_resources:
            if ref not in visited:
                dfs(ref)

        return cycles

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": self.cache.size(),
            "ttl": self.cache.ttl,
            "hit_rate": getattr(self.cache, "_hit_count", 0) / max(getattr(self.cache, "_access_count", 1), 1),
        }

    def clear_cache(self) -> None:
        """Clear the resource cache."""
        self.cache.clear()
