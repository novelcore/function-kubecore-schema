"""Query Processing Engine for KubeCore Platform Context Function.

This module implements intelligent query processing with resource-type-aware logic
and context-driven response generation.
"""

from __future__ import annotations

import logging
from typing import Any

from .resource_resolver import ResourceResolver
from .schema_registry import SchemaRegistry
from .resource_summarizer import ResourceSummarizer


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

    async def process_query(self, input_spec: dict[str, Any]) -> dict[str, Any]:
        """Process query and generate response.
        
        Args:
            input_spec: Input specification containing query and context
            
        Returns:
            Processed platform context response
        """
        query = input_spec.get("query", {})
        context = input_spec.get("context", {})
        
        resource_type = query.get("resourceType")
        if not resource_type:
            raise ValueError("resourceType is required in query")

        self.logger.info(f"Processing query for resource type: {resource_type}")

        # Route to specific processing logic based on resource type
        if resource_type == "XApp":
            return await self._process_app_query(input_spec)
        elif resource_type == "XKubeSystem":
            return await self._process_kubesystem_query(input_spec)
        elif resource_type == "XKubEnv":
            return await self._process_kubenv_query(input_spec)
        else:
            return await self._process_generic_query(input_spec)

    async def _process_app_query(self, input_spec: dict[str, Any]) -> dict[str, Any]:
        """Process XApp-specific query.
        
        XApp queries focus on deployment environments and resource optimization.
        """
        query = input_spec.get("query", {})
        context = input_spec.get("context", {})
        
        # Get available schemas for XApp
        accessible_schemas = self.schema_registry.get_accessible_schemas("XApp")
        requested_schemas = query.get("requestedSchemas", [])
        
        # Filter to only requested schemas that are accessible
        target_schemas = [
            schema for schema in requested_schemas 
            if schema in accessible_schemas
        ]
        
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
        
        # Process each requested schema
        for schema_type in target_schemas:
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
        
        target_schemas = [
            schema for schema in requested_schemas 
            if schema in accessible_schemas
        ]
        
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
        
        target_schemas = [
            schema for schema in requested_schemas 
            if schema in accessible_schemas
        ]
        
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