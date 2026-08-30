# PR Review Report: feat(sandbox-executor): implement SSL trust and CA mounts (Phase 1)

This report contains findings from the Dry-Run code review of Pull Request #48 in the
`Holon-Agentic-Coder/holon-agentic-coder-ref` repository.

---

### 📊 PR Metadata & Role Activation

| Persona                            | Status (🟢 / ⚪) | Primary Trigger (Which files/contexts triggered activation)              |
| :--------------------------------- | :--------------- | :----------------------------------------------------------------------- |
| **Engineering & Architecture**     |                  |                                                                          |
| Principal Engineer                 | 🟢               | Changes to Python CLI logic, process lifecycle, and ca_generator.py      |
| Solution Architect                 | 🟢               | Mitmproxy container integration, networks, and host mounts configuration |
| Frontend Engineer                  | ⚪               | No client-facing UI or frontend files modified                           |
| QA & Test Engineer                 | 🟢               | Integration of tests in `tests/test_token_reduction.py`                  |
| ML & Data Specialist               | ⚪               | No AI modeling, training, or data pipelines modified                     |
| **Product, Design, & Growth**      |                  |                                                                          |
| Product Owner                      | 🟢               | Modified ledger files in `holon-knowledge/ledger/` and planning files    |
| UX/UI Designer                     | ⚪               | No design system or interface assets modified                            |
| SEO & Growth Specialist            | ⚪               | No metadata, page redirects, or web assets modified                      |
| **Operations, Release, & Support** |                  |                                                                          |
| DevOps & SRE                       | 🟢               | Modifications to `role_dispatcher.sh` and container trust anchors        |
| Release Manager                    | ⚪               | No database migrations or staging flow dependencies modified             |
| Support Engineer                   | 🟢               | User-facing preflight binary checks and error logging messages           |
| **Security, Compliance, & Risk**   |                  |                                                                          |
| Security Architect                 | 🟢               | Host Root CA certificate generation and private key boundaries           |
| Compliance Auditor                 | ⚪               | No licensing checks or regulatory compliance files modified              |
| Localization Coordinator           | ⚪               | No translation keys, localized dates or layout files modified            |
| **DevRel & Documentation**         |                  |                                                                          |
| Technical Writer                   | 🟢               | Documentation updates in `README.md` and `docs/sandbox/`                 |
| Developer Advocate                 | ⚪               | No public-facing developer SDK or API modifications                      |

---

### 🔍 Persona Reviews

#### 👥 Security Architect Review

- **🔴 CRITICAL / BLOCKER [apps/sandbox-executor/src/sandbox_executor/token_reduction/ca_generator.py lines 633-650]**:
  Missing CA Extensions in Generated Certificate
  - **Context**: The CA certificate is generated using `openssl req -x509` without explicit CA constraints and key
    usages. Modern TLS verification stacks (BoringSSL/Node, Go, OpenSSL) reject certificates as trust anchors if they
    lack the appropriate CA attributes.
  - **Recommendation**: Pass explicit CA extensions (`basicConstraints=critical,CA:TRUE`,
    `keyUsage=critical,keyCertSign,cRLSign`, and `subjectKeyIdentifier=hash`) when running `openssl req`.
  - **Proposed Code Change**:
    ```diff
    @@ -633,18 +633,25 @@ def generate_root_ca(cert_dir: str | None = None) -> tuple[str, str]:
             [
                 openssl_path,
                 "req",
                 "-x509",
                 "-newkey",
                 "rsa:2048",
                 "-keyout",
                 ca_key_path,
                 "-out",
                 ca_cert_path,
                 "-days",
    ```
-                "365",

*                str(_CA_VALIDITY_DAYS),
                 "-nodes",
                 "-subj",
                 "/CN=Holon Agent Root CA/O=Holon Agentic Coder",
*                "-addext",
*                "basicConstraints=critical,CA:TRUE",
*                "-addext",
*                "keyUsage=critical,keyCertSign,cRLSign",
*                "-addext",
*                "subjectKeyIdentifier=hash",
             ],
  ```

  ```

