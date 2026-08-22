# Plan for I-1787406242-config-driven-executor-prompt-and-metrics

**Plan ID:** P-1787406249-antigravity-agent-gemini-3.5-flash **Parent Intent ID:** NONE **Agent:** antigravity-agent/gemini-3.5-flash **Created At:** 2026-08-22T13:44:09.544Z

## Planner Autonomy Summary

- Intent handling: ACCEPT_AS_IS
- Reframed intent (if applicable): NONE
- Exploration stance: conservative with 1-2 sentence justification.
- Safety priority level: standard
- Priority Justification: The changes modify internal orchestration and metric tracking logic (not system-level resources or security gates), and are fully tested and executed in process-sandbox.

## Exploration

- Proportion of steps that are exploratory: 0.0
- Justification: The task is a straightforward implementation of template loading, metric collection, and unit test expansion with well-defined requirements.

## Overall Plan Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.95                  |
| entropy_pred        | 2.9                   |
| impact_pred         | 60.0                  |
| cost_pred           | 0.5                   |
| learning_value_pred | 2.0                   |
| ev_pred             | 56.63                 |

### Strategy Rationale

The overall strategy focuses on safe, modular enhancement of the `executor.py` script. The success probability is high because the task consists of standard template replacement and git output parsing. The predicted entropy is low (2.9) and easily fits within the 15.0 budget limit. The overall metrics are derived as follows: p_success_pred is determined by the bottleneck step (Step 2, which interacts with the Git CLI); entropy_pred is the sum of all step-level entropies; impact_pred reflects the qualitative value of the combined implementation; cost_pred is the sum of step costs; learning_value_pred is the maximum learning value across steps; ev_pred is calculated from these values using the standard EV formula.

## Safety & Constraint Alignment

- Key world ruleset constraints that affect this plan:
  - Git Flow & Branch Constraints (holon-config/world/constraints.md)
  - Append-Only Ledger (holon-config/world/constraints.md)
  - Testing Constraints (holon-config/world/ruleset.md)
- Potential violations or edge cases:
  - Reading missing template/world files
  - Malformed git diff command or binary file differences
  - Leaving modified files staged on failed executions
- Mitigations built into the plan:
  - Implement defensive existence checks and fallback defaults
  - Robust text-based line parsing with fallback for non-integer diff outputs
  - Explicit 'git reset' rollback on non-success outcomes
- Residual risk accepted (and why): None. The process-sandbox isolation ensures any failures will not propagate.
- Allocated Entropy Budget: 15.0
- Predicted Plan Entropy: 2.9
- Budget Compliance: The strategy fits within budget

## Plan Description & Strategy

This plan implements config-driven executor prompt templating, repository metadata injection, and git diff statistics collection. 
First, we update `executor.py` to walk the repository structure, read the configuration files, load the template and substitute placeholder values. 
Second, we capture all changes made by the executor agent using git diff and record the statistics in `executions.jsonl`.
Third, we provide a default prompt template under `holon-config/prompts/executor.template.md`.
Finally, we implement comprehensive tests covering prompt formatting and diff stats parsing, as well as fixing a flaky docker-related test in `test_executor.py`.

---

## Step 1: Implement Configurable Prompt Templates and Invariant Injection

**Sub‑intent recommendation:** NO **Reasoning:** Simple, low-risk codebase modification with straightforward logic. **Step Type:** IMPLEMENTATION **Exploration level:** EXPLOIT

### Intent & Git Integration

**Step Intent:** Update executor prompt building to load executor.template.md, query the file structure, and read world ruleset/constraints, substituting placeholders before calling the agent CLI. **Git branch:** I-1787406242-config-driven-executor-prompt-and-metrics **Sub‑intent** NONE

### Implementation Details (No code blocks, only logic/steps)

- Define a get_file_structure helper in executor.py that walks the repository directory, ignoring dot files and dot folders (e.g. .git, .venv), up to a max depth of 3, returning a structured list of directories and files.
- Modify executor.py to look for the prompt template at holon-config/prompts/executor.template.md. If the file is not present, fall back to a hardcoded markdown prompt layout.
- Read holon-config/world/ruleset.md and holon-config/world/constraints.md. If these files are not present, default their contents to empty strings.
- Define a dictionary of replacement mapping variables: {plan_branch}, {plan_content}, {intent_json}, {world_ruleset}, {world_constraints}, {file_structure}, {agent}, {model}, {timestamp}, {exec_id}, and {exec_branch}.
- Perform placeholder replacements on the loaded template content to generate the final prompt string.
- Update the prompt writing step to write this computed prompt to the temporary execution prompt file.

### Dependencies & Criticality

**Depends on:** NONE **Is Bottleneck:** YES

### Safety & Constraint Considerations

- Relevant rules: holon-config/world/ruleset.md, docs/safety.md
- Potential failure modes for this step: FileNotFoundError when reading world priors or template files.
- Guardrails and early‑abort checks: Use os.path.exists check before attempting to open any config or world file, falling back to safe defaults.

### Success & Discard Criteria

**Success:** The generated execution prompt correctly contains the file structure and world rules/constraints text. **Discard:** Cost exceeds 1.5x cost_pred or success probability drops below 0.5.

### Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.95                  |
| entropy_pred        | 1.0                   |
| impact_pred         | 30.0                  |
| cost_pred           | 0.15                  |
| learning_value_pred | 1.0                   |
| ev_pred             | 28.55                 |

### Step Metrics Rationale

The implementation uses standard file handling and string replacement. Probability of success is high (0.95). The entropy is low (1.0) because it strictly expands the local CLI builder logic.

---

## Step 2: Collect and Record Git Diff Statistics

