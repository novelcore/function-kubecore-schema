"""Caching system for KubeCore Platform Context Function.

Provides intelligent caching with TTL support for platform context queries
to improve performance and reduce redundant processing.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """Cache entry with TTL support."""
    data: dict[str, Any]
    timestamp: float
    hits: int = 0


class ContextCache:
    """Context cache with TTL and intelligent key generation."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1000):
        """Initialize cache with TTL and size limits.
        
        Args:
            ttl_seconds: Time to live for cache entries (default: 5 minutes)
            max_entries: Maximum number of cache entries (default: 1000)
        """
        self.cache: dict[str, CacheEntry] = {}
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.logger = logging.getLogger(__name__)

    def get(self, key: str) -> dict[str, Any] | None:
        """Get cached context data.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data if valid, None if expired or missing
        """
        if key not in self.cache:
            return None

        entry = self.cache[key]
        current_time = time.time()

        # Check if entry is expired
        if current_time - entry.timestamp > self.ttl_seconds:
            self.logger.debug(f"Cache entry expired: {key}")
            del self.cache[key]
            return None

        # Update hit count and return data
        entry.hits += 1
        self.logger.debug(f"Cache hit: {key} (hits: {entry.hits})")
        return entry.data

    def set(self, key: str, data: dict[str, Any]) -> None:
        """Cache context data.
        
        Args:
            key: Cache key
            data: Data to cache
        """
        # Implement LRU eviction if cache is full
        if len(self.cache) >= self.max_entries:
            self._evict_lru()

        current_time = time.time()
        self.cache[key] = CacheEntry(
            data=data,
            timestamp=current_time,
            hits=0
        )
        self.logger.debug(f"Cache set: {key}")

    def _evict_lru(self) -> None:
        """Evict least recently used cache entries."""
        if not self.cache:
            return

        # Find oldest entry (lowest timestamp)
        oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k].timestamp)
        del self.cache[oldest_key]
        self.logger.debug(f"Evicted cache entry: {oldest_key}")

    def generate_key(self, resource_type: str, context: dict[str, Any],
                    requested_schemas: list[str] | None = None, discovery_mode: str = "forward") -> str:
        """Generate cache key from query parameters.
        
        Args:
            resource_type: Type of resource being queried
            context: Request context including references
            requested_schemas: Optional list of requested schemas
            discovery_mode: Discovery mode (forward, bidirectional)
            
        Returns:
            Generated cache key
        """
        # Create deterministic key components
        key_components = [
            f"type:{resource_type}",
            f"mode:{discovery_mode}",
        ]

        # Add context references in sorted order for consistency
        if "references" in context:
            refs = context["references"]
            sorted_refs = sorted(refs.items()) if isinstance(refs, dict) else []
            key_components.append(f"refs:{hash(str(sorted_refs))}")

        # Add reverse discovery hints if present
        if context.get("requiresReverseDiscovery") and "discoveryHints" in context:
            hints = context["discoveryHints"]
            target_ref = hints.get("targetRef", {})
            key_components.append(f"target:{target_ref.get('kind')}:{target_ref.get('name')}:{target_ref.get('namespace')}")
        
        # Add transitive discovery configuration if enabled
        if context.get("enableTransitiveDiscovery", True):
            key_components.append("transitive:enabled")
            # Include transitive-specific parameters if available
            max_depth = context.get("transitiveMaxDepth", 3)
            key_components.append(f"depth:{max_depth}")

        # Add requested schemas
        if requested_schemas:
            sorted_schemas = sorted(requested_schemas)
            key_components.append(f"schemas:{':'.join(sorted_schemas)}")

        # Generate stable hash
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.logger.info("Cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        if not self.cache:
            return {
                "entries": 0,
                "total_hits": 0,
                "hit_rate": 0.0,
                "oldest_entry_age": 0
            }

        current_time = time.time()
        total_hits = sum(entry.hits for entry in self.cache.values())
        oldest_age = max(current_time - entry.timestamp for entry in self.cache.values())

        # Calculate approximate hit rate (hits / (hits + misses))
        # This is an approximation since we don't track misses directly
        hit_rate = total_hits / (total_hits + len(self.cache)) if total_hits > 0 else 0.0

        return {
            "entries": len(self.cache),
            "total_hits": total_hits,
            "hit_rate": hit_rate,
            "oldest_entry_age": oldest_age,
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl_seconds
        }

    def cleanup_expired(self) -> int:
        """Clean up expired cache entries.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = []

        for key, entry in self.cache.items():
            if current_time - entry.timestamp > self.ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)
