"""Unit tests for the KubeCore Context Function (Phase 3)."""

import unittest
from unittest.mock import AsyncMock, Mock, patch

from function.fn import KubeCoreContextFunction


class TestKubeCoreContextFunction(unittest.TestCase):
    """Test cases for KubeCoreContextFunction class."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("function.fn.SchemaRegistry"), \
             patch("function.fn.K8sClient"), \
             patch("function.fn.ResourceResolver"), \
             patch("function.fn.ResourceSummarizer"), \
             patch("function.fn.QueryProcessor"), \
             patch("function.fn.ResponseGenerator"), \
             patch("function.fn.InsightsEngine"):
            self.function = KubeCoreContextFunction()

    def test_function_initialization(self):
        """Test that function initializes correctly."""
        self.assertIsNotNone(self.function.schema_registry)
        self.assertIsNotNone(self.function.k8s_client)
        self.assertIsNotNone(self.function.resource_resolver)
        self.assertIsNotNone(self.function.resource_summarizer)
        self.assertIsNotNone(self.function.query_processor)
        self.assertIsNotNone(self.function.response_generator)
        self.assertIsNotNone(self.function.insights_engine)
        self.assertIsNotNone(self.function.logger)

    def test_run_function_basic_request(self):
        """Test running function with basic request."""
        # Mock the components
        mock_platform_context = {
            "requestor": {"type": "XApp", "name": "test-app", "namespace": "default"},
            "availableSchemas": {"kubEnv": {"metadata": {}, "instances": []}},
            "relationships": {"direct": []},
        }

        mock_insights = {
            "recommendations": [{"category": "test", "suggestion": "test"}],
            "validationRules": [],
            "suggestedReferences": []
        }

        mock_response = {
            "apiVersion": "context.fn.kubecore.io/v1beta1",
            "kind": "Output",
            "spec": {
                "platformContext": {
                    **mock_platform_context,
                    "insights": mock_insights
                }
            }
        }

        self.function.query_processor.process_query = AsyncMock(return_value=mock_platform_context)
        self.function.insights_engine.generate_insights = Mock(return_value=mock_insights)
        self.function.response_generator.generate_response = Mock(return_value=mock_response)
        self.function.response_generator.validate_response_format = Mock(return_value=True)

        request = {
            "input": {
                "spec": {
                    "query": {
                        "resourceType": "XApp",
                        "requestedSchemas": ["kubEnv"]
                    }
                }
            },
            "observed": {
                "composite": {
                    "metadata": {"name": "test-app", "namespace": "default"},
                    "spec": {}
                }
            }
        }

        result = self.function.run_function(request)

        # Check response structure matches Phase 3 format
        self.assertEqual(result["apiVersion"], "context.fn.kubecore.io/v1beta1")
        self.assertEqual(result["kind"], "Output")
        self.assertIn("spec", result)
        self.assertIn("platformContext", result["spec"])

        platform_context = result["spec"]["platformContext"]
        self.assertIn("requestor", platform_context)
        self.assertIn("availableSchemas", platform_context)
        self.assertIn("relationships", platform_context)
        self.assertIn("insights", platform_context)

        # Verify requestor
        requestor = platform_context["requestor"]
        self.assertEqual(requestor["type"], "XApp")

    def test_run_function_missing_query(self):
        """Test running function with missing query raises ValueError."""
        request = {"input": {"spec": {}}}

        with self.assertRaises(ValueError) as context:
            self.function.run_function(request)

        self.assertIn("Missing 'query' in input specification", str(context.exception))

    def test_run_function_missing_input(self):
        """Test running function with missing input raises ValueError."""
        request = {}

        with self.assertRaises(ValueError) as context:
            self.function.run_function(request)

        self.assertIn("Missing 'query' in input specification", str(context.exception))

    def test_run_function_invalid_response_format(self):
        """Test that invalid response format raises ValueError."""
        # Mock invalid response
        mock_platform_context = {"requestor": {}, "availableSchemas": {}}
        mock_insights = {"recommendations": []}
        mock_invalid_response = {"invalid": "response"}

        self.function.query_processor.process_query = AsyncMock(return_value=mock_platform_context)
        self.function.insights_engine.generate_insights = Mock(return_value=mock_insights)
        self.function.response_generator.generate_response = Mock(return_value=mock_invalid_response)
        self.function.response_generator.validate_response_format = Mock(return_value=False)

        request = {
            "input": {
                "spec": {
                    "query": {"resourceType": "XApp", "requestedSchemas": ["kubEnv"]}
                }
            },
            "observed": {"composite": {"metadata": {}, "spec": {}}}
        }

        with self.assertRaises(ValueError) as context:
            self.function.run_function(request)

        self.assertIn("Generated response does not match expected format", str(context.exception))

    def test_extract_context(self):
        """Test context extraction from request."""
        request = {
            "observed": {
                "composite": {
                    "metadata": {"name": "test-app", "namespace": "default"},
                    "spec": {
                        "kubEnvRef": {"name": "demo-env", "namespace": "test"},
                        "githubProjectRefs": [
                            {"name": "project1", "namespace": "default"},
                            {"name": "project2", "namespace": "default"}
                        ]
                    }
                }
            }
        }

        context = self.function._extract_context(request)

        self.assertEqual(context["requestorName"], "test-app")
        self.assertEqual(context["requestorNamespace"], "default")
        self.assertIn("references", context)

        references = context["references"]
        self.assertIn("kubEnvRefs", references)
        self.assertIn("githubProjectRefs", references)

        self.assertEqual(len(references["kubEnvRefs"]), 1)
        self.assertEqual(references["kubEnvRefs"][0]["name"], "demo-env")

        self.assertEqual(len(references["githubProjectRefs"]), 2)

    def test_extract_context_empty_composite(self):
        """Test context extraction with empty composite resource."""
        request = {"observed": {"composite": {}}}

        context = self.function._extract_context(request)

        self.assertEqual(context["requestorName"], "unknown")
        self.assertEqual(context["requestorNamespace"], "default")
        self.assertEqual(context["references"], {})

    def test_run_function_with_kubesystem_query(self):
        """Test running function with XKubeSystem query."""
        mock_platform_context = {
            "requestor": {"type": "XKubeSystem", "name": "demo-system", "namespace": "kube-system"},
            "availableSchemas": {"kubeCluster": {"metadata": {}, "instances": []}},
            "relationships": {"direct": []},
        }

        mock_insights = {"recommendations": [], "validationRules": [], "suggestedReferences": []}
        mock_response = {
            "apiVersion": "context.fn.kubecore.io/v1beta1",
            "kind": "Output",
            "spec": {"platformContext": {**mock_platform_context, "insights": mock_insights}}
        }

        self.function.query_processor.process_query = AsyncMock(return_value=mock_platform_context)
        self.function.insights_engine.generate_insights = Mock(return_value=mock_insights)
        self.function.response_generator.generate_response = Mock(return_value=mock_response)
        self.function.response_generator.validate_response_format = Mock(return_value=True)

        request = {
            "input": {
                "spec": {
                    "query": {"resourceType": "XKubeSystem", "requestedSchemas": ["kubeCluster"]}
                }
            },
            "observed": {
                "composite": {
                    "metadata": {"name": "demo-system", "namespace": "kube-system"},
                    "spec": {}
                }
            }
        }

        result = self.function.run_function(request)

        self.assertEqual(result["spec"]["platformContext"]["requestor"]["type"], "XKubeSystem")

    def test_run_function_with_kubenv_query(self):
        """Test running function with XKubEnv query."""
        mock_platform_context = {
            "requestor": {"type": "XKubEnv", "name": "demo-env", "namespace": "default"},
            "availableSchemas": {"qualityGate": {"metadata": {}, "instances": []}},
            "relationships": {"direct": []},
        }

        mock_insights = {"recommendations": [], "validationRules": [], "suggestedReferences": []}
        mock_response = {
            "apiVersion": "context.fn.kubecore.io/v1beta1",
            "kind": "Output",
            "spec": {"platformContext": {**mock_platform_context, "insights": mock_insights}}
        }

        self.function.query_processor.process_query = AsyncMock(return_value=mock_platform_context)
        self.function.insights_engine.generate_insights = Mock(return_value=mock_insights)
        self.function.response_generator.generate_response = Mock(return_value=mock_response)
        self.function.response_generator.validate_response_format = Mock(return_value=True)

        request = {
            "input": {
                "spec": {
                    "query": {"resourceType": "XKubEnv", "requestedSchemas": ["qualityGate"]}
                }
            },
            "observed": {
                "composite": {
                    "metadata": {"name": "demo-env", "namespace": "default"},
                    "spec": {}
                }
            }
        }

        result = self.function.run_function(request)

        self.assertEqual(result["spec"]["platformContext"]["requestor"]["type"], "XKubEnv")


if __name__ == "__main__":
    unittest.main()
