"""KubeCore Platform Context Function.

This function provides intelligent schema resolution for the KubeCore platform.
It analyzes composition contexts and returns relevant platform schemas with
relationship mappings to enable informed composition decisions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import grpc
from crossplane.function import logging as fn_logging, resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from crossplane.function.proto.v1 import run_function_pb2_grpc as grpcv1


class KubeCoreContextFunction:
    """Main function class for KubeCore Platform Context resolution."""
    
    def __init__(self):
        """Initialize the function with schema registry."""
        try:
            from .schema_registry import SchemaRegistry
        except ImportError:
            # Fallback for direct execution
            from schema_registry import SchemaRegistry
        
        self.schema_registry = SchemaRegistry()
        self.logger = logging.getLogger(__name__)
    
    def run_function(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Main function entry point for context resolution."""
        self.logger.info("Starting KubeCore context resolution")
        
        # Extract query parameters from request
        input_spec = request.get("input", {}).get("spec", {})
        query = input_spec.get("query", {})
        
        resource_type = query.get("resourceType", "")
        requested_schemas = query.get("requestedSchemas", [])
        include_full_schemas = query.get("includeFullSchemas", True)
        
        self.logger.info(f"Processing query for resource type: {resource_type}")
        
        # Get accessible schemas based on resource type
        accessible_schemas = self.schema_registry.get_accessible_schemas(resource_type)
        
        # Filter requested schemas if specified
        if requested_schemas:
            accessible_schemas = [s for s in accessible_schemas if s in requested_schemas]
        
        # Build response
        response = {
            "platformContext": {
                "requestor": {
                    "type": resource_type,
                    "name": "",  # Will be populated from context
                    "namespace": ""
                },
                "availableSchemas": {},
                "relationships": {
                    "direct": [],
                    "indirect": []
                },
                "insights": {
                    "suggestedReferences": [],
                    "validationRules": [],
                    "recommendations": []
                }
            }
        }
        
        # Populate available schemas
        for schema_name in accessible_schemas:
            schema_info = self.schema_registry.get_schema_info(schema_name)
            if schema_info:
                response["platformContext"]["availableSchemas"][schema_name] = {
                    "metadata": {
                        "apiVersion": schema_info.api_version,
                        "kind": schema_info.kind,
                        "accessible": True,
                        "relationshipPath": self.schema_registry.get_relationship_path(resource_type, schema_name)
                    }
                }
                
                if include_full_schemas:
                    response["platformContext"]["availableSchemas"][schema_name]["schema"] = schema_info.schema
        
        self.logger.info(f"Resolved {len(accessible_schemas)} accessible schemas")
        return response


class FunctionRunner(grpcv1.FunctionRunnerService):
    """A FunctionRunner handles gRPC RunFunctionRequests."""

    def __init__(self):
        """Create a new FunctionRunner."""
        self.log = fn_logging.get_logger()
        self.function = KubeCoreContextFunction()

    async def RunFunction(
        self, req: fnv1.RunFunctionRequest, _: grpc.aio.ServicerContext
    ) -> fnv1.RunFunctionResponse:
        """Run the function."""
        # Extract tag for logging
        try:
            tag = req.meta.tag
        except Exception:
            tag = ""
        
        log = self.log.bind(tag=tag)
        log.info("kubecore-context.start", step="kubecore-context")
        
        # Build response based on the request
        rsp = response.to(req)
        
        # Convert request to dictionary format for processing
        request_dict = {
            "input": resource.struct_to_dict(req.input) if req.input else {},
            "observed": {
                "composite": resource.struct_to_dict(req.observed.composite.resource) if req.observed and req.observed.composite else {}
            }
        }
        
        try:
            # Process the request through our function
            result = self.function.run_function(request_dict)
            
            # Write result to response context
            ctx_key = "context.fn.kubecore.io/platform-context"
            current_ctx = resource.struct_to_dict(rsp.context)
            current_ctx[ctx_key] = result
            rsp.context = resource.dict_to_struct(current_ctx)
            
            response.normal(rsp, "KubeCore context resolution completed successfully")
            log.info("kubecore-context.complete", step="kubecore-context")
            
        except Exception as e:
            self.log.error("kubecore-context.error", error=str(e))
            response.fatal(rsp, f"KubeCore context resolution failed: {str(e)}")
        
        return rsp
