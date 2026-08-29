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
