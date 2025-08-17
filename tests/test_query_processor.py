"""Tests for QueryProcessor and end-to-end query processing functionality."""

from unittest.mock import AsyncMock

import pytest

from function.insights_engine import InsightsEngine
from function.k8s_client import K8sClient
from function.query_processor import QueryProcessor
from function.resource_resolver import ResourceResolver
from function.resource_summarizer import ResourceSummarizer
from function.response_generator import ResponseGenerator
from function.schema_registry import SchemaRegistry


class TestQueryProcessor:
    """Test cases for QueryProcessor class."""

    @pytest.fixture
    def mock_k8s_client(self):
        """Create a mock K8s client."""
        client = AsyncMock(spec=K8sClient)
        return client

    @pytest.fixture
    def schema_registry(self):
        """Create a schema registry instance."""
        return SchemaRegistry()

    @pytest.fixture
    def resource_resolver(self, mock_k8s_client):
        """Create a resource resolver with mock client."""
        return ResourceResolver(mock_k8s_client)

    @pytest.fixture
    def resource_summarizer(self, mock_k8s_client):
        """Create a resource summarizer with mock client."""
        return ResourceSummarizer(mock_k8s_client)

    @pytest.fixture
    def query_processor(self, schema_registry, resource_resolver, resource_summarizer):
        """Create a query processor instance."""
        return QueryProcessor(schema_registry, resource_resolver, resource_summarizer)

    @pytest.fixture
    def response_generator(self, schema_registry):
        """Create a response generator instance."""
        return ResponseGenerator(schema_registry)

    @pytest.fixture
    def insights_engine(self, schema_registry):
        """Create an insights engine instance."""
        return InsightsEngine(schema_registry)

    @pytest.mark.asyncio
    async def test_app_query_processing(self, query_processor):
        """Test XApp query processing with kubEnv references."""
        input_spec = {
            "query": {
                "resourceType": "XApp",
                "requestedSchemas": ["kubEnv"]
            },
            "context": {
                "requestorName": "art-api",
                "requestorNamespace": "default",
                "references": {
                    "kubEnvRefs": [
                        {"name": "demo-dev", "namespace": "test"}
                    ]
                }
            }
        }

        result = await query_processor.process_query(input_spec)

        # Verify basic structure
        assert result["requestor"]["type"] == "XApp"
        assert result["requestor"]["name"] == "art-api"
        assert result["requestor"]["namespace"] == "default"

        # Verify schemas are present
        assert "kubEnv" in result["availableSchemas"]
        kubenv_schema = result["availableSchemas"]["kubEnv"]

        # Verify schema metadata
        assert kubenv_schema["metadata"]["apiVersion"] == "platform.kubecore.io/v1alpha1"
        assert kubenv_schema["metadata"]["kind"] == "XKubEnv"
        assert kubenv_schema["metadata"]["accessible"] is True
        assert kubenv_schema["metadata"]["relationshipPath"] == ["app", "kubEnv"]

        # Verify instances
        assert len(kubenv_schema["instances"]) == 1
        instance = kubenv_schema["instances"][0]
        assert instance["name"] == "demo-dev"
        assert instance["namespace"] == "test"
        assert "environmentType" in instance["summary"]
        assert "resources" in instance["summary"]

        # Verify relationships
        assert "direct" in result["relationships"]
        relationships = result["relationships"]["direct"]
        kubenv_rel = next((r for r in relationships if r["type"] == "kubEnv"), None)
        assert kubenv_rel is not None
        assert kubenv_rel["cardinality"] == "N:N"

    @pytest.mark.asyncio
    async def test_kubesystem_query_processing(self, query_processor):
        """Test XKubeSystem query processing."""
        input_spec = {
            "query": {
                "resourceType": "XKubeSystem",
                "requestedSchemas": ["kubeCluster", "kubEnv"]
            },
            "context": {
                "requestorName": "demo-system",
                "requestorNamespace": "kube-system",
                "references": {
                    "kubeClusterRefs": [
                        {"name": "demo-cluster", "namespace": "default"}
                    ],
                    "kubEnvRefs": [
                        {"name": "demo-prod", "namespace": "production"}
                    ]
                }
            }
        }

        result = await query_processor.process_query(input_spec)

        # Verify requestor
        assert result["requestor"]["type"] == "XKubeSystem"
        assert result["requestor"]["name"] == "demo-system"

        # Verify both schemas are present
        assert "kubeCluster" in result["availableSchemas"]
        assert "kubEnv" in result["availableSchemas"]

        # Verify cluster instance
        cluster_schema = result["availableSchemas"]["kubeCluster"]
        assert len(cluster_schema["instances"]) == 1
        cluster_instance = cluster_schema["instances"][0]
        assert cluster_instance["name"] == "demo-cluster"
        assert "version" in cluster_instance["summary"]
        assert "nodeCount" in cluster_instance["summary"]

        # Verify environment instance
        env_schema = result["availableSchemas"]["kubEnv"]
        assert len(env_schema["instances"]) == 1
        env_instance = env_schema["instances"][0]
        assert env_instance["name"] == "demo-prod"
        assert "systemComponents" in env_instance["summary"]

    @pytest.mark.asyncio
    async def test_kubenv_query_processing(self, query_processor):
        """Test XKubEnv query processing."""
        input_spec = {
            "query": {
                "resourceType": "XKubEnv",
                "requestedSchemas": ["qualityGate", "kubeCluster"]
            },
            "context": {
                "requestorName": "demo-env",
                "requestorNamespace": "default",
                "references": {
                    "qualityGateRefs": [
                        {"name": "security-gate", "namespace": "default"}
                    ],
                    "kubeClusterRefs": [
                        {"name": "demo-cluster", "namespace": "default"}
                    ]
                }
            }
        }

        result = await query_processor.process_query(input_spec)

        # Verify requestor
        assert result["requestor"]["type"] == "XKubEnv"
        assert result["requestor"]["name"] == "demo-env"

        # Verify schemas
        assert "qualityGate" in result["availableSchemas"]
        assert "kubeCluster" in result["availableSchemas"]

        # Verify quality gate instance
        qg_schema = result["availableSchemas"]["qualityGate"]
        qg_instance = qg_schema["instances"][0]
        assert qg_instance["name"] == "security-gate"
        assert "category" in qg_instance["summary"]
        assert "required" in qg_instance["summary"]

    @pytest.mark.asyncio
    async def test_generic_query_processing(self, query_processor):
        """Test generic query processing for unknown resource types."""
        input_spec = {
            "query": {
                "resourceType": "XCustomResource",
                "requestedSchemas": ["githubProject"]
            },
            "context": {
                "requestorName": "custom-resource",
                "requestorNamespace": "default",
                "references": {
                    "githubProjectRefs": [
                        {"name": "demo-project", "namespace": "default"}
                    ]
                }
            }
        }

        result = await query_processor.process_query(input_spec)

        # Verify basic processing works for unknown types
        assert result["requestor"]["type"] == "XCustomResource"
        assert result["requestor"]["name"] == "custom-resource"
        assert "availableSchemas" in result
        assert "relationships" in result

    @pytest.mark.asyncio
    async def test_empty_references(self, query_processor):
        """Test query processing with no references."""
        input_spec = {
            "query": {
                "resourceType": "XApp",
                "requestedSchemas": ["kubEnv"]
            },
            "context": {
                "requestorName": "lonely-app",
                "requestorNamespace": "default",
                "references": {}
            }
        }

        result = await query_processor.process_query(input_spec)

        # Should still return valid structure with empty schemas
        assert result["requestor"]["type"] == "XApp"
        assert "kubEnv" in result["availableSchemas"]
        assert len(result["availableSchemas"]["kubEnv"]["instances"]) == 0

    @pytest.mark.asyncio
    async def test_missing_resource_type(self, query_processor):
        """Test query processing with missing resource type."""
        input_spec = {
            "query": {
                "requestedSchemas": ["kubEnv"]
            },
            "context": {
                "requestorName": "test-app",
                "requestorNamespace": "default"
            }
        }

        with pytest.raises(ValueError, match="resourceType is required"):
            await query_processor.process_query(input_spec)


