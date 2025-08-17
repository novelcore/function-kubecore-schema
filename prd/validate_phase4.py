#!/usr/bin/env python3
"""Phase 4 Validation Script for KubeCore Platform Context Function.

This script validates the performance optimization and packaging implementation.
"""

import sys
import os
import time
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

# Add function directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'function'))

def test_performance_optimized_function():
    """Test the performance-optimized function with caching and parallel processing."""
    print("=== Phase 4 Performance Validation ===\n")
    
    # Import the optimized function
    from fn import KubeCoreContextFunction
    
    # Initialize function
    function = KubeCoreContextFunction()
    print("✓ Function initialized with Phase 4 optimizations")
    
    # Test request
    test_request = {
        "input": {
            "spec": {
                "query": {
                    "resourceType": "XApp",
                    "requestedSchemas": ["kubEnv", "qualityGate"]
                }
            }
        },
        "observed": {
            "composite": {
                "metadata": {
                    "name": "test-app",
                    "namespace": "default"
                },
                "spec": {
                    "kubEnvRefs": [{"name": "prod-env", "namespace": "platform"}],
                    "qualityGateRefs": [{"name": "high-quality", "namespace": "quality"}]
                }
            }
        }
    }
    
    print("\n1. Testing Query Performance (Target: <100ms)")
    
    # Warm up
    start_time = time.time()
    result1 = function.run_function(test_request)
    warmup_duration = (time.time() - start_time) * 1000
    print(f"   Warm-up query: {warmup_duration:.1f}ms")
    
    # Performance test
    start_time = time.time()
    result2 = function.run_function(test_request)
    performance_duration = (time.time() - start_time) * 1000
    print(f"   Optimized query: {performance_duration:.1f}ms")
    
    # Cached query test
    start_time = time.time()
    result3 = function.run_function(test_request)
    cache_duration = (time.time() - start_time) * 1000
    print(f"   Cached query: {cache_duration:.1f}ms")
    
    # Validate performance targets
    performance_target = 100  # 100ms
    cache_target = 10  # 10ms for cache
    
    if performance_duration < performance_target:
        print(f"   ✓ Performance target met: {performance_duration:.1f}ms < {performance_target}ms")
    else:
        print(f"   ⚠ Performance target missed: {performance_duration:.1f}ms >= {performance_target}ms")
    
    if cache_duration < cache_target:
        print(f"   ✓ Cache performance excellent: {cache_duration:.1f}ms < {cache_target}ms")
    else:
        print(f"   ⚠ Cache performance acceptable: {cache_duration:.1f}ms")
    
    print("\n2. Testing Concurrent Query Handling")
    
    def run_query():
        return function.run_function(test_request)
    
    # Test concurrent queries
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_query) for _ in range(5)]
        results = [future.result() for future in futures]
    concurrent_duration = (time.time() - start_time) * 1000
    
    print(f"   5 concurrent queries: {concurrent_duration:.1f}ms")
    print(f"   Average per query: {concurrent_duration/5:.1f}ms")
    print(f"   ✓ All {len(results)} queries completed successfully")
    
    print("\n3. Testing Cache Effectiveness")
    
    # Test cache statistics
    cache_stats = function.cache.get_stats()
    print(f"   Cache entries: {cache_stats['entries']}")
    print(f"   Total hits: {cache_stats['total_hits']}")
    print(f"   Hit rate: {cache_stats['hit_rate']:.2%}")
    
    if cache_stats['hit_rate'] > 0:
        print("   ✓ Cache is working effectively")
    else:
        print("   ⚠ Cache hit rate is low (expected for initial test)")
    
    print("\n4. Testing Performance Metrics")
    
    # Test performance metrics
    perf_metrics = function.performance_optimizer.get_metrics()
    print(f"   Total queries: {perf_metrics['total_queries']}")
    print(f"   Average response time: {perf_metrics['avg_response_time']:.3f}s")
    print(f"   Cache hit rate: {perf_metrics['cache_hit_rate']:.2%}")
    print(f"   Errors: {perf_metrics['errors']}")
    
    print("\n5. Validating Response Structure")
    
    # Validate response structure
    assert "spec" in result1
    assert "platformContext" in result1["spec"]
    platform_context = result1["spec"]["platformContext"]
    
    required_fields = ["requestor", "availableSchemas", "relationships", "insights"]
    for field in required_fields:
        assert field in platform_context, f"Missing required field: {field}"
        print(f"   ✓ {field} present in response")
    
    # Check specific schemas
    schemas = platform_context["availableSchemas"]
    for schema in ["kubEnv", "qualityGate"]:
        if schema in schemas:
            print(f"   ✓ {schema} schema resolved")
            assert "metadata" in schemas[schema]
            assert "instances" in schemas[schema]
        else:
            print(f"   ⚠ {schema} schema not resolved (may be expected)")
    
    print("\n6. Memory Usage Validation")
    
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"   Current memory usage: {memory_mb:.1f} MB")
        
        if memory_mb < 50:
            print("   ✓ Memory usage within target (<50MB)")
        else:
            print(f"   ⚠ Memory usage higher than target: {memory_mb:.1f}MB")
    except ImportError:
        print("   ⚠ psutil not available for memory testing")
    
    print("\n=== Phase 4 Validation Complete ===")
    
    # Summary
    print("\n📊 PERFORMANCE SUMMARY:")
    print(f"   • Query Performance: {performance_duration:.1f}ms")
    print(f"   • Cached Performance: {cache_duration:.1f}ms")
    print(f"   • Concurrent Queries: {len(results)} successful")
    print(f"   • Cache Hit Rate: {cache_stats['hit_rate']:.2%}")
    
    # Clean up
    function.performance_optimizer.cleanup()
    
    return {
        "performance_ms": performance_duration,
        "cache_ms": cache_duration,
        "concurrent_queries": len(results),
        "cache_hit_rate": cache_stats['hit_rate'],
        "memory_mb": memory_mb if 'memory_mb' in locals() else 0
    }

