"""Unit tests for AI Agent Token Reduction Architecture - Phase 1."""

import logging
import os
import stat
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sandbox_executor import cli
from sandbox_executor.cli import (
    CONTAINER_CA_BUNDLE_PATH,
    NO_PROXY_HOSTS,
    _build_proxy_envs,
    _ca_mount_args,
    _container_ca_path,
    _gateway_host_args,
    _proxy_gateway_url,
    get_token_reduction_mounts_and_envs,
    setup_token_reduction_proxy,
    teardown_token_reduction_proxy,
)
from sandbox_executor.token_reduction import ca_generator
from sandbox_executor.token_reduction.ca_generator import generate_root_ca

_THIRTY_DAYS_SECONDS = 30 * 24 * 60 * 60


def _read_text(path: str) -> str:
    with open(path) as handle:
        return handle.read()


def _openssl_text(cert_path: str) -> str:
    """Return ``openssl x509 -noout -text`` output for ``cert_path``."""
    result = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-text"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _expires_within(cert_path: str, window_seconds: int = _THIRTY_DAYS_SECONDS) -> bool:
    """True when ``cert_path`` expires inside ``window_seconds`` (openssl -checkend semantics)."""
    result = subprocess.run(
        ["openssl", "x509", "-in", cert_path, "-noout", "-checkend", str(window_seconds)], capture_output=True
    )
    assert result.returncode in (0, 1), result
    return result.returncode == 1


def _make_ca_with_validity(cert_dir, days: int) -> tuple[str, str]:
    """Write a throwaway CA pair valid for ``days`` at the cached-CA filenames."""
    cert_path = cert_dir / "holon-root-ca.crt"
    key_path = cert_dir / "holon-root-ca.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            str(days),
            "-nodes",
            "-subj",
            "/CN=Holon Agent Root CA/O=Holon Agentic Coder",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
        ],
        check=True,
        capture_output=True,
    )
    return str(cert_path), str(key_path)


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
    """Keep every host-side write (CA dir, proxy cache) inside tmp_path and hand out a real CA."""
    monkeypatch.setattr(cli.os.path, "expanduser", lambda path: str(tmp_path / "home" / path.lstrip("~/")))
    ca_dir = tmp_path / "certs"
    monkeypatch.setattr(cli, "generate_root_ca", lambda *a, **k: generate_root_ca(cert_dir=str(ca_dir)))
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


def test_ca_generator_emits_ca_key_usage_basic_constraints_and_validity(tmp_path):
    """A CA without keyUsage is refused as a trust anchor by BoringSSL/Node, Go and strict OpenSSL."""
    cert_path, _ = generate_root_ca(cert_dir=str(tmp_path))
    text = _openssl_text(cert_path)

    assert "X509v3 Basic Constraints: critical" in text
    assert "CA:TRUE" in text
    assert "X509v3 Key Usage: critical" in text
    assert "Certificate Sign" in text
    assert "CRL Sign" in text
    assert "X509v3 Subject Key Identifier" in text
    # Not expiring inside the 30 day renewal window.
    assert _expires_within(cert_path) is False


def test_ca_generator_reuses_a_valid_cached_ca(tmp_path):
    cert_path, _ = generate_root_ca(cert_dir=str(tmp_path))
    cached_pem = _read_text(cert_path)

    cert_path_2, key_path_2 = generate_root_ca(cert_dir=str(tmp_path))

    assert cert_path_2 == cert_path
    assert _read_text(cert_path_2) == cached_pem
    assert stat.S_IMODE(os.stat(key_path_2).st_mode) == 0o600


def test_ca_generator_regenerates_near_expiry_cached_ca(tmp_path):
    """`openssl x509 -noout` exits 0 for expired certs, so expiry needs its own check + rotation."""
    cert_path, key_path = _make_ca_with_validity(tmp_path, days=5)
    stale_pem = _read_text(cert_path)
    assert _expires_within(cert_path) is True

    new_cert_path, new_key_path = generate_root_ca(cert_dir=str(tmp_path))

    assert new_cert_path == cert_path
    assert new_key_path == key_path
    assert _read_text(cert_path) != stale_pem
    assert _expires_within(cert_path) is False
    text = _openssl_text(cert_path)
    assert "X509v3 Key Usage: critical" in text
    assert "CA:TRUE" in text
    assert stat.S_IMODE(os.stat(key_path).st_mode) == 0o600


def test_ca_generator_raises_without_openssl(tmp_path, monkeypatch):
    monkeypatch.setattr(ca_generator, "shutil", SimpleNamespace(which=lambda _: None))

    with pytest.raises(RuntimeError) as excinfo:
        generate_root_ca(cert_dir=str(tmp_path))

    assert "openssl" in str(excinfo.value).lower()
    assert "brew install openssl" in str(excinfo.value)
    # Nothing bogus may be cached when generation never started.
    assert os.listdir(str(tmp_path)) == []


def test_ca_generator_raises_on_openssl_failure_without_caching_junk(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["openssl"], stderr="req failed")

    monkeypatch.setattr(
        ca_generator,
        "subprocess",
        SimpleNamespace(
            run=boom,
            CalledProcessError=subprocess.CalledProcessError,
            TimeoutExpired=subprocess.TimeoutExpired,
        ),
    )

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
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=fake))

    with pytest.raises(FileNotFoundError) as excinfo:
        setup_token_reduction_proxy()

    assert "mitm_addon.py" in str(excinfo.value)
    assert fake.calls == []  # nothing is launched against a non-existent addon


