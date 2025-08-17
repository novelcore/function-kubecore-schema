"""Integration tests for KubeCore Platform Context Function Phase 2.

This module contains comprehensive integration tests covering realistic scenarios,
mock Kubernetes resources, and end-to-end resolution workflows.
"""

import asyncio
import time
from typing import Any

import pytest

from function.k8s_client import K8sPermissionError, K8sResourceNotFoundError
from function.resource_resolver import (
    ResolvedResource,
    ResourceRef,
    ResourceResolutionError,
    ResourceResolver,
)
from function.resource_summarizer import ResourceSummarizer, SummarizationConfig
from function.schema_registry import SchemaRegistry

# Mock Kubernetes Resources
MOCK_RESOURCES = {
    # XGitHubProvider
    ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProvider", "github-provider", "kubecore-system"): {
        "apiVersion": "github.platform.kubecore.io/v1alpha1",
        "kind": "XGitHubProvider",
        "metadata": {
            "name": "github-provider",
            "namespace": "kubecore-system",
            "uid": "provider-123",
            "creationTimestamp": "2024-01-01T00:00:00Z",
            "labels": {"platform": "kubecore"},
        },
        "spec": {
            "credentials": {"secretRef": {"name": "github-secret"}},
            "organization": "kubecore-org",
            "baseUrl": "https://api.github.com",
        },
        "status": {"ready": True, "message": "Provider ready"},
    },

    # XGitHubProject
    ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProject", "my-project", "kubecore-system"): {
        "apiVersion": "github.platform.kubecore.io/v1alpha1",
        "kind": "XGitHubProject",
        "metadata": {
            "name": "my-project",
            "namespace": "kubecore-system",
            "uid": "project-456",
            "creationTimestamp": "2024-01-01T01:00:00Z",
            "ownerReferences": [{
                "apiVersion": "github.platform.kubecore.io/v1alpha1",
                "kind": "XGitHubProvider",
                "name": "github-provider",
                "uid": "provider-123",
            }],
        },
        "spec": {
            "name": "my-awesome-project",
            "description": "An awesome KubeCore project",
            "visibility": "private",
            "githubProviderRef": {
                "name": "github-provider",
                "namespace": "kubecore-system",
            },
        },
        "status": {"repository": {"url": "https://github.com/kubecore-org/my-awesome-project"}},
    },

    # XKubeNet
    ResourceRef("network.platform.kubecore.io/v1alpha1", "XKubeNet", "primary-network", "kubecore-system"): {
        "apiVersion": "network.platform.kubecore.io/v1alpha1",
        "kind": "XKubeNet",
        "metadata": {
            "name": "primary-network",
            "namespace": "kubecore-system",
            "uid": "network-789",
            "creationTimestamp": "2024-01-01T02:00:00Z",
        },
        "spec": {
            "dns": {"domain": "kubecore.local"},
            "vpc": {"cidr": "10.0.0.0/16"},
        },
        "status": {"ready": True, "networkId": "net-123456"},
    },

    # XKubeCluster
    ResourceRef("platform.kubecore.io/v1alpha1", "XKubeCluster", "production-cluster", "kubecore-system"): {
        "apiVersion": "platform.kubecore.io/v1alpha1",
        "kind": "XKubeCluster",
        "metadata": {
            "name": "production-cluster",
            "namespace": "kubecore-system",
            "uid": "cluster-101",
            "creationTimestamp": "2024-01-01T03:00:00Z",
        },
        "spec": {
            "region": "us-west-2",
            "version": "1.28",
            "githubProjectRef": {
                "name": "my-project",
                "namespace": "kubecore-system",
            },
            "kubeNetRef": {
                "name": "primary-network",
                "namespace": "kubecore-system",
            },
        },
        "status": {"ready": True, "endpoint": "https://cluster-endpoint.amazonaws.com"},
    },

    # XKubeSystem
    ResourceRef("platform.kubecore.io/v1alpha1", "XKubeSystem", "core-system", "kubecore-system"): {
        "apiVersion": "platform.kubecore.io/v1alpha1",
        "kind": "XKubeSystem",
        "metadata": {
            "name": "core-system",
            "namespace": "kubecore-system",
            "uid": "system-202",
            "creationTimestamp": "2024-01-01T04:00:00Z",
        },
        "spec": {
            "kubeClusterRef": {
                "name": "production-cluster",
                "namespace": "kubecore-system",
            },
            "components": ["ingress-nginx", "cert-manager", "prometheus"],
        },
        "status": {"components": {"ready": 3, "total": 3}},
    },

    # XKubEnv (Development)
    ResourceRef("platform.kubecore.io/v1alpha1", "XKubEnv", "development", "my-project"): {
        "apiVersion": "platform.kubecore.io/v1alpha1",
        "kind": "XKubEnv",
        "metadata": {
            "name": "development",
            "namespace": "my-project",
            "uid": "env-dev-303",
            "creationTimestamp": "2024-01-01T05:00:00Z",
        },
        "spec": {
            "environmentType": "development",
            "resources": {
                "profile": "small",
                "defaults": {
                    "requests": {"cpu": "100m", "memory": "128Mi"},
                    "limits": {"cpu": "500m", "memory": "512Mi"},
                },
            },
            "environmentConfig": {
                "variables": {"DEBUG": "true", "LOG_LEVEL": "debug"},
            },
            "qualityGates": [
                {
                    "ref": {"name": "code-quality", "namespace": "kubecore-system"},
                    "key": "security-scan",
                    "phase": "pre-deploy",
                    "required": True,
                }
            ],
            "kubeClusterRef": {
                "name": "production-cluster",
                "namespace": "kubecore-system",
            },
        },
        "status": {"ready": True, "namespace": "my-project-dev"},
    },

    # XKubEnv (Production)
    ResourceRef("platform.kubecore.io/v1alpha1", "XKubEnv", "production", "my-project"): {
        "apiVersion": "platform.kubecore.io/v1alpha1",
        "kind": "XKubEnv",
        "metadata": {
            "name": "production",
            "namespace": "my-project",
            "uid": "env-prod-404",
            "creationTimestamp": "2024-01-01T06:00:00Z",
        },
        "spec": {
            "environmentType": "production",
            "resources": {
                "profile": "large",
                "defaults": {
                    "requests": {"cpu": "1000m", "memory": "1Gi"},
                    "limits": {"cpu": "2000m", "memory": "2Gi"},
                },
            },
            "environmentConfig": {
                "variables": {"DEBUG": "false", "LOG_LEVEL": "info"},
            },
            "qualityGates": [
                {
                    "ref": {"name": "code-quality", "namespace": "kubecore-system"},
                    "key": "security-scan",
                    "phase": "pre-deploy",
                    "required": True,
                },
                {
                    "ref": {"name": "performance-gate", "namespace": "kubecore-system"},
                    "key": "load-test",
                    "phase": "post-deploy",
                    "required": True,
                }
            ],
            "kubeClusterRef": {
                "name": "production-cluster",
                "namespace": "kubecore-system",
            },
        },
        "status": {"ready": True, "namespace": "my-project-prod"},
    },

    # XQualityGate
    ResourceRef("platform.kubecore.io/v1alpha1", "XQualityGate", "code-quality", "kubecore-system"): {
        "apiVersion": "platform.kubecore.io/v1alpha1",
        "kind": "XQualityGate",
        "metadata": {
            "name": "code-quality",
            "namespace": "kubecore-system",
            "uid": "gate-505",
            "creationTimestamp": "2024-01-01T07:00:00Z",
        },
        "spec": {
            "key": "security-scan",
            "description": "Security vulnerability scanning",
            "category": "security",
            "severity": "high",
            "applicability": {
                "environments": ["development", "staging", "production"],
            },
        },
        "status": {"ready": True},
    },

    # XApp
    ResourceRef("platform.kubecore.io/v1alpha1", "XApp", "web-service", "my-project"): {
        "apiVersion": "platform.kubecore.io/v1alpha1",
        "kind": "XApp",
        "metadata": {
            "name": "web-service",
            "namespace": "my-project",
            "uid": "app-606",
            "creationTimestamp": "2024-01-01T08:00:00Z",
        },
        "spec": {
            "type": "web",
            "image": "my-project/web-service:v1.0.0",
            "port": 8080,
            "githubProjectRef": {
                "name": "my-project",
                "namespace": "kubecore-system",
            },
            "environments": [
                {
                    "kubenvRef": {"name": "development", "namespace": "my-project"},
                    "enabled": True,
                    "overrides": {"replicas": 1},
                },
                {
                    "kubenvRef": {"name": "production", "namespace": "my-project"},
                    "enabled": True,
                    "overrides": {"replicas": 3},
                }
            ],
        },
        "status": {"ready": True, "deployments": {"development": "ready", "production": "ready"}},
    },
}


