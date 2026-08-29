# PR #48 — Dry-Run Review, Iteration 3 (head `12872d6`)

- **PR:** `feat(sandbox-executor): implement SSL trust and CA mounts (Phase 1)`
- **Repo / base:** `Holon-Agentic-Coder/holon-agentic-coder-ref` ← `develop`
- **Head reviewed:** `12872d6` (`fix: apply validated PR review suggestions (Iteration 2)`)
- **Worktree:** `holon-agentic-coder-ref/I-1787928238-token-reduction-phase1`
- **Mode:** DRY-RUN, single-agent, read-only. No `gh pr review`, no posting, no commits, no pushes, no source edits.
- **Inputs:** `.agents/prompts/pr_review_prompt.md`, `.subagent/pr48_iter3.diff` (1,984 lines, read once in 250-line
  slices), live worktree.

## Empirical verification log (everything below was executed, not inferred)

| Check | Command | Result | | : -- | : -- | : -- | | Unit tests |
`PYTHONPATH=apps/sandbox-executor/src uv run pytest apps/sandbox-executor/tests -q` | **120 passed, 44 subtests passed**
(41.78s) | | Lint | `uv run ruff check .` | **All checks passed!** | | Markdown format |
`npx prettier --check README.md docs/sandbox/create_plan.md docs/sandbox/execute_plan.md` | **All matched files use
Prettier code style!** | | Entrypoint syntax | `bash -n apps/sandbox-executor/entrypoint/role_dispatcher.sh` | exit 0;
shebang is `#!/usr/bin/env bash`, so the bash arrays are legal (`set -euo pipefail` is active) | | Wrapper passthrough |
`bash -n holon` + `grep` | `holon:6: exec python3 -m sandbox_executor.cli "$@"` → `--token-reduce` really does reach the
CLI | | CA crypto shape | `openssl x509 -in <gen> -noout -text` on a freshly generated CA |
`Basic Constraints: critical CA:TRUE`, `Key Usage: critical Certificate Sign, CRL Sign`, `Subject Key Identifier`
present | | CA lifetime / rotation | `openssl x509 -noout -dates` / `-checkend 2592000` | `notBefore=Aug 29 2026`,
`notAfter=Sep 30 2027` (397d), `checkend 30d` exit 0 → "will not expire" | | Key modes | `ls -l` / `stat` |
`holon-root-ca.key` = `0600`, cert = `0644` | | Phase-2 preflight |
`get_token_reduction_mounts_and_envs(token_reduce=True)` with `mitm_addon.py` absent (confirmed:
`find . -name mitm_addon.py` → empty) | returns `([], {})`, logs
`ERROR:sandbox_executor.cli:...FileNotFoundError...DIRECT egress` to stderr (visible via logging lastResort) — matches
the docs | | Malformed proxy URL | `get_token_reduction_mounts_and_envs(token_reduce=False)` with
`HOLON_PROXY_URL=http://127.0.0.1:99999` and `http://proxy:abc` | **CRASH `ValueError: Port out of range 0-65535` /
`ValueError: Port could not be cast to integer value as 'abc'`** → see IMPORTANT-1 | | Network teardown |
`docker network create` + `docker run -d --network … sleep 2`, then `docker network rm` with the
**exited-but-not-removed** container still attached | **exit 0 on Docker 29.7.2** → the hypothesised per-run network
leak does **not** reproduce; recorded as PASS, with a residual note in NIT-8 | | Image trust store |
`apps/sandbox-executor/Dockerfile` | `ca-certificates` installed (L11), `useradd -m holon` + `WORKDIR /home/holon`
(L32-33), `ENTRYPOINT role_dispatcher.sh` (L45), `USER holon` (L47) → merged bundle path is writable by the entrypoint
user |

**Already-fixed items (iterations 1–2) were re-verified in code, not in commit messages, and are NOT re-reported:**
`keyUsage`/`basicConstraints` addext + 397-day bound + `-checkend` rotation, merged-bundle trust store instead of
`update-ca-certificates`, sidecar-only `:ro` mount of exactly `mitmproxy-ca.pem`/`mitmproxy-ca-cert.pem`, `NO_PROXY`,
lowercase proxy vars, `try/finally` teardown on every exit path, probe-before-generate, per-run resource names,
experimental doc warnings, anchor fix.