class TestResponseGenerator:
    """Test cases for ResponseGenerator class."""

    @pytest.fixture
    def schema_registry(self):
        """Create a schema registry instance."""
        return SchemaRegistry()

    @pytest.fixture
    def response_generator(self, schema_registry):
        """Create a response generator instance."""
        return ResponseGenerator(schema_registry)

    def test_generate_response_format(self, response_generator):
        """Test that response matches exact expected format."""
        platform_context = {
            "requestor": {
                "type": "XApp",
                "name": "art-api",
                "namespace": "default"
            },
            "availableSchemas": {
                "kubEnv": {
                    "metadata": {
                        "apiVersion": "platform.kubecore.io/v1alpha1",
                        "kind": "XKubEnv",
                        "accessible": True,
                        "relationshipPath": ["app", "kubEnv"]
                    },
                    "instances": [
                        {
                            "name": "demo-dev",
                            "namespace": "test",
                            "summary": {
                                "environmentType": "dev",
                                "resources": {
                                    "profile": "small",
                                    "defaults": {
                                        "requests": {"cpu": "100m", "memory": "128Mi"}
                                    }
                                },
                                "qualityGates": ["security-scan"]
                            }
                        }
                    ]
                }
            },
            "relationships": {
                "direct": [
                    {
                        "type": "kubEnv",
                        "cardinality": "N:N",
                        "description": "App can deploy to multiple environments"
                    }
                ]
            },
            "insights": {}
        }

        query = {"resourceType": "XApp"}

        result = response_generator.generate_response(platform_context, query)

        # Verify top-level structure
        assert result["apiVersion"] == "context.fn.kubecore.io/v1beta1"
        assert result["kind"] == "Output"
        assert "spec" in result

        # Verify spec structure
        spec = result["spec"]
        assert "platformContext" in spec

        # Verify platform context
        pc = spec["platformContext"]
        assert pc["requestor"]["type"] == "XApp"
        assert pc["requestor"]["name"] == "art-api"
        assert pc["requestor"]["namespace"] == "default"

        # Verify schemas are present and filtered
        assert "kubEnv" in pc["availableSchemas"]
        kubenv = pc["availableSchemas"]["kubEnv"]
        assert len(kubenv["instances"]) == 1

        # Verify filtering worked (XApp should get environment info)
        instance = kubenv["instances"][0]
        summary = instance["summary"]
        assert "environmentType" in summary
        assert "resources" in summary
        assert "qualityGates" in summary

    def test_schema_filtering_for_app(self, response_generator):
        """Test schema filtering specific to XApp resource type."""
        schema_data = {
            "metadata": {"apiVersion": "test", "kind": "test", "accessible": True, "relationshipPath": []},
            "instances": [
                {
                    "name": "test-instance",
                    "namespace": "default",
                    "summary": {
                        "environmentType": "dev",
                        "resources": {"profile": "small"},
                        "environmentConfig": {"variables": {}},
                        "qualityGates": ["test"],
                        "irrelevantField": "should-be-filtered",
                        "systemInternalData": "not-for-apps"
                    }
                }
            ]
        }

        filtered = response_generator.filter_schema_for_resource_type(schema_data, "XApp")

        # Verify structure preserved
        assert "metadata" in filtered
        assert len(filtered["instances"]) == 1

        # Verify filtering worked
        instance = filtered["instances"][0]
        summary = instance["summary"]
        assert "environmentType" in summary
        assert "resources" in summary
        assert "environmentConfig" in summary
        assert "qualityGates" in summary
        assert "irrelevantField" not in summary
        assert "systemInternalData" not in summary

    def test_schema_filtering_for_kubesystem(self, response_generator):
        """Test schema filtering specific to XKubeSystem resource type."""
        schema_data = {
            "metadata": {"apiVersion": "test", "kind": "test", "accessible": True, "relationshipPath": []},
            "instances": [
                {
                    "name": "test-cluster",
                    "namespace": "default",
                    "summary": {
                        "version": "1.28.0",
                        "region": "us-west-2",
                        "nodeCount": 3,
                        "status": "ready",
                        "systemComponents": ["ingress"],
                        "capacity": {"cpu": "16"},
                        "appSpecificData": "should-be-filtered"
                    }
                }
            ]
        }

        filtered = response_generator.filter_schema_for_resource_type(schema_data, "XKubeSystem")

        instance = filtered["instances"][0]
        summary = instance["summary"]
        assert "version" in summary
        assert "region" in summary
        assert "nodeCount" in summary
        assert "status" in summary
        assert "systemComponents" in summary
        assert "capacity" in summary
        assert "appSpecificData" not in summary

    def test_response_format_validation(self, response_generator):
        """Test response format validation."""
        # Valid response
        valid_response = {
            "apiVersion": "context.fn.kubecore.io/v1beta1",
            "kind": "Output",
            "spec": {
                "platformContext": {
                    "requestor": {
                        "type": "XApp",
                        "name": "test-app",
                        "namespace": "default"
                    },
                    "availableSchemas": {
                        "kubEnv": {
                            "metadata": {
                                "apiVersion": "platform.kubecore.io/v1alpha1",
                                "kind": "XKubEnv",
                                "accessible": True,
                                "relationshipPath": ["app", "kubEnv"]
                            },
                            "instances": [
                                {
                                    "name": "test-env",
                                    "namespace": "default",
                                    "summary": {}
                                }
                            ]
                        }
                    },
                    "relationships": {},
                    "insights": {}
                }
            }
        }

        assert response_generator.validate_response_format(valid_response) is True

        # Invalid responses
        invalid_responses = [
            {},  # Empty
            {"apiVersion": "wrong"},  # Wrong API version
            {
                "apiVersion": "context.fn.kubecore.io/v1beta1",
                "kind": "Wrong"  # Wrong kind
            },
            {
                "apiVersion": "context.fn.kubecore.io/v1beta1",
                "kind": "Output",
                "spec": {}  # Missing platformContext
            }
        ]

        for invalid_response in invalid_responses:
            assert response_generator.validate_response_format(invalid_response) is False


