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
    messages = [{"role": "user", "content": f"Turn {i}"} for i in range(10)]
    payload = {"messages": messages}
    cleaned = cleaner.process_payload(payload, provider="anthropic")

    assert len(cleaned["messages"]) == 8  # 1 prefix + 1 summary + 6 suffix
    assert "[Summary of omitted" in cleaned["messages"][1]["content"]
