"""Kubernetes Client for KubeCore Platform Context Function.

This module provides a robust Kubernetes client with authentication,
error handling, resource fetching, and connection management.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from kubernetes import client, config
from kubernetes.client import ApiException


class K8sConnectionError(Exception):
    """Raised when Kubernetes connection fails."""


class K8sAuthenticationError(Exception):
    """Raised when Kubernetes authentication fails."""


class K8sResourceNotFoundError(Exception):
    """Raised when a requested Kubernetes resource is not found."""


class K8sPermissionError(Exception):
    """Raised when insufficient permissions for Kubernetes operation."""


class K8sClient:
    """Kubernetes client with connection pooling and retry logic."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        connection_timeout: int = 30,
        read_timeout: int = 60,
    ):
        """Initialize the Kubernetes client.
        
        Args:
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Base delay between retries in seconds
            connection_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.logger = logging.getLogger(__name__)

        # Client instances
        self._api_client: client.ApiClient | None = None
        self._core_v1: client.CoreV1Api | None = None
        self._custom_objects: client.CustomObjectsApi | None = None
        self._apps_v1: client.AppsV1Api | None = None

        # Connection state
        self._connected = False
        self._last_health_check = 0.0
        self._health_check_interval = 30.0  # 30 seconds

    async def connect(self) -> None:
        """Establish connection to Kubernetes cluster with authentication."""
        try:
            # Load Kubernetes configuration
            # First try in-cluster config, then fall back to local config
            try:
                config.load_incluster_config()
                self.logger.info("Using in-cluster Kubernetes configuration")
            except config.ConfigException:
                try:
                    config.load_kube_config()
                    self.logger.info("Using local Kubernetes configuration")
                except config.ConfigException as e:
                    raise K8sAuthenticationError(
                        f"Unable to load Kubernetes configuration: {e}"
                    ) from e

            # Configure client timeouts
            configuration = client.Configuration.get_default_copy()
            configuration.connection_pool_maxsize = 10
            configuration.retries = 0  # We handle retries manually

            # Create API client with configuration
            self._api_client = client.ApiClient(configuration)

            # Initialize API instances
            self._core_v1 = client.CoreV1Api(self._api_client)
            self._custom_objects = client.CustomObjectsApi(self._api_client)
            self._apps_v1 = client.AppsV1Api(self._api_client)

            # Test connection
            await self._test_connection()
            self._connected = True
            self._last_health_check = time.time()

            self.logger.info("Successfully connected to Kubernetes cluster")

        except Exception as e:
            self._connected = False
            if isinstance(e, (K8sAuthenticationError, K8sConnectionError)):
                raise
            raise K8sConnectionError(f"Failed to connect to Kubernetes: {e}") from e

    async def disconnect(self) -> None:
        """Close connection to Kubernetes cluster."""
        if self._api_client:
            await self._api_client.close()

        self._api_client = None
        self._core_v1 = None
        self._custom_objects = None
        self._apps_v1 = None
        self._connected = False

        self.logger.info("Disconnected from Kubernetes cluster")

    async def _test_connection(self) -> None:
        """Test Kubernetes cluster connectivity."""
        if not self._core_v1:
            raise K8sConnectionError("Core V1 API client not initialized")

        try:
            # Simple health check - list namespaces (limited to 1 for efficiency)
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._core_v1.list_namespace(limit=1)
            )
        except ApiException as e:
            if e.status == 401:
                raise K8sAuthenticationError("Kubernetes authentication failed") from e
            elif e.status == 403:
                raise K8sPermissionError("Insufficient permissions for Kubernetes API") from e
            else:
                raise K8sConnectionError(f"Kubernetes connection test failed: {e}") from e

    async def _ensure_connected(self) -> None:
        """Ensure connection is active and perform health checks."""
        current_time = time.time()

        if not self._connected:
            await self.connect()
        elif current_time - self._last_health_check > self._health_check_interval:
            try:
                await self._test_connection()
                self._last_health_check = current_time
            except Exception:
                self.logger.warning("Health check failed, reconnecting...")
                await self.connect()

    async def _retry_request(self, func, *args, **kwargs) -> Any:
        """Execute a request with retry logic."""
        await self._ensure_connected()

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                # Execute the function in a thread pool
                return await asyncio.get_event_loop().run_in_executor(
                    None, func, *args, **kwargs
                )
            except ApiException as e:
                last_exception = e

                # Don't retry on certain errors
                if e.status in (401, 403, 404):
                    if e.status == 401:
                        raise K8sAuthenticationError("Authentication failed") from e
                    elif e.status == 403:
                        raise K8sPermissionError("Insufficient permissions") from e
                    elif e.status == 404:
                        raise K8sResourceNotFoundError("Resource not found") from e

                # Log retry attempt
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        f"Request failed (attempt {attempt + 1}), retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)

                    # Reconnect on connection errors
                    if e.status >= 500:
                        try:
                            await self.connect()
                        except Exception as conn_e:
                            self.logger.error(f"Reconnection failed: {conn_e}")

            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(
                        f"Request failed (attempt {attempt + 1}), retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise K8sConnectionError(f"Request failed after {self.max_retries + 1} attempts") from last_exception

    async def get_resource(
        self,
        api_version: str,
        kind: str,
        name: str,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Get a Kubernetes resource by name and namespace.
        
        Args:
            api_version: API version (e.g., "v1", "apps/v1")
            kind: Resource kind (e.g., "Pod", "Deployment")
            name: Resource name
            namespace: Resource namespace (None for cluster-scoped resources)
            
        Returns:
            Resource dictionary
            
        Raises:
            K8sResourceNotFoundError: If resource not found
            K8sPermissionError: If insufficient permissions
            K8sConnectionError: If connection fails
        """
        if not self._custom_objects:
            raise K8sConnectionError("Custom objects API client not initialized")

        try:
            if "/" in api_version:
                group, version = api_version.split("/", 1)
            else:
                group = ""
                version = api_version

            # Determine plural form (simplified)
            plural = self._get_plural_form(kind)

            if namespace:
                response = await self._retry_request(
                    self._custom_objects.get_namespaced_custom_object,
                    group, version, namespace, plural, name
                )
            else:
                response = await self._retry_request(
                    self._custom_objects.get_cluster_custom_object,
                    group, version, plural, name
                )

            return response

        except Exception as e:
            if isinstance(e, (K8sResourceNotFoundError, K8sPermissionError, K8sConnectionError)):
                raise
            raise K8sConnectionError(f"Failed to get resource {kind}/{name}: {e}") from e

    async def list_resources(
        self,
        api_version: str,
        kind: str,
        namespace: str | None = None,
        label_selector: str | None = None,
        field_selector: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List Kubernetes resources with optional filtering.
        
        Args:
            api_version: API version (e.g., "v1", "apps/v1")
            kind: Resource kind (e.g., "Pod", "Deployment")
            namespace: Resource namespace (None for cluster-scoped resources)
            label_selector: Label selector for filtering
            field_selector: Field selector for filtering
            limit: Maximum number of resources to return
            
        Returns:
            List response dictionary with items
            
        Raises:
            K8sPermissionError: If insufficient permissions
            K8sConnectionError: If connection fails
        """
        if not self._custom_objects:
            raise K8sConnectionError("Custom objects API client not initialized")

        try:
            if "/" in api_version:
                group, version = api_version.split("/", 1)
            else:
                group = ""
                version = api_version

            # Determine plural form (simplified)
            plural = self._get_plural_form(kind)

            if namespace:
                response = await self._retry_request(
                    self._custom_objects.list_namespaced_custom_object,
                    group, version, namespace, plural,
                    label_selector=label_selector,
                    field_selector=field_selector,
                    limit=limit
                )
            else:
                response = await self._retry_request(
                    self._custom_objects.list_cluster_custom_object,
                    group, version, plural,
                    label_selector=label_selector,
                    field_selector=field_selector,
                    limit=limit
                )

            return response

        except Exception as e:
            if isinstance(e, (K8sPermissionError, K8sConnectionError)):
                raise
            raise K8sConnectionError(f"Failed to list resources {kind}: {e}") from e

    async def resolve_reference(
        self,
        ref: dict[str, Any],
        source_namespace: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a Kubernetes object reference.
        
        Args:
            ref: Reference object with apiVersion, kind, name, and optionally namespace
            source_namespace: Namespace of the source resource (for same-namespace refs)
            
        Returns:
            Resolved resource dictionary
            
        Raises:
            K8sResourceNotFoundError: If referenced resource not found
            K8sPermissionError: If insufficient permissions
            K8sConnectionError: If connection fails
        """
        api_version = ref.get("apiVersion")
        kind = ref.get("kind")
        name = ref.get("name")
        namespace = ref.get("namespace", source_namespace)

        if not all([api_version, kind, name]):
            raise ValueError("Reference must contain apiVersion, kind, and name")

        return await self.get_resource(api_version, kind, name, namespace)

    def _get_plural_form(self, kind: str) -> str:
        """Get plural form of a Kubernetes resource kind.
        
        This is a simplified implementation. In production, you would
        query the API server for the correct plural form.
        """
        # Common irregular plurals
        irregular = {
            "Endpoints": "endpoints",
            "NetworkPolicy": "networkpolicies",
            "PodSecurityPolicy": "podsecuritypolicies",
        }

        if kind in irregular:
            return irregular[kind]

        # Simple pluralization rules
        kind_lower = kind.lower()
        if kind_lower.endswith("s"):
            return kind_lower + "es"
        elif kind_lower.endswith("y"):
            return kind_lower[:-1] + "ies"
        else:
            return kind_lower + "s"

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[K8sClient, None]:
        """Context manager for managing Kubernetes connections."""
        try:
            await self.connect()
            yield self
        finally:
            await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to Kubernetes cluster."""
        return self._connected
