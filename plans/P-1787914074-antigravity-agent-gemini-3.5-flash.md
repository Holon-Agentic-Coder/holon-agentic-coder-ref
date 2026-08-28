# Plan for I-1787914053-token-reduction-plan

- **Plan ID:** P-1787914074-antigravity-agent-gemini-3.5-flash
- **Parent Intent ID:** NONE
- **Agent:** antigravity-agent/gemini-3.5-flash (version: 1.1.22)
- **Created At:** 2026-08-28T10:47:54.369Z

## Planner Autonomy Summary

- **Intent handling:** REFRAME
- **Reframed intent (if applicable):**
```json
{
  "slug": "token-reduction-plan-reframed",
  "description": "Implement AI Agent Token Reduction Architecture & Non-Escape Local Action Plan",
  "goal": "Design token reduction architecture and implement safe, local-only context cleaning, deduplication, and a process-level mocked semantic cache harness that complies with sandbox isolation constraints.",
  "target_branch": "develop",
  "branch": "I-1787914053-token-reduction-plan",
  "status": "proposed"
}
```
- **Exploration stance:** exploratory with 1–2 sentence justification. An exploratory stance is justified here to investigate local-only token reduction, hybrid caching, and in-process mocking techniques that bypass sandbox isolation limitations while preserving privacy and security.
- **Safety priority level:** elevated
- **Priority Justification:** The intent goals mention a system-wide MITM Proxy & Root CA trust mechanism which, if executed directly, would violate containment tiers in `docs/safety.md` and `world/constraints.md` by attempting privilege escalation and network escape. The safety level is elevated to ensure these actions are strictly prohibited and reframed to safe, in-process local mocks.

## Exploration

- **Proportion of steps that are exploratory:** 0.20
- **Justification:** Step 4 (implementing in-process mock HTTP proxy interceptors) represents an exploratory task to determine the cleanest way to intercept model library traffic without system-level network alterations.

## Overall Plan Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.85                  |
| entropy_pred        | 3.5                   |
| impact_pred         | 75.0                  |
| cost_pred           | 43.0                  |
| learning_value_pred | 7.0                   |
| ev_pred             | 23.2                  |

### Strategy Rationale

The overall plan metrics were derived as follows:
- **p_success_pred**: 0.85. Bounded by Step 4 (0.88), which is the bottleneck step due to the complexity of patching external model libraries (like `httpx` or `openai`) inside a sandboxed Python process.
- **entropy_pred**: 3.5. Derived from the maximum step entropy (3.0 for Step 4) with a minor safety buffer of 0.5. Reframing the intent to local-only components successfully keeps entropy low (compared to > 30.0 for VM sandbox system-wide proxy setup).
- **impact_pred**: 75.0. Delivering a complete local context-reduction library and testing harness offers high utility for debugging and optimization without sandbox escape risks.
- **cost_pred**: 43.0. Aggregated as the sum of all step-level cost predictions (3.0 + 8.0 + 12.0 + 15.0 + 5.0 = 43.0).
- **learning_value_pred**: 7.0. Matches the peak learning target reached in Step 4, which discovers new local interception patterns.
- **ev_pred**: 23.2. Derived using the standard formula `EV = p_success_pred * impact_pred + μ * learning_value_pred - λ * entropy_pred - cost_pred` with default weights `λ = 0.3` and `μ = 0.5` (`0.85 * 75.0 + 0.5 * 7.0 - 0.3 * 3.5 - 43.0 = 23.2`).

## Safety & Constraint Alignment

- **Key world ruleset constraints that affect this plan:**
  - `holon-config/world/constraints.md` (Sandbox Containment Tiers, Prefix-Based Isolation)
  - `docs/safety.md` (Sandbox Escape Detection, Safety Invariant 2: Sandboxing)
- **Potential violations or edge cases:**
  - Standard container and process sandboxes block outbound network requests. Attempting to deploy a live MITM proxy or installing system-wide Root certificates will trigger write violations outside the workspace or raise privilege escalation alerts.
  - Patching global network sockets/transports could inadvertently trigger sandbox network alerts.