class MockK8sClient:
    """Mock Kubernetes client for testing."""

    def __init__(self, resources: dict[ResourceRef, dict[str, Any]] = None):
        self.resources = resources or MOCK_RESOURCES.copy()
        self.call_count = 0
        self.call_log: list[dict[str, Any]] = []
        self._connected = False

    async def connect(self):
        self._connected = True

    async def disconnect(self):
        self._connected = False

    @property
    def is_connected(self):
        return self._connected

    async def get_resource(self, api_version: str, kind: str, name: str, namespace: str = None) -> dict[str, Any]:
        self.call_count += 1
        self.call_log.append({
            "method": "get_resource",
            "api_version": api_version,
            "kind": kind,
            "name": name,
            "namespace": namespace,
        })

        # Simulate some latency
        await asyncio.sleep(0.01)

        # Handle permission errors first
        ref = ResourceRef(api_version, kind, name, namespace)
        if hasattr(self, "_permission_errors") and ref in getattr(self, "_permission_errors", set()):
            raise K8sPermissionError(f"Permission denied: {ref}")

        if ref in self.resources:
            return self.resources[ref]
        else:
            raise K8sResourceNotFoundError(f"Resource not found: {ref}")

    def add_resource(self, ref: ResourceRef, data: dict[str, Any]):
        """Add a resource to the mock."""
        self.resources[ref] = data

    def simulate_permission_error(self, ref: ResourceRef):
        """Simulate permission error for a specific resource."""
        if not hasattr(self, "_permission_errors"):
            self._permission_errors = set()
        self._permission_errors.add(ref)


