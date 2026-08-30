# PR Review Report: feat(sandbox-executor): implement context cleaning and prompt cache optimization (Phase 2)

- **PR Number**: 45
- **Branch**: `I-1787928862-token-reduction-phase2/...`
- **Head Commit**: `3be2956`
- **Verdict**: `CHANGES_REQUESTED` ❌

---

## 📊 PR Metadata & Role Activation Matrix

| Persona                            | Status (🟢 / ⚪) | Primary Trigger (Which files/contexts triggered activation)                                              |
| :--------------------------------- | :--------------- | :------------------------------------------------------------------------------------------------------- |
| **Engineering & Architecture**     |                  |                                                                                                          |
| Principal Engineer                 | 🟢               | `payload_cleaner.py`, `ca_generator.py`, `cli.py` (evaluating cleaner logic, CA generation, CLI options) |
| Solution Architect                 | 🟢               | `payload_cleaner.py`, `cli.py` (evaluating overall token reduction architecture, proxy connection flow)  |
| Frontend Engineer                  | ⚪               | No frontend files changed                                                                                |
| QA & Test Engineer                 | 🟢               | `test_token_reduction.py` (evaluating tests for cleaner and CA generation)                               |
| ML & Data Specialist               | ⚪               | No ML files or models changed                                                                            |
| **Product, Design, & Growth**      |                  |                                                                                                          |
| Product Owner                      | ⚪               | No direct business logic, feature flags or release plan files changed                                    |
| UX/UI Designer                     | ⚪               | No UI/UX or design assets changed                                                                        |
| SEO & Growth Specialist            | ⚪               | No web, SEO, or growth marketing changes                                                                 |
| **Operations, Release, & Support** |                  |                                                                                                          |
| DevOps & SRE                       | 🟢               | `cli.py` (evaluating mitmproxy sidecar Docker container startup and teardown, volume mounts)             |
| Release Manager                    | ⚪               | No staging, migration order, or rollback runbooks changed                                                |
| Support Engineer                   | ⚪               | No user-facing error messages, diagnostics or compatibility changes                                      |
| **Security, Compliance, & Risk**   |                  |                                                                                                          |
| Security Architect                 | 🟢               | `ca_generator.py` (evaluating Root CA certificate generation, private keys, SSL trust config)            |
| Compliance Auditor                 | ⚪               | No compliance or third-party license conflicts                                                           |
| Localization Coordinator           | ⚪               | No translation keys or RTL formatting files changed                                                      |
| **DevRel & Documentation**         |                  |                                                                                                          |
| Technical Writer                   | ⚪               | No documentation, README or API reference changes                                                        |
| Developer Advocate                 | ⚪               | No public SDK, API or developer onboarding friction changes                                              |

---

## 🔍 Persona Reviews

### 👥 Principal Engineer / Tech Lead Review

#### 🔴 CRITICAL / BLOCKER [payload_cleaner.py:L26, L88-L109](file:///Users/thomashan/git/holon-agentic-coder-ref-metadata/holon-agentic-coder-ref/I-1787928862-token-reduction-phase2/apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py#L26-L109): Memory State Leak / Incorrect Deduplication of Unique Messages across Turns

- **Context**: The `seen_content_hashes` dictionary is stored as an instance variable of the `ContextCleaner` class.
  Since the cleaner instance is persistent across different turns of an agent session, it retains the hashes of tool
  outputs processed in earlier turns. When `process_payload()` is invoked on later turns with the accumulated chat
  history, the unique tool outputs from previous turns (which are now "older turns") match these stored hashes and are
  immediately omitted (`[Omitted: ...]`). This results in the complete omission of unique, non-repeating tool results
  once they are older than 2 turns, rendering the LLM blind to its past actions.
- **Recommendation**: Clear `seen_content_hashes` at the start of each payload processing call so that only actual
  duplicates _within_ the current payload's history are omitted.
- **Proposed Code Change**:
  ```diff
  @@ -28,3 +28,4 @@
       def process_payload(self, payload: dict[str, Any], provider: str = "anthropic") -> dict[str, Any]:
           """Processes and optimizes an outgoing LLM JSON request payload.
           """
  +        self.seen_content_hashes = {}
           cleaned_payload = json.loads(json.dumps(payload))  # deep copy
  ```

#### 🔴 CRITICAL / BLOCKER [payload_cleaner.py:L115-L129](file:///Users/thomashan/git/holon-agentic-coder-ref-metadata/holon-agentic-coder-ref/I-1787928862-token-reduction-phase2/apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py#L115-L129): Anthropic Alternating Roles API Violation during Summarization

- **Context**: In `_summarize_anthropic_history()`, a summary message with `role: "user"` is inserted immediately after
  the first message of the history (which typically also has `role: "user"`). This results in consecutive user messages.
  The Anthropic Messages API strictly requires alternating `user` and `assistant` roles, and consecutive messages of the
  same role will result in a 400 Bad Request error.
- **Recommendation**: Adjust the summarization logic to preserve alternating roles. If the first message and the summary
  message are consecutive user messages, they should either be merged into a single message or separated by a mock
  assistant turn.
- **Proposed Code Change**:
  ```python
  # Ensure strict role alternation when returning the new message list
  ```

