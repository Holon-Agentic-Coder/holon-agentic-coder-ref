# TASK: PR Reviewer Subagent (Iteration 2, Dry-Run, Single-Agent Mode)

You are an isolated PR review subagent (fresh context). Work read-only; the ONLY file you may write is the report path
given at the end. NOTE: This is iteration 2. Iteration 1 findings were already fixed in commit 6e25912. Review the
CURRENT state of the diff on its merits; do not re-report fixed issues, and do not assume an issue is fixed just because
a commit message says so - verify in the code.

## User constraints ledger - do NOT recommend these:

- Do NOT add deprecation fallback stubs or error messages for open-codex in cli.py or role_dispatcher.sh. open-codex
  must be removed completely without stubs.
- When dropping an agent (e.g. open-codex), perform complete clean removal across all Dockerfiles, configs, registries,
  entrypoints, and test suites without introducing fallback shims.
- Do NOT add deprecated documentation sections when removing an agent; strip all references to the dropped agent from
  user documentation files completely.
- Do NOT create migration notices, CLI transition feedback, or deprecation release notes when an agent is dropped.

## Invariants:

- agent_removal: Dropping an agent requires complete clean removal across Dockerfiles, bake configs, registries,
  entrypoints, docs, and test suites with ZERO legacy stubs, CLI error shims, migration guides, or release notes
  deprecation warnings.
- dynamic_versioning: Static fallback version dictionaries must not be maintained in code. Rely on dynamic binary CLI
  --version checks inside Docker containers and fall back to 'unknown'. Validate returncode == 0 and catch
  subprocess.TimeoutExpired explicitly for debug logging.
- empirical_verification: Always empirically verify code syntax/import assertions via execution (pytest, python3 -c)
  before accepting LLM diff reviewer findings. Unified diff context lines must not be confused with deleted lines.

## PR Metadata (PR #48, repo Holon-Agentic-Coder/holon-agentic-coder-ref, base develop)

Title: feat(sandbox-executor): implement SSL trust and CA mounts (Phase 1) Head:
I-1787928238-token-reduction-phase1/P-1787928257-antigravity-agent-gemini-3.5-flash/E-1787928747-antigravity-agent-gemini-3.5-flash/_
+1254 / -4 across 14 files

### Description

### Summary

This PR implements **Phase 1** of the AI Agent Token Reduction architecture. It establishes the SSL trust bootstrap
mechanism and configures container mounts so outbound agent traffic can be securely intercepted and optimized.

### Scoped Changes

- **Root CA Generation (`ca_generator.py`):** Automatically generates a self-signed Root CA certificate
  (`holon-root-ca.crt`) on the host if not already present.
- **CLI Mounting & Configuration (`cli.py`):**
  - Added the `--token-reduce` CLI flag to the `plan` and `execute` commands.
  - Mounts the generated Root CA cert into the sandbox container trust store path (`/usr/local/share/ca-certificates/`).
  - Injects target proxy environment variables (`HTTP_PROXY`, `HTTPS_PROXY`, `NODE_EXTRA_CA_CERTS`,
    `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`) so agent libraries trust the proxy.

### How to Test / Verification

1. Run local tests:
   ```bash
   uv run pytest apps/sandbox-executor/tests/test_token_reduction.py
   ```
2. Verify `--token-reduce` is recognized:
   ```bash
   ./holon execute --help
   ```

## Review System Prompt

# System Instructions: Comprehensive Multi-Role Pull Request Reviewer

You are an elite, multi-disciplinary software product and engineering review team. Your objective is to perform a
comprehensive, production-grade review of the provided Pull Request (PR) diff.

To avoid overwhelming the author with irrelevant feedback, you must first dynamically determine which roles should be
activated based exclusively on the files that have changed in the diff. Activate only those roles, and perform the
review through their respective lenses.

---

## 👥 Persona Registry & Focus Areas

Here is the comprehensive registry of roles organized by functional category. You should only activate the roles that
are directly triggered by the specific files that have changed in the PR diff.

### 1. Technical Engineering & System Architecture Roles

- **Principal Engineer / Tech Lead**: Code complexity, architectural fit, design patterns, readability, maintainability,
  naming conventions, technical debt, and extensibility.
- **Solution Architect**: System boundaries, component coupling, integration patterns, API contracts
  (REST/GraphQL/gRPC), caching strategies, scaling bottlenecks, and overall system topology.
- **Frontend Engineer**: UI structure, bundle sizes, client-side state management, CSS/HTML semantics, state-driven
  rendering logic, and browser performance.
- **QA & Test Engineer**: Test coverage, unit/integration/E2E test quality, boundary/edge cases, mocking/stubbing
  validity, test readability, and manual verification steps.
- **Machine Learning (ML) / Data Science Specialist**: Feature engineering, model evaluation, validation datasets,
  inference performance/latency, model drift detection, statistical correctness, and training pipeline changes.

### 2. Product, Design, & Growth Roles

- **Product Owner / Product Manager (PO/PM)**: Business logic validation, alignment with user stories/requirements,
  feature flags, user journey impact, and release readiness.
- **UX/UI Designer**: Design aesthetics, visual consistency (Figma/design system), responsive layout, spacing/margins,
  typography, user feedback animations/micro-interactions, and dark/light theme correctness.
- **SEO & Growth Specialist**: Search engine optimization compliance, page load speeds, semantic HTML metadata
  (OpenGraph tags), page redirection logic, and marketing attribution tags.

### 3. Operations, Release, & Support Roles

- **DevOps & Site Reliability Engineer (SRE)**: CI/CD pipelines, build configurations, Infrastructure-as-Code (IaC),
  logging, metrics, tracing (observability), containerization, environment variables, and resource limits.
- **Release Manager / Release Coordinator**: Release staging dependencies, migrations/deployments ordering, database
  rollback runbooks, feature flag strategies, and changelog verification.
- **Technical Support Engineer / Customer Success Lead**: Customer-facing error messages clarity, diagnostics and
  troubleshooting capability, impact on support ticket volume, self-service tools, and backwards-compatibility breaking
  changes.

### 4. Security, Compliance, & Risk Roles

- **Security Architect**: OWASP Top 10 vulnerabilities, authentication, authorization (RBAC/ABAC), data validation,
  sanitation, cryptography, secrets exposure, dependency vulnerability, and PII leakage.
- **Compliance & Privacy Auditor**: Regulatory compliance (GDPR, CCPA, HIPAA, SOC2), audit logging, copyleft license
  checks (e.g., GPL conflicts), and data retention policies.
- **Localization (L10n) & Internationalization (I18n) Coordinator**: Hardcoded strings, translation keys, formatting of
  numbers/dates/currencies, Right-to-Left (RTL) layout support, and localization bundle structure.

### 5. Developer Relations & Technical Documentation Roles

- **Technical Writer**: Public documentation, inline comments (JSDoc, docstrings), Swagger/OpenAPI docs, README updates,
  and clarity of technical explanations.
- **Developer Advocate (DevRel)**: Public SDK developer experience (DX), developer portal alignment, sample code
  accuracy, public API ease-of-use, and developer onboarding friction.

---

## ⚡ Step 1: Dynamic Role Activation Matrix

Before outputting any review comments, analyze the file diff. Write a brief **Dynamic Role Activation Matrix** using the
following table. Activate roles based _only_ on the files that have changed, not the PR description or other metadata:

| Persona                            | Status (🟢 / ⚪) | Primary Trigger (Which files/contexts triggered activation) |
| :--------------------------------- | :--------------- | :---------------------------------------------------------- |
| **Engineering & Architecture**     |                  |                                                             |
| Principal Engineer                 | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| Solution Architect                 | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| Frontend Engineer                  | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| QA & Test Engineer                 | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| ML & Data Specialist               | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| **Product, Design, & Growth**      |                  |                                                             |
| Product Owner                      | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| UX/UI Designer                     | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| SEO & Growth Specialist            | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| **Operations, Release, & Support** |                  |                                                             |
| DevOps & SRE                       | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| Release Manager                    | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| Support Engineer                   | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| **Security, Compliance, & Risk**   |                  |                                                             |
| Security Architect                 | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| Compliance Auditor                 | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| Localization Coordinator           | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| **DevRel & Documentation**         |                  |                                                             |
| Technical Writer                   | [🟢 / ⚪]        | [Reasoning / files triggered]                               |
| Developer Advocate                 | [🟢 / ⚪]        | [Reasoning / files triggered]                               |

_Note: You should only activate the roles that are relevant to this specific changeset. For example, if there are no
public API changes, the Developer Advocate role should remain inactive (⚪)._

---

## 📝 Step 2: Review Guidelines & Severity Levels

For each **Active** role, review the diff and formulate your feedback. Categorize your findings using these exact
severity levels:

- 🔴 **CRITICAL / BLOCKER**: Major issues that will break functionality, introduce severe security exploits, cause data
  loss, violate compliance, fail acceptance criteria, or severely degrade production performance. These must be fixed
  before merging.
- 🟡 **IMPORTANT / IMPROVEMENT**: Issues that affect code maintainability, visual polish, user experience flow, test
  coverage, minor performance, scale, or design patterns. Highly recommended to address.
- 🟢 **NIT / OPTIONAL**: Style guidelines, minor refactorings, spelling errors, styling nits, or alternative
  implementation suggestions that are left to the author's discretion.
- ✅ **APPROVED / PASS**: Positive findings, praise, validation of implementation quality, or explicit confirmation of
  well-designed changes with no issues.

**Tone Guidelines:**

- Be constructive, respectful, and educational. Explain _why_ something is an issue and _how_ to fix it.
- Always provide code examples or concrete solutions where applicable.
- Avoid generic advice; refer directly to files and line numbers in the diff.

---

## 📤 Step 3: Output Format

Generate your review using the following structure:

### 📊 PR Metadata & Role Activation

_Provide the **Dynamic Role Activation Matrix** here._

---

### 🔍 Persona Reviews

_For each **Active** persona, provide a dedicated section. Skip Inactive personas._

#### 👥 [Persona Name] Review

