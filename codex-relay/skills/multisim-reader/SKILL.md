---
name: multisim-reader
description: Inspect saved Multisim circuits, enumerate components and probes, export connectivity reports, and run DC, AC, or transient simulations through Bifrost. Use for Multisim, .ms14 files, circuit analysis, or simulation output requests.
---

# Multisim Circuit Inspection and Simulation

Use Bifrost's MCP tools. Do not replace unavailable tools with GUI automation,
edit binary `.ms14` files, or claim that a simulation succeeded without returned
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

- Original designs are never saved or modified by these actions. Workflows
  requiring component edits, saved design changes, or live GUI interaction are
  outside this implementation.
- Existing report destinations trigger `confirmation_required`, including in
  force mode. Explain the target to the user, wait for explicit approval, and
  then call `confirm_action`; cancellation must leave the file unchanged.
- Validate exported reports with `validate_result(action_id=...)`; validation
  checks nonempty files and their recorded checksum.
- Use `collect_logs` for failures. A timeout is not automatically retried;
  inspect Multisim before retrying because the worker's state may be uncertain.
- On `ERR_MULTISIM_COM`, include the reported stage and error message. Do not
  treat missing probes, empty samples, or failed analyses as successful runs.