class TestInsightsEngine:
    """Test cases for InsightsEngine class."""

    @pytest.fixture
    def schema_registry(self):
        """Create a schema registry instance."""
        return SchemaRegistry()

    @pytest.fixture
    def insights_engine(self, schema_registry):
        """Create an insights engine instance."""
        return InsightsEngine(schema_registry)

    def test_app_insights_generation(self, insights_engine):
        """Test insights generation for XApp resources."""
        platform_context = {
            "availableSchemas": {
                "kubEnv": {
                    "instances": [
                        {
                            "name": "prod-env",
                            "summary": {"environmentType": "prod"}
                        },
                        {
                            "name": "dev-env",
                            "summary": {"environmentType": "dev"}
                        }
                    ]
                }
            },
            "relationships": {"direct": []}
        }

        insights = insights_engine.generate_insights(platform_context, "XApp")

        # Verify structure
        assert "recommendations" in insights
        assert "validationRules" in insights
        assert "suggestedReferences" in insights

        # Verify XApp-specific recommendations
        recommendations = insights["recommendations"]
        assert len(recommendations) > 0

        # Check for specific recommendation categories
        categories = [r["category"] for r in recommendations]
        assert "resource-optimization" in categories
        assert "security" in categories

        # Check for environment-specific recommendations
        prod_recs = [r for r in recommendations if "production" in r.get("suggestion", "").lower()]
        dev_recs = [r for r in recommendations if "development" in r.get("suggestion", "").lower()]
        assert len(prod_recs) > 0 or len(dev_recs) > 0

        # Verify validation rules
        assert len(insights["validationRules"]) > 0

        # Verify suggested references
        ref_types = [r["type"] for r in insights["suggestedReferences"]]
        assert "kubEnv" in ref_types

    def test_kubesystem_insights_generation(self, insights_engine):
        """Test insights generation for XKubeSystem resources."""
        platform_context = {
            "availableSchemas": {
                "kubeCluster": {
                    "instances": [
                        {
                            "name": "old-cluster",
                            "summary": {"version": "1.25.0"}  # Old version
                        }
                    ]
                }
            },
            "relationships": {"direct": []}
        }

        insights = insights_engine.generate_insights(platform_context, "XKubeSystem")

        # Verify structure
        assert "recommendations" in insights

        recommendations = insights["recommendations"]
        categories = [r["category"] for r in recommendations]

        # Should include infrastructure and security recommendations
        assert "infrastructure" in categories
        assert "security" in categories

        # Should recommend cluster upgrade for old version
        upgrade_recs = [r for r in recommendations if "upgrade" in r.get("suggestion", "").lower()]
        assert len(upgrade_recs) > 0

    def test_kubenv_insights_generation(self, insights_engine):
        """Test insights generation for XKubEnv resources."""
        platform_context = {
            "requestor": {"name": "test-env"},
            "availableSchemas": {
                "qualityGate": {
                    "instances": [{"name": "security-gate"}]
                }
            },
            "relationships": {"direct": []}
        }

        insights = insights_engine.generate_insights(platform_context, "XKubEnv")

        recommendations = insights["recommendations"]
        categories = [r["category"] for r in recommendations]

        # Should include configuration and quality assurance
        assert "configuration" in categories
        assert "quality-assurance" in categories

    def test_cross_cutting_insights(self, insights_engine):
        """Test cross-cutting insights that apply to all resource types."""
        platform_context = {
            "availableSchemas": {},  # No schemas available
            "relationships": {"direct": []}
        }

        insights = insights_engine.generate_insights(platform_context, "XApp")

        recommendations = insights["recommendations"]

        # Should suggest adding references when no schemas are available
        context_recs = [r for r in recommendations if r["category"] == "context"]
        assert len(context_recs) > 0

        # Should include compliance recommendations
        compliance_recs = [r for r in recommendations if r["category"] == "compliance"]
        assert len(compliance_recs) > 0


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @pytest.fixture
    def mock_k8s_client(self):
        """Create a mock K8s client."""
        return AsyncMock(spec=K8sClient)

    @pytest.fixture
    def complete_system(self, mock_k8s_client):
        """Create a complete query processing system."""
        schema_registry = SchemaRegistry()
        resource_resolver = ResourceResolver(mock_k8s_client)
        resource_summarizer = ResourceSummarizer(mock_k8s_client)
        query_processor = QueryProcessor(schema_registry, resource_resolver, resource_summarizer)
        response_generator = ResponseGenerator(schema_registry)
        insights_engine = InsightsEngine(schema_registry)

        return {
            "query_processor": query_processor,
            "response_generator": response_generator,
            "insights_engine": insights_engine
        }

    @pytest.mark.asyncio
    async def test_complete_app_workflow(self, complete_system):
        """Test complete workflow from query to final response."""
        query_processor = complete_system["query_processor"]
        response_generator = complete_system["response_generator"]
        insights_engine = complete_system["insights_engine"]

        # Step 1: Process query
        input_spec = {
            "query": {
                "resourceType": "XApp",
                "requestedSchemas": ["kubEnv"]
            },
            "context": {
                "requestorName": "art-api",
                "requestorNamespace": "default",
                "references": {
                    "kubEnvRefs": [
                        {"name": "demo-dev", "namespace": "test"}
                    ]
                }
            }
        }

        platform_context = await query_processor.process_query(input_spec)

        # Step 2: Generate insights
        insights = insights_engine.generate_insights(platform_context, "XApp")
        platform_context["insights"] = insights

        # Step 3: Generate final response
        final_response = response_generator.generate_response(
            platform_context,
            input_spec["query"]
        )

        # Verify complete response structure
        assert final_response["apiVersion"] == "context.fn.kubecore.io/v1beta1"
        assert final_response["kind"] == "Output"

        # Verify platform context
        pc = final_response["spec"]["platformContext"]
        assert pc["requestor"]["type"] == "XApp"
        assert pc["requestor"]["name"] == "art-api"

        # Verify schemas
        assert "kubEnv" in pc["availableSchemas"]
        kubenv = pc["availableSchemas"]["kubEnv"]
        assert len(kubenv["instances"]) == 1

        # Verify insights
        assert "recommendations" in pc["insights"]
        assert len(pc["insights"]["recommendations"]) > 0

        # Verify response format validation
        assert response_generator.validate_response_format(final_response) is True

    @pytest.mark.asyncio
    async def test_response_format_compliance(self, complete_system):
        """Test that all generated responses comply with the specification."""
        query_processor = complete_system["query_processor"]
        response_generator = complete_system["response_generator"]
        insights_engine = complete_system["insights_engine"]

        # Test different resource types
        test_cases = [
            {
                "resourceType": "XApp",
                "requestedSchemas": ["kubEnv", "githubProject"]
            },
            {
                "resourceType": "XKubeSystem",
                "requestedSchemas": ["kubeCluster"]
            },
            {
                "resourceType": "XKubEnv",
                "requestedSchemas": ["qualityGate"]
            }
        ]

        for query in test_cases:
            input_spec = {
                "query": query,
                "context": {
                    "requestorName": f"test-{query['resourceType'].lower()}",
                    "requestorNamespace": "default",
                    "references": {}
                }
            }

            # Process through complete pipeline
            platform_context = await query_processor.process_query(input_spec)
            insights = insights_engine.generate_insights(platform_context, query["resourceType"])
            platform_context["insights"] = insights
            final_response = response_generator.generate_response(platform_context, query)

            # Verify format compliance
            assert response_generator.validate_response_format(final_response) is True

            # Verify requestor matches
            requestor = final_response["spec"]["platformContext"]["requestor"]
            assert requestor["type"] == query["resourceType"]