- **[Severity] [File Path + Lines]**: [Issue Title]
  - **Context**: [Brief explanation of the current implementation and why it's problematic]
  - **Recommendation**: [Clear instructions on how to resolve the issue]
  - **Proposed Code Change**:
    ```diff
    - [old code line]
    + [new code line]
    ```

---

### 🏆 Overall Verdict

Provide a final verdict for the PR:

- **✅ APPROVED**: The PR is in excellent shape and can be merged as-is.
- **💬 COMMENT**: Good work overall, but there are some suggestions or questions (Nits and Improvements) that should be
  considered.
- **❌ CHANGES REQUESTED**: Critical/Blocker issues must be resolved before this PR can be merged.

---

## 🛠️ Input to Parse:

Below is the PR context and diff to review.

### PR Description

[Insert PR Title & Description Here]

### Git Diff

[Insert Git Diff / Files Changed Here]

## Git Diff (current PR head)

````diff
diff --git a/README.md b/README.md
index 05e0134..5813c0e 100644
--- a/README.md
+++ b/README.md
@@ -728,6 +728,49 @@ flowchart TD

 ---

+## Sandbox CLI usage
+
+All containerized Holon roles are driven by the [`./holon`](holon) host wrapper from the repository root. It maps agent
+names to images, forwards credentials (`GITHUB_TOKEN`, `HOLON_AGENT_*`), mounts the SSH agent socket, and optionally
+attaches the token-reduction proxy.
+
+```bash
+./holon intent intents/my-task.json                                  # Intent Creator
+./holon plan "I-1784983150-build-execution/_" --agent pi-agent --model gemini-3.5-flash
+./holon execute "I-1784983150-build-execution/P-1784988130-pi-agent-gemini-3.5-flash/_" \
+  --agent pi-agent --model gemini-3.5-flash --token-reduce
+```
+
+> [!NOTE] `--token-reduce` is available on `plan` and `execute` (not on `intent`). See
+> [Running Plan Generation](docs/sandbox/create_plan.md) and [Running Execution](docs/sandbox/execute_plan.md) for the
+> full contract.
+
+### Token reduction (`--token-reduce`)
+
+`--token-reduce` starts a locally-owned mitmproxy sidecar and moves the sandbox onto a per-run Docker network so agent
+responses can be compacted before they are tokenized.
+
+> [!WARNING] **`--token-reduce` performs local TLS interception** against that locally-owned proxy. A Holon Root CA is
+> generated at `~/.holon/certs/holon-root-ca.crt` and trusted inside the sandbox. The Root CA **private key**
+> (`holon-root-ca.key`, mode `0600`) stays on the host and is never mounted into any container; the sidecar only
+> receives a narrow read-only cache directory (`~/.holon/proxy-cache`).
+
+- **Prerequisites**: `docker` and `openssl` on the host `PATH`. On any failure (missing binary, failed sidecar, proxy
+  that never becomes ready) the CLI logs an actionable error and the run continues with **direct egress**; a dead proxy
+  is never injected.
+- **Containment**: the sidecar is capped at `--memory=256m --cpus=0.5` with bounded log rotation, and both it and its
+  per-run network (`holon-net-<pid>-<uuid>`) are removed when the run finishes.
+
+| Variable             | Effect                                                                                                                                                    |
+| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
+| `HOLON_TOKEN_REDUCE` | Opt-in without the flag (`1`, `true`, `yes`, `on`). Attaches to an already-running proxy; never starts one.                                               |
+| `HOLON_PROXY_URL`    | Proxy URL used in the `HOLON_TOKEN_REDUCE` path. Defaults to the host gateway (`host.docker.internal:8080` on macOS/Windows, `172.17.0.1:8080` on Linux). |
+
+> [!IMPORTANT] Host `HTTP_PROXY` / `HTTPS_PROXY` are **never** interpreted as opt-in; sandbox networking only changes
+> when `--token-reduce` or `HOLON_TOKEN_REDUCE` is set explicitly.
+
+---
+
 ## Contributing

 This project is currently in the **ideation and planning phase**. The focus is on refining the conceptual architecture,
diff --git a/apps/sandbox-executor/entrypoint/role_dispatcher.sh b/apps/sandbox-executor/entrypoint/role_dispatcher.sh
index 48d415c..2b05fea 100755
--- a/apps/sandbox-executor/entrypoint/role_dispatcher.sh
+++ b/apps/sandbox-executor/entrypoint/role_dispatcher.sh
@@ -45,6 +45,15 @@ if [ -n "${HOLON_AGENT_KEY:-}" ] && [ -n "${HOLON_AGENT_ID:-}" ]; then
     esac
 fi

+# Trust the host-provided Holon Root CA when token reduction is enabled.
+# The sandbox image is Debian-based (python:3.13-slim) with ca-certificates: a file dropped into
+# /usr/local/share/ca-certificates/ only becomes effective after update-ca-certificates runs.
+# Guarded and non-fatal: never block role dispatch over CA bookkeeping.
+HOLON_ROOT_CA_PATH="/usr/local/share/ca-certificates/holon-root-ca.crt"
+if [ -f "$HOLON_ROOT_CA_PATH" ] && command -v update-ca-certificates &>/dev/null; then
+    update-ca-certificates >/dev/null 2>&1 || true
+fi
+
 ROLE="${HOLON_ROLE:-}"

 case "$ROLE" in
diff --git a/apps/sandbox-executor/src/sandbox_executor/cli.py b/apps/sandbox-executor/src/sandbox_executor/cli.py
index 473eeba..eadc9ef 100755
--- a/apps/sandbox-executor/src/sandbox_executor/cli.py
+++ b/apps/sandbox-executor/src/sandbox_executor/cli.py
@@ -5,11 +5,47 @@
 import logging
 import os
 import shutil
+import socket
 import subprocess
 import sys
+import time
+import uuid
+from dataclasses import dataclass
+from urllib.parse import urlparse
+
+from sandbox_executor.token_reduction import generate_root_ca

 logger = logging.getLogger(__name__)

+# Directory the Root CA is mounted into inside the sandbox (picked up by update-ca-certificates
+# in the entrypoint, and referenced by the *_CA_BUNDLE / SSL_CERT_FILE env vars).
+CONTAINER_CA_DIR = "/usr/local/share/ca-certificates"
+PROXY_LISTEN_PORT = 8080
+PROXY_READY_TIMEOUT_SECONDS = 15.0
+PROXY_ATTACH_TIMEOUT_SECONDS = 3.0
+PROXY_POLL_INTERVAL_SECONDS = 0.5
+PROXY_CONNECT_TIMEOUT_SECONDS = 0.5
+_TRUTHY_ENV_VALUES = ("1", "true", "yes", "on")
+
+_TOKEN_REDUCE_HELP = (
+    "Cut agent token usage by routing sandbox egress through a locally-owned mitmproxy sidecar. "
+    "Requires the 'docker' and 'openssl' host binaries and performs LOCAL TLS INTERCEPTION: a Holon "
+    "Root CA is generated under ~/.holon/certs and trusted inside the sandbox (the private key never "
+    "leaves the host)."
+)
+
+
+@dataclass
+class _SidecarState:
+    """Tracks the proxy resources created by THIS run so teardown never touches foreign ones."""
+
+    container_name: str | None = None
+    network_name: str | None = None
+    network_created: bool = False
+
+
+_sidecar_state = _SidecarState()
+

 def find_github_token() -> str | None:
     """Auto-detect GitHub token from environment variables or gh CLI."""
@@ -120,12 +156,286 @@ def get_agent_session_mounts(agent_id: str) -> list[str]:
     return mounts


+def _run_docker(*args: str) -> subprocess.CompletedProcess[str]:
+    """Run a docker command without raising, capturing stdout/stderr for diagnostics."""
+    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
+
+
+def _container_ca_path(ca_cert_path: str) -> str:
+    """Map a host Root CA path onto its read-only in-container location."""
+    return f"{CONTAINER_CA_DIR}/{os.path.basename(ca_cert_path)}"
+
+
+def _ca_mount_args(ca_cert_path: str) -> list[str]:
+    """Docker args mounting the host Root CA certificate read-only into the sandbox."""
+    return ["-v", f"{ca_cert_path}:{_container_ca_path(ca_cert_path)}:ro"]
+
+
+def _build_proxy_envs(ca_cert_path: str, proxy_url: str) -> dict[str, str]:
+    """Env vars that route the sandbox through ``proxy_url`` and make it trust the Holon Root CA."""
+    container_ca = _container_ca_path(ca_cert_path)
+    return {
+        "HTTP_PROXY": proxy_url,
+        "HTTPS_PROXY": proxy_url,
+        "NODE_EXTRA_CA_CERTS": container_ca,
+        "REQUESTS_CA_BUNDLE": container_ca,
+        "CURL_CA_BUNDLE": container_ca,
+        "SSL_CERT_FILE": container_ca,
+    }
+
+
+def _proxy_gateway_url(port: int = PROXY_LISTEN_PORT) -> str:
+    """URL of a proxy listening on the Docker host, correct for the current platform.
+
+    ``172.17.0.1`` is the Linux bridge gateway only; Docker Desktop (macOS/Windows) does not route
+    it, so ``host.docker.internal`` is used there instead.
+    """
+    if sys.platform in ("darwin", "win32"):
+        return f"http://host.docker.internal:{port}"
+    return f"http://172.17.0.1:{port}"
+
+
+def _gateway_host_args() -> list[str]:
+    """Docker args that make ``host.docker.internal`` resolvable on Linux."""
+    if sys.platform in ("darwin", "win32"):
+        return []
+    return ["--add-host", "host.docker.internal:host-gateway"]
+
+
+def _token_reduce_opt_in(token_reduce: bool) -> bool:
+    """True only on explicit opt-in; host HTTP_PROXY/HTTPS_PROXY are never treated as opt-in."""
+    if token_reduce:
+        return True
+    return os.getenv("HOLON_TOKEN_REDUCE", "").strip().lower() in _TRUTHY_ENV_VALUES
+
+
+def _wait_for_proxy(host: str, port: int, timeout: float = PROXY_READY_TIMEOUT_SECONDS) -> bool:
+    """Poll a TCP endpoint until it accepts a connection; return False if it never does."""
+    deadline = time.monotonic() + timeout
+    while True:
+        try:
+            with socket.create_connection((host, port), timeout=PROXY_CONNECT_TIMEOUT_SECONDS):
+                return True
+        except OSError:
+            if time.monotonic() >= deadline:
+                return False
+            time.sleep(PROXY_POLL_INTERVAL_SECONDS)
+
+
+def _proxy_host_port(proxy_url: str) -> tuple[str, int] | None:
+    """Split a proxy URL into ``(host, port)``; None when it cannot be parsed."""
+    parsed = urlparse(proxy_url if "//" in proxy_url else f"//{proxy_url}")
+    if not parsed.hostname:
+        return None
+    return parsed.hostname, parsed.port or PROXY_LISTEN_PORT
+
+
+def _ensure_network(network_name: str) -> bool:
+    """Create a per-run bridge network; returns True when THIS run created it."""
+    result = _run_docker("network", "create", network_name)
+    stderr = (result.stderr or "").strip()
+    if result.returncode == 0:
+        return True
+    logger.debug("docker network create %s exited %s: %s", network_name, result.returncode, stderr)
+    if "already exists" in stderr.lower():
+        return False
+    raise RuntimeError(f"could not create Docker network '{network_name}': {stderr or 'unknown docker error'}")
+
+
+def _published_loopback_port(container_name: str) -> int | None:
+    """Read the host loopback port Docker published for the sidecar's proxy port."""
+    result = _run_docker("port", container_name, f"{PROXY_LISTEN_PORT}/tcp")
+    if result.returncode != 0:
+        logger.debug("docker port %s exited %s: %s", container_name, result.returncode, (result.stderr or "").strip())
+        return None
+    for line in (result.stdout or "").splitlines():
+        candidate = line.strip().rsplit(":", 1)[-1]
+        if candidate.isdigit():
+            return int(candidate)
+    return None
+
+
+def setup_token_reduction_proxy() -> tuple[list[str], dict[str, str]]:
+    """Start this run's mitmproxy sidecar and return the sandbox mounts and env vars.
+
+    Resources are named per run (pid + uuid suffix) and recorded in ``_sidecar_state`` so teardown
+    only ever removes what this run created.
+
+    Raises:
+        FileNotFoundError: If the mitmproxy addon script is missing.
+        RuntimeError: If Docker networking, the sidecar spawn, or the readiness probe fails.
+    """
+    run_suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
+    container_name = f"holon-proxy-{run_suffix}"
+    network_name = f"holon-net-{run_suffix}"
+
+    addon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_reduction", "mitm_addon.py")
+    if not os.path.isfile(addon_path):
+        raise FileNotFoundError(
+            f"mitmproxy addon script not found at '{addon_path}'. Token reduction cannot start its proxy "
+            "without it; re-run without --token-reduce to execute with direct egress."
+        )
+
+    ca_cert_path, _ = generate_root_ca()
+
+    # Share ONLY a narrow proxy cache dir, read-only. Never mount ~/.holon: that subtree holds the
+    # Root CA private key (~/.holon/certs) and the agent auth session stores (~/.holon/sessions).
+    proxy_cache_dir = os.path.join(os.path.expanduser(os.path.join("~", ".holon")), "proxy-cache")
+    os.makedirs(proxy_cache_dir, exist_ok=True)
+
+    _sidecar_state.network_name = network_name
+    _sidecar_state.network_created = _ensure_network(network_name)
+    _sidecar_state.container_name = container_name
+
+    docker_run_proxy = [
+        "docker",
+        "run",
+        "-d",
+        "--name",
+        container_name,
+        "--network",
+        network_name,
+        "--memory=256m",
+        "--cpus=0.5",
+        "--log-opt",
+        "max-size=5m",
+        "--log-opt",
+        "max-file=2",
+        "--restart=no",
+        # Loopback-only publish so the host can run a real TCP readiness probe.
+        "-p",
+        f"127.0.0.1::{PROXY_LISTEN_PORT}",
+        "-v",
+        f"{proxy_cache_dir}:/home/mitmproxy/.holon/proxy-cache:ro",
+        "-v",
+        f"{addon_path}:/tmp/mitm_addon.py:ro",
+        "mitmproxy/mitmproxy:12.2.3",
+        "mitmdump",
+        "-s",
+        "/tmp/mitm_addon.py",
+        "--listen-port",
+        str(PROXY_LISTEN_PORT),
+        "--set",
+        "stream_large_bodies=1m",
+    ]
+
+    proxy_spawn = subprocess.run(docker_run_proxy, capture_output=True, text=True, check=False)
+    if proxy_spawn.returncode != 0:
+        stderr = (proxy_spawn.stderr or "").strip() or (proxy_spawn.stdout or "").strip()
+        teardown_token_reduction_proxy()
+        raise RuntimeError(
+            f"mitmproxy sidecar '{container_name}' failed to start: {stderr or 'unknown docker error'}. "
+            "Re-run without --token-reduce to execute with direct egress."
+        )
+
+    host_port = _published_loopback_port(container_name)
+    if host_port is None:
+        teardown_token_reduction_proxy()
+        raise RuntimeError(
+            f"mitmproxy sidecar '{container_name}' published no host loopback port, so its readiness cannot be "
+            "verified. Re-run without --token-reduce to execute with direct egress."
+        )
+    if not _wait_for_proxy("127.0.0.1", host_port):
+        teardown_token_reduction_proxy()
+        raise RuntimeError(
+            f"mitmproxy sidecar '{container_name}' never accepted connections on 127.0.0.1:{host_port} within "
+            f"{PROXY_READY_TIMEOUT_SECONDS}s (the addon likely crashed on startup). "
+            "Re-run without --token-reduce to execute with direct egress."
+        )
+
+    mounts = ["--network", network_name, *_gateway_host_args(), *_ca_mount_args(ca_cert_path)]
+    return mounts, _build_proxy_envs(ca_cert_path, f"http://{container_name}:{PROXY_LISTEN_PORT}")
+
+
+def teardown_token_reduction_proxy() -> None:
+    """Remove only the sidecar container and network THIS run created (no-op otherwise)."""
+    if _sidecar_state.container_name:
+        result = _run_docker("rm", "-f", _sidecar_state.container_name)
+        if result.returncode != 0:
+            logger.debug(
+                "docker rm -f %s exited %s: %s",
+                _sidecar_state.container_name,
+                result.returncode,
+                (result.stderr or "").strip(),
+            )
+        _sidecar_state.container_name = None
+
+    if _sidecar_state.network_created and _sidecar_state.network_name:
+        result = _run_docker("network", "rm", _sidecar_state.network_name)
+        if result.returncode != 0:
+            logger.debug(
+                "docker network rm %s exited %s: %s",
+                _sidecar_state.network_name,
+                result.returncode,
+                (result.stderr or "").strip(),
+            )
+
+    _sidecar_state.network_name = None
+    _sidecar_state.network_created = False
+
+
+def _attach_external_proxy() -> tuple[list[str], dict[str, str]]:
+    """Attach the sandbox to an already-running proxy (``HOLON_PROXY_URL`` or host gateway).
+
+    Used for the ``HOLON_TOKEN_REDUCE`` opt-in path: the proxy is owned by the user, so this run
+    neither starts nor tears it down. An unreachable proxy degrades to direct egress.
+    """
+    proxy_url = os.getenv("HOLON_PROXY_URL") or _proxy_gateway_url()
+    host_port = _proxy_host_port(proxy_url)
+    if host_port is None:
+        logger.error(
+            "HOLON_TOKEN_REDUCE is enabled but HOLON_PROXY_URL='%s' is not a valid proxy URL. "
+            "This run continues with DIRECT egress (no token reduction).",
+            proxy_url,
+        )
+        return [], {}
+
+    ca_cert_path, _ = generate_root_ca()
+    if not _wait_for_proxy(host_port[0], host_port[1], timeout=PROXY_ATTACH_TIMEOUT_SECONDS):
+        logger.error(
+            "HOLON_TOKEN_REDUCE is enabled but no proxy accepted a TCP connection at %s:%s. Start the proxy or "
+            "point HOLON_PROXY_URL at it; this run continues with DIRECT egress (no token reduction).",
+            host_port[0],
+            host_port[1],
+        )
+        return [], {}
+
+    return [*_gateway_host_args(), *_ca_mount_args(ca_cert_path)], _build_proxy_envs(ca_cert_path, proxy_url)
+
+
+def get_token_reduction_mounts_and_envs(
+    token_reduce: bool = False,
+) -> tuple[list[str], dict[str, str]]:
+    """Build token-reduction mounts/env vars for an explicitly opted-in run.
+
+    Opt-in is strictly ``--token-reduce`` or ``HOLON_TOKEN_REDUCE`` in ``("1", "true", "yes",
+    "on")``. Host ``HTTP_PROXY``/``HTTPS_PROXY`` alone never change sandbox networking. Any failure
+    degrades to direct egress (empty mounts/envs) with an actionable error log.
+    """
+    if not _token_reduce_opt_in(token_reduce):
+        return [], {}
+
+    try:
+        if token_reduce:
+            return setup_token_reduction_proxy()
+        return _attach_external_proxy()
+    except (FileNotFoundError, RuntimeError, OSError) as exc:
+        logger.error(
+            "Token reduction is enabled but could not be configured (%s: %s). This run continues with DIRECT "
+            "egress (no TLS interception, no token reduction).",
+            type(exc).__name__,
+            exc,
+        )
+        return [], {}
+
+
 def run_docker_container(
     role: str,
     image_name: str,
     container_args: list[str],
     agent_id: str = "antigravity",
     intent_file: str | None = None,
+    token_reduce: bool = False,
 ) -> int:
     """Constructs docker run command with auto-discovered credentials and executes it."""
     if not shutil.which("docker"):
@@ -157,6 +467,12 @@ def run_docker_container(
     for k, v in ssh_envs.items():
         docker_cmd.extend(["-e", f"{k}={v}"])

+    # Token Reduction Proxy & CA Mounts
+    tr_mounts, tr_envs = get_token_reduction_mounts_and_envs(token_reduce=token_reduce)
+    docker_cmd.extend(tr_mounts)
+    for k, v in tr_envs.items():
+        docker_cmd.extend(["-e", f"{k}={v}"])
+
     # Intent file mount for intent-creator role
     if role == "intent-creator" and intent_file:
         abs_intent = os.path.abspath(intent_file)
@@ -185,8 +501,11 @@ def run_docker_container(
         else:
             sanitized_cmd.append(item)
     print(f"Executing: {' '.join(sanitized_cmd)}")
-    result = subprocess.run(docker_cmd)
-    return result.returncode
+    try:
+        result = subprocess.run(docker_cmd)
+        return result.returncode
+    finally:
+        teardown_token_reduction_proxy()


 def main() -> None:
@@ -213,12 +532,22 @@ def main() -> None:
         default="gemini-3.5-flash",
         help="Model name to pass to agent (e.g. gemini-3.5-flash, claude-3-5-sonnet)",
     )
+    plan_parser.add_argument(
+        "--token-reduce",
+        action="store_true",
+        help=_TOKEN_REDUCE_HELP,
+    )

     # Subcommand: execute
     exec_parser = subparsers.add_parser("execute", help="Run Sandbox Executor to execute code changes for a plan.")
     exec_parser.add_argument("plan_branch", help="Target plan branch name")
     exec_parser.add_argument("--agent", default="antigravity-agent", help="Agent runner to execute")
     exec_parser.add_argument("--model", default="gemini-3.5-flash", help="Model name to pass to agent")
+    exec_parser.add_argument(
+        "--token-reduce",
+        action="store_true",
+        help=_TOKEN_REDUCE_HELP,
+    )

     args = parser.parse_args()

@@ -241,12 +570,28 @@ def main() -> None:
     elif args.command == "plan":
         image_name = agent_image_mapping.get(agent_id, f"holon/agent-{agent_id}")
         container_args = [args.intent_branch, args.agent, args.model]
-        sys.exit(run_docker_container("planner", image_name, container_args, agent_id=agent_id))
+        sys.exit(
+            run_docker_container(
+                "planner",
+                image_name,
+                container_args,
+                agent_id=agent_id,
+                token_reduce=args.token_reduce,
+            )
+        )

     elif args.command == "execute":
         image_name = agent_image_mapping.get(agent_id, f"holon/agent-{agent_id}")
         container_args = [args.plan_branch, args.agent, args.model]
-        sys.exit(run_docker_container("executor", image_name, container_args, agent_id=agent_id))
+        sys.exit(
+            run_docker_container(
+                "executor",
+                image_name,
+                container_args,
+                agent_id=agent_id,
+                token_reduce=args.token_reduce,
+            )
+        )


 if __name__ == "__main__":
diff --git a/apps/sandbox-executor/src/sandbox_executor/token_reduction/__init__.py b/apps/sandbox-executor/src/sandbox_executor/token_reduction/__init__.py
new file mode 100644
index 0000000..5d57556
--- /dev/null
+++ b/apps/sandbox-executor/src/sandbox_executor/token_reduction/__init__.py
@@ -0,0 +1,10 @@
+"""Token Reduction System for Holon Agentic Coder - Phase 1.
+
+Provides Root CA certificate generation.
+"""
+
+from sandbox_executor.token_reduction.ca_generator import generate_root_ca
+
+__all__ = [
+    "generate_root_ca",
+]
diff --git a/apps/sandbox-executor/src/sandbox_executor/token_reduction/ca_generator.py b/apps/sandbox-executor/src/sandbox_executor/token_reduction/ca_generator.py
new file mode 100644
index 0000000..71f8320
--- /dev/null
+++ b/apps/sandbox-executor/src/sandbox_executor/token_reduction/ca_generator.py
@@ -0,0 +1,158 @@
+"""Root CA generator for the opt-in local token-reduction proxy.
+
+This module owns exactly one job: guarantee that a *valid* self-signed Root CA exists on
+the host so the sandbox can trust the locally-owned MITM proxy.
+
+Actual behaviour:
+
+* ``openssl`` is probed with :func:`shutil.which` before anything is written. When it is
+  missing, a :class:`RuntimeError` carrying an actionable install hint is raised.
+* The certificate is generated with ``openssl req -x509`` under a 60 second timeout.
+  ``subprocess.CalledProcessError`` and ``subprocess.TimeoutExpired`` are translated into
+  :class:`RuntimeError` including the captured stderr.
+* The private key is created with mode ``0o600`` (owner read/write only).
+* Every returned artifact is validated with ``openssl x509 -in <path> -noout`` — both
+  after fresh generation and when reusing an existing file — so a previously poisoned
+  cache is reported instead of silently trusted.
+
+There is deliberately no "fallback certificate" generator: unparseable PEM blobs would be
+cached forever by the existence check and break every TLS client inside the sandbox with
+an opaque error. Fail loudly instead.
+"""
+
+from __future__ import annotations
+
+import logging
+import os
+import shutil
+import subprocess
+
+logger = logging.getLogger(__name__)
+
+_OPENSSL_TIMEOUT_SECONDS = 60
+
+_OPENSSL_INSTALL_HINT = (
+    "Install OpenSSL and retry: macOS 'brew install openssl', Debian/Ubuntu 'apt-get install openssl'."
+)
+
+
+def _require_openssl() -> str:
+    """Return the absolute path of the ``openssl`` binary or raise with an install hint."""
+    openssl_path = shutil.which("openssl")
+    if openssl_path is None:
+        raise RuntimeError(
+            f"openssl binary not found on PATH but is required to manage the Holon Root CA. {_OPENSSL_INSTALL_HINT}"
+        )
+    return openssl_path
+
+
+def _assert_valid_cert(ca_cert_path: str) -> None:
+    """Assert that ``ca_cert_path`` is a parseable X.509 certificate.
+
+    Raises:
+        RuntimeError: If ``openssl`` cannot parse the artifact (or times out doing so).
+    """
+    openssl_path = shutil.which("openssl") or "openssl"
+    try:
+        result = subprocess.run(
+            [openssl_path, "x509", "-in", ca_cert_path, "-noout"],
+            capture_output=True,
+            text=True,
+            timeout=_OPENSSL_TIMEOUT_SECONDS,
+            check=False,
+        )
+    except (subprocess.TimeoutExpired, OSError) as exc:
+        raise RuntimeError(f"Could not validate Root CA certificate at {ca_cert_path}: {exc}") from exc
+
+    if result.returncode != 0:
+        raise RuntimeError(
+            f"Root CA certificate at {ca_cert_path} is not a parseable X.509 certificate "
+            f"(openssl: {result.stderr.strip() or 'unknown error'}). "
+            f"Delete {os.path.dirname(ca_cert_path)} and re-run to regenerate a fresh Root CA. {_OPENSSL_INSTALL_HINT}"
+        )
+
+
+def _harden_key_permissions(ca_key_path: str) -> None:
+    """Restrict the CA private key to owner read/write (``0o600``)."""
+    os.chmod(ca_key_path, 0o600)
+
+
+def generate_root_ca(cert_dir: str | None = None) -> tuple[str, str]:
+    """Ensure a valid self-signed Root CA certificate and private key exist.
+
+    Args:
+        cert_dir: Directory where certs should be stored. Defaults to ``~/.holon/certs``.
+
+    Returns:
+        tuple[str, str]: Paths to ``(ca_cert_path, ca_key_path)``. The certificate is
+        guaranteed to be parseable by ``openssl x509`` and the key is mode ``0o600``.
+
+    Raises:
+        RuntimeError: If ``openssl`` is unavailable, generation fails or times out, or an
+            existing cached certificate is not a parseable X.509 artifact.
+    """
+    openssl_path = _require_openssl()
+
+    if cert_dir is None:
+        cert_dir = os.path.expanduser("~/.holon/certs")
+
+    os.makedirs(cert_dir, exist_ok=True)
+    ca_cert_path = os.path.join(cert_dir, "holon-root-ca.crt")
+    ca_key_path = os.path.join(cert_dir, "holon-root-ca.key")
+
+    if os.path.exists(ca_cert_path) and os.path.exists(ca_key_path):
+        logger.info("Reusing existing Root CA certificate at %s", ca_cert_path)
+        _assert_valid_cert(ca_cert_path)
+        _harden_key_permissions(ca_key_path)
+        return ca_cert_path, ca_key_path
+
+    logger.info("Generating self-signed Root CA certificate at %s", cert_dir)
+
+    # Pre-create the key file with 0o600 so the private key is never world-readable,
+    # even briefly, regardless of the caller's umask.
+    key_fd = os.open(ca_key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
+    os.close(key_fd)
+
+    try:
+        subprocess.run(
+            [
+                openssl_path,
+                "req",
+                "-x509",
+                "-newkey",
+                "rsa:2048",
+                "-keyout",
+                ca_key_path,
+                "-out",
+                ca_cert_path,
+                "-days",
+                "365",
+                "-nodes",
+                "-subj",
+                "/CN=Holon Agent Root CA/O=Holon Agentic Coder",
+            ],
+            capture_output=True,
+            text=True,
+            timeout=_OPENSSL_TIMEOUT_SECONDS,
+            check=True,
+        )
+    except subprocess.CalledProcessError as exc:
+        stderr = (exc.stderr or "").strip()
+        raise RuntimeError(
+            f"OpenSSL failed to generate the Holon Root CA in {cert_dir} (exit {exc.returncode}): {stderr or exc}"
+        ) from exc
+    except subprocess.TimeoutExpired as exc:
+        raise RuntimeError(
+            f"OpenSSL timed out after {_OPENSSL_TIMEOUT_SECONDS}s generating the Holon Root CA in {cert_dir}."
+        ) from exc
+
+    _harden_key_permissions(ca_key_path)
+    _assert_valid_cert(ca_cert_path)
+
+    return ca_cert_path, ca_key_path
+
+
+if __name__ == "__main__":
+    logging.basicConfig(level=logging.INFO)
+    cert, key = generate_root_ca()
+    print(f"Generated Root CA:\n  Cert: {cert}\n  Key:  {key}")
diff --git a/apps/sandbox-executor/tests/test_cli.py b/apps/sandbox-executor/tests/test_cli.py
index 0b2dd0b..cdfd2a8 100644
--- a/apps/sandbox-executor/tests/test_cli.py
+++ b/apps/sandbox-executor/tests/test_cli.py
@@ -125,6 +125,7 @@ def test_main_subcommands(self, mock_run_container):
                 "holon/agent-antigravity",
                 ["intent_branch_name", "antigravity-agent", "gemini-3.5-flash"],
                 agent_id="antigravity",
+                token_reduce=False,
             )

         mock_run_container.reset_mock()
@@ -160,6 +161,7 @@ def test_main_subcommands(self, mock_run_container):
                 "holon/agent-antigravity",
                 ["plan_branch_name", "antigravity-agent", "gemini-3.5-flash"],
                 agent_id="antigravity",
+                token_reduce=False,
             )


diff --git a/apps/sandbox-executor/tests/test_token_reduction.py b/apps/sandbox-executor/tests/test_token_reduction.py
new file mode 100644
index 0000000..8c5abcf
--- /dev/null
+++ b/apps/sandbox-executor/tests/test_token_reduction.py
@@ -0,0 +1,336 @@
+"""Unit tests for AI Agent Token Reduction Architecture - Phase 1."""
+
+import logging
+import os
+import stat
+import subprocess
+from unittest.mock import MagicMock
+
+import pytest
+from sandbox_executor import cli
+from sandbox_executor.cli import (
+    _build_proxy_envs,
+    _ca_mount_args,
+    _container_ca_path,
+    _gateway_host_args,
+    _proxy_gateway_url,
+    get_token_reduction_mounts_and_envs,
+    setup_token_reduction_proxy,
+    teardown_token_reduction_proxy,
+)
+from sandbox_executor.token_reduction.ca_generator import generate_root_ca
+
+
+def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
+    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)
+
+
+class FakeDocker:
+    """Records docker invocations and replays canned results for the token-reduction flow."""
+
+    def __init__(self, spawn=None, port_stdout="127.0.0.1:32768\n", network_stderr=""):
+        self.calls: list[list[str]] = []
+        self.spawn = spawn if spawn is not None else _completed(stdout="containerid")
+        self.port_stdout = port_stdout
+        self.network_stderr = network_stderr
+
+    def __call__(self, cmd, *args, **kwargs):
+        self.calls.append(list(cmd))
+        head = cmd[:3] if len(cmd) >= 3 else list(cmd)
+        if head == ["docker", "network", "create"]:
+            return _completed(returncode=1 if self.network_stderr else 0, stderr=self.network_stderr)
+        if head == ["docker", "network", "rm"]:
+            return _completed()
+        if head[:2] == ["docker", "run"]:
+            return self.spawn
+        if head[:2] == ["docker", "port"]:
+            return _completed(stdout=self.port_stdout)
+        return _completed()
+
+    def joined(self) -> str:
+        return "\n".join(" ".join(call) for call in self.calls)
+
+
+@pytest.fixture(autouse=True)
+def reset_sidecar_state():
+    cli._sidecar_state.container_name = None
+    cli._sidecar_state.network_name = None
+    cli._sidecar_state.network_created = False
+    yield
+    cli._sidecar_state.container_name = None
+    cli._sidecar_state.network_name = None
+    cli._sidecar_state.network_created = False
+
+
+@pytest.fixture
+def host_paths(tmp_path, monkeypatch):
+    """Keep every host-side write (CA dir, proxy cache) inside tmp_path."""
+    monkeypatch.setattr(cli.os.path, "expanduser", lambda path: str(tmp_path / "home" / path.lstrip("~/")))
+    monkeypatch.setattr(cli, "generate_root_ca", lambda *a, **k: (str(tmp_path / "holon-root-ca.crt"), ""))
+    return tmp_path
+
+
+# --------------------------------------------------------------------------------------
+# ca_generator
+# --------------------------------------------------------------------------------------
+
+
+def test_ca_generator(tmp_path):
+    cert_path, key_path = generate_root_ca(cert_dir=str(tmp_path))
+    assert os.path.exists(cert_path)
+    assert os.path.exists(key_path)
+    assert cert_path.endswith("holon-root-ca.crt")
+    assert key_path.endswith("holon-root-ca.key")
+
+    # Second call should reuse existing cert
+    c2, k2 = generate_root_ca(cert_dir=str(tmp_path))
+    assert c2 == cert_path
+    assert k2 == key_path
+
+
+def test_ca_generator_produces_parseable_cert_and_private_key_mode(tmp_path):
+    cert_path, key_path = generate_root_ca(cert_dir=str(tmp_path))
+
+    result = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-text"], capture_output=True, text=True)
+    assert result.returncode == 0, result.stderr
+    with open(cert_path) as handle:
+        assert "BEGIN CERTIFICATE" in handle.read()
+
+    assert stat.S_IMODE(os.stat(key_path).st_mode) == 0o600
+
+
+def test_ca_generator_raises_without_openssl(tmp_path, monkeypatch):
+    monkeypatch.setattr("sandbox_executor.token_reduction.ca_generator.shutil.which", lambda _: None)
+
+    with pytest.raises(RuntimeError) as excinfo:
+        generate_root_ca(cert_dir=str(tmp_path))
+
+    assert "openssl" in str(excinfo.value).lower()
+    assert "brew install openssl" in str(excinfo.value)
+    # Nothing bogus may be cached when generation never started.
+    assert os.listdir(str(tmp_path)) == []
+
+
+def test_ca_generator_raises_on_openssl_failure_without_caching_junk(tmp_path, monkeypatch):
+    def boom(*args, **kwargs):
+        raise subprocess.CalledProcessError(1, ["openssl"], stderr="req failed")
+
+    monkeypatch.setattr("sandbox_executor.token_reduction.ca_generator.subprocess.run", boom)
+
+    with pytest.raises(RuntimeError) as excinfo:
+        generate_root_ca(cert_dir=str(tmp_path))
+
+    assert "req failed" in str(excinfo.value)
+    assert not os.path.exists(os.path.join(str(tmp_path), "holon-root-ca.crt"))
+
+
+def test_ca_generator_detects_poisoned_cache(tmp_path):
+    cert_path = tmp_path / "holon-root-ca.crt"
+    key_path = tmp_path / "holon-root-ca.key"
+    cert_path.write_text("-----BEGIN CERTIFICATE-----\nnot a real cert\n-----END CERTIFICATE-----\n")
+    key_path.write_text("-----BEGIN PRIVATE KEY-----\nnope\n-----END PRIVATE KEY-----\n")
+
+    with pytest.raises(RuntimeError) as excinfo:
+        generate_root_ca(cert_dir=str(tmp_path))
+
+    assert "not a parseable X.509 certificate" in str(excinfo.value)
+    assert "Delete" in str(excinfo.value)
+
+
+# --------------------------------------------------------------------------------------
+# setup_token_reduction_proxy
+# --------------------------------------------------------------------------------------
+
+
+def test_setup_proxy_addon_missing_raises_file_not_found(host_paths, monkeypatch):
+    monkeypatch.setattr(cli.os.path, "isfile", lambda path: False)
+    fake = FakeDocker()
+    monkeypatch.setattr(cli.subprocess, "run", fake)
+
+    with pytest.raises(FileNotFoundError) as excinfo:
+        setup_token_reduction_proxy()
+
+    assert "mitm_addon.py" in str(excinfo.value)
+    assert fake.calls == []  # nothing is launched against a non-existent addon
+
+
+def test_setup_proxy_spawn_failure_raises_and_injects_no_dead_proxy(host_paths, monkeypatch):
+    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
+    fake = FakeDocker(spawn=_completed(returncode=125, stderr="docker: error: image not found"))
+    monkeypatch.setattr(cli.subprocess, "run", fake)
+
+    with pytest.raises(RuntimeError) as excinfo:
+        setup_token_reduction_proxy()
+
+    message = str(excinfo.value)
+    assert "image not found" in message
+    assert "Re-run without --token-reduce" in message
+    # The failed sidecar this run started is cleaned up; no proxy envs are returned.
+    assert "docker rm -f" in fake.joined()
+    assert "docker network rm" in fake.joined()
+
+
+def test_setup_proxy_readiness_failure_raises_without_proxy_envs(host_paths, monkeypatch):
+    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
+    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: False)
+    fake = FakeDocker()
+    monkeypatch.setattr(cli.subprocess, "run", fake)
+
+    with pytest.raises(RuntimeError) as excinfo:
+        setup_token_reduction_proxy()
+
+    assert "never accepted connections" in str(excinfo.value)
+    assert "Re-run without --token-reduce" in str(excinfo.value)
+    assert "docker rm -f" in fake.joined()
+    assert "docker network rm" in fake.joined()
+
+
+def test_setup_proxy_missing_published_port_raises(host_paths, monkeypatch):
+    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
+    fake = FakeDocker(port_stdout="")
+    monkeypatch.setattr(cli.subprocess, "run", fake)
+
+    with pytest.raises(RuntimeError) as excinfo:
+        setup_token_reduction_proxy()
+
+    assert "published no host loopback port" in str(excinfo.value)
+
+
+def test_setup_proxy_success_mounts_only_narrow_ro_cache(host_paths, monkeypatch):
+    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
+    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: True)
+    fake = FakeDocker()
+    monkeypatch.setattr(cli.subprocess, "run", fake)
+
+    mounts, envs = setup_token_reduction_proxy()
+
+    run_cmd = next(call for call in fake.calls if call[:2] == ["docker", "run"])
+    joined_run = " ".join(run_cmd)
+
+    # C1: only the narrow proxy cache is shared, read-only; never ~/.holon wholesale.
+    assert f"{host_paths / 'home' / '.holon' / 'proxy-cache'}:/home/mitmproxy/.holon/proxy-cache:ro" in joined_run
+    assert ":/home/mitmproxy/.holon " not in joined_run
+    assert "holon-root-ca.key" not in joined_run
+
+    # I3: containment + streaming posture.
+    for flag in ["--memory=256m", "--cpus=0.5", "max-size=5m", "max-file=2", "--restart=no", "stream_large_bodies=1m"]:
+        assert flag in joined_run
+
+    # I2: per-run resource names.
+    assert "--network" in mounts
+    network_name = mounts[mounts.index("--network") + 1]
+    assert network_name.startswith("holon-net-")
+    assert network_name not in ("holon-net",)
+    assert envs["HTTP_PROXY"].startswith(f"http://holon-proxy-{os.getpid()}")
+    assert envs["HTTPS_PROXY"] == envs["HTTP_PROXY"]
+    assert envs["SSL_CERT_FILE"] == _container_ca_path(str(host_paths / "holon-root-ca.crt"))
+    assert cli._sidecar_state.network_created is True
+
+
+def test_setup_proxy_network_already_exists_is_not_owned(host_paths, monkeypatch):
+    monkeypatch.setattr(cli.os.path, "isfile", lambda path: True)
+    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: True)
+    fake = FakeDocker(network_stderr="Error response from daemon: network with name x already exists")
+    monkeypatch.setattr(cli.subprocess, "run", fake)
+
+    setup_token_reduction_proxy()
+
+    assert cli._sidecar_state.network_created is False
+    teardown_token_reduction_proxy()
+    assert "docker network rm" not in fake.joined()
+    assert "docker rm -f" in fake.joined()
+
+
+def test_teardown_is_noop_when_this_run_created_nothing(monkeypatch):
+    fake = FakeDocker()
+    monkeypatch.setattr(cli.subprocess, "run", fake)
+
+    teardown_token_reduction_proxy()
+
+    assert fake.calls == []
+
+
+# --------------------------------------------------------------------------------------
+# opt-in contract
+# --------------------------------------------------------------------------------------
+
+
+def test_host_proxy_env_alone_never_rewrites_sandbox_networking(monkeypatch):
+    monkeypatch.delenv("HOLON_TOKEN_REDUCE", raising=False)
+    monkeypatch.setenv("HTTP_PROXY", "http://unrelated-host-proxy:3128")
+    monkeypatch.setenv("HTTPS_PROXY", "http://unrelated-host-proxy:3128")
+
+    assert get_token_reduction_mounts_and_envs(token_reduce=False) == ([], {})
+
+
+@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
+def test_env_var_opt_in_attempts_configuration(monkeypatch, value):
+    monkeypatch.setenv("HOLON_TOKEN_REDUCE", value)
+    calls = []
+    monkeypatch.setattr(cli, "_attach_external_proxy", lambda: calls.append(True) or (["--network", "x"], {}))
+
+    mounts, envs = get_token_reduction_mounts_and_envs(token_reduce=False)
+
+    assert calls == [True]
+    assert mounts == ["--network", "x"]
+    assert envs == {}
+
+
+@pytest.mark.parametrize("value", ["", "0", "false", "off", "http_proxy"])
+def test_env_var_opt_in_requires_truthy_value(monkeypatch, value):
+    monkeypatch.setenv("HOLON_TOKEN_REDUCE", value)
+    monkeypatch.setattr(cli, "_attach_external_proxy", lambda: pytest.fail("must not configure"))
+
+    assert get_token_reduction_mounts_and_envs(token_reduce=False) == ([], {})
+
+
+def test_env_var_opt_in_unreachable_proxy_degrades_to_direct_egress(host_paths, monkeypatch, caplog):
+    monkeypatch.setenv("HOLON_TOKEN_REDUCE", "1")
+    monkeypatch.setenv("HOLON_PROXY_URL", "http://127.0.0.1:9")
+    monkeypatch.setattr(cli, "_wait_for_proxy", lambda *args, **kwargs: False)
+
+    with caplog.at_level(logging.ERROR, logger="sandbox_executor.cli"):
+        mounts, envs = get_token_reduction_mounts_and_envs(token_reduce=False)
+
+    assert (mounts, envs) == ([], {})
+    assert "DIRECT egress" in caplog.text
+    assert "127.0.0.1" in caplog.text
+
+
+def test_flag_opt_in_sidecar_failure_degrades_to_direct_egress(host_paths, monkeypatch, caplog):
+    monkeypatch.setattr(cli.os.path, "isfile", lambda path: False)
+
+    with caplog.at_level(logging.ERROR, logger="sandbox_executor.cli"):
+        mounts, envs = get_token_reduction_mounts_and_envs(token_reduce=True)
+
+    assert (mounts, envs) == ([], {})
+    assert "DIRECT egress" in caplog.text
+    assert "FileNotFoundError" in caplog.text
+
+
+# --------------------------------------------------------------------------------------
+# platform + de-duplication helpers
+# --------------------------------------------------------------------------------------
+
+
+def test_proxy_gateway_url_is_platform_correct(monkeypatch):
+    monkeypatch.setattr(cli.sys, "platform", "darwin")
+    assert _proxy_gateway_url() == "http://host.docker.internal:8080"
+    assert _gateway_host_args() == []
+
+    monkeypatch.setattr(cli.sys, "platform", "linux")
+    assert _proxy_gateway_url() == "http://172.17.0.1:8080"
+    assert _gateway_host_args() == ["--add-host", "host.docker.internal:host-gateway"]
+
+
+def test_ca_mount_and_env_helpers_agree():
+    host_ca = "/host/.holon/certs/holon-root-ca.crt"
+    container_ca = _container_ca_path(host_ca)
+
+    assert _ca_mount_args(host_ca) == ["-v", f"{host_ca}:{container_ca}:ro"]
+    envs = _build_proxy_envs(host_ca, "http://holon-proxy-1:8080")
+    assert envs["HTTP_PROXY"] == envs["HTTPS_PROXY"] == "http://holon-proxy-1:8080"
+    assert envs["NODE_EXTRA_CA_CERTS"] == container_ca
+    assert envs["REQUESTS_CA_BUNDLE"] == container_ca
+    assert envs["CURL_CA_BUNDLE"] == container_ca
+    assert envs["SSL_CERT_FILE"] == container_ca
diff --git a/docs/sandbox/create_plan.md b/docs/sandbox/create_plan.md
index 30c9648..abfa2fd 100644
--- a/docs/sandbox/create_plan.md
+++ b/docs/sandbox/create_plan.md
@@ -36,6 +36,38 @@ Run from the repository root:

 ---

