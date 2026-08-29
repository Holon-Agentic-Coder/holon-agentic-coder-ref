# TASK: PR Review Resolver Subagent — Iteration 2 (PR #48)

You are an isolated resolver subagent running in the PR head worktree. Iteration 1 fixes are already committed
(`6e25912`). The findings below have been **independently re-validated against the current code** — implement them,
verify empirically, commit once, push.

## Ground rules

- Only touch: `apps/sandbox-executor/src/sandbox_executor/cli.py`,
  `apps/sandbox-executor/src/sandbox_executor/token_reduction/*`, `apps/sandbox-executor/tests/*`,
  `apps/sandbox-executor/entrypoint/role_dispatcher.sh`, `docs/sandbox/*.md`, `README.md`.
- Do NOT touch `holon-knowledge/ledger/*.jsonl`, `plans/*.md`, `executions/*.md` (harness-generated, out of scope).
- Do NOT create deprecation shims, migration notices, or backwards-compat fallback stubs (hard repo invariant).
- Do NOT commit the untracked `apps/sandbox-executor/uv.lock` artifact.
- `line-length = 120` (ruff). No new dependencies. Do not weaken or delete existing tests.

## 🔴 CRITICAL fixes (all mandatory)

### C5 — Generated Root CA has no `keyUsage` extension (`ca_generator.py`)

Empirically confirmed: the generated cert has `X509v3 Basic Constraints: critical CA:TRUE` but **no**
`X509v3 Key Usage`. Several TLS stacks (BoringSSL/Node, Go, OpenSSL in strict/`purpose` modes) refuse such a cert as a
trust anchor, so the whole trust bootstrap can fail even when everything else is correct.

Fix: add explicit CA extensions to the `openssl req -x509` invocation:

```
"-addext", "basicConstraints=critical,CA:TRUE",
"-addext", "keyUsage=critical,keyCertSign,cRLSign",
"-addext", "subjectKeyIdentifier=hash",
```

Also add a `-days` value that is not silently reused forever (see I10 for the expiry check).

### C6 — `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` / `CURL_CA_BUNDLE` point at a Holon-CA-ONLY file, replacing the trust store

