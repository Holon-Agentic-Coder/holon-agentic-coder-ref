"""Unit tests for AI Agent Token Reduction Architecture - Phase 2."""

import os
import shutil
import tempfile

import pytest
from sandbox_executor.cli import get_token_reduction_mounts_and_envs
from sandbox_executor.token_reduction.ca_generator import generate_root_ca
from sandbox_executor.token_reduction.payload_cleaner import ContextCleaner


@pytest.fixture
def temp_dir():
    td = tempfile.mkdtemp()
    yield td
    shutil.rmtree(td, ignore_errors=True)


def test_ca_generator(temp_dir):
    cert_path, key_path = generate_root_ca(cert_dir=temp_dir)
    assert os.path.exists(cert_path)
    assert os.path.exists(key_path)
    assert cert_path.endswith("holon-root-ca.crt")
    assert key_path.endswith("holon-root-ca.key")

    # Second call should reuse existing cert
    c2, k2 = generate_root_ca(cert_dir=temp_dir)
    assert c2 == cert_path
    assert k2 == key_path


def test_cli_token_reduction_mounts(monkeypatch, temp_dir):
    monkeypatch.setattr(
        "sandbox_executor.cli.setup_token_reduction_proxy",
        lambda: (
            ["--network", "holon-net", "-v", f"{temp_dir}/ca.crt:/container/ca.crt:ro"],
            {
                "HTTP_PROXY": "http://holon-proxy:8080",
                "HTTPS_PROXY": "http://holon-proxy:8080",
            },
        ),
    )

    mounts, envs = get_token_reduction_mounts_and_envs(token_reduce=True)
    assert "--network" in mounts
    assert envs["HTTP_PROXY"] == "http://holon-proxy:8080"
    assert envs["HTTPS_PROXY"] == "http://holon-proxy:8080"


def test_payload_cleaner_anthropic_deduplication():
    cleaner = ContextCleaner(enable_deduplication=True, enable_prompt_caching=True)
    long_content = "def test_function():\n" + "    print('hello world')\n" * 10

    messages = [
        {"role": "user", "content": "Read file foo.py"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": long_content,
                }
            ],
        },
        {"role": "user", "content": "Read file foo.py again"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_2",
                    "content": long_content,
                }
            ],
        },
        {"role": "user", "content": "What is next?"},
        {"role": "assistant", "content": "Next step..."},
    ]

    payload = {"system": "System instructions", "messages": messages}
    cleaned = cleaner.process_payload(payload, provider="anthropic")

    # Check deduplication on duplicate turn (index 3)
    omitted_content = cleaned["messages"][3]["content"][0]["content"]
    assert "[Omitted:" in omitted_content

    # Check Anthropic cache control injection
    assert isinstance(cleaned["system"], list)
    assert cleaned["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_payload_cleaner_summarization():
    cleaner = ContextCleaner(max_turns=5)
    # Alternating roles: user, assistant, user, assistant...
    messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}"} for i in range(10)]
    payload = {"messages": messages}
    cleaned = cleaner.process_payload(payload, provider="anthropic")

    # Since prefix (user), summary (user), and suffix[0] (user) are consecutive, they are merged into one user message.
    # The remaining 5 suffix messages alternate. Total length = 6.
    assert len(cleaned["messages"]) == 6
    # The summary content should be merged into the first message's content
    assert "[Summary of omitted" in cleaned["messages"][0]["content"]


def test_mitm_addon_file_exists():
    import sandbox_executor.cli

    addon_dir = os.path.dirname(os.path.abspath(sandbox_executor.cli.__file__))
    addon_path = os.path.join(addon_dir, "token_reduction", "mitm_addon.py")
    assert os.path.exists(addon_path), f"mitm_addon.py does not exist at {addon_path}"


def test_payload_cleaner_anthropic_cache_control_types():
    cleaner = ContextCleaner(enable_prompt_caching=True)

    # Case A: target message is a string
    messages_str = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    payload_str = {"system": "system instruction", "messages": messages_str}
    cleaned_str = cleaner.process_payload(payload_str, provider="anthropic")
    target_msg_str = cleaned_str["messages"][-2]
    assert isinstance(target_msg_str["content"], list)
    assert target_msg_str["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert target_msg_str["content"][0]["text"] == "hello"

    # Case B: target message is a list
    messages_list = [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        {"role": "assistant", "content": "hi"},
    ]
    payload_list = {"system": "system instruction", "messages": messages_list}
    cleaned_list = cleaner.process_payload(payload_list, provider="anthropic")
    target_msg_list = cleaned_list["messages"][-2]
    assert isinstance(target_msg_list["content"], list)
    assert target_msg_list["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_payload_cleaner_seen_hashes_reset():
    cleaner = ContextCleaner(enable_deduplication=True)
    long_content = "def test_function():\n" + "    print('hello world')\n" * 10
    messages = [
        {"role": "user", "content": "Read file foo.py"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": long_content,
                }
            ],
        },
        {"role": "user", "content": "Read file foo.py again"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_2",
                    "content": long_content,
                }
            ],
        },
        {"role": "user", "content": "What is next?"},
        {"role": "assistant", "content": "Next step..."},
    ]
    payload = {"messages": messages}

    # First run
    _cleaned_1 = cleaner.process_payload(payload, provider="anthropic")
    # Second run
    cleaned_2 = cleaner.process_payload(payload, provider="anthropic")

    # The first tool result in cleaned_2 should NOT be omitted because seen_content_hashes was reset
    assert "[Omitted:" not in cleaned_2["messages"][1]["content"][0]["content"]
    assert "[Omitted:" in cleaned_2["messages"][3]["content"][0]["content"]