def test_setup_proxy_spawn_failure_raises_and_injects_no_dead_proxy(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
    fake = FakeDocker(spawn=_completed(returncode=125, stderr="docker: error: image not found"))
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=fake))

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
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=fake))

    with pytest.raises(RuntimeError) as excinfo:
        setup_token_reduction_proxy()

    assert "never accepted connections" in str(excinfo.value)
    assert "Re-run without --token-reduce" in str(excinfo.value)
    assert "docker rm -f" in fake.joined()
    assert "docker network rm" in fake.joined()


def test_setup_proxy_missing_published_port_raises(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
    fake = FakeDocker(port_stdout="")
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=fake))

    with pytest.raises(RuntimeError) as excinfo:
        setup_token_reduction_proxy()

    assert "published no host loopback port" in str(excinfo.value)


def test_setup_proxy_success_mounts_only_narrow_ro_cache(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: True)
    fake = FakeDocker()
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=fake))

    mounts, envs = setup_token_reduction_proxy()

    run_cmd = next(call for call in fake.calls if call[:2] == ["docker", "run"])
    joined_run = " ".join(run_cmd)

    # C1: only the narrow proxy cache is shared, read-only; never ~/.holon wholesale.
    assert f"{host_paths / 'home' / '.holon' / 'proxy-cache'}:/home/mitmproxy/.holon/proxy-cache:ro" in joined_run
    assert ":/home/mitmproxy/.holon " not in joined_run
    assert "holon-root-ca.key" not in joined_run

    # I11: mitmproxy needs the CA private key to sign leaves, so exactly the two files it expects
    # are mounted read-only into /home/mitmproxy/.mitmproxy — never the whole certificate dir.
    proxy_ca_dir = host_paths / "home" / ".holon" / "proxy-ca"
    assert f"{proxy_ca_dir / 'mitmproxy-ca.pem'}:/home/mitmproxy/.mitmproxy/mitmproxy-ca.pem:ro" in joined_run
    assert f"{proxy_ca_dir / 'mitmproxy-ca-cert.pem'}:/home/mitmproxy/.mitmproxy/mitmproxy-ca-cert.pem:ro" in joined_run
    assert f"{proxy_ca_dir}:/home/mitmproxy" not in joined_run
    assert f"{proxy_ca_dir / 'mitmproxy-ca.pem'}:/home/mitmproxy/.mitmproxy:ro" not in joined_run
    combined = (proxy_ca_dir / "mitmproxy-ca.pem").read_text()
    cert_only = (proxy_ca_dir / "mitmproxy-ca-cert.pem").read_text()
    assert "BEGIN PRIVATE KEY" in combined and "BEGIN CERTIFICATE" in combined
    assert "BEGIN PRIVATE KEY" not in cert_only
    assert stat.S_IMODE(os.stat(proxy_ca_dir / "mitmproxy-ca.pem").st_mode) == 0o600
    assert stat.S_IMODE(os.stat(proxy_ca_dir).st_mode) == 0o700

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
    # C6: the trust-store overrides point at the merged bundle, never at the single-cert mount.
    assert envs["SSL_CERT_FILE"] == CONTAINER_CA_BUNDLE_PATH
    assert envs["NODE_EXTRA_CA_CERTS"] == _container_ca_path(str(host_paths / "certs" / "holon-root-ca.crt"))
    assert cli._sidecar_state.network_created is True


def test_setup_proxy_network_already_exists_is_not_owned(host_paths, monkeypatch):
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: True)
    fake = FakeDocker(network_stderr="Error response from daemon: network with name x already exists")
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=fake))

    setup_token_reduction_proxy()

    assert cli._sidecar_state.network_created is False
    teardown_token_reduction_proxy()
    assert "docker network rm" not in fake.joined()
    assert "docker rm -f" in fake.joined()


def test_teardown_is_noop_when_this_run_created_nothing(monkeypatch):
    fake = FakeDocker()
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=fake))

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


def test_attach_external_proxy_probes_before_generating_a_ca(host_paths, monkeypatch):
    """An unreachable proxy must not leave a freshly generated CA behind on a direct-egress run."""
    events: list[str] = []
    monkeypatch.setenv("HOLON_PROXY_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(cli, "generate_root_ca", lambda: events.append("generate") or ("/host/ca.crt", "/host/ca.key"))
    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: events.append("probe") or False)

    assert cli._attach_external_proxy() == ([], {})
    assert events == ["probe"]


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
    assert envs["REQUESTS_CA_BUNDLE"] == CONTAINER_CA_BUNDLE_PATH
    assert envs["CURL_CA_BUNDLE"] == CONTAINER_CA_BUNDLE_PATH
    assert envs["SSL_CERT_FILE"] == CONTAINER_CA_BUNDLE_PATH


