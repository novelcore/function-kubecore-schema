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
    from .cache import ContextCache
    from .insights_engine import InsightsEngine
    from .k8s_client import K8sClient
    from .performance import PerformanceOptimizer
    from .query_processor import QueryProcessor
    from .resource_resolver import ResourceResolver
    from .resource_summarizer import ResourceSummarizer
    from .response_generator import ResponseGenerator
    from .schema_registry import SchemaRegistry
    from .transitive_discovery import TransitiveDiscoveryEngine, TransitiveDiscoveryConfig
except ImportError:
    # Fallback for direct execution
    from cache import ContextCache  # type: ignore
    from insights_engine import InsightsEngine  # type: ignore
    from k8s_client import K8sClient  # type: ignore
    from performance import PerformanceOptimizer  # type: ignore
    from query_processor import QueryProcessor  # type: ignore
    from resource_resolver import ResourceResolver  # type: ignore
    from resource_summarizer import ResourceSummarizer  # type: ignore
    from response_generator import ResponseGenerator  # type: ignore
    from schema_registry import SchemaRegistry  # type: ignore
    from transitive_discovery import TransitiveDiscoveryEngine, TransitiveDiscoveryConfig  # type: ignore


class KubeCoreContextFunction:
    """Main function class for KubeCore Platform Context resolution."""

    def __init__(self):
        """Initialize the function with Phase 3 and Phase 4 components."""
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing KubeCoreContextFunction")

        # Initialize Phase 4 performance components
        cache_ttl = int(os.getenv("CACHE_TTL_SECONDS", "300"))
        cache_max_entries = int(os.getenv("CACHE_MAX_ENTRIES", "1000"))
        max_workers = int(os.getenv("MAX_WORKERS", "4"))
        timeout_seconds = float(os.getenv("TIMEOUT_SECONDS", "30.0"))
        
        self.logger.debug(f"Cache configuration: TTL={cache_ttl}s, max_entries={cache_max_entries}")
        self.logger.debug(f"Performance configuration: max_workers={max_workers}, timeout={timeout_seconds}s")

        self.cache = ContextCache(ttl_seconds=cache_ttl, max_entries=cache_max_entries)
        self.performance_optimizer = PerformanceOptimizer(
            max_workers=max_workers,
            timeout_seconds=timeout_seconds
        )
        self.logger.debug("Cache and performance optimizer initialized")

        # Initialize core components
        self.logger.debug("Initializing core components")
        self.schema_registry = SchemaRegistry()
        self.k8s_client = K8sClient()
        # Connect to Kubernetes cluster - this must be done synchronously during init
        try:
            # Run the async connect method synchronously during initialization
            import asyncio
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
            
            if loop is not None:
                # We're in an async context - create a task
                asyncio.create_task(self._connect_k8s_client())
            else:
                # We're not in async context - run it directly
                asyncio.run(self.k8s_client.connect())
                self.logger.debug("K8s client connected successfully")
        except Exception as e:
            self.logger.warning(f"K8s client connection failed during init: {e}")
            # Continue initialization - connection will be attempted later if needed
        
        self.resource_resolver = ResourceResolver(self.k8s_client)
        self.resource_summarizer = ResourceSummarizer(self.k8s_client)
        self.logger.debug("Core components initialized")

        # Initialize Phase 3 processing components
        self.logger.debug("Initializing Phase 3 processing components")
        self.query_processor = QueryProcessor(
            self.schema_registry,
            self.resource_resolver,
            self.resource_summarizer
        )
        self.response_generator = ResponseGenerator(self.schema_registry)
        self.insights_engine = InsightsEngine(self.schema_registry)
        self.logger.debug("Phase 3 processing components initialized")

        # Initialize transitive discovery engine
        transitive_config = TransitiveDiscoveryConfig(
            max_depth=int(os.getenv("TRANSITIVE_MAX_DEPTH", "3")),
            max_resources_per_type=int(os.getenv("TRANSITIVE_MAX_RESOURCES", "50")),
            timeout_per_depth=float(os.getenv("TRANSITIVE_TIMEOUT", "10.0")),
            parallel_workers=int(os.getenv("TRANSITIVE_WORKERS", "5")),
            cache_intermediate_results=os.getenv("TRANSITIVE_CACHE", "true").lower() == "true"
        )
        self.transitive_discovery_engine = TransitiveDiscoveryEngine(
            self.resource_resolver, 
            transitive_config
        )
        self.logger.debug(f"Transitive discovery engine initialized with max_depth={transitive_config.max_depth}")

        # Integrate caching and components into query processor
        self.query_processor.cache = self.cache
        self.query_processor.performance_optimizer = self.performance_optimizer
        self.query_processor.set_transitive_discovery_engine(self.transitive_discovery_engine)
        self.logger.info("KubeCoreContextFunction initialization complete")

    async def _connect_k8s_client(self) -> None:
        """Connect K8s client asynchronously during initialization."""
        try:
            await self.k8s_client.connect()
            self.logger.debug("K8s client connected successfully (async)")
        except Exception as e:
            self.logger.warning(f"K8s client connection failed (async): {e}")

    async def run_function_async(self, request: dict[str, Any]) -> dict[str, Any]:
        """Async main function entry point for context resolution with Phase 4 optimizations."""
        start_time = time.time()
        self.logger.info("Starting KubeCore context resolution (Phase 4 - Optimized)")
        self.logger.debug(f"Request input keys: {list(request.keys())}")

        # Extract input specification
        input_spec = request.get("input", {}).get("spec", {})
        self.logger.debug(f"Input specification keys: {list(input_spec.keys())}")

        # Validate required structure
        if "query" not in input_spec:
            self.logger.error("Missing 'query' in input specification")
            raise ValueError("Missing 'query' in input specification")
        
        self.logger.debug("Input validation passed")

        # Extract context from observed composite resource
        self.logger.debug("Extracting context from observed composite resource")
        context = self._extract_context(request)
        self.logger.debug(f"Extracted context: requestor={context.get('requestorName')}, namespace={context.get('requestorNamespace')}, references={len(context.get('references', {}))} ref types")

        # Check cache first
        query = input_spec["query"]
        resource_type = query.get("resourceType")
        requested_schemas = query.get("requestedSchemas", [])
        
        self.logger.debug(f"Query details: resourceType={resource_type}, requestedSchemas={requested_schemas}")

        # Determine discovery mode
        discovery_mode = "bidirectional" if context.get("requiresReverseDiscovery") else "forward"
        cache_key = self.cache.generate_key(resource_type, context, requested_schemas, discovery_mode)
        self.logger.debug(f"Generated cache key: {cache_key} (mode: {discovery_mode})")
        cached_result = self.cache.get(cache_key)

        if cached_result:
            self.performance_optimizer.update_cache_metrics(True)
            duration = time.time() - start_time
            self.logger.info(f"Cache hit - Query completed in {duration*1000:.1f}ms")
            self.logger.debug(f"Returning cached result with {len(cached_result.get('spec', {}).get('platformContext', {}).get('availableSchemas', {}))} schemas")
            return cached_result

        self.performance_optimizer.update_cache_metrics(False)
        self.logger.debug("Cache miss - proceeding with fresh query processing")

        # Combine query and context for processing
        processing_input = {
            "query": query,
            "context": context
        }
        self.logger.debug(f"Prepared processing input with query and context")

        # Ensure K8s client is connected for transitive discovery
        if not self.k8s_client._connected:
            self.logger.debug("K8s client not connected, attempting connection")
            try:
                await self.k8s_client.connect()
                self.logger.debug("K8s client connected successfully")
            except Exception as e:
                self.logger.warning(f"K8s client connection failed: {e}")
                # Continue with limited functionality

        # Phase 3: Process query with intelligent logic (now with performance optimizations)
        self.logger.debug("Starting query processing")
        platform_context = await self.query_processor.process_query(processing_input)
        self.logger.debug(f"Query processing complete: {len(platform_context.get('availableSchemas', {}))} schemas resolved")

        # Generate insights and recommendations
        self.logger.debug("Generating insights and recommendations")
        insights = self.insights_engine.generate_insights(
            platform_context,
            resource_type
        )
        platform_context["insights"] = insights
        self.logger.debug(f"Generated {len(insights)} insights")

        # Generate standardized response
        self.logger.debug("Generating standardized response")
        final_response = self.response_generator.generate_response(
            platform_context,
            query
        )
        self.logger.debug(f"Response generated with spec containing {len(final_response.get('spec', {}))} top-level keys")

        # Validate response format
        self.logger.debug("Validating response format")
        if not self.response_generator.validate_response_format(final_response):
            self.logger.error("Generated response does not match expected format")
            raise ValueError("Generated response does not match expected format")
        self.logger.debug("Response format validation passed")

        # Cache the response for future queries
        self.logger.debug(f"Caching response with key: {cache_key}")
        self.cache.set(cache_key, final_response)

        # Log performance metrics
        duration = time.time() - start_time
        self.logger.info(f"KubeCore context resolution completed in {duration*1000:.1f}ms")

        # Periodically log cache stats
        if hasattr(self, "_last_stats_log"):
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
        self.logger.debug("Extracting context from request")
        # Get observed composite resource
        observed = request.get("observed", {})
        composite = observed.get("composite", {})
        self.logger.debug(f"Found composite resource with {len(composite)} top-level keys")

        # Extract metadata
        metadata = composite.get("metadata", {})
        spec = composite.get("spec", {})
        self.logger.debug(f"Extracted metadata: {list(metadata.keys())}, spec: {list(spec.keys())}")

        # Build context
        requestor_name = metadata.get("name", "unknown")
        requestor_namespace = metadata.get("namespace", "default")
        requestor_kind = composite.get("kind", "")
        
        context = {
            "requestorName": requestor_name,
            "requestorNamespace": requestor_namespace,
            "requestorKind": requestor_kind,
            "references": {}
        }
        self.logger.debug(f"Built base context: requestor={requestor_name}, namespace={requestor_namespace}, kind={requestor_kind}")

        # Extract references from spec
        # This would typically parse various *Ref fields
        ref_count = 0
        for key, value in spec.items():
            if key.endswith("Ref") and isinstance(value, dict):
                ref_type = key.replace("Ref", "")
                context["references"][f"{ref_type}Refs"] = [value]
                ref_count += 1
                self.logger.debug(f"Found single reference: {key} -> {ref_type}Refs")
            elif key.endswith("Refs") and isinstance(value, list):
                context["references"][key] = value
                ref_count += len(value)
                self.logger.debug(f"Found reference list: {key} with {len(value)} items")
        
        # Add reverse discovery hints for hub resources
        if requestor_kind in ["XGitHubProject", "XKubeCluster", "XKubeNet", "XQualityGate"]:
            context["requiresReverseDiscovery"] = True
            context["discoveryHints"] = {
                "targetRef": {
                    "name": requestor_name,
                    "namespace": requestor_namespace,
                    "kind": requestor_kind
                }
            }
            self.logger.debug(f"Added reverse discovery hints for {requestor_kind}: {requestor_name}")
        
        self.logger.debug(f"Extracted {ref_count} total references across {len(context['references'])} reference types")

        return context

    def _log_performance_stats(self) -> None:
        """Log performance and cache statistics."""
        self.logger.debug("Logging performance statistics")
        try:
            cache_stats = self.cache.get_stats()
            perf_metrics = self.performance_optimizer.get_metrics()

            self.logger.info(f"Performance metrics - Cache: {cache_stats['entries']} entries, {cache_stats['hit_rate']:.2f} hit rate | Queries: {perf_metrics['total_queries']} total, {perf_metrics['avg_response_time']:.1f}ms avg | Parallel ops: {perf_metrics['parallel_operations']}, Errors: {perf_metrics['errors']}")

            # Clean up expired cache entries
            cleaned = self.cache.cleanup_expired()
            if cleaned > 0:
                self.logger.debug(f"Cleaned up {cleaned} expired cache entries")
            else:
                self.logger.debug("No expired cache entries to clean")

            self._last_stats_log = time.time()

        except Exception as e:
            self.logger.warning(f"Error logging performance stats: {e}")
            self.logger.debug(f"Performance stats error details: {e}", exc_info=True)


