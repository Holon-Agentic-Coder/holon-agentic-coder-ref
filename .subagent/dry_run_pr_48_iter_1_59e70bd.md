# PR Review Report — PR #48 (Dry-Run, Single-Agent Mode)

- **Repo:** `Holon-Agentic-Coder/holon-agentic-coder-ref` · **Base:** `develop`
- **Head commit:** `59e70bd` — `feat(sandbox-executor): implement SSL trust and CA mounts (Phase 1)`
- **Reviewed worktree:** `holon-agentic-coder-ref/I-1787928238-token-reduction-phase1`
- **Mode:** Read-only dry run. No `gh pr review`, no comments posted, no commits, no pushes.

## Empirical Verification Performed (invariant: `empirical_verification`)

Per the `empirical_verification` invariant, every syntax/import/lint claim below was validated by execution rather than
inferred from diff context lines.

| Check                        | Command                                                        | Result                                                                                                                  |
| :--------------------------- | :------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------- |
| Full test suite              | `PYTHONPATH=src python3 -m pytest tests/ -q`                   | ✅ **87 passed, 44 subtests passed**                                                                                    |
| Lint                         | `python3 -m ruff check src tests`                              | ✅ All checks passed                                                                                                    |
| Markdown format              | `npx prettier --check plans/... executions/...`                | ✅ All matched files use Prettier code style                                                                            |
| Import of new package        | `PYTHONPATH=apps/sandbox-executor/src python3 -c "import ..."` | ✅ `generate_root_ca` / `_generate_fallback_cert` import cleanly                                                        |
| Real CA generation           | `generate_root_ca(cert_dir=tmp)` → `openssl x509 -noout -text` | ✅ Valid: `subject=CN=Holon Agent Root CA, O=Holon Agentic Coder`, `notAfter=Aug 29 01:25:11 2027 GMT`, key mode `0600` |
| **Fallback CA generation**   | `_generate_fallback_cert()` → `openssl x509 -noout -text`      | ❌ **`returncode 1` — `Could not find certificate from /tmp/certtest/d.crt`**                                           |
| **Fallback key perms**       | `ls -l` on generated key                                       | ❌ **`-rw-r--r--` (0644, world-readable private key)**                                                                  |
| **`mitm_addon.py` presence** | `find . -name "mitm_addon*" -not -path "*/.git/*"`             | ❌ **No matches anywhere in the repository**                                                                            |
| `NO_PROXY` handling          | `grep -rn "NO_PROXY\|no_proxy" --include=*.py --include=*.sh`  | ❌ **Zero references**                                                                                                  |
| `host.docker.internal`       | `grep -rn "host.docker.internal"`                              | ❌ **Zero references** (only `172.17.0.1`)                                                                              |
| Docs for new flag            | `grep -rn "token-reduce" docs/ README.md`                      | ❌ **Zero references**                                                                                                  |
| Base image trust store       | `grep -n "^FROM" apps/sandbox-executor/Dockerfile`             | `python:3.13-slim` (Debian), `ca-certificates` installed, **no `update-ca-certificates` hook**                          |

> **Note on diff reading:** `apps/sandbox-executor/tests/test_cli.py` lines 128/164 (`token_reduce=False`) are genuine
> additions, and the existing `run_docker_container(...)` assertions were correctly updated. The existing test suite was
> not broken by this change.

---

### 📊 PR Metadata & Role Activation

| Persona                            | Status | Primary Trigger (files/contexts)                                                                              |
| :--------------------------------- | :----: | :------------------------------------------------------------------------------------------------------------ |
| **Engineering & Architecture**     |        |                                                                                                               |
| Principal Engineer                 |   🟢   | `cli.py` (+149), `ca_generator.py` (new), duplicated CA/env construction, broad `except Exception`            |
| Solution Architect                 |   🟢   | New sidecar + user-defined bridge network topology; `mitm_addon.py` inter-component contract is unimplemented |
| Frontend Engineer                  |   ⚪   | No UI, CSS, HTML, or client-side state files changed                                                          |
| QA & Test Engineer                 |   🟢   | `tests/test_token_reduction.py` (new, 47 lines), `tests/test_cli.py`                                          |
| ML & Data Specialist               |   ⚪   | No model, feature, or inference-pipeline code changed                                                         |
| **Product, Design, & Growth**      |        |                                                                                                               |
| Product Owner                      |   🟢   | New opt-in feature flag `--token-reduce`; Phase 1 scope vs. undocumented `elif` behaviour                     |
| UX/UI Designer                     |   ⚪   | No visual/design artifacts changed (CLI help text reviewed under DevRel)                                      |
| SEO & Growth Specialist            |   ⚪   | No public web pages, metadata, or redirect logic changed                                                      |
| **Operations, Release, & Support** |        |                                                                                                               |
| DevOps & SRE                       |   🟢   | `docker run` sidecar lifecycle, pinned `mitmproxy/mitmproxy:12.2.3`, `holon-net`, env injection               |
| Release Manager                    |   🟢   | `holon-knowledge/ledger/*.jsonl`, `plans/…md`, `executions/…md`, phased rollout with default-off flag         |
| Support Engineer                   |   🟢   | Silent `logger.warning` failure paths; operator-facing diagnosability of a broken proxy                       |
| **Security, Compliance, & Risk**   |        |                                                                                                               |
| Security Architect                 |   🟢   | Root CA private key handling, `~/.holon` bind mount, MITM blast radius, invalid fallback cert                 |
| Compliance Auditor                 |   🟢   | `GITHUB_TOKEN` / `HOLON_AGENT_KEY` transiting a decrypting MITM proxy with host-persisted flow logs           |
| Localization Coordinator           |   ⚪   | No user-facing localized strings; CLI help is English-only internal tooling                                   |
| **DevRel & Documentation**         |        |                                                                                                               |
| Technical Writer                   |   🟢   | `docs/sandbox/execute_plan.md` & `create_plan.md` document CLI flags but were not updated                     |
| Developer Advocate                 |   🟢   | Public `holon` CLI surface change (`--token-reduce`), `HOLON_PROXY_URL` contract, onboarding friction         |

