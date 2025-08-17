"""Schema Registry for KubeCore Platform Context Function.

This module implements the schema registry that manages platform resource schemas
and their relationships according to the KubeCore platform hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Import platform relationships at module level
try:
    from .platform_relationships import PLATFORM_HIERARCHY, RESOURCE_RELATIONSHIPS
except ImportError:
    # Fallback for direct execution
    from platform_relationships import PLATFORM_HIERARCHY, RESOURCE_RELATIONSHIPS


@dataclass
class ResourceSchema:
    """Represents a resource schema with its metadata and relationships."""

    api_version: str
    kind: str
    schema: dict[str, Any]
    relationships: list[str]


class SchemaRegistry:
    """Registry for managing KubeCore platform schemas and relationships."""

    def __init__(self):
        """Initialize the schema registry with platform schemas."""
        self.schemas: dict[str, ResourceSchema] = {}
        self.hierarchy: dict[str, list[str]] = {}
        self._load_platform_schemas()

    def _load_platform_schemas(self):
        """Load KubeCore platform schemas and relationships."""
        # Load platform hierarchy
        self.hierarchy = PLATFORM_HIERARCHY.copy()

        # Load basic schema definitions
        # These would typically be loaded from actual XRD files or OpenAPI specs
        self.schemas = {
            "XGitHubProvider": ResourceSchema(
                api_version="github.platform.kubecore.io/v1alpha1",
                kind="XGitHubProvider",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "credentials": {"type": "object"},
                                "organization": {"type": "string"},
                                "baseUrl": {"type": "string"},
                            },
                        }
                    },
                },
                relationships=RESOURCE_RELATIONSHIPS.get("XGitHubProvider", {}).get(
                    "owns", []
                ),
            ),
            "XGitHubProject": ResourceSchema(
                api_version="github.platform.kubecore.io/v1alpha1",
                kind="XGitHubProject",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "visibility": {
                                    "type": "string",
                                    "enum": ["public", "private"],
                                },
                                "githubProviderRef": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "namespace": {"type": "string"},
                                    },
                                },
                            },
                        }
                    },
                },
                relationships=RESOURCE_RELATIONSHIPS.get("XGitHubProject", {}).get(
                    "owns", []
                ),
            ),
            "XKubeNet": ResourceSchema(
                api_version="network.platform.kubecore.io/v1alpha1",
                kind="XKubeNet",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "dns": {
                                    "type": "object",
                                    "properties": {"domain": {"type": "string"}},
                                },
                                "vpc": {
                                    "type": "object",
                                    "properties": {"cidr": {"type": "string"}},
                                },
                            },
                        }
                    },
                },
                relationships=RESOURCE_RELATIONSHIPS.get("XKubeNet", {}).get(
                    "supports", []
                ),
            ),
            "XKubeCluster": ResourceSchema(
                api_version="platform.kubecore.io/v1alpha1",
                kind="XKubeCluster",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "region": {"type": "string"},
                                "version": {"type": "string"},
                                "githubProjectRef": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "namespace": {"type": "string"},
                                    },
                                },
                                "kubeNetRef": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "namespace": {"type": "string"},
                                    },
                                },
                            },
                        }
                    },
                },
                relationships=RESOURCE_RELATIONSHIPS.get("XKubeCluster", {}).get(
                    "hosts", []
                ),
            ),
            "XKubeSystem": ResourceSchema(
                api_version="platform.kubecore.io/v1alpha1",
                kind="XKubeSystem",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "kubeClusterRef": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "namespace": {"type": "string"},
                                    },
                                },
                                "components": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                relationships=[],
            ),
            "XKubEnv": ResourceSchema(
                api_version="platform.kubecore.io/v1alpha1",
                kind="XKubEnv",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "environmentType": {"type": "string"},
                                "resources": {
                                    "type": "object",
                                    "properties": {
                                        "profile": {"type": "string"},
                                        "defaults": {
                                            "type": "object",
                                            "properties": {
                                                "requests": {
                                                    "type": "object",
                                                    "properties": {
                                                        "cpu": {"type": "string"},
                                                        "memory": {"type": "string"},
                                                    },
                                                },
                                                "limits": {
                                                    "type": "object",
                                                    "properties": {
                                                        "cpu": {"type": "string"},
                                                        "memory": {"type": "string"},
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                                "environmentConfig": {
                                    "type": "object",
                                    "properties": {
                                        "variables": {
                                            "type": "object",
                                            "additionalProperties": {"type": "string"},
                                        }
                                    },
                                },
                                "qualityGates": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "ref": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "namespace": {"type": "string"},
                                                },
                                            },
                                            "key": {"type": "string"},
                                            "phase": {"type": "string"},
                                            "required": {"type": "boolean"},
                                        },
                                    },
                                },
                                "kubeClusterRef": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "namespace": {"type": "string"},
                                    },
                                },
                            },
                        }
                    },
                },
                relationships=[],
            ),
            "XQualityGate": ResourceSchema(
                api_version="platform.kubecore.io/v1alpha1",
                kind="XQualityGate",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "description": {"type": "string"},
                                "category": {"type": "string"},
                                "severity": {"type": "string"},
                                "applicability": {
                                    "type": "object",
                                    "properties": {
                                        "environments": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        }
                                    },
                                },
                            },
                        }
                    },
                },
                relationships=[],
            ),
            "XGitHubApp": ResourceSchema(
                api_version="github.platform.kubecore.io/v1alpha1",
                kind="XGitHubApp",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "githubProjectRef": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "namespace": {"type": "string"},
                                    },
                                },
                                "appName": {"type": "string"},
                            },
                        }
                    },
                },
                relationships=RESOURCE_RELATIONSHIPS.get("XGitHubApp", {}).get(
                    "sources", []
                ),
            ),
            "XApp": ResourceSchema(
                api_version="platform.kubecore.io/v1alpha1",
                kind="XApp",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "image": {"type": "string"},
                                "port": {"type": "integer"},
                                "githubProjectRef": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "namespace": {"type": "string"},
                                    },
                                },
                                "environments": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "kubenvRef": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "namespace": {"type": "string"},
                                                },
                                            },
                                            "enabled": {"type": "boolean"},
                                            "overrides": {"type": "object"},
                                        },
                                    },
                                },
                            },
                        }
                    },
                },
                relationships=[],
            ),
        }

    def get_accessible_schemas(self, resource_type: str) -> list[str]:
        """Get schemas accessible to a resource type based on platform relationships."""
        if resource_type not in self.hierarchy:
            return []

        return self.hierarchy[resource_type]

    def get_schema_info(self, resource_type: str) -> ResourceSchema | None:
        """Get schema information for a specific resource type."""
        return self.schemas.get(resource_type)

    def get_relationship_path(self, from_type: str, to_type: str) -> list[str]:
        """Get the relationship path from one resource type to another."""
        if from_type == to_type:
            return [from_type]

        # Simple direct relationship check
        accessible = self.get_accessible_schemas(from_type)
        if to_type in accessible:
            return [from_type, to_type]

        # For now, return empty path for indirect relationships
        # This could be enhanced with graph traversal algorithms
        return []
