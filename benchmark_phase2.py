#!/usr/bin/env python3
"""Performance Benchmarks for KubeCore Platform Context Function Phase 2.

This script measures performance against Phase 2 requirements:
- Resource resolution < 2 seconds for typical scenarios
- Memory usage < 100MB for standard deployments
- Concurrent request handling (min 10 simultaneous)
"""

import asyncio
import gc
import logging
import statistics
import time
from typing import Any

import psutil

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import our Phase 2 modules
from function.resource_resolver import ResolvedResource, ResourceRef, ResourceResolver
from function.resource_summarizer import ResourceSummarizer
from function.schema_registry import SchemaRegistry

# Import test resources from integration tests
from tests.test_integration import MOCK_RESOURCES, MockK8sClient


class PerformanceBenchmark:
    """Performance benchmark suite for Phase 2 implementation."""

    def __init__(self):
        self.results: dict[str, Any] = {}
        self.schema_registry = SchemaRegistry()

    async def run_all_benchmarks(self) -> dict[str, Any]:
        """Run all performance benchmarks."""
        logger.info("Starting Phase 2 Performance Benchmarks")

        # Create mock client with extended resource set
        mock_client = self._create_large_mock_client()

        # Run individual benchmarks
        await self.benchmark_single_resource_resolution(mock_client)
        await self.benchmark_relationship_resolution(mock_client)
        await self.benchmark_parallel_resolution(mock_client)
        await self.benchmark_resource_summarization(mock_client)
        await self.benchmark_concurrent_requests(mock_client)
        await self.benchmark_memory_usage(mock_client)
        await self.benchmark_cache_performance(mock_client)

        # Analyze results
        self._analyze_results()

        return self.results

    def _create_large_mock_client(self) -> MockK8sClient:
        """Create a mock client with more resources for realistic testing."""
        extended_resources = MOCK_RESOURCES.copy()

        # Add more resources for comprehensive testing
        for i in range(20):
            # Add more XApp resources
            app_ref = ResourceRef(
                "platform.kubecore.io/v1alpha1",
                "XApp",
                f"app-service-{i}",
                "test-project"
            )
            extended_resources[app_ref] = {
                "apiVersion": "platform.kubecore.io/v1alpha1",
                "kind": "XApp",
                "metadata": {
                    "name": f"app-service-{i}",
                    "namespace": "test-project",
                    "uid": f"app-{i}-uid",
                    "creationTimestamp": "2024-01-01T08:00:00Z",
                },
                "spec": {
                    "type": "web",
                    "image": f"test-project/app-service-{i}:v1.0.0",
                    "port": 8080 + i,
                    "githubProjectRef": {
                        "name": "my-project",
                        "namespace": "kubecore-system",
                    },
                    "environments": [
                        {
                            "kubenvRef": {"name": "development", "namespace": "test-project"},
                            "enabled": True,
                        }
                    ],
                },
                "status": {"ready": True},
            }

            # Add corresponding XKubEnv resources
            env_ref = ResourceRef(
                "platform.kubecore.io/v1alpha1",
                "XKubEnv",
                f"env-{i}",
                "test-project"
            )
            extended_resources[env_ref] = {
                "apiVersion": "platform.kubecore.io/v1alpha1",
                "kind": "XKubEnv",
                "metadata": {
                    "name": f"env-{i}",
                    "namespace": "test-project",
                    "uid": f"env-{i}-uid",
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
                    "kubeClusterRef": {
                        "name": "production-cluster",
                        "namespace": "kubecore-system",
                    },
                },
                "status": {"ready": True},
            }

        return MockK8sClient(extended_resources)

    async def benchmark_single_resource_resolution(self, mock_client: MockK8sClient):
        """Benchmark single resource resolution performance."""
        logger.info("Benchmarking single resource resolution...")

        await mock_client.connect()
        resolver = ResourceResolver(mock_client, cache_ttl=60.0)

        # Test different resource types
        test_refs = [
            ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProvider", "github-provider", "kubecore-system"),
            ResourceRef("platform.kubecore.io/v1alpha1", "XKubeCluster", "production-cluster", "kubecore-system"),
            ResourceRef("platform.kubecore.io/v1alpha1", "XApp", "web-service", "my-project"),
        ]

        resolution_times = []

        for ref in test_refs:
            start_time = time.time()
            try:
                resolved = await resolver.resolve_resource(ref)
                end_time = time.time()
                resolution_times.append(end_time - start_time)
            except Exception as e:
                logger.warning(f"Failed to resolve {ref}: {e}")

        avg_time = statistics.mean(resolution_times) if resolution_times else float("inf")
        max_time = max(resolution_times) if resolution_times else float("inf")

        self.results["single_resource_resolution"] = {
            "average_time": avg_time,
            "max_time": max_time,
            "successful_resolutions": len(resolution_times),
            "meets_requirement": max_time < 0.5,  # Should be much faster than 2s for single resource
        }

        logger.info(f"Single resource resolution - Avg: {avg_time:.3f}s, Max: {max_time:.3f}s")

    async def benchmark_relationship_resolution(self, mock_client: MockK8sClient):
        """Benchmark resource resolution with relationships."""
        logger.info("Benchmarking relationship resolution...")

        await mock_client.connect()
        resolver = ResourceResolver(mock_client, cache_ttl=60.0)

        # Test with complex resource that has multiple relationships
        ref = ResourceRef("platform.kubecore.io/v1alpha1", "XApp", "web-service", "my-project")

        start_time = time.time()
        try:
            resolved_resources = await resolver.resolve_with_relationships(
                ref, max_depth=3, max_resources=20
            )
            end_time = time.time()

            resolution_time = end_time - start_time
            resource_count = len(resolved_resources)

            self.results["relationship_resolution"] = {
                "resolution_time": resolution_time,
                "resources_resolved": resource_count,
                "meets_requirement": resolution_time < 2.0,  # Phase 2 requirement
                "avg_time_per_resource": resolution_time / resource_count if resource_count > 0 else float("inf"),
            }

            logger.info(f"Relationship resolution - Time: {resolution_time:.3f}s, Resources: {resource_count}")

        except Exception as e:
            logger.error(f"Relationship resolution failed: {e}")
            self.results["relationship_resolution"] = {
                "resolution_time": float("inf"),
                "resources_resolved": 0,
                "meets_requirement": False,
                "error": str(e),
            }

    async def benchmark_parallel_resolution(self, mock_client: MockK8sClient):
        """Benchmark parallel resource resolution."""
        logger.info("Benchmarking parallel resolution...")

        await mock_client.connect()
        resolver = ResourceResolver(mock_client, max_concurrent=10)

        # Create multiple references for parallel resolution
        test_refs = []
        for i in range(15):
            test_refs.append(ResourceRef(
                "platform.kubecore.io/v1alpha1",
                "XApp",
                f"app-service-{i}",
                "test-project"
            ))

        start_time = time.time()
        try:
            results = await resolver.resolve_parallel(test_refs, max_concurrent=10)
            end_time = time.time()

            resolution_time = end_time - start_time
            successful_count = sum(1 for r in results.values() if isinstance(r, ResolvedResource))

            self.results["parallel_resolution"] = {
                "resolution_time": resolution_time,
                "total_resources": len(test_refs),
                "successful_resolutions": successful_count,
                "meets_requirement": resolution_time < 2.0,
                "throughput": successful_count / resolution_time if resolution_time > 0 else 0,
            }

            logger.info(f"Parallel resolution - Time: {resolution_time:.3f}s, Success: {successful_count}/{len(test_refs)}")

        except Exception as e:
            logger.error(f"Parallel resolution failed: {e}")
            self.results["parallel_resolution"] = {
                "resolution_time": float("inf"),
                "meets_requirement": False,
                "error": str(e),
            }

    async def benchmark_resource_summarization(self, mock_client: MockK8sClient):
        """Benchmark resource summarization performance."""
        logger.info("Benchmarking resource summarization...")

        await mock_client.connect()
        resolver = ResourceResolver(mock_client)
        summarizer = ResourceSummarizer(self.schema_registry)

        # Resolve multiple resources
        test_refs = [
            ResourceRef("github.platform.kubecore.io/v1alpha1", "XGitHubProvider", "github-provider", "kubecore-system"),
            ResourceRef("platform.kubecore.io/v1alpha1", "XKubeCluster", "production-cluster", "kubecore-system"),
            ResourceRef("platform.kubecore.io/v1alpha1", "XApp", "web-service", "my-project"),
        ]

        # Add more app resources
        for i in range(10):
            test_refs.append(ResourceRef(
                "platform.kubecore.io/v1alpha1",
                "XApp",
                f"app-service-{i}",
                "test-project"
            ))

        # Resolve resources first
        results = await resolver.resolve_parallel(test_refs)
        resolved_resources = {ref: res for ref, res in results.items() if isinstance(res, ResolvedResource)}

        # Benchmark summarization
        start_time = time.time()
        try:
            summaries = summarizer.summarize_multiple(resolved_resources)
            end_time = time.time()

            summarization_time = end_time - start_time
            resource_count = len(resolved_resources)

            self.results["resource_summarization"] = {
                "summarization_time": summarization_time,
                "resources_summarized": len(summaries),
                "total_resources": resource_count,
                "avg_time_per_resource": summarization_time / resource_count if resource_count > 0 else 0,
                "meets_requirement": summarization_time < 1.0,  # Should be fast
            }

            logger.info(f"Summarization - Time: {summarization_time:.3f}s, Resources: {len(summaries)}")

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            self.results["resource_summarization"] = {
                "summarization_time": float("inf"),
                "meets_requirement": False,
                "error": str(e),
            }

    async def benchmark_concurrent_requests(self, mock_client: MockK8sClient):
        """Benchmark concurrent request handling."""
        logger.info("Benchmarking concurrent request handling...")

        await mock_client.connect()

        # Create multiple resolvers to simulate concurrent requests
        resolvers = [ResourceResolver(mock_client, max_concurrent=5) for _ in range(10)]

        async def simulate_request(resolver_idx: int):
            """Simulate a single request."""
            resolver = resolvers[resolver_idx]
            ref = ResourceRef(
                "platform.kubecore.io/v1alpha1",
                "XApp",
                f"app-service-{resolver_idx}",
                "test-project"
            )

            start_time = time.time()
            try:
                resolved_resources = await resolver.resolve_with_relationships(
                    ref, max_depth=2, max_resources=10
                )
                end_time = time.time()

                return {
                    "success": True,
                    "time": end_time - start_time,
                    "resources": len(resolved_resources),
                }
            except Exception as e:
                end_time = time.time()
                return {
                    "success": False,
                    "time": end_time - start_time,
                    "error": str(e),
                }

        # Run concurrent requests
        start_time = time.time()
        tasks = [simulate_request(i) for i in range(10)]
        request_results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        total_time = end_time - start_time
        successful_requests = sum(1 for r in request_results if isinstance(r, dict) and r.get("success"))
        avg_request_time = statistics.mean([
            r["time"] for r in request_results
            if isinstance(r, dict) and "time" in r
        ]) if request_results else 0

        self.results["concurrent_requests"] = {
            "total_time": total_time,
            "successful_requests": successful_requests,
            "total_requests": len(tasks),
            "avg_request_time": avg_request_time,
            "meets_requirement": successful_requests >= 10 and avg_request_time < 2.0,
            "throughput": successful_requests / total_time if total_time > 0 else 0,
        }

        logger.info(f"Concurrent requests - Success: {successful_requests}/10, Avg time: {avg_request_time:.3f}s")

    async def benchmark_memory_usage(self, mock_client: MockK8sClient):
        """Benchmark memory usage during operations."""
        logger.info("Benchmarking memory usage...")

        # Force garbage collection before measurement
        gc.collect()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        await mock_client.connect()
        resolver = ResourceResolver(mock_client)
        summarizer = ResourceSummarizer(self.schema_registry)

        # Perform intensive operations
        test_refs = []
        for i in range(50):  # More resources for memory testing
            test_refs.append(ResourceRef(
                "platform.kubecore.io/v1alpha1",
                "XApp",
                f"app-service-{i}",
                "test-project"
            ))

        # Resolution phase
        results = await resolver.resolve_parallel(test_refs, max_concurrent=10)
        resolved_resources = {ref: res for ref, res in results.items() if isinstance(res, ResolvedResource)}

        # Summarization phase
        summaries = summarizer.summarize_multiple(resolved_resources)

        # Measure memory after operations
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_usage = final_memory - initial_memory

        self.results["memory_usage"] = {
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_usage_mb": memory_usage,
            "resources_processed": len(resolved_resources),
            "meets_requirement": memory_usage < 100,  # Phase 2 requirement
            "memory_per_resource": memory_usage / len(resolved_resources) if resolved_resources else 0,
        }

        logger.info(f"Memory usage - Used: {memory_usage:.2f}MB, Resources: {len(resolved_resources)}")

    async def benchmark_cache_performance(self, mock_client: MockK8sClient):
        """Benchmark cache performance impact."""
        logger.info("Benchmarking cache performance...")

        await mock_client.connect()

        # Test with caching enabled
        resolver_with_cache = ResourceResolver(mock_client, cache_ttl=300.0)

        # Test with caching disabled
        resolver_no_cache = ResourceResolver(mock_client, cache_ttl=0.0)

        test_ref = ResourceRef(
            "platform.kubecore.io/v1alpha1",
            "XApp",
            "web-service",
            "my-project"
        )

        # Benchmark with cache - first run
        start_time = time.time()
        await resolver_with_cache.resolve_resource(test_ref)
        first_run_time = time.time() - start_time

        # Benchmark with cache - second run (should be faster)
        start_time = time.time()
        await resolver_with_cache.resolve_resource(test_ref)
        cached_run_time = time.time() - start_time

        # Benchmark without cache
        start_time = time.time()
        await resolver_no_cache.resolve_resource(test_ref)
        no_cache_time = time.time() - start_time

        cache_improvement = (first_run_time - cached_run_time) / first_run_time * 100 if first_run_time > 0 else 0

        self.results["cache_performance"] = {
            "first_run_time": first_run_time,
            "cached_run_time": cached_run_time,
            "no_cache_time": no_cache_time,
            "cache_improvement_percent": cache_improvement,
            "cache_effective": cached_run_time < first_run_time,
        }

        logger.info(f"Cache performance - Improvement: {cache_improvement:.1f}%")

    def _analyze_results(self):
        """Analyze benchmark results against Phase 2 requirements."""
        logger.info("Analyzing benchmark results...")

        # Check Phase 2 requirements
        requirements_met = {
            "resource_resolution_time": self.results.get("relationship_resolution", {}).get("meets_requirement", False),
            "memory_usage": self.results.get("memory_usage", {}).get("meets_requirement", False),
            "concurrent_handling": self.results.get("concurrent_requests", {}).get("meets_requirement", False),
        }

        all_requirements_met = all(requirements_met.values())

        self.results["phase2_compliance"] = {
            "requirements_met": requirements_met,
            "all_requirements_met": all_requirements_met,
            "summary": self._generate_summary(),
        }

        logger.info(f"Phase 2 Compliance: {'PASS' if all_requirements_met else 'FAIL'}")

    def _generate_summary(self) -> str:
        """Generate a summary of benchmark results."""
        summary_lines = [
            "=== Phase 2 Performance Benchmark Summary ===",
            "",
        ]

        # Single resource resolution
        single_res = self.results.get("single_resource_resolution", {})
        summary_lines.append(f"Single Resource Resolution: {single_res.get('average_time', 0):.3f}s avg")

        # Relationship resolution
        rel_res = self.results.get("relationship_resolution", {})
        summary_lines.append(f"Relationship Resolution: {rel_res.get('resolution_time', 0):.3f}s ({rel_res.get('resources_resolved', 0)} resources)")

        # Parallel resolution
        par_res = self.results.get("parallel_resolution", {})
        summary_lines.append(f"Parallel Resolution: {par_res.get('throughput', 0):.1f} resources/sec")

        # Memory usage
        mem_usage = self.results.get("memory_usage", {})
        summary_lines.append(f"Memory Usage: {mem_usage.get('memory_usage_mb', 0):.2f}MB")

        # Concurrent requests
        conc_req = self.results.get("concurrent_requests", {})
        summary_lines.append(f"Concurrent Requests: {conc_req.get('successful_requests', 0)}/10 successful")

        summary_lines.extend([
            "",
            "Phase 2 Requirements:",
            f"✓ Resolution < 2s: {'PASS' if rel_res.get('meets_requirement') else 'FAIL'}",
            f"✓ Memory < 100MB: {'PASS' if mem_usage.get('meets_requirement') else 'FAIL'}",
            f"✓ Concurrent ≥ 10: {'PASS' if conc_req.get('meets_requirement') else 'FAIL'}",
        ])

        return "\n".join(summary_lines)

    def print_detailed_results(self):
        """Print detailed benchmark results."""
        print(self._generate_summary())
        print("\nDetailed Results:")
        for benchmark, data in self.results.items():
            if benchmark != "phase2_compliance":
                print(f"\n{benchmark.replace('_', ' ').title()}:")
                for key, value in data.items():
                    if isinstance(value, float):
                        print(f"  {key}: {value:.4f}")
                    else:
                        print(f"  {key}: {value}")


async def main():
    """Run the Phase 2 performance benchmarks."""
    benchmark = PerformanceBenchmark()

    try:
        results = await benchmark.run_all_benchmarks()
        benchmark.print_detailed_results()

        # Save results to file
        import json
        with open("phase2_benchmark_results.json", "w") as f:
            # Convert float values to avoid JSON serialization issues
            json_safe_results = {}
            for key, value in results.items():
                if isinstance(value, dict):
                    json_safe_results[key] = {
                        k: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
                        for k, v in value.items()
                    }
                else:
                    json_safe_results[key] = value

            json.dump(json_safe_results, f, indent=2)

        logger.info("Benchmark results saved to phase2_benchmark_results.json")

        # Return exit code based on compliance
        compliance = results.get("phase2_compliance", {})
        return 0 if compliance.get("all_requirements_met", False) else 1

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
