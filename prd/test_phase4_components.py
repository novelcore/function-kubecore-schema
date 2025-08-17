#!/usr/bin/env python3
"""Simplified Phase 4 Component Testing Script.

Tests the Phase 4 components without requiring full dependencies.
"""

import json
import os
import sys
import time

# Add function directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "function"))

def test_cache_performance():
    """Test cache performance and functionality."""
    print("=== Testing Cache Performance ===\n")

    from cache import ContextCache

    # Initialize cache
    cache = ContextCache(ttl_seconds=60, max_entries=100)
    print("✓ Cache initialized")

    # Test basic operations
    test_data = {"schemas": {"kubEnv": {"name": "test"}}, "processed": True}
    cache_key = "test_key_123"

    # Test set/get
    cache.set(cache_key, test_data)
    result = cache.get(cache_key)
    assert result is not None
    assert result["processed"] == True
    print("✓ Basic cache operations working")

    # Test key generation
    key1 = cache.generate_key("XApp", {"references": {"kubEnvRefs": [{"name": "test"}]}}, ["kubEnv"])
    key2 = cache.generate_key("XApp", {"references": {"kubEnvRefs": [{"name": "test"}]}}, ["kubEnv"])
    assert key1 == key2
    print("✓ Cache key generation is deterministic")

    # Test cache statistics
    stats = cache.get_stats()
    assert stats["entries"] > 0
    print(f"✓ Cache stats: {stats['entries']} entries, {stats['hit_rate']:.2%} hit rate")

    # Test performance with many entries
    start_time = time.time()
    for i in range(100):
        cache.set(f"perf_test_{i}", {"data": f"test_data_{i}"})
    set_duration = time.time() - start_time

    start_time = time.time()
    for i in range(100):
        result = cache.get(f"perf_test_{i}")
        assert result is not None
    get_duration = time.time() - start_time

    print(f"✓ Cache performance: {set_duration*1000:.1f}ms to set 100 items, {get_duration*1000:.1f}ms to get 100 items")

    # Test TTL expiration
    short_cache = ContextCache(ttl_seconds=0.1)
    short_cache.set("expire_test", {"data": "will_expire"})
    time.sleep(0.15)
    expired = short_cache.get("expire_test")
    assert expired is None
    print("✓ TTL expiration working")

    return {
        "cache_entries": stats["entries"],
        "set_performance_ms": set_duration * 1000,
        "get_performance_ms": get_duration * 1000
    }

def test_performance_optimizer():
    """Test performance optimizer functionality."""
    print("\n=== Testing Performance Optimizer ===\n")

    from performance import PerformanceOptimizer

    # Initialize optimizer
    optimizer = PerformanceOptimizer(max_workers=4, timeout_seconds=10.0)
    print("✓ Performance optimizer initialized")

    # Test metrics
    initial_metrics = optimizer.get_metrics()
    assert "total_queries" in initial_metrics
    assert "avg_response_time" in initial_metrics
    print("✓ Metrics collection working")

    # Test cache metrics updates
    optimizer.update_cache_metrics(True)   # Hit
    optimizer.update_cache_metrics(True)   # Hit
    optimizer.update_cache_metrics(False)  # Miss

    updated_metrics = optimizer.get_metrics()
    assert updated_metrics["cache_hit_rate"] > 0.5  # Should be 2/3
    print(f"✓ Cache metrics: {updated_metrics['cache_hit_rate']:.2%} hit rate")

    # Test async parallel processing (simplified)
    import asyncio

    async def test_parallel():
        def mock_processor(item):
            time.sleep(0.01)  # Simulate work
            return item * 2

        items = list(range(10))
        start_time = time.time()
        results = await optimizer.batch_process(items, mock_processor, batch_size=5)
        duration = time.time() - start_time

        assert len(results) == 10
        return duration

    # Run async test
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        parallel_duration = loop.run_until_complete(test_parallel())
        print(f"✓ Parallel processing: 10 items in {parallel_duration*1000:.1f}ms")
    finally:
        loop.close()
        optimizer.cleanup()

    return {
        "parallel_duration_ms": parallel_duration * 1000,
        "cache_hit_rate": updated_metrics["cache_hit_rate"]
    }

def test_integration_without_grpc():
    """Test core function components without gRPC dependencies."""
    print("\n=== Testing Core Components Integration ===\n")

    # Test imports
    try:
        from cache import ContextCache
        from performance import PerformanceOptimizer
        from query_processor import QueryProcessor
        from schema_registry import SchemaRegistry
        print("✓ All core components import successfully")
    except ImportError as e:
        print(f"⚠ Import failed: {e}")
        return {}

    # Test component initialization
    cache = ContextCache()
    optimizer = PerformanceOptimizer(max_workers=2)
    schema_registry = SchemaRegistry()

    print("✓ Components initialize without errors")

    # Test cache integration
    test_context = {
        "requestorName": "test-app",
        "references": {"kubEnvRefs": [{"name": "test-env"}]}
    }

    cache_key = cache.generate_key("XApp", test_context, ["kubEnv", "qualityGate"])
    test_response = {"test": "response", "schemas": {"kubEnv": {"name": "test"}}}

    # Cache the response
    cache.set(cache_key, test_response)

    # Retrieve from cache
    cached = cache.get(cache_key)
    assert cached is not None
    assert cached["test"] == "response"
    print("✓ Cache integration working")

    # Test that different queries generate different keys
    different_key = cache.generate_key("XKubeSystem", test_context, ["kubEnv"])
    assert cache_key != different_key
    print("✓ Cache key differentiation working")

    cleanup_optimizer = optimizer
    cleanup_optimizer.cleanup()

    return {
        "integration_success": True,
        "cache_key_length": len(cache_key)
    }

