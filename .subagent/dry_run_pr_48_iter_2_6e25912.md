# PR Review Report — Iteration 2 (Dry-Run, Single-Agent Mode)

- **PR:** #48 — `feat(sandbox-executor): implement SSL trust and CA mounts (Phase 1)`
- **Repo / base:** `Holon-Agentic-Coder/holon-agentic-coder-ref` ← `develop`
- **Head reviewed:** `6e25912` (`fix: apply validated PR review suggestions (Iteration 1)`) on branch
  `I-1787928238-token-reduction-phase1/P-1787928257-antigravity-agent-gemini-3.5-flash/E-1787928747-antigravity-agent-gemini-3.5-flash/_`
- **Diff:** +1254 / −4 across 14 files (`git diff --stat origin/develop...HEAD`)
- **Mode:** read-only dry run. No `gh pr review`, no commit, no push, no source modification. The only file written is
  this report.

---

## 0. Iteration-1 Regression Check (verified in code, not from the commit message)

| Iter-1 finding                                                      | Status in `6e25912`                                                                                                                                                                                       | How verified                                                                                                            |
| :------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------- |
| C1 — wholesale `~/.holon` mount leaked CA key + agent sessions      | ✅ **Fixed** — only `~/.holon/proxy-cache:/home/mitmproxy/.holon/proxy-cache:ro` (`cli.py:309-313`)                                                                                                       | Code read + `test_setup_proxy_success_mounts_only_narrow_ro_cache` passes                                               |
| C2 — unparseable fallback cert cached forever, world-readable key   | ✅ **Fixed** — `_generate_fallback_cert` deleted; `shutil.which` probe; `CalledProcessError`/`TimeoutExpired` → `RuntimeError`; `timeout=60`; key pre-created `0o600`; `_assert_valid_cert` on both paths | Live run: `generate_root_ca()` → `-rw------- holon-root-ca.key`, `openssl x509 -noout` rc=0; poisoned-cache test passes |
| C3 — dead proxy injected as "healthy"; addon path unchecked         | ✅ **Fixed** — `os.path.isfile(addon_path)` guard, spawn rc check, `_wait_for_proxy` TCP loop, loopback-only publish + `docker port`                                                                      | Live run: `--token-reduce` → `MOUNTS: [] ENVS: {}` + actionable ERROR                                                   |
| C4 — host `HTTP_PROXY` treated as opt-in                            | ✅ **Fixed** — `_token_reduce_opt_in` only honours `--token-reduce` / truthy `HOLON_TOKEN_REDUCE`                                                                                                         | `test_host_proxy_env_alone_never_rewrites_sandbox_networking` passes                                                    |
| I2/I5 — shared `holon-net` name, teardown touched foreign resources | ✅ **Fixed** — `holon-proxy-<pid>-<uuid8>` / `holon-net-<pid>-<uuid8>` + `_SidecarState` ownership                                                                                                        | Code read + tests                                                                                                       |
| I4 — no `update-ca-certificates` hook                               | ⚠️ **Added but inert** — see **C-3** below                                                                                                                                                                | Executed inside `holon/agent-antigravity` as uid 1000 → rc=2, `Permission denied`                                       |

**Harness/test/lint state (executed):**

```text
uv run pytest apps/sandbox-executor/tests -q   -> 111 passed, 44 subtests passed in 40.61s
uv run ruff check .                            -> All checks passed!
uv run ruff format --check .                   -> 17 files already formatted
npx prettier --check README.md docs/sandbox/*.md -> All matched files use Prettier code style!
bash -n apps/sandbox-executor/entrypoint/role_dispatcher.sh -> OK
```

None of the iteration-1 findings above are re-reported.

---

## 1. 📊 PR Metadata & Role Activation (Dynamic Role Activation Matrix)

| Persona                           | Status | Primary Trigger (files/contexts)                                                                                                     |
| :-------------------------------- | :----- | :----------------------------------------------------------------------------------------------------------------------------------- |
| **Engineering & Architecture**    |        |                                                                                                                                      |
| Principal Engineer                | 🟢     | `cli.py` (+353), `token_reduction/ca_generator.py` (new) — new lifecycle/state machine, subprocess + crypto plumbing                 |
| Solution Architect                | 🟢     | New sidecar + per-run bridge network topology; host↔sidecar↔sandbox CA trust contract (`cli.py`, `role_dispatcher.sh`, `Dockerfile`) |
| Frontend Engineer                 | ⚪     | No UI/HTML/CSS/JS files in the diff                                                                                                  |
| QA & Test Engineer                | 🟢     | `tests/test_token_reduction.py` (new, 336 lines), `tests/test_cli.py`                                                                |
| ML & Data Specialist              | ⚪     | No model/feature/dataset code; token-reduction logic (the addon) is not in this diff                                                 |
| **Product, Design & Growth**      |        |                                                                                                                                      |
| Product Owner                     | 🟢     | `--token-reduce` is a user-facing feature flag; README/docs promise behaviour the code cannot currently deliver                      |
| UX/UI Designer                    | ⚪     | No visual/design surface (CLI text only)                                                                                             |
| SEO & Growth Specialist           | ⚪     | No public web pages/metadata                                                                                                         |
| **Operations, Release & Support** |        |                                                                                                                                      |
| DevOps & SRE                      | 🟢     | `docker run` sidecar flags, image pinning, network lifecycle, `role_dispatcher.sh`, `Dockerfile` trust store                         |
| Release Manager                   | 🟢     | Phase 1 / Phase 2 staging, inert-flag release posture, teardown/rollback of run-scoped resources                                     |
| Support Engineer                  | 🟢     | Degradation error strings, `--help` text, troubleshooting claims in docs                                                             |
| **Security, Compliance & Risk**   |        |                                                                                                                                      |
| Security Architect                | 🟢     | Root CA generation/crypto extensions, TLS interception, bind-mount scope, key permissions                                            |
| Compliance & Privacy Auditor      | 🟢     | Interception of credential-bearing agent traffic + on-disk `~/.holon/proxy-cache`                                                    |
| Localization Coordinator          | ⚪     | No user-facing localized strings introduced                                                                                          |
| **DevRel & Documentation**        |        |                                                                                                                                      |
| Technical Writer                  | 🟢     | `README.md`, `docs/sandbox/create_plan.md`, `docs/sandbox/execute_plan.md`                                                           |
| Developer Advocate                | 🟢     | `./holon` CLI is the developer surface: `--token-reduce` help text + `HOLON_*` env contract                                          |

---

## 2. 🔍 Persona Reviews

### 👥 Security Architect Review

