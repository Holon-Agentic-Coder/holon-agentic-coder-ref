"""MITM proxy interceptor & addon for LLM API request optimization and response caching (Phase 3)."""

import json
import logging
import time
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

    def detect_provider(self, url_or_path: str, payload: dict[str, Any] | None = None) -> str:
        """Determines the provider protocol family (anthropic, openai, gemini)
        based on target URL, path, or payload structure.
        """
        url_lower = url_or_path.lower()
        if "anthropic" in url_lower or "v1/messages" in url_lower:
            return "anthropic"
        if (
            "generativelanguage.googleapis.com" in url_lower
            or "gemini" in url_lower
            or "generatecontent" in url_lower
            or "streamgeneratecontent" in url_lower
        ):
            return "gemini"

        openai_providers = [
            "openai",
            "openrouter",
            "deepseek",
            "groq",
            "together",
            "mistral",
            "fireworks",
            "ollama",
            "vllm",
            "lmstudio",
            "chat/completions",
            "v1/completions",
        ]
        if any(p in url_lower for p in openai_providers):
            return "openai"

        if payload and isinstance(payload, dict):
            if "anthropic-version" in payload or "anthropic_version" in payload:
                return "anthropic"
            if "contents" in payload:
                return "gemini"
            if "messages" in payload or "prompt" in payload:
                return "openai"
            if "system" in payload:
                return "anthropic"

        return "unknown"

    def intercept_request(
        self, endpoint: str, request_json: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Intercepts and optimizes an outgoing JSON API request payload.

        Tuple Return Design:
            1. First Element (cleaned_request_json): The cleaned request body (with deduplicated tool
               outputs and cache control breakpoints).
            2. Second Element (cached_response_or_none): The pre-cached LLM response payload served from the
               local SQLite database (llm_cache.db), or None on a cache miss.

        Operational Impact in MitmproxyAddon:
            This allows MitmproxyAddon.request(flow) to short-circuit HTTP network requests directly on cache
            hits without sending outbound traffic to LLM provider endpoints (Anthropic/OpenAI/Gemini).

        Args:
            endpoint: The API endpoint URL or path.
            request_json: Incoming JSON body from agent.

        Returns:
            tuple[dict[str, Any], dict[str, Any] | None]:
                (cleaned_request_json, cached_response_or_none)
        """
        provider = self.detect_provider(endpoint, request_json)
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

        provider = self.detect_provider(endpoint, request_json)
        if provider != "unknown":
            try:
                self.cache_store.put(request_json, response_json, provider=provider)
            except Exception:
                logger.exception("Cache store put failed for endpoint %s.", endpoint)


def estimate_chars(data: Any, max_depth: int = 10) -> int:
    """Recursively estimates prompt/response characters from nested request/response structures.

    Returns 0 for unsupported primitive types or when max_depth is reached.
    """
    if max_depth <= 0:
        return 0
    if isinstance(data, str):
        return len(data)
    if isinstance(data, list):
        return sum(estimate_chars(x, max_depth - 1) for x in data)
    if isinstance(data, dict):
        total = 0
        found_target = False
        if "system" in data:
            total += estimate_chars(data["system"], max_depth - 1)
            found_target = True
        for key in ("messages", "message", "prompt", "contents", "parts", "choices", "candidates", "content", "text"):
            if key in data:
                total += estimate_chars(data[key], max_depth - 1)
                found_target = True
        if found_target:
            return total
        return sum(estimate_chars(v, max_depth - 1) for v in data.values())
    return 0


def extract_token_counts(req_data: dict[str, Any], resp_data: dict[str, Any], provider: str) -> tuple[int, int]:
    """Extracts (input_tokens, output_tokens) from request/response data."""
    input_tokens = 0
    output_tokens = 0
    parsed = False

    try:
        if isinstance(resp_data, dict):
            if provider == "anthropic":
                usage = resp_data.get("usage") or {}
                if "input_tokens" in usage and "output_tokens" in usage:
                    input_tokens = (
                        int(usage["input_tokens"])
                        + int(usage.get("cache_read_input_tokens", 0))
                        + int(usage.get("cache_creation_input_tokens", 0))
                    )
                    output_tokens = int(usage["output_tokens"])
                    parsed = True
            elif provider == "openai":
                usage = resp_data.get("usage") or {}
                if "prompt_tokens" in usage and "completion_tokens" in usage:
                    input_tokens = int(usage["prompt_tokens"])
                    output_tokens = int(usage["completion_tokens"])
                    parsed = True
            elif provider == "gemini":
                usage = resp_data.get("usageMetadata") or {}
                if "promptTokenCount" in usage and "candidatesTokenCount" in usage:
                    input_tokens = int(usage["promptTokenCount"])
                    output_tokens = int(usage["candidatesTokenCount"])
                    parsed = True
    except Exception:
        logger.debug("Failed to parse token counts for provider %s from response; using estimation fallback", provider)

    if not parsed:
        logger.debug(
            "Provider usage dictionary missing or invalid for %s; estimating token counts from payload characters",
            provider,
        )
        input_chars = estimate_chars(req_data)
        output_chars = estimate_chars(resp_data)
        input_tokens = max(1, input_chars // 4) if input_chars > 0 else 0
        output_tokens = max(1, output_chars // 4) if output_chars > 0 else 0

    return input_tokens, output_tokens


# mitmproxy addon entrypoint compatible function
class MitmproxyAddon:
    """Addon for mitmproxy command line tool."""

    def __init__(self):
        self.interceptor = MITMProxyInterceptor()
        self.total_requests = 0
        self.cache_hits = 0

    def request(self, flow: Any) -> None:
        """Mitmproxy request callback."""
        if getattr(flow, "request", None) is None:
            return
        url = getattr(flow.request, "pretty_url", "")
        data = None
        try:
            content = flow.request.get_text()
            if content:
                data = json.loads(content)
        except Exception as exc:
            # Request body is non-JSON or unparseable; proceed with URL-based provider detection
            logger.debug("Non-JSON or unparseable request body for endpoint %s: %s", url, exc)

        provider = self.interceptor.detect_provider(url, data)
        if provider != "unknown":
            flow.provider = provider
            flow.request_start_time = time.perf_counter()  # float: timestamp from time.perf_counter()
            self.total_requests += 1

            try:
                if data is not None:
                    cleaned_data, cached_resp = self.interceptor.intercept_request(url, data)
                    flow.req_data = cleaned_data
                    flow.request.set_text(json.dumps(cleaned_data))

                    if cached_resp:
                        self.cache_hits += 1
                        flow.is_cached = True

                        headers = {"Content-Type": "application/json"}
                        response_cls = (
                            getattr(http, "Response", None)
                            or getattr(flow, "Response", None)
                            or globals().get("Response")
                        )
                        if response_cls and hasattr(response_cls, "make"):
                            flow.response = response_cls.make(200, json.dumps(cached_resp).encode("utf-8"), headers)

                        # Inject telemetry headers on cache hit
                        hit_rate = self.cache_hits / self.total_requests if self.total_requests > 0 else 0.0
                        if getattr(flow, "response", None) is not None:
                            if not hasattr(flow.response, "headers") or flow.response.headers is None:
                                flow.response.headers = {}
                            flow.response.headers["X-Holon-Cache-Hit-Rate"] = f"{hit_rate:.4f}"
                            flow.response.headers["X-Holon-TTFT-Ms"] = "0.00"
                            flow.response.headers["X-Holon-Prefill-TPS"] = "0.0000"
                            flow.response.headers["X-Holon-Tail-Prefill-TPS"] = "0.0000"
                            flow.response.headers["X-Holon-Decode-Time-Sec"] = "0.000"
                            flow.response.headers["X-Holon-Output-TPS"] = "0.0000"
                            flow.response.headers["X-Holon-Total-Time-Ms"] = "0.00"
            except json.JSONDecodeError as exc:
                logger.debug("Non-JSON request body for endpoint %s: %s", url, exc)
            except Exception:
                logger.exception("Mitmproxy request intercept error for endpoint: %s", url)

    def responseheaders(self, flow: Any) -> None:
        """Mitmproxy response headers callback."""
        if getattr(flow, "provider", "unknown") != "unknown":
            flow.response_headers_time = time.perf_counter()  # float: timestamp from time.perf_counter()

    def response(self, flow: Any) -> None:
        """Mitmproxy response callback."""
        if getattr(flow, "request", None) is None or getattr(flow, "response", None) is None:
            return

        provider = getattr(flow, "provider", "unknown")
        if provider == "unknown" or getattr(flow, "is_cached", False):
            return

        url = getattr(flow.request, "pretty_url", "")
        status_code = getattr(flow.response, "status_code", 200)

        if status_code == 200:
            try:
                req_data = getattr(flow, "req_data", None)
                if req_data is None:
                    req_text = flow.request.get_text()
                    if req_text:
                        req_data = json.loads(req_text)
                resp_text = flow.response.get_text()
                if req_data is not None and resp_text:
                    resp_data = json.loads(resp_text)
                    self.interceptor.intercept_response(url, req_data, resp_data, status_code=status_code)

                    # Extract token counts
                    input_tokens, output_tokens = extract_token_counts(req_data, resp_data, provider)

                    # Compute timing metrics
                    req_start = getattr(flow, "request_start_time", None)
                    resp_headers_time = getattr(flow, "response_headers_time", None)

                    now = time.perf_counter()
                    if req_start is None:
                        req_start = now
                    if resp_headers_time is None:
                        resp_headers_time = now

                    ttft = resp_headers_time - req_start
                    total_time = now - req_start
                    generation_time = total_time - ttft

                    cache_read_tokens = (
                        int((resp_data.get("usage") or {}).get("cache_read_input_tokens", 0))
                        if provider == "anthropic" and isinstance(resp_data, dict)
                        else 0
                    )
                    uncached_input_tokens = max(0, input_tokens - cache_read_tokens)
                    prefill_tps = input_tokens / ttft if ttft > 0 else 0.0
                    tail_prefill_tps = uncached_input_tokens / ttft if ttft > 0 else 0.0
                    output_tps = output_tokens / generation_time if generation_time > 0 else 0.0
                    hit_rate = self.cache_hits / self.total_requests if self.total_requests > 0 else 0.0

                    # Inject telemetry headers on cache miss
                    if not hasattr(flow.response, "headers") or flow.response.headers is None:
                        flow.response.headers = {}
                    flow.response.headers["X-Holon-Cache-Hit-Rate"] = f"{hit_rate:.4f}"
                    flow.response.headers["X-Holon-TTFT-Ms"] = f"{ttft * 1000:.2f}"
                    flow.response.headers["X-Holon-Prefill-TPS"] = f"{prefill_tps:.4f}"
                    flow.response.headers["X-Holon-Tail-Prefill-TPS"] = f"{tail_prefill_tps:.4f}"
                    flow.response.headers["X-Holon-Decode-Time-Sec"] = f"{generation_time:.3f}"
                    flow.response.headers["X-Holon-Output-TPS"] = f"{output_tps:.4f}"
                    flow.response.headers["X-Holon-Total-Time-Ms"] = f"{total_time * 1000:.2f}"
            except json.JSONDecodeError as exc:
                logger.debug("Non-JSON request/response body for endpoint %s: %s", url, exc)
            except Exception:
                logger.exception("Mitmproxy response intercept error for endpoint: %s", url)
        else:
            logger.warning("Skipping caching response with HTTP status code %d for %s", status_code, url)


addons = [MitmproxyAddon()]