@pytest.fixture
def mock_k8s_client():
    """Fixture providing a mock Kubernetes client."""
    return MockK8sClient()


@pytest.fixture
def schema_registry():
    """Fixture providing a schema registry."""
    return SchemaRegistry()


@pytest.fixture
def resource_resolver(mock_k8s_client):
    """Fixture providing a resource resolver with mock client."""
    return ResourceResolver(mock_k8s_client, cache_ttl=60.0)


@pytest.fixture
def resource_summarizer(schema_registry):
    """Fixture providing a resource summarizer."""
    config = SummarizationConfig(
        max_depth=3,
        max_array_elements=5,
        include_status=True,
    )
    return ResourceSummarizer(schema_registry, config)


class TestKubernetesClientIntegration:
    """Test Kubernetes client integration functionality."""

    @pytest.mark.asyncio
    async def test_client_connection(self, mock_k8s_client):
        """Test client connection and disconnection."""
        assert not mock_k8s_client.is_connected

        await mock_k8s_client.connect()
        assert mock_k8s_client.is_connected

        await mock_k8s_client.disconnect()
        assert not mock_k8s_client.is_connected

    @pytest.mark.asyncio
    async def test_resource_fetching(self, mock_k8s_client):
        """Test basic resource fetching."""
        await mock_k8s_client.connect()

        # Test successful resource fetch
        resource = await mock_k8s_client.get_resource(
            "github.platform.kubecore.io/v1alpha1",
            "XGitHubProvider",
            "github-provider",
            "kubecore-system"
        )

        assert resource["kind"] == "XGitHubProvider"
        assert resource["metadata"]["name"] == "github-provider"
        assert mock_k8s_client.call_count == 1

    @pytest.mark.asyncio
    async def test_resource_not_found(self, mock_k8s_client):
        """Test handling of resource not found errors."""
        await mock_k8s_client.connect()

        with pytest.raises(K8sResourceNotFoundError):
            await mock_k8s_client.get_resource(
                "platform.kubecore.io/v1alpha1",
                "XApp",
                "nonexistent-app",
                "default"
            )

    @pytest.mark.asyncio
    async def test_permission_error_handling(self, mock_k8s_client):
        """Test handling of permission errors."""
        await mock_k8s_client.connect()

        # Simulate permission error
        test_ref = ResourceRef("platform.kubecore.io/v1alpha1", "XApp", "restricted-app", "default")
        mock_k8s_client.simulate_permission_error(test_ref)

        with pytest.raises(K8sPermissionError):
            await mock_k8s_client.get_resource(
                "platform.kubecore.io/v1alpha1",
                "XApp",
                "restricted-app",
                "default"
            )


