"""Response Generation Engine for KubeCore Platform Context Function.

This module implements standardized response generation with schema filtering
and format compliance according to the KubeCore specification.
"""

from __future__ import annotations

import logging
from typing import Any

from .schema_registry import SchemaRegistry


class ResponseGenerator:
    """Generates standardized platform context responses."""

    def __init__(self, schema_registry: SchemaRegistry):
        """Initialize the response generator.
        
        Args:
            schema_registry: Registry for schema information and filtering
        """
        self.schema_registry = schema_registry
        self.logger = logging.getLogger(__name__)

    def generate_response(
        self,
        platform_context: dict[str, Any],
        query: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate standardized response in KubeCore format.
        
        Args:
            platform_context: Processed platform context data
            query: Original query parameters
            
        Returns:
            Standardized response matching KubeCore specification
        """
        resource_type = query.get("resourceType")
        
        # Filter schemas based on resource type needs
        filtered_schemas = self._filter_schemas_for_resource_type(
            platform_context.get("availableSchemas", {}),
            resource_type
        )
        
        # Generate insights for the resource type
        insights = self._generate_insights_for_response(platform_context, resource_type)
        
        # Build the standardized response
        response = {
            "apiVersion": "context.fn.kubecore.io/v1beta1",
            "kind": "Output",
            "spec": {
                "platformContext": {
                    "requestor": platform_context.get("requestor", {
                        "type": resource_type or "unknown",
                        "name": "unknown",
                        "namespace": "default"
                    }),
                    "availableSchemas": filtered_schemas,
                    "relationships": platform_context.get("relationships", {}),
                    "insights": insights
                }
            }
        }
        
        self.logger.debug(f"Generated response for {resource_type} with {len(filtered_schemas)} schemas")
        
        return response

    def _filter_schemas_for_resource_type(
        self,
        schemas: dict[str, Any],
        resource_type: str,
    ) -> dict[str, Any]:
        """Filter schemas based on resource type needs.
        
        Args:
            schemas: Available schemas to filter
            resource_type: Type of resource making the request
            
        Returns:
            Filtered schemas optimized for the resource type
        """
        filtered_schemas = {}
        
        for schema_name, schema_data in schemas.items():
            filtered_schema = self.filter_schema_for_resource_type(
                schema_data, resource_type
            )
            if filtered_schema:
                filtered_schemas[schema_name] = filtered_schema
        
        return filtered_schemas

    def filter_schema_for_resource_type(
        self,
        schema: dict[str, Any],
        resource_type: str,
    ) -> dict[str, Any]:
        """Filter individual schema based on resource type needs.
        
        Args:
            schema: Schema to filter
            resource_type: Type of resource making the request
            
        Returns:
            Filtered schema with relevant fields for the resource type
        """
        if not schema:
            return schema
        
        # Create a deep copy of the schema to avoid modifying the original
        filtered_schema = {
            "metadata": schema.get("metadata", {}),
            "instances": []
        }
        
        # Filter instances based on resource type
        instances = schema.get("instances", [])
        for instance in instances:
            filtered_instance = self._filter_instance_for_resource_type(
                instance, resource_type
            )
            if filtered_instance:
                filtered_schema["instances"].append(filtered_instance)
        
        return filtered_schema

    def _filter_instance_for_resource_type(
        self,
        instance: dict[str, Any],
        resource_type: str,
    ) -> dict[str, Any]:
        """Filter instance data based on resource type needs.
        
        Args:
            instance: Instance to filter
            resource_type: Type of resource making the request
            
        Returns:
            Filtered instance with relevant data
        """
        if not instance:
            return instance
        
        # Base instance structure
        filtered_instance = {
            "name": instance.get("name", "unknown"),
            "namespace": instance.get("namespace", "default"),
            "summary": {}
        }
        
        summary = instance.get("summary", {})
        
        # Filter summary based on resource type
        if resource_type == "XApp":
            # XApp needs deployment-relevant information
            filtered_summary = {}
            
            # Include environment and resource information
            if "environmentType" in summary:
                filtered_summary["environmentType"] = summary["environmentType"]
            
            if "resources" in summary:
                filtered_summary["resources"] = summary["resources"]
            
            if "environmentConfig" in summary:
                filtered_summary["environmentConfig"] = summary["environmentConfig"]
            
            if "qualityGates" in summary:
                filtered_summary["qualityGates"] = summary["qualityGates"]
            
            # Include deployment-specific fields
            if "repository" in summary:
                filtered_summary["repository"] = summary["repository"]
            
            if "cicdEnabled" in summary:
                filtered_summary["cicdEnabled"] = summary["cicdEnabled"]
            
            filtered_instance["summary"] = filtered_summary
            
        elif resource_type == "XKubeSystem":
            # XKubeSystem needs infrastructure information
            filtered_summary = {}
            
            if "version" in summary:
                filtered_summary["version"] = summary["version"]
            
            if "region" in summary:
                filtered_summary["region"] = summary["region"]
            
            if "nodeCount" in summary:
                filtered_summary["nodeCount"] = summary["nodeCount"]
            
            if "status" in summary:
                filtered_summary["status"] = summary["status"]
            
            if "systemComponents" in summary:
                filtered_summary["systemComponents"] = summary["systemComponents"]
            
            if "capacity" in summary:
                filtered_summary["capacity"] = summary["capacity"]
            
            filtered_instance["summary"] = filtered_summary
            
        elif resource_type == "XKubEnv":
            # XKubEnv needs environment configuration information
            filtered_summary = {}
            
            if "environmentType" in summary:
                filtered_summary["environmentType"] = summary["environmentType"]
            
            if "resources" in summary:
                filtered_summary["resources"] = summary["resources"]
            
            if "qualityGates" in summary:
                filtered_summary["qualityGates"] = summary["qualityGates"]
            
            if "capacity" in summary:
                filtered_summary["capacity"] = summary["capacity"]
            
            if "systemComponents" in summary:
                filtered_summary["systemComponents"] = summary["systemComponents"]
            
            filtered_instance["summary"] = filtered_summary
            
        else:
            # For other resource types, include all summary data
            filtered_instance["summary"] = summary
        
        return filtered_instance

    def _generate_insights_for_response(
        self,
        platform_context: dict[str, Any],
        resource_type: str,
    ) -> dict[str, Any]:
        """Generate insights section for the response.
        
        Args:
            platform_context: Platform context data
            resource_type: Type of resource making the request
            
        Returns:
            Insights dictionary with recommendations and suggestions
        """
        base_insights = platform_context.get("insights", {})
        
        # Add default insights if none exist
        if not base_insights.get("recommendations"):
            base_insights["recommendations"] = []
        
        if not base_insights.get("suggestedReferences"):
            base_insights["suggestedReferences"] = []
        
        if not base_insights.get("validationRules"):
            base_insights["validationRules"] = []
        
        return base_insights

    def validate_response_format(self, response: dict[str, Any]) -> bool:
        """Validate that response matches the expected format.
        
        Args:
            response: Response to validate
            
        Returns:
            True if response format is valid, False otherwise
        """
        try:
            # Check top-level structure
            if not isinstance(response, dict):
                return False
            
            if response.get("apiVersion") != "context.fn.kubecore.io/v1beta1":
                return False
            
            if response.get("kind") != "Output":
                return False
            
            # Check spec structure
            spec = response.get("spec", {})
            if not isinstance(spec, dict):
                return False
            
            platform_context = spec.get("platformContext", {})
            if not isinstance(platform_context, dict):
                return False
            
            # Check required fields in platformContext
            required_fields = ["requestor", "availableSchemas", "relationships", "insights"]
            for field in required_fields:
                if field not in platform_context:
                    return False
            
            # Check requestor structure
            requestor = platform_context.get("requestor", {})
            if not isinstance(requestor, dict):
                return False
            
            requestor_required = ["type", "name", "namespace"]
            for field in requestor_required:
                if field not in requestor:
                    return False
            
            # Check availableSchemas structure
            schemas = platform_context.get("availableSchemas", {})
            if not isinstance(schemas, dict):
                return False
            
            # Validate each schema structure
            for schema_name, schema_data in schemas.items():
                if not self._validate_schema_structure(schema_data):
                    return False
            
            # Check relationships structure
            relationships = platform_context.get("relationships", {})
            if not isinstance(relationships, dict):
                return False
            
            # Check insights structure
            insights = platform_context.get("insights", {})
            if not isinstance(insights, dict):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Response validation failed: {e}")
            return False

    def _validate_schema_structure(self, schema_data: dict[str, Any]) -> bool:
        """Validate the structure of a schema in the response.
        
        Args:
            schema_data: Schema data to validate
            
        Returns:
            True if schema structure is valid, False otherwise
        """
        if not isinstance(schema_data, dict):
            return False
        
        # Check required fields
        if "metadata" not in schema_data or "instances" not in schema_data:
            return False
        
        metadata = schema_data.get("metadata", {})
        if not isinstance(metadata, dict):
            return False
        
        # Check metadata fields
        metadata_required = ["apiVersion", "kind", "accessible", "relationshipPath"]
        for field in metadata_required:
            if field not in metadata:
                return False
        
        # Check instances
        instances = schema_data.get("instances", [])
        if not isinstance(instances, list):
            return False
        
        # Validate each instance
        for instance in instances:
            if not self._validate_instance_structure(instance):
                return False
        
        return True

    def _validate_instance_structure(self, instance: dict[str, Any]) -> bool:
        """Validate the structure of an instance in the response.
        
        Args:
            instance: Instance data to validate
            
        Returns:
            True if instance structure is valid, False otherwise
        """
        if not isinstance(instance, dict):
            return False
        
        # Check required fields
        required_fields = ["name", "namespace", "summary"]
        for field in required_fields:
            if field not in instance:
                return False
        
        # Summary can be any dictionary
        summary = instance.get("summary", {})
        if not isinstance(summary, dict):
            return False
        
        return True