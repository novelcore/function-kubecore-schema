"""Unit tests for the KubeCore Context Function."""

import unittest
from unittest.mock import Mock, patch
from function.fn import KubeCoreContextFunction


class TestKubeCoreContextFunction(unittest.TestCase):
    """Test cases for KubeCoreContextFunction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('function.fn.SchemaRegistry'):
            self.function = KubeCoreContextFunction()
    
    def test_function_initialization(self):
        """Test that function initializes correctly."""
        self.assertIsNotNone(self.function.schema_registry)
        self.assertIsNotNone(self.function.logger)
    
    def test_run_function_basic_request(self):
        """Test running function with basic request."""
        # Mock the schema registry
        self.function.schema_registry.get_accessible_schemas = Mock(return_value=["XKubEnv", "XQualityGate"])
        self.function.schema_registry.get_schema_info = Mock()
        self.function.schema_registry.get_relationship_path = Mock(return_value=["XApp", "XKubEnv"])
        
        # Mock schema info
        mock_schema_info = Mock()
        mock_schema_info.api_version = "platform.kubecore.io/v1alpha1"
        mock_schema_info.kind = "XKubEnv"
        mock_schema_info.schema = {"type": "object", "properties": {}}
        self.function.schema_registry.get_schema_info.return_value = mock_schema_info
        
        request = {
            "input": {
                "spec": {
                    "query": {
                        "resourceType": "XApp",
                        "requestedSchemas": ["XKubEnv"],
                        "includeFullSchemas": True
                    }
                }
            }
        }
        
        result = self.function.run_function(request)
        
        # Check response structure
        self.assertIn("platformContext", result)
        platform_context = result["platformContext"]
        
        self.assertIn("requestor", platform_context)
        self.assertIn("availableSchemas", platform_context)
        self.assertIn("relationships", platform_context)
        self.assertIn("insights", platform_context)
        
        # Check requestor
        requestor = platform_context["requestor"]
        self.assertEqual(requestor["type"], "XApp")
        
        # Check that accessible schemas were called correctly
        self.function.schema_registry.get_accessible_schemas.assert_called_once_with("XApp")
    
    def test_run_function_with_requested_schemas_filter(self):
        """Test that requested schemas filter works correctly."""
        # Mock the schema registry
        self.function.schema_registry.get_accessible_schemas = Mock(
            return_value=["XKubEnv", "XQualityGate", "XGitHubProject"]
        )
        self.function.schema_registry.get_schema_info = Mock()
        self.function.schema_registry.get_relationship_path = Mock(return_value=["XApp", "XKubEnv"])
        
        # Mock schema info
        mock_schema_info = Mock()
        mock_schema_info.api_version = "platform.kubecore.io/v1alpha1"
        mock_schema_info.kind = "XKubEnv"
        mock_schema_info.schema = {"type": "object"}
        self.function.schema_registry.get_schema_info.return_value = mock_schema_info
        
        request = {
            "input": {
                "spec": {
                    "query": {
                        "resourceType": "XApp",
                        "requestedSchemas": ["XKubEnv"],  # Only request one schema
                        "includeFullSchemas": True
                    }
                }
            }
        }
        
        result = self.function.run_function(request)
        
        # Check that only the requested schema is included
        available_schemas = result["platformContext"]["availableSchemas"]
        self.assertIn("XKubEnv", available_schemas)
        
        # Should only call get_schema_info for the requested schema
        self.function.schema_registry.get_schema_info.assert_called_with("XKubEnv")
    
    def test_run_function_without_full_schemas(self):
        """Test running function without including full schemas."""
        # Mock the schema registry
        self.function.schema_registry.get_accessible_schemas = Mock(return_value=["XKubEnv"])
        self.function.schema_registry.get_schema_info = Mock()
        self.function.schema_registry.get_relationship_path = Mock(return_value=["XApp", "XKubEnv"])
        
        # Mock schema info
        mock_schema_info = Mock()
        mock_schema_info.api_version = "platform.kubecore.io/v1alpha1"
        mock_schema_info.kind = "XKubEnv"
        mock_schema_info.schema = {"type": "object"}
        self.function.schema_registry.get_schema_info.return_value = mock_schema_info
        
        request = {
            "input": {
                "spec": {
                    "query": {
                        "resourceType": "XApp",
                        "includeFullSchemas": False
                    }
                }
            }
        }
        
        result = self.function.run_function(request)
        
        # Check that schema is not included when includeFullSchemas is False
        available_schemas = result["platformContext"]["availableSchemas"]
        if "XKubEnv" in available_schemas:
            self.assertNotIn("schema", available_schemas["XKubEnv"])
    
    def test_run_function_empty_request(self):
        """Test running function with empty request."""
        # Mock the schema registry
        self.function.schema_registry.get_accessible_schemas = Mock(return_value=[])
        
        request = {
            "input": {
                "spec": {
                    "query": {
                        "resourceType": ""
                    }
                }
            }
        }
        
        result = self.function.run_function(request)
        
        # Should still return valid structure
        self.assertIn("platformContext", result)
        platform_context = result["platformContext"]
        self.assertIn("availableSchemas", platform_context)
        self.assertEqual(len(platform_context["availableSchemas"]), 0)
    
    def test_run_function_missing_query(self):
        """Test running function with missing query."""
        request = {
            "input": {
                "spec": {}
            }
        }
        
        result = self.function.run_function(request)
        
        # Should handle missing query gracefully
        self.assertIn("platformContext", result)
    
    def test_run_function_missing_input(self):
        """Test running function with missing input."""
        request = {}
        
        result = self.function.run_function(request)
        
        # Should handle missing input gracefully
        self.assertIn("platformContext", result)


if __name__ == "__main__":
    unittest.main()