---

### 🔍 Persona Reviews

#### 👥 Security Architect Review

- **🔴 CRITICAL — `cli.py:143-157` (`setup_token_reduction_proxy`): Root CA private key and agent session credentials
  are bind-mounted into the MITM sidecar, read-write**
  - **Context**: The sidecar is launched with `-v {holon_home}:/home/mitmproxy/.holon` where `holon_home = ~/.holon`,
    with **no `:ro` suffix**. Two other code paths place highly sensitive material _inside_ that exact subtree:
    - `ca_generator.py:22-24` → `~/.holon/certs/holon-root-ca.key` (the CA **private key**).
    - `cli.py:53-56` (`get_agent_session_mounts`) → `~/.holon/sessions/antigravity`, the interactive agent
      authentication session store.

    The comment claims this mount exists only "to persist cache db", but the mount is a superset of the whole agent
    state directory. Consequence: any RCE or dependency compromise inside `mitmproxy/mitmproxy:12.2.3` (a third-party
    image running a Python addon script) yields the root CA private key — enabling forgery of trusted certificates for
    _every_ future sandbox on this host — plus the agent's live auth session tokens. A read-write mount additionally
    lets the sidecar tamper with host session state.

  - **Recommendation**: Never mount a parent directory of secrets. Mount only the narrow cache path actually required,
    read-only, and keep the CA private key outside any container-visible path. The proxy only needs the **certificate**,
    never the key. Also generate the key with an explicit restrictive mode rather than relying on `openssl`'s default.
  - **Proposed Code Change**:
    ```diff
    -    # We mount ~/.holon folder to persist cache db in /home/mitmproxy/.holon inside container
    -    home_dir = os.path.expanduser("~")
    -    holon_home = os.path.join(home_dir, ".holon")
    -    os.makedirs(holon_home, exist_ok=True)
    +    # Mount ONLY the proxy cache dir (never ~/.holon: it contains the CA private key
    +    # and agent auth session stores). Read-only.
    +    holon_home = os.path.expanduser("~")
    +    proxy_cache = os.path.join(holon_home, ".holon", "proxy-cache")
    +    os.makedirs(proxy_cache, exist_ok=True)
    ...
    -        "-v",
    -        f"{holon_home}:/home/mitmproxy/.holon",
    +        "-v",
    +        f"{proxy_cache}:/home/mitmproxy/.holon/cache:ro",
    ```
    And in `ca_generator.py`, harden key creation and stop returning the key path to callers that only need the cert:
    ```diff
     def _generate_fallback_cert(cert_path: str, key_path: str) -> None:
    -    with open(key_path, "w") as kf:
    +    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    +    with os.fdopen(fd, "w") as kf:
    ```

- **🔴 CRITICAL — `ca_generator.py:55-77`: fallback "certificate" is structurally invalid and is permanently cached, and
  the fallback key is world-readable**
  - **Context**: Empirically confirmed. `_generate_fallback_cert` writes truncated base64 blobs;
    `openssl x509 -in d.crt -noout -text` returns **`1`** with `Could not find certificate`. This is worse than failing
    loudly:
    1. `generate_root_ca()` swallows the real `openssl` error (`except Exception`), logs a `warning`, and **returns
       success**.
    2. `cli.py` then mounts this non-cert into the container trust store and points `SSL_CERT_FILE`,
       `REQUESTS_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS` at it.
    3. Every TLS client in the sandbox now fails with an opaque `unable to load client CA file` / `ERR_SSL_…` instead of
       a clear "openssl is missing" message.
    4. Because of the `if os.path.exists(ca_cert_path) and os.path.exists(ca_key_path)` early-return at line 25, the
       bogus files are **cached forever** — installing `openssl` later does not heal the state; the user must manually
       delete `~/.holon/certs/*`.
    5. The fallback key is written `0644` (verified `-rw-r--r--`).

    This is a fake-success shim that converts a diagnosable environment error into a permanent, self-healing-resistant
    broken state.

  - **Recommendation**: Fail fast and explicitly. Probe for `openssl` with `shutil.which` (which the plan already
    mandated), raise a typed error with an actionable message, and never persist an artifact that cannot be parsed.
    Validate any generated cert before returning it.
  - **Proposed Code Change**:
    ```diff
    -    try:
    -        subprocess.run([...], check=True, capture_output=True, text=True)
    -    except Exception as exc:
    -        logger.warning(
    -            "OpenSSL CA generation failed or openssl not found: %s. Generating fallback cert.",
    -            exc,
    -        )
    -        _generate_fallback_cert(ca_cert_path, ca_key_path)
    +    if shutil.which("openssl") is None:
    +        raise RuntimeError(
    +            "openssl binary not found on host; cannot bootstrap the Holon Root CA. "
    +            "Install OpenSSL (macOS: `brew install openssl`, Debian: `apt-get install openssl`)."
    +        )
    +    try:
    +        subprocess.run([...], check=True, capture_output=True, text=True)
    +    except subprocess.CalledProcessError as exc:
    +        raise RuntimeError(f"openssl CA generation failed: {exc.stderr.strip()}") from exc
    +    except subprocess.TimeoutExpired as exc:
    +        raise RuntimeError("openssl CA generation timed out") from exc
    +    os.chmod(ca_key_path, 0o600)
    +    _assert_valid_cert(ca_cert_path)   # openssl x509 -in <path> -noout
    +    return ca_cert_path, ca_key_path
    ```
    and delete `_generate_fallback_cert` entirely.