---

## 📊 PR Metadata & Role Activation

Changed files: `README.md`, `apps/sandbox-executor/entrypoint/role_dispatcher.sh`,
`apps/sandbox-executor/src/sandbox_executor/cli.py`, `.../token_reduction/__init__.py`,
`.../token_reduction/ca_generator.py`, `apps/sandbox-executor/tests/test_cli.py`,
`apps/sandbox-executor/tests/test_token_reduction.py`, `docs/sandbox/create_plan.md`, `docs/sandbox/execute_plan.md`,
plus harness-generated `plans/`, `executions/`, `holon-knowledge/ledger/*.jsonl` (declared out of scope).

| Persona                            | Status (🟢 / ⚪) | Primary Trigger (Which files/contexts triggered activation)                                                                           |
| :--------------------------------- | :--------------- | :------------------------------------------------------------------------------------------------------------------------------------ |
| **Engineering & Architecture**     |                  |                                                                                                                                       |
| Principal Engineer                 | 🟢               | `cli.py` (+350 lines of orchestration, module-global sidecar state), `ca_generator.py` (new module boundary)                          |
| Solution Architect                 | 🟢               | Host↔container trust boundary, per-run Docker network, sidecar/agent separation, Phase 1/Phase 2 seam                                 |
| Frontend Engineer                  | ⚪               | No UI, CSS/HTML or client-state files changed                                                                                         |
| QA & Test Engineer                 | 🟢               | `tests/test_token_reduction.py` (+558 lines), `tests/test_cli.py`; test suite executed                                                |
| ML & Data Specialist               | ⚪               | No model, dataset or inference-pipeline code changed (token reduction is a transport concern here)                                    |
| **Product, Design, & Growth**      |                  |                                                                                                                                       |
| Product Owner                      | 🟢               | New user-facing opt-in surface (`--token-reduce`, `HOLON_TOKEN_REDUCE`, `HOLON_PROXY_URL`) and its Phase 1/2 scope statement          |
| UX/UI Designer                     | ⚪               | No visual/design surface; CLI help text reviewed under DevRel                                                                         |
| SEO & Growth Specialist            | ⚪               | No public web pages, metadata or routing changed                                                                                      |
| **Operations, Release, & Support** |                  |                                                                                                                                       |
| DevOps & SRE                       | 🟢               | `docker run`/`network` lifecycle, sidecar resource caps + log rotation, `role_dispatcher.sh`, `Dockerfile` trust store, env injection |
| Release Manager                    | 🟢               | Experimental flag shipped dark-by-default; Phase 2 dependency ordering; rollback = flag off                                           |
| Support Engineer                   | 🟢               | Failure-path messages, degradation semantics, operator diagnosability of "why is my run not proxied"                                  |
| **Security, Compliance, & Risk**   |                  |                                                                                                                                       |
| Security Architect                 | 🟢               | Root CA + private key handling, MITM trust bootstrap, bind-mount exposure, TLS interception posture                                   |
| Compliance Auditor                 | 🟢               | Retention/redaction posture of intercepted traffic, key custody, `~/.holon` data separation                                           |
| Localization Coordinator           | ⚪               | No user-facing localized strings; all output is English operator logging                                                              |
| **DevRel & Documentation**         |                  |                                                                                                                                       |
| Technical Writer                   | 🟢               | `README.md` + two `docs/sandbox/*.md` contract sections, docstrings, inline comments                                                  |
| Developer Advocate                 | 🟢               | Public CLI DX: flag discoverability, `--help` text, env-var contract, failure guidance                                                |

---

## 🔍 Persona Reviews

### 👥 Security Architect Review

- **✅ APPROVED / PASS — `cli.py:_mitm_proxy_ca_paths` / `setup_token_reduction_proxy` (diff L251-272, L395-425)**
  - **Context**: A MITM CA inherently needs its private key on the signing side. The implementation narrows exposure to
    exactly two files (`mitmproxy-ca.pem` key+cert at `0600`, `mitmproxy-ca-cert.pem` at `0644`) inside a `0700`
    `~/.holon/proxy-ca`, mounts **only those two files** `:ro` into `/home/mitmproxy/.mitmproxy`, and mounts **only the
    public certificate** into the agent container (`_ca_mount_args` takes `ca_cert_path`). `~/.holon` is never mounted
    wholesale, so `~/.holon/certs` (Root CA key) and `~/.holon/sessions` (agent credentials) stay out of the sidecar.
  - **Evidence**: `os.open(..., 0o600)` before the first write plus a defensive re-`chmod` closes the umask window; the
    test asserts `0o600`/`0o700` modes, that the combined file contains `BEGIN PRIVATE KEY`, that the cert-only file
    does **not**, and that `holon-root-ca.key` never appears in the `docker run` line. Verified locally: generated key
    mode is `0o600`.

