"""Disk-backed hybrid & semantic caching layer for LLM prompts."""

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from typing import Any

logger = logging.getLogger(__name__)


class HybridCacheStore:
    """Hybrid exact prefix tree and semantic local cache store for LLM responses."""

    def __init__(self, cache_dir: str | None = None, similarity_threshold: float = 0.85):
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.holon/cache")
        os.makedirs(cache_dir, exist_ok=True)

        self.cache_dir = cache_dir
        self.similarity_threshold = similarity_threshold
        self.db_path = os.path.join(cache_dir, "llm_cache.db")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_cache (
                    key TEXT PRIMARY KEY,
                    provider TEXT,
                    prompt_normalized TEXT,
                    response_json TEXT,
                    created_at REAL,
                    hit_count INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    def generate_prefix_key(self, payload: dict[str, Any], provider: str = "anthropic") -> str:
        """Generates a stable prefix-tree hash key from the payload system and message turns."""
        normalized_str = self.normalize_payload(payload, provider)
        return hashlib.sha256(normalized_str.encode("utf-8")).hexdigest()

    def normalize_payload(self, payload: dict[str, Any], provider: str = "anthropic") -> str:
        """Normalizes payload by stripping transient variables like timestamps, run IDs, and temporary tokens."""
        raw_json = json.dumps(payload, sort_keys=True)
        # Strip ISO timestamps
        norm = re.sub(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?",
            "<TIMESTAMP>",
            raw_json,
        )
        # Strip UUIDs / hexadecimal run hashes
        norm = re.sub(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            "<UUID>",
            norm,
        )
        # Strip random digits in task IDs
        norm = re.sub(r"task-\d+", "task-<ID>", norm)
        return norm

    def get(self, payload: dict[str, Any], provider: str = "anthropic") -> dict[str, Any] | None:
        """Looks up cached response by exact prefix match or semantic similarity match.

        Returns:
            dict[str, Any] | None: Cached response JSON payload if match found, else None.
        """
        prefix_key = self.generate_prefix_key(payload, provider)

        # 1. Exact Prefix Matching
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT response_json, hit_count FROM prompt_cache WHERE key = ?",
                (prefix_key,),
            )
            row = cursor.fetchone()
            if row:
                resp_json, hit_count = row
                cursor.execute(
                    "UPDATE prompt_cache SET hit_count = ? WHERE key = ?",
                    (hit_count + 1, prefix_key),
                )
                conn.commit()
                logger.info("Exact cache hit for key %s", prefix_key[:10])
                return json.loads(resp_json)

        # 2. Semantic Similarity Matching
        target_norm = self.normalize_payload(payload, provider)
        target_tokens = set(re.findall(r"\w+", target_norm.lower()))

        if not target_tokens:
            return None

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, prompt_normalized, response_json, hit_count FROM prompt_cache WHERE provider = ?",
                (provider,),
            )
            rows = cursor.fetchall()

            for key, stored_norm, resp_json, hit_count in rows:
                stored_tokens = set(re.findall(r"\w+", stored_norm.lower()))
                if not stored_tokens:
                    continue

                intersection = len(target_tokens & stored_tokens)
                union = len(target_tokens | stored_tokens)
                similarity = intersection / union if union > 0 else 0.0

                if similarity >= self.similarity_threshold:
                    cursor.execute(
                        "UPDATE prompt_cache SET hit_count = ? WHERE key = ?",
                        (hit_count + 1, key),
                    )
                    conn.commit()
                    logger.info(
                        "Semantic cache hit (similarity=%.2f) for key %s",
                        similarity,
                        key[:10],
                    )
                    return json.loads(resp_json)

        return None

    def put(self, payload: dict[str, Any], response: dict[str, Any], provider: str = "anthropic") -> None:
        """Stores a prompt payload and LLM response in the cache store."""
        prefix_key = self.generate_prefix_key(payload, provider)
        norm_prompt = self.normalize_payload(payload, provider)
        resp_json = json.dumps(response)
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO prompt_cache
                (key, provider, prompt_normalized, response_json, created_at, hit_count)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (prefix_key, provider, norm_prompt, resp_json, now),
            )
            conn.commit()
            logger.info("Stored response in cache for key %s", prefix_key[:10])

    def clear(self) -> None:
        """Clears all entries from the cache store."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM prompt_cache")
            conn.commit()