#### 🟡 IMPORTANT / IMPROVEMENT [payload_cleaner.py:L151-L156](file:///Users/thomashan/git/holon-agentic-coder-ref-metadata/holon-agentic-coder-ref/I-1787928862-token-reduction-phase2/apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py#L151-L156): Message Cache Control Bypassed for String-based Message Contents

- **Context**: The `_inject_anthropic_cache_control` method only attempts to inject the cache control dictionary if
  `content` is a `list`. However, in many standard SDK uses and within this codebase, message `content` is a plain
  `string`. When `content` is a string, the injection logic is bypassed, and the prompt cache breakpoint is not applied
  to the recent message history.
- **Recommendation**: Support string content by converting it into a structured text block list containing
  `cache_control` when injection is requested.
- **Proposed Code Change**:
  ```diff
  @@ -151,6 +151,8 @@
               target_msg = messages[-2]
               content = target_msg.get("content")
               if isinstance(content, list) and len(content) > 0:
                   last_block = content[-1]
                   if isinstance(last_block, dict) and "cache_control" not in last_block:
                       last_block["cache_control"] = {"type": "ephemeral"}
  +            elif isinstance(content, str):
  +                target_msg["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
  ```

---

### 👥 Solution Architect Review

#### 🔴 CRITICAL / BLOCKER [cli.py:L140](file:///Users/thomashan/git/holon-agentic-coder-ref-metadata/holon-agentic-coder-ref/I-1787928862-token-reduction-phase2/apps/sandbox-executor/src/sandbox_executor/cli.py#L140): Broken Reference / Missing `mitm_addon.py` File

- **Context**: The `cli.py` changes reference `sandbox_executor/token_reduction/mitm_addon.py` as `addon_path` and
  attempt to mount it to the `holon-proxy` container. However, the file `mitm_addon.py` is completely missing from this
  branch/PR. When running with `--token-reduce`, Docker will fail to locate this file on the host, causing the sidecar
  container setup to fail.
- **Recommendation**: Ensure that the `mitm_addon.py` file is correctly committed and included in the PR branch.

---

### 👥 Security Architect Review

#### 🔴 CRITICAL / BLOCKER [ca_generator.py:L64-L77](file:///Users/thomashan/git/holon-agentic-coder-ref-metadata/holon-agentic-coder-ref/I-1787928862-token-reduction-phase2/apps/sandbox-executor/src/sandbox_executor/token_reduction/ca_generator.py#L64-L77): Broken and Insecure Fallback Certificates

- **Context**: The `_generate_fallback_cert` method writes a hardcoded private key and certificate. Not only is sharing
  a private key in source code a security risk, but the dummy key and certificate strings provided are severely
  truncated and syntactically malformed. If the fallback is triggered (e.g. on a host without `openssl`), `mitmproxy`
  will crash immediately upon failing to parse the invalid cert/key.
- **Recommendation**: Instead of writing invalid dummy PEM strings, the fallback should fail gracefully with a clear
  instruction to install `openssl`, or generate a valid self-signed certificate dynamically in memory.

---

### 👥 DevOps & SRE Review

#### 🟡 IMPORTANT / IMPROVEMENT [cli.py:L175-L177](file:///Users/thomashan/git/holon-agentic-coder-ref-metadata/holon-agentic-coder-ref/I-1787928862-token-reduction-phase2/apps/sandbox-executor/src/sandbox_executor/cli.py#L175-L177): Fragile Startup Wait time

- **Context**: After starting the `holon-proxy` container, the script runs `time.sleep(1.0)` to wait for the proxy to
  initialize before proceeding. Relying on a fixed sleep duration is fragile and can lead to race conditions or
  unnecessary delays, depending on host performance and docker daemon load.
- **Recommendation**: Implement a simple TCP connection probe or check container health before proceeding.

---

### 👥 QA & Test Engineer Review

#### 🟡 IMPORTANT / IMPROVEMENT [test_token_reduction.py:L33-L49](file:///Users/thomashan/git/holon-agentic-coder-ref-metadata/holon-agentic-coder-ref/I-1787928862-token-reduction-phase2/apps/sandbox-executor/tests/test_token_reduction.py#L33-L49): Incomplete Test Assertions and High Mocking

- **Context**: The `test_cli_token_reduction_mounts` test mocks out `setup_token_reduction_proxy` completely, which
  conceals the missing `mitm_addon.py` issue. Furthermore, `test_payload_cleaner_anthropic_deduplication` only asserts
  that the system block has cache control, failing to assert that the history message also has it (which would have
  revealed that string messages bypass caching).
- **Recommendation**: Add integration tests that test the actual proxy startup (or check if files exist), and expand
  cleaner assertions to verify message cache control and alternating roles validity.

---

## 🏆 Overall Verdict

**❌ CHANGES REQUESTED**

Four Critical blockers must be resolved before this PR can be merged:

1. Fix the memory state leak in `ContextCleaner.seen_content_hashes` by resetting it on each `process_payload()` call.
2. Fix the alternating roles violation in `_summarize_anthropic_history`.
3. Include the missing `mitm_addon.py` file in the branch.
4. Replace the malformed/broken fallback certificates logic in `ca_generator.py`.