- **✅ APPROVED / PASS — blast radius of the new trust anchor (`ca_generator.py`, `role_dispatcher.sh`)**
  - **Context**: The Holon Root CA is installed into **no** host trust store and into **no** container that did not
    explicitly opt in. Inside the sandbox it is trusted only through env overrides that the entrypoint unsets if the
    merged bundle cannot be written, so a failed bootstrap degrades to the image's default store rather than to a broken
    or widened trust store. `NO_PROXY` keeps loopback and `169.254.169.254` off the interception path.

- **🟢 NIT / OPTIONAL (NIT-2) — `cli.py:setup_token_reduction_proxy` sidecar `docker run` args (diff L404-431)**
  - **Context**: The sidecar is well bounded on resources (`--memory=256m --cpus=0.5`, `--log-opt max-size=5m`,
    `max-file=2`, `--restart=no`, loopback-only `-p 127.0.0.1::8080`) but not on privileges, and nothing identifies its
    containers as Holon-owned. If the host CLI is `SIGKILL`ed, `finally` never runs and the sidecar container + network
    are orphaned with no way to reap them selectively.
  - **Recommendation**: Add privilege drops and a run label so orphans are re-claimable in Phase 2, e.g.
    ```diff
    +        "--cap-drop", "ALL",
    +        "--security-opt", "no-new-privileges",
    +        "--label", f"holon.run-id={run_suffix}",
    +        "--label", "holon.component=token-reduce-proxy",
    ```
    and (Phase 2) a `docker ps -q --filter label=holon.component=token-reduce-proxy` sweep at CLI start.

- **🟢 NIT / OPTIONAL (NIT-3) — `cli.py:NO_PROXY_HOSTS` (diff L60)**
  - **Context**: `localhost,127.0.0.1,::1,169.254.169.254` covers EC2/GCE-style IMDSv1 metadata but not the ECS task
    endpoint (`169.254.170.2`), GCE metadata DNS name (`metadata.google.internal`) or IPv6 IMDS (`fd00:ec2::254`). Those
    would be force-proxied through the MITM sidecar once functional — an unnecessary credential-bearing path.
  - **Recommendation**: widen the list (and mirror it in the docs table) before Phase 2 makes interception real:
    ```diff
    -NO_PROXY_HOSTS = "localhost,127.0.0.1,::1,169.254.169.254"
    +NO_PROXY_HOSTS = "localhost,127.0.0.1,::1,169.254.169.254,169.254.170.2,fd00:ec2::254,metadata.google.internal"
    ```

### 👥 Compliance & Privacy Auditor Review

- **✅ APPROVED / PASS — retention / redaction honesty (`README.md`, `docs/sandbox/*.md`)**
  - **Context**: All three docs state explicitly that the proxy cache is mounted read-only, logs are size-bounded, and
    **no credential redaction is implemented yet**, therefore `--token-reduce` must only be used against a locally-owned
    proxy. Stating the gap instead of implying a control that does not exist is the right compliance posture, and it
    matches the code (no redaction filter exists anywhere in the diff).
- **✅ APPROVED / PASS — data separation**: only `~/.holon/proxy-cache` (created empty, `:ro`) is shared with the
  sidecar; agent session stores under `~/.holon/sessions` are not reachable from it.

### 👥 Principal Engineer / Tech Lead Review

- **✅ APPROVED / PASS — module boundary and fail-loud discipline (`ca_generator.py`)**
  - **Context**: One job per module, `_ensure_root_ca()` shared by the API and `__main__`, `RuntimeError` translation
    for every openssl failure with an actionable "Delete <dir> and re-run" hint, explicit `subprocess.TimeoutExpired`
    handling on both the generation and the validation probes, and **no** fallback-certificate stub. The docstring
    explains _why_ a poisoned cache must not be trusted, which is exactly the kind of comment that survives.
  - **Evidence**: `openssl` absence raises before anything is written (test asserts `os.listdir(tmp_path) == []`);
    `CalledProcessError` leaves no `.crt` behind; poisoned cache is detected. All verified by the executed suite.

