# Holon World Ruleset

This document defines the static coding conventions, runtime constraints, package specifications, and architectural
rules for this repository. All planning and execution agents must consult and obey these rules.

---

## 1. Runtime & Environment Specification

- **Python Runtime:** Strict target version `==3.13.*`.
- **Package Management:** Managed using `uv` workspace commands. No manual modification of virtualenv packages; all
  dependencies must be declared in `pyproject.toml`.
- **Project Layout:** Monorepo/Workspace structure:
  - Root project matches metadata constraints.
  - Sub-packages are isolated under the `apps/` directory (e.g. `apps/sandbox-executor` as a workspace member).
  - Cross-references between members must be declared as local path mappings in `[tool.uv.sources]`.

---

## 2. Coding Conventions & Standards

- **PEP 8 Compliance:** All Python source files must conform to standard style rules (spacing, naming, imports layout).
- **Typing Guidelines:** Use strict static type annotations (`typing` module) for all public functions, classes, and
  method signatures.
- **Docstring Requirements:** Every module, class, and public function must have an explanatory docstring outlining
  inputs, outputs, exceptions, and side-effects.
- **Imports Discipline:**
  - Avoid wildcard imports (`from module import *`).
  - Keep core domain models independent of framework-specific classes (Clean Architecture).

---

## 3. Testing Constraints

- **Testing Tool:** `pytest==9.1.1` as the standard test runner.
- **Test Location:** Unit tests must be placed in a corresponding `tests/` directory matching the source file being
  tested (e.g., `tests/test_planner.py` for `entrypoints/planner.py`).
- **Execution Boundary:** Sandbox executions are not allowed to modify tests or test assertions. Any change to test
  files must be explicitly declared in the planning step.
