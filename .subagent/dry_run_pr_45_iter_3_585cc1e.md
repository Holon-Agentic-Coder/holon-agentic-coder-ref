# Pull Request Review Report (Dry-Run Mode)

**PR Link:** https://github.com/Holon-Agentic-Coder/holon-agentic-coder-ref/pull/45  
**Commit:** `585cc1e`  
**Review Execution Mode:** Dry-Run / Single-Agent

---

### 📊 PR Metadata & Role Activation

| Persona                            | Status (🟢 / ⚪) | Primary Trigger (Which files/contexts triggered activation)                            |
| :--------------------------------- | :--------------- | :------------------------------------------------------------------------------------- |
| **Engineering & Architecture**     |                  |                                                                                        |
| Principal Engineer                 | 🟢               | Triggered by implementation details of `payload_cleaner.py` and `mitm_addon.py`.       |
| Solution Architect                 | 🟢               | Triggered by LLM API integration patterns and sidecar design.                          |
| Frontend Engineer                  | ⚪               | No frontend, client-side state, or styling changes.                                    |
| QA & Test Engineer                 | 🟢               | Triggered by modifications to `test_token_reduction.py`.                               |
| ML & Data Specialist               | ⚪               | No model training or pipeline changes.                                                 |
| **Product, Design, & Growth**      |                  |                                                                                        |
| Product Owner                      | ⚪               | No user stories or PM requirements logic updates.                                      |
| UX/UI Designer                     | ⚪               | No UI components or Figma designs.                                                     |
| SEO & Growth Specialist            | ⚪               | No SEO or metadata changes.                                                            |
| **Operations, Release, & Support** |                  |                                                                                        |
| DevOps & SRE                       | 🟢               | Triggered by docker lifecycle, certificates, and proxy environment config in `cli.py`. |
| Release Manager                    | ⚪               | No deployment order or database migrations.                                            |
| Support Engineer                   | ⚪               | No customer-facing diagnostic changes.                                                 |
| **Security, Compliance, & Risk**   |                  |                                                                                        |
| Security Architect                 | ⚪               | (Evaluated under Tech Lead and SRE roles for key exposure).                            |
| Compliance Auditor                 | ⚪               | No license or compliance audits.                                                       |
| Localization Coordinator           | ⚪               | No translation or localization bundle changes.                                         |
| **DevRel & Documentation**         |                  |                                                                                        |
| Technical Writer                   | ⚪               | No documentation updates.                                                              |
| Developer Advocate                 | ⚪               | No public SDK changes.                                                                 |

---

### 🔍 Persona Reviews

#### 👥 Principal Engineer / Tech Lead Review