- **🔴 CRITICAL / BLOCKER [apps/sandbox-executor/src/sandbox_executor/cli.py lines 262-293]**: mitmproxy Container
  Missing Access to CA Private Key
  - **Context**: TLS interception requires the proxy sidecar to sign dynamic leaf certificates using the Root CA's
    private key. In the current implementation, only the public certificate is mounted into the sandbox container. No CA
    private key is mounted into the mitmproxy container. The proxy will generate its own ephemeral CA, causing TLS
    validation failures inside the sandbox.
  - **Recommendation**: Materialize a combined PEM bundle (`mitmproxy-ca.pem` containing both certificate and private
    key, mode `0600`) and mount it read-only to `/home/mitmproxy/.mitmproxy/mitmproxy-ca.pem` in the mitmproxy sidecar
    container. Keep the private key away from the agent's sandbox container.
  - **Proposed Code Change**:
    ```diff
    @@ -280,6 +280,10 @@ def setup_token_reduction_proxy() -> tuple[list[str], dict[str, str]]:
             f"127.0.0.1::{PROXY_LISTEN_PORT}",
             "-v",
             f"{proxy_cache_dir}:/home/mitmproxy/.holon/proxy-cache:ro",
    +        "-v",
    +        f"{mitm_ca_combined}:{MITM_PROXY_CA_DIR}/mitmproxy-ca.pem:ro",
    +        "-v",
    +        f"{mitm_ca_cert}:{MITM_PROXY_CA_DIR}/mitmproxy-ca-cert.pem:ro",
             "-v",
             f"{addon_path}:/tmp/mitm_addon.py:ro",
    ```

- **🟡 IMPORTANT / IMPROVEMENT [apps/sandbox-executor/src/sandbox_executor/token_reduction/ca_generator.py lines
  619-623]**: Missing CA Certificate Expiry and Renewal Check
  - **Context**: The CA generator currently checks for file existence only. It does not check if the cached CA
    certificate has expired or is close to expiry. Over time, expired trust anchors will silently break all intercepted
    TLS streams.
  - **Recommendation**: Inspect certificate expiry using `openssl x509 -checkend <seconds>` and trigger regeneration if
    the CA certificate will expire within a renewal window (e.g. 30 days).
  - **Proposed Code Change**:
    ```diff
    @@ -619,5 +619,14 @@ def generate_root_ca(cert_dir: str | None = None) -> tuple[str, str]:
         if os.path.exists(ca_cert_path) and os.path.exists(ca_key_path):
    -        logger.info("Reusing existing Root CA certificate at %s", ca_cert_path)
             _assert_valid_cert(ca_cert_path)
    -        _harden_key_permissions(ca_key_path)
    -        return ca_cert_path, ca_key_path
    +        if _expires_within(ca_cert_path, _CA_RENEWAL_WINDOW_SECONDS):
    +            logger.warning(
    +                "Cached Root CA at %s expires within %s days; regenerating it.",
    +                ca_cert_path,
    +                _CA_RENEWAL_WINDOW_SECONDS // 86400,
    +            )
    +            _remove_cached_ca(ca_cert_path, ca_key_path)
    +        else:
    +            logger.info("Reusing existing Root CA certificate at %s", ca_cert_path)
    +            _harden_key_permissions(ca_key_path)
    +            return ca_cert_path, ca_key_path, False
    ```

---

#### 👥 DevOps & SRE Review

