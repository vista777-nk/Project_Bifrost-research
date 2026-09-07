# Multisim Codex Integration

This guide covers the currently implemented inspection and analysis tools.
Native circuit creation and editing remain required, unfinished product work;
see [Circuit Authoring Scope](decisions/TDR-002-circuit-authoring-scope.md).

## Runtime

Bifrost's `codex-relay@personal` plugin uses the existing 64-bit Python MCP
server. Multisim 14.3 exposes an apartment-threaded, 32-bit in-process COM DLL,
so the adapter launches a separate **32-bit Windows PowerShell STA worker**.
This avoids installing another Python runtime or loading a 32-bit DLL in a
64-bit process.

The adapter discovers `MultisimInterface.MultisimApp` using the 32-bit registry
view and resolves `MSInterface.dll`, `Multisim.exe`, and the Windows PowerShell
host. On this machine the software lives under:

```text
C:\Program Files (x86)\National Instruments\Circuit Design Suite 14.3
```

`BIFROST_MULTISIM_EXE` optionally overrides the executable location. No registry,
system PATH, PowerShell execution policy, or persistent Codex approval policy
is changed. Local scripts must be permitted by the existing Windows policy.

Registration is checked without launching Multisim. The `probe` action performs
an actual connection and reports the software version and worker bitness.

## Supported Workflow

1. Start a new Codex CLI session after updating the plugin.
2. Ask Codex to use Bifrost to check Multisim availability and run `probe`.
3. Inspect a saved circuit with `read_circuit` or `list_components`.
4. Export a connectivity report or run an analysis on that circuit.
5. Validate report artifacts or retrieve simulation samples by action ID.

Example request:

> Use Bifrost to inspect my saved Multisim circuit, enumerate its outputs, and
> run a DC operating-point analysis. Do not modify the original design.

Each file-based action takes an explicit absolute `file_path`. The adapter
opens a temporary copy and never calls `Save`, `SaveAs`, or component-edit APIs.
Self-contained designs were used for verification. Relative external model
dependencies are not copied automatically and can cause an explicit failure.

### Reports

`export_netlist` requires `file_path` and `output_file`; `format` is `text` or
`csv`. This calls NI's `ReportNetlist` and writes a **connectivity report**, not
a simulator-ready SPICE deck. Destinations must be separate `.txt` or `.csv`
files. Existing files require explicit confirmation, and a file created by
another process during execution is not silently overwritten.

### Simulations

`run_simulation` accepts `dc`, `ac`, and `transient`. It validates probe names,
limits output count and sampling requests, and captures numeric results before
disconnecting. AC supports linear, decade, and octave sweeps. Transient data
includes its sampling rate. Refer to the bundled
[Multisim skill](../codex-relay/skills/multisim-reader/SKILL.md) for parameter limits.

`get_output_data` takes `simulation_action_id` and `output_name`; results are
cached for the last 16 successful simulations in the current MCP process.
They are not durable and do not survive a server restart. Empty or non-finite
samples are failures, not successful simulations.

## Verification

The worker's methods and enum values were checked against the installed
`MSInterface.dll` type library. Unit tests cover source preservation,
confirmation, overwrite races, malformed worker output, invalid arguments,
timeouts, and simulation result retrieval.

Live tests run through an actual MCP stdio client/server connection. They use
NI's installed **Using Analyses** sample, which contains 18 components and
outputs `V(BPout)` and `V(LPout)`. The vendor sample is not copied into this
repository. Each test verifies its original SHA-256 hash remains unchanged.

Verified on the installed Multisim 14.3 environment: 8 live tests passed,
including text/CSV reports, approved overwrites, single-output DC, linear/
decade/octave AC sweeps, and transient samples. The non-hardware suite passed
164 tests with 1 skip; focused Python adapter coverage was 91%.
The refreshed installed plugin was also verified directly in Codex on
2026-09-08 with `probe`, `read_circuit`, `run_simulation`, and `get_output_data`.

Run the non-hardware regression suite:

```powershell
.\.venv-codex\Scripts\python.exe -m pytest tests/ -q -m 'not hardware'
```

Opt into live Multisim tests, which can start the application:

```powershell
$env:BIFROST_MULTISIM_TEST_CIRCUIT = 'C:\Users\Public\Documents\National Instruments\Circuit Design Suite 14.3\samples\LabVIEW Multisim API Toolkit\Using Analyses\Using Analyses.ms14'
.\.venv-codex\Scripts\python.exe -m pytest tests/test_multisim_integration.py -q
```

## Failure Handling

- `ERR_SOFTWARE_NOT_FOUND`: inspect the 32-bit COM registration and executable paths.
- `ERR_MULTISIM_COM`: the response identifies the failing COM stage and native message.
- `ERR_TIMEOUT`: the worker exceeded its deadline; inspect Multisim before retrying.
- `ERR_OUTPUT_NOT_FOUND`: use a successful simulation ID from the same running MCP process.
- `ERR_CONFIRMATION_REQUIRED`: obtain user approval or choose a new report destination.

Simulation timeouts are not automatically retried. The adapter does not stop
arbitrary existing Multisim processes or weaken execution policy to recover.