def test_build_proxy_envs_never_replaces_the_trust_store_with_the_holon_ca():
    """SSL_CERT_FILE/REQUESTS_CA_BUNDLE replace the store, so they must point at the merged bundle."""
    host_ca = "/host/.holon/certs/holon-root-ca.crt"
    single_cert_mount = _container_ca_path(host_ca)
    envs = _build_proxy_envs(host_ca, "http://holon-proxy-1:8080")

    for name in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        assert envs[name] == CONTAINER_CA_BUNDLE_PATH
        assert envs[name] != single_cert_mount
        assert not envs[name].startswith("/usr/local/share/ca-certificates")

    # NODE_EXTRA_CA_CERTS augments Node's built-in roots, so the single-cert mount is correct there.
    assert envs["NODE_EXTRA_CA_CERTS"] == single_cert_mount


def test_build_proxy_envs_emits_lowercase_proxy_vars_and_no_proxy():
    envs = _build_proxy_envs("/host/.holon/certs/holon-root-ca.crt", "http://holon-proxy-1:8080")

    for name in ("http_proxy", "https_proxy"):
        assert envs[name] == "http://holon-proxy-1:8080"

    assert envs["NO_PROXY"] == NO_PROXY_HOSTS
    assert envs["no_proxy"] == NO_PROXY_HOSTS
    for host in ("localhost", "127.0.0.1", "::1", "169.254.169.254"):
        assert host in envs["NO_PROXY"]
        assert host in envs["no_proxy"]


# --------------------------------------------------------------------------------------
# teardown coverage (I14)
# --------------------------------------------------------------------------------------


def _stub_run_preconditions(monkeypatch, teardowns: list[bool]) -> None:
    """Neutralise host discovery and record teardown calls for run_docker_container tests."""
    monkeypatch.setattr(
        cli, "shutil", SimpleNamespace(which=lambda name: "/usr/bin/docker" if name == "docker" else None)
    )
    monkeypatch.setattr(cli, "find_github_token", lambda: None)
    monkeypatch.setattr(
        cli,
        "get_token_reduction_mounts_and_envs",
        lambda **kwargs: (["--network", "holon-net-x"], {"HTTP_PROXY": "http://holon-proxy-x:8080"}),
    )
    monkeypatch.setattr(cli, "teardown_token_reduction_proxy", lambda: teardowns.append(True))


def test_run_docker_container_tears_down_sidecar_on_early_return(monkeypatch, tmp_path):
    teardowns: list[bool] = []
    _stub_run_preconditions(monkeypatch, teardowns)
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=lambda *a, **k: pytest.fail("docker must not run")))

    rc = cli.run_docker_container(
        "intent-creator", "holon/orchestrator", [], intent_file=str(tmp_path / "missing-intent.json")
    )

    assert rc == 1
    assert teardowns == [True]


def test_run_docker_container_tears_down_sidecar_when_body_raises(monkeypatch):
    teardowns: list[bool] = []
    _stub_run_preconditions(monkeypatch, teardowns)

    def boom(agent_id):
        raise RuntimeError("session mount exploded")

    monkeypatch.setattr(cli, "get_agent_session_mounts", boom)

    with pytest.raises(RuntimeError, match="session mount exploded"):
        cli.run_docker_container("executor", "holon/agent-pi", [], agent_id="pi")

    assert teardowns == [True]


def test_run_docker_container_tears_down_sidecar_after_the_run(monkeypatch):
    teardowns: list[bool] = []
    _stub_run_preconditions(monkeypatch, teardowns)
    monkeypatch.setattr(cli, "subprocess", SimpleNamespace(run=lambda *a, **k: _completed(returncode=7)))

    assert cli.run_docker_container("executor", "holon/agent-pi", [], agent_id="pi") == 7
    assert teardowns == [True]


def test_hybrid_cache(tmp_path):
    from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore

    cache = HybridCacheStore(cache_dir=str(tmp_path), similarity_threshold=0.8)

    req_1 = {
        "system": "You are a helpful assistant.",
        "messages": [{"role": "user", "content": "Fix bug in 2026-08-28T18:00:00Z task-1234"}],
    }
    resp_1 = {"result": "Fixed bug in task-1234"}

    cache.put(req_1, resp_1, provider="anthropic")

    # Exact lookup after normalization (timestamp & task ID stripped)
    req_2 = {
        "system": "You are a helpful assistant.",
        "messages": [{"role": "user", "content": "Fix bug in 2026-08-28T19:30:00Z task-5678"}],
    }
    cached_resp = cache.get(req_2, provider="anthropic")
    assert cached_resp is not None
    assert cached_resp["result"] == "Fixed bug in task-1234"


def test_hybrid_cache_dissimilar_user_prompts(tmp_path):
    from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore

    cache = HybridCacheStore(cache_dir=str(tmp_path), similarity_threshold=0.85)
    sys_prompt = "You are a helpful coding assistant."
    req_1 = {"system": sys_prompt, "messages": [{"role": "user", "content": "Fix bug in authentication module"}]}
    req_2 = {"system": sys_prompt, "messages": [{"role": "user", "content": "Delete production database records"}]}
    cache.put(req_1, {"result": "Bug fixed"}, provider="anthropic")
    assert cache.get(req_2, provider="anthropic") is None