- **🟡 IMPORTANT / IMPROVEMENT — `cli.py:_proxy_host_port` + `get_token_reduction_mounts_and_envs` (diff L560-566,
  L575-597)**
  - **Context**: `_proxy_host_port` reads `parsed.port`, and `urllib.parse` raises `ValueError` (not `OSError`) for a
    syntactically present but invalid port. The outer guard catches only `(FileNotFoundError, RuntimeError, OSError)`,
    so a malformed `HOLON_PROXY_URL` escapes the documented contract ("Any failure degrades to direct egress (empty
    mounts/envs) with an actionable error log") and kills the whole run with a traceback — the one behaviour this PR
    promises never to produce. **Verified by execution:**
    ```
    HOLON_PROXY_URL=http://127.0.0.1:99999  -> CRASH ValueError: Port out of range 0-65535
    HOLON_PROXY_URL=http://proxy:abc        -> CRASH ValueError: Port could not be cast to integer value as 'abc'
    ```
    Note the _empty-host_ branch (`return None` → "is not a valid proxy URL" → `([], {})`) is correct but has **zero
    test coverage** — `grep` shows the only `HOLON_PROXY_URL` tests use `http://127.0.0.1:9`, which exercises the
    unreachable-proxy path instead.
  - **Recommendation**: normalise the parse failure into the existing `None` sentinel (keeps the "degrade, don't crash"
    invariant local to the parser rather than spread across the `except` tuple), and add the missing regression test.
    ```diff
     def _proxy_host_port(proxy_url: str) -> tuple[str, int] | None:
         """Split a proxy URL into ``(host, port)``; None when it cannot be parsed."""
    -    parsed = urlparse(proxy_url if "//" in proxy_url else f"//{proxy_url}")
    -    if not parsed.hostname:
    -        return None
    -    return parsed.hostname, parsed.port or PROXY_LISTEN_PORT
    +    try:
    +        parsed = urlparse(proxy_url if "//" in proxy_url else f"//{proxy_url}")
    +        port = parsed.port  # raises ValueError for a non-numeric or out-of-range port
    +    except ValueError:
    +        return None
    +    if not parsed.hostname:
    +        return None
    +    return parsed.hostname, port or PROXY_LISTEN_PORT
    ```
    ```diff
    +@pytest.mark.parametrize("url", ["http://127.0.0.1:99999", "http://proxy:notaport", "://no-host"])
    +def test_invalid_proxy_url_degrades_to_direct_egress(monkeypatch, caplog, url):
    +    monkeypatch.setenv("HOLON_TOKEN_REDUCE", "1")
    +    monkeypatch.setenv("HOLON_PROXY_URL", url)
    +    with caplog.at_level(logging.ERROR, logger="sandbox_executor.cli"):
    +        assert get_token_reduction_mounts_and_envs(token_reduce=False) == ([], {})
    +    assert "not a valid proxy URL" in caplog.text
    ```
  - **Severity rationale**: opt-in-only, experimental surface and it fails loudly rather than silently — not a blocker,
    but it contradicts a promise the PR itself documents in three files.

- **🟢 NIT / OPTIONAL (NIT-7) — `cli.py:_sidecar_state` module-global singleton (diff L74-82)**
  - **Context**: Teardown bookkeeping lives in a module-level mutable. The CLI is strictly one-run-per-process today, so
    this is safe, but `run_docker_container` is importable as a library call and two concurrent calls in one process
    would clobber each other's `container_name`/`network_name` and leak one sidecar.
  - **Recommendation**: either return the state from `setup_token_reduction_proxy()` and pass it to teardown, or add a
    one-line comment stating the single-run-per-process assumption as an explicit invariant.

### 👥 Solution Architect Review

- **✅ APPROVED / PASS — Phase 1/Phase 2 seam**: the addon path is gated by a preflight `os.path.isfile` **before** any
  Docker or openssl side effect (`fake.calls == []` asserted), so Phase 2 can drop `mitm_addon.py` in without touching
  the trust bootstrap. The flag is documented as experimental in `--help`, README and both sandbox docs.
