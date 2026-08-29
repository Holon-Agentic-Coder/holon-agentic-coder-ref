# TASK: PR Review Resolver Subagent — Iteration 1 (PR #48)

You are an isolated resolver subagent running in the PR head worktree. You have already-validated review findings below.
Implement the fixes, verify empirically, commit once, and push.

Working directory: the PR head worktree (branch `I-1787928238-token-reduction-phase1/P-.../E-.../_`).

## Ground rules

- Only touch: `apps/sandbox-executor/src/sandbox_executor/cli.py`,
  `apps/sandbox-executor/src/sandbox_executor/token_reduction/*`, `apps/sandbox-executor/tests/*`,
  `apps/sandbox-executor/entrypoint/role_dispatcher.sh`, `docs/sandbox/*.md`, `README.md`.
- Do NOT touch `holon-knowledge/ledger/*.jsonl`, `plans/*.md`, `executions/*.md` (harness-generated, out of scope).
- Do NOT create deprecation shims, migration notices, or backwards-compat fallback stubs (hard repo invariant).
- Keep `line-length = 120` (ruff). No new dependencies.
- Do NOT weaken or delete existing tests.

## 🔴 CRITICAL fixes (all mandatory)

### C1 — Sidecar bind-mount leaks the CA private key and agent auth sessions (cli.py `setup_token_reduction_proxy`)

`-v {~/.holon}:/home/mitmproxy/.holon` is read-WRITE and its subtree contains `~/.holon/certs/holon-root-ca.key` (CA
private key) and `~/.holon/sessions/antigravity` (agent auth session store, see `get_agent_session_mounts`).

Fix: mount ONLY a narrow proxy cache directory, read-only. The proxy never needs the private key.

```python
proxy_cache_dir = os.path.join(holon_home, "proxy-cache")
os.makedirs(proxy_cache_dir, exist_ok=True)
...
"-v", f"{proxy_cache_dir}:/home/mitmproxy/.holon/proxy-cache:ro",
```

### C2 — Invalid fallback certificate is cached forever; key is world-readable (`ca_generator.py`)

`_generate_fallback_cert` writes truncated, unparseable PEM blobs, then `generate_root_ca` returns success. Because of
the `os.path.exists(...)` early-return, the bogus files are cached permanently and every TLS client in the sandbox fails
with an opaque error. Empirically confirmed: `openssl x509 -in <fallback> -noout -text` fails.

Fix:

- DELETE `_generate_fallback_cert` entirely (no shim, no stub).
- Probe `shutil.which("openssl")` first; if missing raise `RuntimeError` with an actionable install hint (macOS
  `brew install openssl`, Debian `apt-get install openssl`).
- Catch `subprocess.CalledProcessError` and `subprocess.TimeoutExpired` explicitly (NOT blanket `Exception`), re-raise
  as `RuntimeError` including stderr. Add `timeout=60` to the openssl call.
- Create the key with mode `0o600` (`os.open(..., 0o600)` semantics or `os.chmod(ca_key_path, 0o600)` after generation).
- Add `_assert_valid_cert(ca_cert_path)` that runs `openssl x509 -in <path> -noout` and raises `RuntimeError` if the
  artifact is not a parseable certificate; call it before returning (both on fresh generation and when reusing an
  existing cert, so a previously poisoned cache is detected and reported with a clear "delete ~/.holon/certs" hint).
- Update the module docstring so it matches actual behaviour (it currently promises behaviour it does not implement).

### C3 — Sidecar launched against a non-existent addon; dead proxy reported as healthy (cli.py)

`mitm_addon.py` does not exist anywhere in the repo, so Docker creates an empty directory at the bind source,
`mitmdump -s /tmp/mitm_addon.py` exits, but `docker run -d` already returned 0 → the agent is moved onto `holon-net`
with `HTTP_PROXY` pointing at a dead proxy = total network failure. Same outcome in the `returncode != 0` branch, which
still injects `HTTP_PROXY=http://172.17.0.1:8080`.

Fix:

- `if not os.path.isfile(addon_path): raise FileNotFoundError(...)` with the expected path in the message.
- On `proxy_spawn.returncode != 0`: raise `RuntimeError` including `proxy_spawn.stderr.strip()` and the hint "Re-run
  without --token-reduce to execute with direct egress." Do NOT inject a dead proxy URL.
- Replace `time.sleep(1.0)` with a real readiness probe `_wait_for_proxy(host, port, timeout)` using a TCP
  `socket.create_connection` retry loop (0.5s interval, 15s timeout) against the container name/port; if it never
  becomes ready, `docker rm -f` the sidecar you started and raise `RuntimeError`.
- Move `import time` to module scope (or drop it if unused after the probe refactor).

### C4 — Non-opt-in code path silently rewrites sandbox networking for every existing user (cli.py)

The `elif os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")` branch injects proxy + CA env vars into the sandbox for
any user who merely exports an unrelated host proxy variable. This is an undocumented, non-opt-in behaviour change to
every existing `holon plan` / `holon execute` run.

Fix: make it strictly opt-in. Apply proxy/CA injection ONLY when `token_reduce` is true, OR when the user explicitly
opts in via `HOLON_TOKEN_REDUCE` in `("1","true","yes","on")`. Never infer opt-in from `HTTP_PROXY`/`HTTPS_PROXY` alone.
When opted in via env var but the proxy is unreachable, log an actionable error and return empty mounts/envs (direct
egress) rather than a dead proxy.

## 🟡 IMPORTANT fixes (implement all)

- **I1 Platform-correct gateway**: `172.17.0.1` is Linux-only and unreachable on Docker Desktop/macOS (this file already
  branches on `sys.platform == "darwin"`). Add a helper that returns `http://host.docker.internal:8080` on
  darwin/windows and `http://172.17.0.1:8080` on Linux, and add `--add-host=host.docker.internal:host-gateway` to the
  target container mounts on Linux.
