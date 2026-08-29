"""Context cleaning, tool output deduplication, and prompt cache optimization for LLM payloads."""

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ContextCleaner:
    """Cleans JSON LLM payloads by deduplicating tool outputs, summarizing history,

    and inserting prompt cache control breakpoints for Anthropic API schemas.
    """

    def __init__(
        self,
        enable_deduplication: bool = True,
        enable_prompt_caching: bool = True,
        max_turns: int = 30,
    ):
        self.enable_deduplication = enable_deduplication
        self.enable_prompt_caching = enable_prompt_caching
        self.max_turns = max_turns
        self.seen_content_hashes: dict[str, tuple[int, str]] = {}  # hash -> (turn_index, resource_name)

    def process_payload(self, payload: dict[str, Any], provider: str = "anthropic") -> dict[str, Any]:
        """Processes and optimizes an outgoing LLM JSON request payload.

        Args:
            payload: Parsed JSON payload dictionary.
            provider: Provider format ('anthropic', 'openai', or 'gemini').

        Returns:
            dict[str, Any]: Optimized JSON payload dictionary.
        """
        self.seen_content_hashes = {}
        cleaned_payload = json.loads(json.dumps(payload))  # deep copy

        if provider == "anthropic":
            cleaned_payload = self._clean_anthropic(cleaned_payload)
        elif provider == "openai":
            cleaned_payload = self._clean_openai(cleaned_payload)
        elif provider == "gemini":
            cleaned_payload = self._clean_gemini(cleaned_payload)

        return cleaned_payload

    def _clean_anthropic(self, payload: dict[str, Any]) -> dict[str, Any]:
        messages = payload.get("messages", [])
        if not isinstance(messages, list):
            return payload

        # 1. Deduplicate tool outputs in history turns
        if self.enable_deduplication:
            messages = self._deduplicate_anthropic_tool_outputs(messages)

        # 2. History summarization if message turns exceed max_turns
        if len(messages) > self.max_turns:
            messages = self._summarize_anthropic_history(messages)
            messages = self._merge_consecutive_roles(messages)

        payload["messages"] = messages

        # 3. Automatic Prompt Cache Breakpoints Insertion for Anthropic
        if self.enable_prompt_caching:
            payload = self._inject_anthropic_cache_control(payload)

        return payload

    def _deduplicate_anthropic_tool_outputs(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned_messages = []
        turn_count = len(messages)

        for turn_idx, msg in enumerate(messages):
            # Only deduplicate in older history turns (leave current turn intact)
            is_older_turn = turn_idx < (turn_count - 2)
            content = msg.get("content")

            if isinstance(content, list):
                cleaned_content = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        tool_out = item.get("content", "")
                        resource_name = item.get("tool_use_id", f"tool_result_{turn_idx}")

                        if isinstance(tool_out, str) and len(tool_out) > 100:
                            content_hash = hashlib.sha256(tool_out.encode("utf-8")).hexdigest()
                            if content_hash in self.seen_content_hashes and is_older_turn:
                                prev_turn, prev_res = self.seen_content_hashes[content_hash]
                                item = dict(item)
                                item["content"] = (
                                    f"[Omitted: Tool result content is identical to Turn {prev_turn} ({prev_res})]"
                                )
                            else:
                                self.seen_content_hashes[content_hash] = (
                                    turn_idx,
                                    resource_name,
                                )

                    cleaned_content.append(item)
                msg["content"] = cleaned_content

            elif isinstance(content, str) and len(content) > 200:
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                if content_hash in self.seen_content_hashes and is_older_turn:
                    prev_turn, prev_res = self.seen_content_hashes[content_hash]
                    msg["content"] = f"[Omitted: Message content is identical to Turn {prev_turn} ({prev_res})]"
                else:
                    self.seen_content_hashes[content_hash] = (turn_idx, f"turn_{turn_idx}")

            cleaned_messages.append(msg)

        return cleaned_messages

    def _is_clean_user_message(self, msg: dict[str, Any], provider: str) -> bool:
        if msg.get("role") != "user":
            return False

        content = msg.get("content")
        if provider == "anthropic":
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        return False
            return True
        elif provider == "openai":
            return True
        return False

    def _summarize_anthropic_history(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        target_idx = len(messages) - 6
        suffix_idx = None
        for i in range(target_idx, 0, -1):
            if self._is_clean_user_message(messages[i], "anthropic"):
                suffix_idx = i
                break
        if suffix_idx is None:
            for i in range(target_idx + 1, len(messages)):
                if self._is_clean_user_message(messages[i], "anthropic"):
                    suffix_idx = i
                    break

        if suffix_idx is None or suffix_idx <= 1:
            return messages

        prefix = messages[:1]
        suffix = messages[suffix_idx:]
        middle = messages[1:suffix_idx]

        summary_text = (
            f"[Summary of omitted {len(middle)} intermediate conversation turns: "
            "Agent performed file reads, search commands, and initial code edits.]"
        )
        summary_msg = {
            "role": "user",
            "content": summary_text,
        }

        return [*prefix, summary_msg, *suffix]


    def _merge_consecutive_roles(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not messages:
            return []
        merged = []
        for msg in messages:
            if not merged:
                merged.append(json.loads(json.dumps(msg)))
                continue
            prev = merged[-1]
            if prev.get("role") == msg.get("role"):
                prev_content = prev.get("content")
                curr_content = msg.get("content")

                if isinstance(prev_content, list) or isinstance(curr_content, list):
                    prev_blocks = []
                    if isinstance(prev_content, list):
                        prev_blocks.extend(prev_content)
                    elif isinstance(prev_content, str):
                        prev_blocks.append({"type": "text", "text": prev_content})

                    curr_blocks = []
                    if isinstance(curr_content, list):
                        curr_blocks.extend(curr_content)
                    elif isinstance(curr_content, str):
                        curr_blocks.append({"type": "text", "text": curr_content})

                    prev["content"] = prev_blocks + curr_blocks
                else:
                    prev["content"] = str(prev_content) + "\n\n" + str(curr_content)
            else:
                merged.append(json.loads(json.dumps(msg)))
        return merged

    def _inject_anthropic_cache_control(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Inject cache_control on system prompt block
        system = payload.get("system")
        if isinstance(system, list) and len(system) > 0:
            last_sys = system[-1]
            if isinstance(last_sys, dict) and "cache_control" not in last_sys:
                last_sys["cache_control"] = {"type": "ephemeral"}
        elif isinstance(system, str):
            payload["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

        # Inject cache_control on tools definition if present
        tools = payload.get("tools")
        if isinstance(tools, list) and len(tools) > 0:
            last_tool = tools[-1]
            if isinstance(last_tool, dict) and "cache_control" not in last_tool:
                last_tool["cache_control"] = {"type": "ephemeral"}

        # Inject cache_control on recent messages history turn
        messages = payload.get("messages", [])
        if len(messages) >= 2:
            target_msg = messages[-2]
            content = target_msg.get("content")
            if isinstance(content, list) and len(content) > 0:
                last_block = content[-1]
                if isinstance(last_block, dict) and "cache_control" not in last_block:
                    last_block["cache_control"] = {"type": "ephemeral"}
            elif isinstance(content, str):
                target_msg["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]

        return payload

    def _clean_openai(self, payload: dict[str, Any]) -> dict[str, Any]:
        messages = payload.get("messages", [])
        if not isinstance(messages, list):
            return payload

        turn_count = len(messages)
        cleaned_messages = []

        for turn_idx, msg in enumerate(messages):
            is_older_turn = turn_idx < (turn_count - 2)
            content = msg.get("content", "")

            if isinstance(content, str) and len(content) > 200:
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                if content_hash in self.seen_content_hashes and is_older_turn:
                    prev_turn, prev_res = self.seen_content_hashes[content_hash]
                    msg["content"] = f"[Omitted: Message content is identical to Turn {prev_turn} ({prev_res})]"
                else:
                    self.seen_content_hashes[content_hash] = (turn_idx, f"turn_{turn_idx}")

            cleaned_messages.append(msg)

        if len(cleaned_messages) > self.max_turns:
            target_idx = len(cleaned_messages) - 6
            suffix_idx = None
            for i in range(target_idx, 0, -1):
                if self._is_clean_user_message(cleaned_messages[i], "openai"):
                    suffix_idx = i
                    break
            if suffix_idx is None:
                for i in range(target_idx + 1, len(cleaned_messages)):
                    if self._is_clean_user_message(cleaned_messages[i], "openai"):
                        suffix_idx = i
                        break

            if suffix_idx is not None and suffix_idx > 1:
                prefix = cleaned_messages[:1]
                suffix = cleaned_messages[suffix_idx:]
                middle_count = len(cleaned_messages) - len(prefix) - len(suffix)
                summary_msg = {
                    "role": "user",
                    "content": f"[Summary of omitted {middle_count} intermediate conversation turns]",
                }
                cleaned_messages = [*prefix, summary_msg, *suffix]

        payload["messages"] = cleaned_messages
        return payload

    def _clean_gemini(self, payload: dict[str, Any]) -> dict[str, Any]:
        contents = payload.get("contents", [])
        if not isinstance(contents, list):
            return payload

        turn_count = len(contents)
        cleaned_contents = []

        for turn_idx, turn in enumerate(contents):
            is_older_turn = turn_idx < (turn_count - 2)
            parts = turn.get("parts", [])
            cleaned_parts = []

            for part in parts:
                text = part.get("text", "")
                if isinstance(text, str) and len(text) > 200:
                    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    if text_hash in self.seen_content_hashes and is_older_turn:
                        prev_turn, prev_res = self.seen_content_hashes[text_hash]
                        part["text"] = f"[Omitted: Content is identical to Turn {prev_turn} ({prev_res})]"
                    else:
                        self.seen_content_hashes[text_hash] = (turn_idx, f"turn_{turn_idx}")

                cleaned_parts.append(part)

            turn["parts"] = cleaned_parts
            cleaned_contents.append(turn)

        payload["contents"] = cleaned_contents
        return payload