- **🟡 IMPORTANT — `cli.py:180-190` + proxy design: agent bearer credentials transit a decrypting MITM whose flow logs
  are persisted to the host**
  - **Context**: `run_docker_container` injects `GITHUB_TOKEN` and `HOLON_AGENT_KEY` into the agent container
    (`cli.py:243-252`), and `--token-reduce` then forces all of that agent's HTTPS through `holon-proxy`, which holds
    the CA key and can therefore decrypt them. The addon is loaded from `/tmp/mitm_addon.py` and the container has a
    host-persisted bind mount, so any `mitmdump` flow saving writes Authorization headers into a host directory. Nothing
    in the diff declares a data-handling posture for that material.
  - **Recommendation**: Make the proxy's non-decrypting/credential-stripping posture explicit and enforced in code, not
    just in the (currently missing) addon: set `--set stream_large_bodies=1m`, `--set connection_strategy=regular`, and
    explicitly drop `Authorization`/`Cookie` from any saved artefact. Document that `--token-reduce` performs TLS
    interception and must only be used against a locally-owned proxy.

---

#### 👥 DevOps & SRE Review

- **🔴 CRITICAL — `cli.py:140,159,166-178`: sidecar is launched against a host addon path that does not exist, and there
  is no readiness verification, so a dead proxy is reported as healthy**
  - **Context**: `find . -name "mitm_addon*"` returns **nothing** — `mitm_addon.py` is not in this PR and not in the
    repo. Two distinct failure modes both end with the sandbox pointed at a proxy that is not listening:
    - **(a) Missing addon (the normal case today).** Docker silently creates a missing bind-mount **source** as an empty
      _directory_. `mitmdump -s /tmp/mitm_addon.py` then fails to load the script and the container exits — but
      `docker run -d` has already returned `0`. The `else` branch is taken, `proxy_url = "http://holon-proxy:8080"` and
      `mounts = ["--network", "holon-net"]` are applied, and every agent HTTPS request now fails with
      `connection refused`. The agent has no direct egress because it was moved onto `holon-net`.
    - **(b) Explicit spawn failure** (`proxy_spawn.returncode != 0`, e.g. image not pullable / offline / daemon down).
      The code sets `proxy_url = "http://172.17.0.1:8080"` and `mounts = []`, but **still injects `HTTP_PROXY` and
      `HTTPS_PROXY` pointing at that dead address**. Nothing is listening on the Docker bridge gateway. Total network
      failure for the agent, with only a `logger.warning` as evidence.

    In both cases the operator's `holon execute --token-reduce` run dies deep inside the agent with confusing
    TLS/connect errors, and the `finally` teardown at line 302-304 then deletes the evidence container.

  - **Recommendation**: Ship `mitm_addon.py` in this PR (or gate the mount on `os.path.exists`). Treat a non-ready proxy
    as a hard error rather than injecting a dead proxy URL. Verify readiness with a real TCP probe before returning
    `proxy_url`, and return empty env vars when the proxy is unavailable.
  - **Proposed Code Change**:
    ```diff
     addon_path = os.path.join(addon_dir, "token_reduction", "mitm_addon.py")
    +if not os.path.isfile(addon_path):
    +    raise FileNotFoundError(f"mitmproxy addon missing at {addon_path}; cannot enable token reduction")
    ...
     if proxy_spawn.returncode != 0:
    -    logger.warning("Failed to start mitmproxy sidecar container: %s", proxy_spawn.stderr)
    -    # Fallback to local default proxy url if sidecar fails
    -    proxy_url = "http://172.17.0.1:8080"
    -    mounts = []
    +    raise RuntimeError(
    +        f"holon-proxy sidecar failed to start: {proxy_spawn.stderr.strip()}. "
    +        "Re-run without --token-reduce to execute with direct egress."
    +    )
    +if not _wait_for_proxy("holon-proxy", 8080, timeout=15.0):
    +    raise RuntimeError("holon-proxy started but never accepted connections on :8080")
     else:
    -    # Wait a moment for proxy to initialize
    -    time.sleep(1.0)
         proxy_url = "http://holon-proxy:8080"
         mounts = ["--network", "holon-net"]
    ```

