"""MITM proxy interceptor & addon for LLM API request optimization and response caching (Phase 3)."""

import json
import logging
import time
from typing import Any
from urllib.parse import urlparse

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
        parse_target = url_lower if "://" in url_lower else f"https://{url_lower}"
        parsed = urlparse(parse_target)
        hostname = parsed.hostname or url_lower

        if "anthropic" in url_lower or "v1/messages" in url_lower:
            return "anthropic"
        if (
            hostname == "generativelanguage.googleapis.com"
            or hostname.endswith(".generativelanguage.googleapis.com")
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


def find_nested_key(data: Any, target_keys: tuple[str, ...] | str, max_depth: int = 10) -> Any:
    """Recursively searches nested dicts/lists to find the first occurrence of any key in target_keys.

    Evaluates target keys at the current nesting level (breadth-first) before recursing deeper into
    child dictionaries or lists. If target_keys is a tuple of key names, keys present at a shallower
    nesting level will take precedence over target keys located deeper in the data structure.
    """
    if max_depth <= 0 or not data:
        return None
    if isinstance(target_keys, str):
        target_keys = (target_keys,)

    if isinstance(data, dict):
        for key in target_keys:
            if key in data and data[key] is not None:
                return data[key]
        for val in data.values():
            if isinstance(val, (dict, list)):
                res = find_nested_key(val, target_keys, max_depth - 1)
                if res is not None:
                    return res
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                res = find_nested_key(item, target_keys, max_depth - 1)
                if res is not None:
                    return res
    return None


def log_telemetry(msg: str) -> None:
    """Logs telemetry message to mitmproxy console context if available, falling back to standard logger."""
    try:
        from mitmproxy import ctx

        if hasattr(ctx, "log") and hasattr(ctx.log, "info"):
            ctx.log.info(msg)
            return
    except Exception:
        # mitmproxy context is unavailable or inactive in this execution context
        pass

    logger.info(msg)


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


def safe_int(val: Any, default: int = 0) -> int:
    """Safely converts val to int, returning default on None or ValueError/TypeError."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def extract_sse_cache_read_tokens(resp_text: str) -> int:
    """Extracts cache_read_input_tokens from Anthropic SSE text if present.

    Delegates to extract_sse_token_counts to ensure single-pass SSE stream line parsing.
    """
    _, _, cache_read_tokens = extract_sse_token_counts(resp_text, {}, "anthropic")
    return cache_read_tokens


def extract_sse_token_counts(resp_text: str, req_data: dict[str, Any], provider: str) -> tuple[int, int, int]:
    """Extracts (input_tokens, output_tokens, cache_read_tokens) from SSE stream text."""
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0

    # Track parsed metrics
    input_tokens_parsed = None
    output_tokens_parsed = None
    cache_read_tokens_parsed = None
    accumulated_content_len = 0

    # We split the stream by lines.
    lines = resp_text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Strip "data:" prefix if present
        json_str = line
        if line.startswith("data:"):
            json_str = line[5:].strip()

        if not json_str or json_str == "[DONE]":
            continue

        try:
            chunk = json.loads(json_str)
        except Exception:
            continue

        if not isinstance(chunk, dict):
            continue

        if provider == "anthropic":
            # Anthropic SSE format
            event_type = find_nested_key(chunk, ("type",))
            if event_type == "message_start":
                message = find_nested_key(chunk, ("message",)) or {}
                usage = find_nested_key(message, ("usage",)) or {}
                if "cache_read_input_tokens" in usage:
                    cache_read_tokens_parsed = safe_int(usage.get("cache_read_input_tokens"))
                if "input_tokens" in usage:
                    input_tokens_parsed = (
                        safe_int(usage.get("input_tokens"))
                        + safe_int(usage.get("cache_read_input_tokens"))
                        + safe_int(usage.get("cache_creation_input_tokens"))
                    )
            elif event_type == "message_delta":
                usage = find_nested_key(chunk, ("usage",)) or {}
                if "output_tokens" in usage:
                    output_tokens_parsed = safe_int(usage.get("output_tokens"))
            elif event_type == "content_block_delta":
                delta = find_nested_key(chunk, ("delta",)) or {}
                text = delta.get("text", "")
                if text:
                    accumulated_content_len += len(text)

        elif provider == "openai":
            # OpenAI SSE format
            usage = find_nested_key(chunk, ("usage",))
            if usage and isinstance(usage, dict):
                if "prompt_tokens" in usage:
                    input_tokens_parsed = safe_int(usage.get("prompt_tokens"))
                if "completion_tokens" in usage:
                    output_tokens_parsed = safe_int(usage.get("completion_tokens"))

            choices = find_nested_key(chunk, ("choices",))
            if choices and isinstance(choices, list) and len(choices) > 0:
                first_choice = choices[0]
                if isinstance(first_choice, dict):
                    delta = first_choice.get("delta")
                    if isinstance(delta, dict):
                        content = delta.get("content", "")
                        if isinstance(content, str) and content:
                            accumulated_content_len += len(content)

        elif provider == "gemini":
            # Gemini / Cloud Code PA format
            usage = find_nested_key(chunk, ("usageMetadata", "usage"))
            if usage and isinstance(usage, dict):
                if "promptTokenCount" in usage:
                    input_tokens_parsed = safe_int(usage.get("promptTokenCount"))
                if "candidatesTokenCount" in usage:
                    output_tokens_parsed = safe_int(usage.get("candidatesTokenCount"))

            candidates = find_nested_key(chunk, ("candidates", "choices", "contents"))
            if candidates and isinstance(candidates, list):
                for candidate in candidates:
                    if isinstance(candidate, dict):
                        content = candidate.get("content")
                        if isinstance(content, dict):
                            parts = content.get("parts")
                            if isinstance(parts, list):
                                for part in parts:
                                    if isinstance(part, dict):
                                        text = part.get("text", "")
                                        if isinstance(text, str) and text:
                                            accumulated_content_len += len(text)
                                    elif isinstance(part, str) and part:
                                        accumulated_content_len += len(part)
                        elif isinstance(content, str) and content:
                            accumulated_content_len += len(content)
                    elif isinstance(candidate, str) and candidate:
                        accumulated_content_len += len(candidate)

    # Fallback/estimate calculations
    if input_tokens_parsed is not None:
        input_tokens = input_tokens_parsed
    else:
        input_chars = estimate_chars(req_data)
        input_tokens = max(1, input_chars // 4) if input_chars > 0 else 0

    if output_tokens_parsed is not None:
        output_tokens = output_tokens_parsed
    else:
        output_tokens = max(1, accumulated_content_len // 4) if accumulated_content_len > 0 else 0

    if cache_read_tokens_parsed is not None:
        cache_read_tokens = cache_read_tokens_parsed

    return input_tokens, output_tokens, cache_read_tokens


def extract_token_counts(
    req_data: dict[str, Any], resp_data: dict[str, Any] | str, provider: str
) -> tuple[int, int, int]:
    """Extracts (input_tokens, output_tokens, cache_read_tokens) from request/response data."""
    if isinstance(resp_data, str):
        return extract_sse_token_counts(resp_data, req_data, provider)

    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    parsed = False

    try:
        if isinstance(resp_data, dict):
            if provider == "anthropic":
                usage = resp_data.get("usage") or {}
                if "input_tokens" in usage and "output_tokens" in usage:
                    cache_read_tokens = safe_int(usage.get("cache_read_input_tokens"))
                    input_tokens = (
                        safe_int(usage.get("input_tokens"))
                        + cache_read_tokens
                        + safe_int(usage.get("cache_creation_input_tokens"))
                    )
                    output_tokens = safe_int(usage.get("output_tokens"))
                    parsed = True
            elif provider == "openai":
                usage = resp_data.get("usage") or {}
                if "prompt_tokens" in usage and "completion_tokens" in usage:
                    input_tokens = safe_int(usage.get("prompt_tokens"))
                    output_tokens = safe_int(usage.get("completion_tokens"))
                    parsed = True
            elif provider == "gemini":
                usage = resp_data.get("usageMetadata") or {}
                if "promptTokenCount" in usage and "candidatesTokenCount" in usage:
                    input_tokens = safe_int(usage.get("promptTokenCount"))
                    output_tokens = safe_int(usage.get("candidatesTokenCount"))
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

    return input_tokens, output_tokens, cache_read_tokens


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

                        log_msg = (
                            f"📊 [TELEMETRY] Provider: {provider.upper()} | "
                            f"Cache: HIT (Hit Rate: {hit_rate * 100:.1f}%) | "
                            f"TTFT: 0.00ms | Prefill: 0.00 t/s | Output: 0.00 t/s | "
                            f"Total: 0.00ms"
                        )
                        log_telemetry(log_msg)
            except json.JSONDecodeError as exc:
                logger.debug("Non-JSON request body for endpoint %s: %s", url, exc)
            except Exception:
                logger.exception("Mitmproxy request intercept error for endpoint: %s", url)

    def responseheaders(self, flow: Any) -> None:
        """Mitmproxy response headers callback."""
        if getattr(flow, "provider", "unknown") != "unknown":
            flow.response_headers_time = time.perf_counter()  # float: timestamp from time.perf_counter()
            response = getattr(flow, "response", None)
            if response is not None:
                headers = getattr(response, "headers", None)
                content_type = ""
                if headers:
                    if hasattr(headers, "get"):
                        content_type = headers.get("Content-Type") or headers.get("content-type") or ""
                    elif isinstance(headers, dict):
                        for k, v in headers.items():
                            if k.lower() == "content-type":
                                content_type = v
                                break
                if "text/event-stream" in content_type:
                    flow.sse_chunks = []

                    def sse_stream_wrapper(chunk: bytes) -> bytes:
                        if chunk:
                            flow.sse_chunks.append(chunk)
                        return chunk

                    response.stream = sse_stream_wrapper

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

                sse_chunks = getattr(flow, "sse_chunks", None)
                is_sse = sse_chunks is not None

                if is_sse:
                    resp_data = b"".join(sse_chunks).decode("utf-8", errors="ignore")
                else:
                    resp_text = flow.response.get_text()
                    resp_data = json.loads(resp_text) if resp_text else None

                if req_data is not None and resp_data:
                    # Note: Response caching is explicitly bypassed for SSE streams (is_sse is True)
                    # because streaming responses cannot be served statically from cache, but telemetry
                    # metrics (token counts, TTFT, TPS) are still calculated and logged.
                    if not is_sse:
                        self.interceptor.intercept_response(url, req_data, resp_data, status_code=status_code)

                    # Extract token counts and cache read tokens in a single pass
                    input_tokens, output_tokens, cache_read_tokens = extract_token_counts(req_data, resp_data, provider)

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

                    log_msg = (
                        f"📊 [TELEMETRY] Provider: {provider.upper()} | "
                        f"Cache: MISS (Hit Rate: {hit_rate * 100:.1f}%) | "
                        f"TTFT: {ttft * 1000:.1f}ms | "
                        f"Prefill: {prefill_tps:.2f} t/s ({input_tokens} tok) | "
                        f"Output: {output_tps:.2f} t/s ({output_tokens} tok in {generation_time:.2f}s) | "
                        f"Total: {total_time * 1000:.1f}ms"
                    )
                    log_telemetry(log_msg)
            except json.JSONDecodeError as exc:
                logger.debug("Non-JSON request/response body for endpoint %s: %s", url, exc)
            except Exception:
                logger.exception("Mitmproxy response intercept error for endpoint: %s", url)
        else:
            logger.warning("Skipping caching response with HTTP status code %d for %s", status_code, url)
            start_t = getattr(flow, "request_start_time", None) or time.perf_counter()
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            log_msg = f"⚠️ [TELEMETRY] Provider: {provider.upper()} | Status: {status_code} | Total: {elapsed_ms:.1f}ms"
            log_telemetry(log_msg)


addons = [MitmproxyAddon()]