def test_mitm_interceptor(tmp_path):
    from sandbox_executor.token_reduction.mitm_addon import MITMProxyInterceptor

    interceptor = MITMProxyInterceptor(cache_dir=str(tmp_path), enable_caching=True)
    endpoint = "https://api.anthropic.com/v1/messages"

    req_json = {
        "system": "System prompt",
        "messages": [{"role": "user", "content": "Hello LLM"}],
    }

    # Initial request -> Cache miss
    cleaned_req, cached_resp = interceptor.intercept_request(endpoint, req_json)
    assert cached_resp is None
    assert isinstance(cleaned_req["system"], list)

    # Store response
    fake_resp = {"id": "msg_123", "content": [{"type": "text", "text": "Hello human"}]}
    interceptor.intercept_response(endpoint, cleaned_req, fake_resp)

    # Subsequent identical request -> Cache hit
    _, cached_hit = interceptor.intercept_request(endpoint, req_json)
    assert cached_hit is not None
    assert cached_hit["id"] == "msg_123"


def test_mitm_interceptor_caching_disabled(tmp_path):
    from sandbox_executor.token_reduction.mitm_addon import MITMProxyInterceptor

    cache_dir = tmp_path / "should_not_be_created"
    interceptor = MITMProxyInterceptor(cache_dir=str(cache_dir), enable_caching=False)
    assert interceptor._cache_store is None
    assert not cache_dir.exists()

    endpoint = "https://api.anthropic.com/v1/messages"
    req_json = {"system": "System prompt", "messages": [{"role": "user", "content": "Hello LLM"}]}
    _cleaned_req, cached_resp = interceptor.intercept_request(endpoint, req_json)
    assert cached_resp is None
    assert interceptor._cache_store is None
    assert not cache_dir.exists()


def test_mitm_addon_lifecycle_and_hit_count(tmp_path):
    import json
    import sqlite3

    from sandbox_executor.token_reduction.mitm_addon import MitmproxyAddon

    cache_dir = tmp_path / "cache"
    addon = MitmproxyAddon()
    addon.interceptor.cache_dir = str(cache_dir)

    class FakeRequest:
        def __init__(self, url, text):
            self.pretty_url = url
            self._text = text

        def get_text(self):
            return self._text

        def set_text(self, text):
            self._text = text

    class FakeResponse:
        def __init__(self, status_code=200, text=""):
            self.status_code = status_code
            self._text = text

        def get_text(self):
            return self._text

        @classmethod
        def make(cls, status_code, content, headers=None):
            return cls(status_code=status_code, text=content.decode("utf-8") if isinstance(content, bytes) else content)

    class FakeFlow:
        def __init__(self, request, response=None):
            self.request = request
            self.response = response
            self.Response = FakeResponse

    url = "https://api.anthropic.com/v1/messages"
    req_body = json.dumps({"system": "System prompt", "messages": [{"role": "user", "content": "Test mitm flow"}]})

    # Flow 1: Initial request (cache miss) -> backend response -> response callback stores in cache
    flow1 = FakeFlow(FakeRequest(url, req_body), FakeResponse(200, json.dumps({"id": "resp_1"})))
    addon.request(flow1)
    assert getattr(flow1, "is_cached", False) is False

    addon.response(flow1)

    # Check cache table hit_count (should be 0)
    db_path = cache_dir / "llm_cache.db"
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT hit_count FROM prompt_cache").fetchone()
        assert row[0] == 0

    # Flow 2: Subsequent request (cache hit)
    flow2 = FakeFlow(FakeRequest(url, req_body))
    addon.request(flow2)
    assert getattr(flow2, "is_cached", False) is True
    assert flow2.response is not None
    assert json.loads(flow2.response.get_text()) == {"id": "resp_1"}

    # Call response callback on cached flow -> should not re-put or reset hit_count to 0
    addon.response(flow2)

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT hit_count FROM prompt_cache").fetchone()
        assert row[0] == 1


def test_hybrid_cache_atomic_hit_count_and_system_prompt_normalization(tmp_path):
    import sqlite3

    from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore

    cache = HybridCacheStore(cache_dir=str(tmp_path), similarity_threshold=0.8)

    req_1 = {
        "system": "You are assistant at 2026-08-30T00:00:00Z with task-100",
        "messages": [
            {
                "role": "user",
                "content": "word1 word2 word3 word4 word5 word6 word7 word8 word9 test",
            }
        ],
    }
    resp_1 = {"output": "Refactored auth"}
    cache.put(req_1, resp_1, provider="anthropic")

    # 1. Exact match (with normalized timestamps/task IDs)
    req_exact = {
        "system": "You are assistant at 2026-08-30T01:00:00Z with task-200",
        "messages": [
            {
                "role": "user",
                "content": "word1 word2 word3 word4 word5 word6 word7 word8 word9 test",
            }
        ],
    }
    resp = cache.get(req_exact, provider="anthropic")
    assert resp == resp_1

    # 2. Semantic match with transient tokens in system prompt (9 shared out of 11 union = 0.818 >= 0.8)
    req_semantic = {
        "system": "You are assistant at 2026-08-30T02:00:00Z with task-300",
        "messages": [
            {
                "role": "user",
                "content": "word1 word2 word3 word4 word5 word6 word7 word8 word9 check",
            }
        ],
    }
    resp_sem = cache.get(req_semantic, provider="anthropic")
    assert resp_sem == resp_1

    # Verify hit_count incremented to 2 (1 exact hit + 1 semantic hit)
    db_path = tmp_path / "llm_cache.db"
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT hit_count FROM prompt_cache").fetchone()
        assert row[0] == 2