- **🟡 IMPORTANT — `cli.py:172,214`: `172.17.0.1` is Linux-only and is broken on Docker Desktop for macOS, which this
  file otherwise special-cases**
  - **Context**: `cli.py:49` and `cli.py:70` branch on `sys.platform == "darwin"`, so macOS/Docker Desktop is a
    first-class host. On Docker Desktop the Linux bridge gateway `172.17.0.1` is **not** the host — it is unreachable
    from the VM. Both fallback proxy URLs therefore point into a black hole on the platform most contributors use. There
    is no `host.docker.internal` reference anywhere in the repo (verified by grep).
  - **Recommendation**: Derive the gateway per-platform and add the Linux host-gateway mapping so the same URL works
    everywhere.
  - **Proposed Code Change**:
    ```diff
    -        proxy_url = "http://172.17.0.1:8080"
    +        gateway = "host.docker.internal" if sys.platform in ("darwin", "win32") else "172.17.0.1"
    +        proxy_url = f"http://{gateway}:8080"
    ```
    and add `"--add-host", "host.docker.internal:host-gateway"` to the agent `docker run` on Linux.

- **🟡 IMPORTANT — `cli.py:178,201-204`: hardcoded singleton container/network names make concurrent runs destroy each
  other, and the network is never reclaimed**
  - **Context**: `holon-proxy` and `holon-net` are global fixed names. Step 2 unconditionally runs
    `docker rm -f holon-proxy` at startup, so a second `holon … --token-reduce` in another terminal kills the first
    run's proxy mid-flight. Conversely, the `finally` teardown at line 302-304 deletes a proxy the _other_ run just
    created. `docker network create holon-net` (line 128) has no matching `docker network rm`, so the network leaks; and
    if the CLI is `SIGKILL`ed the `-d` sidecar leaks too (the `finally` block does not run).
  - **Recommendation**: Namespace resources per session and add a stale-resource sweep. At minimum, key the names on the
    PID/session id and clean up the network.
  - **Proposed Code Change**:
    ```diff
    -    subprocess.run(["docker", "rm", "-f", "holon-proxy"], capture_output=True, check=False)
    +    proxy_name = f"holon-proxy-{os.getpid()}"
    +    network_name = "holon-net"
    ```
    plus, in the `finally`:
    ```diff
    -        if token_reduce:
    -            subprocess.run(["docker", "rm", "-f", "holon-proxy"], capture_output=True, check=False)
    +        if token_reduce:
    +            subprocess.run(["docker", "rm", "-f", proxy_name], capture_output=True, check=False)
    +            subprocess.run(
    +                ["docker", "network", "prune", "-f", "--filter", "until=24h"],
    +                capture_output=True, check=False,
    +            )
    ```

- **🟡 IMPORTANT — `cli.py:144-165`: sidecar has no resource limits, no privilege drop, no restart policy, and no log
  bound**
  - **Context**: The `docker run` for `holon-proxy` sets only `--name`, `--network`, and two `-v` flags. It runs the
    upstream image as its default (root) user, unbounded on CPU/memory, with no `--restart` and no `--log-opt max-size`.
    A proxy that buffers large LLM streaming responses is exactly the workload that OOMs the developer host, and an
    unbounded json-file log will grow across long agent sessions.
  - **Recommendation**: Add explicit containment flags to the sidecar invocation.
  - **Proposed Code Change**:
    ```diff
         docker_run_proxy = [
             "docker", "run", "-d",
    +        "--user", "65532:65532",
    +        "--memory", "512m", "--cpus", "1.0",
    +        "--restart", "unless-stopped",
    +        "--log-opt", "max-size=10m", "--log-opt", "max-file=2",
             "--name", "holon-proxy",
    ```

- **🟢 NIT — `cli.py:128`: `docker network create` discards stderr entirely, so "already exists" is indistinguishable
  from a real daemon failure**
  - **Context**: `capture_output=True, check=False` with no inspection of the result. A dead Docker daemon, a name
    conflict with a different driver, or a plugin error all look identical to the expected "network already exists"
    error, and the code proceeds to a confusing later failure.
  - **Recommendation**: Check the return code and only tolerate the specific "already exists" message.
  - **Proposed Code Change**:
    ```diff
    -    subprocess.run(["docker", "network", "create", "holon-net"], capture_output=True, check=False)
    +    net = subprocess.run(
    +        ["docker", "network", "create", "holon-net"], capture_output=True, text=True, check=False
    +    )
    +    if net.returncode != 0 and "already exists" not in net.stderr.lower():
    +        logger.warning("Could not create holon-net: %s", net.stderr.strip())
    ```