**Sub‑intent recommendation:** NO **Reasoning:** Directly integrates into executor.py logging logic. **Step Type:** IMPLEMENTATION **Exploration level:** EXPLOIT

### Intent & Git Integration

**Step Intent:** Measure git changes made by the executor agent during execution and record files modified, lines added, and lines deleted in the execution ledger. **Git branch:** I-1787406242-config-driven-executor-prompt-and-metrics **Sub‑intent** NONE

### Implementation Details (No code blocks, only logic/steps)

- Prior to writing the executions.jsonl ledger entry, run 'git add -A' to stage all current changes (including any new untracked files).
- Run 'git diff --cached --numstat' to get git's count of added lines, deleted lines, and changed files.
- Parse the output of the git diff command line-by-line, splitting on whitespace, extracting added and deleted counts, and converting them to integers (handling non-numeric values like binary file markers gracefully by defaulting to 0).
- If the execution status is not success (e.g. failure), run 'git reset' to unstage the changes, reverting the index back to its original state so that only the execution report and ledger are committed.
- Add a new dictionary 'diff_stats' to the 'exec_entry' ledger dictionary before it is JSON-serialized, containing: 'files_modified', 'lines_added', and 'lines_deleted'.

### Dependencies & Criticality

**Depends on:** Step 1 **Is Bottleneck:** YES

### Safety & Constraint Considerations

- Relevant rules: holon-config/world/constraints.md#3
- Potential failure modes for this step: Git command failure, parsing error on malformed diff statistics, or failing to unstage files on failure.
- Guardrails and early‑abort checks: Use try-except blocks during parsing and ensure git reset is executed in a finally block or under status conditional checks.

### Success & Discard Criteria

**Success:** executions.jsonl contains the diff_stats key with correct values matching the git diff. **Discard:** Git diff returns persistent errors or code fails to execute.

### Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.95                  |
| entropy_pred        | 1.2                   |
| impact_pred         | 40.0                  |
| cost_pred           | 0.15                  |
| learning_value_pred | 2.0                   |
| ev_pred             | 38.49                 |

### Step Metrics Rationale

This step involves Git CLI execution and parsing. Success probability is 0.95 because Git commands are run inside the local repo directory. Learning value is high (2.0) since it provides the core calibration metrics.

---

## Step 3: Define Default Executor Prompt Template

**Sub‑intent recommendation:** NO **Reasoning:** A simple text-only template file addition. **Step Type:** CONFIG **Exploration level:** EXPLOIT

### Intent & Git Integration

**Step Intent:** Create the default executor prompt template under holon-config/prompts/executor.template.md. **Git branch:** I-1787406242-config-driven-executor-prompt-and-metrics **Sub‑intent** NONE

### Implementation Details (No code blocks, only logic/steps)

- Create the directory holon-config/prompts if it does not already exist.
- Write the default template containing explanation text and the placeholders: {plan_branch}, {plan_content}, {intent_json}, {world_ruleset}, {world_constraints}, and {file_structure}.

### Dependencies & Criticality

**Depends on:** NONE **Is Bottleneck:** NO

### Safety & Constraint Considerations

- Relevant rules: None.
- Potential failure modes for this step: None.
- Guardrails and early‑abort checks: None.

### Success & Discard Criteria

**Success:** File holon-config/prompts/executor.template.md is created and populated with valid placeholders. **Discard:** Writing to file fails.

### Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.98                  |
| entropy_pred        | 0.2                   |
| impact_pred         | 15.0                  |
| cost_pred           | 0.05                  |
| learning_value_pred | 0.5                   |
| ev_pred             | 14.84                 |

### Step Metrics Rationale

Extremely simple task. High success probability (0.98), minimal entropy (0.2), and low cost.

---

## Step 4: Expand Unit Tests for New Executor Features

**Sub‑intent recommendation:** NO **Reasoning:** Extends the existing test suite under apps/sandbox-executor/tests. **Step Type:** TEST **Exploration level:** EXPLOIT

### Intent & Git Integration

**Step Intent:** Provide full test coverage for repository walk structure, template parsing, world priors injection, diff statistics gathering, and fix existing docker-related test failures. **Git branch:** I-1787406242-config-driven-executor-prompt-and-metrics **Sub‑intent** NONE

### Implementation Details (No code blocks, only logic/steps)

- Write unit tests for get_file_structure verifying depth limits and ignoring rules.
- Write unit tests verifying that prompt template values are loaded and formatted correctly when both custom template files are present and when falling back to default.
- Write unit tests for diff stats parsing, mocking git commands to return different diff outputs (empty, populated, binary files).
- Write unit tests verifying that executions.jsonl includes the correct diff_stats field.
- Patch os.path.exists in test_main_keep_workspace_existing_git to return False for '/.dockerenv' to ensure the test passes reliably even inside containerized development sandboxes.

### Dependencies & Criticality

**Depends on:** Step 1, Step 2 **Is Bottleneck:** YES

### Safety & Constraint Considerations

- Relevant rules: holon-config/world/ruleset.md#3
- Potential failure modes for this step: Mocking side effects causing test isolation issues.
- Guardrails and early‑abort checks: Use standard unittest.mock patterns and clean up all mocks on tearDown.

### Success & Discard Criteria

**Success:** All test cases in test_executor.py pass successfully under pytest. **Discard:** Unresolvable testing failures.

### Metrics

| metric              | value                 |
| ------------------- | --------------------- |
| p_success_pred      | 0.95                  |
| entropy_pred        | 0.5                   |
| impact_pred         | 25.0                  |
| cost_pred           | 0.15                  |
| learning_value_pred | 1.0                   |
| ev_pred             | 23.95                 |

### Step Metrics Rationale

Straightforward testing logic. High probability of success (0.95), low entropy (0.5), and low cost (0.15).

---
