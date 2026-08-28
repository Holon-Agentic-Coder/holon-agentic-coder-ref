"""Unit tests for AI Agent Token Reduction Architecture - Phase 1."""

import os
import shutil
import tempfile

import pytest
from sandbox_executor.cli import get_token_reduction_mounts_and_envs
from sandbox_executor.token_reduction.ca_generator import generate_root_ca


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