- **Mitigations built into the plan:**
  - Reframing the system-wide MITM proxy to an in-process, mock transport patching library.
  - Ensuring all caching, cleaning, and indexing operations run strictly locally in-memory or within the active workspace.
- **Residual risk accepted (and why):**
  - None. By shifting to in-process mock hooks, we eliminate the need for privilege escalation or actual network communication, fully adhering to sandbox safety standards.
- **Allocated Entropy Budget:** 15.0
- **Predicted Plan Entropy:** 10.0
- **Budget Compliance:** The strategy fits within budget (Predicted Plan Entropy of 10.0 < 15.0 allocated).

## Plan Description & Strategy

This plan establishes the architecture and implements a local-only token reduction system. In Step 1, we compile the design specifications for token reduction. In Step 2, we implement context cleaning and message deduplication. In Step 3, we build the local hybrid/semantic cache. In Step 4, we design an in-process HTTP mock interceptor to route model queries through our token reduction system without network access or Root CA changes. In Step 5, we verify all features using unit tests.

---

## Step 1: Perform Info-Gathering & Technical Architecture Design

- **Sub‑intent recommendation:** NO
- **Reasoning:** Documentation and architectural specification with low execution risk.
- **Step Type:** INFO_GATHERING
- **Exploration level:** EXPLOIT

### Intent & Git Integration

- **Step Intent:** Create a technical architecture document defining the token optimization layers (cleaner, cache, local mock interceptor) and documenting how they align with sandbox constraints.
- **Git branch:** `I-1787914053-token-reduction-plan/step1-architecture-design`
- **Sub‑intent:** NONE

### Implementation Details (No code blocks, only logic/steps)

- Create `docs/architecture/token_reduction_spec.md`.
- Detail the multi-tiered context optimization architecture, explaining why system-wide MITM Proxy & Root CA trust are deferred/replaced by in-process mocking.
- Outline the interfaces for the Context Cleaner, Semantic Cache, and Mock Interceptor.
- Document safety and sandbox compliance constraints.

### Dependencies & Criticality

- **Depends on:** NONE
- **Is Bottleneck:** NO

### Safety & Constraint Considerations

- **Relevant rules:** `docs/safety.md`
- **Potential failure modes for this step:** None, documentation-only step.
- **Guardrails and early‑abort checks:** Ensure that no live network testing is proposed in the specification.

### Success & Discard Criteria

- **Success:** Technical specification `docs/architecture/token_reduction_spec.md` is successfully created and verified.
- **Discard:** Discard if the architecture violates any core sandbox constraints.

### Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.98                  |
| entropy_pred        | 1.0                   |
| impact_pred         | 40.0                  |
| cost_pred           | 3.0                   |
| learning_value_pred | 4.0                   |
| ev_pred             | 37.9                  |

### Step Metrics Rationale

High success probability and low entropy due to documentation-only nature, providing structure for subsequent steps.

---

## Step 2: Implement Context Cleaning & Deduplication Library

- **Sub‑intent recommendation:** NO
- **Reasoning:** Implementation of stateless python utility module with low architectural risk.
- **Step Type:** IMPLEMENTATION
- **Exploration level:** EXPLOIT

### Intent & Git Integration

- **Step Intent:** Implement a context cleaning and message deduplication library to filter redundant messages and minify prompt templates.
- **Git branch:** `I-1787914053-token-reduction-plan/step2-context-cleaner`
- **Sub‑intent:** NONE

### Implementation Details (No code blocks, only logic/steps)

- Create `apps/sandbox-executor/src/sandbox_executor/token_reduction/context_cleaner.py`.
- Implement a `ContextCleaner` class with methods for filtering duplicate user messages, consolidating redundant system prompts, and pruning historical chat interactions.
- Provide a prompt minification algorithm that trims whitespace, strips unnecessary comments/metadata, and compresses templates while retaining core instructions.
- Ensure all parsing logic is fully deterministic and utilizes standard python libraries.