- **🟢 NIT — `cli.py:124-126`: `import time` is function-local for no reason**
  - **Context**: `time` is a stdlib module with no cycle risk; the in-function import hides a dependency and adds a
    lookup on every call.
  - **Recommendation**: Move it to the module import block alongside `os`, `shutil`, `subprocess`, `sys`.

---

#### 👥 Solution Architect Review

- **🟡 IMPORTANT — `cli.py:180-190` vs. `ca_generator.py` + `Dockerfile:11`: the CA is mounted into a Debian path that
  is inert without `update-ca-certificates`, so the stated trust contract is only partially honoured**
  - **Context**: The PR description states the cert is mounted into the "sandbox container trust store path
    (`/usr/local/share/ca-certificates/`)". On the actual base image (`python:3.13-slim`, Debian, with `ca-certificates`
    installed), dropping a `.crt` into `/usr/local/share/ca-certificates/` has **no effect** until
    `update-ca-certificates` regenerates `/etc/ssl/certs/ca-certificates.crt`. Nothing in the diff adds that hook. The
    env-var belt (`SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`, `CURL_CA_BUNDLE`) covers Python
    `requests`/`httpx` and Node, but **not** Go-based CLIs (which read only the system pool and ignore all four
    variables), nor `openssl s_client`, nor `git` invocations that resolve the default pool. The result is a
    half-trusted sandbox where some tools work and others fail with `x509: certificate signed by unknown authority`.
  - **Recommendation**: Either (a) point the env vars at a pre-merged bundle and mount to `/etc/ssl/certs/` as well, or
    (b) add an entrypoint pre-step that runs `update-ca-certificates` when the Holon CA is present. Option (b) is the
    durable fix and matches the "trust bootstrap" intent.
  - **Proposed Code Change** (entrypoint pre-step):
    ```diff
    +if [ -f /usr/local/share/ca-certificates/holon-root-ca.crt ]; then
    +    update-ca-certificates >/dev/null 2>&1 || true
    +fi
    ```

- **🟡 IMPORTANT — `cli.py:193-224`: `get_token_reduction_mounts_and_envs` implements two divergent code paths that
  duplicate the same CA/env construction**
  - **Context**: The `if token_reduce:` branch and the `elif os.getenv("HTTP_PROXY")…` branch each independently import
    `generate_root_ca`, recompute `container_cert_path`, re-append the same `-v` mount, and re-type the same six env-var
    keys. Any Phase 2 change (new env var, new path, `NO_PROXY`) must be made twice, and the two paths already differ in
    how `proxy_url` is derived. This is the seed of a drift bug.
  - **Recommendation**: Extract a single
    `_build_ca_mount_and_proxy_env(proxy_url: str) -> tuple[list[str], dict[str,str]]` helper and have both branches
    call it after resolving their own `proxy_url`.

- **🟢 NIT — `cli.py:135,209`: `generate_root_ca` is imported function-locally twice, even though
  `token_reduction/__init__.py` already re-exports it**
  - **Context**: `token_reduction/__init__.py:6` does `from … import generate_root_ca` and declares `__all__`, yet both
    call sites re-import the submodule directly inside the function body. The package's public surface is therefore
    unused.
  - **Recommendation**: Import once at module scope: `from sandbox_executor.token_reduction import generate_root_ca`.

---

#### 👥 Product Owner Review

- **🔴 CRITICAL — `cli.py:206-222`: an undocumented, non-opt-in code path changes sandbox networking for every existing
  user who happens to export a proxy variable**
  - **Context**: The PR is scoped and marketed as an **opt-in** Phase 1 behind `--token-reduce`. But the
    `elif os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")` branch fires whenever the flag is _absent_ and the host
    merely has a proxy variable set — which is the normal state for corporate/VPN users. That branch then (1) mounts the
    Holon CA into the container, (2) **overwrites** `HTTPS_PROXY` with
    `os.getenv("HOLON_PROXY_URL") or os.getenv("HTTP_PROXY") or "http://172.17.0.1:8080"`, and (3) redirects
    `SSL_CERT_FILE` to the Holon CA. For a user who exports only `HTTPS_PROXY` (a common corporate pattern),
    `HTTP_PROXY` is unset, so `HTTPS_PROXY` inside the container is silently replaced by `http://172.17.0.1:8080` — a
    dead address on both macOS and any Linux host without a local proxy. Their previously-working `holon execute` now
    fails, with no flag involved and no mention in the PR description. This is a backwards-compatibility regression on
    the default path.
  - **Recommendation**: Make CA/proxy injection strictly conditional on the explicit opt-in, and preserve host proxy
    values verbatim when merely forwarding them. If host-proxy passthrough is genuinely wanted, it must be its own
    documented, per-var, value-preserving behaviour.
  - **Proposed Code Change**:
    ```diff
    -    elif os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"):
    +    elif os.getenv("HOLON_PROXY_URL"):
    +        # Explicit opt-in via dedicated env var only; never hijack plain host proxy vars.
    +        proxy_url = os.environ["HOLON_PROXY_URL"]
    ```
    and when forwarding, keep the two vars independent:
    ```diff
    -            env_vars["HTTP_PROXY"] = proxy_url
    -            env_vars["HTTPS_PROXY"] = proxy_url
    +            for var in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
    +                if os.getenv(var):
    +                    env_vars[var] = os.environ[var]
    ```