+## Optional: Token Reduction Proxy (`--token-reduce`)
+
+Pass `--token-reduce` to route the planner sandbox's HTTP(S) egress through a locally-owned mitmproxy sidecar, so
+responses can be compacted before the agent spends tokens on them.
+
+```bash
+./holon plan "I-1782654790-bootstrap-holon-cli-intent/_" --agent pi-agent --model gemini-3.5-flash --token-reduce
+```
+
+> [!WARNING] **`--token-reduce` performs local TLS interception.** A Holon Root CA is generated at
+> `~/.holon/certs/holon-root-ca.crt` and made trusted inside the sandbox so it can decrypt and re-encrypt agent traffic.
+> The Root CA **private key** (`holon-root-ca.key`, mode `0600`) stays on the host and is never mounted into any
+> container; the sidecar only receives a narrow read-only cache directory (`~/.holon/proxy-cache`).
+
+- **Prerequisites**: the `docker` and `openssl` host binaries. If either is missing, the sidecar fails to start, or it
+  never becomes ready, the CLI logs an actionable error and the run continues with **direct egress** — a dead proxy is
+  never injected into the sandbox.
+- **Isolation**: the sidecar runs on a per-run Docker network (`holon-net-<pid>-<uuid>`), is capped at
+  `--memory=256m --cpus=0.5` with bounded log rotation, and both it and its network are removed when the run finishes.
+
+### Environment contract
+
+| Variable             | Effect                                                                                                                                                    |
+| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
+| `HOLON_TOKEN_REDUCE` | Opt-in without the flag (`1`, `true`, `yes`, `on`). Attaches to an already-running proxy; never starts one.                                               |
+| `HOLON_PROXY_URL`    | Proxy URL used in the `HOLON_TOKEN_REDUCE` path. Defaults to the host gateway (`host.docker.internal:8080` on macOS/Windows, `172.17.0.1:8080` on Linux). |
+
+> [!IMPORTANT] Host `HTTP_PROXY` / `HTTPS_PROXY` are **never** interpreted as opt-in. Sandbox networking is only changed
+> when you pass `--token-reduce` or set `HOLON_TOKEN_REDUCE` explicitly.
+
+---
+
 ## Low-Level Execution (Manual `docker run`)

 If you need to invoke Docker manually, run the following command to start the planner container, replacing arguments as
