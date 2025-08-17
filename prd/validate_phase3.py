#!/usr/bin/env python3
"""Validation script for Phase 3 implementation.

This script validates that the Phase 3 implementation generates responses
that match the exact specification format.
"""

import asyncio
import json
import logging
import sys
from typing import Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import function components
from function.fn import KubeCoreContextFunction
from function.query_processor import QueryProcessor
from function.response_generator import ResponseGenerator
from function.insights_engine import InsightsEngine
from function.schema_registry import SchemaRegistry
from function.resource_resolver import ResourceResolver
from function.resource_summarizer import ResourceSummarizer
from function.k8s_client import K8sClient


def validate_response_structure(response: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate response structure against specification.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Check top-level structure
    if not isinstance(response, dict):
        errors.append("Response must be a dictionary")
        return False, errors
    
    # Check required top-level fields
    required_fields = ["apiVersion", "kind", "spec"]
    for field in required_fields:
        if field not in response:
            errors.append(f"Missing required field: {field}")
    
    # Check API version
    if response.get("apiVersion") != "context.fn.kubecore.io/v1beta1":
        errors.append(f"Incorrect apiVersion: {response.get('apiVersion')}")
    
    # Check kind
    if response.get("kind") != "Output":
        errors.append(f"Incorrect kind: {response.get('kind')}")
    
    # Check spec structure
    spec = response.get("spec", {})
    if not isinstance(spec, dict):
        errors.append("spec must be a dictionary")
        return False, errors
    
    if "platformContext" not in spec:
        errors.append("spec must contain platformContext")
        return False, errors
    
    # Check platform context structure
    pc = spec["platformContext"]
    if not isinstance(pc, dict):
        errors.append("platformContext must be a dictionary")
        return False, errors
    
    # Check required platform context fields
    pc_required = ["requestor", "availableSchemas", "relationships", "insights"]
    for field in pc_required:
        if field not in pc:
            errors.append(f"platformContext missing required field: {field}")
    
    # Check requestor structure
    requestor = pc.get("requestor", {})
    if not isinstance(requestor, dict):
        errors.append("requestor must be a dictionary")
    else:
        requestor_required = ["type", "name", "namespace"]
        for field in requestor_required:
            if field not in requestor:
                errors.append(f"requestor missing required field: {field}")
    
    # Check availableSchemas structure
    schemas = pc.get("availableSchemas", {})
    if not isinstance(schemas, dict):
        errors.append("availableSchemas must be a dictionary")
    else:
        for schema_name, schema_data in schemas.items():
            schema_errors = validate_schema_structure(schema_name, schema_data)
            errors.extend(schema_errors)
    
    # Check relationships structure
    relationships = pc.get("relationships", {})
    if not isinstance(relationships, dict):
        errors.append("relationships must be a dictionary")
    
    # Check insights structure
    insights = pc.get("insights", {})
    if not isinstance(insights, dict):
        errors.append("insights must be a dictionary")
    
    return len(errors) == 0, errors


def validate_schema_structure(schema_name: str, schema_data: dict[str, Any]) -> list[str]:
    """Validate individual schema structure."""
    errors = []
    
    if not isinstance(schema_data, dict):
        errors.append(f"Schema {schema_name} must be a dictionary")
        return errors
    
    # Check required fields
    required_fields = ["metadata", "instances"]
    for field in required_fields:
        if field not in schema_data:
            errors.append(f"Schema {schema_name} missing required field: {field}")
    
    # Check metadata
    metadata = schema_data.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append(f"Schema {schema_name} metadata must be a dictionary")
    else:
        metadata_required = ["apiVersion", "kind", "accessible", "relationshipPath"]
        for field in metadata_required:
            if field not in metadata:
                errors.append(f"Schema {schema_name} metadata missing field: {field}")
    
    # Check instances
    instances = schema_data.get("instances", [])
    if not isinstance(instances, list):
        errors.append(f"Schema {schema_name} instances must be a list")
    else:
        for i, instance in enumerate(instances):
            instance_errors = validate_instance_structure(schema_name, i, instance)
            errors.extend(instance_errors)
    
    return errors


def validate_instance_structure(schema_name: str, index: int, instance: dict[str, Any]) -> list[str]:
    """Validate individual instance structure."""
    errors = []
    
    if not isinstance(instance, dict):
        errors.append(f"Schema {schema_name} instance {index} must be a dictionary")
        return errors
    
    # Check required fields
    required_fields = ["name", "namespace", "summary"]
    for field in required_fields:
        if field not in instance:
            errors.append(f"Schema {schema_name} instance {index} missing field: {field}")
    
    # Check summary
    summary = instance.get("summary", {})
    if not isinstance(summary, dict):
        errors.append(f"Schema {schema_name} instance {index} summary must be a dictionary")
    
    return errors


async def test_app_query() -> tuple[bool, dict[str, Any], list[str]]:
    """Test XApp query processing."""
    logger.info("Testing XApp query processing...")
    
    # Create function instance
    function = KubeCoreContextFunction()
    
    # Test input
    request = {
        "input": {
            "spec": {
                "query": {
                    "resourceType": "XApp",
                    "requestedSchemas": ["kubEnv"]
                }
            }
        },
        "observed": {
            "composite": {
                "metadata": {
                    "name": "art-api",
                    "namespace": "default"
                },
                "spec": {
                    "kubEnvRef": {
                        "name": "demo-dev",
                        "namespace": "test"
                    }
                }
            }
        }
    }
    
    try:
        result = function.run_function(request)
        is_valid, errors = validate_response_structure(result)
        return is_valid, result, errors
    except Exception as e:
        return False, {}, [f"Exception during processing: {str(e)}"]


async def test_kubesystem_query() -> tuple[bool, dict[str, Any], list[str]]:
    """Test XKubeSystem query processing."""
    logger.info("Testing XKubeSystem query processing...")
    
    function = KubeCoreContextFunction()
    
    request = {
        "input": {
            "spec": {
                "query": {
                    "resourceType": "XKubeSystem",
                    "requestedSchemas": ["kubeCluster"]
                }
            }
        },
        "observed": {
            "composite": {
                "metadata": {
                    "name": "demo-system",
                    "namespace": "kube-system"
                },
                "spec": {
                    "kubeClusterRef": {
                        "name": "demo-cluster",
                        "namespace": "default"
                    }
                }
            }
        }
    }
    
    try:
        result = function.run_function(request)
        is_valid, errors = validate_response_structure(result)
        return is_valid, result, errors
    except Exception as e:
        return False, {}, [f"Exception during processing: {str(e)}"]


async def test_kubenv_query() -> tuple[bool, dict[str, Any], list[str]]:
    """Test XKubEnv query processing."""
    logger.info("Testing XKubEnv query processing...")
    
    function = KubeCoreContextFunction()
    
    request = {
        "input": {
            "spec": {
                "query": {
                    "resourceType": "XKubEnv",
                    "requestedSchemas": ["qualityGate"]
                }
            }
        },
        "observed": {
            "composite": {
                "metadata": {
                    "name": "demo-env",
                    "namespace": "default"
                },
                "spec": {
                    "qualityGateRefs": [
                        {
                            "name": "security-gate",
                            "namespace": "default"
                        }
                    ]
                }
            }
        }
    }
    
    try:
        result = function.run_function(request)
        is_valid, errors = validate_response_structure(result)
        return is_valid, result, errors
    except Exception as e:
        return False, {}, [f"Exception during processing: {str(e)}"]


def validate_expected_response_format():
    """Validate that our expected format matches the specification."""
    logger.info("Validating expected response format...")
    
    expected_response = {
        "apiVersion": "context.fn.kubecore.io/v1beta1",
        "kind": "Output",
        "spec": {
            "platformContext": {
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
                                    }
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
                "insights": {
                    "recommendations": [
                        {
                            "category": "resource-optimization",
                            "suggestion": "Consider overriding memory requests for Python applications",
                            "impact": "medium"
                        }
                    ]
                }
            }
        }
    }
    
    is_valid, errors = validate_response_structure(expected_response)
    return is_valid, expected_response, errors


