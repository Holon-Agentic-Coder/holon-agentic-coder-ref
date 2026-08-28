"""MITM proxy interceptor & addon for LLM API request optimization and response caching (Phase 3)."""

import json
import logging
from typing import Any

from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore
from sandbox_executor.token_reduction.payload_cleaner import JSONContextCleaner

logger = logging.getLogger(__name__)


class MITMProxyInterceptor:
    """Interceptor for LLM requests that performs context cleaning,
    deduplication, prompt cache optimization, and local response caching.
    """

    def __init__(self, cache_dir: str | None = None, enable_caching: bool = True):
        self.cleaner = JSONContextCleaner()
        self.cache_store = HybridCacheStore(cache_dir=cache_dir)
        self.enable_caching = enable_caching

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
            cached_response = self.cache_store.get(cleaned_request, provider=provider)
            if cached_response is not None:
                logger.info("Serving response from local cache for endpoint %s", endpoint)
                return cleaned_request, cached_response

        return cleaned_request, None

    def intercept_response(self, endpoint: str, request_json: dict[str, Any], response_json: dict[str, Any]) -> None:
        """Records an LLM response into the local cache.

        Args:
            endpoint: The API endpoint URL or path.
            request_json: Cleaned request JSON payload.
            response_json: Received response JSON from provider API.
        """
        if not self.enable_caching:
            return

        provider = self.detect_provider(endpoint)
        if provider != "unknown":
            self.cache_store.put(request_json, response_json, provider=provider)


# mitmproxy addon entrypoint compatible function
class MitmproxyAddon:
    """Addon for mitmproxy command line tool."""

    def __init__(self):
        self.interceptor = MITMProxyInterceptor()

    def request(self, flow: Any) -> None:
        """Mitmproxy request callback."""
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
                        flow.response = flow.Response.make(200, json.dumps(cached_resp).encode("utf-8"), headers)
            except Exception:
                logger.exception("Mitmproxy request intercept error for endpoint: %s", url)

    def response(self, flow: Any) -> None:
        """Mitmproxy response callback."""
        url = getattr(flow.request, "pretty_url", "")
        provider = self.interceptor.detect_provider(url)
        if provider != "unknown":
            try:
                req_text = flow.request.get_text()
                resp_text = flow.response.get_text()
                if req_text and resp_text:
                    req_data = json.loads(req_text)
                    resp_data = json.loads(resp_text)
                    self.interceptor.intercept_response(url, req_data, resp_data)
            except Exception:
                logger.exception("Mitmproxy response intercept error for endpoint: %s", url)


addons = [MitmproxyAddon()]
