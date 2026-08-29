"""Unit tests for AI Agent Token Reduction Architecture - Phase 1."""

import logging
import os
import stat
import subprocess
from unittest.mock import MagicMock

import pytest
from sandbox_executor import cli
from sandbox_executor.cli import (
    _build_proxy_envs,
    _ca_mount_args,
    _container_ca_path,
    _gateway_host_args,
    _proxy_gateway_url,
    get_token_reduction_mounts_and_envs,
    setup_token_reduction_proxy,
    teardown_token_reduction_proxy,
)
from sandbox_executor.token_reduction.ca_generator import generate_root_ca


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


class FakeDocker:
    """Records docker invocations and replays canned results for the token-reduction flow."""

    def __init__(self, spawn=None, port_stdout="127.0.0.1:32768\n", network_stderr=""):
        self.calls: list[list[str]] = []
        self.spawn = spawn if spawn is not None else _completed(stdout="containerid")
        self.port_stdout = port_stdout
        self.network_stderr = network_stderr

    def __call__(self, cmd, *args, **kwargs):
        self.calls.append(list(cmd))
        head = cmd[:3] if len(cmd) >= 3 else list(cmd)
        if head == ["docker", "network", "create"]:
            return _completed(returncode=1 if self.network_stderr else 0, stderr=self.network_stderr)
        if head == ["docker", "network", "rm"]:
            return _completed()
        if head[:2] == ["docker", "run"]:
            return self.spawn
        if head[:2] == ["docker", "port"]:
            return _completed(stdout=self.port_stdout)
        return _completed()

    def joined(self) -> str:
        return "\n".join(" ".join(call) for call in self.calls)


@pytest.fixture(autouse=True)
def reset_sidecar_state():
    cli._sidecar_state.container_name = None
    cli._sidecar_state.network_name = None
    cli._sidecar_state.network_created = False
    yield
    cli._sidecar_state.container_name = None
    cli._sidecar_state.network_name = None
    cli._sidecar_state.network_created = False


@pytest.fixture
def host_paths(tmp_path, monkeypatch):
    """Keep every host-side write (CA dir, proxy cache) inside tmp_path."""
    monkeypatch.setattr(cli.os.path, "expanduser", lambda path: str(tmp_path / "home" / path.lstrip("~/")))
    monkeypatch.setattr(cli, "generate_root_ca", lambda *a, **k: (str(tmp_path / "holon-root-ca.crt"), ""))
    return tmp_path


# --------------------------------------------------------------------------------------
# ca_generator
# --------------------------------------------------------------------------------------


def test_ca_generator(tmp_path):
    cert_path, key_path = generate_root_ca(cert_dir=str(tmp_path))
    assert os.path.exists(cert_path)
    assert os.path.exists(key_path)
    assert cert_path.endswith("holon-root-ca.crt")
    assert key_path.endswith("holon-root-ca.key")

    # Second call should reuse existing cert
    c2, k2 = generate_root_ca(cert_dir=str(tmp_path))
    assert c2 == cert_path
    assert k2 == key_path


def test_ca_generator_produces_parseable_cert_and_private_key_mode(tmp_path):
    cert_path, key_path = generate_root_ca(cert_dir=str(tmp_path))

    result = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-text"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with open(cert_path) as handle:
        assert "BEGIN CERTIFICATE" in handle.read()

    assert stat.S_IMODE(os.stat(key_path).st_mode) == 0o600


def test_ca_generator_raises_without_openssl(tmp_path, monkeypatch):
    monkeypatch.setattr("sandbox_executor.token_reduction.ca_generator.shutil.which", lambda _: None)

    with pytest.raises(RuntimeError) as excinfo:
        generate_root_ca(cert_dir=str(tmp_path))

    assert "openssl" in str(excinfo.value).lower()
    assert "brew install openssl" in str(excinfo.value)
    # Nothing bogus may be cached when generation never started.
    assert os.listdir(str(tmp_path)) == []


def test_ca_generator_raises_on_openssl_failure_without_caching_junk(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["openssl"], stderr="req failed")

    monkeypatch.setattr("sandbox_executor.token_reduction.ca_generator.subprocess.run", boom)

    with pytest.raises(RuntimeError) as excinfo:
        generate_root_ca(cert_dir=str(tmp_path))

    assert "req failed" in str(excinfo.value)
    assert not os.path.exists(os.path.join(str(tmp_path), "holon-root-ca.crt"))