diff --git a/docs/sandbox/execute_plan.md b/docs/sandbox/execute_plan.md
index 9bfd8c3..73a4712 100644
--- a/docs/sandbox/execute_plan.md
+++ b/docs/sandbox/execute_plan.md
@@ -52,6 +52,38 @@ sandbox:
 - **macOS**: Mounts `/run/host-services/ssh-auth.sock` to the container and updates the `SSH_AUTH_SOCK` environment.
 - **Linux/Other**: Mounts the host's existing `SSH_AUTH_SOCK` value to `/run/ssh-agent` in the container.

+### 4. Optional Token Reduction Proxy (`--token-reduce`)
+
+```bash
+./holon execute "I-1782654790-bootstrap-holon-cli-intent/P-1784988130-antigravity-agent-gemini-3.5-flash/_" \
+  --agent antigravity-agent --model gemini-3.5-flash --token-reduce
+```
+
+`--token-reduce` routes the sandbox's HTTP(S) egress through a locally-owned mitmproxy sidecar so agent responses can be
+compacted before they are tokenized.
+
+> [!WARNING] **`--token-reduce` performs local TLS interception.** A Holon Root CA is generated at
+> `~/.holon/certs/holon-root-ca.crt` and trusted inside the sandbox (registered by the entrypoint via
+> `update-ca-certificates`). The Root CA **private key** (`holon-root-ca.key`, mode `0600`) stays on the host and is
+> never mounted into any container; the sidecar only receives a narrow read-only cache directory
+> (`~/.holon/proxy-cache`).
+
+- **Prerequisites**: the `docker` and `openssl` host binaries. If either is missing, the sidecar fails to start, or it
+  never becomes ready, the CLI logs an actionable error and the run continues with **direct egress** — a dead proxy is
+  never injected into the sandbox.
+- **Isolation**: the sidecar runs on a per-run Docker network (`holon-net-<pid>-<uuid>`), is capped at
+  `--memory=256m --cpus=0.5` with bounded log rotation, and both it and its network are removed when the run finishes.
+
+### Environment contract
+
+| Variable             | Effect                                                                                                                                                    |
+| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
+| `HOLON_TOKEN_REDUCE` | Opt-in without the flag (`1`, `true`, `yes`, `on`). Attaches to an already-running proxy; never starts one.                                               |
+| `HOLON_PROXY_URL`    | Proxy URL used in the `HOLON_TOKEN_REDUCE` path. Defaults to the host gateway (`host.docker.internal:8080` on macOS/Windows, `172.17.0.1:8080` on Linux). |
+
+> [!IMPORTANT] Host `HTTP_PROXY` / `HTTPS_PROXY` are **never** interpreted as opt-in. Sandbox networking is only changed
+> when you pass `--token-reduce` or set `HOLON_TOKEN_REDUCE` explicitly.
+
 ---

 ## Command Breakdown
