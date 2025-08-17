"""Integration tests for the KubeCore Context Function gRPC interface."""

import unittest
from unittest.mock import Mock, patch

from crossplane.function import resource
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from google.protobuf import json_format

from function.fn import FunctionRunner


class TestFunctionRunner(unittest.IsolatedAsyncioTestCase):
    """Test cases for FunctionRunner gRPC service."""

    def setUp(self):
        """Set up test fixtures."""
        self.maxDiff = 2000

        # Mock the schema registry to avoid import issues during testing
        with patch("function.fn.SchemaRegistry"):
            self.runner = FunctionRunner()

    async def test_run_function_basic_request(self):
        """Test running function with basic gRPC request."""
        # Mock the function's run_function method
        mock_result = {
            "platformContext": {
                "requestor": {
                    "type": "XApp",
                    "name": "test-app",
                    "namespace": "default",
                },
                "availableSchemas": {
                    "XKubEnv": {
                        "metadata": {
                            "apiVersion": "platform.kubecore.io/v1alpha1",
                            "kind": "XKubEnv",
                            "accessible": True,
                            "relationshipPath": ["XApp", "XKubEnv"],
                        }
                    }
                },
                "relationships": {"direct": [], "indirect": []},
                "insights": {
                    "suggestedReferences": [],
                    "validationRules": [],
                    "recommendations": [],
                },
            }
        }

        self.runner.function.run_function = Mock(return_value=mock_result)

        # Create test request
        input_dict = {
            "spec": {"query": {"resourceType": "XApp", "includeFullSchemas": True}}
        }

        req = fnv1.RunFunctionRequest(input=resource.dict_to_struct(input_dict))

        # Run the function
        result = await self.runner.RunFunction(req, None)

        # Convert result to dict for easier testing
        result_dict = json_format.MessageToDict(result)

        # Check that context was populated
        self.assertIn("context", result_dict)
        context = result_dict["context"]
        self.assertIn("context.fn.kubecore.io/platform-context", context)

        platform_context = context["context.fn.kubecore.io/platform-context"]
        self.assertIn("platformContext", platform_context)

        # Verify the mock was called
        self.runner.function.run_function.assert_called_once()

    async def test_run_function_with_observed_composite(self):
        """Test running function with observed composite resource."""
        # Mock the function's run_function method
        mock_result = {
            "platformContext": {
                "requestor": {
                    "type": "XApp",
                    "name": "test-app",
                    "namespace": "default",
                },
                "availableSchemas": {},
                "relationships": {"direct": [], "indirect": []},
                "insights": {
                    "suggestedReferences": [],
                    "validationRules": [],
                    "recommendations": [],
                },
            }
        }

        self.runner.function.run_function = Mock(return_value=mock_result)

        # Create test request with observed composite
        input_dict = {"spec": {"query": {"resourceType": "XApp"}}}

        composite_dict = {
            "apiVersion": "platform.kubecore.io/v1alpha1",
            "kind": "XApp",
            "metadata": {"name": "test-app", "namespace": "default"},
            "spec": {"type": "rest", "image": "test-image:latest"},
        }

        req = fnv1.RunFunctionRequest(
            input=resource.dict_to_struct(input_dict),
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(composite_dict)
                )
            ),
        )

        # Run the function
        result = await self.runner.RunFunction(req, None)

        # Check that result is successful
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].severity, fnv1.Severity.SEVERITY_NORMAL)

        # Verify the mock was called with correct structure
        self.runner.function.run_function.assert_called_once()
        call_args = self.runner.function.run_function.call_args[0][0]
        self.assertIn("input", call_args)
        self.assertIn("observed", call_args)
        self.assertIn("composite", call_args["observed"])

    async def test_run_function_error_handling(self):
        """Test that function handles errors gracefully."""
        # Mock the function to raise an exception
        self.runner.function.run_function = Mock(side_effect=Exception("Test error"))

        input_dict = {"spec": {"query": {"resourceType": "XApp"}}}

        req = fnv1.RunFunctionRequest(input=resource.dict_to_struct(input_dict))

        # Run the function
        result = await self.runner.RunFunction(req, None)

        # Check that error is handled properly
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].severity, fnv1.Severity.SEVERITY_FATAL)
        self.assertIn("Test error", result.results[0].message)

    async def test_run_function_empty_input(self):
        """Test running function with empty input."""
        # Mock the function's run_function method
        mock_result = {
            "platformContext": {
                "requestor": {"type": "", "name": "", "namespace": ""},
                "availableSchemas": {},
                "relationships": {"direct": [], "indirect": []},
                "insights": {
                    "suggestedReferences": [],
                    "validationRules": [],
                    "recommendations": [],
                },
            }
        }

        self.runner.function.run_function = Mock(return_value=mock_result)

        # Create request with no input
        req = fnv1.RunFunctionRequest()

        # Run the function
        result = await self.runner.RunFunction(req, None)

        # Should handle empty input gracefully
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].severity, fnv1.Severity.SEVERITY_NORMAL)

        # Verify the mock was called
        self.runner.function.run_function.assert_called_once()
        call_args = self.runner.function.run_function.call_args[0][0]
        self.assertEqual(call_args["input"], {})

    async def test_logging_integration(self):
        """Test that logging works correctly."""
        # Mock the function's run_function method
        mock_result = {
            "platformContext": {
                "requestor": {"type": "XApp", "name": "", "namespace": ""},
                "availableSchemas": {},
                "relationships": {"direct": [], "indirect": []},
                "insights": {
                    "suggestedReferences": [],
                    "validationRules": [],
                    "recommendations": [],
                },
            }
        }

        self.runner.function.run_function = Mock(return_value=mock_result)

        input_dict = {"spec": {"query": {"resourceType": "XApp"}}}

        req = fnv1.RunFunctionRequest(
            input=resource.dict_to_struct(input_dict),
            meta=fnv1.RequestMeta(tag="test-tag"),
        )

        # Run the function
        result = await self.runner.RunFunction(req, None)

        # Should complete successfully
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].severity, fnv1.Severity.SEVERITY_NORMAL)


if __name__ == "__main__":
    unittest.main()