- **🟡 IMPORTANT — `cli.py:170-173,203,222`: every failure degrades silently, so the feature can be requested and
  quietly not applied**
  - **Context**: Three separate `except Exception` / `logger.warning` paths return empty or partial mounts. An operator
    who passes `--token-reduce` and gets a silent no-op has no way to know whether token reduction is active — which
    defeats the purpose of a measurement-oriented Phase 1 and will produce misleading "reduction achieved" data
    downstream.
  - **Recommendation**: For an explicitly requested flag, fail loudly by default; optionally allow soft degradation via
    a separate `HOLON_TOKEN_REDUCE_SOFT_FAIL=1`. Echo a one-line confirmation to stdout when the proxy is live.

---

#### 👥 QA & Test Engineer Review

- **🟡 IMPORTANT — `tests/test_token_reduction.py:1-47`: the suite is green (87 passed) yet misses every critical defect
  in this PR; coverage is concentrated on the one mocked happy path**
  - **Context**: Verified by execution — `pytest` reports **87 passed** while the repo simultaneously ships a missing
    `mitm_addon.py`, an unparseable fallback cert, and a dead-proxy env injection. Concretely untested:
    - `test_ca_generator` asserts only `os.path.exists(...)` and filename suffixes. It would pass unchanged against the
      garbage fallback PEM, because it never parses the certificate.
    - The `elif os.getenv("HTTP_PROXY")` branch has **zero** coverage — including the `HTTPS_PROXY`-clobbering bug.
    - The `proxy_spawn.returncode != 0` fallback branch has zero coverage.
    - The `finally:` teardown at `cli.py:302-304` has zero coverage.
    - `--token-reduce` argparse wiring (`args.token_reduce` → `run_docker_container(token_reduce=…)`) has zero coverage;
      `test_cli.py` only asserts the negative `token_reduce=False`.
    - `setup_token_reduction_proxy` itself is never exercised (fully monkeypatched at line 34-42).
  - **Recommendation**: Add the assertions below. The cert-validity check alone would have caught the fallback bug.
  - **Proposed Code Change**:
    ```diff
     def test_ca_generator(temp_dir):
         cert_path, key_path = generate_root_ca(cert_dir=temp_dir)
         assert os.path.exists(cert_path)
    +    # Must be a real, parseable X.509 certificate — not a placeholder PEM.
    +    parse = subprocess.run(
    +        ["openssl", "x509", "-in", cert_path, "-noout", "-subject"],
    +        capture_output=True, text=True,
    +    )
    +    assert parse.returncode == 0, parse.stderr
    +    assert "Holon Agent Root CA" in parse.stdout
    +    assert oct(os.stat(key_path).st_mode & 0o777) == "0o600"

    +def test_host_proxy_does_not_clobber_https_proxy(monkeypatch):
    +    monkeypatch.setenv("HTTPS_PROXY", "http://corp-proxy:3128")
    +    monkeypatch.delenv("HTTP_PROXY", raising=False)
    +    monkeypatch.delenv("HOLON_PROXY_URL", raising=False)
    +    _, envs = get_token_reduction_mounts_and_envs(token_reduce=False)
    +    assert envs.get("HTTPS_PROXY", "http://corp-proxy:3128") == "http://corp-proxy:3128"

    +def test_proxy_spawn_failure_does_not_inject_dead_proxy(monkeypatch):
    +    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: _FakeProc(rc=1))
    +    with pytest.raises(RuntimeError):
    +        cli.setup_token_reduction_proxy()

    +def test_token_reduce_flag_is_wired(mock_run_container):
    +    cli.main.__wrapped__ if False else None  # drive via sys.argv patching
    +    # assert run_docker_container called with token_reduce=True for `plan --token-reduce`
    ```

- **🟡 IMPORTANT — plan Step 3 acceptance criteria are not met; two of three plan guardrails are unimplemented**
  - **Context**: `plans/P-1787928257-antigravity-agent-gemini-3.5-flash.md` is the contract this PR was executed
    against. Comparing it to the shipped code:
    | Plan requirement                                                                               | Shipped?                                   |
    | :--------------------------------------------------------------------------------------------- | :----------------------------------------- |
    | Step 1 guardrail: "Check for `openssl` command availability using `shutil.which`"              | ❌ replaced by silent dummy-cert fallback  |
    | Step 1 guardrail: "Trap process execution errors and … **raising a RuntimeError**"             | ❌ swallowed into `logger.warning`         |
    | Step 2: forward `NO_PROXY` / `no_proxy`                                                        | ❌ zero references in repo (grep-verified) |
    | Step 2: support `HOLON_HTTP_PROXY` / `HOLON_HTTPS_PROXY` / `HOLON_NO_PROXY` overrides          | ❌ only `HOLON_PROXY_URL` exists           |
    | Step 3: `test_run_docker_container_with_proxy_and_ca` asserting `-v` cert mount + `-e` CA vars | ❌ not present                             |
    | Step 3: "All new and existing tests pass"                                                      | ✅ 87 passed                               |
  - **Recommendation**: Either implement the remaining plan items or record the deviation explicitly in the execution
    record. Do not mark the plan "Success" while its guardrails are unmet.

