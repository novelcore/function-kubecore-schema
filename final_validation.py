#!/usr/bin/env python3
"""Final Phase 4 Validation - Simple component testing without external dependencies."""

import json
import os
import sys
import time


def test_phase4_components():
    """Test Phase 4 components without external dependencies."""
    print("🚀 Phase 4 Final Validation")
    print("=" * 50)

    # Add function directory to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "function"))

    results = {}

    # Test 1: Cache functionality
    print("\n1. Testing Cache Component...")
    try:
        from cache import ContextCache

        cache = ContextCache(ttl_seconds=1, max_entries=10)

        # Basic operations
        cache.set("test_key", {"data": "test_value", "number": 42})
        result = cache.get("test_key")
        assert result is not None
        assert result["data"] == "test_value"
        assert result["number"] == 42

        # Key generation
        key1 = cache.generate_key("XApp", {"references": {}}, ["kubEnv"])
        key2 = cache.generate_key("XApp", {"references": {}}, ["kubEnv"])
        assert key1 == key2

        # TTL expiration
        cache_short = ContextCache(ttl_seconds=0.01)
        cache_short.set("expire_test", {"will": "expire"})
        time.sleep(0.02)
        expired = cache_short.get("expire_test")
        assert expired is None

        # Statistics
        stats = cache.get_stats()
        assert "entries" in stats
        assert "hit_rate" in stats

        print("   ✓ Basic cache operations")
        print("   ✓ Key generation (deterministic)")
        print("   ✓ TTL expiration")
        print("   ✓ Statistics collection")

        results["cache"] = {"status": "PASS", "entries": stats["entries"]}

    except Exception as e:
        print(f"   ❌ Cache test failed: {e}")
        results["cache"] = {"status": "FAIL", "error": str(e)}

    # Test 2: Performance Optimizer
    print("\n2. Testing Performance Optimizer...")
    try:
        from performance import PerformanceOptimizer

        optimizer = PerformanceOptimizer(max_workers=2, timeout_seconds=5.0)

        # Metrics collection
        metrics = optimizer.get_metrics()
        required_metrics = ["total_queries", "avg_response_time", "cache_hit_rate"]
        for metric in required_metrics:
            assert metric in metrics

        # Cache metrics update
        optimizer.update_cache_metrics(True)  # Hit
        optimizer.update_cache_metrics(False) # Miss
        updated_metrics = optimizer.get_metrics()
        assert updated_metrics["cache_hit_rate"] == 0.5  # 1 hit out of 2 total

        # Cleanup
        optimizer.cleanup()

        print("   ✓ Metrics collection")
        print("   ✓ Cache metrics tracking")
        print("   ✓ Resource cleanup")

        results["performance"] = {"status": "PASS", "hit_rate": updated_metrics["cache_hit_rate"]}

    except Exception as e:
        print(f"   ❌ Performance optimizer test failed: {e}")
        results["performance"] = {"status": "FAIL", "error": str(e)}

    # Test 3: Integration
    print("\n3. Testing Component Integration...")
    try:
        cache = ContextCache(ttl_seconds=60)
        optimizer = PerformanceOptimizer(max_workers=2)

        # Test that components can work together
        test_data = {
            "query": {"resourceType": "XApp"},
            "context": {"requestorName": "test"},
            "response": {"schemas": {"kubEnv": {"name": "test-env"}}}
        }

        # Generate cache key
        cache_key = cache.generate_key(
            test_data["query"]["resourceType"],
            test_data["context"],
            ["kubEnv"]
        )

        # Cache response
        cache.set(cache_key, test_data["response"])

        # Retrieve and validate
        cached_response = cache.get(cache_key)
        assert cached_response is not None
        assert cached_response["schemas"]["kubEnv"]["name"] == "test-env"

        # Update performance metrics
        optimizer.update_cache_metrics(True)  # Cache hit

        print("   ✓ Cache + Performance integration")
        print("   ✓ End-to-end data flow")

        results["integration"] = {"status": "PASS"}

    except Exception as e:
        print(f"   ❌ Integration test failed: {e}")
        results["integration"] = {"status": "FAIL", "error": str(e)}

    # Test 4: File Structure
    print("\n4. Validating File Structure...")
    expected_files = [
        "function/cache.py",
        "function/performance.py",
        "function/fn.py",
        "manifests/function.yaml",
        "package/crossplane.yaml",
        "docs/README.md",
        "PHASE4_FINAL_EVALUATION_REPORT.md"
    ]

    missing_files = []
    present_files = []

    for file_path in expected_files:
        if os.path.exists(file_path):
            present_files.append(file_path)
            print(f"   ✓ {file_path}")
        else:
            missing_files.append(file_path)
            print(f"   ❌ {file_path} missing")

    results["files"] = {
        "status": "PASS" if not missing_files else "PARTIAL",
        "present": len(present_files),
        "missing": len(missing_files)
    }

    # Test 5: Performance Benchmarks
    print("\n5. Running Performance Benchmarks...")
    try:
        cache = ContextCache()

        # Benchmark cache operations
        start_time = time.time()
        for i in range(100):
            cache.set(f"bench_{i}", {"data": f"value_{i}", "index": i})
        set_time = time.time() - start_time

        start_time = time.time()
        for i in range(100):
            result = cache.get(f"bench_{i}")
            assert result is not None
            assert result["index"] == i
        get_time = time.time() - start_time

        print(f"   ✓ Cache SET: {set_time*1000:.1f}ms for 100 operations")
        print(f"   ✓ Cache GET: {get_time*1000:.1f}ms for 100 operations")

        # Performance targets
        set_target = 50  # 50ms for 100 operations
        get_target = 10  # 10ms for 100 operations

        set_pass = (set_time * 1000) < set_target
        get_pass = (get_time * 1000) < get_target

        print(f"   {'✓' if set_pass else '⚠'} SET performance: {'PASS' if set_pass else 'SLOW'}")
        print(f"   {'✓' if get_pass else '⚠'} GET performance: {'PASS' if get_pass else 'SLOW'}")

        results["benchmarks"] = {
            "status": "PASS" if (set_pass and get_pass) else "SLOW",
            "set_ms": set_time * 1000,
            "get_ms": get_time * 1000
        }

    except Exception as e:
        print(f"   ❌ Benchmark failed: {e}")
        results["benchmarks"] = {"status": "FAIL", "error": str(e)}

    # Summary
    print("\n" + "=" * 50)
    print("📊 FINAL VALIDATION SUMMARY")
    print("=" * 50)

    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r.get("status") == "PASS")

    for test_name, result in results.items():
        status_icon = "✅" if result.get("status") == "PASS" else "⚠️" if result.get("status") == "PARTIAL" else "❌"
        print(f"{status_icon} {test_name.upper()}: {result.get('status', 'UNKNOWN')}")

    success_rate = (passed_tests / total_tests) * 100
    print(f"\nSUCCESS RATE: {success_rate:.0f}% ({passed_tests}/{total_tests} tests passed)")

    # Final determination
    if success_rate >= 80 and results.get("cache", {}).get("status") == "PASS":
        final_status = "🎉 PRODUCTION READY"
        print(f"\n{final_status}")
        print("Phase 4 implementation is complete and ready for production!")
        exit_code = 0
    else:
        final_status = "⚠️ NEEDS ATTENTION"
        print(f"\n{final_status}")
        print("Some components need attention before production deployment.")
        exit_code = 1

    # Save results
    final_results = {
        "phase": "Phase 4 - Final Validation",
        "timestamp": time.time(),
        "success_rate": success_rate,
        "status": final_status,
        "results": results
    }

    with open("phase4_final_validation.json", "w") as f:
        json.dump(final_results, f, indent=2)

    print("\nResults saved to: phase4_final_validation.json")
    return exit_code

if __name__ == "__main__":
    exit_code = test_phase4_components()
    sys.exit(exit_code)