async def main():
    """Main validation function."""
    logger.info("Starting Phase 3 validation...")
    
    all_tests_passed = True
    
    # Test 1: Validate expected format
    logger.info("=" * 60)
    logger.info("TEST 1: Expected Format Validation")
    is_valid, response, errors = validate_expected_response_format()
    if is_valid:
        logger.info("✅ Expected format validation PASSED")
    else:
        logger.error("❌ Expected format validation FAILED")
        for error in errors:
            logger.error(f"  - {error}")
        all_tests_passed = False
    
    # Test 2: XApp query
    logger.info("=" * 60)
    logger.info("TEST 2: XApp Query Processing")
    is_valid, response, errors = await test_app_query()
    if is_valid:
        logger.info("✅ XApp query test PASSED")
        logger.info(f"Response contains {len(response.get('spec', {}).get('platformContext', {}).get('availableSchemas', {}))} schemas")
    else:
        logger.error("❌ XApp query test FAILED")
        for error in errors:
            logger.error(f"  - {error}")
        all_tests_passed = False
    
    # Test 3: XKubeSystem query
    logger.info("=" * 60)
    logger.info("TEST 3: XKubeSystem Query Processing")
    is_valid, response, errors = await test_kubesystem_query()
    if is_valid:
        logger.info("✅ XKubeSystem query test PASSED")
    else:
        logger.error("❌ XKubeSystem query test FAILED")
        for error in errors:
            logger.error(f"  - {error}")
        all_tests_passed = False
    
    # Test 4: XKubEnv query
    logger.info("=" * 60)
    logger.info("TEST 4: XKubEnv Query Processing")
    is_valid, response, errors = await test_kubenv_query()
    if is_valid:
        logger.info("✅ XKubEnv query test PASSED")
    else:
        logger.error("❌ XKubEnv query test FAILED")
        for error in errors:
            logger.error(f"  - {error}")
        all_tests_passed = False
    
    # Summary
    logger.info("=" * 60)
    if all_tests_passed:
        logger.info("🎉 ALL TESTS PASSED - Phase 3 implementation is valid!")
        return 0
    else:
        logger.error("💥 SOME TESTS FAILED - Phase 3 implementation needs fixes")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)