- **✅ APPROVED / PASS — ownership discipline**: resources are named `holon-proxy-<pid>-<uuid8>` /
  `holon-net-<pid>-<uuid8>` and `_ensure_network` distinguishes "I created it" from "it already existed", so teardown
  never deletes a foreign network (`test_setup_proxy_network_already_exists_is_not_owned`).
- **✅ APPROVED / PASS — readiness gating**: a dead proxy is never injected. The host-side probe runs against the
  _published loopback port_ read from `docker port` (not a guessed fixed port), and the attach path probes **before**
  generating a CA so a doomed run leaves no fresh trust anchor behind.

### 👥 DevOps & SRE Review

- **✅ APPROVED / PASS — `role_dispatcher.sh` trust bootstrap (diff L110-146)**: correct diagnosis that `USER holon`
  makes `update-ca-certificates` impossible; merged bundle written as `holon` into `WORKDIR /home/holon` (verified
  writable in the `Dockerfile`), `chmod 600`, `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` pointed at the
  **merged** file and `NODE_EXTRA_CA_CERTS` at the single-cert mount, `NO_PROXY` preserved, and — critically — the
  overrides are **unset** when the bundle cannot be written so clients fall back to the image store instead of failing
  every HTTPS call. `bash -n` clean; arrays are legal under the `#!/usr/bin/env bash` shebang; every failure branch
  still logs to stderr rather than being swallowed by `set -e`.
- **✅ APPROVED / PASS — per-run network removal**: verified on Docker 29.7.2 that `docker network rm` succeeds even
  when an exited-but-not-removed container is still attached, and the agent container is started with `--rm`
  (`cli.py:522`), so the documented "container and network removed on every exit path" holds.
