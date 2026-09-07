# Project Handoff

Last inspected: 2026-09-07.

## Purpose and Structure

Bifrost bridges AI agents and industrial software through structured actions,
adapters, validation, and relay interfaces. It is a Python monorepo:

- `core/`: domain models, errors, action execution, validators, and workflows.
- `adapters/`: mock and KiCad implementations, plus a partial Multisim adapter.
- `codex-relay/`: MCP server, six tools, input schemas, and agent skills.
- `hermes-relay/`: tool definitions and prompts; execution remains scaffolded.
- `tests/`: core, mock, KiCad, MCP, and smoke tests.

Use [the Phase 1 execution plan](decisions/Phase-1-execution-order.md) for the
intended sequence and collaboration rules: one task at a time, tests first,
code plus tests plus a changelog entry, and a full regression run afterward.

## Inherited Working Tree

At takeover, branch `dev` and the local `origin/dev` tracking reference both
pointed to `e5b6f42`. No remote fetch was performed. There were 10 modified tracked
files and 6 untracked files. The initial takeover preserved that work without
committing, resetting, or reverting it.

The recovered work includes the MCP server and tools, confirmation and result
storage, action risk fields, KiCad filesystem-only actions and artifact
collection, CI adjustments, and documentation. At takeover, the execution plan
marked Step 4 complete, but the implementation remained uncommitted. The user
subsequently authorized committing the recovered work with its tests and fixes.

## Verification Baseline

Commands were run from the repository root with `python` resolving to
`E:\anaconda3\python.exe` (Python 3.13.5, pytest 8.3.4).

- Before the takeover fix: `python -m pytest tests/ -q -m 'not hardware'`
  passed all 119 tests.
- After the fix and final import cleanup: `python -m pytest tests/ -q` passed
  all 129 tests.
- Focused Ruff checks passed for `codex-relay/codex_plugin/mcp/tools.py` and
  `tests/test_mcp_tools.py`.
- Inherited `python -m ruff check . --output-format concise`: 78 findings,
  mostly in the Hermes scaffolding, older adapter code, and older tests.
- Inherited `python -m mypy core/`: 13 errors in 5 files, primarily missing
  generic parameters and return annotations.
- A subsequent attempt to expand the lint recheck was blocked by an approval
  service concurrency error. The full lint and mypy results above are the
  initial takeover baseline, not newly completed pre-commit checks.
- `.venv\Scripts\python.exe -m pytest` cannot run: pytest is not installed in
  that environment. The successful runs used the system interpreter above.
- `kicad-cli` was not found on PATH. Real KiCad export and Multisim COM
  operations were not verified. Python 3.11/3.12 and Linux were not tested here.
- The MCP SDK test checks in-process tool registration and a `list_adapters`
  call. It does not establish a complete stdio client/server workflow.

## Takeover Fix

The MCP risk calculation elevated dangerous action names only when a caller
requested `low` risk. Requesting `medium` allowed a firmware action to execute
without confirmation, including in force mode.

Added ten mock-only regression cases. Two failed before the fix, demonstrating
adapter execution without confirmation. Recognized dangerous actions now have
a minimum risk of `high`, while `critical` requests remain critical. Tests cover
normal and force modes, no execution before confirmation, execution after
confirmation, and unchanged low/medium behavior for nondangerous actions.

Changed files: `codex-relay/codex_plugin/mcp/tools.py`,
`tests/test_mcp_tools.py`, and `CHANGELOG.md`. This is a narrow correction, not a
complete security audit; risk detection still relies on action-name keywords.

## Remaining Work

1. Finish Phase 1 Step 5: `examples/` contains only `.gitkeep`; add the planned
   minimal KiCad export example and verify it with an actual KiCad installation.
2. Resolve the recorded lint and core type-check failures in focused changes,
   and establish a reproducible development environment.
3. Verify the MCP stdio workflow separately from the in-process SDK test.
4. Complete or explicitly disable the Multisim placeholder operations before
   relying on them: several currently report success without performing the
   described COM operation. They are not production-ready.

Preserve inherited edits when continuing. Do not infer hardware readiness or
full Phase 1 completion from the passing mock/unit suite.
