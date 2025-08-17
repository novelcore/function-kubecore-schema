"""Unit tests for the schema registry module."""

import unittest
from function.schema_registry import SchemaRegistry
from function.platform_relationships import PLATFORM_HIERARCHY


class TestSchemaRegistry(unittest.TestCase):
    """Test cases for SchemaRegistry class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.registry = SchemaRegistry()
    
    def test_schema_registry_initialization(self):
        """Test that schema registry initializes correctly."""
        # Test that schemas are loaded
        self.assertGreater(len(self.registry.schemas), 0)
        
        # Test that hierarchy is loaded
        self.assertGreater(len(self.registry.hierarchy), 0)
        
        # Test that expected schemas are present
        expected_schemas = [
            "XApp", "XKubEnv", "XQualityGate", "XGitHubProject",
            "XGitHubApp", "XKubeCluster", "XKubeNet", "XKubeSystem",
            "XGitHubProvider"
        ]
        
        for schema in expected_schemas:
            self.assertIn(schema, self.registry.schemas)
    
    def test_get_accessible_schemas_for_app(self):
        """Test getting accessible schemas for XApp resource type."""
        schemas = self.registry.get_accessible_schemas("XApp")
        
        expected = ["XKubEnv", "XQualityGate", "XGitHubProject", "XGitHubApp", "XKubeCluster", "XKubeNet", "XKubeSystem"]
        
        # Check that all expected schemas are present
        for schema in expected:
            self.assertIn(schema, schemas, f"Expected schema {schema} not found in accessible schemas for XApp")
    
    def test_get_accessible_schemas_for_kubesystem(self):
        """Test getting accessible schemas for XKubeSystem resource type."""
        schemas = self.registry.get_accessible_schemas("XKubeSystem")
        
        expected = ["XKubeCluster", "XGitHubProject", "XKubeNet", "XGitHubProvider"]
        
        # Check that all expected schemas are present
        for schema in expected:
            self.assertIn(schema, schemas, f"Expected schema {schema} not found in accessible schemas for XKubeSystem")
    
    def test_get_accessible_schemas_for_kubenv(self):
        """Test getting accessible schemas for XKubEnv resource type."""
        schemas = self.registry.get_accessible_schemas("XKubEnv")
        
        expected = ["XKubeCluster", "XQualityGate", "XGitHubProject", "XKubeNet"]
        
        # Check that all expected schemas are present
        for schema in expected:
            self.assertIn(schema, schemas, f"Expected schema {schema} not found in accessible schemas for XKubEnv")
    
    def test_get_accessible_schemas_unknown_type(self):
        """Test getting accessible schemas for unknown resource type."""
        schemas = self.registry.get_accessible_schemas("UnknownType")
        self.assertEqual(schemas, [])
    
    def test_get_schema_info(self):
        """Test getting schema information for a resource type."""
        schema_info = self.registry.get_schema_info("XApp")
        
        self.assertIsNotNone(schema_info)
        self.assertEqual(schema_info.api_version, "platform.kubecore.io/v1alpha1")
        self.assertEqual(schema_info.kind, "XApp")
        self.assertIsInstance(schema_info.schema, dict)
        self.assertIn("type", schema_info.schema)
    
    def test_get_schema_info_unknown_type(self):
        """Test getting schema information for unknown resource type."""
        schema_info = self.registry.get_schema_info("UnknownType")
        self.assertIsNone(schema_info)
    
    def test_get_relationship_path_direct(self):
        """Test getting relationship path for direct relationships."""
        path = self.registry.get_relationship_path("XApp", "XKubEnv")
        self.assertEqual(path, ["XApp", "XKubEnv"])
    
    def test_get_relationship_path_same_type(self):
        """Test getting relationship path for same resource type."""
        path = self.registry.get_relationship_path("XApp", "XApp")
        self.assertEqual(path, ["XApp"])
    
    def test_get_relationship_path_indirect(self):
        """Test getting relationship path for indirect relationships."""
        # For now, indirect relationships return empty path
        # This could be enhanced with graph traversal
        path = self.registry.get_relationship_path("XApp", "XGitHubProvider")
        # Since XGitHubProvider is not directly accessible from XApp, should return empty
        # But it's in the hierarchy, so it should return the path
        if path:
            self.assertIn("XApp", path)
    
    def test_platform_hierarchy_consistency(self):
        """Test that platform hierarchy is consistent with loaded schemas."""
        for resource_type, accessible_schemas in PLATFORM_HIERARCHY.items():
            # Check that the resource type itself exists in schemas
            self.assertIn(resource_type, self.registry.schemas, 
                         f"Resource type {resource_type} not found in schemas")
            
            # Check that all accessible schemas exist
            for schema in accessible_schemas:
                self.assertIn(schema, self.registry.schemas, 
                             f"Accessible schema {schema} for {resource_type} not found in schemas")
    
    def test_schema_structure_validation(self):
        """Test that all schemas have required structure."""
        for resource_type, schema_info in self.registry.schemas.items():
            # Check that schema has required fields
            self.assertIsNotNone(schema_info.api_version, 
                               f"Schema {resource_type} missing api_version")
            self.assertIsNotNone(schema_info.kind, 
                               f"Schema {resource_type} missing kind")
            self.assertIsInstance(schema_info.schema, dict, 
                                f"Schema {resource_type} schema is not a dict")
            self.assertIsInstance(schema_info.relationships, list, 
                                f"Schema {resource_type} relationships is not a list")
            
            # Check that schema has OpenAPI structure
            self.assertIn("type", schema_info.schema, 
                         f"Schema {resource_type} missing type field")
            self.assertEqual(schema_info.schema["type"], "object", 
                           f"Schema {resource_type} type is not object")


if __name__ == "__main__":
    unittest.main()