- **I2 Concurrency / cleanup**: hardcoded singleton names `holon-proxy` / `holon-net` make concurrent runs destroy each
  other, and the network is never reclaimed. Derive per-run names with a suffix (e.g. `os.getpid()` or a short uuid4
  hex), track whether THIS run created the network, and in the `finally` teardown remove only the sidecar/network this
  run created. Never `docker rm -f` a container you did not start.
- **I3 Sidecar containment**: add resource/log bounds to the `docker run` for the proxy: `--memory=256m`, `--cpus=0.5`,
  `--log-opt max-size=5m`, `--log-opt max-file=2`, `--restart=no`, and `--read-only` is NOT required (skip if it breaks
  mitmproxy). Also add mitmproxy posture flags `--set stream_large_bodies=1m` so large bodies are streamed not buffered.
- **I4 Debian trust store is inert**: the image is `python:3.13-slim` (Debian) with `ca-certificates`; a file dropped in
  `/usr/local/share/ca-certificates/` only takes effect after `update-ca-certificates`. In
  `apps/sandbox-executor/entrypoint/role_dispatcher.sh`, if the cert exists at the container path and
  `update-ca-certificates` is available, run it (guarded, non-fatal, `|| true`) before dispatching the role.
- **I5 De-duplicate**: the two branches duplicate CA path + 6 env var assignments. Extract one helper
  `_build_proxy_envs(ca_cert_path, proxy_url) -> dict[str, str]` and one `_ca_mount_args(ca_cert_path) -> list[str]`
  used by both paths.
- **I6 No silent degradation**: every `except Exception` in the token-reduction paths must become a narrow exception
  type, log at `error` (not `warning`) with an actionable message stating that the run continues with DIRECT egress, and
  return empty mounts/envs.
- **I7 Tests** (`apps/sandbox-executor/tests/test_token_reduction.py`): add coverage for the previously untested paths —
  - `setup_token_reduction_proxy` with `subprocess.run` mocked: asserts addon-missing raises `FileNotFoundError`;
    asserts non-zero spawn raises `RuntimeError`; asserts readiness probe failure raises and does NOT return proxy envs.
  - `generate_root_ca` with `shutil.which` patched to None → raises `RuntimeError`.
  - `generate_root_ca` output is a parseable certificate (assert via `openssl x509 -in ... -noout` returncode 0) and the
    key file mode is `0o600`.
  - opt-in logic: `get_token_reduction_mounts_and_envs(token_reduce=False)` with `HTTP_PROXY` set returns `([], {})`;
    with `HOLON_TOKEN_REDUCE=1` it attempts configuration.
  - Use pytest's built-in `tmp_path` fixture for new tests (replace the hand-rolled `mkdtemp`/`rmtree` fixture too).
- **I8 Docs**: document `--token-reduce` and the `HOLON_TOKEN_REDUCE` / `HOLON_PROXY_URL` env contract in
  `docs/sandbox/create_plan.md`, `docs/sandbox/execute_plan.md`, and the CLI usage section of `README.md`. State
  explicitly that `--token-reduce` performs local TLS interception against a locally-owned proxy and that the Root CA
  private key stays on the host. Keep markdown prettier-clean (line width 120).
- **I9 Help text**: make the `--token-reduce` help text state the prerequisite (docker + openssl) and the TLS
  interception side effect.

## 🟢 NITs (fix if trivial)

- Function-local `from ... import generate_root_ca` duplicated → import at module scope via the package re-export.
- `docker network create` discards stderr → capture and log at debug, and treat "already exists" as success.

## Explicitly NOT doing (record as skipped, with rationale)

- Plan/ledger metric disagreements and the bundled `plans/`, `executions/`, `ledger/*.jsonl` files: harness-generated
  artifacts, repo convention commits them; out of code-review scope.
- Adding `--token-reduce` to the `intent` subcommand: not in the Phase 1 plan scope.
- Shipping a full `mitm_addon.py` implementation: Phase 2 scope; Phase 1 must fail loudly until it exists (C3).

## Verification (MANDATORY before commit)

```bash
cd <worktree root>
PYTHONPATH=apps/sandbox-executor/src uv run pytest apps/sandbox-executor/tests -q   # must be all green
uv run ruff check .                                                                 # must be clean
uv run ruff format --check .                                                        # must be clean (or run ruff format .)
npx prettier --check "docs/sandbox/*.md" "README.md"                                # must be clean (or run --write)
```

Also empirically prove C2 is fixed:

```bash
python3 -c "
import sys,tempfile,subprocess,os;sys.path.insert(0,'apps/sandbox-executor/src')
from sandbox_executor.token_reduction.ca_generator import generate_root_ca
d=tempfile.mkdtemp();c,k=generate_root_ca(cert_dir=d)
print('cert parseable:', subprocess.run(['openssl','x509','-in',c,'-noout','-text'],capture_output=True).returncode==0)
print('key mode:', oct(os.stat(k).st_mode & 0o777))"
```

## Commit & push

```bash
git add -A
git commit -m "fix: apply validated PR review suggestions (Iteration 1)"
git push origin HEAD
```

`git push origin HEAD` pushes to the existing PR feature branch only. Never push to `main` or `develop`.

## Final message format

Print exactly:

```
APPLIED: <comma separated ids e.g. C1,C2,C3,C4,I1,...>
SKIPPED: <ids + one-line rationale each>
TESTS: <pytest summary line>
LINT: <ruff + prettier status>
COMMIT: <short sha>
PUSHED: <yes|no>
```
