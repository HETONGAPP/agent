"""
Grafana API Client
Flexible client for Grafana API operations
"""

import logging
from typing import Dict, Any, Optional, List
import os

logger = logging.getLogger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not available, Grafana client will use requests")


class GrafanaClient:
    """
    Flexible Grafana API client
    Supports various Grafana API operations
    """

    def __init__(self, url: str, api_key: str, org_id: Optional[int] = None, timeout: int = 30):
        """
        Initialize Grafana client

        Args:
            url: Grafana base URL (e.g., http://localhost:3000)
            api_key: Grafana API key
            org_id: Optional organization ID
            timeout: Request timeout in seconds
        """
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.org_id = org_id
        self.timeout = timeout

        # Use httpx if available (async), otherwise requests (sync)
        self._use_httpx = HTTPX_AVAILABLE

        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        if org_id:
            self._headers["X-Grafana-Org-Id"] = str(org_id)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request to Grafana API

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (relative to base URL)
            **kwargs: Additional arguments for request

        Returns:
            Response JSON data
        """
        url = f"{self.url}/api/{endpoint.lstrip('/')}"

        if self._use_httpx:
            # Use httpx (sync mode for compatibility)
            import httpx
            with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json() if response.content else {}
        else:
            # Fallback to requests
            import requests
            response = requests.request(
                method, url, headers=self._headers, timeout=self.timeout, **kwargs
            )
            response.raise_for_status()
            return response.json() if response.content else {}

    async def _make_async_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make async HTTP request to Grafana API

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional arguments

        Returns:
            Response JSON data
        """
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx not available, cannot make async requests")

        import httpx
        url = f"{self.url}/api/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}

    def get_datasources(self) -> List[Dict[str, Any]]:
        """Get all data sources"""
        return self._make_request("GET", "datasources")

    def get_dashboards(self) -> List[Dict[str, Any]]:
        """Get all dashboards"""
        return self._make_request("GET", "search?type=dash-db")

    def get_dashboard(self, uid: str) -> Dict[str, Any]:
        """Get dashboard by UID"""
        return self._make_request("GET", f"dashboards/uid/{uid}")

    def create_annotation(
        self,
        text: str,
        tags: Optional[List[str]] = None,
        dashboard_id: Optional[int] = None,
        panel_id: Optional[int] = None,
        time_start: Optional[int] = None,
        time_end: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create annotation in Grafana

        Args:
            text: Annotation text
            tags: Optional tags
            dashboard_id: Optional dashboard ID
            panel_id: Optional panel ID
            time_start: Start time (Unix timestamp in milliseconds)
            time_end: End time (Unix timestamp in milliseconds)
            **kwargs: Additional annotation fields

        Returns:
            Created annotation data
        """
        annotation_data = {
            "text": text,
            "tags": tags or [],
            **kwargs
        }

        if dashboard_id is not None:
            annotation_data["dashboardId"] = dashboard_id
        if panel_id is not None:
            annotation_data["panelId"] = panel_id
        if time_start is not None:
            annotation_data["time"] = time_start
        if time_end is not None:
            annotation_data["timeEnd"] = time_end

        return self._make_request("POST", "annotations", json=annotation_data)

    async def create_annotation_async(
        self,
        text: str,
        tags: Optional[List[str]] = None,
        dashboard_id: Optional[int] = None,
        panel_id: Optional[int] = None,
        time_start: Optional[int] = None,
        time_end: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create annotation asynchronously"""
        annotation_data = {
            "text": text,
            "tags": tags or [],
            **kwargs
        }

        if dashboard_id is not None:
            annotation_data["dashboardId"] = dashboard_id
        if panel_id is not None:
            annotation_data["panelId"] = panel_id
        if time_start is not None:
            annotation_data["time"] = time_start
        if time_end is not None:
            annotation_data["timeEnd"] = time_end

        return await self._make_async_request("POST", "annotations", json=annotation_data)

    def get_annotations(
        self,
        dashboard_id: Optional[int] = None,
        panel_id: Optional[int] = None,
        from_time: Optional[int] = None,
        to_time: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get annotations

        Args:
            dashboard_id: Optional dashboard ID filter
            panel_id: Optional panel ID filter
            from_time: Start time (Unix timestamp in milliseconds)
            to_time: End time (Unix timestamp in milliseconds)
            tags: Optional tags filter

        Returns:
            List of annotations
        """
        params = {}
        if dashboard_id is not None:
            params["dashboardId"] = dashboard_id
        if panel_id is not None:
            params["panelId"] = panel_id
        if from_time is not None:
            params["from"] = from_time
        if to_time is not None:
            params["to"] = to_time
        if tags:
            params["tags"] = ",".join(tags)

        return self._make_request("GET", "annotations", params=params)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "GrafanaClient":
        """
        Create Grafana client from configuration

        Args:
            config: Grafana configuration from app.yaml

        Returns:
            GrafanaClient instance
        """
        url = config.get("url", "http://localhost:3000")
        api_key = config.get("api_key", "")
        # Resolve environment variable references in api_key
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            env_var_name = api_key[2:-1]
            api_key = os.getenv(env_var_name, "")
        if not api_key:
            api_key = os.getenv("GRAFANA_API_KEY", "")
        org_id = config.get("org_id", 1)
        timeout = config.get("timeout", 30)

        return cls(url=url, api_key=api_key, org_id=org_id, timeout=timeout)