def test_ca_generator_detects_poisoned_cache(tmp_path):
    cert_path = tmp_path / "holon-root-ca.crt"
    key_path = tmp_path / "holon-root-ca.key"
    cert_path.write_text("-----BEGIN CERTIFICATE-----\nnot a real cert\n-----END CERTIFICATE-----\n")
    key_path.write_text("-----BEGIN PRIVATE KEY-----\nnope\n-----END PRIVATE KEY-----\n")

    with pytest.raises(RuntimeError) as excinfo:
        generate_root_ca(cert_dir=str(tmp_path))

    assert "not a parseable X.509 certificate" in str(excinfo.value)
    assert "Delete" in str(excinfo.value)


# --------------------------------------------------------------------------------------
# setup_token_reduction_proxy
# --------------------------------------------------------------------------------------


def test_setup_proxy_addon_missing_raises_file_not_found(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: False)
    fake = FakeDocker()
    monkeypatch.setattr(cli.subprocess, "run", fake)

    with pytest.raises(FileNotFoundError) as excinfo:
        setup_token_reduction_proxy()

    assert "mitm_addon.py" in str(excinfo.value)
    assert fake.calls == []  # nothing is launched against a non-existent addon


def test_setup_proxy_spawn_failure_raises_and_injects_no_dead_proxy(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
    fake = FakeDocker(spawn=_completed(returncode=125, stderr="docker: error: image not found"))
    monkeypatch.setattr(cli.subprocess, "run", fake)

    with pytest.raises(RuntimeError) as excinfo:
        setup_token_reduction_proxy()

    message = str(excinfo.value)
    assert "image not found" in message
    assert "Re-run without --token-reduce" in message
    # The failed sidecar this run started is cleaned up; no proxy envs are returned.
    assert "docker rm -f" in fake.joined()
    assert "docker network rm" in fake.joined()


def test_setup_proxy_readiness_failure_raises_without_proxy_envs(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: False)
    fake = FakeDocker()
    monkeypatch.setattr(cli.subprocess, "run", fake)

    with pytest.raises(RuntimeError) as excinfo:
        setup_token_reduction_proxy()

    assert "never accepted connections" in str(excinfo.value)
    assert "Re-run without --token-reduce" in str(excinfo.value)
    assert "docker rm -f" in fake.joined()
    assert "docker network rm" in fake.joined()


def test_setup_proxy_missing_published_port_raises(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
    fake = FakeDocker(port_stdout="")
    monkeypatch.setattr(cli.subprocess, "run", fake)

    with pytest.raises(RuntimeError) as excinfo:
        setup_token_reduction_proxy()

    assert "published no host loopback port" in str(excinfo.value)


def test_setup_proxy_success_mounts_only_narrow_ro_cache(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: True)
    fake = FakeDocker()
    monkeypatch.setattr(cli.subprocess, "run", fake)

    mounts, envs = setup_token_reduction_proxy()

    run_cmd = next(call for call in fake.calls if call[:2] == ["docker", "run"])
    joined_run = " ".join(run_cmd)

    # C1: only the narrow proxy cache is shared, read-only; never ~/.holon wholesale.
    assert f"{host_paths / 'home' / '.holon' / 'proxy-cache'}:/home/mitmproxy/.holon/proxy-cache:ro" in joined_run
    assert ":/home/mitmproxy/.holon " not in joined_run
    assert "holon-root-ca.key" not in joined_run

    # I3: containment + streaming posture.
    for flag in ["--memory=256m", "--cpus=0.5", "max-size=5m", "max-file=2", "--restart=no", "stream_large_bodies=1m"]:
        assert flag in joined_run

    # I2: per-run resource names.
    assert "--network" in mounts
    network_name = mounts[mounts.index("--network") + 1]
    assert network_name.startswith("holon-net-")
    assert network_name not in ("holon-net",)
    assert envs["HTTP_PROXY"].startswith(f"http://holon-proxy-{os.getpid()}")
    assert envs["HTTPS_PROXY"] == envs["HTTP_PROXY"]
    assert envs["SSL_CERT_FILE"] == _container_ca_path(str(host_paths / "holon-root-ca.crt"))
    assert cli._sidecar_state.network_created is True


def test_setup_proxy_network_already_exists_is_not_owned(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: True)
    fake = FakeDocker(network_stderr="Error response from daemon: network with name x already exists")
    monkeypatch.setattr(cli.subprocess, "run", fake)

    setup_token_reduction_proxy()

    assert cli._sidecar_state.network_created is False
    teardown_token_reduction_proxy()
    assert "docker network rm" not in fake.joined()
    assert "docker rm -f" in fake.joined()


def test_teardown_is_noop_when_this_run_created_nothing(monkeypatch):
    fake = FakeDocker()
    monkeypatch.setattr(cli.subprocess, "run", fake)

    teardown_token_reduction_proxy()

    assert fake.calls == []


# --------------------------------------------------------------------------------------
# opt-in contract
# --------------------------------------------------------------------------------------


def test_host_proxy_env_alone_never_rewrites_sandbox_networking(monkeypatch):
    monkeypatch.delenv("HOLON_TOKEN_REDUCE", raising=False)
    monkeypatch.setenv("HTTP_PROXY", "http://unrelated-host-proxy:3128")
    monkeypatch.setenv("HTTPS_PROXY", "http://unrelated-host-proxy:3128")

    assert get_token_reduction_mounts_and_envs(token_reduce=False) == ([], {})


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_env_var_opt_in_attempts_configuration(monkeypatch, value):
    monkeypatch.setenv("HOLON_TOKEN_REDUCE", value)
    calls = []
    monkeypatch.setattr(cli, "_attach_external_proxy", lambda: calls.append(True) or (["--network", "x"], {}))

    mounts, envs = get_token_reduction_mounts_and_envs(token_reduce=False)

    assert calls == [True]
    assert mounts == ["--network", "x"]
    assert envs == {}


@pytest.mark.parametrize("value", ["", "0", "false", "off", "http_proxy"])
def test_env_var_opt_in_requires_truthy_value(monkeypatch, value):
    monkeypatch.setenv("HOLON_TOKEN_REDUCE", value)
    monkeypatch.setattr(cli, "_attach_external_proxy", lambda: pytest.fail("must not configure"))

    assert get_token_reduction_mounts_and_envs(token_reduce=False) == ([], {})


def test_env_var_opt_in_unreachable_proxy_degrades_to_direct_egress(host_paths, monkeypatch, caplog):
    monkeypatch.setenv("HOLON_TOKEN_REDUCE", "1")
    monkeypatch.setenv("HOLON_PROXY_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: False)

    with caplog.at_level(logging.ERROR, logger="sandbox_executor.cli"):
        mounts, envs = get_token_reduction_mounts_and_envs(token_reduce=False)

    assert (mounts, envs) == ([], {})
    assert "DIRECT egress" in caplog.text
    assert "127.0.0.1" in caplog.text


def test_flag_opt_in_sidecar_failure_degrades_to_direct_egress(host_paths, monkeypatch, caplog):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: False)

    with caplog.at_level(logging.ERROR, logger="sandbox_executor.cli"):
        mounts, envs = get_token_reduction_mounts_and_envs(token_reduce=True)

    assert (mounts, envs) == ([], {})
    assert "DIRECT egress" in caplog.text
    assert "FileNotFoundError" in caplog.text


# --------------------------------------------------------------------------------------
# platform + de-duplication helpers
# --------------------------------------------------------------------------------------


def test_proxy_gateway_url_is_platform_correct(monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "darwin")
    assert _proxy_gateway_url() == "http://host.docker.internal:8080"
    assert _gateway_host_args() == []

    monkeypatch.setattr(cli.sys, "platform", "linux")
    assert _proxy_gateway_url() == "http://172.17.0.1:8080"
    assert _gateway_host_args() == ["--add-host", "host.docker.internal:host-gateway"]


def test_ca_mount_and_env_helpers_agree():
    host_ca = "/host/.holon/certs/holon-root-ca.crt"
    container_ca = _container_ca_path(host_ca)

    assert _ca_mount_args(host_ca) == ["-v", f"{host_ca}:{container_ca}:ro"]
    envs = _build_proxy_envs(host_ca, "http://holon-proxy-1:8080")
    assert envs["HTTP_PROXY"] == envs["HTTPS_PROXY"] == "http://holon-proxy-1:8080"
    assert envs["NODE_EXTRA_CA_CERTS"] == container_ca
    assert envs["REQUESTS_CA_BUNDLE"] == container_ca
    assert envs["CURL_CA_BUNDLE"] == container_ca
    assert envs["SSL_CERT_FILE"] == container_ca
