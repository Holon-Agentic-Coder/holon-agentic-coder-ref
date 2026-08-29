# PR Review — Dry Run (Iteration 1)

> **Mode:** Dry-Run (no comments posted to GitHub) **PR:**
> [#45 feat(sandbox-executor): implement context cleaning and prompt cache optimization (Phase 2)](https://github.com/Holon-Agentic-Coder/holon-agentic-coder-ref/pull/45)
> **Head commit:** `dc899b0d77ccbde42751e4efc8a06439750256c1` **Reviewer agent:** single-agent pass **Reviewed at:**
> 2026-08-29T14:44:54+10:00

---

## 📋 PR Summary

- **Author:** thomashan (Holon Intent/Planner/Executor Agents)
- **Base branch:** `develop`
- **Additions:** 711 lines | **Deletions:** 2 lines | **Changed files:** 8
- **Existing review decision:** None (one automated `github-code-quality` comment only)

### Files Changed

| File                                                                            | Change                                            |
| ------------------------------------------------------------------------------- | ------------------------------------------------- |
| `apps/sandbox-executor/src/sandbox_executor/token_reduction/__init__.py`        | Modified — exports `ContextCleaner`               |
| `apps/sandbox-executor/src/sandbox_executor/token_reduction/mitm_addon.py`      | **New** — mitmproxy interceptor                   |
| `apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py` | **New** — `ContextCleaner` core logic (305 lines) |
| `executions/E-1787928996-antigravity-agent-gemini-3.5-flash.md`                 | **New** — execution record                        |
| `holon-knowledge/ledger/executions.jsonl`                                       | Modified — appended execution entry               |
| `holon-knowledge/ledger/intents.jsonl`                                          | Modified — appended intent entry                  |
| `holon-knowledge/ledger/plans.jsonl`                                            | Modified — appended plan entry                    |
| `plans/P-1787928877-antigravity-agent-gemini-3.5-flash.md`                      | **New** — plan document                           |

---

## 🔴 Critical Issues

### C-1 — Hardcoded `/tmp/src` absolute path in `mitm_addon.py`

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/mitm_addon.py` (line 9)

```python
sys.path.insert(0, "/tmp/src")
```

**Severity:** 🔴 Critical

**Rationale:** This hardcodes an absolute path (`/tmp/src`) directly into production module code, violating the project
rule that strictly prohibits absolute paths in code (`.agents/rules.md` §4: _"Never use absolute paths ... in any
documentation, instructions, code comments, tool outputs, or task references"_). This path is not guaranteed to exist at
runtime in all execution environments, will silently fail path resolution, and makes the module non-portable. The
`sys.path.insert` at module load time is also an anti-pattern — proper packaging should handle the import path.

**Recommendation:** Remove the `sys.path.insert` line entirely. The `sandbox_executor` package should be importable from
its installed package path without manual path manipulation. If the MITM proxy needs to be run standalone, provide a
wrapper script or entry-point that configures `PYTHONPATH` via environment variable rather than mutating `sys.path` in
library code.

---

### C-2 — No tests added for `payload_cleaner.py` (plan promised `test_context_cleaner.py`)

**File:** `apps/sandbox-executor/tests/test_context_cleaner.py` — **missing from this PR**

**Severity:** 🔴 Critical

**Rationale:** The PR description and the committed plan (`plans/P-1787928877-antigravity-agent-gemini-3.5-flash.md`)
both explicitly define Step 3 as _"Implement comprehensive unit tests in
`apps/sandbox-executor/tests/test_context_cleaner.py`"_ with a success criterion of _"All unit tests pass successfully
under `pytest` with coverage above 90%."_ No test file appears anywhere in this diff. The PR adds 305 lines of complex
algorithmic logic (hashing, deduplication, cache injection, history summarization, role merging) with zero test
coverage. This directly contradicts the project's testing invariants in `.agents/rules.md` and the plan's own success
criteria.

**Recommendation:** Add `apps/sandbox-executor/tests/test_context_cleaner.py` covering at minimum:

- Tool output deduplication (Anthropic format): identical vs distinct hashes, threshold boundary (100-char minimum),
  older-turn vs current-turn guard.
- Cache control injection: system string → list conversion, tool list injection, `messages[-2]` targeting.
- History summarization: `max_turns` trigger, `suffix_idx` fallback logic, `_merge_consecutive_roles` for string and
  block content.
- OpenAI and Gemini paths: basic deduplication pass-through.
- Edge cases: empty `messages`, `content` as `None`, single-message payloads, unknown provider pass-through.

---

## 🟡 Important Issues

### I-1 — Mutable instance state on `ContextCleaner` is not thread-safe

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py` (lines ~36, ~45)

```python
self.seen_content_hashes: dict[str, tuple[int, str]] = {}  # instance state

def process_payload(self, payload, provider="anthropic"):
    self.seen_content_hashes = {}  # reset at top of each call
```

**Severity:** 🟡 Important

**Rationale:** `seen_content_hashes` is an instance-level dict that is reset at the start of every `process_payload`
call. While partially defensive, it introduces a thread-safety risk: if a single `ContextCleaner` instance is shared
across concurrent requests (e.g., in a multi-threaded mitmproxy context), two concurrent `process_payload` calls will
corrupt each other's hash state mid-execution. The `MITMProxyInterceptor.__init__` creates one shared `ContextCleaner()`
instance that persists for the lifetime of the addon process, making this a real concurrency hazard.

**Recommendation:** Move `seen_content_hashes` to be a local dict inside `process_payload` (method-local scope) and pass
it as a parameter to all sub-methods. This eliminates shared mutable state entirely and is thread-safe.

---

### I-2 — `_deduplicate_anthropic_tool_outputs` uses shallow copy for nested content

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py` (lines ~93–115)

```python
item = dict(item)  # shallow copy only
item["content"] = "[Omitted: ...]"
```

**Severity:** 🟡 Important

**Rationale:** The `dict(item)` creates only a _shallow_ copy. If `content` is a nested list of blocks (valid per
Anthropic spec — tool_result content can be a list), the shallow copy does not protect nested structure. The strategy is
inconsistent: the entry-level deep copy (`json.loads(json.dumps(payload))`) is correct, but internal shallow copies
undermine that protection for nested data.

**Recommendation:** Either rely entirely on the top-level deep copy and mutate directly (since `process_payload` already
deep-copies the payload), or use `copy.deepcopy(item)` for consistency. Add a comment explaining the mutation approach.

---

### I-3 — Magic number `6` in `_summarize_anthropic_history` and `_clean_openai`

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py`

```python
target_idx = len(messages) - 6  # unexplained magic number
```

**Severity:** 🟡 Important

**Rationale:** The constant `6` controls how many trailing turns are kept verbatim before summarizing. It has no named
constant, no docstring explanation, and no relationship to the configurable `max_turns` parameter. A future maintainer
cannot reason about why exactly 6 turns are preserved, or whether this should scale with `max_turns`.

**Recommendation:** Extract to a named `__init__` parameter (e.g., `keep_recent_turns: int = 6`) with documentation:

```python
def __init__(self, ..., keep_recent_turns: int = 6):
    self.keep_recent_turns = keep_recent_turns
```

---

### I-4 — `_clean_openai` and `_clean_gemini` mutate `msg`/`part` dicts directly

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py` (lines ~230–240, ~270–280)

**Severity:** 🟡 Important

**Rationale:** Unlike the Anthropic path which uses `item = dict(item)`, the OpenAI and Gemini paths directly mutate the
`msg` and `part` objects from the deep-copied payload. While technically safe (the deep copy is done at entry), this is
inconsistent with the Anthropic approach and creates confusing maintenance patterns. The mutation strategy should be
explicit and uniform.

**Recommendation:** Document the mutation strategy clearly or standardize across all three provider paths.

---

### I-5 — Plan markdown uses `JSONContextCleaner` but implementation uses `ContextCleaner`

**File:** `plans/P-1787928877-antigravity-agent-gemini-3.5-flash.md`

**Severity:** 🟡 Important

**Rationale:** The plan document consistently refers to `JSONContextCleaner` (Steps 1–3 of the plan), while the
implementation uses `ContextCleaner`. This naming discrepancy between plan artifacts and implementation reduces
traceability — reviewers and future agents cannot directly map plan references to implemented code.

**Recommendation:** Either update the plan document to reflect the final implementation name (`ContextCleaner`), or if
the rename was intentional, add a note in the execution record explaining the rename decision.

---

## 🔵 Nit / Minor Issues

### N-1 — Extra blank line before `_merge_consecutive_roles` (PEP 8)

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py`

Three blank lines between methods instead of the PEP 8 standard of two for methods within a class body.

---

### N-2 — `mitm_addon.py` not documented as standalone entrypoint in `__init__.py`

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/__init__.py`

`mitm_addon.py` is not exported from the package. This is correct (it's a mitmproxy script, not a library), but a
comment in `__init__.py` or the module docstring would clarify why it is excluded from `__all__`.

---

### N-3 — `_clean_gemini` has no history summarization (asymmetric with Anthropic/OpenAI)

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/payload_cleaner.py`

The Gemini path only deduplicates but does not apply `max_turns` history summarization. If intentional (Gemini handles
context limits differently), document with a comment.

---

### N-4 — `detect_provider` URL heuristics may produce false positives

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/mitm_addon.py` (lines 25–33)

Checks like `"v1/messages" in url_lower` and `"chat/completions" in url_lower` may match non-LLM endpoints. Consider
more specific URL anchoring or a config-based mapping.

---

### N-5 — `MitmproxyAddon.request` silently swallows all exceptions

**File:** `apps/sandbox-executor/src/sandbox_executor/token_reduction/mitm_addon.py` (lines 64–70)

```python
except Exception as e:
    logger.warning("Mitmproxy request intercept error: %s", e)
```

This is intentional (fail-open for proxy resilience) but the severity level of the log should at least be `ERROR` for
unexpected exceptions. Silently continuing with a `WARNING` could mask bugs in production.

---

## ✅ Positive Observations

- **Deep copy at entry**: `json.loads(json.dumps(payload))` correctly prevents mutation of the caller's original
  payload.
- **Provider bypass**: Unknown providers are gracefully bypassed with `logger.warning`.
- **Cache breakpoint injection**: Correctly limits injection to system, tools, and `messages[-2]`, staying within
  Anthropic's 4-breakpoint maximum.
- **`_merge_consecutive_roles`**: Handles string-to-block content promotion to prevent invalid consecutive-role payloads
  after summarization.
- **Type annotations**: Comprehensive `dict[str, Any]`, `list[dict[str, Any]]` throughout.
- **Public method docstrings**: All public methods include Args/Returns documentation.
- **Ledger entries**: All three ledger files (`executions.jsonl`, `intents.jsonl`, `plans.jsonl`) correctly updated.
- **`__init__.py`**: Correctly exports `ContextCleaner` in `__all__`.

---

## 📊 Summary

| Severity     | Count |
| ------------ | ----- |
| 🔴 Critical  | 2     |
| 🟡 Important | 5     |
| 🔵 Nit       | 5     |

---

## 🏁 Verdict: `CHANGES_REQUESTED`

Two critical blockers must be resolved before merge:

1. **C-1**: Remove the hardcoded `/tmp/src` absolute path from `mitm_addon.py` — violates `.agents/rules.md` path rules
   and makes the module non-portable.
2. **C-2**: Add the missing test file `apps/sandbox-executor/tests/test_context_cleaner.py` — explicitly promised in the
   plan's success criteria and required by project testing invariants.

The core implementation logic in `payload_cleaner.py` is sound and well-structured. The Important issues (thread-safety,
magic numbers, naming inconsistency) should be addressed in the same iteration as the critical fixes.

> **CI Check:** Deferred — Critical and Important issues were found. CI status not checked per conditional policy.