### Dependencies & Criticality

- **Depends on:** Step 1
- **Is Bottleneck:** YES

### Safety & Constraint Considerations

- **Relevant rules:** `holon-config/world/ruleset.md` (Coding Conventions)
- **Potential failure modes for this step:** Malformed regex or parser errors corrupting prompt structures.
- **Guardrails and early‑abort checks:** Apply strict string format validation checks before and after cleaning.

### Success & Discard Criteria

- **Success:** `context_cleaner.py` cleanly minifies and deduplicates chat lists without loss of critical semantic instructions.
- **Discard:** Discard if parsing errors exceed 1% during mock trial cases.

### Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.95                  |
| entropy_pred        | 2.0                   |
| impact_pred         | 65.0                  |
| cost_pred           | 8.0                   |
| learning_value_pred | 5.0                   |
| ev_pred             | 55.65                 |

### Step Metrics Rationale

Standard logic library development with high predictability, low complexity, and clear specifications.

---

## Step 3: Implement Local Semantic Cache and RAG Mock Indexer

- **Sub‑intent recommendation:** YES
- **Reasoning:** Introduces a cache layer and state lookup mechanics that may benefit from a dedicated branch and evaluation.
- **Step Type:** IMPLEMENTATION
- **Exploration level:** BALANCED

- **Hypothesis being tested:** Local TF-IDF or simple vector approximations can accurately identify cache hits for semantic duplicates under sandbox limitations.
- **Learning target:** Measure lookup accuracy and compute cost of semantic caching in sandbox environments.
- **Maximum acceptable cost for this learning:** 12.0 cost units.

### Intent & Git Integration

- **Step Intent:** Build a local in-memory hybrid/semantic cache and mock indexer to avoid duplicate model calls.
- **Git branch:** `I-1787914053-token-reduction-plan/step3-local-cache`
- **Sub‑intent:** NONE

### Implementation Details (No code blocks, only logic/steps)

- Create `apps/sandbox-executor/src/sandbox_executor/token_reduction/semantic_cache.py`.
- Implement a `SemanticCache` class that performs exact prompt matching and fuzzy matching (TF-IDF/cosine similarity).
- Implement a mock local RAG indexer to manage chunks in-memory.
- Provide a simple serializer to persist cache entries in the local active workspace.

### Dependencies & Criticality

- **Depends on:** Step 1
- **Is Bottleneck:** NO

### Safety & Constraint Considerations

- **Relevant rules:** `holon-config/world/ruleset.md` (Testing Constraints)
- **Potential failure modes for this step:** Cache state file growth causing workspace size violations or performance degradation.
- **Guardrails and early‑abort checks:** Limit the cache size to 1000 items and file size to under 5MB.

### Success & Discard Criteria

- **Success:** `semantic_cache.py` successfully retrieves cached results for exact and semantic duplicate prompts locally.
- **Discard:** Discard if cache indexing adds latency exceeding 100ms per query.

### Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.92                  |
| entropy_pred        | 2.5                   |
| impact_pred         | 70.0                  |
| cost_pred           | 12.0                  |
| learning_value_pred | 6.0                   |
| ev_pred             | 54.65                 |

### Step Metrics Rationale

Slightly higher entropy due to similarity calculations and local file persistence, but holds significant learning value for local caching.

---

## Step 4: Implement In-Process Mock HTTP Proxy / Interceptor for Testing

- **Sub‑intent recommendation:** STRONGLY_YES
- **Reasoning:** Highest risk step involving network monkeypatching/interception; should be isolated with independent validation.
- **Step Type:** EXPLORATION
- **Exploration level:** EXPLORATORY

