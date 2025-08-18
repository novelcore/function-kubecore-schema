#!/usr/bin/env python3
"""Debug script for transitive discovery issues."""

import asyncio
import logging
import sys

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

# Add current directory to path for imports
sys.path.insert(0, '.')

from function.resource_resolver import ResourceResolver
from function.transitive_discovery import TransitiveDiscoveryEngine, TransitiveDiscoveryConfig, TRANSITIVE_RELATIONSHIP_CHAINS

async def debug_transitive_discovery():
    """Debug the transitive discovery step by step."""
    
    print("🔍 Debug Transitive Discovery")
    print("=" * 50)
    
    # Check relationship chains
    print("📋 Checking relationship chains...")
    chains = TRANSITIVE_RELATIONSHIP_CHAINS.get("XGitHubProject", [])
    print(f"Found {len(chains)} relationship chains for XGitHubProject:")
    for i, (target_kind, ref_chain) in enumerate(chains):
        print(f"  {i+1}. {target_kind} via {ref_chain} ({len(ref_chain)} hops)")
    
    # Initialize components
    print("\n🏗️ Initializing components...")
    resource_resolver = ResourceResolver()
    config = TransitiveDiscoveryConfig(max_depth=3)
    engine = TransitiveDiscoveryEngine(resource_resolver, config)
    
    # Test target reference
    target_ref = {
        "name": "demo-project",
        "namespace": "test",
        "kind": "XGitHubProject",
        "apiVersion": "github.platform.kubecore.io/v1alpha1"
    }
    
    context = {
        "requestorName": "demo-project", 
        "requestorNamespace": "test",
        "enableTransitiveDiscovery": True,
        "transitiveMaxDepth": 3
    }
    
    print(f"\n🎯 Target: {target_ref['kind']}({target_ref['name']}) in namespace {target_ref['namespace']}")
    
    # Test each relationship chain individually
    print("\n🔗 Testing individual relationship chains:")
    for i, (target_kind, ref_chain) in enumerate(chains):
        print(f"\n--- Chain {i+1}: {target_kind} via {ref_chain} ---")
        
        try:
            # Test the chain traversal
            result = await engine._traverse_relationship_chain(
                target_ref, "XGitHubProject", target_kind, ref_chain, context
            )
            print(f"✅ Result: {len(result)} resources found")
            for r in result:
                print(f"   - {r.kind}({r.name}) in {r.namespace}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Test full discovery
    print(f"\n🚀 Testing full transitive discovery...")
    try:
        results = await engine.discover_transitive_relationships(
            target_ref, "XGitHubProject", context
        )
        print(f"✅ Full discovery result: {len(results)} schema types")
        for schema_type, resources in results.items():
            print(f"   {schema_type}: {len(resources)} resources")
            for r in resources:
                print(f"     - {r.kind}({r.name}) in {r.namespace}")
    except Exception as e:
        print(f"❌ Full discovery error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_transitive_discovery())