def test_payload_cleaner_alternating_roles_after_summarization():
    cleaner = ContextCleaner(max_turns=5)
    # 10 user messages. If not merged, we would end up with consecutive user messages.
    messages = [{"role": "user", "content": f"Turn {i}"} for i in range(10)]
    payload = {"messages": messages}
    cleaned = cleaner.process_payload(payload, provider="anthropic")

    # Verify strict role alternation
    for i in range(len(cleaned["messages"]) - 1):
        assert cleaned["messages"][i]["role"] != cleaned["messages"][i + 1]["role"], (
            f"Consecutive roles found at index {i}: "
            f"{cleaned['messages'][i]['role']} and {cleaned['messages'][i + 1]['role']}"
        )


def test_anthropic_history_truncation_boundary():
    cleaner = ContextCleaner(max_turns=6, enable_prompt_caching=False)
    messages = [
        {"role": "user", "content": "Initial prompt"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "foo", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "result1"}]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t2", "name": "bar", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "result2"}]},
        {"role": "assistant", "content": "Let me think"},
        {"role": "user", "content": "A clean user query without tool results"},  # clean boundary!
        {"role": "assistant", "content": "Final response"},
    ]
    payload = {"messages": messages}
    cleaned = cleaner.process_payload(payload, provider="anthropic")
    
    # We should have truncated the middle. Let's make sure it kept the clean boundary and the final message.
    # The output messages: prefix (messages[0]), summary_msg, and suffix (starting at clean boundary).
    # Since prefix (user), summary_msg (user), and suffix[0] (user) are consecutive, they are merged.
    # The clean boundary message content "A clean user query without tool results" should be merged in.
    merged_user_msg = cleaned["messages"][0]
    assert merged_user_msg["role"] == "user"
    assert "A clean user query without tool results" in merged_user_msg["content"]
    assert cleaned["messages"][-1]["content"] == "Final response"


def test_openai_history_truncation_boundary():
    cleaner = ContextCleaner(max_turns=5)
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello 1"},
        {"role": "assistant", "content": "Hi 1"},
        {"role": "user", "content": "Hello 2"},
        {"role": "assistant", "content": "Hi 2"},
        {"role": "user", "content": "Hello 3"},
        {"role": "assistant", "content": "Hi 3"},
        {"role": "user", "content": "Hello 4"},
        {"role": "assistant", "content": "Hi, what tool?"},
        {"role": "tool", "content": "tool output", "tool_call_id": "tc1"},
        {"role": "user", "content": "How about now?"},  # clean boundary!
        {"role": "assistant", "content": "Success!"},
    ]
    payload = {"messages": messages}
    cleaned = cleaner.process_payload(payload, provider="openai")
    
    # Prefix: index 0 (system)
    # Suffix: index 5 onwards (7 messages)
    # Middle: index 1 to 4 (4 messages) replaced by 1 summary message
    # Total messages: 9
    assert len(cleaned["messages"]) == 9
    assert cleaned["messages"][0]["role"] == "system"
    assert "Summary of omitted 4" in cleaned["messages"][1]["content"]
    assert cleaned["messages"][2]["content"] == "Hello 3"
    assert cleaned["messages"][-2]["content"] == "How about now?"
    assert cleaned["messages"][-1]["content"] == "Success!"


def test_mitm_addon_provider_detection_and_unknown_fallback():
    from sandbox_executor.token_reduction.mitm_addon import MITMProxyInterceptor
    
    interceptor = MITMProxyInterceptor()
    
    # Standard endpoints
    assert interceptor.detect_provider("https://api.openai.com/v1/chat/completions") == "openai"
    assert interceptor.detect_provider("https://api.anthropic.com/v1/messages") == "anthropic"
    assert interceptor.detect_provider("https://generativelanguage.googleapis.com/v1beta/models") == "gemini"
    
    # Custom endpoints with standard paths
    assert interceptor.detect_provider("http://localhost:8000/v1/chat/completions") == "openai"
    assert interceptor.detect_provider("http://localhost:8000/v1/messages") == "anthropic"
    
    # Unknown provider URL/path
    assert interceptor.detect_provider("https://example.com/custom/api") == "unknown"
    
    # Intercepting request with unknown provider should leave payload unmodified
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    res = interceptor.intercept_request("https://example.com/custom/api", payload)
    assert res == payload

