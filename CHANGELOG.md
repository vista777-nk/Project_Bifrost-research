# Changelog

All notable changes to Bifrost are documented in this file.

## Unreleased

### Added

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