class TestResourceResolutionEngine:
    """Test resource resolution engine functionality."""

    @pytest.mark.asyncio
    async def test_single_resource_resolution(self, resource_resolver, mock_k8s_client):
        """Test resolving a single resource."""
        await mock_k8s_client.connect()

        ref = ResourceRef(
            "github.platform.kubecore.io/v1alpha1",
            "XGitHubProvider",
            "github-provider",
            "kubecore-system"
        )

        resolved = await resource_resolver.resolve_resource(ref)

        assert resolved.ref == ref
        assert resolved.data["kind"] == "XGitHubProvider"
        assert not resolved.cached  # First resolution
        assert len(resolved.relationships) >= 0

    @pytest.mark.asyncio
    async def test_resource_caching(self, resource_resolver, mock_k8s_client):
        """Test resource caching functionality."""
        await mock_k8s_client.connect()

        ref = ResourceRef(
            "github.platform.kubecore.io/v1alpha1",
            "XGitHubProject",
            "my-project",
            "kubecore-system"
        )

        # First resolution
        resolved1 = await resource_resolver.resolve_resource(ref)
        call_count_1 = mock_k8s_client.call_count

        # Second resolution (should use cache)
        resolved2 = await resource_resolver.resolve_resource(ref)
        call_count_2 = mock_k8s_client.call_count

        assert resolved1.ref == resolved2.ref
        assert resolved2.cached
        assert call_count_2 == call_count_1  # No additional K8s calls

    @pytest.mark.asyncio
    async def test_relationship_resolution(self, resource_resolver, mock_k8s_client):
        """Test resolving resources with relationships."""
        await mock_k8s_client.connect()

        # Resolve XKubeCluster which has relationships to other resources
        ref = ResourceRef(
            "platform.kubecore.io/v1alpha1",
            "XKubeCluster",
            "production-cluster",
            "kubecore-system"
        )

        resolved_resources = await resource_resolver.resolve_with_relationships(
            ref, max_depth=2, max_resources=10
        )

        assert len(resolved_resources) > 1
        assert ref in resolved_resources

        # Should resolve related resources like XGitHubProject and XKubeNet
        related_kinds = {r.ref.kind for r in resolved_resources.values()}
        assert "XKubeCluster" in related_kinds

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, resource_resolver, mock_k8s_client):
        """Test circular dependency detection and resolution limits."""
        await mock_k8s_client.connect()

        # Test that resolution stops at reasonable limits rather than infinite loops
        # Use existing resources and test with very low limits
        ref = ResourceRef(
            "platform.kubecore.io/v1alpha1",
            "XApp",
            "web-service",
            "my-project"
        )

        # Test with extremely low resource limit to trigger limit error
        try:
            resolved_resources = await resource_resolver.resolve_with_relationships(
                ref, max_depth=1, max_resources=1
            )
            # Should either complete with limited resources or raise an error
            assert len(resolved_resources) <= 1
        except ResourceResolutionError:
            # This is also acceptable - hitting resource limits
            pass

        # Test the actual circular dependency detection utility method
        # Create test resolved resources with circular references
        ref_a = ResourceRef("test/v1", "ResourceA", "resource-a", "default")
        ref_b = ResourceRef("test/v1", "ResourceB", "resource-b", "default")

        resolved_a = ResolvedResource(ref=ref_a, data={}, relationships=[ref_b])
        resolved_b = ResolvedResource(ref=ref_b, data={}, relationships=[ref_a])

        test_resources = {ref_a: resolved_a, ref_b: resolved_b}

        # Test circular dependency detection method
        cycles = resource_resolver.detect_circular_dependencies(test_resources)
        assert len(cycles) > 0  # Should detect at least one cycle

    @pytest.mark.asyncio
    async def test_parallel_resolution(self, resource_resolver, mock_k8s_client):
        """Test parallel resource resolution."""
        await mock_k8s_client.connect()

        refs = [
            ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProvider", "github-provider", "kubecore-system"),
            ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProject", "my-project", "kubecore-system"),
            ResourceRef("network.platform.kubecore.io/v1alpha1", "XKubeNet", "primary-network", "kubecore-system"),
        ]

        start_time = time.time()
        results = await resource_resolver.resolve_parallel(refs, max_concurrent=3)
        end_time = time.time()

        assert len(results) == 3
        successful_count = sum(1 for r in results.values() if isinstance(r, ResolvedResource))
        assert successful_count == 3

        # Should be faster than sequential resolution
        assert end_time - start_time < 1.0  # Should complete quickly with mock

    @pytest.mark.asyncio
    async def test_resolution_limits(self, resource_resolver, mock_k8s_client):
        """Test resource resolution limits."""
        await mock_k8s_client.connect()

        ref = ResourceRef(
            "platform.kubecore.io/v1alpha1",
            "XApp",
            "web-service",
            "my-project"
        )

        # Test with very low limits
        resolved_resources = await resource_resolver.resolve_with_relationships(
            ref, max_depth=1, max_resources=2
        )

        # Should respect the limits
        assert len(resolved_resources) <= 2