Empirically confirmed in `_build_proxy_envs`: all three point at the single-cert mount
`/usr/local/share/ca-certificates/holon-root-ca.crt`. `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` **replace** the trust
store rather than augmenting it, so once `--token-reduce` is enabled every legitimate HTTPS endpoint (github.com,
api.openai.com, the agent's own LLM endpoint) fails verification inside the sandbox. This is a total-outage class bug.

Fix — build a **merged** bundle inside the container at role start, in the entrypoint (which runs as the unprivileged
`holon` user and therefore cannot write to `/etc/ssl/certs`):

1. In `cli.py::_build_proxy_envs`, keep `NODE_EXTRA_CA_CERTS` pointing at the read-only Holon CA mount (that variable
   _augments_ Node's built-in roots — correct usage), and point `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` /
   `CURL_CA_BUNDLE` at a merged bundle path, e.g. `/home/holon/.holon-ca-bundle.crt`, which the entrypoint materialises.
2. In `entrypoint/role_dispatcher.sh`, before role dispatch: if the Holon CA file exists, concatenate the image's system
   bundle (`/etc/ssl/certs/ca-certificates.crt`, if readable) plus the Holon CA into
   `${HOLON_CA_BUNDLE_PATH:-/home/holon/.holon-ca-bundle.crt}`, `chmod 600` it, and `export` the three variables to it.
   If the system bundle is missing, still write the merged bundle from whatever exists and keep going. Failures must be
   non-fatal but logged to stderr (no `>/dev/null 2>&1 || true` blanket silence).
3. Remove the now-obsolete `update-ca-certificates` block (see C7).

### C7 — `update-ca-certificates` can never succeed: the image runs as `USER holon` (uid 1000)

Empirically confirmed: `Dockerfile:47` sets `USER holon`, so `update-ca-certificates` (which writes root-owned
`/etc/ssl/certs`) always fails, and the current guard `>/dev/null 2>&1 || true` makes it a **silent no-op** — the
documented trust mechanism does not exist.

Fix: delete that block entirely (no shim) and rely on the merged-bundle mechanism from C6 plus `NODE_EXTRA_CA_CERTS`.
Correct the docs wherever they claim the Debian store is refreshed.

## 🟡 IMPORTANT fixes (implement all)

- **I10 Expiry is never checked** (`ca_generator.py::_assert_valid_cert`): `openssl x509 -noout` returns 0 for an
  expired cert, so a stale CA is reused forever. Add `openssl x509 -checkend <N>` (reject if it expires within 30 days)
  and, when the cached CA is expired/near-expiry, regenerate it instead of reusing it (delete the stale key/cert pair
  first, then regenerate). Keep the actionable error for the unrecoverable case.
- **I11 Sidecar is never given the Holon Root CA**: mitmproxy would sign leaves with its own ephemeral CA that the
  sandbox does not trust, so interception can never work. Build a combined `mitmproxy-ca.pem` (key + cert) plus
  `mitmproxy-ca-cert.pem` under `~/.holon/proxy-ca/` and bind-mount ONLY those two files read-only into
  `/home/mitmproxy/.mitmproxy/`. Add a code comment stating explicitly that a MITM proxy inherently requires the CA
  private key, that the mount is limited to those two files, and that the key must never be exposed to the _agent_
  container. Set `0600` on the combined file.
- **I12 No `NO_PROXY`**: add `NO_PROXY` **and** lowercase `no_proxy` = `localhost,127.0.0.1,::1,169.254.169.254` so
  loopback tooling and link-local metadata endpoints are not force-proxied.
- **I13 Lowercase proxy vars**: `curl` and many CLIs read `http_proxy`/`https_proxy` only. Emit lowercase duplicates of
  `HTTP_PROXY`/`HTTPS_PROXY` (and keep the uppercase ones).
- **I14 Teardown gaps** (`run_docker_container`): the sidecar teardown is wired only to the `finally` of the final
  `subprocess.run`. Any earlier `return`/exception (missing docker, missing token, image-name resolution, arg
  sanitisation) orphans the sidecar container and network. Restructure so that once `setup_token_reduction_proxy()` has
  succeeded, `teardown_token_reduction_proxy()` runs on **every** exit path (wrap the remainder of the function body in
  `try/finally`).
- **I15 Crypto-shape tests** (`tests/test_token_reduction.py`): add assertions that the generated CA actually carries
  `X509v3 Key Usage` with `Certificate Sign`/`CRL Sign`, `Basic Constraints: CA:TRUE`, and is not expiring within 30
  days (parse via `openssl x509 -noout -text` / `-checkend`). Add a test that a near-expiry cached CA is regenerated.
  Add a test that `_build_proxy_envs` never points `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` at the single-cert CA path, and
  that `NO_PROXY`/`no_proxy` and lowercase proxy vars are present.
- **I16 Docs must describe reality**: `--token-reduce` is currently **inert by design** — `mitm_addon.py` is Phase 2, so
  the preflight raises `FileNotFoundError` and the run degrades to direct egress. State that explicitly in `README.md`,
  `docs/sandbox/create_plan.md`, `docs/sandbox/execute_plan.md` and `_TOKEN_REDUCE_HELP` (mark the flag **experimental /
  not yet functional**), describe the merged-bundle trust mechanism (not `update-ca-certificates`), state that the CA
  private key is mounted read-only into the proxy sidecar and never into the agent container, and state the flow-log
  retention/redaction posture (proxy cache is read-only; no credential redaction is implemented yet — Phase 2 — so
  `--token-reduce` must only be used against a locally-owned proxy).
- **I17 Broken anchor** in `docs/sandbox/execute_plan.md` (the in-page anchor link does not resolve) — fix it.

## 🟢 NITs (fix if cheap)

- `ca_generator.py::__main__` prints "Generated Root CA" even when reusing an existing CA → report generated vs reused.
- `_attach_external_proxy` calls `generate_root_ca()` before the reachability probe → probe first, then generate.
- Log the first-run `mitmproxy/mitmproxy:12.2.3` image pull so it is not invisible (log at info before the
  `docker run`).
- `CURL_CA_BUNDLE` is honoured by `requests`, not by `curl` itself → add a one-line comment so the next reader does not
  assume otherwise.
- Tests monkeypatch process-global stdlib modules → scope patches to the module under test where practical.

## Explicitly NOT doing (record as skipped, with rationale)

- Shipping `mitm_addon.py` / making `--token-reduce` functional: Phase 2 scope. Phase 1 must keep failing preflight
  loudly, and the docs now say the flag is experimental.
- Digest-pinning `mitmproxy/mitmproxy:12.2.3`: requires a registry-promotion workflow outside this PR's scope.
- Bundled `plans/`, `executions/`, `ledger/*.jsonl` and plan/ledger metric drift: harness-generated artifacts.

## Verification (MANDATORY before commit)

```bash
cd <worktree root>
PYTHONPATH=apps/sandbox-executor/src uv run pytest apps/sandbox-executor/tests -q   # all green
uv run ruff check . && uv run ruff format --check .                                 # clean
npx prettier --check "docs/sandbox/*.md" "README.md"                                # clean (or --write)
bash -n apps/sandbox-executor/entrypoint/role_dispatcher.sh                         # clean
```

Prove C5 + I10 empirically and include the output in your final message:

```bash
python3 -c "
import sys,tempfile,subprocess,os;sys.path.insert(0,'apps/sandbox-executor/src')
from sandbox_executor.token_reduction.ca_generator import generate_root_ca
d=tempfile.mkdtemp();c,k=generate_root_ca(cert_dir=d)
t=subprocess.run(['openssl','x509','-in',c,'-noout','-text'],capture_output=True,text=True).stdout
print('keyUsage present:', 'Key Usage' in t, '| certSign:', 'Certificate Sign' in t, '| CA:TRUE:', 'CA:TRUE' in t)
print('checkend 30d:', subprocess.run(['openssl','x509','-in',c,'-noout','-checkend',str(30*86400)],capture_output=True).returncode==0)
print('key mode:', oct(os.stat(k).st_mode & 0o777))"
```

Prove C6: run the entrypoint snippet logic against a temp Holon CA and show the merged bundle contains more than one
`BEGIN CERTIFICATE` block.

## Commit & push

```bash
git add -A ':!apps/sandbox-executor/uv.lock'
git commit -m "fix: apply validated PR review suggestions (Iteration 2)"
git push origin HEAD
```

Never push to `main` or `develop`.

## Final message format

```
APPLIED: <ids>
SKIPPED: <ids + one-line rationale>
TESTS: <pytest summary>
LINT: <ruff + prettier + bash -n status>
CRYPTO_PROOF: <the openssl assertions output>
COMMIT: <short sha>
PUSHED: <yes|no>
```