def test_hybrid_cache_openai_system_prompt_isolation(tmp_path):
    from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore

    cache = HybridCacheStore(cache_dir=str(tmp_path), similarity_threshold=0.8)

    stored_openai_req = {
        "messages": [
            {"role": "system", "content": "You are a specialized code review bot."},
            {"role": "user", "content": "Analyze performance and optimization of database queries in repository"},
        ]
    }
    stored_resp = {"choices": [{"message": {"content": "DB queries look optimized."}}]}

    cache.put(stored_openai_req, stored_resp, provider="openai")

    # 1. Query with different OpenAI system prompt but identical user message -> Cache miss
    diff_sys_req = {
        "messages": [
            {"role": "system", "content": "You are a code formatter bot."},
            {"role": "user", "content": "Analyze performance and optimization of database queries in repository"},
        ]
    }
    assert cache.get(diff_sys_req, provider="openai") is None

    # 2. Query with same OpenAI system prompt and high token overlap user message -> Cache hit
    same_sys_req = {
        "messages": [
            {"role": "system", "content": "You are a specialized code review bot."},
            {"role": "user", "content": "Analyze performance and efficiency of database queries in repository"},
        ]
    }
    hit_resp = cache.get(same_sys_req, provider="openai")
    assert hit_resp is not None
    assert hit_resp["choices"][0]["message"]["content"] == "DB queries look optimized."


def test_mitm_addon_null_response_flow():
    from sandbox_executor.token_reduction.mitm_addon import MitmproxyAddon

    addon = MitmproxyAddon()

    class FakeFlowNullResponse:
        def __init__(self):
            self.request = MagicMock(pretty_url="https://api.openai.com/v1/chat/completions")
            self.response = None
            self.is_cached = False

    flow = FakeFlowNullResponse()
    # Call response on flow with response=None should return cleanly without raising AttributeError
    addon.response(flow)


def test_hybrid_cache_cross_provider_exact_match_isolation(tmp_path):
    from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore

    cache = HybridCacheStore(cache_dir=str(tmp_path), similarity_threshold=0.8)

    payload = {
        "system": "You are a coding assistant.",
        "messages": [{"role": "user", "content": "Write a python function to compute fibonacci numbers."}],
    }
    response = {"content": "def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)"}

    # Store payload under anthropic provider
    cache.put(payload, response, provider="anthropic")

    # Exact lookup for anthropic returns the cached response
    assert cache.get(payload, provider="anthropic") == response

    # Exact lookup for openai with identical payload returns None due to provider isolation
    assert cache.get(payload, provider="openai") is None


def test_mitm_addon_null_request_flow():
    from sandbox_executor.token_reduction.mitm_addon import MitmproxyAddon

    addon = MitmproxyAddon()

    class FakeFlowNullRequest:
        def __init__(self):
            self.request = None
            self.response = None
            self.is_cached = False

    flow = FakeFlowNullRequest()
    # Call request and response callbacks on flow with request=None should return cleanly
    addon.request(flow)
    addon.response(flow)


def test_mitm_addon_error_response_caching_bypass(tmp_path):
    import json

    from sandbox_executor.token_reduction.mitm_addon import MitmproxyAddon, MITMProxyInterceptor

    cache_dir = tmp_path / "cache"
    interceptor = MITMProxyInterceptor(cache_dir=str(cache_dir), enable_caching=True)
    endpoint = "https://api.anthropic.com/v1/messages"
    req_json = {"system": "System prompt", "messages": [{"role": "user", "content": "Trigger error test"}]}

    # 1. Non-200 HTTP status code should NOT be stored by intercept_response
    err_resp_500 = {"error": {"type": "api_error", "message": "Internal Server Error"}}
    interceptor.intercept_response(endpoint, req_json, err_resp_500, status_code=500)
    _, cached_500 = interceptor.intercept_request(endpoint, req_json)
    assert cached_500 is None

    # 2. HTTP 200 with top-level "error" payload should NOT be stored
    err_resp_200 = {"error": {"type": "rate_limit_error", "message": "Rate limit exceeded"}}
    interceptor.intercept_response(endpoint, req_json, err_resp_200, status_code=200)
    _, cached_200 = interceptor.intercept_request(endpoint, req_json)
    assert cached_200 is None

    # 3. HTTP 200 with type == "error" payload should NOT be stored
    type_err_resp = {"type": "error", "error": {"type": "invalid_request_error", "message": "Bad request"}}
    interceptor.intercept_response(endpoint, req_json, type_err_resp, status_code=200)
    _, cached_type_err = interceptor.intercept_request(endpoint, req_json)
    assert cached_type_err is None

    # 4. Test MitmproxyAddon callback skips non-200 flow
    addon = MitmproxyAddon()
    addon.interceptor.cache_dir = str(cache_dir)

    class FakeRequest:
        pretty_url = endpoint

        def get_text(self):
            return json.dumps(req_json)

    class FakeResponse:
        status_code = 429

        def get_text(self):
            return json.dumps({"error": "Rate limit exceeded"})

    class FakeFlow:
        request = FakeRequest()
        response = FakeResponse()

    flow = FakeFlow()
    addon.response(flow)
    _, cached_flow = interceptor.intercept_request(endpoint, req_json)
    assert cached_flow is None


