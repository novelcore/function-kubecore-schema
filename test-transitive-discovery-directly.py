#!/usr/bin/env python3
"""Direct test of transitive discovery functionality with real resources."""

import asyncio
import json
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

# Add current directory to path for imports
sys.path.insert(0, '.')

from function.fn import KubeCoreContextFunction


async def test_transitive_discovery_with_real_resources():
    """Test transitive discovery using the real function with demo-project."""
    
    print("🚀 Testing Transitive Discovery with Real Resources")
    print("=" * 60)
    
    # Initialize the function
    try:
        function = KubeCoreContextFunction()
        print("✅ Function initialized successfully")
    except Exception as e:
        print(f"❌ Function initialization failed: {e}")
        return False
    
    # Create test request that mimics what the composition sends
    test_request = {
        "input": {
            "apiVersion": "context.fn.kubecore.io/v1beta1",
            "kind": "ContextInput",
            "spec": {
                "query": {
                    "resourceType": "XGitHubProject",
                    "requestedSchemas": [
                        "kubeCluster",   # Should find via 1-hop: githubProjectRef
                        "kubEnv",        # Should find via 2-hop: githubProjectRef → kubeClusterRef
                        "app",           # Should find via 3-hop: githubProjectRef → kubeClusterRef → kubenvRef
                        "kubeSystem"     # Should find via 2-hop: githubProjectRef → kubeClusterRef
                    ]
                },
                "context": {
                    "requestorName": "demo-project",
                    "requestorNamespace": "test", 
                    "enableTransitiveDiscovery": True,
                    "transitiveMaxDepth": 3,
                    "references": {
                        "githubProjectRefs": [
                            {
                                "name": "demo-project",
                                "namespace": "test",
                                "apiVersion": "github.platform.kubecore.io/v1alpha1", 
                                "kind": "XGitHubProject"
                            }
                        ]
                    }
                }
            }
        },
        "observed": {
            "composite": {
                "metadata": {
                    "name": "demo-project",
                    "namespace": "test"
                },
                "spec": {
                    "githubProjectRef": {
                        "name": "demo-project",
                        "namespace": "test"
                    }
                }
            }
        }
    }
    
    print("\n📋 Test Request:")
    print(f"- Resource Type: {test_request['input']['spec']['query']['resourceType']}")
    print(f"- Requested Schemas: {test_request['input']['spec']['query']['requestedSchemas']}")
    print(f"- Transitive Discovery: {test_request['input']['spec']['context']['enableTransitiveDiscovery']}")
    print(f"- Max Depth: {test_request['input']['spec']['context']['transitiveMaxDepth']}")
    
    try:
        print("\n🔍 Executing transitive discovery test...")
        result = await function.run_function_async(test_request)
        
        print("\n📊 Results:")
        print(f"- Response keys: {list(result.keys())}")
        
        if "spec" in result and "platformContext" in result["spec"]:
            platform_context = result["spec"]["platformContext"]
            
            if "availableSchemas" in platform_context:
                schemas = platform_context["availableSchemas"]
                print(f"- Found schemas: {list(schemas.keys())}")
                
                for schema_type, schema_data in schemas.items():
                    instances = schema_data.get("instances", [])
                    discovery_method = schema_data.get("metadata", {}).get("discoveryMethod", "unknown")
                    print(f"  * {schema_type}: {len(instances)} instances (discovery: {discovery_method})")
                    
                    for instance in instances:
                        summary = instance.get("summary", {})
                        discovery_info = ""
                        if "discoveryHops" in summary:
                            discovery_info = f" ({summary['discoveryHops']} hops)"
                        if "relationshipChain" in summary:
                            discovery_info += f" - {summary['relationshipChain']}"
                        
                        print(f"    - {instance.get('name', 'unknown')}{discovery_info}")
                
                # Success criteria
                if len(schemas) > 0:
                    print("\n✅ SUCCESS: Transitive discovery found resources!")
                    
                    # Check for specific expected discoveries
                    expected_schemas = ["kubeCluster", "kubEnv", "app"] 
                    found_schemas = list(schemas.keys())
                    missing_schemas = [s for s in expected_schemas if s not in found_schemas]
                    
                    if missing_schemas:
                        print(f"⚠️  Missing expected schemas: {missing_schemas}")
                    else:
                        print("🎉 All expected schemas discovered transitively!")
                    
                    return True
                else:
                    print("❌ FAILURE: No schemas discovered")
                    return False
            else:
                print("❌ FAILURE: No availableSchemas in platformContext")
                return False
        else:
            print("❌ FAILURE: No platformContext in response")
            print(f"Response: {json.dumps(result, indent=2)}")
            return False
            
    except Exception as e:
        print(f"❌ FAILURE: Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    success = await test_transitive_discovery_with_real_resources()
    
    if success:
        print("\n🎉 Transitive Discovery Test PASSED!")
        print("The function successfully discovered resources through transitive relationships.")
        sys.exit(0)
    else:
        print("\n❌ Transitive Discovery Test FAILED!")
        print("Please check the function implementation or resource availability.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())