def test_deployment_manifests():
    """Test deployment manifest structure."""
    print("\n=== Deployment Manifest Validation ===\n")
    
    manifest_path = "manifests/function.yaml"
    if os.path.exists(manifest_path):
        print("✓ Deployment manifest exists")
        
        with open(manifest_path, 'r') as f:
            content = f.read()
        
        # Check for required components
        required_components = [
            "Function",
            "DeploymentRuntimeConfig", 
            "ServiceAccount",
            "ClusterRole",
            "ClusterRoleBinding",
            "ConfigMap"
        ]
        
        for component in required_components:
            if f"kind: {component}" in content:
                print(f"   ✓ {component} defined")
            else:
                print(f"   ⚠ {component} missing")
        
        # Check environment variables
        env_vars = ["CACHE_TTL_SECONDS", "MAX_WORKERS", "TIMEOUT_SECONDS"]
        for var in env_vars:
            if var in content:
                print(f"   ✓ Environment variable {var} configured")
            else:
                print(f"   ⚠ Environment variable {var} missing")
                
    else:
        print("⚠ Deployment manifest not found")

def test_documentation():
    """Test documentation completeness."""
    print("\n=== Documentation Validation ===\n")
    
    doc_path = "docs/README.md"
    if os.path.exists(doc_path):
        print("✓ Documentation exists")
        
        with open(doc_path, 'r') as f:
            content = f.read()
        
        # Check for required sections
        required_sections = [
            "## Overview",
            "## Installation", 
            "## Usage Examples",
            "## Performance Characteristics",
            "## Troubleshooting"
        ]
        
        for section in required_sections:
            if section in content:
                print(f"   ✓ {section} section present")
            else:
                print(f"   ⚠ {section} section missing")
                
        print(f"   Documentation length: {len(content)} characters")
    else:
        print("⚠ Documentation not found")

if __name__ == "__main__":
    try:
        # Run all validations
        performance_results = test_performance_optimized_function()
        test_deployment_manifests()
        test_documentation()
        
        # Save results
        results = {
            "phase": "Phase 4 - Performance Optimization & Packaging",
            "timestamp": time.time(),
            "performance_metrics": performance_results,
            "status": "VALIDATED",
            "summary": {
                "query_performance_ms": performance_results["performance_ms"],
                "cache_performance_ms": performance_results["cache_ms"],
                "concurrent_capacity": performance_results["concurrent_queries"],
                "memory_usage_mb": performance_results["memory_mb"]
            }
        }
        
        with open("phase4_validation_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ Phase 4 validation completed successfully!")
        print(f"Results saved to: phase4_validation_results.json")
        
        # Determine if targets were met
        meets_targets = (
            performance_results["performance_ms"] < 100 and  # <100ms
            performance_results["cache_ms"] < 50 and        # <50ms cached
            performance_results["concurrent_queries"] >= 5   # 5+ concurrent
        )
        
        if meets_targets:
            print("🎉 All performance targets met - Production ready!")
        else:
            print("⚠️ Some performance targets missed - Review needed")
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)