- **Hypothesis being tested:** Standard client libraries (like `httpx` and `requests`) can be monkeypatched in-process to redirect model API calls to the local token cleaner and cache layers without triggering sandbox escape or connection errors.
- **Learning target:** Understand the best way to hook client transports without raising sandbox connection errors.
- **Maximum acceptable cost for this learning:** 15.0 cost units.

### Intent & Git Integration

- **Step Intent:** Build an in-process proxy harness that intercepts client outbound HTTP calls and routes them through the token optimizer.
- **Git branch:** `I-1787914053-token-reduction-plan/step4-mock-interceptor`
- **Sub‑intent:** NEW

### Implementation Details (No code blocks, only logic/steps)

- Create `apps/sandbox-executor/src/sandbox_executor/token_reduction/interceptor.py`.
- Implement a mock transport or interceptor class that patches outbound HTTP client transports (`httpx.MockTransport` or custom request routing).
- Hook the interceptor to redirect API calls to the local `SemanticCache` and `ContextCleaner` first before attempting external connection.
- Ensure that the interceptor safely fails open (or throws local exceptions) without attempting actual network connections.

### Dependencies & Criticality

- **Depends on:** Step 2, Step 3
- **Is Bottleneck:** YES

### Safety & Constraint Considerations

- **Relevant rules:** `docs/safety.md#Sandbox-escape-detection`, `world/constraints.md#2-Sandbox-Containment-Tiers`
- **Potential failure modes for this step:** Unintentional outbound connections triggering sandbox termination.
- **Guardrails and early‑abort checks:** Ensure the mock transport raises a connection error/exception for any unhandled URLs, preventing actual network socket calls.

### Success & Discard Criteria

- **Success:** Client library outbound calls are successfully intercepted and processed by the context cleaner and cache, completely avoiding sandbox network alerts.
- **Discard:** Discard immediately if any actual network sockets are opened or if sandbox termination is triggered.

### Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.88                  |
| entropy_pred        | 3.0                   |
| impact_pred         | 75.0                  |
| cost_pred           | 15.0                  |
| learning_value_pred | 7.0                   |
| ev_pred             | 53.6                  |

### Step Metrics Rationale

High-entropy exploratory step due to client patching, but enables the core token reduction architecture safely inside sandboxed constraints.

---

## Step 5: Write Comprehensive Unit Tests and Run Sandbox Verification

- **Sub‑intent recommendation:** NO
- **Reasoning:** Standard testing step with well-understood mechanics and low risk.
- **Step Type:** TEST
- **Exploration level:** EXPLOIT

### Intent & Git Integration

- **Step Intent:** Add comprehensive unit tests and run validations for the cleaner, cache, and mock interceptor modules.
- **Git branch:** `I-1787914053-token-reduction-plan/step5-testing-validation`
- **Sub‑intent:** NONE

### Implementation Details (No code blocks, only logic/steps)

- Create `apps/sandbox-executor/tests/test_token_reduction.py`.
- Implement tests verifying `ContextCleaner` deduplication and minification.
- Implement tests for `SemanticCache` hits and misses.
- Implement mock integration tests ensuring the mock interceptor handles requests correctly.
- Execute the test suite using pytest to verify 100% compliance.

### Dependencies & Criticality

- **Depends on:** Step 4
- **Is Bottleneck:** YES

### Safety & Constraint Considerations

- **Relevant rules:** `holon-config/world/ruleset.md` (Testing Constraints)
- **Potential failure modes for this step:** Test framework attempting network calls during library init.
- **Guardrails and early‑abort checks:** Disable all external network access using pytest configuration or custom mock fixtures.

### Success & Discard Criteria

- **Success:** All test cases pass successfully.
- **Discard:** Discard if testing fails or is unstable.

### Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.96                  |
| entropy_pred        | 1.5                   |
| impact_pred         | 50.0                  |
| cost_pred           | 5.0                   |
| learning_value_pred | 3.0                   |
| ev_pred             | 44.05                 |

### Step Metrics Rationale

Low complexity, standard testing phase ensuring robustness of code changes before delivery.
