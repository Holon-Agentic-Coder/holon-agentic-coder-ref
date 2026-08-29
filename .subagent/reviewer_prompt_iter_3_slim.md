# TASK: PR Reviewer Subagent (Iteration 3, Dry-Run, Single-Agent Mode)

You are an isolated PR review subagent with a FRESH context. You are READ-ONLY: the only file you may write is the
report path named at the end. Keep your own context small — read the large inputs once, in chunks if needed, and do not
re-read them repeatedly.

## Inputs (read these from disk)

1. Review rubric / persona registry / output format:
   `/Users/thomashan/git/holon-agentic-coder-ref-metadata/.agents/prompts/pr_review_prompt.md`
2. Current PR diff (head commit `12872d6`):
   `/Users/thomashan/git/holon-agentic-coder-ref-metadata/.subagent/pr48_iter3.diff` (read it with offset/limit in
   ~250-line slices to stay within memory)
3. PR head worktree (verify code in place, run tests):
   `/Users/thomashan/git/holon-agentic-coder-ref-metadata/holon-agentic-coder-ref/I-1787928238-token-reduction-phase1`

## PR context

- PR #48 `feat(sandbox-executor): implement SSL trust and CA mounts (Phase 1)`, repo
  `Holon-Agentic-Coder/holon-agentic-coder-ref`, base `develop`.
- Purpose: Phase 1 of token reduction — host Root CA generation, `--token-reduce` CLI flag, CA mount + proxy env
  injection into the sandbox container, plus an opt-in external-proxy attach path.
- Iterations 1 and 2 review findings are ALREADY FIXED (commits `6e25912`, `12872d6`). Do NOT re-report fixed issues. Do
  NOT assume something is fixed because a commit message says so — verify in the code.

## User constraints ledger — never recommend these

- No deprecation fallback stubs, CLI error shims, migration notices, or deprecation release notes anywhere.
- No static fallback version dictionaries; rely on dynamic CLI checks with `returncode == 0` and explicit
  `subprocess.TimeoutExpired` handling.
- Always empirically verify syntax/import/test assertions by EXECUTING before reporting them; never confuse unified-diff
  context lines with deleted lines.

## Declared out of scope — do NOT flag as defects

- Shipping `mitm_addon.py` / making `--token-reduce` actually functional (Phase 2). The flag is documented as
  experimental and fails preflight loudly.
- Digest-pinning `mitmproxy/mitmproxy:12.2.3`.
- Harness-generated artifacts: `plans/*.md`, `executions/*.md`, `holon-knowledge/ledger/*.jsonl`.

## Rules

1. Perform the review yourself in THIS single pass. Do NOT spawn subagents.
2. Ground every finding in the actual code. Empirically verify claims about syntax, imports, missing files, crypto
   artifacts, or test results by executing them:
   - `PYTHONPATH=apps/sandbox-executor/src uv run pytest apps/sandbox-executor/tests -q`
   - `uv run ruff check .`
   - `python3 -c ...`, `openssl x509 ...`, `bash -n ...` Mark anything you could not verify as UNVERIFIED.
3. Severity discipline: 🔴 CRITICAL is reserved for breakage, security exploits, data loss, or total-outage behaviour.
   If the only remaining items are documentation polish, style, or optional suggestions, the verdict MUST be `APPROVED`
   or `COMMENT`, never `CHANGES_REQUESTED`.
4. DRY-RUN: no `gh pr review`, no GitHub posting, no commits, no pushes, no source edits.
5. Categorise positive confirmations as ✅ APPROVED / PASS (not 🟢 NIT).

## Output (MANDATORY)

Write the full structured report (Dynamic Role Activation Matrix, per-persona reviews, Overall Verdict) to:

`/Users/thomashan/git/holon-agentic-coder-ref-metadata/.subagent/dry_run_review_iter_3_12872d6.md`

Then print to stdout, as your final message, EXACTLY these three lines:

```
VERDICT: <APPROVED | CHANGES_REQUESTED | COMMENT>
COUNTS: CRITICAL=<n> IMPORTANT=<n> NIT=<n>
REPORT: /Users/thomashan/git/holon-agentic-coder-ref-metadata/.subagent/dry_run_review_iter_3_12872d6.md
```