def test_hybrid_cache_anthropic_tool_result_content_block_extraction(tmp_path):
    from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore

    cache = HybridCacheStore(cache_dir=str(tmp_path), similarity_threshold=0.8)
    sys_prompt = "You are a coding assistant with tool support."

    req_1 = {
        "system": sys_prompt,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_123",
                        "content": [
                            {
                                "type": "text",
                                "text": ("Successfully compiled binary target main without any compilation warnings"),
                            }
                        ],
                    }
                ],
            }
        ],
    }
    resp_1 = {"content": [{"type": "text", "text": "Compilation completed successfully."}]}
    cache.put(req_1, resp_1, provider="anthropic")

    # Query with semantically similar tool_result text content
    req_2 = {
        "system": sys_prompt,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_456",
                        "content": "Successfully compiled binary target main without any build warnings",
                    }
                ],
            }
        ],
    }
    cached = cache.get(req_2, provider="anthropic")
    assert cached is not None
    assert cached["content"][0]["text"] == "Compilation completed successfully."


def test_hybrid_cache_multi_turn_recent_instruction_semantic_matching(tmp_path):
    from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore

    cache = HybridCacheStore(cache_dir=str(tmp_path), similarity_threshold=0.85)
    sys_prompt = "You are a coding agent working on repo refactoring."

    # Turn 9 in a long conversation history (turns 1..8 share setup words)
    long_history_turn9 = [
        {"role": "user", "content": "Turn 1: Initialize project setup and environment verification"},
        {"role": "assistant", "content": "Turn 1 done"},
        {"role": "user", "content": "Turn 2: Read directory structure and source files"},
        {"role": "assistant", "content": "Turn 2 done"},
        {"role": "user", "content": "Turn 3: Run preliminary linter and static check"},
        {"role": "assistant", "content": "Turn 3 done"},
        {"role": "user", "content": "Turn 9: Refactor authentication middleware in auth.py"},
    ]
    req_turn9 = {"system": sys_prompt, "messages": long_history_turn9}
    resp_turn9 = {"content": [{"type": "text", "text": "Auth middleware refactored."}]}
    cache.put(req_turn9, resp_turn9, provider="anthropic")

    # Turn 10 with long history (turns 1..9) but a completely DIFFERENT instruction in turn 10:
    long_history_turn10 = [
        *long_history_turn9,
        {"role": "assistant", "content": "Turn 9 done"},
        {"role": "user", "content": "Turn 10: Delete temporary log files from output build directory"},
    ]
    req_turn10_diff = {"system": sys_prompt, "messages": long_history_turn10}

    # Should NOT hit Turn 9 cache entry because Turn 10 instruction is different!
    assert cache.get(req_turn10_diff, provider="anthropic") is None

    # Query Turn 10 with semantically SIMILAR instruction for turn 10:
    long_history_turn10_similar = [
        *long_history_turn9,
        {"role": "assistant", "content": "Turn 9 done"},
        {"role": "user", "content": "Turn 10: Delete temporary log files from build output folder"},
    ]
    req_turn10_sim = {"system": sys_prompt, "messages": long_history_turn10_similar}

    # Put Turn 10 response into cache
    resp_turn10 = {"content": [{"type": "text", "text": "Log files deleted."}]}
    cache.put(req_turn10_diff, resp_turn10, provider="anthropic")

    # Querying with semantically similar turn 10 should hit Turn 10 cache
    cached_turn10 = cache.get(req_turn10_sim, provider="anthropic")
    assert cached_turn10 is not None
    assert cached_turn10["content"][0]["text"] == "Log files deleted."


def test_mitm_addon_response_make_import_fallback(monkeypatch):
    import json

    from sandbox_executor.token_reduction import mitm_addon
    from sandbox_executor.token_reduction.mitm_addon import MitmproxyAddon

    addon = MitmproxyAddon()

    url = "https://api.anthropic.com/v1/messages"
    req_payload = {"system": "Sys", "messages": [{"role": "user", "content": "Hi"}]}
    cached_payload = {"id": "cached_resp_123"}
    monkeypatch.setattr(addon.interceptor, "intercept_request", lambda u, d: (d, cached_payload))

    class MockHttpResponse:
        @classmethod
        def make(cls, status_code, content, headers):
            return {
                "mock_http": True,
                "status_code": status_code,
                "content": json.loads(content.decode("utf-8")),
                "headers": headers,
            }

    class MockHttpModule:
        Response = MockHttpResponse

    monkeypatch.setattr(mitm_addon, "http", MockHttpModule)

    class FakeRequest:
        pretty_url = url

        def get_text(self):
            return json.dumps(req_payload)

        def set_text(self, text):
            pass

    class FakeFlowWithoutResponseAttr:
        request = FakeRequest()
        response = None
        is_cached = False

    flow_a = FakeFlowWithoutResponseAttr()
    addon.request(flow_a)
    assert getattr(flow_a, "is_cached", False) is True
    assert flow_a.response == {
        "mock_http": True,
        "status_code": 200,
        "content": cached_payload,
        "headers": {"Content-Type": "application/json"},
    }

    monkeypatch.setattr(mitm_addon, "http", None)

    class FakeFlowWithResponseAttr:
        request = FakeRequest()
        response = None
        is_cached = False

        class Response:
            @classmethod
            def make(cls, status_code, content, headers):
                return {
                    "mock_flow_response": True,
                    "status_code": status_code,
                    "content": json.loads(content.decode("utf-8")),
                }

    flow_b = FakeFlowWithResponseAttr()
    addon.request(flow_b)
    assert getattr(flow_b, "is_cached", False) is True
    assert flow_b.response == {
        "mock_flow_response": True,
        "status_code": 200,
        "content": cached_payload,
    }


