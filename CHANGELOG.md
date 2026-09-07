# Changelog

All notable changes to Bifrost are documented in this file.

## Unreleased

### Changed

- Kept mouse/keyboard and GUI-control automation prohibited and documented a
  verified non-GUI Multisim compressed-XML route, including native reopening,
  a persisted value edit, and component/connectivity creation proofs.
- Restored native circuit creation and editing in both KiCad and Multisim as
  explicit product acceptance criteria, separate from the completed integration
  foundation; recorded authoring API gaps and a native-file acceptance case.

### Added

- Added a 32-bit Multisim COM worker, circuit inspection, connectivity reports,
  bounded simulations, and output retrieval by simulation action ID.
- Added source snapshots and explicit, race-safe report overwrite confirmation.
- Added a current Codex plugin manifest and a local packaging command that pins
  the installed Python runtime and KiCad paths without editing global settings.
- Added subprocess MCP smoke checks for automatic negotiation and the legacy
  handshake, including tool discovery and structured execution errors.
- Implemented the Codex MCP server with six tools, runtime result storage,
  validation, log collection, previews, retries, and explicit confirmation.
- Added MCP tool schemas plus unit and in-process MCP SDK integration tests.

### Fixed

- Prevent callers from bypassing confirmation for recognized dangerous actions
  by supplying medium risk, including in force mode.
- Restored the documented action risk and permission fields used by relay
  safety gates.
- Allowed filesystem-only KiCad inspection and artifact collection when the
  KiCad executable is unavailable, and record exported Gerber artifacts.
- Added overwrite detection so existing output targets require confirmation.
- Install MCP dependencies in GitHub Actions so relay SDK integration tests run.
- Added monorepo import paths for direct `pytest` and local plugin execution.
