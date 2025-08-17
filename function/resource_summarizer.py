"""Resource Summarization for KubeCore Platform Context Function.

This module extracts key attributes from resolved resources based on schema
specifications and provides optimized summaries for context resolution.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .resource_resolver import ResolvedResource, ResourceRef
from .schema_registry import ResourceSchema, SchemaRegistry


@dataclass
class ResourceSummary:
    """Summary of a Kubernetes resource with key attributes."""

    ref: ResourceRef
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    relationships: list[ResourceRef] = field(default_factory=list)
    extraction_time: float = field(default_factory=time.time)
    schema_version: str = ""

    @property
    def age(self) -> float:
        """Age of the summary in seconds."""
        return time.time() - self.extraction_time


@dataclass
class SummarizationConfig:
    """Configuration for resource summarization."""

    # Field extraction settings
    max_depth: int = 3
    max_array_elements: int = 10
    max_string_length: int = 500

    # Schema compliance
    follow_schema: bool = True
    include_defaults: bool = False

    # Performance settings
    cache_summaries: bool = True
    parallel_processing: bool = True

    # Output customization
    include_metadata: bool = True
    include_relationships: bool = True
    include_status: bool = False


class ResourceSummarizer:
    """Engine for extracting and summarizing resource attributes."""

    def __init__(
        self,
        schema_registry: SchemaRegistry,
        config: SummarizationConfig | None = None,
    ):
        """Initialize the resource summarizer.
        
        Args:
            schema_registry: Registry for resource schemas
            config: Summarization configuration
        """
        self.schema_registry = schema_registry
        self.config = config or SummarizationConfig()
        self.logger = logging.getLogger(__name__)

        # Cache for schemas and summaries
        self._schema_cache: dict[str, ResourceSchema] = {}
        self._summary_cache: dict[ResourceRef, ResourceSummary] = {}

    def summarize_resource(
        self,
        resolved: ResolvedResource,
        requested_fields: set[str] | None = None,
    ) -> ResourceSummary:
        """Summarize a resolved resource based on its schema.
        
        Args:
            resolved: Resolved resource to summarize
            requested_fields: Specific fields to include in summary
            
        Returns:
            Resource summary with extracted key attributes
        """
        # Check cache first
        if self.config.cache_summaries:
            cached = self._summary_cache.get(resolved.ref)
            if cached and cached.age < 300:  # 5 minutes cache
                return cached

        self.logger.debug(f"Summarizing resource: {resolved.ref}")

        # Get schema for the resource
        schema = self._get_resource_schema(resolved.ref.kind)

        # Extract summary based on schema
        summary_data = self._extract_summary_data(
            resolved.data,
            schema,
            requested_fields,
        )

        # Extract metadata
        metadata = self._extract_metadata(resolved.data)

        # Create summary
        summary = ResourceSummary(
            ref=resolved.ref,
            summary=summary_data,
            metadata=metadata,
            relationships=resolved.relationships.copy(),
            schema_version=schema.api_version if schema else "",
        )

        # Cache the summary
        if self.config.cache_summaries:
            self._summary_cache[resolved.ref] = summary

        self.logger.debug(
            f"Summarized {resolved.ref}: {len(summary_data)} fields, "
            f"{len(summary.relationships)} relationships"
        )

        return summary

    def summarize_multiple(
        self,
        resolved_resources: dict[ResourceRef, ResolvedResource],
        requested_fields: dict[str, set[str]] | None = None,
    ) -> dict[ResourceRef, ResourceSummary]:
        """Summarize multiple resolved resources.
        
        Args:
            resolved_resources: Dictionary of resolved resources
            requested_fields: Fields to include per resource kind
            
        Returns:
            Dictionary of resource summaries
        """
        summaries: dict[ResourceRef, ResourceSummary] = {}

        for ref, resolved in resolved_resources.items():
            try:
                # Get requested fields for this resource kind
                fields = None
                if requested_fields:
                    fields = requested_fields.get(ref.kind)

                summary = self.summarize_resource(resolved, fields)
                summaries[ref] = summary

            except Exception as e:
                self.logger.warning(f"Failed to summarize {ref}: {e}")
                # Create minimal summary
                summaries[ref] = ResourceSummary(
                    ref=ref,
                    summary={"error": str(e)},
                    metadata={"summarization_failed": True},
                )

        self.logger.info(f"Summarized {len(summaries)} resources")
        return summaries

    def _get_resource_schema(self, kind: str) -> ResourceSchema | None:
        """Get schema for a resource kind with caching."""
        if kind in self._schema_cache:
            return self._schema_cache[kind]

        schema = self.schema_registry.get_schema_info(kind)
        if schema:
            self._schema_cache[kind] = schema

        return schema

    def _extract_summary_data(
        self,
        resource_data: dict[str, Any],
        schema: ResourceSchema | None,
        requested_fields: set[str] | None = None,
    ) -> dict[str, Any]:
        """Extract summary data based on schema and configuration."""
        summary: dict[str, Any] = {}

        if not self.config.follow_schema or not schema:
            # Extract without schema guidance
            return self._extract_without_schema(resource_data, requested_fields)

        # Extract based on schema
        schema_properties = schema.schema.get("properties", {})
        spec_properties = schema_properties.get("spec", {}).get("properties", {})

        # Extract spec fields
        spec_data = resource_data.get("spec", {})
        if spec_data:
            summary["spec"] = self._extract_fields_by_schema(
                spec_data,
                spec_properties,
                requested_fields,
                depth=0,
            )

        # Extract status if configured
        if self.config.include_status:
            status_data = resource_data.get("status", {})
            status_properties = schema_properties.get("status", {}).get("properties", {})
            if status_data and status_properties:
                summary["status"] = self._extract_fields_by_schema(
                    status_data,
                    status_properties,
                    requested_fields,
                    depth=0,
                )

        return summary

    def _extract_without_schema(
        self,
        resource_data: dict[str, Any],
        requested_fields: set[str] | None = None,
    ) -> dict[str, Any]:
        """Extract summary data without schema guidance."""
        summary: dict[str, Any] = {}

        # Extract key sections
        sections_to_extract = ["spec"]
        if self.config.include_status:
            sections_to_extract.append("status")

        for section in sections_to_extract:
            section_data = resource_data.get(section, {})
            if section_data:
                summary[section] = self._extract_key_fields(
                    section_data,
                    requested_fields,
                    depth=0,
                )

        return summary

    def _extract_fields_by_schema(
        self,
        data: dict[str, Any],
        schema_properties: dict[str, Any],
        requested_fields: set[str] | None = None,
        depth: int = 0,
    ) -> dict[str, Any]:
        """Extract fields based on schema properties."""
        if depth >= self.config.max_depth:
            return {}

        extracted: dict[str, Any] = {}

        for field_name, field_schema in schema_properties.items():
            # Skip if not in requested fields
            if requested_fields and field_name not in requested_fields:
                continue

            field_value = data.get(field_name)

            # Handle missing fields
            if field_value is None:
                if self.config.include_defaults and "default" in field_schema:
                    extracted[field_name] = field_schema["default"]
                continue

            # Extract based on field type
            field_type = field_schema.get("type", "string")

            if field_type == "object":
                # Recursively extract object fields
                nested_properties = field_schema.get("properties", {})
                if nested_properties and isinstance(field_value, dict):
                    extracted[field_name] = self._extract_fields_by_schema(
                        field_value,
                        nested_properties,
                        requested_fields,
                        depth + 1,
                    )
                else:
                    extracted[field_name] = self._sanitize_value(field_value)

            elif field_type == "array":
                # Handle arrays with item schemas
                extracted[field_name] = self._extract_array_items(
                    field_value,
                    field_schema.get("items", {}),
                    depth,
                )

            else:
                # Simple field types
                extracted[field_name] = self._sanitize_value(field_value)

        return extracted

    def _extract_key_fields(
        self,
        data: dict[str, Any],
        requested_fields: set[str] | None = None,
        depth: int = 0,
    ) -> dict[str, Any]:
        """Extract key fields without schema guidance."""
        if depth >= self.config.max_depth:
            return {}

        extracted: dict[str, Any] = {}

        # Priority fields to always include
        priority_fields = {
            "name", "namespace", "type", "image", "port", "version",
            "region", "credentials", "organization", "baseUrl",
            "environmentType", "components", "key", "description",
            "appName", "visibility"
        }

        for field_name, field_value in data.items():
            # Skip if not in requested fields (when specified)
            if requested_fields and field_name not in requested_fields:
                continue

            # Always include priority fields
            if field_name in priority_fields or requested_fields is None:
                if isinstance(field_value, dict):
                    # Recursively extract nested objects
                    extracted[field_name] = self._extract_key_fields(
                        field_value,
                        requested_fields,
                        depth + 1,
                    )
                elif isinstance(field_value, list):
                    # Handle arrays
                    extracted[field_name] = self._extract_array_items(
                        field_value,
                        {},
                        depth,
                    )
                else:
                    # Simple values
                    extracted[field_name] = self._sanitize_value(field_value)

        return extracted

    def _extract_array_items(
        self,
        array_value: list[Any],
        item_schema: dict[str, Any],
        depth: int,
    ) -> list[Any]:
        """Extract and summarize array items."""
        if not isinstance(array_value, list):
            return []

        # Limit array size for performance
        max_items = self.config.max_array_elements
        limited_array = array_value[:max_items]

        extracted_items = []
        item_type = item_schema.get("type", "string")

        for item in limited_array:
            if item_type == "object" and isinstance(item, dict):
                # Extract object properties
                item_properties = item_schema.get("properties", {})
                if item_properties:
                    extracted_item = self._extract_fields_by_schema(
                        item,
                        item_properties,
                        None,
                        depth + 1,
                    )
                else:
                    extracted_item = self._extract_key_fields(item, None, depth + 1)
                extracted_items.append(extracted_item)
            else:
                # Simple item types
                extracted_items.append(self._sanitize_value(item))

        # Add truncation indicator if needed
        if len(array_value) > max_items:
            extracted_items.append(f"... ({len(array_value) - max_items} more items)")

        return extracted_items

    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize a value for inclusion in summary."""
        if isinstance(value, str):
            # Truncate long strings
            if len(value) > self.config.max_string_length:
                return value[:self.config.max_string_length] + "..."
            return value

        elif isinstance(value, (int, float, bool)):
            return value

        elif value is None:
            return None

        elif isinstance(value, (dict, list)):
            # For complex types not handled elsewhere, convert to string
            str_value = str(value)
            if len(str_value) > self.config.max_string_length:
                return str_value[:self.config.max_string_length] + "..."
            return str_value

        else:
            # Unknown types
            return str(value)

    def _extract_metadata(self, resource_data: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from resource."""
        if not self.config.include_metadata:
            return {}

        metadata = resource_data.get("metadata", {})

        # Extract key metadata fields
        extracted_metadata = {}
        metadata_fields = [
            "name", "namespace", "creationTimestamp", "generation",
            "resourceVersion", "uid", "labels", "annotations"
        ]

        for field in metadata_fields:
            value = metadata.get(field)
            if value is not None:
                extracted_metadata[field] = self._sanitize_value(value)

        # Extract owner references
        owner_refs = metadata.get("ownerReferences", [])
        if owner_refs:
            extracted_metadata["ownerReferences"] = [
                {
                    "apiVersion": ref.get("apiVersion"),
                    "kind": ref.get("kind"),
                    "name": ref.get("name"),
                }
                for ref in owner_refs[:5]  # Limit to 5 owners
            ]

        return extracted_metadata

    def get_summary_for_kind(
        self,
        kind: str,
        summaries: dict[ResourceRef, ResourceSummary],
    ) -> list[ResourceSummary]:
        """Get all summaries for a specific resource kind."""
        return [
            summary for ref, summary in summaries.items()
            if ref.kind == kind
        ]

    def get_relationship_summary(
        self,
        summaries: dict[ResourceRef, ResourceSummary],
    ) -> dict[str, list[dict[str, Any]]]:
        """Get a summary of relationships across all resources."""
        relationship_map: dict[str, list[dict[str, Any]]] = {}

        for summary in summaries.values():
            source_kind = summary.ref.kind

            for rel_ref in summary.relationships:
                rel_key = f"{source_kind} -> {rel_ref.kind}"

                if rel_key not in relationship_map:
                    relationship_map[rel_key] = []

                relationship_map[rel_key].append({
                    "source": str(summary.ref),
                    "target": str(rel_ref),
                    "relationship_type": self._infer_relationship_type(summary.ref, rel_ref),
                })

        return relationship_map

    def _infer_relationship_type(
        self,
        from_ref: ResourceRef,
        to_ref: ResourceRef,
    ) -> str:
        """Infer the relationship type between two resources."""
        # This could be enhanced with more sophisticated logic
        from_kind = from_ref.kind.lower()
        to_kind = to_ref.kind.lower()

        # Common patterns
        if "cluster" in from_kind and "net" in to_kind:
            return "uses"
        elif "app" in from_kind and "env" in to_kind:
            return "deploysTo"
        elif "env" in from_kind and "cluster" in to_kind:
            return "runsOn"
        elif "project" in from_kind:
            return "owns"
        else:
            return "references"

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._schema_cache.clear()
        self._summary_cache.clear()
        self.logger.debug("Cleared summarizer caches")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "schema_cache_size": len(self._schema_cache),
            "summary_cache_size": len(self._summary_cache),
            "config": {
                "max_depth": self.config.max_depth,
                "max_array_elements": self.config.max_array_elements,
                "follow_schema": self.config.follow_schema,
                "cache_summaries": self.config.cache_summaries,
            },
        }