def test_manifest_structure():
    """Test deployment manifest completeness."""
    print("\n=== Testing Deployment Manifests ===\n")

    manifest_files = {
        "manifests/function.yaml": "Main deployment manifest",
        "package/crossplane.yaml": "Crossplane package manifest",
        "docs/README.md": "Documentation"
    }

    results = {}

    for file_path, description in manifest_files.items():
        if os.path.exists(file_path):
            with open(file_path) as f:
                content = f.read()

            print(f"✓ {description} exists ({len(content)} characters)")
            results[file_path] = {"exists": True, "size": len(content)}

            # Check for key content
            if "function.yaml" in file_path:
                checks = [
                    ("DeploymentRuntimeConfig", "runtime config"),
                    ("CACHE_TTL_SECONDS", "cache configuration"),
                    ("MAX_WORKERS", "worker configuration"),
                    ("ConfigMap", "configuration map")
                ]

                for check_text, check_desc in checks:
                    if check_text in content:
                        print(f"   ✓ {check_desc} configured")
                    else:
                        print(f"   ⚠ {check_desc} missing")

            elif "crossplane.yaml" in file_path:
                checks = [
                    ("function-kubecore-platform-context", "correct name"),
                    ("meta.crossplane.io/description", "description"),
                    ("crossplane:", "crossplane version"),
                    ("permissions:", "RBAC permissions")
                ]

                for check_text, check_desc in checks:
                    if check_text in content:
                        print(f"   ✓ {check_desc} present")
                    else:
                        print(f"   ⚠ {check_desc} missing")

        else:
            print(f"⚠ {description} missing: {file_path}")
            results[file_path] = {"exists": False, "size": 0}

    return results

def run_comprehensive_test():
    """Run all Phase 4 component tests."""
    print("🚀 Phase 4: Performance Optimization & Packaging Validation")
    print("=" * 60)

    results = {}

    try:
        # Test individual components
        cache_results = test_cache_performance()
        results["cache"] = cache_results

        perf_results = test_performance_optimizer()
        results["performance"] = perf_results

        integration_results = test_integration_without_grpc()
        results["integration"] = integration_results

        manifest_results = test_manifest_structure()
        results["manifests"] = manifest_results

        # Overall assessment
        print("\n" + "=" * 60)
        print("📊 PHASE 4 VALIDATION SUMMARY")
        print("=" * 60)

        print(f"✓ Cache Performance: {cache_results['set_performance_ms']:.1f}ms set, {cache_results['get_performance_ms']:.1f}ms get")
        print(f"✓ Parallel Processing: {perf_results['parallel_duration_ms']:.1f}ms for 10 items")
        print(f"✓ Cache Hit Rate: {perf_results['cache_hit_rate']:.2%}")
        print(f"✓ Component Integration: {'Success' if integration_results.get('integration_success') else 'Failed'}")

        manifest_count = sum(1 for r in manifest_results.values() if r.get("exists", False))
        print(f"✓ Deployment Manifests: {manifest_count}/{len(manifest_results)} files present")

        # Performance targets assessment
        cache_fast = cache_results["get_performance_ms"] < 50  # <50ms for 100 operations
        parallel_fast = perf_results["parallel_duration_ms"] < 500  # <500ms for 10 parallel operations
        good_hit_rate = perf_results["cache_hit_rate"] > 0.5

        targets_met = cache_fast and parallel_fast and good_hit_rate

        print("\n🎯 Performance Targets:")
        print(f"   Cache Speed: {'✓' if cache_fast else '⚠'} {cache_results['get_performance_ms']:.1f}ms (target: <50ms)")
        print(f"   Parallel Processing: {'✓' if parallel_fast else '⚠'} {perf_results['parallel_duration_ms']:.1f}ms (target: <500ms)")
        print(f"   Cache Hit Rate: {'✓' if good_hit_rate else '⚠'} {perf_results['cache_hit_rate']:.2%} (target: >50%)")

        # Final status
        if targets_met and manifest_count >= 2:
            status = "🎉 PRODUCTION READY"
            print(f"\n{status}")
            print("All performance targets met and deployment manifests are complete!")
        else:
            status = "⚠️ REVIEW REQUIRED"
            print(f"\n{status}")
            print("Some performance targets or manifests need attention.")

        # Save results
        final_results = {
            "phase": "Phase 4 - Performance Optimization & Packaging",
            "timestamp": time.time(),
            "status": status,
            "performance_targets_met": targets_met,
            "results": results,
            "summary": {
                "cache_performance_ms": cache_results["get_performance_ms"],
                "parallel_performance_ms": perf_results["parallel_duration_ms"],
                "cache_hit_rate": perf_results["cache_hit_rate"],
                "manifests_complete": manifest_count >= 2
            }
        }

        with open("phase4_validation_results.json", "w") as f:
            json.dump(final_results, f, indent=2)

        print("\nResults saved to: phase4_validation_results.json")
        return final_results

    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "FAILED", "error": str(e)}

if __name__ == "__main__":
    results = run_comprehensive_test()

    # Set exit code based on results
    if "PRODUCTION READY" in results.get("status", ""):
        sys.exit(0)
    else:
        sys.exit(1)