- **🔴 CRITICAL / BLOCKER [apps/sandbox-executor/src/sandbox_executor/cli.py#L271-L310]**: Concurrency & Race Condition
  in Proxy Lifecycle
  - **Context**: The helper function `setup_token_reduction_proxy` hardcodes the docker container name to
    `"holon-proxy"` and the network to `"holon-net"`. In Phase 1, these were uniquely generated per-run using
    `os.getpid()` and a UUID suffix to support parallel executions of the sandbox-executor. By hardcoding a static name,
    any concurrent runs will kill each other's sidecar proxy containers and cause execution failures.
  - **Recommendation**: Restore unique per-run suffixes for container name and network name, and ensure
    `teardown_token_reduction_proxy` cleans up the specific resources created by the run.
  - **Proposed Code Change**:
    ```diff
    -     # 1. Create docker network holon-net if not exists
    -     subprocess.run(["docker", "network", "create", "holon-net"], capture_output=True, check=False)
    -
    ```
-     # 2. Kill existing holon-proxy sidecar if running
-     subprocess.run(["docker", "rm", "-f", "holon-proxy"], capture_output=True, check=False)

*     run_suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
*     container_name = f"holon-proxy-{run_suffix}"
*     network_name = f"holon-net-{run_suffix}"
  ```

  ```

- **🟢 NIT / OPTIONAL [apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py#L928-L975]**:
  Missing Merge Consecutive Roles in OpenAI Context Cleaner
  - **Context**: In `_clean_openai`, if conversation history is summarized, the cleaner inserts a `summary_msg` with
    role `"user"` between `prefix` and `suffix`. Because `suffix` begins with a clean user message, this can lead to
    consecutive user messages in the final payload. While the OpenAI API is less strict about role alternation than
    Anthropic, calling `_merge_consecutive_roles` would ensure consistency and cleaner payload structure.
  - **Recommendation**: Add a call to `self._merge_consecutive_roles` in `_clean_openai` after history summarization is
    performed.
  - **Proposed Code Change**:
    ```diff
                     cleaned_messages = [*prefix, summary_msg, *suffix]
    ```

*                    cleaned_messages = self._merge_consecutive_roles(cleaned_messages)
  ```

  ```

---

#### 👥 Solution Architect Review

- **🔴 CRITICAL / BLOCKER [apps/sandbox-executor/src/sandbox_executor/cli.py#L271-L310]**: Interception Egress Failure
  due to Missing CA Certificate Config in Proxy
  - **Context**: The `docker run` command starting the mitmproxy container does not mount the generated CA certificate
    and private key files (`mitmproxy-ca.pem` and `mitmproxy-ca-cert.pem`) into the container's
    `/home/mitmproxy/.mitmproxy/` directory. As a result, mitmproxy generates an ephemeral internal CA certificate on
    startup. The sandbox-executor container's clients (which trust the host-generated Root CA) will fail TLS handshake
    verification on all intercepted HTTPS requests.
  - **Recommendation**: Re-implement generating the combined PEM CA cert+key and mounting them to
    `/home/mitmproxy/.mitmproxy/mitmproxy-ca.pem:ro` and `/home/mitmproxy/.mitmproxy/mitmproxy-ca-cert.pem:ro`.
  - **Proposed Code Change**:
    ```diff
              "--name",
              "holon-proxy",
              "--network",
              "holon-net",
    ```
-             "-v",
-             f"{holon_home}:/home/mitmproxy/.holon",

*             "-v",
*             f"{mitm_ca_combined}:/home/mitmproxy/.mitmproxy/mitmproxy-ca.pem:ro",
*             "-v",
*             f"{mitm_ca_cert}:/home/mitmproxy/.mitmproxy/mitmproxy-ca-cert.pem:ro",
  ```

  ```

---

#### 👥 QA & Test Engineer Review

- **🟡 IMPORTANT / IMPROVEMENT [apps/sandbox-executor/tests/test_token_reduction.py]**: Deletion of Critical CLI and
  Proxy Integration Tests
  - **Context**: The PR deletes all tests verifying proxy setup, docker network creation, CA cert regeneration upon
    expiry, and sidecar containment options (`test_setup_proxy_*`, `test_teardown_*`, etc.). The new tests only verify
    the `ContextCleaner` payload logic, leaving the entire CLI wrapper integration and proxy container configuration
    completely untested and unverified.
  - **Recommendation**: Restore the deleted test suite and adapt it to verify the updated CLI integration logic,
    ensuring actual proxy setup and error pathways are thoroughly tested.

---

#### 👥 DevOps & Site Reliability Engineer (SRE) Review

- **🔴 CRITICAL / BLOCKER [apps/sandbox-executor/src/sandbox_executor/cli.py#L431-L439]**: Over-scoped CA Mount and SSL
  Bundle Replacement Vulnerability
  - **Context**: In `get_token_reduction_mounts_and_envs`, the environment variables `SSL_CERT_FILE`,
    `REQUESTS_CA_BUNDLE`, and `CURL_CA_BUNDLE` are pointed directly to `container_cert_path` (the individual Holon Root
    CA cert). These environment variables _replace_ the system's root store instead of augmenting it. Therefore, the
    container's clients will trust _only_ the Holon proxy, breaking connectivity to any other standard HTTPS endpoints
    (such as GitHub, public package repositories, etc.) when proxying is bypassed.
  - **Recommendation**: Construct and mount a merged trust bundle (system roots + Holon root CA) at container start, and
    point replacement env vars to it, or only set `NODE_EXTRA_CA_CERTS` and standard `HTTP_PROXY`/`HTTPS_PROXY`
    variables without overwriting system-level bundles.
  - **Proposed Code Change**:
    ```diff
          env_vars = {
              "HTTP_PROXY": proxy_url,
              "HTTPS_PROXY": proxy_url,
              "NODE_EXTRA_CA_CERTS": container_cert_path,
    ```
-             "REQUESTS_CA_BUNDLE": container_cert_path,
-             "CURL_CA_BUNDLE": container_cert_path,
-             "SSL_CERT_FILE": container_cert_path,

*             "REQUESTS_CA_BUNDLE": container_merged_bundle_path,
*             "CURL_CA_BUNDLE": container_merged_bundle_path,
*             "SSL_CERT_FILE": container_merged_bundle_path,
          }
  ```

  ```

- **🟡 IMPORTANT / IMPROVEMENT [apps/sandbox-executor/src/sandbox_executor/cli.py#L295]**: Security Over-exposure of
  Root CA Private Key
  - **Context**: The `docker run` command mounts the entire host `~/.holon` folder into the proxy container as
    `/home/mitmproxy/.holon`. This directory contains the Root CA private key (`~/.holon/certs/holon-root-ca.key`) and
    the agent auth session stores. Exposing the Root CA private key and session keys to the intercepting proxy container
    unnecessarily increases the security risk if the container gets compromised.
  - **Recommendation**: Narrow the volume mount to only the cache directory (e.g., `~/.holon/proxy-cache`) and mount the
    combined CA certificate files separately and read-only, matching the Phase 1 security posture.
  - **Proposed Code Change**:
    ```diff

    ```
-             "-v",
-             f"{holon_home}:/home/mitmproxy/.holon",

*             "-v",
*             f"{proxy_cache_dir}:/home/mitmproxy/.holon/proxy-cache:ro",
  ```

  ```

---

### 🏆 Overall Verdict

**❌ CHANGES REQUESTED**

Several critical issues have been identified that will break container network routing, cause TLS handshake failures on
egress requests, and introduce concurrency issues/race conditions when running parallel executors. These must be
addressed before merging.

> [!NOTE] The CI build check (`gh pr checks`) has been deferred because critical and important issues were found during
> the code review evaluation.
