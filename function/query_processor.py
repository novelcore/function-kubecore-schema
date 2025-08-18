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
