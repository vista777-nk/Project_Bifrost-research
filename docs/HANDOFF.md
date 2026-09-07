# Project Handoff

Last inspected: 2026-09-08.

## Product Scope Correction

The user clarified that the original requirement is to **design and edit
circuits in both KiCad and Multisim**, not only inspect/export/simulate existing
files. The current plugin is integration infrastructure and does not yet meet
that requirement. Authoring is now an explicit product acceptance gate in
[TDR-002](decisions/TDR-002-circuit-authoring-scope.md).

Prioritize native authoring feasibility and persisted editing, particularly the
Multisim component-placement/wiring gap. Keep the original design-versus-API
distinction explicit: exposed RLC setters, replacement, and SaveAs are not proof
of arbitrary circuit creation; KiCad PCB editing is not schematic editing.
No authoring runtime operations were added in this scope correction.

## Multisim Implementation Update

The user redirected work to Multisim before real KiCad testing. The actual
32-bit Windows PowerShell host now connects successfully to Multisim 14.3.
The adapter uses an isolated JSON-in/JSON-out worker with the registered
`MultisimInterface.MultisimApp` COM class; no second Python installation or
execution-policy change is needed.

Implemented: probe, circuit/component inspection, text/CSV connectivity reports,
DC/AC/transient simulation, and sample retrieval by simulation action ID.
File-based operations use temporary copies; report writes are explicit and
protected by confirmation plus an exclusive-create check for overwrite races.
The relay now marks `Action.confirmation_granted` only after `confirm_action`.
This field is not an exposed run-action parameter.

Live MCP tests use NI's installed Using Analyses example and verify the source
hash is unchanged. COM signatures/constants came from the installed type
library. DC/AC calls require typed string arrays; transient sampling is
configured to fill its requested buffer before the simulation stop time.
Verification: 8 live MCP tests passed; the non-hardware suite passed 164 tests
with 1 skip and 91% Multisim Python adapter coverage. The wheel includes
`adapters/multisim/worker.ps1`.

After the network interruption, the refreshed plugin's own MCP tools were
verified in the active Codex session: availability, probe (Multisim 14.3,
32-bit worker), enumeration of 18 components, DC analysis, and numeric output
retrieval for `V(BPout)` all succeeded. The installed plugin version is
`0.1.0+codex.20260907155231` in the personal marketplace.

See [Multisim Setup](MULTISIM_SETUP.md) for the exact scope, limits, and opt-in
live test command. Reports are connectivity reports, not SPICE decks. Samples
are cached for 16 simulation IDs and disappear on MCP restart. Relative external
model files are not copied automatically. No KiCad integration tests were
performed as part of this Multisim-focused work.

The older activation and takeover sections below are historical context.

## Codex Activation Update

The user prioritized a working Codex CLI plugin for the installed KiCad and
Multisim programs. Plugin packaging and the real MCP connection are now verified:

- Codex CLI: 0.153.4; plugin: `codex-relay@personal`.
- Personal marketplace: `C:\Users\linux\.agents\plugins\marketplace.json`.
- Local plugin source: `C:\Users\linux\plugins\codex-relay`.
- Runtime: repository-local `.venv-codex`, Python 3.11.5 based on KiCad's bundled
  interpreter, with both `bifrost` and `bifrost-codex` installed editable.
- KiCad CLI: `E:\KiCad\8.0\bin\kicad-cli.exe`, verified version 8.0.9.
- Both automatic MCP negotiation and legacy stdio handshake tests passed.
- The exact generated plugin configuration passed stdio smoke testing from a
  temporary working directory, without relying on the repository cwd.
- A fresh `codex exec` session discovered and called `bifrost-codex.list_adapters`
  successfully with reviewed approval. The first read-only invocation was
  blocked by its non-interactive `never` approval policy; no persistent approval
  settings were changed.
- Full tests at this milestone: 134 passed, 1 skipped because KiCad is now
  installed in the test runtime. This supersedes the old 129-test baseline below.

The repository now uses `.codex-plugin/plugin.json`; the portable source
manifest is rendered into a machine-local plugin by `codex_plugin.local_setup`.
Only the three implemented skills are copied. The generated plugin passed the
plugin-creator validator. The old root-level manifest and obsolete install
command were removed. The MCP server requires properly installed packages.

Multisim's actual registered ProgID is `MultisimInterface.MultisimApp` and its
32-bit in-process server is
`C:\Program Files (x86)\National Instruments\Circuit Design Suite 14.3\MSInterface.dll`.
The installed type library exposes `Connect`, `OpenFile`, `EnumComponents`,
`ReportNetlist`, `RunSimulation`, `DoACSweep`, `DoDCOperatingPoint`, and
`GetOutputData`. Metadata inspection does not establish successful execution.
The attempted COM connection actually ran in 64-bit PowerShell despite the
requested shell path. Its class-registration failure is therefore inconclusive;
the corrected 32-bit-host probe was blocked by the approval service's concurrency
error and requires user authorization to retry. No design was opened or changed.

Next: verify real KiCad exports and DRC, then implement the Multisim 32-bit host
and actual operations. The prior baseline and remaining-task details below are
historical context, not a claim that these integrations are complete.

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
