# TASK: PR Reviewer Subagent (Dry-Run, Single-Agent Mode)

You are an isolated PR review subagent. Work read-only; the ONLY file you may write is the report path given at the end.

## User constraints ledger (from .subagent/coordination.json) — do NOT recommend these:

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
+567 / -4 across 10 files

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

## Git Diff

```diff
diff --git a/apps/sandbox-executor/src/sandbox_executor/cli.py b/apps/sandbox-executor/src/sandbox_executor/cli.py
index 473eeba..0c0037f 100755
--- a/apps/sandbox-executor/src/sandbox_executor/cli.py
+++ b/apps/sandbox-executor/src/sandbox_executor/cli.py
@@ -120,12 +120,117 @@ def get_agent_session_mounts(agent_id: str) -> list[str]:
     return mounts


+def setup_token_reduction_proxy() -> tuple[list[str], dict[str, str]]:
+    """Spawns the mitmproxy Docker sidecar and returns target container mounts and network options."""
+    import time
+
+    # 1. Create docker network holon-net if not exists
+    subprocess.run(["docker", "network", "create", "holon-net"], capture_output=True, check=False)
+
+    # 2. Kill existing holon-proxy sidecar if running
+    subprocess.run(["docker", "rm", "-f", "holon-proxy"], capture_output=True, check=False)
+
+    # 3. Generate Root CA cert
+    from sandbox_executor.token_reduction.ca_generator import generate_root_ca
+
+    ca_cert_path, _ = generate_root_ca()
+
+    # 4. Resolve host addon path
+    addon_dir = os.path.dirname(os.path.abspath(__file__))
+    addon_path = os.path.join(addon_dir, "token_reduction", "mitm_addon.py")
+
+    # 5. Start the holon-proxy docker sidecar
+    # We mount ~/.holon folder to persist cache db in /home/mitmproxy/.holon inside container
+    home_dir = os.path.expanduser("~")
+    holon_home = os.path.join(home_dir, ".holon")
+    os.makedirs(holon_home, exist_ok=True)
+
+    docker_run_proxy = [
+        "docker",
+        "run",
+        "-d",
+        "--name",
+        "holon-proxy",
+        "--network",
+        "holon-net",
+        "-v",
+        f"{holon_home}:/home/mitmproxy/.holon",
+        "-v",
+        f"{addon_path}:/tmp/mitm_addon.py:ro",
+        "mitmproxy/mitmproxy:12.2.3",
+        "mitmdump",
+        "-s",
+        "/tmp/mitm_addon.py",
+        "--listen-port",
+        "8080",
+    ]
+
+    proxy_spawn = subprocess.run(docker_run_proxy, capture_output=True, text=True, check=False)
+    if proxy_spawn.returncode != 0:
+        logger.warning("Failed to start mitmproxy sidecar container: %s", proxy_spawn.stderr)
+        # Fallback to local default proxy url if sidecar fails
+        proxy_url = "http://172.17.0.1:8080"
+        mounts = []
+    else:
+        # Wait a moment for proxy to initialize
+        time.sleep(1.0)
+        proxy_url = "http://holon-proxy:8080"
+        mounts = ["--network", "holon-net"]
+
+    container_cert_path = "/usr/local/share/ca-certificates/holon-root-ca.crt"
+    mounts.extend(["-v", f"{ca_cert_path}:{container_cert_path}:ro"])
+
+    env_vars = {
+        "HTTP_PROXY": proxy_url,
+        "HTTPS_PROXY": proxy_url,
+        "NODE_EXTRA_CA_CERTS": container_cert_path,
+        "REQUESTS_CA_BUNDLE": container_cert_path,
+        "CURL_CA_BUNDLE": container_cert_path,
+        "SSL_CERT_FILE": container_cert_path,
+    }
+    return mounts, env_vars
+
+
+def get_token_reduction_mounts_and_envs(
+    token_reduce: bool = False,
+) -> tuple[list[str], dict[str, str]]:
+    """Generates Root CA cert and constructs proxy volume mounts and environment variables."""
+    mounts = []
+    env_vars = {}
+
+    if token_reduce:
+        try:
+            return setup_token_reduction_proxy()
+        except Exception as e:
+            logger.warning("Failed to configure token reduction proxy sidecar: %s", e)
+    elif os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"):
+        try:
+            from sandbox_executor.token_reduction.ca_generator import generate_root_ca
+
+            ca_cert_path, _ = generate_root_ca()
+            container_cert_path = "/usr/local/share/ca-certificates/holon-root-ca.crt"
+            mounts.extend(["-v", f"{ca_cert_path}:{container_cert_path}:ro"])
+
+            proxy_url = os.getenv("HOLON_PROXY_URL") or os.getenv("HTTP_PROXY") or "http://172.17.0.1:8080"
+            env_vars["HTTP_PROXY"] = proxy_url
+            env_vars["HTTPS_PROXY"] = proxy_url
+            env_vars["NODE_EXTRA_CA_CERTS"] = container_cert_path
+            env_vars["REQUESTS_CA_BUNDLE"] = container_cert_path
+            env_vars["CURL_CA_BUNDLE"] = container_cert_path
+            env_vars["SSL_CERT_FILE"] = container_cert_path
+        except Exception as e:
+            logger.warning("Failed to configure token reduction proxy mounts: %s", e)
+
+    return mounts, env_vars
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
@@ -157,6 +262,12 @@ def run_docker_container(
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
@@ -185,8 +296,12 @@ def run_docker_container(
         else:
             sanitized_cmd.append(item)
     print(f"Executing: {' '.join(sanitized_cmd)}")
-    result = subprocess.run(docker_cmd)
-    return result.returncode
+    try:
+        result = subprocess.run(docker_cmd)
+        return result.returncode
+    finally:
+        if token_reduce:
+            subprocess.run(["docker", "rm", "-f", "holon-proxy"], capture_output=True, check=False)


 def main() -> None:
@@ -213,12 +328,22 @@ def main() -> None:
         default="gemini-3.5-flash",
         help="Model name to pass to agent (e.g. gemini-3.5-flash, claude-3-5-sonnet)",
     )
+    plan_parser.add_argument(
+        "--token-reduce",
+        action="store_true",
+        help="Enable MITM proxy and SSL CA mounts for agent token reduction",
+    )

     # Subcommand: execute
     exec_parser = subparsers.add_parser("execute", help="Run Sandbox Executor to execute code changes for a plan.")
     exec_parser.add_argument("plan_branch", help="Target plan branch name")
     exec_parser.add_argument("--agent", default="antigravity-agent", help="Agent runner to execute")
     exec_parser.add_argument("--model", default="gemini-3.5-flash", help="Model name to pass to agent")
+    exec_parser.add_argument(
+        "--token-reduce",
+        action="store_true",
+        help="Enable MITM proxy and SSL CA mounts for agent token reduction",
+    )

     args = parser.parse_args()

@@ -241,12 +366,28 @@ def main() -> None:
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
index 0000000..c4dcb1e
--- /dev/null
+++ b/apps/sandbox-executor/src/sandbox_executor/token_reduction/ca_generator.py
@@ -0,0 +1,83 @@
+"""Automated Root CA certificate generator for MITM proxy SSL/TLS trust."""
+
+import logging
+import os
+import subprocess
+
+logger = logging.getLogger(__name__)
+
+
+def generate_root_ca(cert_dir: str | None = None) -> tuple[str, str]:
+    """Generates a self-signed Root CA certificate and private key if not already present.
+
+    Args:
+        cert_dir: Directory where certs should be stored. Defaults to ~/.holon/certs.
+
+    Returns:
+        tuple[str, str]: Paths to (ca_cert_path, ca_key_path).
+    """
+    if cert_dir is None:
+        cert_dir = os.path.expanduser("~/.holon/certs")
+
+    os.makedirs(cert_dir, exist_ok=True)
+    ca_cert_path = os.path.join(cert_dir, "holon-root-ca.crt")
+    ca_key_path = os.path.join(cert_dir, "holon-root-ca.key")
+
+    if os.path.exists(ca_cert_path) and os.path.exists(ca_key_path):
+        logger.info("Root CA certificate already exists at %s", ca_cert_path)
+        return ca_cert_path, ca_key_path
+
+    logger.info("Generating self-signed Root CA certificate at %s", cert_dir)
+
+    try:
+        subprocess.run(
+            [
+                "openssl",
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
+            check=True,
+            capture_output=True,
+            text=True,
+        )
+    except Exception as exc:
+        logger.warning(
+            "OpenSSL CA generation failed or openssl not found: %s. Generating fallback cert.",
+            exc,
+        )
+        _generate_fallback_cert(ca_cert_path, ca_key_path)
+
+    return ca_cert_path, ca_key_path
+
+
+def _generate_fallback_cert(cert_path: str, key_path: str) -> None:
+    """Fallback generator writing basic PEM files if openssl binary is missing."""
+    dummy_key = (
+        "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC5\n-----END PRIVATE KEY-----\n"
+    )
+    dummy_cert = (
+        "-----BEGIN CERTIFICATE-----\n"
+        "MIIDdTCCAl2gAwIBAgIUHOLONROOTCA00000000000000000001MA0GCSqGSIb3\n"
+        "-----END CERTIFICATE-----\n"
+    )
+    with open(key_path, "w") as kf:
+        kf.write(dummy_key)
+    with open(cert_path, "w") as cf:
+        cf.write(dummy_cert)
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
index 0000000..e42a221
--- /dev/null
+++ b/apps/sandbox-executor/tests/test_token_reduction.py
@@ -0,0 +1,47 @@
+"""Unit tests for AI Agent Token Reduction Architecture - Phase 1."""
+
+import os
+import shutil
+import tempfile
+
+import pytest
+from sandbox_executor.cli import get_token_reduction_mounts_and_envs
+from sandbox_executor.token_reduction.ca_generator import generate_root_ca
+
+
+@pytest.fixture
+def temp_dir():
+    td = tempfile.mkdtemp()
+    yield td
+    shutil.rmtree(td, ignore_errors=True)
+
+
+def test_ca_generator(temp_dir):
+    cert_path, key_path = generate_root_ca(cert_dir=temp_dir)
+    assert os.path.exists(cert_path)
+    assert os.path.exists(key_path)
+    assert cert_path.endswith("holon-root-ca.crt")
+    assert key_path.endswith("holon-root-ca.key")
+
+    # Second call should reuse existing cert
+    c2, k2 = generate_root_ca(cert_dir=temp_dir)
+    assert c2 == cert_path
+    assert k2 == key_path
+
+
+def test_cli_token_reduction_mounts(monkeypatch, temp_dir):
+    monkeypatch.setattr(
+        "sandbox_executor.cli.setup_token_reduction_proxy",
+        lambda: (
+            ["--network", "holon-net", "-v", f"{temp_dir}/ca.crt:/container/ca.crt:ro"],
+            {
+                "HTTP_PROXY": "http://holon-proxy:8080",
+                "HTTPS_PROXY": "http://holon-proxy:8080",
+            },
+        ),
+    )
+
+    mounts, envs = get_token_reduction_mounts_and_envs(token_reduce=True)
+    assert "--network" in mounts
+    assert envs["HTTP_PROXY"] == "http://holon-proxy:8080"
+    assert envs["HTTPS_PROXY"] == "http://holon-proxy:8080"
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
```

## Output Requirements (MANDATORY)

1. Perform the review yourself in THIS single agent pass. Do NOT spawn further subagents.
2. Ground every finding in the actual diff. You may read files in the current working directory (the PR head worktree)
   to verify context. Do NOT modify any source file.
3. DRY-RUN MODE: do NOT run `gh pr review`, do NOT post comments to GitHub, do NOT commit or push.
4. Write your full structured review report (Role Activation Matrix, Persona Reviews, Overall Verdict) to this exact
   absolute path: /Users/thomashan/git/holon-agentic-coder-ref-metadata/.subagent/dry_run_review_iter_1_59e70bd.md
5. Then print to stdout, as your final message, EXACTLY these three lines: VERDICT: <APPROVED | CHANGES_REQUESTED |
   COMMENT> COUNTS: CRITICAL=<n> IMPORTANT=<n> NIT=<n> REPORT:
   /Users/thomashan/git/holon-agentic-coder-ref-metadata/.subagent/dry_run_review_iter_1_59e70bd.md