class FunctionRunner(grpcv1.FunctionRunnerService):
    """A FunctionRunner handles gRPC RunFunctionRequests."""

    def __init__(self):
        """Create a new FunctionRunner."""
        self.log = fn_logging.get_logger()
        self.log.info("Initializing FunctionRunner")
        self.function = KubeCoreContextFunction()
        self.log.debug("FunctionRunner initialization complete")

    async def RunFunction(
        self, req: fnv1.RunFunctionRequest, _: grpc.aio.ServicerContext
    ) -> fnv1.RunFunctionResponse:
        """Run the function."""
        # Extract tag for logging
        try:
            tag = req.meta.tag
            self.log.debug(f"Extracted request tag: {tag}")
        except Exception as e:
            tag = ""
            self.log.debug(f"No tag found in request: {e}")

        log = self.log.bind(tag=tag)
        log.info("kubecore-context.start", step="kubecore-context")
        log.debug(f"Starting function execution with tag: {tag}")

        # Build response based on the request
        log.debug("Building response object")
        rsp = response.to(req)

        # Convert request to dictionary format for processing
        log.debug("Converting request to dictionary format")
        composite_resource = {}
        if req.observed and req.observed.composite:
            composite_resource = resource.struct_to_dict(
                req.observed.composite.resource
            )
            log.debug(f"Converted composite resource with {len(composite_resource)} top-level keys")
        else:
            log.debug("No observed composite resource found")

        input_dict = resource.struct_to_dict(req.input) if req.input else {}
        request_dict = {
            "input": input_dict,
            "observed": {"composite": composite_resource},
        }
        log.debug(f"Prepared request dictionary: input keys={list(input_dict.keys())}, composite keys={list(composite_resource.keys())}")

        try:
            # Process the request through our function (async)
            log.debug("Starting async function processing")
            result = await self.function.run_function_async(request_dict)
            log.debug(f"Function processing completed, result keys: {list(result.keys())}")

            # Write result to response context with correct format
            ctx_key = "context.fn.kubecore.io/platform-context"
            current_ctx = resource.struct_to_dict(rsp.context)
            log.debug(f"Writing result to context key: {ctx_key}")

            # Extract the platformContext from the Phase 3 response
            if "spec" in result and "platformContext" in result["spec"]:
                platform_context = result["spec"]["platformContext"]
                current_ctx[ctx_key] = platform_context
                log.debug(f"Set platform context with {len(platform_context.get('availableSchemas', {}))} schemas")
            else:
                # Fallback for backward compatibility
                current_ctx[ctx_key] = result
                log.debug("Used fallback for backward compatibility - setting entire result as context")

            rsp.context = resource.dict_to_struct(current_ctx)
            log.debug("Response context updated successfully")

            response.normal(rsp, "KubeCore context resolution completed successfully")
            log.info("kubecore-context.complete", step="kubecore-context")
            log.debug("Function execution completed successfully")

        except Exception as e:
            self.log.error("kubecore-context.error", error=str(e))
            self.log.debug(f"Function execution failed with exception: {e}", exc_info=True)
            response.fatal(rsp, f"KubeCore context resolution failed: {e!s}")

        log.debug("Returning response")
        return rsp