- **🟢 NIT — `tests/test_token_reduction.py:12-17`: `temp_dir` fixture hand-rolls `mkdtemp`/`rmtree` instead of using
  pytest's built-in `tmp_path`**
  - **Context**: `tmp_path` is automatically isolated per test and cleaned by pytest, and it removes the
    `ignore_errors=True` cleanup that can mask a leaked directory.
  - **Recommendation**: Drop the custom fixture and take `tmp_path: Path` as a test argument.

---

#### 👥 Technical Writer Review

- **🟡 IMPORTANT — `docs/sandbox/execute_plan.md`, `docs/sandbox/create_plan.md`, `README.md`: the new `--token-reduce`
  flag and `HOLON_PROXY_URL` contract are undocumented**
  - **Context**: `grep -rn "token-reduce\|token_reduce" docs/ README.md` returns **zero** hits, even though both files
    document the `holon plan` / `holon execute` CLI surface. The PR also introduces an undocumented env-var contract
    (`HOLON_PROXY_URL`) and an undocumented implicit host-proxy passthrough. A user cannot discover, or correctly
    operate, a flag that performs TLS interception from the current docs.
  - **Recommendation**: Add a "Token Reduction (opt-in)" section covering: what the flag starts, the fact that it
    performs MITM TLS interception, the generated CA location (`~/.holon/certs/`), the sidecar lifecycle, `openssl` as a
    host prerequisite, and `HOLON_PROXY_URL`.

- **🟢 NIT — `ca_generator.py:11-19`: docstring promises behaviour the function does not implement**
  - **Context**: The docstring says it "Generates a self-signed Root CA certificate and private key if not already
    present", with no mention of the `openssl` prerequisite, the fallback path, the 365-day lifetime, or the fact that a
    previously-written invalid cert will be reused indefinitely.
  - **Recommendation**: Document the prerequisite and the reuse/caching semantics (and remove the fallback per the
    Security finding).

---

#### 👥 Developer Advocate Review

- **🟡 IMPORTANT — `cli.py:331-336,344-349`: the flag's help text hides a prerequisite and a security-relevant side
  effect**
  - **Context**: `"Enable MITM proxy and SSL CA mounts for agent token reduction"` does not tell the developer that (a)
    `openssl` must be installed on the host, (b) a background container named `holon-proxy` will be created and
    force-killed on exit, (c) all agent TLS will be intercepted and decrypted, and (d) a run may silently proceed
    without reduction if the sidecar fails. For a flag that changes network trust semantics, that is onboarding friction
    and a surprise waiting to happen.
  - **Recommendation**: Make the help text state the prerequisite and the interception explicitly.
  - **Proposed Code Change**:
    ```diff
         help="Enable MITM proxy and SSL CA mounts for agent token reduction",
    +    help=(
    +        "Route agent HTTPS through a local mitmproxy sidecar (holon-proxy) to reduce token usage. "
    +        "Requires 'openssl' on the host. Performs TLS interception using a generated root CA at "
    +        "~/.holon/certs/. Fails if the sidecar cannot start."
    +    ),
    ```

- **🟢 NIT — `cli.py:331` vs. `cli.py:318-320`: `--token-reduce` is absent from the `intent` subcommand, so the CLI
  surface is inconsistent**
  - **Context**: `intent` also runs a containerised agent through `run_docker_container`, but cannot opt into reduction.
    If Phase 1 intentionally limits scope to `plan`/`execute`, that asymmetry should be a deliberate, documented choice.

---

#### 👥 Principal Engineer Review

- **🟡 IMPORTANT — `cli.py:170-173,203,222,302-304`: `except Exception` used as blanket control flow obscures real
  bugs**
  - **Context**: Four broad handlers convert every error class — `FileNotFoundError`, `PermissionError`,
    `subprocess.CalledProcessError`, `TimeoutExpired`, and genuine programming errors like `NameError`/`TypeError` —
    into a single `logger.warning`. This is precisely why the missing `mitm_addon.py` and the invalid fallback cert did
    not surface. It also conflicts with the repo's own `dynamic_versioning` invariant discipline of catching
    `subprocess.TimeoutExpired` explicitly for debug logging.
  - **Recommendation**: Catch narrow exception types, log with `exc_info=True` at debug level, and reserve soft
    degradation for the non-opt-in path only.

- **🟢 NIT — `cli.py:180` vs. plan Step 2: mount target drifted from the plan without a recorded rationale**
  - **Context**: The plan specified `/etc/ssl/certs/holon-ca.crt`; the code uses
    `/usr/local/share/ca-certificates/holon-root-ca.crt`. The new path is arguably more correct as a _source_ location,
    but as noted above it is inert without `update-ca-certificates`. Record the decision so Phase 2 does not re-litigate
    it.

---

#### 👥 Release Manager Review