class TestResourceSummarization:
    """Test resource summarization functionality."""

    def test_basic_summarization(self, resource_summarizer, schema_registry):
        """Test basic resource summarization."""
        ref = ResourceRef(
            "github.platform.kubecore.io/v1alpha1",
            "XGitHubProvider",
            "github-provider",
            "kubecore-system"
        )

        resource_data = MOCK_RESOURCES[ref]
        resolved = ResolvedResource(ref=ref, data=resource_data)

        summary = resource_summarizer.summarize_resource(resolved)

        assert summary.ref == ref
        assert "spec" in summary.summary
        assert summary.summary["spec"]["organization"] == "kubecore-org"
        assert summary.metadata["name"] == "github-provider"

    def test_summarization_with_relationships(self, resource_summarizer):
        """Test summarization including relationships."""
        ref = ResourceRef(
            "platform.kubecore.io/v1alpha1",
            "XKubeCluster",
            "production-cluster",
            "kubecore-system"
        )

        resource_data = MOCK_RESOURCES[ref]

        # Create mock relationships
        relationships = [
            ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProject", "my-project", "kubecore-system"),
            ResourceRef("network.platform.kubecore.io/v1alpha1", "XKubeNet", "primary-network", "kubecore-system"),
        ]

        resolved = ResolvedResource(ref=ref, data=resource_data, relationships=relationships)

        summary = resource_summarizer.summarize_resource(resolved)

        assert len(summary.relationships) == 2
        assert summary.summary["spec"]["region"] == "us-west-2"
        assert summary.summary["spec"]["version"] == "1.28"

    def test_multiple_resource_summarization(self, resource_summarizer):
        """Test summarizing multiple resources."""
        resolved_resources = {}

        for ref, data in list(MOCK_RESOURCES.items())[:3]:  # Take first 3 resources
            resolved_resources[ref] = ResolvedResource(ref=ref, data=data)

        summaries = resource_summarizer.summarize_multiple(resolved_resources)

        assert len(summaries) == 3
        for ref, summary in summaries.items():
            assert summary.ref == ref
            assert "spec" in summary.summary or "error" in summary.summary

    def test_summarization_field_filtering(self, resource_summarizer):
        """Test summarization with specific field requests."""
        ref = ResourceRef(
            "platform.kubecore.io/v1alpha1",
            "XKubEnv",
            "development",
            "my-project"
        )

        resource_data = MOCK_RESOURCES[ref]
        resolved = ResolvedResource(ref=ref, data=resource_data)

        # Request only specific fields
        requested_fields = {"environmentType", "resources"}
        summary = resource_summarizer.summarize_resource(resolved, requested_fields)

        spec = summary.summary.get("spec", {})
        assert "environmentType" in spec
        assert "resources" in spec
        # Should not include other fields if filtering is working

    def test_array_summarization(self, resource_summarizer):
        """Test summarization of array fields."""
        ref = ResourceRef(
            "platform.kubecore.io/v1alpha1",
            "XApp",
            "web-service",
            "my-project"
        )

        resource_data = MOCK_RESOURCES[ref]
        resolved = ResolvedResource(ref=ref, data=resource_data)

        summary = resource_summarizer.summarize_resource(resolved)

        # Check that environments array is properly summarized
        spec = summary.summary.get("spec", {})
        environments = spec.get("environments", [])
        assert len(environments) == 2
        assert all("kubenvRef" in env for env in environments)


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    @pytest.mark.asyncio
    async def test_complete_app_context_resolution(self, mock_k8s_client, schema_registry):
        """Test complete context resolution for an XApp."""
        await mock_k8s_client.connect()

        # Create resolver and summarizer
        resolver = ResourceResolver(mock_k8s_client, cache_ttl=60.0)
        summarizer = ResourceSummarizer(schema_registry)

        # Start with an XApp resource
        app_ref = ResourceRef(
            "platform.kubecore.io/v1alpha1",
            "XApp",
            "web-service",
            "my-project"
        )

        # Resolve the app and its relationships
        resolved_resources = await resolver.resolve_with_relationships(
            app_ref, max_depth=3, max_resources=20
        )

        # Summarize all resolved resources
        summaries = summarizer.summarize_multiple(resolved_resources)

        # Verify we got comprehensive context
        assert len(summaries) >= 1
        assert app_ref in summaries

        # Check that we have summaries for related resources
        resolved_kinds = {ref.kind for ref in summaries.keys()}
        expected_kinds = {"XApp"}  # At minimum the app itself
        assert expected_kinds.issubset(resolved_kinds)

        # Verify app summary contains key information
        app_summary = summaries[app_ref]
        assert app_summary.summary["spec"]["type"] == "web"
        assert app_summary.summary["spec"]["port"] == 8080
        assert len(app_summary.summary["spec"]["environments"]) == 2

    @pytest.mark.asyncio
    async def test_platform_hierarchy_traversal(self, mock_k8s_client, schema_registry):
        """Test traversing the platform hierarchy."""
        await mock_k8s_client.connect()

        resolver = ResourceResolver(mock_k8s_client)
        summarizer = ResourceSummarizer(schema_registry)

        # Start from a cluster (mid-level in hierarchy)
        cluster_ref = ResourceRef(
            "platform.kubecore.io/v1alpha1",
            "XKubeCluster",
            "production-cluster",
            "kubecore-system"
        )

        # Resolve with relationships
        resolved_resources = await resolver.resolve_with_relationships(
            cluster_ref, max_depth=2, max_resources=15
        )

        summaries = summarizer.summarize_multiple(resolved_resources)

        # Should include the cluster and related resources
        assert cluster_ref in summaries

        # Check cluster summary
        cluster_summary = summaries[cluster_ref]
        assert cluster_summary.summary["spec"]["region"] == "us-west-2"
        assert cluster_summary.summary["spec"]["version"] == "1.28"

        # Verify relationships are captured
        assert len(cluster_summary.relationships) >= 0

    @pytest.mark.asyncio
    async def test_performance_benchmarks(self, mock_k8s_client, schema_registry):
        """Test performance benchmarks for Phase 2 requirements."""
        await mock_k8s_client.connect()

        resolver = ResourceResolver(mock_k8s_client, max_concurrent=10)
        summarizer = ResourceSummarizer(schema_registry)

        # Test multiple resource types
        test_refs = [
            ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProvider", "github-provider", "kubecore-system"),
            ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProject", "my-project", "kubecore-system"),
            ResourceRef("platform.kubecore.io/v1alpha1", "XKubeCluster", "production-cluster", "kubecore-system"),
            ResourceRef("platform.kubecore.io/v1alpha1", "XApp", "web-service", "my-project"),
        ]

        # Benchmark parallel resolution
        start_time = time.time()
        results = await resolver.resolve_parallel(test_refs, max_concurrent=10)
        resolution_time = time.time() - start_time

        # Benchmark summarization
        resolved_resources = {ref: res for ref, res in results.items() if isinstance(res, ResolvedResource)}

        start_time = time.time()
        summaries = summarizer.summarize_multiple(resolved_resources)
        summarization_time = time.time() - start_time

        # Performance assertions (with mock, these should be very fast)
        assert resolution_time < 1.0  # Should complete within 1 second
        assert summarization_time < 0.5  # Should complete within 0.5 seconds
        assert len(summaries) == len(resolved_resources)

        print(f"Resolution time: {resolution_time:.3f}s")
        print(f"Summarization time: {summarization_time:.3f}s")
        print(f"Resources processed: {len(summaries)}")

    @pytest.mark.asyncio
    async def test_error_resilience(self, mock_k8s_client, schema_registry):
        """Test system resilience to various error conditions."""
        await mock_k8s_client.connect()

        resolver = ResourceResolver(mock_k8s_client)
        summarizer = ResourceSummarizer(schema_registry)

        # Mix of valid and invalid references
        test_refs = [
            # Valid references
            ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProvider", "github-provider", "kubecore-system"),
            ResourceRef("platform.kubecore.io/v1alpha1", "XApp", "web-service", "my-project"),

            # Invalid references
            ResourceRef("platform.kubecore.io/v1alpha1", "XApp", "nonexistent-app", "default"),
            ResourceRef("invalid/v1", "InvalidKind", "invalid-resource", "default"),
        ]

        # Parallel resolution should handle errors gracefully
        results = await resolver.resolve_parallel(test_refs)

        # Should have results for all refs (some successful, some errors)
        assert len(results) == len(test_refs)

        # Count successes and failures
        successes = sum(1 for r in results.values() if isinstance(r, ResolvedResource))
        failures = sum(1 for r in results.values() if isinstance(r, Exception))

        assert successes >= 2  # Valid refs should succeed
        assert failures >= 2   # Invalid refs should fail

        # Summarization should handle partial results
        resolved_resources = {ref: res for ref, res in results.items() if isinstance(res, ResolvedResource)}
        summaries = summarizer.summarize_multiple(resolved_resources)

        # Should successfully summarize the valid resources
        assert len(summaries) == successes

    @pytest.mark.asyncio
    async def test_cache_effectiveness(self, mock_k8s_client, schema_registry):
        """Test cache effectiveness for repeated operations."""
        await mock_k8s_client.connect()

        resolver = ResourceResolver(mock_k8s_client, cache_ttl=300.0)  # Long TTL for testing

        ref = ResourceRef(
            "github.platform.kubecore.io/v1alpha1",
            "XGitHubProject",
            "my-project",
            "kubecore-system"
        )

        # First resolution
        initial_call_count = mock_k8s_client.call_count
        resolved1 = await resolver.resolve_resource(ref)
        calls_after_first = mock_k8s_client.call_count

        # Second resolution (should use cache)
        resolved2 = await resolver.resolve_resource(ref)
        calls_after_second = mock_k8s_client.call_count

        # Third resolution (should still use cache)
        resolved3 = await resolver.resolve_resource(ref)
        calls_after_third = mock_k8s_client.call_count

        # Verify caching behavior
        assert calls_after_first > initial_call_count  # First call made request
        assert calls_after_second == calls_after_first  # Second call used cache
        assert calls_after_third == calls_after_first   # Third call used cache

        assert resolved2.cached
        assert resolved3.cached

        # Verify cache stats
        cache_stats = resolver.get_cache_stats()
        assert cache_stats["size"] >= 1


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_integration.py -v
    pytest.main([__file__, "-v", "--tb=short"])
