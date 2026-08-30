"""MITM proxy interceptor & addon for LLM API request optimization and response caching (Phase 3)."""

import json
import logging
from typing import Any

try:
    from mitmproxy import http
except ImportError:
    http = None

from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore
from sandbox_executor.token_reduction.payload_cleaner import JSONContextCleaner

logger = logging.getLogger(__name__)


class MITMProxyInterceptor:
    """Interceptor for LLM requests that performs context cleaning,
    deduplication, prompt cache optimization, and local response caching.
    """

    def __init__(self, cache_dir: str | None = None, enable_caching: bool = True):
        self.cleaner = JSONContextCleaner()
        self.cache_dir = cache_dir
        self.enable_caching = enable_caching
        self._cache_store: HybridCacheStore | None = None

    @property
    def cache_store(self) -> HybridCacheStore:
        if self._cache_store is None:
            self._cache_store = HybridCacheStore(cache_dir=self.cache_dir)
        return self._cache_store

    def detect_provider(self, url_or_path: str) -> str:
        """Determines the provider based on target URL or endpoint path."""
        url_lower = url_or_path.lower()
        if "anthropic" in url_lower or "v1/messages" in url_lower:
            return "anthropic"
        if "openai" in url_lower or "chat/completions" in url_lower:
            return "openai"
        if "googleapis" in url_lower or "gemini" in url_lower:
            return "gemini"
        return "unknown"

    def intercept_request(
        self, endpoint: str, request_json: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Intercepts an outgoing JSON API request payload.

        Args:
            endpoint: The API endpoint URL or path.
            request_json: Incoming JSON body from agent.

        Returns:
            tuple[dict[str, Any], dict[str, Any] | None]:
                (cleaned_request_json, cached_response_or_none)
        """
        provider = self.detect_provider(endpoint)
        if provider == "unknown":
            logger.warning("Unknown LLM provider for endpoint: %s. Bypassing payload cleaning.", endpoint)
            return request_json, None

        # Step 1: Clean and optimize request payload
        cleaned_request = self.cleaner.process_payload(request_json, provider=provider)

        # Step 2: Check local cache if enabled
        if self.enable_caching:
            try:
                cached_response = self.cache_store.get(cleaned_request, provider=provider)
                if cached_response is not None:
                    logger.info("Serving response from local cache for endpoint %s", endpoint)
                    return cleaned_request, cached_response
            except Exception:
                logger.exception("Cache lookup failed for endpoint %s; bypassing cache.", endpoint)

        return cleaned_request, None

    def intercept_response(
        self,
        endpoint: str,
        request_json: dict[str, Any],
        response_json: dict[str, Any],
        status_code: int = 200,
    ) -> None:
        """Records an LLM response into the local cache.

        Args:
            endpoint: The API endpoint URL or path.
            request_json: Cleaned request JSON payload.
            response_json: Received response JSON from provider API.
            status_code: HTTP status code of the response.
        """
        if not self.enable_caching:
            return

        if status_code != 200:
            logger.warning("Skipping cache put for non-200 HTTP status code (%d) on %s", status_code, endpoint)
            return

        if isinstance(response_json, dict) and ("error" in response_json or response_json.get("type") == "error"):
            logger.warning("Skipping cache put for API error response payload on %s", endpoint)
            return

        provider = self.detect_provider(endpoint)
        if provider != "unknown":
            try:
                self.cache_store.put(request_json, response_json, provider=provider)
            except Exception:
                logger.exception("Cache store put failed for endpoint %s.", endpoint)


# mitmproxy addon entrypoint compatible function
class MitmproxyAddon:
    """Addon for mitmproxy command line tool."""

    def __init__(self):
        self.interceptor = MITMProxyInterceptor()

    def request(self, flow: Any) -> None:
        """Mitmproxy request callback."""
        if getattr(flow, "request", None) is None:
            return
        url = getattr(flow.request, "pretty_url", "")
        provider = self.interceptor.detect_provider(url)
        if provider != "unknown":
            try:
                content = flow.request.get_text()
                if content:
                    data = json.loads(content)
                    cleaned_data, cached_resp = self.interceptor.intercept_request(url, data)
                    flow.request.set_text(json.dumps(cleaned_data))

                    if cached_resp:
                        headers = {"Content-Type": "application/json"}
                        response_cls = (
                            getattr(http, "Response", None)
                            or getattr(flow, "Response", None)
                            or globals().get("Response")
                        )
                        if response_cls and hasattr(response_cls, "make"):
                            flow.response = response_cls.make(200, json.dumps(cached_resp).encode("utf-8"), headers)
                        flow.is_cached = True
            except json.JSONDecodeError as exc:
                logger.debug("Non-JSON request body for endpoint %s: %s", url, exc)
            except Exception:
                logger.exception("Mitmproxy request intercept error for endpoint: %s", url)

    def response(self, flow: Any) -> None:
        """Mitmproxy response callback."""
        if getattr(flow, "request", None) is None or getattr(flow, "response", None) is None:
            return
        url = getattr(flow.request, "pretty_url", "")
        provider = self.interceptor.detect_provider(url)
        status_code = getattr(flow.response, "status_code", 200)
        if provider != "unknown" and not getattr(flow, "is_cached", False):
            if status_code != 200:
                logger.warning("Skipping caching response with HTTP status code %d for %s", status_code, url)
                return
            try:
                req_text = flow.request.get_text()
                resp_text = flow.response.get_text()
                if req_text and resp_text:
                    req_data = json.loads(req_text)
                    resp_data = json.loads(resp_text)
                    self.interceptor.intercept_response(url, req_data, resp_data, status_code=status_code)
            except json.JSONDecodeError as exc:
                logger.debug("Non-JSON request/response body for endpoint %s: %s", url, exc)
            except Exception:
                logger.exception("Mitmproxy response intercept error for endpoint: %s", url)


addons = [MitmproxyAddon()]