- **🟢 NIT / OPTIONAL (NIT-1) — `cli.py:_run_docker` has no timeout (diff L186-188)**
  - **Context**: `ca_generator` correctly bounds every openssl call with `timeout=60` and translates
    `subprocess.TimeoutExpired`, but the Docker helpers (`network create`, `run`, `port`, `rm`, `network rm`) run
    unbounded. A wedged Docker daemon therefore hangs the run forever _and_ prevents the `finally` teardown from ever
    executing — the exact scenario the teardown contract is meant to cover. (The pre-existing
    `subprocess.run(docker_cmd)` for the agent container shares this shape, so this is consistency, not regression.)
  - **Recommendation**:
    ```diff
    -def _run_docker(*args: str) -> subprocess.CompletedProcess[str]:
    -    """Run a docker command without raising, capturing stdout/stderr for diagnostics."""
    -    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
    +_DOCKER_TIMEOUT_SECONDS = 120
    +
    +def _run_docker(*args: str) -> subprocess.CompletedProcess[str]:
    +    """Run a docker command without raising, capturing stdout/stderr for diagnostics."""
    +    try:
    +        return subprocess.run(["docker", *args], capture_output=True, text=True, check=False,
    +                              timeout=_DOCKER_TIMEOUT_SECONDS)
    +    except subprocess.TimeoutExpired as exc:
    +        raise RuntimeError(f"'docker {' '.join(args)}' timed out after {_DOCKER_TIMEOUT_SECONDS}s") from exc
    ```
    (`_ensure_network` already raises `RuntimeError`, so the caller's degradation contract is preserved.)
- **🟢 NIT / OPTIONAL (NIT-8) — `cli.py:teardown_token_reduction_proxy` failure visibility (diff L470-495)**
  - **Context**: Both `docker rm -f` and `docker network rm` failures are logged at `logger.debug`, which is invisible
    at the CLI's effective log level. On older daemons (pre-20.10 behaviour) an attached endpoint _can_ block network
    removal, and the operator would get no signal that a per-run network survived.
  - **Recommendation**: keep `debug` for the expected "already gone" case but escalate a non-zero `network rm` to
    `logger.warning` with the resource name, so leaked networks are discoverable without `-v`.

### 👥 QA & Test Engineer Review

- **✅ APPROVED / PASS — 120 tests pass, 44 subtests, no weakened or deleted assertions**: `test_token_reduction.py`
  grew from 26 to 35 tests in iteration 2 and now covers crypto shape (`keyUsage`/`CA:TRUE`/SKI/`-checkend`),
  near-expiry rotation, valid-cache reuse, key/dir modes, sidecar-only CA mounts, merged-bundle env invariants,
  `NO_PROXY` + lowercase proxy vars, opt-in truthiness, probe-before-generate ordering, and teardown on early-return /
  exception / normal paths. `test_cli.py` was updated only to add `token_reduce=False` to the two
  `assert_called_once_with` calls — a signature change, not a loosened assertion.
- **✅ APPROVED / PASS — test hygiene**: `reset_sidecar_state` is autouse and resets before _and_ after, `host_paths`
  keeps every host write inside `tmp_path`, `FakeDocker` records the exact argv so the mount/flag assertions are real,
  and stdlib patches are scoped to the module under test (`cli.os.path.isfile`, `ca_generator.shutil`) instead of
  globally.
- **🟡 covered under IMPORTANT-1**: the `_proxy_host_port` → `None` branch and its "is not a valid proxy URL" log line
  are the only uncovered failure branch in the new module; the parametrised test above closes it.

### 👥 Product Owner / Product Manager Review

- **✅ APPROVED / PASS — scope honesty and dark launch**: the flag ships inert-by-default, `--token-reduce` is exposed
  only on `plan`/`execute` (not `intent`), and README/create_plan/execute_plan all carry the same "experimental / not
  yet functional, degrades to direct egress" warning. Host `HTTP_PROXY`/`HTTPS_PROXY` are explicitly excluded from the
  opt-in surface (`test_host_proxy_env_alone_never_rewrites_sandbox_networking`), which prevents the worst surprise: a
  user's corporate proxy silently rewriting sandbox networking.
- **✅ APPROVED / PASS — no deprecation surface**: no fallback stubs, CLI error shims, migration notices or deprecation
  release notes anywhere in the diff.

### 👥 Release Manager Review

- **✅ APPROVED / PASS — rollback is trivial**: with the flag off (default) the only behavioural change to existing runs
  is the entrypoint's `if [ -f "$HOLON_ROOT_CA_PATH" ]` guard, which is false whenever the CA is not mounted, so
  `develop` behaviour is byte-identical for every current invocation. Phase 2 dependency (`mitm_addon.py`) is named in
  the docs and enforced by the preflight, so the ordering is explicit rather than tribal knowledge.
- **✅ APPROVED / PASS — image pinning posture**: `mitmproxy/mitmproxy:12.2.3` is a fixed semver tag (digest pinning was
  declared out of scope) and the first-run pull is pre-announced in the info log so a slow pull is not mistaken for a
  hang.

### 👥 Technical Support Engineer Review

- **✅ APPROVED / PASS — every failure names the escape hatch**: each raise and each degradation ends with "Re-run
  without `--token-reduce` to execute with direct egress" / "this run continues with DIRECT egress", and the readiness
  error includes the concrete `127.0.0.1:<published port>` plus the "the addon likely crashed on startup" hypothesis.
  Verified live: the missing-addon path prints a single actionable `ERROR` line and the run proceeds.
- **✅ APPROVED / PASS — no secret leakage in diagnostics**: the printed `Executing: …` line still redacts
  `GITHUB_TOKEN`/`HOLON_AGENT_KEY`, and the newly injected env vars contain only paths and a container-local proxy URL.

### 👥 Developer Advocate Review

- **✅ APPROVED / PASS — discoverability**: `--token-reduce` help text states experimental status, the Phase 2 gap, the
  host binary prerequisites, and the key-exposure model in one paragraph; the env-var contract is a two-row table
  repeated identically in all three docs; the `execute_plan.md` anchor
  `#4-optional-token-reduction-proxy---token-reduce` resolves correctly against the generated GitHub slug.

### 👥 Technical Writer Review

- **✅ APPROVED / PASS — mechanism-level documentation**: the docs explain _why_ the merged bundle exists (those three
  variables _replace_ the store, `NODE_EXTRA_CA_CERTS` _augments_), which is the single most common way this design gets
  broken by a later contributor. Prettier-clean.
- **🟢 NIT / OPTIONAL (NIT-4) — triple-duplicated warning block (`README.md` L731-797, `create_plan.md` L39-90,
  `execute_plan.md` L55-107)**
  - **Context**: The ~30-line "Trust mechanism / Key exposure / Retention posture" block is copied verbatim three times.
    Phase 2 will change it (redaction lands, addon ships), and three copies drift.
  - **Recommendation**: keep the canonical block in one place (e.g. a new `docs/sandbox/token_reduction.md`) and replace
    the other two with a one-paragraph summary plus a link.
- **🟢 NIT / OPTIONAL (NIT-5) — `docs/sandbox/create_plan.md:127` "Argument Breakdown"**
  - **Context**: `execute_plan.md` gained a `--token-reduce` bullet in its "Command Breakdown", but the parallel
    "Argument Breakdown" in `create_plan.md` was not updated, so the two docs now describe the same flag at different
    levels of completeness.
  - **Recommendation**: add the matching bullet (or state explicitly that the section documents only the manual
    `docker run` arguments).

---

## 🧾 Findings Ledger

| ID | Severity | File | Title | Verified | | : -- | : -- | : -- | : -- | : -- | | IMPORTANT-1 | 🟡 |
`apps/sandbox-executor/src/sandbox_executor/cli.py` | `ValueError` from `parsed.port` escapes the
degrade-to-direct-egress guard; invalid-URL branch untested | ✅ executed | | NIT-1 | 🟢 | `cli.py:_run_docker` | No
`timeout=` on Docker subprocesses; wedged daemon hangs the run and skips teardown | ✅ code | | NIT-2 | 🟢 |
`cli.py:setup_token_reduction_proxy` | Sidecar lacks `--cap-drop ALL` / `no-new-privileges` / run label for orphan
reaping | ✅ code | | NIT-3 | 🟢 | `cli.py:NO_PROXY_HOSTS` | ECS/GCE/IPv6 metadata endpoints not excluded from
interception | ✅ code | | NIT-4 | 🟢 | `README.md`, `docs/sandbox/*.md` | 30-line security block triplicated → Phase 2
drift risk | ✅ code | | NIT-5 | 🟢 | `docs/sandbox/create_plan.md` | "Argument Breakdown" lacks the `--token-reduce`
bullet its sibling doc gained | ✅ code | | NIT-6 | 🟢 | `cli.py:_mitm_proxy_ca_paths` | `0700` dir + `0600` key
bind-mounted into an image whose `mitmproxy` uid may not match the host uid; Phase 2 should confirm readability or pass
`--user` | ⚠️ UNVERIFIED (no mitmproxy image pulled) | | NIT-7 | 🟢 | `cli.py:_sidecar_state` | Module-global teardown
state assumes one run per process | ✅ code | | NIT-8 | 🟢 | `cli.py:teardown_token_reduction_proxy` | `network rm`
failure logged only at `debug`; invisible on daemons where an attached endpoint blocks removal | ✅ PASS on Docker
29.7.2, UNVERIFIED on older |

**Out-of-scope items deliberately NOT flagged:** absence of `mitm_addon.py` / `--token-reduce` not yet functional
(preflight verified to fail loudly and degrade), digest-pinning `mitmproxy/mitmproxy:12.2.3`, and the harness-generated
`plans/`, `executions/`, `holon-knowledge/ledger/*.jsonl` artifacts.

---

## 🏆 Overall Verdict

**💬 COMMENT** — good work overall; mergeable as-is, with one improvement and a set of optional suggestions worth
folding into Phase 2.

- **CRITICAL=0.** Tests (120 + 44 subtests), `ruff check`, `prettier --check` and `bash -n` all pass; the CA artifacts
  were re-verified with `openssl` (critical `CA:TRUE` + `keyCertSign,cRLSign`, 397-day validity, `0600` key); the
  private key never reaches the agent container; teardown covers every exit path; and the opt-in contract is enforced
  against host proxy env vars.
- **IMPORTANT=1** — `HOLON_PROXY_URL` with a malformed port crashes the CLI instead of degrading to direct egress
  (reproduced). Small, local fix; it contradicts a guarantee the PR documents in three files, so it is worth taking now
  rather than in Phase 2.
- **NIT=8** — hardening, coverage and documentation-consistency suggestions, all optional.

Per the severity discipline, no blocker-class issue exists in this changeset, so `CHANGES_REQUESTED` is not warranted.
