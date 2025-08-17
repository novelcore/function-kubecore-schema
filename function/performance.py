"""Performance optimization utilities for KubeCore Platform Context Function.

Provides parallel processing, async operations, and performance monitoring
to optimize function response times and resource usage.
"""

from __future__ import annotations

import asyncio
import time
import logging
from typing import List, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring."""
    total_queries: int = 0
    avg_response_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    parallel_operations: int = 0
    errors: int = 0


class PerformanceOptimizer:
    """Performance optimizer with parallel processing and monitoring."""
    
    def __init__(self, max_workers: int = 4, timeout_seconds: float = 30.0):
        """Initialize performance optimizer.
        
        Args:
            max_workers: Maximum number of parallel workers
            timeout_seconds: Timeout for operations
        """
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.metrics = PerformanceMetrics()
        self.logger = logging.getLogger(__name__)
    
    async def resolve_references_parallel(self, 
                                        references: List[Dict[str, Any]], 
                                        resolver_func: Callable) -> List[Dict[str, Any]]:
        """Resolve resource references in parallel.
        
        Args:
            references: List of resource references to resolve
            resolver_func: Function to resolve individual references
            
        Returns:
            List of resolved resource data
        """
        if not references:
            return []
        
        start_time = time.time()
        self.metrics.parallel_operations += 1
        
        try:
            loop = asyncio.get_event_loop()
            
            # Create tasks for parallel execution
            tasks = [
                loop.run_in_executor(
                    self.executor, 
                    self._safe_resolve_reference, 
                    ref, 
                    resolver_func
                )
                for ref in references
            ]
            
            # Execute with timeout
            resolved_refs = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.timeout_seconds
            )
            
            # Filter out exceptions and log them
            results = []
            for i, result in enumerate(resolved_refs):
                if isinstance(result, Exception):
                    self.logger.warning(f"Failed to resolve reference {i}: {result}")
                    self.metrics.errors += 1
                    # Add placeholder for failed reference
                    results.append({"error": str(result), "index": i})
                else:
                    results.append(result)
            
            duration = time.time() - start_time
            self.logger.debug(f"Resolved {len(references)} references in {duration:.3f}s")
            
            return results
            
        except asyncio.TimeoutError:
            self.logger.error(f"Reference resolution timed out after {self.timeout_seconds}s")
            self.metrics.errors += 1
            raise
        except Exception as e:
            self.logger.error(f"Error in parallel reference resolution: {e}")
            self.metrics.errors += 1
            raise
    
    def _safe_resolve_reference(self, reference: Dict[str, Any], 
                              resolver_func: Callable) -> Dict[str, Any]:
        """Safely resolve a single reference with error handling.
        
        Args:
            reference: Reference to resolve
            resolver_func: Function to resolve the reference
            
        Returns:
            Resolved reference data
        """
        try:
            return resolver_func(reference)
        except Exception as e:
            self.logger.warning(f"Failed to resolve reference {reference}: {e}")
            return {"error": str(e), "reference": reference}
    
    async def process_schemas_parallel(self, 
                                     schema_names: List[str], 
                                     processor_func: Callable) -> Dict[str, Any]:
        """Process multiple schemas in parallel.
        
        Args:
            schema_names: List of schema names to process
            processor_func: Function to process individual schemas
            
        Returns:
            Dictionary mapping schema names to processed data
        """
        if not schema_names:
            return {}
        
        start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            
            # Create tasks for parallel schema processing
            tasks = {
                name: loop.run_in_executor(
                    self.executor,
                    self._safe_process_schema,
                    name,
                    processor_func
                )
                for name in schema_names
            }
            
            # Wait for all tasks to complete
            results = {}
            for name, task in tasks.items():
                try:
                    result = await asyncio.wait_for(task, timeout=self.timeout_seconds)
                    results[name] = result
                except asyncio.TimeoutError:
                    self.logger.warning(f"Schema processing timed out for {name}")
                    results[name] = {"error": "timeout"}
                    self.metrics.errors += 1
                except Exception as e:
                    self.logger.warning(f"Error processing schema {name}: {e}")
                    results[name] = {"error": str(e)}
                    self.metrics.errors += 1
            
            duration = time.time() - start_time
            self.logger.debug(f"Processed {len(schema_names)} schemas in {duration:.3f}s")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in parallel schema processing: {e}")
            self.metrics.errors += 1
            raise
    
    def _safe_process_schema(self, schema_name: str, 
                           processor_func: Callable) -> Dict[str, Any]:
        """Safely process a single schema with error handling.
        
        Args:
            schema_name: Name of schema to process
            processor_func: Function to process the schema
            
        Returns:
            Processed schema data
        """
        try:
            return processor_func(schema_name)
        except Exception as e:
            self.logger.warning(f"Failed to process schema {schema_name}: {e}")
            return {"error": str(e), "schema": schema_name}
    
    def measure_performance(self, func: Callable) -> Callable:
        """Decorator to measure function performance.
        
        Args:
            func: Function to measure
            
        Returns:
            Decorated function with performance tracking
        """
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Update metrics
                self.metrics.total_queries += 1
                self.metrics.avg_response_time = (
                    (self.metrics.avg_response_time * (self.metrics.total_queries - 1) + duration)
                    / self.metrics.total_queries
                )
                
                self.logger.debug(f"Function {func.__name__} completed in {duration:.3f}s")
                return result
                
            except Exception as e:
                self.metrics.errors += 1
                self.logger.error(f"Error in {func.__name__}: {e}")
                raise
        
        return wrapper
    
    async def batch_process(self, 
                          items: List[Any], 
                          processor: Callable,
                          batch_size: int = 10) -> List[Any]:
        """Process items in batches to control resource usage.
        
        Args:
            items: Items to process
            processor: Processing function
            batch_size: Size of each batch
            
        Returns:
            List of processed results
        """
        if not items:
            return []
        
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            self.logger.debug(f"Processing batch {i//batch_size + 1} of {len(batch)} items")
            
            try:
                # Process batch in parallel
                loop = asyncio.get_event_loop()
                batch_tasks = [
                    loop.run_in_executor(self.executor, processor, item)
                    for item in batch
                ]
                
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*batch_tasks, return_exceptions=True),
                    timeout=self.timeout_seconds
                )
                
                results.extend(batch_results)
                
            except asyncio.TimeoutError:
                self.logger.error(f"Batch processing timed out")
                self.metrics.errors += 1
                # Add placeholder results for failed batch
                results.extend([{"error": "timeout"} for _ in batch])
            except Exception as e:
                self.logger.error(f"Error in batch processing: {e}")
                self.metrics.errors += 1
                results.extend([{"error": str(e)} for _ in batch])
        
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics.
        
        Returns:
            Dictionary containing performance metrics
        """
        cache_total = self.metrics.cache_hits + self.metrics.cache_misses
        cache_hit_rate = (
            self.metrics.cache_hits / cache_total 
            if cache_total > 0 else 0.0
        )
        
        return {
            "total_queries": self.metrics.total_queries,
            "avg_response_time": self.metrics.avg_response_time,
            "cache_hit_rate": cache_hit_rate,
            "parallel_operations": self.metrics.parallel_operations,
            "errors": self.metrics.errors,
            "max_workers": self.max_workers,
            "timeout_seconds": self.timeout_seconds
        }
    
    def update_cache_metrics(self, hit: bool) -> None:
        """Update cache hit/miss metrics.
        
        Args:
            hit: True if cache hit, False if cache miss
        """
        if hit:
            self.metrics.cache_hits += 1
        else:
            self.metrics.cache_misses += 1
    
    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        self.metrics = PerformanceMetrics()
        self.logger.info("Performance metrics reset")
    
    def cleanup(self) -> None:
        """Clean up resources."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
            self.logger.info("Performance optimizer cleaned up")