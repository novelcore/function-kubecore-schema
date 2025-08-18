#!/usr/bin/env python3
"""Local test using kubectl context to connect to the remote cluster."""

import asyncio
import logging
import sys
import os
from kubernetes import client, config

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Add current directory to path for imports
sys.path.insert(0, '.')

from function.fn import KubeCoreContextFunction
from function.k8s_client import K8sClient

async def test_local_function_with_k8s():
    """Test the function locally but connecting to the remote Kubernetes cluster."""
    
    print("🚀 Local Function Test with Remote Kubernetes")
    print("=" * 60)
    
    try:
        # Load kubectl configuration 
        print("🔧 Loading kubectl configuration...")
        config.load_kube_config()
        k8s_api_client = client.ApiClient()
        print("✅ Kubectl configuration loaded successfully")
        
        # Create our K8s client wrapper
        print("🔧 Initializing K8sClient wrapper...")
        k8s_client = K8sClient(k8s_api_client)
        print("✅ K8sClient initialized")
        
        # Initialize the function with real K8s client
        print("🔧 Initializing KubeCoreContextFunction...")
        function = KubeCoreContextFunction()
        
        # Check if function components are initialized
        print(f"📋 Function components check:")
        print(f"  - Query processor: {'✅' if hasattr(function, 'query_processor') and function.query_processor else '❌'}")
        print(f"  - Schema registry: {'✅' if hasattr(function, 'schema_registry') and function.schema_registry else '❌'}")
        print(f"  - Transitive engine: {'✅' if hasattr(function, 'transitive_discovery_engine') and function.transitive_discovery_engine else '❌'}")
        print(f"  - Resource resolver: {'✅' if hasattr(function, 'resource_resolver') and function.resource_resolver else '❌'}")
        
        print("✅ KubeCoreContextFunction initialized")
        
    except Exception as e:
        print(f"❌ Function initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test the exact same request that should work in the cluster
    test_request = {
        "input": {
            "apiVersion": "context.fn.kubecore.io/v1beta1",
            "kind": "ContextInput",
            "spec": {
                "query": {
                    "resourceType": "XGitHubProject",
                    "requestedSchemas": [
                        "kubeCluster",
                        "kubEnv", 
                        "app",
                        "kubeSystem"
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
    print(f"- Requestor: {test_request['input']['spec']['context']['requestorName']}/{test_request['input']['spec']['context']['requestorNamespace']}")
    
    # Test direct function call
    print("\n🔍 Testing direct function call...")
    try:
        result = await function.run_function_async(test_request)
        
        print("\n📊 Direct Function Results:")
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
                
                if len(schemas) > 0:
                    print("\n✅ SUCCESS: Function executed with schemas discovered!")
                    return True
                else:
                    print("\n⚠️  Function executed but no schemas discovered")
                    
                    # Additional debugging - check what's in platform context
                    print(f"\n🔍 Platform Context Debug:")
                    print(f"- Requestor: {platform_context.get('requestor', 'missing')}")
                    print(f"- Available schemas keys: {list(platform_context.get('availableSchemas', {}).keys())}")
                    print(f"- Relationships: {platform_context.get('relationships', 'missing')}")
                    print(f"- Insights: {platform_context.get('insights', 'missing')}")
                    
                    return False
            else:
                print("❌ No availableSchemas in platformContext")
                print(f"Platform context keys: {list(platform_context.keys())}")
                return False
        else:
            print("❌ No platformContext in response")
            print(f"Result spec keys: {list(result.get('spec', {}).keys())}")
            return False
            
    except Exception as e:
        print(f"❌ Direct function call failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    print("Starting local function test with remote Kubernetes cluster...")
    
    success = await test_local_function_with_k8s()
    
    if success:
        print("\n🎉 Local Function Test PASSED!")
        print("The function successfully executed with transitive discovery.")
        sys.exit(0)
    else:
        print("\n❌ Local Function Test FAILED!")
        print("The function did not execute as expected.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())