- **🔴 CRITICAL — `apps/sandbox-executor/src/sandbox_executor/token_reduction/ca_generator.py:112-131`
  (`generate_root_ca` openssl `req -x509` invocation): the generated Root CA has no `keyUsage` extension, so the
  sandbox's own TLS stack refuses to trust it as an anchor**

  - **Context**: The command is
    `openssl req -x509 -newkey rsa:2048 -keyout … -out … -days 365 -nodes -subj "/CN=Holon Agent Root CA/O=Holon Agentic Coder"`.
    OpenSSL emits only `subjectKeyIdentifier`, `authorityKeyIdentifier` and `basicConstraints=CA:TRUE` — verified on the
    artifact this code produced:

    ```text
    $ openssl x509 -in ~/.holon/certs/holon-root-ca.crt -noout -text | sed -n '/X509v3 extensions/,/Signature/p'
    X509v3 Subject Key Identifier: 9D:0D:5C:…
    X509v3 Authority Key Identifier: 9D:0D:5C:…
    X509v3 Basic Constraints: critical
        CA:TRUE
    ```

    No `X509v3 Key Usage`. OpenSSL ≥3.2 in strict mode (and Python's `ssl` default context) rejects a trust anchor that
    lacks the key-usage extension. Executed **inside the actual sandbox image** (`holon/agent-antigravity`,
    `python 3.13.14 | OpenSSL 3.5.6`) against a leaf signed by this CA:

    ```text
    RESULT sandbox-python trust Holon-signed leaf: FAILED -> SSLCertVerificationError
      [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
      CA cert does not include key usage extension (_ssl.c:1032)
    ```

    Consequence: the CA that this PR generates, mounts and advertises as "trusted inside the sandbox" is **unusable as a
    trust anchor** by exactly the client class the sandbox runs (Python 3.13 in `python:3.13-slim`). Every intercepted
    TLS session would fail with an opaque `CERTIFICATE_VERIFY_FAILED`, and — because `_assert_valid_cert` only parses
    the PEM — the CLI reports success. This defeats the stated purpose of Phase 1 ("establishes the SSL trust bootstrap
    mechanism").

  - **Recommendation**: Emit a proper CA profile. Add `basicConstraints=critical,CA:TRUE`,
    `keyUsage=critical,keyCertSign,cRLSign` (and keep `subjectKeyIdentifier=hash`). I validated the fix in the same
    sandbox image:

    ```text
    FIXED CA (keyUsage=keyCertSign) as trust anchor in sandbox python: VERIFIED OK
    ```

    Also add a regression test that asserts the generated cert carries `Key Usage: Certificate Sign` (parse
    `openssl x509 -noout -text`) — the current tests only assert "BEGIN CERTIFICATE" and rc=0, which is precisely the
    gap that let this through.

  - **Proposed Code Change**:

    ```diff
                 "-nodes",
                 "-subj",
                 "/CN=Holon Agent Root CA/O=Holon Agentic Coder",
    +            "-addext",
    +            "basicConstraints=critical,CA:TRUE",
    +            "-addext",
    +            "keyUsage=critical,keyCertSign,cRLSign",
    +            "-addext",
    +            "subjectKeyIdentifier=hash",
             ],
    ```

    ```diff
    +def _assert_usable_ca(ca_cert_path: str) -> None:
    +    """A trust anchor must be marked as a certificate signer or strict verifiers reject it."""
    +    text = subprocess.run(
    +        [shutil.which("openssl") or "openssl", "x509", "-in", ca_cert_path, "-noout", "-text"],
    +        capture_output=True, text=True, timeout=_OPENSSL_TIMEOUT_SECONDS, check=False,
    +    ).stdout
    +    if "Certificate Sign" not in text:
    +        raise RuntimeError(
    +            f"Root CA at {ca_cert_path} lacks keyUsage=keyCertSign; strict TLS clients reject it. "
    +            f"Delete {os.path.dirname(ca_cert_path)} and re-run to regenerate."
    +        )
    ```

- **🟡 IMPORTANT — `cli.py:303-313` (`setup_token_reduction_proxy`): the sidecar is never given the Holon Root CA, so it
  will sign leaf certificates with its own ephemeral CA that the sandbox does not trust**

  - **Context**: The sidecar mounts are exactly `proxy-cache:ro` and `/tmp/mitm_addon.py:ro`. `mitmdump` is started with
    no `confdir`/CA configuration, so it generates a throwaway CA inside the container on every run and signs
    intercepted leaf certs with **that** CA. The sandbox, however, is told to trust `holon-root-ca.crt`. The two halves
    of the trust bootstrap can never meet: interception yields `CERTIFICATE_VERIFY_FAILED` for the agent. The docs make
    this an explicit invariant — "the private key … is never mounted into any container" — which is correct as a
    _sandbox_ containment rule but is incompatible with the sidecar ever using the Holon CA. Note the containment
    argument still holds if the key is scoped to the sidecar only: the sidecar is a separate container on a per-run
    network, is read-only, and never receives agent credentials or session mounts.

  - **Recommendation**: Materialise a mitmproxy-compatible confdir on the host and mount it read-only into the sidecar,
    then reword the invariant to "never mounted into the **sandbox**". mitmproxy's confdir layout is `mitmproxy-ca.pem`
    (key + cert), `mitmproxy-ca-cert.pem` (cert only), `mitmproxy-dhparam.pem`. Because mitmproxy may want to write
    `mitmproxy-dhparam.pem`, either pre-create it or mount the confdir read-write while keeping it a dedicated directory
    that contains nothing else.

  - **Proposed Code Change**:

    ```diff
    +    confdir = os.path.join(os.path.expanduser("~"), ".holon", "mitmproxy-confdir")
    +    os.makedirs(confdir, exist_ok=True)
    +    ca_pem = os.path.join(confdir, "mitmproxy-ca.pem")
    +    if not os.path.exists(ca_pem):
    +        with open(ca_pem, "w") as fh, open(ca_cert_path) as crt, open(ca_key_path) as key:
    +            fh.write(crt.read()); fh.write(key.read())
    +        os.chmod(ca_pem, 0o600)
    +    shutil.copyfile(ca_cert_path, os.path.join(confdir, "mitmproxy-ca-cert.pem"))
         ...
         "-v",
    -    f"{proxy_cache_dir}:/home/mitmproxy/.holon/proxy-cache:ro",
    +    f"{proxy_cache_dir}:/home/mitmproxy/.holon/proxy-cache:ro",
    +    f"{confdir}:/home/mitmproxy/.mitmproxy",
    ```

- **🟡 IMPORTANT — `cli.py:170-181` (`_build_proxy_envs`): no `NO_PROXY` / `no_proxy` is injected, so _all_ egress —
  including loopback services and link-local metadata endpoints — is forced through the MITM proxy**

  - **Context**: `grep -rn "NO_PROXY\|no_proxy" apps docs README.md` returns **zero** hits. With only
    `HTTP_PROXY`/`HTTPS_PROXY` set, a sandbox process that talks to a local dev server, a sidecar on `127.0.0.1`, an
    internal registry, or the cloud metadata endpoint `169.254.169.254` will send that traffic to mitmproxy, which will
    fail or hang. This is the classic self-inflicted outage pattern for injected proxies. (The plan document for this
    intent explicitly listed `NO_PROXY` forwarding; it is still unimplemented.)

  - **Recommendation**: Inject a conservative default denylist and allow an operator override via `HOLON_NO_PROXY`.

  - **Proposed Code Change**:

    ```diff
    +DEFAULT_NO_PROXY = "localhost,127.0.0.1,::1,169.254.169.254"
    +
     def _build_proxy_envs(ca_cert_path: str, proxy_url: str) -> dict[str, str]:
         container_ca = _container_ca_path(ca_cert_path)
    +    no_proxy = os.getenv("HOLON_NO_PROXY", DEFAULT_NO_PROXY)
         return {
             "HTTP_PROXY": proxy_url,
             "HTTPS_PROXY": proxy_url,
    +        "NO_PROXY": no_proxy,
    ```

- **✅ APPROVED / PASS — mount scoping and key hygiene (iteration-1 C1/C2 hardening holds)**

  `~/.holon` is no longer mounted wholesale; only `~/.holon/proxy-cache` is shared, read-only. The private key is
  pre-created with `os.open(..., 0o600)` before openssl writes it (so it is never briefly world-readable regardless of
  umask) and re-hardened on the reuse path. Verified live: `-rw------- holon-root-ca.key`. The sidecar publishes
  loopback-only (`-p 127.0.0.1::8080`), which is the correct posture for a readiness probe without exposing an open
  proxy on the LAN. There is deliberately no fallback certificate generator, and a poisoned cache is detected and
  reported with a delete hint — good fail-loud design.

---

### 👥 DevOps & Site Reliability Engineer Review

- **🔴 CRITICAL — `apps/sandbox-executor/entrypoint/role_dispatcher.sh:48-56` + `Dockerfile:33-49`:
  `update-ca-certificates` can never succeed because the image runs as `USER holon` (uid 1000); the documented trust
  mechanism is a silent no-op**

  - **Context**: The new hook is guarded by `|| true`, which converts a guaranteed failure into silence.
    `apps/sandbox-executor/Dockerfile` ends the base stage with `USER holon`, and every agent stage inherits it.
    Executed inside the real image with the CA mounted exactly as `cli.py` mounts it:

    ```text
    $ docker run --rm -u holon -v …/holon-root-ca.crt:/usr/local/share/ca-certificates/holon-root-ca.crt:ro \
        --entrypoint bash holon/agent-antigravity -c 'update-ca-certificates; echo rc=$?'
    whoami: 1000
    Updating certificates in /etc/ssl/certs...
    /usr/sbin/update-ca-certificates: 109: cannot create /etc/ssl/certs/ca-certificates.crt.new: Permission denied
    update-ca-certificates exit=2
    --- after: symlink present? ---
    NO holon symlink
    ```

    So the Debian trust store is never updated. `docs/sandbox/execute_plan.md` states the CA is "trusted inside the
    sandbox (registered by the entrypoint via `update-ca-certificates`)" — that claim is false in the shipped image.
    Every client that resolves trust through `/etc/ssl/certs/ca-certificates.crt` (curl, git-over-HTTPS, Go binaries,
    the `openssl` CLI, `wget`) will reject intercepted traffic — including the executor's own `git push` to GitHub once
    egress is intercepted.

  - **Recommendation**: Do the CA merge where the runtime user is actually allowed to write. Building a merged bundle in
    the entrypoint works as uid 1000 — validated in-container:

    ```text
    bundle built as uid 1000, size 225694
    MERGED-BUNDLE via SSL_CERT_FILE in sandbox python: VERIFIED OK
    ```

    Keep `update-ca-certificates` only as an opportunistic root-mode path (or drop it), and stop documenting it as the
    mechanism.

  - **Proposed Code Change**:

    ```diff
    -HOLON_ROOT_CA_PATH="/usr/local/share/ca-certificates/holon-root-ca.crt"
    -if [ -f "$HOLON_ROOT_CA_PATH" ] && command -v update-ca-certificates &>/dev/null; then
    -    update-ca-certificates >/dev/null 2>&1 || true
    -fi
    +HOLON_ROOT_CA_PATH="/usr/local/share/ca-certificates/holon-root-ca.crt"
    +HOLON_CA_BUNDLE="/tmp/holon-ca-bundle.crt"
    +if [ -f "$HOLON_ROOT_CA_PATH" ]; then
    +    # uid 1000 cannot run update-ca-certificates; merge the system roots with the Holon CA into a
    +    # writable bundle and point OpenSSL/libssl consumers at it. Non-fatal by design.
    +    { cat /etc/ssl/certs/ca-certificates.crt 2>/dev/null || true; cat "$HOLON_ROOT_CA_PATH"; } \
    +        > "$HOLON_CA_BUNDLE" 2>/dev/null || true
    +    export SSL_CERT_FILE="$HOLON_CA_BUNDLE" REQUESTS_CA_BUNDLE="$HOLON_CA_BUNDLE" \
    +           CURL_CA_BUNDLE="$HOLON_CA_BUNDLE"
    +fi
    ```

- **🟡 IMPORTANT — `cli.py:470-505` (`run_docker_container`): teardown is only wired to the `subprocess.run` `finally`,
  so several reachable early-exit paths orphan the sidecar container and its network**

  - **Context**: `get_token_reduction_mounts_and_envs()` (which _creates_ the network and starts the container) is
    called at line 471, but the `try/finally: teardown_token_reduction_proxy()` only wraps `subprocess.run(docker_cmd)`
    at line 504. Everything between the two can leave the process:
    - `get_agent_session_mounts()` (line 486) calls `sys.exit(1)` on macOS when `~/.holon/sessions/antigravity` is
      missing — a routine user error. `SystemExit` is not caught, teardown never runs.
    - the intent-file check (line 478) does `return 1`.
    - `KeyboardInterrupt` between setup and `docker run`.
    - `SIGKILL` / host reboot: `--restart=no` prevents resurrection but the stopped container and the `holon-net-*`
      network persist forever.

    `grep -n "label\|prune\|atexit\|signal" cli.py` → no hits, so there is no ownership metadata and no stale sweep; a
    user who hits this a few times accumulates unremovable `holon-net-*` networks (Docker caps custom networks per
    daemon in practice, and each leaked network also reserves a /16 subnet).

  - **Recommendation**: (1) start the `try` immediately after the resources exist; (2) register `atexit` as a
    belt-and-braces; (3) label run-scoped resources and best-effort sweep stale `holon-proxy-*` / `holon-net-*` at setup
    time.

  - **Proposed Code Change**:

    ```diff
         tr_mounts, tr_envs = get_token_reduction_mounts_and_envs(token_reduce=token_reduce)
         docker_cmd.extend(tr_mounts)
         for k, v in tr_envs.items():
             docker_cmd.extend(["-e", f"{k}={v}"])

    +    try:
         # Intent file mount for intent-creator role
         if role == "intent-creator" and intent_file:
             ...
         print(f"Executing: {' '.join(sanitized_cmd)}")
    -    try:
            result = subprocess.run(docker_cmd)
         return result.returncode
    -    finally:
    -        teardown_token_reduction_proxy()
    +    finally:
    +        teardown_token_reduction_proxy()
    ```

    ```diff
     +    "--label", "holon.token-reduce=1",   # on docker run, and --label on network create
     +atexit.register(teardown_token_reduction_proxy)  # in setup_token_reduction_proxy()
    ```

- **🟢 NIT — `cli.py:316-336`: the first-run image pull is invisible, and the third-party image is tag-pinned only**

  - **Context**: `subprocess.run(docker_run_proxy, capture_output=True, …)` swallows docker's pull progress. On a cold
    cache the CLI prints nothing for the duration of a ~200 MB pull and looks hung; there is no pre-pull in
    `apps/sandbox-executor/build_all_images.sh` / `docker-bake.hcl` either.
  - **Recommendation**: Log an explicit "pulling mitmproxy/mitmproxy:12.2.3 (first run only)" line, or add a
    `docker pull` step to `build_all_images.sh`; consider pinning by digest for reproducibility and supply-chain
    integrity.

- **✅ APPROVED / PASS — sidecar containment**: `--memory=256m --cpus=0.5`, `--log-opt max-size=5m max-file=2`,
  `--restart=no`, `stream_large_bodies=1m`, per-run resource names, and "only remove what this run created"
  (`_SidecarState.network_created`, `"already exists"` ⇒ not owned) are all correct and are covered by tests, including
  the no-op teardown case.

---

### 👥 Principal Engineer Review

- **🔴 CRITICAL — `cli.py:170-181` (`_build_proxy_envs`): `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` / `CURL_CA_BUNDLE` are
  pointed at a file containing **only** the Holon Root CA, which _replaces_ the trust store instead of augmenting it —
  every legitimate HTTPS endpoint then fails verification inside the sandbox**

  - **Context**: `_container_ca_path()` returns `/usr/local/share/ca-certificates/holon-root-ca.crt`, and that single-CA
    file is what gets exported as `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE` and `CURL_CA_BUNDLE`. Unlike
    `NODE_EXTRA_CA_CERTS` (which is _additive_ by design), `SSL_CERT_FILE` overrides OpenSSL's default verify path —
    Python's `ssl.create_default_context()` honours it verbatim — and `REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` are the
    _complete_ bundle for `requests`/`pip`/`httpx`. Reproduced on the host and confirmed to apply in the sandbox image:

    ```text
    A1 legit site, cafile=pub-ca (baseline)                       : VERIFIED OK
    A2 legit site, SSL_CERT_FILE=holon-root-ca.crt (PR injection) : FAILED -> SSLCertVerificationError
         certificate verify failed: unable to get local issuer certificate
    A3 legit site, SSL_CERT_FILE=merged bundle (proposed fix)      : VERIFIED OK

    # inside holon/agent-antigravity (python 3.13.14):
    RESULT default verify cafile honours SSL_CERT_FILE: /holonca/holon-root-ca.crt
    ```

    Net effect when `--token-reduce` is enabled: `pip install`, `requests`-based tooling and any OpenSSL-default client
    inside the sandbox can no longer reach `api.anthropic.com`, `github.com` or `pypi.org`. This is a hard functional
    break of the very traffic the sandbox exists to produce, and it is triggered by an opt-in flag the docs present as
    safe.

  - **Recommendation**: Never point these variables at a single-CA file. Either (a) don't set them at all and rely on
    the system store (which requires the C-3 fix), or (b) build and point at a merged bundle (system roots + Holon CA).
    Option (b) is what I validated. Keep `NODE_EXTRA_CA_CERTS` as-is — it is correct.

  - **Proposed Code Change**:

    ```diff
    -CONTAINER_CA_DIR = "/usr/local/share/ca-certificates"
    +CONTAINER_CA_DIR = "/usr/local/share/ca-certificates"
    +# Merged bundle (system roots + Holon CA) built by role_dispatcher.sh; never point CA_* vars at the
    +# single-CA file, that would replace the trust store instead of extending it.
    +CONTAINER_MERGED_CA_BUNDLE = "/tmp/holon-ca-bundle.crt"

     def _build_proxy_envs(ca_cert_path: str, proxy_url: str) -> dict[str, str]:
    -    container_ca = _container_ca_path(ca_cert_path)
    -    return {
    -        "HTTP_PROXY": proxy_url,
    -        "HTTPS_PROXY": proxy_url,
    -        "NODE_EXTRA_CA_CERTS": container_ca,
    -        "REQUESTS_CA_BUNDLE": container_ca,
    -        "CURL_CA_BUNDLE": container_ca,
    -        "SSL_CERT_FILE": container_ca,
    -    }
    +    # NODE_EXTRA_CA_CERTS is additive; the CA_* bundle vars are not, so they must reference a merged bundle.
    +    return {
    +        "HTTP_PROXY": proxy_url,
    +        "HTTPS_PROXY": proxy_url,
    +        "NODE_EXTRA_CA_CERTS": _container_ca_path(ca_cert_path),
    +    }
    ```

- **🟡 IMPORTANT — `token_reduction/ca_generator.py:52-70` (`_assert_valid_cert`): expiry is never checked, and
  `openssl x509 -noout` returns 0 for an expired certificate — a one-year-old CA is silently reused forever**

  - **Context**: The CA is minted with `-days 365`, and `generate_root_ca()` short-circuits on
    `os.path.exists(cert) and os.path.exists(key)`. `_assert_valid_cert` only checks parseability. Proven:

    ```text
    notAfter=Jan  2 00:00:00 2020 GMT
    plain -noout returncode on EXPIRED cert: 0 '' ''
    -checkend 86400 returncode: 1 Certificate will expire
    ```

    So 12 months after first use, every intercepted TLS session fails with `certificate has expired`, the "poisoned
    cache ⇒ delete ~/.holon/certs" hint never fires, and the user has no idea that a stale file in their home directory
    is the cause.

  - **Recommendation**: Add `-checkend` to the validation and surface an actionable message (or auto-rotate).

  - **Proposed Code Change**:

    ```diff
         if result.returncode != 0:
             raise RuntimeError(
                 f"Root CA certificate at {ca_cert_path} is not a parseable X.509 certificate "
                 f"(openssl: {result.stderr.strip() or 'unknown error'}). "
                 f"Delete {os.path.dirname(ca_cert_path)} and re-run to regenerate a fresh Root CA. {_OPENSSL_INSTALL_HINT}"
             )
    +
    +    expiry = subprocess.run(
    +        [openssl_path, "x509", "-in", ca_cert_path, "-noout", "-checkend", _CA_MIN_LIFETIME_SECONDS],
    +        capture_output=True, text=True, timeout=_OPENSSL_TIMEOUT_SECONDS, check=False,
    +    )
    +    if expiry.returncode != 0:
    +        raise RuntimeError(
    +            f"Root CA at {ca_cert_path} expires within {_CA_MIN_LIFETIME_SECONDS}s "
    +            f"(openssl: {expiry.stdout.strip() or expiry.stderr.strip()}). "
    +            f"Delete {os.path.dirname(ca_cert_path)} and re-run to regenerate a fresh Root CA."
    +        )
    ```

- **🟢 NIT — `token_reduction/ca_generator.py:155-158` (`__main__`): prints "Generated Root CA" even when an existing CA
  was reused**

  - **Context**: `generate_root_ca()` logs `Reusing existing Root CA certificate…`, but the CLI entry point
    unconditionally prints `Generated Root CA:`. Trivially misleading for anyone using the module directly.
  - **Recommendation**: Return or capture the reuse decision (e.g. a second return value or a module-level flag) and
    print accordingly, or just print `Root CA at: …`.

- **🟢 NIT — `cli.py:341-347` (`_attach_external_proxy`): `generate_root_ca()` runs before the reachability probe**

  - **Context**: The attach path mints `~/.holon/certs` (and hard-requires `openssl`) even when no proxy is running, so
    a user who merely exports `HOLON_TOKEN_REDUCE=1` gets host side effects and an openssl-missing error instead of the
    intended "no proxy reachable" message.
  - **Recommendation**: Probe first, then generate the CA.

- **✅ APPROVED / PASS**: The refactor into small, individually testable helpers (`_container_ca_path`,
  `_ca_mount_args`, `_build_proxy_envs`, `_proxy_gateway_url`, `_gateway_host_args`, `_proxy_host_port`,
  `_ensure_network`, `_published_loopback_port`) removed the iteration-1 duplication; `_SidecarState` makes ownership
  explicit; `_wait_for_proxy` replaced `time.sleep` with a bounded, monotonic deadline loop; the platform split
  (`host.docker.internal` vs `172.17.0.1`, `--add-host …:host-gateway` only on Linux) is correct; the fail-loud "no
  fallback certificate" rationale in the module docstring now matches the implementation exactly.

---

### 👥 Product Owner / Product Manager Review

- **🟡 IMPORTANT — `README.md:748-762`, `docs/sandbox/create_plan.md:39-68`, `docs/sandbox/execute_plan.md:55-88`,
  `cli.py:31-36` (`_TOKEN_REDUCE_HELP`): user-facing docs describe a working feature that is unconditionally inert in
  this PR**

  - **Context**: `mitm_addon.py` does not exist anywhere in the repository
    (`find . -name "mitm_addon*" -not -path "*/.venv/*"` → no matches;
    `ls apps/sandbox-executor/src/sandbox_executor/token_reduction/` → `__init__.py`, `ca_generator.py` only). Therefore
    the `--token-reduce` path always raises `FileNotFoundError` and degrades. Executed:

    ```text
    ERROR:sandbox_executor.cli:Token reduction is enabled but could not be configured (FileNotFoundError:
      mitmproxy addon script not found at '…/token_reduction/mitm_addon.py'. …). This run continues with
      DIRECT egress (no TLS interception, no token reduction).
    MOUNTS: []
    ENVS: {}
    ```

    Yet the README says "`--token-reduce` starts a locally-owned mitmproxy sidecar and moves the sandbox onto a per-run
    Docker network so agent responses can be compacted", the docs repeat it, and `--help` promises "Cut agent token
    usage". A user following the documented quickstart gets a full run with zero token reduction and a single ERROR line
    in the log. The PR's own "How to Test" section only checks that the flag is _parsed_ (`./holon execute --help`),
    which is why this gap is invisible in the acceptance criteria.

  - **Recommendation**: Pick one and make code + docs agree: (a) ship `mitm_addon.py` in this PR, or (b) label Phase 1
    honestly — "`--token-reduce` currently bootstraps trust only; the compaction addon lands in Phase 2, so runs
    continue with direct egress" — in the README, both docs pages, and `_TOKEN_REDUCE_HELP`. Option (b) is a
    documentation-only change and keeps the Phase 1/Phase 2 split the resolver intended.

  - **Proposed Code Change**:

    ```diff
     _TOKEN_REDUCE_HELP = (
    -    "Cut agent token usage by routing sandbox egress through a locally-owned mitmproxy sidecar. "
    +    "Route sandbox egress through a locally-owned mitmproxy sidecar (Phase 1 bootstraps the trust "
    +    "store only; response compaction lands in Phase 2, so runs currently fall back to direct egress). "
         "Requires the 'docker' and 'openssl' host binaries and performs LOCAL TLS INTERCEPTION: a Holon "
         "Root CA is generated under ~/.holon/certs and trusted inside the sandbox (the private key never "
         "leaves the host)."
     )
    ```

- **✅ APPROVED / PASS — opt-in contract**: The "host `HTTP_PROXY`/`HTTPS_PROXY` are never interpreted as opt-in" rule
  is implemented exactly as documented, is parametrised by tests over truthy/falsy values, and the "a dead proxy is
  never injected" promise holds in code and in the executed degradation paths. That is a genuinely good safety contract
  for a networking-mutating flag.

---

### 👥 QA & Test Engineer Review

- **🟡 IMPORTANT — `tests/test_token_reduction.py`: no test asserts the _crypto shape_ of the generated CA, which is
  exactly how the C-1 (missing `keyUsage`) and I-1 (expiry) defects survive a green suite**

  - **Context**: `test_ca_generator_produces_parseable_cert_and_private_key_mode` asserts rc=0 from
    `openssl x509 -noout -text`, `"BEGIN CERTIFICATE" in file`, and mode `0o600`. All three pass for a CA that the
    sandbox's own Python refuses to trust. The suite is otherwise strong (111 passed, 44 subtests) — this is the one
    class of assertion that is missing.
  - **Recommendation**: Add assertions on `Key Usage: … Certificate Sign`, `Basic Constraints: … CA:TRUE`, and
    `-checkend` success; ideally add one end-to-end test that spins a TLS server with a leaf signed by the generated CA
    and verifies it with `ssl.create_default_context(cafile=<generated>)` — that single test would have caught C-1.

  - **Proposed Code Change**:

    ```diff
    +def test_ca_generator_emits_usable_trust_anchor(tmp_path):
    +    cert_path, _ = generate_root_ca(cert_dir=str(tmp_path))
    +    text = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-text"],
    +                          capture_output=True, text=True, check=True).stdout
    +    assert "CA:TRUE" in text
    +    assert "Certificate Sign" in text
    +    check = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-checkend", "86400"],
    +                           capture_output=True, text=True)
    +    assert check.returncode == 0, "Root CA must not expire within a day"
    ```

- **🟢 NIT — `tests/test_token_reduction.py:63-77, 118-121`: monkeypatches are applied to process-global stdlib
  modules**

  - **Context**: `cli.os is os` and `cli.subprocess is subprocess` are both `True` (verified), so
    `monkeypatch.setattr(cli.os.path, "isfile", …)`, `monkeypatch.setattr(cli.os.path, "expanduser", …)` and
    `monkeypatch.setattr(cli.subprocess, "run", fake)` replace stdlib behaviour for the _whole interpreter_ for the
    duration of each test — including pytest plugins and any library code loaded transitively. I checked the practical
    blast radius on this Python (3.14): `shutil.which` and `importlib.util.find_spec` still worked, so nothing is broken
    today; the risk is future flakiness that is very hard to attribute.
  - **Recommendation**: Route the sidecar spawn through a tiny indirection
    (`def _spawn_sidecar(cmd): return subprocess.run(cmd, capture_output=True, text=True, check=False)`) and patch
    `cli._spawn_sidecar` / `cli._run_docker` instead of the stdlib; keep `expanduser` patching on a `cli`-level
    `_holon_home()` helper.

- **🟢 NIT — `tests/test_token_reduction.py:196-200`: the "never mount `~/.holon` wholesale" assertions have a hole**

  - **Context**: The guards are `":/home/mitmproxy/.holon " not in joined_run` (trailing space) and
    `"holon-root-ca.key" not in joined_run`. A future regression that mounts the _directory_
    `~/.holon/certs:/home/mitmproxy/.holon/certs:ro` satisfies both while re-leaking the private key.
  - **Recommendation**: Assert structurally — parse every `-v` source and require that any source under the holon home
    equals the proxy-cache path.

  - **Proposed Code Change**:

    ```diff
    -    assert ":/home/mitmproxy/.holon " not in joined_run
    -    assert "holon-root-ca.key" not in joined_run
    +    holon_home = str(host_paths / "home" / ".holon")
    +    for src, dst in zip(run_cmd[run_cmd.index("-v")::3], run_cmd[run_cmd.index("-v") + 1::3]):
    +        if src.startswith(holon_home):
    +            assert src == f"{holon_home}/proxy-cache", f"leaked host path into sidecar: {src} -> {dst}"
    ```

- **✅ APPROVED / PASS**: The `FakeDocker` recorder + `joined()` idiom makes docker-argv assertions readable;
  `reset_sidecar_state` is `autouse` so global state cannot bleed across tests; the degradation paths are asserted at
  the log level (`caplog` + `"DIRECT egress"`), which is what a support engineer will actually see;
  `test_teardown_is_noop_when_this_run_created_nothing` and `test_setup_proxy_network_already_exists_is_not_owned` pin
  the "never touch foreign resources" invariant; `test_host_proxy_env_alone_never_rewrites_sandbox_networking` pins the
  opt-in invariant. `tests/test_cli.py` was updated minimally (`token_reduce=False`) without weakening any prior
  assertion.

---

### 👥 Technical Writer Review

- **🟢 NIT — `docs/sandbox/execute_plan.md:93-95`: the in-page anchor link is broken**

  - **Context**: The link is `[Optional Token Reduction Proxy](#4-optional-token-reduction-proxy--token-reduce)` but the
    heading is
    `### 4. Optional Token Reduction Proxy (\`--token-reduce\`)`. Applying GitHub's slug algorithm (strip ``. ( ) ` ``,
    lowercase, spaces → hyphens) yields `4-optional-token-reduction-proxy---token-reduce` — **three** hyphens before
    `token-reduce`, not two. Verified with a slugger replication:

    ```text
    computed anchor: 4-optional-token-reduction-proxy---token-reduce
    link in doc   : #4-optional-token-reduction-proxy--token-reduce
    MATCH: False
    ```

  - **Recommendation**: Fix the anchor, or drop the anchor and reference the section by name.

- **🟡 IMPORTANT — `docs/sandbox/execute_plan.md:64-67`, `README.md:753-756`: the docs assert a trust mechanism and a
  containment property that the code does not deliver**

  - **Context**: Two sentences are factually wrong today: (1) "trusted inside the sandbox (registered by the entrypoint
    via `update-ca-certificates`)" — that command exits 2 as uid 1000 (see C-3); (2) "The Root CA private key … is never
    mounted into any container" — true today only because the sidecar never receives the CA at all, which is itself the
    defect in I-2. Documentation that names a specific mechanism will be the first thing a debugging user checks.
  - **Recommendation**: After fixing C-3/I-2, restate the mechanism precisely ("merged into `/tmp/holon-ca-bundle.crt`
    by the entrypoint; `NODE_EXTRA_CA_CERTS` for Node-based agents") and scope the containment claim to the sandbox.

- **✅ APPROVED / PASS**: Structure and tone are consistent with the existing docs (`> [!WARNING]` / `[!IMPORTANT]`
  callouts, env-contract tables, prerequisites + isolation bullets), the `--token-reduce`-not-on-`intent` note is
  accurate, the platform-specific gateway table matches `_proxy_gateway_url()` exactly, and `npx prettier --check` is
  clean. The "Prerequisites … the CLI logs an actionable error and the run continues with direct egress" paragraph is an
  accurate description of the implemented degradation behaviour.

---

### 👥 Developer Advocate Review

- **🟡 IMPORTANT — `cli.py:170-181` + docs: proxy injection is uppercase-only, so `curl` and other lowercase-only
  clients silently bypass the proxy**

  - **Context**: `_build_proxy_envs` sets only `HTTP_PROXY`/`HTTPS_PROXY`. Verified inside the sandbox image:

    ```text
    uppercase only: curl: (6) Could not resolve host: example.invalid      # proxy ignored
    lowercase only: curl: (7) Failed to connect to 127.0.0.1 port 9         # proxy honoured
    no proxy:       curl: (6) Could not resolve host: example.invalid
    ```

    For a developer, "I enabled token reduction and my curl/Go/wget traffic still went direct" is an invisible partial
    failure — the worst DX outcome, because nothing is reported.

  - **Recommendation**: Set the lowercase aliases alongside the uppercase ones (and `no_proxy` with `NO_PROXY` from the
    Security finding).

  - **Proposed Code Change**:

    ```diff
         return {
             "HTTP_PROXY": proxy_url,
             "HTTPS_PROXY": proxy_url,
    +        "http_proxy": proxy_url,
    +        "https_proxy": proxy_url,
    +        "NO_PROXY": no_proxy,
    +        "no_proxy": no_proxy,
             "NODE_EXTRA_CA_CERTS": container_ca,
         }
    ```

- **🟢 NIT — `cli.py:177` (`CURL_CA_BUNDLE`): the variable name implies curl honours it; it does not**

  - **Context**: `CURL_CA_BUNDLE` is consumed by `requests`/`pip`, not by curl (see the curl matrix above — curl reads
    `http_proxy`/`https_proxy` and `--cacert`). Combined with the C-2 replacement hazard, this entry is both misleading
    and harmful.
  - **Recommendation**: Drop it, or rename the intent in a comment and keep it only if the merged-bundle fix (C-2)
    lands.

- **✅ APPROVED / PASS**: `_TOKEN_REDUCE_HELP` discloses TLS interception and the openssl/docker prerequisites up front
  — exactly what a developer needs before opting in; the `HOLON_TOKEN_REDUCE` / `HOLON_PROXY_URL` contract is small,
  documented in all three surfaces, and the error strings name the failing host/port and the remediation ("Start the
  proxy or point `HOLON_PROXY_URL` at it"), which is genuinely actionable.

---

### 👥 Release Manager / Release Coordinator Review

- **🟡 IMPORTANT — Phase 1 / Phase 2 staging: the flag is released as GA while its enabling artifact is deferred**

  - **Context**: The resolver explicitly deferred `mitm_addon.py` to Phase 2 and made Phase 1 "fail loudly". That is the
    right engineering call, but the _release_ consequence is that `develop` gains a user-visible flag that is a
    guaranteed no-op, plus three docs pages describing Phase 2 behaviour. Anyone who enables it in automation gets a
    green run with zero token reduction — a silent metric regression rather than a loud one.
  - **Recommendation**: Land the doc/help wording from the PO finding in this PR so the release note and the CLI agree,
    and state in the PR description that Phase 1 delivers trust bootstrap + degradation scaffolding only. Also note the
    PR bundles harness artifacts (`plans/`, `executions/`, `holon-knowledge/ledger/*.jsonl`) with code; that is repo
    convention, but call it out in the release summary so the changelog is not read as "the agent implemented a 262-line
    plan for the CLI".

- **✅ APPROVED / PASS**: Rollback posture is good — the feature is strictly opt-in, no default sandbox path changes, no
  schema/migration, and teardown removes run-scoped resources. Nothing here requires a deploy-ordering runbook.

---

### 👥 Technical Support Engineer / Customer Success Lead Review

- **🟡 IMPORTANT — `cli.py:437-443` + docs: interception of credential-bearing agent traffic has no documented redaction
  or retention story**

  - **Context**: The sandbox carries `GITHUB_TOKEN`, `HOLON_AGENT_KEY` and vendor API keys (see `run_docker_container`
    env forwarding and the sanitising printer at line 494, which exists precisely because these are secrets). Enabling
    `--token-reduce` routes every one of those bearer tokens through mitmproxy, and the design shares
    `~/.holon/proxy-cache` with it. The WARNING blocks disclose "TLS interception" but not "your agent's credentials
    transit and may be persisted by this proxy". Support will own the "did my token leak?" ticket, and the compliance
    auditor will ask what is in the cache and for how long.
  - **Recommendation**: Document (a) what the sidecar writes to `~/.holon/proxy-cache`, (b) retention/rotation, (c) that
    the Phase 2 addon must redact `Authorization`/`x-api-key` headers and secret-bearing response bodies, and (d) how to
    purge (`rm -rf ~/.holon/proxy-cache`). Consider a `--token-reduce` confirmation line printed once per host.

- **✅ APPROVED / PASS**: The degradation messages are the strongest part of this PR from a support standpoint — they
  name the subsystem, the exception type, the concrete path/host:port, the consequence ("DIRECT egress, no TLS
  interception, no token reduction") and the remediation ("Re-run without --token-reduce").
  `test_env_var_opt_in_unreachable_proxy_degrades_to_direct_egress` and
  `test_flag_opt_in_sidecar_failure_degrades_to_direct_egress` lock that wording in.

---

## 3. 🏆 Overall Verdict

**❌ CHANGES REQUESTED**

Iteration 1's fixes are real and verified in code: the `~/.holon` leak, the poisoned fallback certificate, the
dead-proxy injection, the shared network name and the opt-in contract are all genuinely resolved, the suite is green
(111 passed / 44 subtests), and ruff/format/prettier/`bash -n` are clean. The engineering skeleton — per-run resource
ownership, bounded readiness probing, containment flags, fail-loud CA handling, honest degradation — is sound and worth
keeping.

What blocks merge is that the **trust bootstrap itself does not work**, and three of the four root causes are only
visible by executing TLS handshakes inside the real sandbox image:

1. **C-1** The generated Root CA has no `keyUsage` extension → the sandbox's own Python 3.13/OpenSSL 3.5 rejects it as a
   trust anchor (`CA cert does not include key usage extension`). Fix validated in-container.
2. **C-2** `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` point at a single-CA file, which _replaces_ the trust
   store → every legitimate HTTPS endpoint fails (`unable to get local issuer certificate`). Merged-bundle fix
   validated.
3. **C-3** `update-ca-certificates` cannot run as the image's `USER holon` (uid 1000) → exit 2, `Permission denied`, no
   symlink; the documented mechanism is a silent no-op and curl/git/Go clients never trust the CA.
   Merged-bundle-in-entrypoint fix validated as uid 1000.

Plus the two scope/architecture items that decide whether Phase 1 is shippable as-is: the sidecar never receives the CA
it needs to sign intercepted traffic (**I-2**), and the flag is unconditionally inert while three docs pages and
`--help` advertise it as working (**I-1**).

**Merge-blocking checklist**

1. Add `keyUsage=critical,keyCertSign,cRLSign` (+ `basicConstraints=critical,CA:TRUE`) to CA generation, and a test that
   asserts the generated cert is usable as a trust anchor. (C-1)
2. Stop pointing `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` at the single-CA file; use a merged bundle or
   rely on the system store. (C-2)
3. Make the in-container CA registration work as uid 1000 and correct the docs that claim `update-ca-certificates` does
   it. (C-3)
4. Give the sidecar the Holon CA via a dedicated mitmproxy confdir, and re-scope the "private key never mounted into any
   container" claim to the sandbox. (I-2)
5. Reconcile docs/`--help` with actual Phase 1 behaviour (ship `mitm_addon.py`, or state that runs currently fall back
   to direct egress). (I-1)

**Strongly recommended in the same pass** (cheap, high leverage): `NO_PROXY`/`no_proxy` defaults (I-3), lowercase proxy
aliases (I-4), teardown coverage for the `sys.exit(1)` / `return 1` early-exit paths plus labels/stale sweep (I-5), CA
expiry check via `-checkend` (I-6), and the credential-retention paragraph (I-7).

**Counts:** CRITICAL=3, IMPORTANT=7, NIT=7

---

## 4. Appendix — Empirical Verification Log

All commands were executed in the PR head worktree at `6e25912`; nothing outside `/tmp` was written and no source file
was modified.

| #   | Claim                                                         | Command                                                                                                                                                                                 | Result                                                                                                                              |
| :-- | :------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Suite/lint clean                                              | `uv run pytest apps/sandbox-executor/tests -q`; `uv run ruff check .`; `uv run ruff format --check .`; `npx prettier --check README.md docs/sandbox/*.md`; `bash -n role_dispatcher.sh` | 111 passed + 44 subtests; all checks passed; 17 files formatted; prettier clean; bash syntax OK                                     |
| 2   | `mitm_addon.py` absent                                        | `find . -name "mitm_addon*" -not -path "*/.venv/*"`; `ls …/token_reduction/`                                                                                                            | no matches; only `__init__.py`, `ca_generator.py`                                                                                   |
| 3   | `--token-reduce` always degrades                              | `PYTHONPATH=… python3 -c "cli.get_token_reduction_mounts_and_envs(token_reduce=True)"` (temp `HOME`)                                                                                    | `MOUNTS: [] ENVS: {}` + `ERROR … FileNotFoundError … DIRECT egress`                                                                 |
| 4   | Sandbox runs as uid 1000                                      | `docker run --rm --entrypoint id holon/agent-antigravity`                                                                                                                               | `uid=1000(holon)`                                                                                                                   |
| 5   | `update-ca-certificates` fails as uid 1000                    | `docker run -u holon -v holon-root-ca.crt:/usr/local/share/ca-certificates/… --entrypoint bash … -c 'update-ca-certificates'`                                                           | `Permission denied` on `/etc/ssl/certs/ca-certificates.crt.new`, `exit=2`, no `holon` symlink                                       |
| 6   | Generated CA lacks `keyUsage`                                 | `openssl x509 -in holon-root-ca.crt -noout -text`                                                                                                                                       | only SKI, AKI, `Basic Constraints: critical CA:TRUE`                                                                                |
| 7   | Sandbox Python rejects that CA as anchor                      | `docker run -i -u holon … --entrypoint python3 holon/agent-antigravity /certs/probe.py` (TLS server with a Holon-signed leaf, client `cafile=holon-root-ca.crt`)                        | `python 3.13.14 \| OpenSSL 3.5.6`; `FAILED … CA cert does not include key usage extension`                                          |
| 8   | `keyUsage` fix works                                          | same probe with a CA minted using `-addext keyUsage=critical,keyCertSign,cRLSign`                                                                                                       | `FIXED CA … VERIFIED OK`                                                                                                            |
| 9   | `SSL_CERT_FILE` overrides the default store                   | `ssl.get_default_verify_paths()` after setting `SSL_CERT_FILE` (host + container)                                                                                                       | returns the injected single-CA path                                                                                                 |
| 10  | Single-CA override breaks legit sites; merged bundle fixes it | local TLS server signed by a separate "public" CA; clients A1/A2/A3                                                                                                                     | A1 `VERIFIED OK`; A2 `FAILED … unable to get local issuer certificate`; A3 `VERIFIED OK`                                            |
| 11  | Merged bundle works as uid 1000 in the sandbox                | `cat /etc/ssl/certs/ca-certificates.crt <holon-ca> > /tmp/holon-bundle.crt` + `SSL_CERT_FILE` probe in `holon/agent-antigravity`                                                        | `bundle built as uid 1000, size 225694`; `MERGED-BUNDLE … VERIFIED OK`                                                              |
| 12  | `-noout` passes on expired certs                              | `openssl req -x509 -not_before 20200101000000Z -not_after 20200102000000Z …` then `-noout` / `-checkend 86400`                                                                          | `-noout` rc=**0**; `-checkend` rc=**1** (`Certificate will expire`)                                                                 |
| 13  | curl ignores uppercase proxy vars                             | `docker run -u holon … bash -c 'HTTPS_PROXY=http://127.0.0.1:9 curl http://example.invalid/'` vs lowercase                                                                              | uppercase → `(6) Could not resolve host` (proxy bypassed); lowercase → `(7) Failed to connect to 127.0.0.1 port 9` (proxy honoured) |
| 14  | No `NO_PROXY` anywhere                                        | `grep -rn "NO_PROXY\|no_proxy" apps docs README.md`                                                                                                                                     | zero hits                                                                                                                           |
| 15  | No labels / prune / atexit / signal handling                  | `grep -n "label\|prune\|atexit\|signal" cli.py`                                                                                                                                         | zero hits                                                                                                                           |
| 16  | Monkeypatches hit process-global stdlib                       | `python3 -c "cli.os is os; cli.subprocess is subprocess"`                                                                                                                               | both `True` (no current breakage observed in `shutil.which` / `importlib.util.find_spec`)                                           |
| 17  | Broken docs anchor                                            | GitHub slugger replication on `### 4. Optional Token Reduction Proxy (\`--token-reduce\`)`                                                                                              | computed `…proxy---token-reduce` vs linked `…proxy--token-reduce` → mismatch                                                        |
| 18  | Sidecar image availability                                    | `docker manifest inspect mitmproxy/mitmproxy:12.2.3`                                                                                                                                    | inconclusive (no network/registry access from this environment) — reported as a NIT only, not as a defect                           |
