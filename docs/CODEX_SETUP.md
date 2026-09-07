# Local Codex Plugin Setup

The plugin exposes six MCP tools backed by the shared `core/` and `adapters/`
packages. Its Codex plugin identifier is `codex-relay`; the Python distribution
and MCP server remain `bifrost-codex`.

## Windows Runtime

User workflow and tested authoring limits: [Native Circuit Authoring](10-circuit-authoring.md).

Run these commands from the repository root. Substitute your installed KiCad
directory if it differs. A separate environment leaves KiCad and the existing
project `.venv` unchanged. `--system-site-packages` makes KiCad's `pcbnew`
available to the relay.

```powershell
& 'E:\KiCad\8.0\bin\python.exe' -m venv --system-site-packages .venv-codex
.\.venv-codex\Scripts\python.exe -m pip install -e '.[codex,dev,multisim]' -e ./codex-relay
```

The repository's `.codex-plugin/plugin.json` is the portable manifest. The
local packaging command copies that manifest and the three implemented skills,
then generates an MCP configuration with absolute runtime paths. Empty skill
folders for later phases are not distributed. No machine paths are committed
to the portable manifest.

For native Multisim authoring, install Node.js and initialize a fresh local
directory from the licensed Multisim 14.3 sample installation:

```powershell
npm install --prefix .bifrost-authoring/runtime/node --ignore-scripts --strict-ssl=true --no-audit --no-fund --save-exact electronics-workbench-decoder@0.2.0
.\.venv-codex\Scripts\python.exe -m adapters.multisim.setup_authoring --home .bifrost-authoring/runtime
```

The generated component/probe templates stay local and ignored by Git. Setup
refuses to replace an existing pack; use a fresh directory for a rebuild.
This machine's pack is already initialized. Do not rerun initialization for
ordinary testing. No downloaded package install scripts are needed.

## Install

Create the initial personal marketplace entry with Codex's bundled
`plugin-creator` skill. Then prepare its home-relative source directory:

```powershell
.\.venv-codex\Scripts\python.exe -m codex_plugin.local_setup --source ./codex-relay --destination "$HOME\plugins\codex-relay" --kicad-bin 'E:\KiCad\8.0\bin' --authoring-home .bifrost-authoring/runtime
codex plugin add codex-relay@personal
```

The marketplace file is `$HOME\.agents\plugins\marketplace.json`; its local
`./plugins/codex-relay` source resolves under `$HOME` in Codex CLI 0.153.4.
`local_setup` does not create or modify marketplace entries. Do not use the old
`codex plugin install --local` command.

## Verify

```powershell
.\.venv-codex\Scripts\python.exe -m codex_plugin.mcp.smoke --config "$HOME\plugins\codex-relay\.mcp.json"
.\.venv-codex\Scripts\python.exe -m codex_plugin.mcp.smoke --config "$HOME\plugins\codex-relay\.mcp.json" --mode legacy
.\.venv-codex\Scripts\python.exe -m pytest tests/ -q
```

The smoke test starts a separate server from a temporary directory, discovers
all six tools, calls `list_adapters`, and checks a structured missing-adapter
error. It does not open or modify a design. Both Python packages must be
installed in the configured runtime; pytest's import paths are not a substitute.

Start a **new Codex CLI session** after installation. Request:

> Use the Bifrost plugin to list available engineering adapters. Do not modify files.

Approve the MCP discovery call when prompted. Non-interactive `codex exec`
with approval policy `never` cannot make a tool call that requires approval.
Use reviewed approval or an interactive session, not an unrestricted sandbox.

## Current Readiness

- Plugin installation, stdio discovery, and a real Codex CLI `list_adapters`
  call were verified with Codex CLI 0.153.4 on Windows.
- KiCad 8.0.9 is detected through its bundled Python and configured CLI path.
  Native divider creation/editing, reopening, and ERC acceptance pass.
- Multisim 14.3 uses an isolated 32-bit COM worker. Circuit inspection,
  connectivity reports, DC, AC, and transient analysis are implemented and
  have live MCP integration coverage. Native R/C/L/VDC authoring also passes
  persisted revision and divider DC acceptance. See [Multisim Setup](MULTISIM_SETUP.md).
- Hermes is not part of this plugin and remains scaffolded.

Native authoring always publishes a distinct revision and preserves the input.
Simulation success requires captured numeric results, not just a successful command.

## Development Updates

Python packages are installed editable, so a newly started MCP process uses
current source. After changing plugin metadata, MCP configuration, or skills,
run `local_setup` again, use the plugin-creator cachebuster helper on
`$HOME\plugins\codex-relay`, reinstall with `codex plugin add`, and start a new
session. Existing MCP processes retain their previous code and in-memory state.