def test_hybrid_cache_put_upsert_preserves_hit_count(tmp_path):
    import sqlite3

    from sandbox_executor.token_reduction.hybrid_cache import HybridCacheStore

    cache = HybridCacheStore(cache_dir=str(tmp_path))
    req = {
        "system": "System prompt",
        "messages": [{"role": "user", "content": "Test hit count preservation"}],
    }
    resp1 = {"output": "Initial response"}
    cache.put(req, resp1, provider="anthropic")

    cache.get(req, provider="anthropic")
    cache.get(req, provider="anthropic")

    db_path = tmp_path / "llm_cache.db"
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT hit_count, response_json FROM prompt_cache").fetchone()
        assert row[0] == 2
        assert "Initial response" in row[1]

    resp2 = {"output": "Updated response"}
    cache.put(req, resp2, provider="anthropic")

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT hit_count, response_json FROM prompt_cache").fetchone()
        assert row[0] == 2
        assert "Updated response" in row[1]


def test_rag_indexer(tmp_path):
    from sandbox_executor.token_reduction.rag_indexer import RAGCodebaseIndexer

    temp_dir = str(tmp_path)
    py_file = os.path.join(temp_dir, "sample.py")
    with open(py_file, "w") as f:
        f.write("class DatabaseConnection:\n    def connect(self):\n        pass\n")

    indexer = RAGCodebaseIndexer(root_dir=temp_dir)

    # Test AST symbol lookup
    syms = indexer.graph_find_symbol("DatabaseConnection")
    assert len(syms) == 1
    assert syms[0]["file"] == "sample.py"
    assert syms[0]["type"] == "class"

    # Test Keyword Search
    results = indexer.semantic_search("connect")
    assert len(results) >= 1
    assert results[0]["file"] == "sample.py"

    # Test Context Bootstrap
    bootstrap = indexer.build_context_bootstrap(query="connect")
    assert "DatabaseConnection" in bootstrap


def test_openbrain_memory(tmp_path):
    from sandbox_executor.token_reduction.openbrain_memory import OpenBrainMemory

    temp_dir = str(tmp_path)
    ob = OpenBrainMemory(db_dir=temp_dir)

    mem_id = ob.store_memory(
        topic="pytest",
        content="Use -m 'not integration_test' for fast unit testing",
        category="lesson_learned",
    )
    assert mem_id > 0

    memories = ob.fetch_memories(topic="pytest")
    assert len(memories) == 1
    assert memories[0]["topic"] == "pytest"

    formatted = ob.format_memory_context(topic="pytest")
    assert "OpenBrain Episodic Memories" in formatted
    assert "not integration_test" in formatted


def test_ringer_orchestrator():
    from sandbox_executor.token_reduction.ringer_orchestrator import RingerOrchestrator

    orchestrator = RingerOrchestrator(architect_model="claude-3-5-sonnet", executor_model="gemini-3.5-flash")

    subtask = orchestrator.plan_subtask(task_id="t1", description="Run linting", commands=["ruff check ."])
    assert subtask["assigned_model"] == "gemini-3.5-flash"

    outcome = orchestrator.record_execution_outcome(
        task_id="t1",
        success=True,
        raw_output="All checks passed!\nLine 2\nLine 3\nLine 4\nLine 5\nDone.",
    )
    assert outcome.success is True
    assert "[Subtask t1 SUCCESS" in outcome.summary

    summary = orchestrator.build_architect_summary()
    assert "Ringer Executor Subtask Results Summary" in summary
    assert "t1" in summary


def test_cli_token_reduction_mounts(monkeypatch, tmp_path):
    temp_dir = str(tmp_path)
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