- **🔴 CRITICAL / BLOCKER [apps/sandbox-executor/entrypoint/role_dispatcher.sh lines 67-71]**: `update-ca-certificates`
  Fails Under Unprivileged User Mode
  - **Context**: The sandbox container image drops root privileges and runs as the `holon` user (`USER holon` in
    Dockerfile). Running `update-ca-certificates` inside the entrypoint requires root privileges to write under
    `/etc/ssl/certs` and will fail silently. As a result, the Holon Root CA is never added to the trust store.
  - **Recommendation**: Instead of calling `update-ca-certificates`, concatenate the system store
    `/etc/ssl/certs/ca-certificates.crt` and the Holon Root CA into `/home/holon/.holon-ca-bundle.crt`. Export the
    environment variables `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, and `CURL_CA_BUNDLE` pointing to this combined file.
    Point `NODE_EXTRA_CA_CERTS` directly to the single-cert Holon CA mount (as Node.js accepts single augmenting files).
  - **Proposed Code Change**:
    ```diff
    @@ -67,5 +67,31 @@
    -HOLON_ROOT_CA_PATH="/usr/local/share/ca-certificates/holon-root-ca.crt"
    -if [ -f "$HOLON_ROOT_CA_PATH" ] && command -v update-ca-certificates &>/dev/null; then
    -    update-ca-certificates >/dev/null 2>&1 || true
    -fi
    +HOLON_ROOT_CA_PATH="${HOLON_ROOT_CA_PATH:-/usr/local/share/ca-certificates/holon-root-ca.crt}"
    +HOLON_CA_BUNDLE_PATH="${HOLON_CA_BUNDLE_PATH:-/home/holon/.holon-ca-bundle.crt}"
    +SYSTEM_CA_BUNDLE="${SYSTEM_CA_BUNDLE:-/etc/ssl/certs/ca-certificates.crt}"
    +
    +if [ -f "$HOLON_ROOT_CA_PATH" ]; then
    +    if [ -r "$SYSTEM_CA_BUNDLE" ]; then
    +        HOLON_CA_SOURCES=("$SYSTEM_CA_BUNDLE" "$HOLON_ROOT_CA_PATH")
    +    else
    +        HOLON_CA_SOURCES=("$HOLON_ROOT_CA_PATH")
    +    fi
    +    if cat "${HOLON_CA_SOURCES[@]}" > "$HOLON_CA_BUNDLE_PATH"; then
    +        chmod 600 "$HOLON_CA_BUNDLE_PATH"
    +        export SSL_CERT_FILE="$HOLON_CA_BUNDLE_PATH"
    +        export REQUESTS_CA_BUNDLE="$HOLON_CA_BUNDLE_PATH"
    +        export CURL_CA_BUNDLE="$HOLON_CA_BUNDLE_PATH"
    +        export NODE_EXTRA_CA_CERTS="$HOLON_ROOT_CA_PATH"
    +    else
    +        unset SSL_CERT_FILE REQUESTS_CA_BUNDLE CURL_CA_BUNDLE
    +    fi
    +fi
    ```

- **🟡 IMPORTANT / IMPROVEMENT [apps/sandbox-executor/src/sandbox_executor/cli.py lines 419-438]**: Resource Leak on
  Exception During Container Startup
  - **Context**: In `run_docker_container()`, the proxy container and network resources are configured and set up.
    However, if an error or exception occurs after the sidecar is spun up but before `subprocess.run(docker_cmd)`
    finishes (e.g. if validation fails or config checks raise an error), `teardown_token_reduction_proxy()` is bypassed,
    leading to orphaned containers and networks.
  - **Recommendation**: Place the commands after `get_token_reduction_mounts_and_envs()` inside a `try-finally` block to
    guarantee that sidecar container and network resources are torn down under all conditions.
  - **Proposed Code Change**:
    ```diff
    @@ -419,20 +419,23 @@ def run_docker_container(
         # Token Reduction Proxy & CA Mounts
         tr_mounts, tr_envs = get_token_reduction_mounts_and_envs(token_reduce=token_reduce)
    -    docker_cmd.extend(tr_mounts)
    -    for k, v in tr_envs.items():
    -        docker_cmd.extend(["-e", f"{k}={v}"])
    -
    -    # Intent file mount for intent-creator role
    -    ...
    -    print(f"Executing: {' '.join(sanitized_cmd)}")
    -    result = subprocess.run(docker_cmd)
    -    return result.returncode
    +    try:
    +        docker_cmd.extend(tr_mounts)
    +        for k, v in tr_envs.items():
    +            docker_cmd.extend(["-e", f"{k}={v}"])
    +        # ... rest of the setup code ...
    +        result = subprocess.run(docker_cmd)
    +        return result.returncode
    +    finally:
    +        teardown_token_reduction_proxy()
    ```

---

#### 👥 Technical Writer Review

- **🟡 IMPORTANT / IMPROVEMENT [README.md, docs/sandbox/create_plan.md, docs/sandbox/execute_plan.md]**: Misleading
  Readiness Posture in Documentation
  - **Context**: The documentation presents `--token-reduce` as a fully functional feature in Phase 1. However, since
    the Phase 2 mitmproxy addon (`mitm_addon.py`) is not shipped in Phase 1, `--token-reduce` is not yet functional in
    this release.
  - **Recommendation**: Clarify in the documentation that `--token-reduce` is experimental and not yet functional for
    Phase 1 because the mitmproxy addon is scheduled for Phase 2. Mention that preflight checks will fall back to direct
    egress.

---

### 🏆 Overall Verdict

- **❌ CHANGES REQUESTED**: The PR cannot be merged as-is because the CA injection mechanism fails completely due to
  user privileges, and the sidecar cannot perform TLS interception without the CA private key. Address the Critical
  findings.
