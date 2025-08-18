#!/usr/bin/env python3
"""Comprehensive unit tests for Phase 1 Fix: Context extraction and input structure discovery."""

import asyncio
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Set up path for imports
sys.path.insert(0, '.')

from function.fn import KubeCoreContextFunction


class TestContextExtraction(unittest.TestCase):
    """Comprehensive unit tests for context extraction with Phase 1 improvements."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock all the complex dependencies to focus on context extraction
        with patch('function.fn.ContextCache'), \
             patch('function.fn.PerformanceOptimizer'), \
             patch('function.fn.SchemaRegistry'), \
             patch('function.fn.K8sClient') as mock_k8s, \
             patch('function.fn.ResourceResolver'), \
             patch('function.fn.ResourceSummarizer'), \
             patch('function.fn.QueryProcessor'), \
             patch('function.fn.ResponseGenerator'), \
             patch('function.fn.InsightsEngine'), \
             patch('function.fn.TransitiveDiscoveryEngine'):
            
            # Configure the K8s client mock
            mock_k8s.return_value._connected = False
            mock_k8s.return_value.connect = AsyncMock()
            
            self.function = KubeCoreContextFunction()
            self.function.logger = logging.getLogger(__name__)
            self.function.logger.setLevel(logging.DEBUG)

    def test_input_structure_inspection_finds_flag(self):
        """Test 1: Input structure inspection correctly finds enableTransitiveDiscovery."""
        request = {
            "input": {
                "spec": {
                    "context": {
                        "enableTransitiveDiscovery": True,
                        "transitiveMaxDepth": 3
                    },
                    "query": {"resourceType": "XGitHubProject"}
                }
            }
        }
        
        # This should not raise any exceptions and should log the discovery
        with self.assertLogs(level='DEBUG') as cm:
            self.function._inspect_input_structure(request)
            
        # Verify that the flag was found and logged
        debug_logs = ' '.join(cm.output)
        self.assertIn("FOUND enableTransitiveDiscovery", debug_logs)
        self.assertIn("request.input.spec.context.enableTransitiveDiscovery = True", debug_logs)

    def test_input_structure_inspection_handles_missing_flag(self):
        """Test 2: Input structure inspection handles missing enableTransitiveDiscovery gracefully."""
        request = {
            "input": {
                "spec": {
                    "query": {"resourceType": "XGitHubProject"}
                }
            }
        }
        
        with self.assertLogs(level='DEBUG') as cm:
            self.function._inspect_input_structure(request)
            
        debug_logs = ' '.join(cm.output)
        self.assertIn("enableTransitiveDiscovery NOT FOUND", debug_logs)

    def test_context_extraction_location_1_input_spec_context(self):
        """Test 3: Context extraction finds flag in input.spec.context (Location 1)."""
        request = {
            "observed": {
                "composite": {
                    "metadata": {"name": "test-app", "namespace": "default"},
                    "spec": {"githubProjectRef": {"name": "test-project"}}
                }
            }
        }
        
        input_spec = {
            "context": {
                "enableTransitiveDiscovery": True,
                "transitiveMaxDepth": 2
            }
        }
        
        context = self.function._extract_context(request, input_spec)
        
        self.assertTrue(context.get("enableTransitiveDiscovery"))
        self.assertEqual(context.get("transitiveMaxDepth"), 2)
        self.assertEqual(context.get("requestorName"), "test-app")

    def test_context_extraction_location_2_input_spec_direct(self):
        """Test 4: Context extraction finds flag directly in input.spec (Location 2)."""
        request = {
            "observed": {
                "composite": {
                    "metadata": {"name": "test-app", "namespace": "default"},
                    "spec": {}
                }
            }
        }
        
        input_spec = {
            "enableTransitiveDiscovery": True,
            "query": {"resourceType": "XGitHubProject"}
        }
        
        context = self.function._extract_context(request, input_spec)
        
        self.assertTrue(context.get("enableTransitiveDiscovery"))

    def test_context_extraction_location_3_request_input_context(self):
        """Test 5: Context extraction finds flag in request.input.context (Location 3)."""
        request = {
            "input": {
                "context": {
                    "enableTransitiveDiscovery": True,
                    "transitiveMaxDepth": 4
                }
            },
            "observed": {
                "composite": {
                    "metadata": {"name": "test-app", "namespace": "default"},
                    "spec": {}
                }
            }
        }
        
        input_spec = {}
        
        context = self.function._extract_context(request, input_spec)
        
        self.assertTrue(context.get("enableTransitiveDiscovery"))

    def test_context_extraction_location_4_request_input_direct(self):
        """Test 6: Context extraction finds flag directly in request.input (Location 4)."""
        request = {
            "input": {
                "enableTransitiveDiscovery": False,
                "spec": {"query": {"resourceType": "XGitHubProject"}}
            },
            "observed": {
                "composite": {
                    "metadata": {"name": "test-app", "namespace": "default"},
                    "spec": {}
                }
            }
        }
        
        input_spec = {}
        
        context = self.function._extract_context(request, input_spec)
        
        self.assertFalse(context.get("enableTransitiveDiscovery"))

    def test_context_extraction_flag_not_found(self):
        """Test 7: Context extraction handles case when flag is not found anywhere."""
        request = {
            "observed": {
                "composite": {
                    "metadata": {"name": "test-app", "namespace": "default"},
                    "spec": {}
                }
            }
        }
        
        input_spec = {}
        
        with self.assertLogs(level='WARNING') as cm:
            context = self.function._extract_context(request, input_spec)
            
        # Flag should not be present in context
        self.assertNotIn("enableTransitiveDiscovery", context)
        
        # Should log a warning
        warning_logs = ' '.join(cm.output)
        self.assertIn("enableTransitiveDiscovery not found", warning_logs)

    def test_context_extraction_priority_order(self):
        """Test 8: Context extraction respects priority order (Location 1 > 2 > 3 > 4)."""
        request = {
            "input": {
                "enableTransitiveDiscovery": False,  # Location 4 - lowest priority
                "context": {
                    "enableTransitiveDiscovery": False  # Location 3 - lower priority
                }
            },
            "observed": {
                "composite": {
                    "metadata": {"name": "test-app", "namespace": "default"},
                    "spec": {}
                }
            }
        }
        
        input_spec = {
            "enableTransitiveDiscovery": False,  # Location 2 - higher priority
            "context": {
                "enableTransitiveDiscovery": True   # Location 1 - highest priority
            }
        }
        
        context = self.function._extract_context(request, input_spec)
        
        # Should use value from Location 1 (highest priority)
        self.assertTrue(context.get("enableTransitiveDiscovery"))

    def test_context_extraction_preserves_references(self):
        """Test 9: Context extraction preserves all reference extraction logic."""
        request = {
            "observed": {
                "composite": {
                    "metadata": {"name": "test-app", "namespace": "default"},
                    "spec": {
                        "githubProjectRef": {"name": "project-1"},
                        "kubeClusterRefs": [{"name": "cluster-1"}, {"name": "cluster-2"}]
                    }
                }
            }
        }
        
        input_spec = {
            "context": {
                "enableTransitiveDiscovery": True,
                "references": {
                    "additionalRefs": [{"name": "additional-resource"}]
                }
            }
        }
        
        context = self.function._extract_context(request, input_spec)
        
        # Check composite spec references were extracted
        self.assertIn("githubProjectRefs", context["references"])
        self.assertIn("kubeClusterRefs", context["references"])
        
        # Check input.spec.context references were merged
        self.assertIn("additionalRefs", context["references"])
        
        # Check transitive flag
        self.assertTrue(context.get("enableTransitiveDiscovery"))

    def test_context_extraction_hub_resource_hints(self):
        """Test 10: Context extraction adds reverse discovery hints for hub resources."""
        request = {
            "observed": {
                "composite": {
                    "kind": "XGitHubProject",
                    "metadata": {"name": "demo-project", "namespace": "test"},
                    "spec": {}
                }
            }
        }
        
        input_spec = {"context": {"enableTransitiveDiscovery": True}}
        
        context = self.function._extract_context(request, input_spec)
        
        # Should add reverse discovery hints
        self.assertTrue(context.get("requiresReverseDiscovery"))
        self.assertIn("discoveryHints", context)
        
        hints = context["discoveryHints"]
        self.assertEqual(hints["targetRef"]["name"], "demo-project")
        self.assertEqual(hints["targetRef"]["kind"], "XGitHubProject")


class TestK8sRetryLogic(unittest.TestCase):
    """Test K8s client connection retry logic."""

    def setUp(self):
        """Set up test fixtures with mocked K8s client."""
        with patch('function.fn.ContextCache'), \
             patch('function.fn.PerformanceOptimizer'), \
             patch('function.fn.SchemaRegistry'), \
             patch('function.fn.K8sClient') as self.mock_k8s, \
             patch('function.fn.ResourceResolver'), \
             patch('function.fn.ResourceSummarizer'), \
             patch('function.fn.QueryProcessor'), \
             patch('function.fn.ResponseGenerator'), \
             patch('function.fn.InsightsEngine'), \
             patch('function.fn.TransitiveDiscoveryEngine'):
            
            self.function = KubeCoreContextFunction()
            self.function.logger = logging.getLogger(__name__)
            self.function.logger.setLevel(logging.DEBUG)

    async def test_k8s_retry_success_on_first_attempt(self):
        """Test 11: K8s connection succeeds on first attempt."""
        # Configure mock to succeed immediately
        self.function.k8s_client.connect = AsyncMock()
        
        await self.function._connect_k8s_with_retry()
        
        # Should be called exactly once
        self.function.k8s_client.connect.assert_called_once()

    async def test_k8s_retry_success_on_second_attempt(self):
        """Test 12: K8s connection succeeds on second attempt after retry."""
        # Configure mock to fail first time, succeed second time
        self.function.k8s_client.connect = AsyncMock(side_effect=[
            Exception("Connection failed"), 
            None  # Success on second attempt
        ])
        
        await self.function._connect_k8s_with_retry()
        
        # Should be called twice
        self.assertEqual(self.function.k8s_client.connect.call_count, 2)

    async def test_k8s_retry_fails_after_max_attempts(self):
        """Test 13: K8s connection fails after maximum retry attempts."""
        # Configure mock to always fail
        self.function.k8s_client.connect = AsyncMock(side_effect=Exception("Always fails"))
        
        with self.assertRaises(Exception) as cm:
            await self.function._connect_k8s_with_retry()
        
        # Should be called 3 times (max attempts)
        self.assertEqual(self.function.k8s_client.connect.call_count, 3)
        self.assertIn("3 attempts", str(cm.exception))


class TestAsyncScenarios(unittest.TestCase):
    """Test async execution scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        with patch('function.fn.ContextCache'), \
             patch('function.fn.PerformanceOptimizer'), \
             patch('function.fn.SchemaRegistry'), \
             patch('function.fn.K8sClient') as mock_k8s, \
             patch('function.fn.ResourceResolver'), \
             patch('function.fn.ResourceSummarizer'), \
             patch('function.fn.QueryProcessor') as mock_query_processor, \
             patch('function.fn.ResponseGenerator') as mock_response_gen, \
             patch('function.fn.InsightsEngine') as mock_insights, \
             patch('function.fn.TransitiveDiscoveryEngine'):
            
            # Configure mocks for async execution
            mock_k8s.return_value._connected = False
            mock_k8s.return_value.connect = AsyncMock()
            
            mock_query_processor.return_value.process_query = AsyncMock(return_value={"availableSchemas": {}})
            mock_response_gen.return_value.generate_response.return_value = {"spec": {"platformContext": {"availableSchemas": {}}}}
            mock_response_gen.return_value.validate_response_format.return_value = True
            mock_insights.return_value.generate_insights.return_value = []
            
            self.function = KubeCoreContextFunction()
            self.function.logger = logging.getLogger(__name__)

    async def test_async_execution_with_transitive_discovery_enabled(self):
        """Test 14: Full async execution with transitive discovery enabled."""
        request = {
            "input": {
                "spec": {
                    "query": {
                        "resourceType": "XGitHubProject",
                        "requestedSchemas": ["kubeCluster", "kubEnv"]
                    },
                    "context": {
                        "enableTransitiveDiscovery": True,
                        "transitiveMaxDepth": 3
                    }
                }
            },
            "observed": {
                "composite": {
                    "metadata": {"name": "demo-project", "namespace": "test"},
                    "spec": {"githubProjectRef": {"name": "demo-project"}}
                }
            }
        }
        
        # This should execute without errors and trigger K8s connection
        result = await self.function.run_function_async(request)
        
        # Should return a valid response
        self.assertIn("spec", result)
        
        # K8s client should have been connected due to transitive discovery
        self.function.k8s_client.connect.assert_called_once()


# Test execution utilities
def run_async_test(coro):
    """Helper to run async tests."""
    return asyncio.run(coro)


if __name__ == "__main__":
    # Configure logging for test execution
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestContextExtraction))
    suite.addTests(loader.loadTestsFromTestCase(TestK8sRetryLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestAsyncScenarios))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    if result.wasSuccessful():
        print("\n🎉 All Phase 1 tests PASSED!")
        sys.exit(0)
    else:
        print(f"\n❌ {len(result.failures + result.errors)} tests FAILED")
        sys.exit(1)