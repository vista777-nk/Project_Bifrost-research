# Native Circuit Authoring Contract

Status: native divider acceptance passes on KiCad 8.0.9 and Multisim 14.3.
The implementation uses native files, CLI, and COM; no GUI-control backend exists.

## Start Testing

The configured local plugin is `codex-relay@personal`. After its update, open a
new PowerShell session, enter this repository, and run `codex`. A suitable request is:

> Use Bifrost to create a native 5 V divider in both KiCad and Multisim, with
> R1 and R2 each 10 kohms. Use fresh files in output/my-divider. Inspect each
> result, change R2 to 20 kohms in a new revision, then add a 1 uF capacitor
> across R2 and remove it in another revision. Report native checks and the
> Multisim DC output before and after the resistor edit. Do not control the
> mouse or keyboard, and preserve every original revision.

Codex uses structured plugin actions; there is no need to operate the desktop.
The applications may display documents as a consequence of their native APIs.
Opening the returned native files yourself is optional visual inspection.

For a deterministic check without an LLM, use a fresh output directory:

```powershell
.\.venv-codex\Scripts\python.exe scripts/verify_native_authoring.py --config "$HOME\plugins\codex-relay\.mcp.json" --output-dir output/native-acceptance
```

This creates four native revisions per application and a `verification.json`
report through an actual MCP client/server connection. It checks native
reopening, KiCad ERC evidence, Multisim DC near 2.5 V and 3.333333 V, and prior
revision hashes. The input specification is
[voltage-divider.json](../examples/circuits/voltage-divider.json).

## Supported Contract

The initial catalog contains two-pin R, C, L, and VDC components. Values use SI
units, coordinates use millimeters, and rotations are 0/90/180/270 degrees.
Net `0` is ground. Unsupported component families and native schemas must fail
explicitly; this is not permission to replace them with carrier blocks.

Actions through `run_action(app=..., action_name=..., parameters=...)`:

- `find_components`: optional `query`; returns the supported native catalog.
- `inspect_schematic`: `input_file`; returns components, pins/nets, placement,
  and `input_sha256` for optimistic concurrency control.
- `create_schematic`: `output_file`, `circuit` with a `components` array.
- `edit_schematic`: `input_file`, `output_file`, `expected_input_sha256`, and
  `changes`. Operations are `set_value`, `add`, `remove`, `replace`, `move`,
  `rotate`, `connect`, and `disconnect`.

Each component has `reference`, `kind`, numeric `value`, `x_mm`, `y_mm`,
`rotation`, and `pins`, a mapping from `1`/`2` to a net name or null. Omitted
positions get deterministic, separated initial positions. Edits refer to real
component references, never screen coordinates.

All mutation requests are validated before changing files. Source hashes must
match. New revisions are published only after native-format verification;
existing output files require explicit confirmation. Return the native artifact,
checksum, semantic changes, and validation evidence. Keep unsupported and
unrelated native content rather than silently discarding it.

`preview_action` returns validated before/after circuits without publishing a
revision. Native checks are pending until execution. Invalid parameters and
stale source hashes fail before overwrite confirmation. Existing output files
require `confirm_action`; even confirmation cannot overwrite the input file.

Successful KiCad writes include a native netlist comparison and an ERC report
in `metadata.verification`. Check `erc_passed` and the `erc` report: publishing
an editable revision does not imply an electrically valid circuit. Multisim
writes verify actual COM component enumeration, RLC values, and connectivity;
simulation is a separate action returning numeric evidence.

## Current Limits

- Authoring supports KiCad 8/schema 20231120 and Multisim 14.3/schema 67.
- The four component families above are implemented. Op-amps, transistors,
  arbitrary vendor libraries, multi-sheet designs, buses, and PCB placement/
  routing are still outside this authoring release.
- Full topology editing applies to Bifrost-authored single-sheet files.
  Supported imported files accept value edits. Unsupported native content
  causes explicit rejection rather than silent loss.
- Saving through either native application may replace the Bifrost authoring
  marker. Such a saved file is treated as imported for subsequent topology edits.
- Topology edits reroute wires. Value-only edits preserve native wiring and
  existing component records. References persist across same-family edits;
  replacement may use a new native identity.
- Numeric values use SI units, not strings such as `10k`. Rotation is in quarter
  turns; new placement is snapped to the software's native grid. Unchanged
  component positions are preserved during value edits.
- Multisim uses an installation-derived local component/probe pack. It is not
  redistributed. Relative external model files are not copied automatically.

This passes the bounded TDR-002 acceptance case; it does not mean every feature
or component in either application is automated. Broader library and imported
topology support remain project work.
