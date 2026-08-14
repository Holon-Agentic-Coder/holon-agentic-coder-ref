# PR Review — Dry Run (iter 1 · `1104b16`)

**PR**:
[#28 — feat(sandbox-executor): align executor with planner patterns](https://github.com/Holon-Agentic-Coder/holon-agentic-coder-ref/pull/28)
**Branch**: `feat/0011-implement-executor` **Mode**: Dry-Run (`--dry-run`) · Single-Agent Pass **Reviewed at**:
2026-08-14T22:54:00+10:00

---

## 📊 PR Metadata & Role Activation

### PR Description Summary

- Truncate long arguments in `run_cmd` print message to prevent log flooding.
- Standardise `repo_dir` setup to default to `~/.holon-sandbox/workspace` (in sandbox) or `~/.holon/repo` (locally) and
  clean it if exists.
- Support workspace reuse and warm caching (via `git fetch`/`checkout`) when `HOLON_KEEP_WORKSPACE=1` is enabled.
- Stage all changes (`git add -A`) on successful execution to capture code modifications.

### Files Changed

| File                                                                | Type                                              |
| ------------------------------------------------------------------- | ------------------------------------------------- |
| `apps/sandbox-executor/src/sandbox_executor/entrypoint/executor.py` | Python — core executor logic (~280 net new lines) |
| `apps/sandbox-executor/tests/test_executor.py`                      | Python — tests (~400 net new lines)               |
| `apps/sandbox-executor/uv.lock`                                     | Lock file (deleted)                               |
| `docs/architecture.md`                                              | Markdown — formatting fix                         |
| `docs/faq.md`                                                       | Markdown — formatting fix                         |
| `docs/safety.md`                                                    | Markdown — formatting fix                         |
| `docs/wisdombase_schema.md`                                         | Markdown — formatting fix                         |

### Dynamic Role Activation Matrix

| Persona                            | Status | Primary Trigger                                                          |
| :--------------------------------- | :----- | :----------------------------------------------------------------------- |
| **Engineering & Architecture**     |        |                                                                          |
| Principal Engineer                 | 🟢     | `executor.py` — complex control flow, safety checks, workspace lifecycle |
| Solution Architect                 | 🟢     | Sandbox detection heuristics, workspace reuse strategy                   |
| Frontend Engineer                  | ⚪     | No frontend files changed                                                |
| QA & Test Engineer                 | 🟢     | `test_executor.py` — large new test suite                                |
| ML & Data Specialist               | ⚪     | No ML files changed                                                      |
| **Product, Design, & Growth**      |        |                                                                          |
| Product Owner                      | ⚪     | Internal infrastructure; no user-facing product changes                  |
| UX/UI Designer                     | ⚪     | No UI files changed                                                      |
| SEO & Growth Specialist            | ⚪     | No SEO-relevant changes                                                  |
| **Operations, Release, & Support** |        |                                                                          |
| DevOps & SRE                       | 🟢     | Workspace lifecycle, cleanup strategies, `uv.lock` deletion              |
| Release Manager                    | ⚪     | No migrations or release-gating changes                                  |
| Support Engineer                   | ⚪     | No customer-facing error surface changes                                 |
| **Security, Compliance, & Risk**   |        |                                                                          |
| Security Architect                 | 🟢     | Path safety (`FORBIDDEN_ROOTS`, `ALLOWED_PARENTS`), secret redaction     |
| Compliance Auditor                 | ⚪     | No regulatory or licence changes                                         |
| Localization Coordinator           | ⚪     | No string localisation changes                                           |
| **DevRel & Documentation**         |        |                                                                          |
| Technical Writer                   | 🟢     | Markdown formatting corrections in `docs/`                               |
| Developer Advocate                 | ⚪     | No SDK/API surface changes                                               |

---

## 🔍 Persona Reviews

---

### 👥 Principal Engineer / Tech Lead Review

#### ✅ `executor.py` — Comprehensive secret redaction infrastructure

- **Context**: `redact_text`, `redact_args`, and `_is_secret_flag` provide layered, defense-in-depth redaction covering
  URL credentials, query parameters, JSON key-value patterns, and CLI flags. The truncation guard
  (`_MAX_REDACT_INPUT_LEN`) prevents ReDoS on pathological inputs. The design decision to pre-compute
  `ALLOWED_PARENT_RESOLVED` / `ALLOWED_EXACT_RESOLVED` at module load to freeze the safelist before any test mocks is
  excellent.
- **Verdict**: ✅ APPROVED / PASS

#### ✅ `executor.py` — Conditional `git add -A` only on success

- **Context**: Staging all changes (`git add -A`) is guarded behind `exec_status == "success"`, preventing a failed
  agent run from staging partial/broken files. The `git diff --cached --quiet` guard before commit is also correct.
- **Verdict**: ✅ APPROVED / PASS

#### ✅ `executor.py` — `_cleanup_repo_dir` handles all filesystem shapes

- **Context**: Mount points, symlinks, regular directories, and regular files are all handled via distinct branches.
  `_clear_dir_contents` is correctly restricted to directory paths.
- **Verdict**: ✅ APPROVED / PASS

#### 🟡 `executor.py` lines 408–413 — `git clean -fd` skipped for non-sandbox `HOLON_KEEP_WORKSPACE` reuse

- **Context**: When `HOLON_KEEP_WORKSPACE=1` is set and the existing `.git` dir is reused, `git clean -fd` is only
  executed when `in_sandbox` is true OR when `repo_dir` equals the literal sandbox default path. In a local workspace
  (developer laptop), uncommitted/untracked files from the previous run are NOT cleaned before `git checkout -f -B`,
  which could silently contaminate the run.

```python
# executor.py ~line 408
if in_sandbox or repo_dir == os.path.expanduser("~/.holon-sandbox/workspace"):
    run_cmd(["git", "clean", "-fd"], cwd=repo_dir)
else:
    print(
        f"Warning: Skipping 'git clean -fd' as we are in a local workspace at {repo_dir}.", file=sys.stderr
    )
```

- **Recommendation**: This is a deliberate product trade-off (preserving local developer files), but the warning should
  be surfaced prominently and documented in the `HOLON_KEEP_WORKSPACE` env var comments. If not intentional, consider
  always running `git clean -fd` when `HOLON_KEEP_WORKSPACE=1` since the intent is "fetch & update", not "preserve local
  state".
- **Severity**: 🟡 IMPORTANT / IMPROVEMENT

#### 🟢 `executor.py` lines 354–358 — Inline multi-line equality comparisons reduce readability

- **Context**: Sandbox heuristic detection uses multi-line equality comparisons with a comment embedded in the middle of
  the expression, which is hard to scan.

- **Recommendation**: Extract the comment above the block:

```python
# Heuristic fallback: sandbox containers without HOLON_ROLE or /.dockerenv
# Use HOLON_REPO_DIR to override in ambiguous environments (Linux/macOS/Windows).
in_sandbox_heuristic = os.getenv("USER") == "holon" or os.getenv("USERNAME") == "holon"
```

- **Severity**: 🟢 NIT / OPTIONAL

---

### 👥 Solution Architect Review

#### ✅ Sandbox detection layering — explicit > heuristic with clear warning

- **Context**: The three-tier detection (`HOLON_IN_SANDBOX` → `HOLON_ROLE` → `/.dockerenv` → username heuristic) is
  well-reasoned. Printing a warning when the heuristic fires without explicit confirmation is a good practice.
- **Verdict**: ✅ APPROVED / PASS

#### 🟡 `executor.py` lines 393–414 — `.git` directory presence check is fragile for workspace reuse validation

- **Context**: The decision to reuse vs. clone is based solely on `os.path.exists(os.path.join(repo_dir, ".git"))`. This
  check does not verify:
  1. Whether the `.git` dir belongs to the correct remote (`repo_url`).
  2. Whether the repo is in a sane state (e.g., not mid-merge or mid-rebase).

  A stale `.git` from a different repository will silently trigger the reuse path (`git fetch <new_url> <branch>`)
  instead of a clean clone, potentially causing confusing failures.

- **Recommendation**: Add a `git remote get-url origin` check and compare against `repo_url` before deciding to reuse:

```python
remote_result = run_cmd(["git", "remote", "get-url", "origin"], cwd=repo_dir, check=False)
if remote_result.returncode != 0 or remote_result.stdout.strip() != repo_url:
    # Remote mismatch — clean up and re-clone
    _cleanup_repo_dir(repo_dir, raise_on_error=True)
    os.makedirs(repo_dir, exist_ok=True)
    run_cmd(["git", "clone", "--branch", plan_branch, "--single-branch", "--depth", "1", repo_url, "."], cwd=repo_dir)
else:
    run_cmd(["git", "fetch", repo_url, plan_branch], cwd=repo_dir)
    ...
```

- **Severity**: 🟡 IMPORTANT / IMPROVEMENT

---

### 👥 QA & Test Engineer Review

#### ✅ New test suite — comprehensive coverage of redaction and safety checks

- **Context**: The new tests cover `redact_args`, `redact_text` (including oversized input), `_check_forbidden_root`
  (allowed/blocked paths, symlinks), `_clear_dir_contents` (permission errors, symlinks), `_handle_remove_readonly`,
  `_cleanup_repo_dir`, mount points, keep-workspace flows, git-add-on-failure guards. The test volume is substantial and
  well-structured.
- **Verdict**: ✅ APPROVED / PASS

#### ✅ `test_redact_args` — known limitation documented with explicit test case

- **Context**: The "chained flags" known limitation is explicitly tested and commented, communicating intent clearly to
  future maintainers.
- **Verdict**: ✅ APPROVED / PASS

#### 🟡 `test_executor.py` lines 727–730 — `test_main_default_workspace_deleted` version-guards a test assertion that patches `shutil.rmtree` directly

- **Context**: The test patches `shutil.rmtree` rather than `executor._rmtree`, which bypasses
  `_handle_remove_readonly`. If `_rmtree` is ever refactored, the mock will silently stop covering the real
  implementation.

```python
if sys.version_info >= (3, 12):  # noqa: UP036
    mock_rmtree.assert_any_call(default_dir, onexc=executor._handle_remove_readonly)
else:
    mock_rmtree.assert_any_call(default_dir, onerror=executor._handle_remove_readonly)
```

- **Recommendation**: Patch `executor._rmtree` directly (or use an integration-style temp dir) to decouple the test from
  the Python version shim and from internal `shutil.rmtree` dispatch.
- **Severity**: 🟡 IMPORTANT / IMPROVEMENT

#### 🟢 `test_executor.py` ~line 885 — `test_clear_dir_contents_raise_on_error` patches `os.unlink` at global scope

- **Context**: The test patches `"os.unlink"` (global) rather than `"sandbox_executor.entrypoint.executor.os.unlink"`
  (module-local), which could affect other modules in the same process.

- **Recommendation**:

```python
with patch("sandbox_executor.entrypoint.executor.os.unlink", side_effect=PermissionError("Permission denied")):
```

- **Severity**: 🟢 NIT / OPTIONAL

---

### 👥 DevOps & SRE Review

#### ✅ `uv.lock` deletion — correct for virtual package

- **Context**: The deleted `uv.lock` contained only the virtual `sandbox-executor` package with no third-party
  dependencies. Removing it is correct as such lock files add no reproducibility value.
- **Verdict**: ✅ APPROVED / PASS

#### ✅ Warning messages routed to `stderr`

- **Context**: All warnings are now correctly routed to `sys.stderr`, preserving stdout for structured output and
  adhering to POSIX convention.
- **Verdict**: ✅ APPROVED / PASS

#### 🟢 `executor.py` — No structured logging

- **Context**: All diagnostics are plain `print()` calls. As the executor grows, ad-hoc prints will become harder to
  filter in production log aggregators.
- **Recommendation**: Introduce `import logging` with a module-level logger as a follow-up task.
- **Severity**: 🟢 NIT / OPTIONAL

---

### 👥 Security Architect Review

#### ✅ `FORBIDDEN_ROOTS` + `ALLOWED_PARENTS` + `ALLOWED_EXACT` — Defense-in-depth path safety

- **Context**: Double-resolving paths via both `os.path.abspath` and `os.path.realpath` prevents symlink bypass attacks
  (covered by `test_check_forbidden_root_symlinks`).
- **Verdict**: ✅ APPROVED / PASS

#### ✅ `redact_text` — ReDoS prevention via input truncation

- **Context**: The `_MAX_REDACT_INPUT_LEN` guard with line-boundary-aligned truncation is a thoughtful addition.
- **Verdict**: ✅ APPROVED / PASS

#### ✅ `run_cmd` — Raw stdout/stderr now redacted before printing

- **Context**: The `env` parameter removal and redaction of `CalledProcessError` output before printing are correct
  security improvements.
- **Verdict**: ✅ APPROVED / PASS

#### 🟡 `executor.py` lines 241–270 — `redact_args` known bypass underdocumented at module level

- **Context**: Secret values starting with `-` are intentionally not masked (to avoid masking legitimate flags). This is
  a documented and tested trade-off. However, the limitation is only documented in an inline code comment inside
  `redact_args` — not in a module docstring, README, or SECURITY note.

- **Recommendation**: Document this known limitation in the module docstring (see Technical Writer finding) or in a
  `SECURITY.md` note so future maintainers can make an informed decision when updating the redaction logic.
- **Severity**: 🟡 IMPORTANT / IMPROVEMENT _(documentation gap, low exploitability in practice)_

---

### 👥 Technical Writer Review

#### ✅ Markdown formatting fixes across `docs/`

- **Context**: All four documentation files have their escaped bold Markdown corrected to proper `**...**` syntax,
  overly long lines reflowed cleanly, and the stray leading space in `"DNA"` corrected.
- **Verdict**: ✅ APPROVED / PASS

#### 🟢 `executor.py` — Module-level docstring missing

- **Recommendation**: Add a module docstring documenting the entry point and key environment variables:

```python
"""Sandbox executor entrypoint for Holon Agentic Coder.

Clones or reuses a workspace repository, runs the configured agent, captures
execution results into the ledger, and commits/pushes the execution branch.

Key environment variables:
    HOLON_REPO_DIR: Override the default workspace directory.
    HOLON_KEEP_WORKSPACE: Set to '1' to skip cleanup and reuse the existing workspace.
    HOLON_IN_SANDBOX: Set to '1' to explicitly mark sandbox context.
    HOLON_SKIP_PUSH: Set to '1' to skip the git push step.
    HOLON_ROLE: When set, implies sandbox context.

Known limitations:
    - redact_args: Secret values starting with '-' are not masked to avoid
      over-masking legitimate flags that immediately follow a secret flag.
"""
```

- **Severity**: 🟢 NIT / OPTIONAL

---

## 🏆 Overall Verdict

### Finding Summary

| Severity                   | Count | Items                                                                                                                                                                                                                                                                                                                                                                                              |
| :------------------------- | :---- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🔴 CRITICAL / BLOCKER      | 0     | —                                                                                                                                                                                                                                                                                                                                                                                                  |
| 🟡 IMPORTANT / IMPROVEMENT | 4     | `git clean -fd` skip in local keep-workspace reuse; `.git` remote URL not validated before reuse; `shutil.rmtree` test mock bypasses `_handle_remove_readonly`; `redact_args` bypass underdocumented at module level                                                                                                                                                                               |
| 🟢 NIT / OPTIONAL          | 4     | Inline multi-line equality comments; global `os.unlink` patch scope; missing module docstring; no structured logging                                                                                                                                                                                                                                                                               |
| ✅ APPROVED / PASS         | 11    | Secret redaction infrastructure; conditional `git add -A`; `_cleanup_repo_dir` filesystem handling; sandbox detection layering; `ALLOWED_PARENT_RESOLVED` pre-computation; new test suite coverage; known limitation test documentation; `uv.lock` deletion; stderr routing; path safety symlink protection; ReDoS prevention; `run_cmd` env param removal + output redaction; Markdown formatting |

> **Note**: The user-rejected recommendations (`'Python 3.12 compatibility for shutil.rmtree'`,
> `'Support for Unseparated apikey and secretkey Keynames'`,
> `'Add os.getcwd() to ALLOWED_EXACT or os.path.expanduser(~) to ALLOWED_PARENTS'`) were noted but **excluded from the
> verdict** as per coordination constraints.

### ❌ CHANGES REQUESTED

Four **🟡 IMPORTANT / IMPROVEMENT** findings were identified:

1. **`git clean -fd` skip in local `HOLON_KEEP_WORKSPACE` reuse** (`executor.py` ~line 408): Untracked files from
   previous runs could silently contaminate the local workspace reuse path.

2. **`.git` remote URL not validated before workspace reuse** (`executor.py` ~line 393): A stale `.git` dir from a
   different remote would silently trigger the reuse path rather than a clean clone.

3. **`shutil.rmtree` test mock fragility** (`test_executor.py` ~line 727): `test_main_default_workspace_deleted` patches
   `shutil.rmtree` directly rather than `executor._rmtree`, making it brittle to internal refactoring.

4. **`redact_args` bypass underdocumented** (`executor.py` ~line 251 + module level): The known security limitation
   (secret values starting with `-` are not masked) is only documented inline and should be elevated to
   module/SECURITY-level documentation.

---

## 🗳️ Ensemble Review Breakdown

> **Single-Agent Mode** — Ensemble voting not applicable (3-subagent ensemble disabled by caller instruction).

- **Reviewer 1** (`single-agent-pass`): `CHANGES_REQUESTED`
- **Ensemble Consensus Verdict**: `CHANGES_REQUESTED`

> 🤖 **Reviewed by**: `antigravity-agent` (Single-Agent Pass) · **Model**: `gemini-2.5-pro`