@@ -59,6 +91,9 @@ sandbox:
 - **`plan_branch`** (positional, required): The target plan branch to execute.
 - **`--agent`** (optional, default: `antigravity-agent`): Agent runner to execute.
 - **`--model`** (optional, default: `gemini-3.5-flash`): Target LLM model name.
+- **`--token-reduce`** (optional, flag): Route sandbox egress through the local token-reduction proxy (requires
+  `docker` + `openssl`; performs local TLS interception, see
+  [Optional Token Reduction Proxy](#4-optional-token-reduction-proxy--token-reduce)).

 ---

diff --git a/executions/E-1787928747-antigravity-agent-gemini-3.5-flash.md b/executions/E-1787928747-antigravity-agent-gemini-3.5-flash.md
new file mode 100644
index 0000000..bb5562c
--- /dev/null
+++ b/executions/E-1787928747-antigravity-agent-gemini-3.5-flash.md
@@ -0,0 +1,15 @@
+# Execution Record: E-1787928747-antigravity-agent-gemini-3.5-flash
+
+- Plan Branch: `I-1787928238-token-reduction-phase1/P-1787928257-antigravity-agent-gemini-3.5-flash/_`
+- Agent: `antigravity-agent`
+- Agent Version: `1.1.22`
+- Model: `gemini-3.5-flash`
+- Timestamp: `2026-08-28T14:52:27.637433+00:00`
+
+## Status
+
+Success
+
+## Summary
+
+Plan executed successfully
diff --git a/holon-knowledge/ledger/executions.jsonl b/holon-knowledge/ledger/executions.jsonl
index db91e49..98f7e40 100644
--- a/holon-knowledge/ledger/executions.jsonl
+++ b/holon-knowledge/ledger/executions.jsonl
@@ -1,3 +1,4 @@
 {"execution_id": "E-1787049387-antigravity-agent-gemini-3.5-flash", "plan_branch": "I-1787048466-executor-architecture-spec/P-1787048480-antigravity-agent-gemini-3.5-flash/_", "agent": "antigravity-agent", "model": "gemini-3.5-flash", "status": "success", "summary": "Plan executed successfully", "execution_file": "executions/E-1787049387-antigravity-agent-gemini-3.5-flash.md", "created_at": "2026-08-18T10:36:27.617715+00:00"}
 {"execution_id": "E-1787051559-antigravity-agent-gemini-3.5-flash", "plan_branch": "I-1787051498-executor-plan-calibration/P-1787051525-antigravity-agent-gemini-3.5-flash/_", "agent": "antigravity-agent", "model": "gemini-3.5-flash", "status": "success", "summary": "Plan executed successfully in sandbox. Calibration report generated under plans/P-1787051525-antigravity-agent-gemini-3.5-flash_calibration.md on the calibrated branch.", "execution_file": "executions/E-1787051559-antigravity-agent-gemini-3.5-flash.md", "created_at": "2026-08-18T11:12:39.000Z"}
 {"execution_id": "E-1787563716-antigravity-agent-gemini-3.5-flash", "plan_branch": "I-1787563553-record-agent-version/P-1787563567-antigravity-agent-gemini-3.5-flash/_", "agent": "antigravity-agent", "model": "gemini-3.5-flash", "status": "success", "summary": "Plan executed successfully", "execution_file": "executions/E-1787563716-antigravity-agent-gemini-3.5-flash.md", "created_at": "2026-08-24T09:28:36.410675+00:00"}
+{"execution_id": "E-1787928747-antigravity-agent-gemini-3.5-flash", "plan_branch": "I-1787928238-token-reduction-phase1/P-1787928257-antigravity-agent-gemini-3.5-flash/_", "agent": "antigravity-agent", "agent_version": "1.1.22", "model": "gemini-3.5-flash", "status": "success", "summary": "Plan executed successfully", "execution_file": "executions/E-1787928747-antigravity-agent-gemini-3.5-flash.md", "created_at": "2026-08-28T14:52:27.637433+00:00"}
diff --git a/holon-knowledge/ledger/intents.jsonl b/holon-knowledge/ledger/intents.jsonl
index b71635d..836f505 100644
--- a/holon-knowledge/ledger/intents.jsonl
+++ b/holon-knowledge/ledger/intents.jsonl
@@ -1,3 +1,4 @@
 {"slug": "executor-architecture-spec", "description": "Add execution architecture specification and agent credentials requirements for executor", "goal": "Create docs/executor/execution_architecture_specification.md and docs/executor/agent_credentials_requirements.md, and update docs/sandbox/execute_plan.md to document the executor architecture, multi-tier credentials, safety policies, and execution flow", "target_branch": "develop", "branch": "I-1787048466-executor-architecture-spec", "status": "proposed", "created_at": "2026-08-18T10:21:07.559Z"}
 {"slug": "executor-plan-calibration", "description": "Perform full Holon flow with plan calibration", "goal": "Execute plan calibration flow and create plans/P-1787051525-antigravity-agent-gemini-3.5-flash_calibration.md", "target_branch": "develop", "branch": "I-1787051498-executor-plan-calibration", "status": "proposed", "created_at": "2026-08-18T11:11:38.000Z"}
 {"slug": "record-agent-version", "description": "Record agent version numbers alongside agent names in plans ledger, executions ledger, plan markdown templates, execution records, and architecture documentation", "goal": "Implement agent CLI version resolution in AgentRunner, record agent_version in plans.jsonl and executions.jsonl ledgers as well as plan and execution markdown records, and update all architectural and workflow documentation and unit tests", "target_branch": "develop", "entropy_budget": 4.0, "branch": "I-1787563553-record-agent-version", "status": "proposed", "created_at": "2026-08-24T09:25:54.684Z"}
+{"slug": "token-reduction-phase1", "description": "Token Reduction Phase 1: MITM Interceptor & Trust Bootstrap", "goal": "Implement Root CA certificate generation and integrate container mounts and proxy environment variables into the CLI wrapper.", "target_branch": "develop", "branch": "I-1787928238-token-reduction-phase1", "status": "proposed", "created_at": "2026-08-28T14:44:03.200Z"}
diff --git a/holon-knowledge/ledger/plans.jsonl b/holon-knowledge/ledger/plans.jsonl
index a0d631a..146f452 100644
--- a/holon-knowledge/ledger/plans.jsonl
+++ b/holon-knowledge/ledger/plans.jsonl
@@ -1,3 +1,4 @@
 {"plan_id": "P-1787048480-antigravity-agent-gemini-3.5-flash", "intent_branch": "I-1787048466-executor-architecture-spec/_", "agent": "antigravity-agent", "model": "gemini-3.5-flash", "p_success": 0.98, "entropy": 0.8, "impact": 20.0, "cost": 2.0, "learning_value": 0.5, "ev": 18.020000000000003, "created_at": "2026-08-18T10:23:11.427Z", "plan_file": "plans/P-1787048480-antigravity-agent-gemini-3.5-flash.md", "status": "proposed"}
 {"plan_id": "P-1787051525-antigravity-agent-gemini-3.5-flash", "intent_branch": "I-1787051498-executor-plan-calibration/_", "agent": "antigravity-agent", "model": "gemini-3.5-flash", "p_success": 0.98, "entropy": 1.2, "impact": 35.0, "cost": 4.0, "learning_value": 2.5, "ev": 31.19, "created_at": "2026-08-18T11:12:05.000Z", "plan_file": "plans/P-1787051525-antigravity-agent-gemini-3.5-flash.md", "status": "proposed"}
 {"plan_id": "P-1787563567-antigravity-agent-gemini-3.5-flash", "intent_branch": "I-1787563553-record-agent-version/_", "agent": "antigravity-agent", "model": "gemini-3.5-flash", "p_success": 0.97, "entropy": 1.0, "impact": 40.0, "cost": 2.0, "learning_value": 2.0, "ev": 38.699999999999996, "created_at": "2026-08-24T09:28:26.952Z", "plan_file": "plans/P-1787563567-antigravity-agent-gemini-3.5-flash.md", "status": "proposed"}
+{"plan_id": "P-1787928257-antigravity-agent-gemini-3.5-flash", "intent_branch": "I-1787928238-token-reduction-phase1/_", "agent": "antigravity-agent", "agent_version": "1.1.22", "model": "gemini-3.5-flash", "p_success": 0.95, "entropy": 2.0, "impact": 70.0, "cost": 10.0, "learning_value": 3.0, "ev": 59.3, "created_at": "2026-08-28T14:46:33.455Z", "plan_file": "plans/P-1787928257-antigravity-agent-gemini-3.5-flash.md", "status": "proposed"}
diff --git a/plans/P-1787928257-antigravity-agent-gemini-3.5-flash.md b/plans/P-1787928257-antigravity-agent-gemini-3.5-flash.md
new file mode 100644
index 0000000..e948e28
--- /dev/null
+++ b/plans/P-1787928257-antigravity-agent-gemini-3.5-flash.md
@@ -0,0 +1,262 @@
+# Plan for I-1787928238-token-reduction-phase1
+
+- **Plan ID:** P-1787928257-antigravity-agent-gemini-3.5-flash
+- **Parent Intent ID:** NONE
+- **Agent:** antigravity-agent/gemini-3.5-flash (version: 1.1.22)
+- **Created At:** 2026-08-28T14:44:24Z
+
+## Planner Autonomy Summary
+
+- **Intent handling:** ACCEPT_AS_IS
+- **Reframed intent (if applicable):** NONE
+- **Exploration stance:** conservative with 1–2 sentence justification. We choose a conservative stance as the
+  requirements are clear and the task is to establish baseline CA and proxy routing functionality without high-risk
+  modifications to core orchestration logic.
+- **Safety priority level:** standard
+- **Priority Justification:** Standard level is appropriate because we are modifying only the CLI wrapper to mount certs
+  and forward proxy environment variables without altering the core sandbox execution boundaries or privilege
+  requirements.
+
+## Exploration
+
+- **Proportion of steps that are exploratory:** 0.0
+- **Justification:** No exploratory steps are needed because generating self-signed certificates and mounting files via
+  docker run is a standard, deterministic operation with minimal uncertainty.
+
+## Overall Plan Metrics
+
+| metric              | value |
+| ------------------- | ----- |
+| p_success_pred      | 0.90  |
+| entropy_pred        | 7.5   |
+| impact_pred         | 80    |
+| cost_pred           | 35    |
+| learning_value_pred | 4.0   |
+| ev_pred             | 36.75 |
+
+### Strategy Rationale
+
+We accept the intent as-is because it sets up the mandatory trust bootstrap foundation for MITM proxy interception. The
+overall plan metrics are aggregated from individual steps: overall success probability is determined by the bottleneck
+step (Step 2, which involves complex env var forwarding and Docker command modification); overall entropy is the sum of
+step entropies; cost is the sum of step costs; impact and learning value are the maximum of step impacts and learning
+values, respectively. The resulting EV is positive (36.75), indicating high feasibility and value.
+
+## Safety & Constraint Alignment
+
+- **Key world ruleset constraints that affect this plan:**
+  - `constraints.md#2` (Sandbox Containment Tiers) - Filesystem mounts must be read-only where possible, and we must not
+    violate container sandboxing.
+  - `ruleset.md#3` (Testing Constraints) - We must add proper tests and not modify unrelated code.
+- **Potential violations or edge cases:**
+  - Exposing host sensitive credentials or keys to the container sandbox.
+  - Mounting directories outside the allowed ones or using write permissions where read-only is sufficient.
+- **Mitigations built into the plan:**
+  - The Root CA certificate is mounted strictly read-only (`:ro`).
+  - Sensitive proxy credentials are kept secure and only standard environment variables are forwarded.
+- **Residual risk accepted (and why):** None, as all code changes are isolated to CLI wrapper parameters and standard
+  OpenSSL subprocessing on the host.
+- **Allocated Entropy Budget:** 15.0
+- **Predicted Plan Entropy:** 7.5
+- **Budget Compliance:** The strategy fits within budget
+
+## Plan Description & Strategy
+
+The strategy is to implement Root CA certificate generation and validation on the host using the pre-installed `openssl`
+command-line utility. Once generated, we mount this certificate into the container's standard CA location and set
+proxy-related environment variables so that any containerized processes automatically trust the CA and route their TLS
+connections through the intercepting proxy. Finally, we implement tests to verify these commands and variables are
+constructed correctly.
+
+---
+
+## Step 1: Implement Root CA Generation Utility
+
+- **Sub‑intent recommendation:** NO
+- **Reasoning:** Simple, low-risk Python utility wrapper around standard openssl CLI, not reusable outside
+  sandbox-executor scope.
+- **Step Type:** IMPLEMENTATION
+- **Exploration level:** EXPLOIT
+
+### Intent & Git Integration
+
+- **Step Intent:** Implement host-side Root CA certificate generation and verification in sandbox-executor.
+- **Git branch:** I-1787928238-token-reduction-phase1
+- **Sub‑intent:** NONE
+
+### Implementation Details (No code blocks, only logic/steps)
+
+1. Create or modify a module in `sandbox_executor` (e.g. `sandbox_executor/cert.py` or within `cli.py` directly) to
+   define `ensure_root_ca()`.
+2. Define `HOLON_CERTS_DIR` defaulting to `~/.holon/certs`.
+3. If `ca.key` and `ca.crt` do not exist in that directory:
+   - Invoke `openssl genrsa -out ca.key 4096` via subprocess.
+   - Invoke `openssl req -new -x509 -days 3650 -key ca.key -out ca.crt -subj "/CN=Holon Root CA/O=Holon/OU=Sandbox"` via
+     subprocess.
+4. Verify files were created and return their absolute paths.
+
+### Dependencies & Criticality
+
+- **Depends on:** NONE
+- **Is Bottleneck:** YES
+
+### Safety & Constraint Considerations
+
+- **Relevant rules:** safety.md#3 (Trust is earned, not granted), constraints.md#2 (Process Sandbox subprocess
+  boundaries)
+- **Potential failure modes for this step:**
+  - `openssl` binary missing on the host.
+  - Write permission denied in `~/.holon/certs`.
+- **Guardrails and early‑abort checks:**
+  - Check for `openssl` command availability using `shutil.which` before execution.
+  - Trap process execution errors and log detailed error messages before raising a RuntimeError.
+
+### Success & Discard Criteria
+
+- **Success:** `ensure_root_ca()` returns valid file paths to generated Root CA certificate and private key.
+- **Discard:** subprocess execution fails repeatedly or `openssl` cannot be found on host.
+
+### Metrics
+
+| metric              | value |
+| ------------------- | ----- |
+| p_success_pred      | 0.95  |
+| entropy_pred        | 2.5   |
+| impact_pred         | 60    |
+| cost_pred           | 10    |
+| learning_value_pred | 3.0   |
+| ev_pred             | 47.75 |
+
+### Step Metrics Rationale
+
+This step uses standard commands and has a very high success probability (0.95) and low entropy (2.5) since `openssl` is
+already confirmed to be present on the system and files are generated in standard agent state paths.
+
+---
+
+## Step 2: CLI Wrapper Integration for Mounts and Proxy Environment Variables
+
+- **Sub‑intent recommendation:** NO
+- **Reasoning:** Straightforward integration of volume mounts and environment variable forwarding in CLI execution
+  method.
+- **Step Type:** IMPLEMENTATION
+- **Exploration level:** EXPLOIT
+
+### Intent & Git Integration
+
+- **Step Intent:** Modify the Docker execution wrapper to mount the CA certificate and forward proxy environment
+  variables.
+- **Git branch:** I-1787928238-token-reduction-phase1
+- **Sub‑intent:** NONE
+
+### Implementation Details (No code blocks, only logic/steps)
+
+1. Import the Root CA utility in `sandbox_executor/cli.py`.
+2. Within `run_docker_container()`, invoke `ensure_root_ca()` to get `ca.crt` path.
+3. Append a read-only Docker volume mount: `-v <ca.crt_path>:/etc/ssl/certs/holon-ca.crt:ro`.
+4. Append container environment variables:
+   - `REQUESTS_CA_BUNDLE=/etc/ssl/certs/holon-ca.crt`
+   - `CURL_CA_BUNDLE=/etc/ssl/certs/holon-ca.crt`
+   - `SSL_CERT_FILE=/etc/ssl/certs/holon-ca.crt`
+   - `NODE_EXTRA_CA_CERTS=/etc/ssl/certs/holon-ca.crt`
+5. Read proxy environment variables (`HTTP_PROXY`, `http_proxy`, `HTTPS_PROXY`, `https_proxy`, `NO_PROXY`, `no_proxy`)
+   from the host environment and forward them to the container command args if present.
+6. Support `HOLON_` prefixed proxy variable overrides (`HOLON_HTTP_PROXY`, `HOLON_HTTPS_PROXY`, `HOLON_NO_PROXY`) and
+   map them to their corresponding standard proxy environment variables inside the container.
+
+### Dependencies & Criticality
+
+- **Depends on:** Step 1
+- **Is Bottleneck:** YES
+
+### Safety & Constraint Considerations
+
+- **Relevant rules:** constraints.md#2 (Container Sandbox constraints)
+- **Potential failure modes for this step:**
+  - Docker daemon configuration prevents mounting from `~/.holon/certs`.
+  - Misformatted proxy URL syntax breaking docker command parsing.
+- **Guardrails and early‑abort checks:**
+  - Use `os.path.abspath` to ensure absolute path mounts.
+  - Keep the mount read-only (`:ro`) to prevent sandbox processes from tampering with the certificate.
+
+### Success & Discard Criteria
+
+- **Success:** CLI correctly builds and prints the Docker run command containing the certificate mount and
+  forwarded/overridden proxy variables.
+- **Discard:** CLI execution fails or command argument lists are malformed.
+
+### Metrics
+
+| metric              | value |
+| ------------------- | ----- |
+| p_success_pred      | 0.90  |
+| entropy_pred        | 3.0   |
+| impact_pred         | 80    |
+| cost_pred           | 15    |
+| learning_value_pred | 4.0   |
+| ev_pred             | 58.1  |
+
+### Step Metrics Rationale
+
+Step 2 is the core delivery of the intent with high impact (80) and slightly higher entropy (3.0) due to string
+formatting and environment mapping, but still has a very high success probability (0.90).
+
+---
+
+## Step 3: Implement Unit and Integration Tests
+
+- **Sub‑intent recommendation:** NO
+- **Reasoning:** Standard testing procedure for CLI arguments and environment parsing.
+- **Step Type:** TEST
+- **Exploration level:** EXPLOIT
+
+### Intent & Git Integration
+
+- **Step Intent:** Add test cases in `apps/sandbox-executor/tests/test_cli.py` to assert correct cert generation and
+  docker command assembly.
+- **Git branch:** I-1787928238-token-reduction-phase1
+- **Sub‑intent:** NONE
+
+### Implementation Details (No code blocks, only logic/steps)
+
+1. Add `test_ensure_root_ca` in `test_cli.py` mocking file checks and `subprocess.run` to verify openssl commands are
+   invoked correctly.
+2. Add `test_run_docker_container_with_proxy_and_ca` mocking `ensure_root_ca` and `subprocess.run`. Assert that:
+   - Volume mount `-v` points to the certificate path.
+   - CA bundle variables are present in docker args.
+   - Proxy env variables and `HOLON_` proxy overrides are correctly forwarded as `-e` arguments.
+
+### Dependencies & Criticality
+
+- **Depends on:** Step 2
+- **Is Bottleneck:** NO
+
+### Safety & Constraint Considerations
+
+- **Relevant rules:** ruleset.md#3 (Testing Constraints)
+- **Potential failure modes for this step:**
+  - Mock collision with other CLI tests.
+- **Guardrails and early‑abort checks:**
+  - Clean up any temporary directories used in tests.
+
+### Success & Discard Criteria
+
+- **Success:** All new and existing tests pass.
+- **Discard:** Test failures that cannot be resolved within budget.
+
+### Metrics
+
+| metric              | value |
+| ------------------- | ----- |
+| p_success_pred      | 0.95  |
+| entropy_pred        | 2.0   |
+| impact_pred         | 70    |
+| cost_pred           | 10    |
+| learning_value_pred | 3.0   |
+| ev_pred             | 57.4  |
+
+### Step Metrics Rationale
+
+Testing has high success probability and low risk/entropy (2.0) while providing substantial regression protection.
+
+---
````

## Output Requirements (MANDATORY)

1. Perform the review yourself in THIS single agent pass. Do NOT spawn further subagents.
2. Ground every finding in the actual diff/code. Read files in the current working directory (PR head worktree) to
   verify. Empirically verify any claim about syntax, imports, missing files, or test results by EXECUTING (e.g.
   `PYTHONPATH=apps/sandbox-executor/src uv run pytest apps/sandbox-executor/tests -q`, `uv run ruff check .`,
   `python3 -c ...`, `find`). Do not report a guess as a fact.
3. DRY-RUN MODE: do NOT run `gh pr review`, do NOT post to GitHub, do NOT commit or push, do NOT modify source files.
4. Write your full structured review report to this exact absolute path:
   /Users/thomashan/git/holon-agentic-coder-ref-metadata/.subagent/dry_run_review_iter_2_6e25912.md
5. Then print to stdout, as your final message, EXACTLY these three lines: VERDICT: <APPROVED | CHANGES_REQUESTED |
   COMMENT> COUNTS: CRITICAL=<n> IMPORTANT=<n> NIT=<n> REPORT:
   /Users/thomashan/git/holon-agentic-coder-ref-metadata/.subagent/dry_run_review_iter_2_6e25912.md
