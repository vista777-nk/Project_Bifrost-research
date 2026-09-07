---
name: multisim-reader
description: Create and edit supported native Multisim circuits, inspect saved designs, export connectivity, and run simulations through Bifrost. Use for Multisim or .ms14 circuit design, editing, analysis, and simulation requests.
---

# Multisim Native Circuits

Use Bifrost's MCP tools. Do not replace unavailable tools with GUI automation,
hand-edit compressed `.ms14` files, or claim that a simulation succeeded without returned
numeric output data.

## Start

1. Call `list_adapters(filter="multisim")`. Availability means that the required
   files and 32-bit COM registration exist; it does not verify the license.
2. Call `run_action(app="multisim", action_name="probe")` to verify connection,
   software version, and the 32-bit worker. Stop and report any error.
3. Use an absolute path to an existing, saved Multisim design. The adapter works
   on temporary copies; relative external model files are not copied automatically.

The MCP server remains 64-bit. The adapter uses Windows' existing 32-bit
PowerShell COM host. A separate 32-bit Python installation is not required.
Never disable PowerShell or Codex security policy to force an operation through.

## Actions

All actions use `run_action(app="multisim", action_name=..., parameters=...)`.

| Action | Parameters | Result |
|---|---|---|
| `probe` | None | Connection, version, worker bitness |
| `read_circuit` | `file_path` | Circuit name, component references, output names |
| `list_components` | `file_path` | Component and output enumeration |
| `export_netlist` | `file_path`, `output_file`, optional `format`: `text` or `csv` | Connectivity report artifact |
| `run_simulation` | `file_path`, optional analysis settings below | Simulation action ID and available output names |
| `get_output_data` | `simulation_action_id`, `output_name` | Numeric samples and interpolation metadata |

## Native Authoring

The native writer supports Multisim 14.3/schema 67 and the locally initialized
R, C, L, VDC catalog. It creates real symbols, ports, wires, ground, and voltage
probes without controlling desktop input. `find_components` with optional `query`
returns the installed authoring catalog; a missing local pack is an explicit error.

- `create_schematic`: `output_file` ending in `.ms14`, and `circuit`.
- `inspect_schematic`: `input_file`; returns `circuit` and `input_sha256`.
- `edit_schematic`: `input_file`, distinct `output_file`, the latest
  `expected_input_sha256`, and a `changes` array.

`circuit.components` contains up to 128 objects with `reference`, `kind`
(`R`, `C`, `L`, `VDC`), numeric SI `value`, optional `x_mm`/`y_mm`, `rotation`
(0/90/180/270), and `pins` mapping `"1"`/`"2"` to net names or null. Net `"0"`
is ground. Coordinates are snapped to the native grid and returned in results.
References and net names use ASCII identifiers. New circuit titles must be ASCII.

Edits: `set_value` takes `reference,value`; `remove` takes `reference`;
`replace` takes `reference,kind,value`; `move` takes `reference,x_mm,y_mm`;
`rotate` takes `reference,rotation`; `connect` takes `reference,pin,net`;
`disconnect` takes `reference,pin`; `add` takes a complete `component` object.
Every edit object includes its `op`. A replace keeps the reference and wiring.

Use `preview_action` when reviewing a batch: it validates parameters and shows
before/after circuits, but native validation is still pending. Successful writes
include native reopening, component/value/connectivity evidence, and checksums.
Call `validate_result` on the published artifact. For electrical verification,
run the requested simulation and retrieve its numeric data separately.

Full topology edits currently require a Bifrost-authored, single-sheet file.
Supported imported designs accept value edits while preserving their native
objects. Saving through Multisim itself may remove the authoring marker, after
which topology edits are rejected. Unsupported components, hierarchy, or
instruments must be reported; do not substitute another component family.
This is a bounded authoring catalog, not the full Multisim component database.

`export_netlist` exports NI's connectivity report, **not an executable SPICE
deck**. Use a separate `.txt` or `.csv` destination. `output_file` is required;
never supply an original circuit as the output destination.

## Simulation

Always pass `file_path`; a preceding read does not establish a persistent open
circuit for later operations. Enumerate output names before selecting them.
Use exact names such as `V(BPout)`, not guessed node or component identifiers.

- `analysis_type`: `dc` (default), `ac`, or `transient`.
- `output_names`: up to 16 names from `read_circuit`. Omitted or empty selects
  the available voltage outputs, provided there are between 1 and 16.
- `sample_count`: 2 to 10000, default 128. For AC logarithmic sweeps this is
  density per decade or octave, with an additional total-point limit.
- Transient: `stop_time` in seconds, from `1e-9` to `60`, default `0.01`.
- AC: `start_frequency` and `stop_frequency` in Hz, from `0.001` to `1e9`,
  with stop greater than start; defaults are 1 and 1000.
- AC: `sweep_type` is `linear` (default), `decade`, or `octave`.

After a successful simulation, use its returned `action_id` as
`simulation_action_id` when retrieving each output. Results are held for the
last 16 successful simulations in that MCP process and are lost on restart.
Do not assume the latest simulation belongs to the current task.

Keep NI's returned sample/matrix structure and interpolation information.
Transient outputs also include `sample_rate_hz`. Do not invent units, axes,
waveform values, or convergence results that were not returned.

## Safety and Verification

- Original designs are never saved or modified by these actions. Authoring
  publishes a distinct native revision only after verification.
- Existing report destinations trigger `confirmation_required`, including in
  force mode. Use existing explicit user authorization when it covers that
  overwrite; otherwise obtain it before `confirm_action`. Cancellation leaves
  the file unchanged. A source hash mismatch requires fresh inspection.
- Validate exported reports with `validate_result(action_id=...)`; validation
  checks nonempty files and their recorded checksum.
- Use `collect_logs` for failures. A timeout is not automatically retried;
  inspect Multisim before retrying because the worker's state may be uncertain.
- On `ERR_MULTISIM_COM`, include the reported stage and error message. Do not
  treat missing probes, empty samples, or failed analyses as successful runs.
