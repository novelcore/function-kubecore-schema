"""Query Processing Engine for KubeCore Platform Context Function.

This module implements intelligent query processing with resource-type-aware logic
and context-driven response generation.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .resource_resolver import ResourceResolver
from .resource_summarizer import ResourceSummarizer
from .schema_registry import SchemaRegistry
from .transitive_discovery import TransitiveDiscoveryEngine, TransitiveDiscoveryConfig


class QueryProcessor:
    """Processes queries with resource-type-specific logic."""

    def __init__(
        self,
        schema_registry: SchemaRegistry,
        resource_resolver: ResourceResolver,
        resource_summarizer: ResourceSummarizer,
    ):
        """Initialize the query processor.
        
        Args:
            schema_registry: Registry for schema information
            resource_resolver: Resolver for resource relationships
            resource_summarizer: Summarizer for resource data
        """
        self.schema_registry = schema_registry
        self.resource_resolver = resource_resolver
        self.resource_summarizer = resource_summarizer
        self.logger = logging.getLogger(__name__)
        self.logger.debug("QueryProcessor initialized")

        # Phase 4 components (set by main function)
        self.cache: Any | None = None
        self.performance_optimizer: Any | None = None
        
        # Transitive discovery engine
        self.transitive_discovery_engine: TransitiveDiscoveryEngine | None = None

    async def process_query(self, input_spec: dict[str, Any]) -> dict[str, Any]:
        """Process query and generate response with Phase 4 optimizations.
        
        Args:
            input_spec: Input specification containing query and context
            
        Returns:
            Processed platform context response
        """
        start_time = time.time()
        query = input_spec.get("query", {})
        context = input_spec.get("context", {})
        
        self.logger.debug(f"Processing query: {query}")
        self.logger.debug(f"Context: {context}")

        resource_type = query.get("resourceType")
        if not resource_type:
            self.logger.error("resourceType is required in query")
            raise ValueError("resourceType is required in query")

        self.logger.info(f"Processing query for resource type: {resource_type}")

        # Route to specific processing logic based on resource type
        try:
            if resource_type == "XApp":
                result = await self._process_app_query(input_spec)
            elif resource_type == "XKubeSystem":
                result = await self._process_kubesystem_query(input_spec)
            elif resource_type == "XKubEnv":
                result = await self._process_kubenv_query(input_spec)
            else:
                result = await self._process_generic_query(input_spec)

            # Perform reverse discovery if required
            if context.get("requiresReverseDiscovery") and "discoveryHints" in context:
                await self._perform_reverse_discovery(result, context)
            
            # Perform transitive discovery if enabled and engine available
            transitive_enabled = context.get("enableTransitiveDiscovery", True)
            has_engine = self.transitive_discovery_engine is not None
            self.logger.info(f"Transitive discovery check: enabled={transitive_enabled}, has_engine={has_engine}")
            
            if transitive_enabled and has_engine:
                self.logger.info(f"Starting transitive discovery for {resource_type}")
                await self._perform_transitive_discovery(result, context, resource_type)
            else:
                self.logger.info(f"Skipping transitive discovery: enabled={transitive_enabled}, has_engine={has_engine}")

            duration = time.time() - start_time
            self.logger.debug(f"Query processing completed in {duration*1000:.1f}ms")
            return result

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Query processing failed after {duration*1000:.1f}ms: {e}")
            raise

    async def _process_app_query(self, input_spec: dict[str, Any]) -> dict[str, Any]:
        """Process XApp-specific query.
        
        XApp queries focus on deployment environments and resource optimization.
        """
        query = input_spec.get("query", {})
        context = input_spec.get("context", {})

        # Get available schemas for XApp
        accessible_schemas = self.schema_registry.get_accessible_schemas("XApp")
        requested_schemas = query.get("requestedSchemas", [])

        self.logger.debug(f"XApp accessible schemas: {accessible_schemas}")
        self.logger.debug(f"XApp requested schemas: {requested_schemas}")

        # Map requested schema names to actual schema names and check accessibility
        target_schemas = []
        for schema in requested_schemas:
            actual_schema_name = self._map_requested_to_actual_schema(schema)
            if actual_schema_name in accessible_schemas:
                target_schemas.append(schema)

        self.logger.debug(f"XApp target schemas: {target_schemas}")

        # Build platform context
        platform_context = {
            "requestor": {
                "type": "XApp",
                "name": context.get("requestorName", "unknown"),
                "namespace": context.get("requestorNamespace", "default")
            },
            "availableSchemas": {},
            "relationships": {"direct": []},
            "insights": {}
        }

        # Process schemas in parallel for better performance
        if target_schemas and self.performance_optimizer:
            try:
                # Use parallel processing for multiple schemas
                await self._process_schemas_parallel(
                    target_schemas, context, platform_context, "app"
                )
            except Exception as e:
                self.logger.warning(f"Parallel schema processing failed, falling back to sequential: {e}")
                # Fallback to sequential processing
                for schema_type in target_schemas:
                    await self._process_schema_for_app(
                        schema_type, context, platform_context
                    )
        else:
            # Sequential processing fallback
            for schema_type in target_schemas:
                await self._process_schema_for_app(
                    schema_type, context, platform_context
                )

        # Also process schemas even if no references exist (for empty reference test)
        for schema_type in requested_schemas:
            if schema_type not in platform_context["availableSchemas"] and schema_type in accessible_schemas:
                await self._process_schema_for_app(
                    schema_type, context, platform_context
                )

        # Add XApp-specific relationship information
        platform_context["relationships"]["direct"].extend([
            {
                "type": "kubEnv",
                "cardinality": "N:N",
                "description": "App can deploy to multiple environments"
            },
            {
                "type": "githubProject",
                "cardinality": "1:1",
                "description": "App belongs to a GitHub project"
            }
        ])

        return platform_context

    async def _process_kubesystem_query(self, input_spec: dict[str, Any]) -> dict[str, Any]:
        """Process XKubeSystem-specific query.
        
        XKubeSystem queries focus on cluster infrastructure and system components.
        """
        query = input_spec.get("query", {})
        context = input_spec.get("context", {})

        accessible_schemas = self.schema_registry.get_accessible_schemas("XKubeSystem")
        requested_schemas = query.get("requestedSchemas", [])

        self.logger.debug(f"XKubeSystem accessible schemas: {accessible_schemas}")
        self.logger.debug(f"XKubeSystem requested schemas: {requested_schemas}")

        # Map requested schema names to actual schema names and check accessibility
        target_schemas = []
        for schema in requested_schemas:
            actual_schema_name = self._map_requested_to_actual_schema(schema)
            if actual_schema_name in accessible_schemas:
                target_schemas.append(schema)

        self.logger.debug(f"XKubeSystem target schemas: {target_schemas}")

        platform_context = {
            "requestor": {
                "type": "XKubeSystem",
                "name": context.get("requestorName", "unknown"),
                "namespace": context.get("requestorNamespace", "default")
            },
            "availableSchemas": {},
            "relationships": {"direct": []},
            "insights": {}
        }

        # Process each requested schema
        for schema_type in target_schemas:
            await self._process_schema_for_kubesystem(
                schema_type, context, platform_context
            )

        # Also process schemas even if no references exist
        for schema_type in requested_schemas:
            if schema_type not in platform_context["availableSchemas"] and schema_type in accessible_schemas:
                await self._process_schema_for_kubesystem(
                    schema_type, context, platform_context
                )

        # Add XKubeSystem-specific relationships
        platform_context["relationships"]["direct"].extend([
            {
                "type": "kubeCluster",
                "cardinality": "1:1",
                "description": "System belongs to a cluster"
            },
            {
                "type": "kubEnv",
                "cardinality": "1:N",
                "description": "System hosts multiple environments"
            }
        ])

        return platform_context

    async def _process_kubenv_query(self, input_spec: dict[str, Any]) -> dict[str, Any]:
        """Process XKubEnv-specific query.
        
        XKubEnv queries focus on environment configuration and resource constraints.
        """
        query = input_spec.get("query", {})
        context = input_spec.get("context", {})

        accessible_schemas = self.schema_registry.get_accessible_schemas("XKubEnv")
        requested_schemas = query.get("requestedSchemas", [])

        self.logger.debug(f"XKubEnv accessible schemas: {accessible_schemas}")
        self.logger.debug(f"XKubEnv requested schemas: {requested_schemas}")

        # Map requested schema names to actual schema names and check accessibility
        target_schemas = []
        for schema in requested_schemas:
            actual_schema_name = self._map_requested_to_actual_schema(schema)
            if actual_schema_name in accessible_schemas:
                target_schemas.append(schema)

        self.logger.debug(f"XKubEnv target schemas: {target_schemas}")

        platform_context = {
            "requestor": {
                "type": "XKubEnv",
                "name": context.get("requestorName", "unknown"),
                "namespace": context.get("requestorNamespace", "default")
            },
            "availableSchemas": {},
            "relationships": {"direct": []},
            "insights": {}
        }

        # Process each requested schema
        for schema_type in target_schemas:
            await self._process_schema_for_kubenv(
                schema_type, context, platform_context
            )

        # Also process schemas even if no references exist
        for schema_type in requested_schemas:
            if schema_type not in platform_context["availableSchemas"] and schema_type in accessible_schemas:
                await self._process_schema_for_kubenv(
                    schema_type, context, platform_context
                )

        # Add XKubEnv-specific relationships
        platform_context["relationships"]["direct"].extend([
            {
                "type": "kubeCluster",
                "cardinality": "1:1",
                "description": "Environment runs on a cluster"
            },
            {
                "type": "qualityGate",
                "cardinality": "N:N",
                "description": "Environment applies quality gates"
            }
        ])

        return platform_context

    async def _process_generic_query(self, input_spec: dict[str, Any]) -> dict[str, Any]:
        """Process generic query for other resource types."""
        query = input_spec.get("query", {})
        context = input_spec.get("context", {})
        resource_type = query.get("resourceType")

        accessible_schemas = self.schema_registry.get_accessible_schemas(resource_type)
        requested_schemas = query.get("requestedSchemas", [])

        target_schemas = [
            schema for schema in requested_schemas
            if schema in accessible_schemas
        ]

        platform_context = {
            "requestor": {
                "type": resource_type,
                "name": context.get("requestorName", "unknown"),
                "namespace": context.get("requestorNamespace", "default")
            },
            "availableSchemas": {},
            "relationships": {"direct": []},
            "insights": {}
        }

        # Process each requested schema
        for schema_type in target_schemas:
            await self._process_schema_generic(
                schema_type, context, platform_context
            )

        # Also process schemas even if no references exist
        for schema_type in requested_schemas:
            if schema_type not in platform_context["availableSchemas"] and schema_type in accessible_schemas:
                await self._process_schema_generic(
                    schema_type, context, platform_context
                )

        return platform_context

    async def _process_schema_for_app(
        self,
        schema_type: str,
        context: dict[str, Any],
        platform_context: dict[str, Any],
    ) -> None:
        """Process a specific schema for XApp queries."""
        # Map requested schema name to actual schema name
        actual_schema_name = self._map_requested_to_actual_schema(schema_type)
        schema_info = self.schema_registry.get_schema_info(actual_schema_name)
        if not schema_info:
            return

        # Get instances from context references
        ref_key = f"{schema_type}Refs"
        refs = context.get("references", {}).get(ref_key, [])

        instances = []
        for ref in refs:
            # Create summary based on schema type and XApp needs
            if schema_type == "kubEnv":
                summary = await self._create_kubenv_summary_for_app(ref)
            elif schema_type == "githubProject":
                summary = await self._create_project_summary_for_app(ref)
            else:
                summary = await self._create_generic_summary(ref)

            instances.append({
                "name": ref.get("name", "unknown"),
                "namespace": ref.get("namespace", "default"),
                "summary": summary
            })

        # Use the requested schema name as the key, not the actual schema name
        platform_context["availableSchemas"][schema_type] = {
            "metadata": {
                "apiVersion": schema_info.api_version,
                "kind": schema_info.kind,
                "accessible": True,
                "relationshipPath": ["app", schema_type]
            },
            "instances": instances
        }

    async def _process_schema_for_kubesystem(
        self,
        schema_type: str,
        context: dict[str, Any],
        platform_context: dict[str, Any],
    ) -> None:
        """Process a specific schema for XKubeSystem queries."""
        # Map requested schema name to actual schema name
        actual_schema_name = self._map_requested_to_actual_schema(schema_type)
        schema_info = self.schema_registry.get_schema_info(actual_schema_name)
        if not schema_info:
            return

        ref_key = f"{schema_type}Refs"
        refs = context.get("references", {}).get(ref_key, [])

        instances = []
        for ref in refs:
            if schema_type == "kubeCluster":
                summary = await self._create_cluster_summary_for_system(ref)
            elif schema_type == "kubEnv":
                summary = await self._create_kubenv_summary_for_system(ref)
            else:
                summary = await self._create_generic_summary(ref)

            instances.append({
                "name": ref.get("name", "unknown"),
                "namespace": ref.get("namespace", "default"),
                "summary": summary
            })

        platform_context["availableSchemas"][schema_type] = {
            "metadata": {
                "apiVersion": schema_info.api_version,
                "kind": schema_info.kind,
                "accessible": True,
                "relationshipPath": ["kubeSystem", schema_type]
            },
            "instances": instances
        }

    async def _process_schema_for_kubenv(
        self,
        schema_type: str,
        context: dict[str, Any],
        platform_context: dict[str, Any],
    ) -> None:
        """Process a specific schema for XKubEnv queries."""
        # Map requested schema name to actual schema name
        actual_schema_name = self._map_requested_to_actual_schema(schema_type)
        schema_info = self.schema_registry.get_schema_info(actual_schema_name)
        if not schema_info:
            return

        ref_key = f"{schema_type}Refs"
        refs = context.get("references", {}).get(ref_key, [])

        instances = []
        for ref in refs:
            if schema_type == "qualityGate":
                summary = await self._create_quality_gate_summary(ref)
            elif schema_type == "kubeCluster":
                summary = await self._create_cluster_summary_for_env(ref)
            else:
                summary = await self._create_generic_summary(ref)

            instances.append({
                "name": ref.get("name", "unknown"),
                "namespace": ref.get("namespace", "default"),
                "summary": summary
            })

        platform_context["availableSchemas"][schema_type] = {
            "metadata": {
                "apiVersion": schema_info.api_version,
                "kind": schema_info.kind,
                "accessible": True,
                "relationshipPath": ["kubEnv", schema_type]
            },
            "instances": instances
        }

    async def _process_schema_generic(
        self,
        schema_type: str,
        context: dict[str, Any],
        platform_context: dict[str, Any],
    ) -> None:
        """Process a schema for generic resource types."""
        # Map requested schema name to actual schema name
        actual_schema_name = self._map_requested_to_actual_schema(schema_type)
        schema_info = self.schema_registry.get_schema_info(actual_schema_name)
        if not schema_info:
            return

        ref_key = f"{schema_type}Refs"
        refs = context.get("references", {}).get(ref_key, [])

        instances = []
        for ref in refs:
            summary = await self._create_generic_summary(ref)
            instances.append({
                "name": ref.get("name", "unknown"),
                "namespace": ref.get("namespace", "default"),
                "summary": summary
            })

        platform_context["availableSchemas"][schema_type] = {
            "metadata": {
                "apiVersion": schema_info.api_version,
                "kind": schema_info.kind,
                "accessible": True,
                "relationshipPath": ["generic", schema_type]
            },
            "instances": instances
        }

    async def _create_kubenv_summary_for_app(self, ref: dict[str, Any]) -> dict[str, Any]:
        """Create KubEnv summary optimized for XApp needs."""
        return {
            "environmentType": "dev",  # Would be resolved from actual resource
            "resources": {
                "profile": "small",
                "defaults": {
                    "requests": {"cpu": "100m", "memory": "128Mi"},
                    "limits": {"cpu": "500m", "memory": "512Mi"}
                }
            },
            "qualityGates": ["security-scan", "performance-test"]
        }

    async def _create_project_summary_for_app(self, ref: dict[str, Any]) -> dict[str, Any]:
        """Create GitHub project summary for XApp needs."""
        return {
            "repository": ref.get("name", "unknown"),
            "visibility": "private",
            "cicdEnabled": True
        }

    async def _create_cluster_summary_for_system(self, ref: dict[str, Any]) -> dict[str, Any]:
        """Create cluster summary for XKubeSystem needs."""
        return {
            "version": "1.28.0",
            "region": "us-west-2",
            "nodeCount": 3,
            "status": "ready"
        }

    async def _create_kubenv_summary_for_system(self, ref: dict[str, Any]) -> dict[str, Any]:
        """Create KubEnv summary for XKubeSystem needs."""
        return {
            "environmentType": "dev",
            "resources": {"profile": "small"},
            "systemComponents": ["ingress", "monitoring"]
        }

    async def _create_cluster_summary_for_env(self, ref: dict[str, Any]) -> dict[str, Any]:
        """Create cluster summary for XKubEnv needs."""
        return {
            "version": "1.28.0",
            "capacity": {
                "cpu": "16",
                "memory": "64Gi",
                "storage": "1000Gi"
            }
        }

    async def _create_quality_gate_summary(self, ref: dict[str, Any]) -> dict[str, Any]:
        """Create quality gate summary."""
        return {
            "key": ref.get("name", "unknown"),
            "category": "security",
            "severity": "high",
            "required": True
        }

    async def _create_generic_summary(self, ref: dict[str, Any]) -> dict[str, Any]:
        """Create a generic summary for any resource type."""
        return {
            "name": ref.get("name", "unknown"),
            "status": "available"
        }

    def _map_requested_to_actual_schema(self, requested_name: str) -> str:
        """Map requested schema names to actual schema names in the registry."""
        # Mapping from common request names to actual schema names
        schema_name_mapping = {
            "kubEnv": "XKubEnv",
            "kubeCluster": "XKubeCluster",
            "kubeSystem": "XKubeSystem",
            "kubeNet": "XKubeNet",
            "qualityGate": "XQualityGate",
            "githubProject": "XGitHubProject",
            "githubProvider": "XGitHubProvider",
            "githubApp": "XGitHubApp",
            "app": "XApp"
        }

        return schema_name_mapping.get(requested_name, requested_name)

    async def _discover_reverse_relationships(
        self,
        target_ref: dict[str, Any],
        resource_type: str,
        context: dict[str, Any]
    ) -> dict[str, list[dict]]:
        """
        Discover resources that reference the target resource.
        
        For XGitHubProject, search: XKubeCluster, XKubEnv, XApp, XGitHubApp
        For XKubeCluster, search: XKubeSystem, XKubEnv
        For XKubeNet, search: XKubeCluster
        
        Args:
            target_ref: Target resource reference (name, namespace)
            resource_type: Type of the target resource
            context: Request context
            
        Returns:
            Dictionary of discovered reverse references
        """
        # Define reverse discovery mapping
        reverse_discovery_map = {
            "XGitHubProject": [
                ("XKubeCluster", "platform.kubecore.io/v1alpha1", "githubProjectRef"),
                ("XKubEnv", "platform.kubecore.io/v1alpha1", "githubProjectRef"), 
                ("XApp", "app.kubecore.io/v1alpha1", "githubProjectRef"),
                ("XGitHubApp", "github.platform.kubecore.io/v1alpha1", "githubProjectRef"),
                ("XQualityGate", "platform.kubecore.io/v1alpha1", "githubProjectRef")
            ],
            "XKubeCluster": [
                ("XKubeSystem", "platform.kubecore.io/v1alpha1", "kubeClusterRef"),
                ("XKubEnv", "platform.kubecore.io/v1alpha1", "kubeClusterRef")
            ],
            "XKubeNet": [
                ("XKubeCluster", "platform.kubecore.io/v1alpha1", "kubeNetRef")
            ],
            "XQualityGate": [
                ("XKubEnv", "platform.kubecore.io/v1alpha1", "qualityGates"),
                ("XApp", "app.kubecore.io/v1alpha1", "qualityGates")
            ]
        }
        
        if resource_type not in reverse_discovery_map:
            return {}
            
        target_name = target_ref.get("name")
        target_namespace = target_ref.get("namespace")
        
        if not target_name:
            return {}
            
        discovered_refs = {}
        search_configs = reverse_discovery_map[resource_type]
        
        # Process searches in parallel if performance optimizer is available
        if self.performance_optimizer and len(search_configs) > 1:
            try:
                import asyncio
                tasks = [
                    self._search_for_reverse_refs(
                        target_name, target_namespace, kind, api_version, ref_field
                    ) 
                    for kind, api_version, ref_field in search_configs
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.logger.warning(f"Reverse discovery search failed: {result}")
                        continue
                    kind = search_configs[i][0]
                    ref_type = self._kind_to_ref_type(kind)
                    if result and ref_type:
                        discovered_refs[ref_type] = result
                        
            except Exception as e:
                self.logger.warning(f"Parallel reverse discovery failed, using sequential: {e}")
                # Fall back to sequential processing
                for kind, api_version, ref_field in search_configs:
                    try:
                        refs = await self._search_for_reverse_refs(
                            target_name, target_namespace, kind, api_version, ref_field
                        )
                        ref_type = self._kind_to_ref_type(kind)
                        if refs and ref_type:
                            discovered_refs[ref_type] = refs
                    except Exception as e:
                        self.logger.warning(f"Sequential reverse discovery failed for {kind}: {e}")
        else:
            # Sequential processing
            for kind, api_version, ref_field in search_configs:
                try:
                    refs = await self._search_for_reverse_refs(
                        target_name, target_namespace, kind, api_version, ref_field
                    )
                    ref_type = self._kind_to_ref_type(kind)
                    if refs and ref_type:
                        discovered_refs[ref_type] = refs
                except Exception as e:
                    self.logger.warning(f"Reverse discovery failed for {kind}: {e}")
                    
        return discovered_refs

    async def _search_for_reverse_refs(
        self,
        target_name: str,
        target_namespace: str | None,
        search_kind: str,
        search_api_version: str,
        ref_field: str
    ) -> list[dict]:
        """
        Search for resources of a specific kind that reference the target.
        
        Args:
            target_name: Name of target resource
            target_namespace: Namespace of target resource
            search_kind: Kind of resources to search
            search_api_version: API version of resources to search
            ref_field: Reference field to check
            
        Returns:
            List of resource references that point to target
        """
        found_refs = []
        
        try:
            # List all resources of the search kind
            list_result = await self.resource_resolver.k8s_client.list_resources(
                api_version=search_api_version,
                kind=search_kind,
                limit=100  # Reasonable limit to avoid excessive API calls
            )
            
            items = list_result.get("items", [])
            self.logger.debug(f"Searching {len(items)} {search_kind} resources for refs to {target_name}")
            
            for item in items:
                if self._contains_reference_to(item, target_name, target_namespace, ref_field):
                    metadata = item.get("metadata", {})
                    found_refs.append({
                        "name": metadata.get("name"),
                        "namespace": metadata.get("namespace"),
                        "apiVersion": search_api_version,
                        "kind": search_kind
                    })
                    
            self.logger.debug(f"Found {len(found_refs)} {search_kind} resources referencing {target_name}")
            
        except Exception as e:
            self.logger.warning(f"Failed to search {search_kind} for references to {target_name}: {e}")
            
        return found_refs
        
    def _contains_reference_to(self, resource: dict, target_name: str, target_namespace: str | None, ref_field: str) -> bool:
        """
        Check if resource contains reference to target.
        
        Args:
            resource: Resource to check
            target_name: Name of target resource
            target_namespace: Namespace of target resource  
            ref_field: Reference field to check
            
        Returns:
            True if resource contains reference to target
        """
        spec = resource.get("spec", {})
        
        # Handle direct reference fields (e.g., githubProjectRef)
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
                        ref_obj = ref_item.get("ref", ref_item)  # Handle both ref.ref and direct ref structures
                        if isinstance(ref_obj, dict):
                            if (ref_obj.get("name") == target_name and 
                               (target_namespace is None or ref_obj.get("namespace") == target_namespace)):
                                return True
        
        return False
        
    def _kind_to_ref_type(self, kind: str) -> str | None:
        """Convert Kubernetes kind to reference type."""
        kind_to_ref_map = {
            "XKubeCluster": "kubeClusterRefs",
            "XKubEnv": "kubEnvRefs", 
            "XApp": "appRefs",
            "XGitHubApp": "githubAppRefs",
            "XQualityGate": "qualityGateRefs",
            "XKubeSystem": "kubeSystemRefs"
        }
        return kind_to_ref_map.get(kind)

    async def _perform_reverse_discovery(self, platform_context: dict[str, Any], context: dict[str, Any]) -> None:
        """
        Perform reverse discovery and merge results into platform context.
        
        Args:
            platform_context: Platform context to update with reverse discovery results
            context: Request context containing discovery hints
        """
        hints = context.get("discoveryHints", {})
        target_ref = hints.get("targetRef", {})
        
        if not target_ref.get("name"):
            self.logger.warning("No target reference found for reverse discovery")
            return
            
        resource_type = target_ref.get("kind", "")
        self.logger.info(f"Performing reverse discovery for {resource_type}: {target_ref.get('name')}")
        
        try:
            # Discover reverse relationships
            discovered_refs = await self._discover_reverse_relationships(
                target_ref, resource_type, context
            )
            
            # Merge discovered references into platform context
            if discovered_refs:
                # Update the context references with discovered reverse references
                context.setdefault("references", {}).update(discovered_refs)
                
                # Process the newly discovered schemas
                for ref_type, refs in discovered_refs.items():
                    if refs:  # Only process if we have actual references
                        schema_type = ref_type.replace("Refs", "")  # Convert appRefs -> app
                        await self._process_discovered_schema(
                            schema_type, refs, platform_context
                        )
                        
                self.logger.info(f"Reverse discovery completed: found {sum(len(refs) for refs in discovered_refs.values())} references across {len(discovered_refs)} types")
            else:
                self.logger.debug(f"No reverse references found for {resource_type}: {target_ref.get('name')}")
                
        except Exception as e:
            self.logger.warning(f"Reverse discovery failed: {e}")

    async def _process_discovered_schema(
        self,
        schema_type: str,
        refs: list[dict],
        platform_context: dict[str, Any]
    ) -> None:
        """
        Process a schema discovered through reverse discovery.
        
        Args:
            schema_type: Type of schema to process (e.g., 'app', 'kubEnv')
            refs: List of discovered references
            platform_context: Platform context to update
        """
        # Map requested schema name to actual schema name
        actual_schema_name = self._map_requested_to_actual_schema(schema_type)
        schema_info = self.schema_registry.get_schema_info(actual_schema_name)
        if not schema_info:
            self.logger.warning(f"Schema info not found for {actual_schema_name}")
            return

        instances = []
        for ref in refs:
            # Create summary based on the resource type
            summary = await self._create_reverse_discovered_summary(ref)
            instances.append({
                "name": ref.get("name", "unknown"),
                "namespace": ref.get("namespace", "default"),
                "summary": summary
            })

        # Add to platform context
        platform_context["availableSchemas"][schema_type] = {
            "metadata": {
                "apiVersion": schema_info.api_version,
                "kind": schema_info.kind,
                "accessible": True,
                "relationshipPath": ["reverse", schema_type],
                "discoveryMethod": "reverse"
            },
            "instances": instances
        }
        
        self.logger.debug(f"Added {len(instances)} instances for schema {schema_type} via reverse discovery")

    async def _create_reverse_discovered_summary(self, ref: dict[str, Any]) -> dict[str, Any]:
        """Create summary for reverse-discovered resource."""
        return {
            "name": ref.get("name", "unknown"),
            "kind": ref.get("kind", "unknown"),
            "status": "discovered",
            "discoveredBy": "reverse-lookup"
        }

    async def _process_schemas_parallel(
        self,
        schema_types: list[str],
        context: dict[str, Any],
        platform_context: dict[str, Any],
        resource_category: str
    ) -> None:
        """Process multiple schemas in parallel using the performance optimizer.
        
        Args:
            schema_types: List of schema types to process
            context: Request context
            platform_context: Platform context to update
            resource_category: Category of resource (app, kubesystem, kubenv, generic)
        """
        if not self.performance_optimizer or not schema_types:
            return

        # Define processor function based on resource category
        async def process_single_schema(schema_type: str) -> tuple[str, dict[str, Any]]:
            temp_context = {"availableSchemas": {}}

            if resource_category == "app":
                await self._process_schema_for_app(schema_type, context, temp_context)
            elif resource_category == "kubesystem":
                await self._process_schema_for_kubesystem(schema_type, context, temp_context)
            elif resource_category == "kubenv":
                await self._process_schema_for_kubenv(schema_type, context, temp_context)
            else:
                await self._process_schema_generic(schema_type, context, temp_context)

            return schema_type, temp_context.get("availableSchemas", {}).get(schema_type)

        # Process schemas in parallel
        try:
            import asyncio
            tasks = [process_single_schema(schema_type) for schema_type in schema_types]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Merge results into platform_context
            for result in results:
                if isinstance(result, Exception):
                    self.logger.warning(f"Schema processing error: {result}")
                    continue

                schema_type, schema_data = result
                if schema_data:
                    platform_context["availableSchemas"][schema_type] = schema_data

        except Exception as e:
            self.logger.error(f"Parallel schema processing failed: {e}")
            raise

    async def _perform_transitive_discovery(
        self,
        platform_context: dict[str, Any],
        context: dict[str, Any],
        resource_type: str
    ) -> None:
        """
        Perform transitive discovery and merge results into platform context.
        
        Args:
            platform_context: Platform context to update with transitive discovery results
            context: Request context
            resource_type: Type of resource being queried
        """
        if not self.transitive_discovery_engine:
            return
            
        # Extract target reference for transitive discovery
        requestor = platform_context.get("requestor", {})
        target_ref = {
            "name": requestor.get("name", "unknown"),
            "namespace": requestor.get("namespace", "default"),
            "kind": resource_type,
            "apiVersion": self._get_api_version_for_kind(resource_type)
        }
        
        self.logger.info(f"Performing transitive discovery for {resource_type}: {target_ref.get('name')}")
        
        try:
            # Discover transitive relationships
            transitive_resources = await self.transitive_discovery_engine.discover_transitive_relationships(
                target_ref, resource_type, context
            )
            
            # Merge transitive discoveries into platform context
            if transitive_resources:
                for schema_type, resources in transitive_resources.items():
                    if resources:  # Only process if we have actual resources
                        await self._process_transitive_schema(
                            schema_type, resources, platform_context
                        )
                        
                self.logger.info(f"Transitive discovery completed: found {sum(len(resources) for resources in transitive_resources.values())} resources across {len(transitive_resources)} types")
            else:
                self.logger.debug(f"No transitive relationships found for {resource_type}: {target_ref.get('name')}")
                
        except Exception as e:
            self.logger.warning(f"Transitive discovery failed: {e}")

    async def _process_transitive_schema(
        self,
        schema_type: str,
        transitive_resources: list,
        platform_context: dict[str, Any]
    ) -> None:
        """
        Process a schema discovered through transitive discovery.
        
        Args:
            schema_type: Type of schema to process (e.g., 'app', 'kubEnv')
            transitive_resources: List of TransitiveDiscoveredResource objects
            platform_context: Platform context to update
        """
        # Map requested schema name to actual schema name
        actual_schema_name = self._map_requested_to_actual_schema(schema_type)
        schema_info = self.schema_registry.get_schema_info(actual_schema_name)
        if not schema_info:
            self.logger.warning(f"Schema info not found for {actual_schema_name}")
            return

        instances = []
        for transitive_resource in transitive_resources:
            # Create instance data with transitive information
            instance_data = {
                "name": transitive_resource.name,
                "namespace": transitive_resource.namespace,
                "summary": {
                    **transitive_resource.summary,
                    "discoveryHops": transitive_resource.discovery_hops,
                    "discoveryMethod": transitive_resource.discovery_method,
                    "relationshipChain": " → ".join(
                        f"{ref.kind}({ref.name})" for ref in transitive_resource.relationship_path
                    )
                }
            }
            
            # Add intermediate resources information if present
            if transitive_resource.intermediate_resources:
                instance_data["summary"]["intermediateResources"] = [
                    {
                        "kind": ref.kind,
                        "name": ref.name,
                        "namespace": ref.namespace
                    }
                    for ref in transitive_resource.intermediate_resources
                ]
            
            instances.append(instance_data)

        # Check if schema already exists in platform context
        if schema_type in platform_context["availableSchemas"]:
            # Merge with existing instances, avoiding duplicates
            existing_instances = platform_context["availableSchemas"][schema_type]["instances"]
            existing_names = {(inst["name"], inst["namespace"]) for inst in existing_instances}
            
            new_instances = [
                inst for inst in instances
                if (inst["name"], inst["namespace"]) not in existing_names
            ]
            
            if new_instances:
                existing_instances.extend(new_instances)
                # Update metadata to indicate transitive discovery was used
                platform_context["availableSchemas"][schema_type]["metadata"]["discoveryMethod"] = "hybrid"
        else:
            # Add new schema entry
            platform_context["availableSchemas"][schema_type] = {
                "metadata": {
                    "apiVersion": schema_info.api_version,
                    "kind": schema_info.kind,
                    "accessible": True,
                    "relationshipPath": ["transitive", schema_type],
                    "discoveryMethod": "transitive"
                },
                "instances": instances
            }
        
        self.logger.debug(f"Added {len(instances)} transitive instances for schema {schema_type}")

    def _get_api_version_for_kind(self, kind: str) -> str:
        """Get the API version for a given Kubernetes kind."""
        api_version_map = {
            "XApp": "app.kubecore.io/v1alpha1",
            "XKubeSystem": "platform.kubecore.io/v1alpha1",
            "XKubEnv": "platform.kubecore.io/v1alpha1",
            "XKubeCluster": "platform.kubecore.io/v1alpha1",
            "XGitHubProject": "github.platform.kubecore.io/v1alpha1",
            "XGitHubApp": "github.platform.kubecore.io/v1alpha1",
            "XQualityGate": "platform.kubecore.io/v1alpha1"
        }
        return api_version_map.get(kind, "unknown")

    def set_transitive_discovery_engine(self, engine: TransitiveDiscoveryEngine) -> None:
        """Set the transitive discovery engine instance."""
        self.transitive_discovery_engine = engine
        self.logger.debug("Transitive discovery engine configured")
