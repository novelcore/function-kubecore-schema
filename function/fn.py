"""KubeCore Platform Context Function.

This function provides intelligent schema resolution for the KubeCore platform.
It analyzes composition contexts and returns relevant platform schemas with
relationship mappings to enable informed composition decisions.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import grpc
from crossplane.function import logging as fn_logging
from crossplane.function import resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from crossplane.function.proto.v1 import run_function_pb2_grpc as grpcv1

# Import Phase 3 and Phase 4 components at module level
try:
    from .schema_registry import SchemaRegistry
    from .query_processor import QueryProcessor
    from .response_generator import ResponseGenerator
    from .insights_engine import InsightsEngine
    from .resource_resolver import ResourceResolver
    from .resource_summarizer import ResourceSummarizer
    from .k8s_client import K8sClient
    from .cache import ContextCache
    from .performance import PerformanceOptimizer
except ImportError:
    # Fallback for direct execution
    from schema_registry import SchemaRegistry  # type: ignore
    from query_processor import QueryProcessor  # type: ignore
    from response_generator import ResponseGenerator  # type: ignore
    from insights_engine import InsightsEngine  # type: ignore
    from resource_resolver import ResourceResolver  # type: ignore
    from resource_summarizer import ResourceSummarizer  # type: ignore
    from k8s_client import K8sClient  # type: ignore
    from cache import ContextCache  # type: ignore
    from performance import PerformanceOptimizer  # type: ignore


class KubeCoreContextFunction:
    """Main function class for KubeCore Platform Context resolution."""

    def __init__(self):
        """Initialize the function with Phase 3 and Phase 4 components."""
        self.logger = logging.getLogger(__name__)
        
        # Initialize Phase 4 performance components
        cache_ttl = int(os.getenv("CACHE_TTL_SECONDS", "300"))
        cache_max_entries = int(os.getenv("CACHE_MAX_ENTRIES", "1000"))
        max_workers = int(os.getenv("MAX_WORKERS", "4"))
        timeout_seconds = float(os.getenv("TIMEOUT_SECONDS", "30.0"))
        
        self.cache = ContextCache(ttl_seconds=cache_ttl, max_entries=cache_max_entries)
        self.performance_optimizer = PerformanceOptimizer(
            max_workers=max_workers, 
            timeout_seconds=timeout_seconds
        )
        
        # Initialize core components
        self.schema_registry = SchemaRegistry()
        self.k8s_client = K8sClient()
        self.resource_resolver = ResourceResolver(self.k8s_client)
        self.resource_summarizer = ResourceSummarizer(self.k8s_client)
        
        # Initialize Phase 3 processing components
        self.query_processor = QueryProcessor(
            self.schema_registry,
            self.resource_resolver,
            self.resource_summarizer
        )
        self.response_generator = ResponseGenerator(self.schema_registry)
        self.insights_engine = InsightsEngine(self.schema_registry)
        
        # Integrate caching into query processor
        self.query_processor.cache = self.cache
        self.query_processor.performance_optimizer = self.performance_optimizer

    async def run_function_async(self, request: dict[str, Any]) -> dict[str, Any]:
        """Async main function entry point for context resolution with Phase 4 optimizations."""
        start_time = time.time()
        self.logger.info("Starting KubeCore context resolution (Phase 4 - Optimized)")

        # Extract input specification
        input_spec = request.get("input", {}).get("spec", {})
        
        # Validate required structure
        if "query" not in input_spec:
            raise ValueError("Missing 'query' in input specification")
        
        # Extract context from observed composite resource
        context = self._extract_context(request)
        
        # Check cache first
        query = input_spec["query"]
        resource_type = query.get("resourceType")
        requested_schemas = query.get("requestedSchemas", [])
        
        cache_key = self.cache.generate_key(resource_type, context, requested_schemas)
        cached_result = self.cache.get(cache_key)
        
        if cached_result:
            self.performance_optimizer.update_cache_metrics(True)
            duration = time.time() - start_time
            self.logger.info(f"Cache hit - Query completed in {duration*1000:.1f}ms")
            return cached_result
        
        self.performance_optimizer.update_cache_metrics(False)
        
        # Combine query and context for processing
        processing_input = {
            "query": query,
            "context": context
        }
        
        # Phase 3: Process query with intelligent logic (now with performance optimizations)
        platform_context = await self.query_processor.process_query(processing_input)
        
        # Generate insights and recommendations
        insights = self.insights_engine.generate_insights(
            platform_context, 
            resource_type
        )
        platform_context["insights"] = insights
        
        # Generate standardized response
        final_response = self.response_generator.generate_response(
            platform_context,
            query
        )
        
        # Validate response format
        if not self.response_generator.validate_response_format(final_response):
            raise ValueError("Generated response does not match expected format")
        
        # Cache the response for future queries
        self.cache.set(cache_key, final_response)
        
        # Log performance metrics
        duration = time.time() - start_time
        self.logger.info(f"KubeCore context resolution completed in {duration*1000:.1f}ms")
        
        # Periodically log cache stats
        if hasattr(self, '_last_stats_log'):
            if time.time() - self._last_stats_log > 60:  # Every minute
                self._log_performance_stats()
        else:
            self._last_stats_log = time.time()
        
        return final_response

    def run_function(self, request: dict[str, Any]) -> dict[str, Any]:
        """Synchronous wrapper for async function."""
        try:
            # Check if there's already a running event loop
            asyncio.get_running_loop()
            # If we're in an async context, we can't use asyncio.run()
            raise RuntimeError("run_function called from within an event loop context. Use run_function_async instead.")
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.run_function_async(request))

    def _extract_context(self, request: dict[str, Any]) -> dict[str, Any]:
        """Extract context information from the request."""
        # Get observed composite resource
        observed = request.get("observed", {})
        composite = observed.get("composite", {})
        
        # Extract metadata
        metadata = composite.get("metadata", {})
        spec = composite.get("spec", {})
        
        # Build context
        context = {
            "requestorName": metadata.get("name", "unknown"),
            "requestorNamespace": metadata.get("namespace", "default"),
            "references": {}
        }
        
        # Extract references from spec
        # This would typically parse various *Ref fields
        for key, value in spec.items():
            if key.endswith("Ref") and isinstance(value, dict):
                ref_type = key.replace("Ref", "")
                context["references"][f"{ref_type}Refs"] = [value]
            elif key.endswith("Refs") and isinstance(value, list):
                context["references"][key] = value
        
        return context
    
    def _log_performance_stats(self) -> None:
        """Log performance and cache statistics."""
        try:
            cache_stats = self.cache.get_stats()
            perf_metrics = self.performance_optimizer.get_metrics()
            
            self.logger.info("Performance metrics", extra={
                "cache_entries": cache_stats["entries"],
                "cache_hit_rate": cache_stats["hit_rate"],
                "total_queries": perf_metrics["total_queries"],
                "avg_response_time": perf_metrics["avg_response_time"],
                "parallel_operations": perf_metrics["parallel_operations"],
                "errors": perf_metrics["errors"]
            })
            
            # Clean up expired cache entries
            cleaned = self.cache.cleanup_expired()
            if cleaned > 0:
                self.logger.debug(f"Cleaned up {cleaned} expired cache entries")
                
            self._last_stats_log = time.time()
            
        except Exception as e:
            self.logger.warning(f"Error logging performance stats: {e}")


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
        composite_resource = {}
        if req.observed and req.observed.composite:
            composite_resource = resource.struct_to_dict(
                req.observed.composite.resource
            )

        request_dict = {
            "input": resource.struct_to_dict(req.input) if req.input else {},
            "observed": {"composite": composite_resource},
        }

        try:
            # Process the request through our function (async)
            result = await self.function.run_function_async(request_dict)

            # Write result to response context with correct format
            ctx_key = "context.fn.kubecore.io/platform-context"
            current_ctx = resource.struct_to_dict(rsp.context)
            
            # Extract the platformContext from the Phase 3 response
            if "spec" in result and "platformContext" in result["spec"]:
                current_ctx[ctx_key] = result["spec"]["platformContext"]
            else:
                # Fallback for backward compatibility
                current_ctx[ctx_key] = result
                
            rsp.context = resource.dict_to_struct(current_ctx)

            response.normal(rsp, "KubeCore context resolution completed successfully")
            log.info("kubecore-context.complete", step="kubecore-context")

        except Exception as e:
            self.log.error("kubecore-context.error", error=str(e))
            response.fatal(rsp, f"KubeCore context resolution failed: {e!s}")

        return rsp