- **🟡 IMPORTANT — `plans/…md` vs. `holon-knowledge/ledger/plans.jsonl`: the plan document and the ledger disagree on
  every decision metric**
  - **Context**: Verified by direct comparison. The plan's "Overall Plan Metrics" table records `p_success_pred 0.90`,
    `entropy_pred 7.5`, `impact_pred 80`, `cost_pred 35`, `learning_value_pred 4.0`, `ev_pred 36.75`. The appended
    `plans.jsonl` row for the same `plan_id` records `p_success 0.95`, `entropy 2.0`, `impact 70.0`, `cost 10.0`,
    `learning_value 3.0`, `ev 59.3`. The ledger is the input to prioritisation/EV analytics, so this row will silently
    skew it. (The plan also declares `Allocated Entropy Budget: 15.0` / `Predicted Plan Entropy: 7.5`, while
    `intents.jsonl` records no `entropy_budget` for this intent — unlike the prior `record-agent-version` intent, which
    carried `4.0`.)
  - **Recommendation**: Reconcile the ledger row to the plan document (or vice versa) in this PR, and add a consistency
    check to the ledger writer.

- **🟢 NIT — `executions/E-…md` + three `ledger/*.jsonl` rows + `plans/…md` are bundled into a feature PR**
  - **Context**: Runtime bookkeeping artifacts are interleaved with the functional change, which inflates the diff and
    makes cherry-pick/backport of the code change harder. Default-off flag + separate artifacts is the safer pattern for
    a phased rollout.

---

#### 👥 Support Engineer Review

- **🟡 IMPORTANT — `cli.py:170-173,203,222`: failure diagnostics are insufficient for triage, and the teardown deletes
  the evidence**
  - **Context**: When `--token-reduce` misbehaves, the operator sees one `logger.warning` line (and `cli.py` never calls
    `logging.basicConfig`, so only the `logging.lastResort` WARNING+ path emits it) followed by agent-side
    TLS/connection errors. The `finally` block then runs `docker rm -f holon-proxy`, destroying the container whose logs
    explain the failure. There is no documented triage command.
  - **Recommendation**: On failure, print the actionable next step and preserve logs.
  - **Proposed Code Change**:
    ```diff
    -        logger.warning("Failed to start mitmproxy sidecar container: %s", proxy_spawn.stderr)
    +        logger.error("holon-proxy failed to start:\n%s", proxy_spawn.stderr.strip())
    +        logger.error(
    +            "Triage: `docker logs holon-proxy`  |  retry without --token-reduce  |  "
    +            "check `openssl version` and `docker images mitmproxy/mitmproxy:12.2.3`"
    +        )
    ```
    and gate teardown behind a `HOLON_KEEP_PROXY=1` escape hatch for debugging.

---

### 🏆 Overall Verdict

**❌ CHANGES_REQUESTED**

The scaffolding is sound and hygiene is clean — `ruff` passes, `prettier` passes, and all **87 tests pass** — and the
`token_reduction` package layout, `--token-reduce` default-off gating, read-only cert mount, and pinned
`mitmproxy/mitmproxy:12.2.3` tag are all good calls. The existing `test_cli.py` assertions were correctly updated rather
than bypassed.

However, the feature cannot currently work as described, and two findings are security-blocking:

1. **`mitm_addon.py` does not exist in the repository** (grep-verified), and there is no proxy readiness check — so
   `--token-reduce` either reports a dead container as healthy or injects `HTTP_PROXY`/`HTTPS_PROXY` pointing at a
   non-listening address. Either way the sandbox loses all egress.
2. **`-v ~/.holon:/home/mitmproxy/.holon` (read-write) exposes the Root CA private key and the Antigravity auth session
   store to a third-party MITM image.**
3. **The fallback certificate is rejected by OpenSSL** (`Could not find certificate`, verified) and is then cached
   permanently by the `os.path.exists` early-return, with the private key written `0644`.
4. **The `elif os.getenv("HTTP_PROXY") …` branch changes networking for users who did not opt in** and silently replaces
   `HTTPS_PROXY` with a dead default, a backwards-compatibility regression on the default path.

**Merge-blocking checklist:** ship `mitm_addon.py` (or gate the mount) + add a real readiness probe and fail-fast
semantics; narrow the sidecar mount to a dedicated read-only cache dir and remove the CA key from any container-visible
path; delete `_generate_fallback_cert` in favour of an explicit `shutil.which("openssl")` guard + `RuntimeError`, and
`chmod 0600` the key; make CA/proxy injection strictly opt-in and value-preserving.

**Strongly recommended before merge:** forward `NO_PROXY` and honour the plan's `HOLON_HTTP_PROXY`/`HOLON_HTTPS_PROXY`
overrides; use `host.docker.internal` on macOS; add `update-ca-certificates` to the image entrypoint so the Debian trust
store actually trusts the CA; namespace `holon-proxy`/`holon-net` per session; add the cert-validity and
`HTTPS_PROXY`-clobbering regression tests (the cert assertion alone would have caught finding #3); document
`--token-reduce` in `docs/sandbox/execute_plan.md` and `docs/sandbox/create_plan.md`; reconcile the `plans.jsonl` metric
row with the plan document.

---

**Counts:** CRITICAL=4 · IMPORTANT=12 · NIT=6
