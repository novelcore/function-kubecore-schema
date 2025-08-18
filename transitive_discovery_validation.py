#!/usr/bin/env python3
"""Validation script for transitive discovery implementation."""

import asyncio
import json
import logging
import sys
import time
from unittest.mock import AsyncMock, MagicMock

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

# Add current directory to path for imports
sys.path.insert(0, '.')

from function.transitive_discovery import (
    TransitiveDiscoveryEngine,
    TransitiveDiscoveryConfig,
    TransitiveDiscoveredResource,
    TRANSITIVE_RELATIONSHIP_CHAINS
)
from function.resource_resolver import ResourceRef


class TransitiveDiscoveryValidator:
    """Validator for transitive discovery functionality."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.mock_k8s_data = self._create_mock_k8s_data()

    def _create_mock_k8s_data(self) -> dict:
        """Create mock Kubernetes data for testing."""
        return {
            "XGitHubProject": [
                {
                    "metadata": {"name": "demo-project", "namespace": "test"},
                    "spec": {"githubProviderRef": {"name": "github-prod", "namespace": "test"}}
                }
            ],
            "XKubeCluster": [
                {
                    "metadata": {"name": "demo-cluster", "namespace": "test"},
                    "spec": {"githubProjectRef": {"name": "demo-project", "namespace": "test"}}
                }
            ],
            "XKubEnv": [
                {
                    "metadata": {"name": "demo-dev", "namespace": "test"},
                    "spec": {"kubeClusterRef": {"name": "demo-cluster", "namespace": "test"}}
                },
                {
                    "metadata": {"name": "demo-prod", "namespace": "test"},
                    "spec": {"kubeClusterRef": {"name": "demo-cluster", "namespace": "test"}}
                }
            ],
            "XApp": [
                {
                    "metadata": {"name": "art-api", "namespace": "test"},
                    "spec": {
                        "kubenvRef": {"name": "demo-dev", "namespace": "test"},
                        "githubProjectRef": {"name": "demo-project", "namespace": "test"}
                    }
                }
            ],
            "XGitHubApp": [
                {
                    "metadata": {"name": "art-api-repo", "namespace": "test"},
                    "spec": {"githubProjectRef": {"name": "demo-project", "namespace": "test"}}
                }
            ],
            "XKubeSystem": [
                {
                    "metadata": {"name": "demo-system", "namespace": "test"},
                    "spec": {"kubeClusterRef": {"name": "demo-cluster", "namespace": "test"}}
                }
            ]
        }

    def _create_mock_resource_resolver(self) -> MagicMock:
        """Create a mock resource resolver with test data."""
        resolver = MagicMock()
        resolver.k8s_client = MagicMock()

        async def mock_list_resources(api_version, kind, limit=100):
            items = self.mock_k8s_data.get(kind, [])
            return {"items": items}

        resolver.k8s_client.list_resources = AsyncMock(side_effect=mock_list_resources)
        return resolver

    async def test_relationship_chains(self) -> bool:
        """Test that relationship chains are properly defined."""
        print("🔍 Testing relationship chain definitions...")
        
        try:
            # Test that all expected chains are defined
            expected_sources = ["XGitHubProject", "XKubeCluster", "XKubEnv", "XApp"]
            for source in expected_sources:
                if source not in TRANSITIVE_RELATIONSHIP_CHAINS:
                    print(f"❌ Missing relationship chains for {source}")
                    return False
                chains = TRANSITIVE_RELATIONSHIP_CHAINS[source]
                print(f"✅ {source} has {len(chains)} relationship chains")
                
                for target_kind, ref_chain in chains:
                    print(f"   → {target_kind} via {' → '.join(ref_chain)}")
            
            return True
        except Exception as e:
            print(f"❌ Relationship chain test failed: {e}")
            return False

    async def test_basic_discovery(self) -> bool:
        """Test basic transitive discovery functionality."""
        print("\n🔍 Testing basic transitive discovery...")
        
        try:
            # Create engine with mock resolver
            mock_resolver = self._create_mock_resource_resolver()
            config = TransitiveDiscoveryConfig(
                max_depth=2,
                max_resources_per_type=10,
                timeout_per_depth=5.0
            )
            engine = TransitiveDiscoveryEngine(mock_resolver, config)
            
            # Test discovery for GitHub project
            target_ref = {
                "name": "demo-project",
                "namespace": "test",
                "kind": "XGitHubProject",
                "apiVersion": "github.platform.kubecore.io/v1alpha1"
            }
            
            result = await engine.discover_transitive_relationships(
                target_ref, "XGitHubProject", {}
            )
            
            print(f"✅ Discovery completed, found {len(result)} schema types:")
            for schema_type, resources in result.items():
                print(f"   - {schema_type}: {len(resources)} resources")
                for resource in resources:
                    print(f"     * {resource.name} ({resource.discovery_method}, {resource.discovery_hops} hops)")
            
            # Verify expected discoveries
            if "kubeCluster" not in result:
                print("❌ Expected to find kubeCluster resources")
                return False
                
            if "kubEnv" not in result:
                print("❌ Expected to find kubEnv resources")  
                return False
                
            return True
        except Exception as e:
            print(f"❌ Basic discovery test failed: {e}")
            return False

    async def test_performance_monitoring(self) -> bool:
        """Test performance monitoring capabilities."""
        print("\n🔍 Testing performance monitoring...")
        
        try:
            mock_resolver = self._create_mock_resource_resolver()
            config = TransitiveDiscoveryConfig(
                circuit_breaker_enabled=True,
                memory_limit_mb=10
            )
            engine = TransitiveDiscoveryEngine(mock_resolver, config)
            
            # Perform some operations to generate stats
            target_ref = {
                "name": "demo-project",
                "namespace": "test",
                "kind": "XGitHubProject"
            }
            await engine.discover_transitive_relationships(target_ref, "XGitHubProject", {})
            
            # Check performance stats
            stats = engine.get_performance_stats()
            required_fields = ["total_api_calls", "failed_api_calls", "success_rate", "discovered_resources"]
            
            for field in required_fields:
                if field not in stats:
                    print(f"❌ Missing performance stat: {field}")
                    return False
            
            print(f"✅ Performance stats collected:")
            print(f"   - Total API calls: {stats['total_api_calls']}")
            print(f"   - Success rate: {stats['success_rate']:.2%}")
            print(f"   - Discovered resources: {stats['discovered_resources']}")
            print(f"   - Memory usage: {stats['estimated_memory_mb']:.2f} MB")
            
            # Test health check
            health = engine.is_healthy()
            print(f"✅ Engine health check: {'Healthy' if health else 'Unhealthy'}")
            
            return True
        except Exception as e:
            print(f"❌ Performance monitoring test failed: {e}")
            return False

    async def test_circuit_breaker(self) -> bool:
        """Test circuit breaker functionality."""
        print("\n🔍 Testing circuit breaker...")
        
        try:
            mock_resolver = self._create_mock_resource_resolver()
            
            # Mock failures for one resource type
            original_list_resources = mock_resolver.k8s_client.list_resources
            
            async def failing_list_resources(api_version, kind, limit=100):
                if kind == "XKubeCluster":
                    raise Exception("Simulated API failure")
                return await original_list_resources(api_version, kind, limit)
            
            mock_resolver.k8s_client.list_resources = AsyncMock(side_effect=failing_list_resources)
            
            config = TransitiveDiscoveryConfig(
                circuit_breaker_enabled=True,
                circuit_breaker_threshold=2
            )
            engine = TransitiveDiscoveryEngine(mock_resolver, config)
            
            # Trigger failures to open circuit breaker
            target_ref = {"name": "test", "namespace": "test", "kind": "XGitHubProject"}
            
            for i in range(3):
                await engine.discover_transitive_relationships(target_ref, "XGitHubProject", {})
            
            # Check circuit breaker status
            stats = engine.get_performance_stats()
            cluster_breaker = stats["circuit_breakers"].get("XKubeCluster", {})
            
            if cluster_breaker.get("state") != "open":
                print(f"❌ Circuit breaker should be open, but is {cluster_breaker.get('state')}")
                return False
            
            print("✅ Circuit breaker opened after failures")
            return True
        except Exception as e:
            print(f"❌ Circuit breaker test failed: {e}")
            return False

    async def test_caching(self) -> bool:
        """Test intermediate result caching."""
        print("\n🔍 Testing caching functionality...")
        
        try:
            mock_resolver = self._create_mock_resource_resolver()
            config = TransitiveDiscoveryConfig(cache_intermediate_results=True)
            engine = TransitiveDiscoveryEngine(mock_resolver, config)
            
            # Perform operation that should cache results
            test_data = [{"name": "test-resource", "namespace": "test"}]
            cache_key = "test-cache-key"
            
            # Test cache miss
            result = engine._get_from_intermediate_cache(cache_key)
            if result is not None:
                print("❌ Expected cache miss")
                return False
            
            # Test cache put and hit
            engine._put_in_intermediate_cache(cache_key, test_data)
            result = engine._get_from_intermediate_cache(cache_key)
            
            if result != test_data:
                print("❌ Cache hit returned wrong data")
                return False
            
            print("✅ Caching functionality works correctly")
            
            # Test cache stats
            stats = engine.get_performance_stats()
            if "cache_entries" not in stats:
                print("❌ Cache stats missing")
                return False
            
            print(f"✅ Cache contains {stats['cache_entries']} entries")
            return True
        except Exception as e:
            print(f"❌ Caching test failed: {e}")
            return False

    async def test_configuration(self) -> bool:
        """Test configuration management."""
        print("\n🔍 Testing configuration management...")
        
        try:
            # Test configuration creation
            config = TransitiveDiscoveryConfig(
                max_depth=5,
                max_resources_per_type=100,
                timeout_per_depth=15.0,
                parallel_workers=8,
                circuit_breaker_threshold=10
            )
            
            if config.max_depth != 5:
                print("❌ Configuration not set correctly")
                return False
            
            # Test engine configuration
            mock_resolver = self._create_mock_resource_resolver()
            engine = TransitiveDiscoveryEngine(mock_resolver, config)
            
            original_depth = engine.config.max_depth
            engine.update_config(max_depth=7)
            
            if engine.config.max_depth != 7:
                print("❌ Configuration update failed")
                return False
            
            print("✅ Configuration management works correctly")
            return True
        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
            return False

    async def run_all_tests(self) -> bool:
        """Run all validation tests."""
        print("🚀 Starting Transitive Discovery Validation")
        print("=" * 50)
        
        tests = [
            self.test_relationship_chains,
            self.test_basic_discovery,
            self.test_performance_monitoring,
            self.test_circuit_breaker,
            self.test_caching,
            self.test_configuration
        ]
        
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                print(f"❌ Test {test.__name__} failed with exception: {e}")
                results.append(False)
        
        print("\n" + "=" * 50)
        print("📊 VALIDATION RESULTS")
        print("=" * 50)
        
        passed = sum(results)
        total = len(results)
        
        print(f"Tests Passed: {passed}/{total}")
        print(f"Success Rate: {passed/total:.1%}")
        
        if passed == total:
            print("✅ ALL TESTS PASSED - Transitive Discovery implementation is valid!")
            return True
        else:
            print("❌ Some tests failed - Please review implementation")
            return False


async def main():
    """Main validation function."""
    validator = TransitiveDiscoveryValidator()
    success = await validator.run_all_tests()
    
    if success:
        print("\n🎉 Transitive Discovery implementation is ready for production!")
        sys.exit(0)
    else:
        print("\n⚠️  Please address test failures before deployment")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())