def test_mitm_addon_telemetry_headers(tmp_path, monkeypatch):
    import json
    from unittest.mock import MagicMock
    from sandbox_executor.token_reduction.mitm_addon import MitmproxyAddon, time

    addon = MitmproxyAddon()
    addon.interceptor.cache_dir = str(tmp_path / "cache")

    class FakeRequest:
        def __init__(self, url, text):
            self.pretty_url = url
            self._text = text

        def get_text(self):
            return self._text

        def set_text(self, text):
            self._text = text

    class FakeResponse:
        def __init__(self, status_code=200, text=""):
            self.status_code = status_code
            self._text = text
            self.headers = {}

        def get_text(self):
            return self._text

        @classmethod
        def make(cls, status_code, content, headers=None):
            resp = cls(status_code=status_code, text=content.decode("utf-8") if isinstance(content, bytes) else content)
            resp.headers = dict(headers) if headers else {}
            return resp

    class FakeFlow:
        def __init__(self, request, response=None):
            self.request = request
            self.response = response
            self.Response = FakeResponse
            self.is_cached = False

    # Mock time.perf_counter to return deterministic timestamps
    timestamps = [10.0, 12.5, 15.0]
    ts_iter = iter(timestamps)
    monkeypatch.setattr(time, "perf_counter", lambda: next(ts_iter))

    # Let's test Anthropic cache miss
    url = "https://api.anthropic.com/v1/messages"
    req_body = {"model": "claude-3-5-sonnet", "messages": [{"role": "user", "content": "Hi LLM"}]}
    resp_body = {
        "content": [{"type": "text", "text": "Hello human"}],
        "usage": {"input_tokens": 100, "output_tokens": 50}
    }

    flow = FakeFlow(
        FakeRequest(url, json.dumps(req_body)),
        FakeResponse(200, json.dumps(resp_body))
    )

    addon.request(flow)
    addon.responseheaders(flow)
    addon.response(flow)

    assert flow.response.headers["X-Holon-Cache-Hit-Rate"] == "0.0000"
    assert flow.response.headers["X-Holon-TTFT"] == "2.5000"
    assert flow.response.headers["X-Holon-Prefill-TPS"] == "40.0000"  # 100 tokens / 2.5s = 40.0
    assert flow.response.headers["X-Holon-Tail-Prefill-TPS"] == "40.0000"
    assert flow.response.headers["X-Holon-Decode-Time"] == "2.5000"
    assert flow.response.headers["X-Holon-Output-TPS"] == "20.0000"   # 50 tokens / 2.5s = 20.0
    assert flow.response.headers["X-Holon-Total-Time"] == "5.0000"

    # Now let's test a Cache Hit flow (which will be the 2nd request)
    ts_iter = iter([20.0, 25.0])
    
    flow_hit = FakeFlow(FakeRequest(url, json.dumps(req_body)))
    addon.request(flow_hit)

    assert flow_hit.is_cached is True
    assert flow_hit.response.headers["X-Holon-Cache-Hit-Rate"] == "0.5000"  # 1 hit / 2 requests
    assert flow_hit.response.headers["X-Holon-TTFT"] == "0.0000"
    assert flow_hit.response.headers["X-Holon-Prefill-TPS"] == "0.0000"
    assert flow_hit.response.headers["X-Holon-Tail-Prefill-TPS"] == "0.0000"
    assert flow_hit.response.headers["X-Holon-Decode-Time"] == "0.0000"
    assert flow_hit.response.headers["X-Holon-Output-TPS"] == "0.0000"
    assert flow_hit.response.headers["X-Holon-Total-Time"] == "0.0000"


def test_mitm_addon_telemetry_providers_and_fallback(tmp_path, monkeypatch):
    import json
    from sandbox_executor.token_reduction.mitm_addon import MitmproxyAddon, time

    addon = MitmproxyAddon()
    addon.interceptor.cache_dir = str(tmp_path / "cache")

    class FakeRequest:
        def __init__(self, url, text):
            self.pretty_url = url
            self._text = text
        def get_text(self):
            return self._text

    class FakeResponse:
        def __init__(self, text):
            self.status_code = 200
            self._text = text
            self.headers = {}
        def get_text(self):
            return self._text

    class FakeFlow:
        def __init__(self, request, response):
            self.request = request
            self.response = response
            self.is_cached = False

    # 1. OpenAI provider check
    ts_iter = iter([10.0, 12.0, 14.0])
    monkeypatch.setattr(time, "perf_counter", lambda: next(ts_iter))

    flow_openai = FakeFlow(
        FakeRequest("https://api.openai.com/v1/chat/completions", json.dumps({"messages": []})),
        FakeResponse(json.dumps({"usage": {"prompt_tokens": 8, "completion_tokens": 6}}))
    )
    addon.request(flow_openai)
    addon.responseheaders(flow_openai)
    addon.response(flow_openai)

    assert flow_openai.response.headers["X-Holon-Prefill-TPS"] == "4.0000"
    assert flow_openai.response.headers["X-Holon-Output-TPS"] == "3.0000"

    # 2. Gemini provider check
    ts_iter = iter([10.0, 12.0, 14.0])
    flow_gemini = FakeFlow(
        FakeRequest("https://generativelanguage.googleapis.com/v1beta/models/gemini", json.dumps({"contents": []})),
        FakeResponse(json.dumps({"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 8}}))
    )
    addon.request(flow_gemini)
    addon.responseheaders(flow_gemini)
    addon.response(flow_gemini)

    assert flow_gemini.response.headers["X-Holon-Prefill-TPS"] == "5.0000"
    assert flow_gemini.response.headers["X-Holon-Output-TPS"] == "4.0000"

    # 3. Fallback character-based estimation check
    ts_iter = iter([10.0, 12.0, 14.0])
    req_body = {"messages": [{"content": "A" * 40}]}
    resp_body = {"choices": [{"message": {"content": "B" * 24}}]}

    flow_fallback = FakeFlow(
        FakeRequest("https://api.openai.com/v1/chat/completions", json.dumps(req_body)),
        FakeResponse(json.dumps(resp_body))
    )
    addon.request(flow_fallback)
    addon.responseheaders(flow_fallback)
    addon.response(flow_fallback)

    assert flow_fallback.response.headers["X-Holon-Prefill-TPS"] == "5.0000"
    assert flow_fallback.response.headers["X-Holon-Output-TPS"] == "3.0000"


def test_estimate_chars_system_and_prompt_keys():
    from sandbox_executor.token_reduction.mitm_addon import estimate_chars

    # Test system key present along with non-target fields
    data_system = {"system": "System instructions here", "custom_meta": "extra metadata"}
    assert estimate_chars(data_system) == len("System instructions here")

    # Test prompt key
    data_prompt = {"prompt": "Hello world prompt"}
    assert estimate_chars(data_prompt) == len("Hello world prompt")


