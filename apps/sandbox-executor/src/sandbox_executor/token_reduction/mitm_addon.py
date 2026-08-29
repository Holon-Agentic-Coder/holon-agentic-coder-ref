"""MITM proxy interceptor & addon for LLM API request optimization (Phase 2)."""

import json
import logging
import sys
from typing import Any

# Ensure the mounted src directory is in Python path so we can import sandbox_executor
sys.path.insert(0, "/tmp/src")

from sandbox_executor.token_reduction.payload_cleaner import ContextCleaner

logger = logging.getLogger(__name__)


class MITMProxyInterceptor:
    """Interceptor for LLM requests that performs context cleaning,

    deduplication, and prompt cache optimization.
    """

    def __init__(self):
        self.cleaner = ContextCleaner()

    def detect_provider(self, url_or_path: str) -> str:
        """Determines the provider based on target URL or endpoint path."""
        url_lower = url_or_path.lower()
        if "anthropic" in url_lower:
            return "anthropic"
        if "openai" in url_lower:
            return "openai"
        if "googleapis" in url_lower or "gemini" in url_lower:
            return "gemini"
        return "anthropic"

    def intercept_request(self, endpoint: str, request_json: dict[str, Any]) -> dict[str, Any]:
        """Intercepts and cleans an outgoing JSON API request payload.

        Args:
            endpoint: The API endpoint URL or path.
            request_json: Incoming JSON body from agent.

        Returns:
            dict[str, Any]: Cleaned request JSON payload.
        """
        provider = self.detect_provider(endpoint)
        return self.cleaner.process_payload(request_json, provider=provider)


# mitmproxy addon entrypoint compatible function
class MitmproxyAddon:
    """Addon for mitmproxy command line tool."""

    def __init__(self):
        self.interceptor = MITMProxyInterceptor()

    def request(self, flow: Any) -> None:
        """Mitmproxy request callback."""
        url = getattr(flow.request, "pretty_url", "")
        if any(p in url for p in ("anthropic.com", "openai.com", "googleapis.com")):
            try:
                content = flow.request.get_text()
                if content:
                    data = json.loads(content)
                    cleaned_data = self.interceptor.intercept_request(url, data)
                    flow.request.set_text(json.dumps(cleaned_data))
            except Exception as e:
                logger.warning("Mitmproxy request intercept error: %s", e)


addons = [MitmproxyAddon()]
