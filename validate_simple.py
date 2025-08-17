#!/usr/bin/env python3
"""Simple Phase 1 validation script for KubeCore Platform Context Function."""

import os
import sys

# Add the function directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "function"))

def validate_implementation():
    """Validate Phase 1 implementation."""
    try:
        from platform_relationships import PLATFORM_HIERARCHY
        from schema_registry import SchemaRegistry

        # Initialize registry
        registry = SchemaRegistry()

        # Basic validation
        assert len(registry.schemas) == 9, f"Expected 9 schemas, got {len(registry.schemas)}"
        assert len(PLATFORM_HIERARCHY) == 9, f"Expected 9 hierarchy entries, got {len(PLATFORM_HIERARCHY)}"

        # Test XApp accessible schemas
        app_schemas = registry.get_accessible_schemas("XApp")
        expected_app_schemas = [
            "XKubEnv", "XQualityGate", "XGitHubProject",
            "XGitHubApp", "XKubeCluster", "XKubeNet", "XKubeSystem"
        ]

        for schema in expected_app_schemas:
            assert schema in app_schemas, f"Missing schema {schema} for XApp"

        # Test schema info retrieval
        app_schema_info = registry.get_schema_info("XApp")
        assert app_schema_info is not None, "Failed to retrieve XApp schema info"
        assert app_schema_info.api_version == "platform.kubecore.io/v1alpha1"
        assert app_schema_info.kind == "XApp"

        # Test relationship paths
        path = registry.get_relationship_path("XApp", "XKubEnv")
        assert path == ["XApp", "XKubEnv"], f"Incorrect relationship path: {path}"

        return True

    except Exception as e:
        print(f"Validation failed: {e}")
        return False

if __name__ == "__main__":
    success = validate_implementation()
    if success:
        print("✓ Phase 1 validation passed")
    else:
        print("✗ Phase 1 validation failed")
    sys.exit(0 if success else 1)
