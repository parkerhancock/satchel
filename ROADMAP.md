# Roadmap

Satchel is public alpha software. The roadmap prioritizes correctness,
validation, and developer ergonomics before adding many more targets.

## Current Surface

- Neutral `satchel.yaml` source manifest.
- Codex, Claude, GitHub Copilot, Microsoft 365 Copilot Cowork, ChatGPT metadata,
  Anthropic Connectors Directory metadata, and experimental Antigravity target
  adapters.
- Generated manifest and marketplace outputs.
- Source validation, drift checks, structural output validation, and smoke
  tests.
- JSON Schema and fixture-based conformance tests.
- `satchel --version` and `satchel check --json` for automation.
- On-demand release smoke workflow for PyPI and GitHub-tag installs.
- Marketplace installability docs and `satchel check --release`.
- Target-scoped smoke tests and package archives.
- Marketplace patch mode for preserving host-owned metadata.
- Generated schema reference docs from the JSON Schema.
- Host validator plugin registry for non-mutating CLI validators.
- Standards watch source registry, snapshots, and scheduled drift issue
  workflow.

## Near-Term Work

- Concrete Codex and Copilot command validators when those CLIs expose stable
  non-mutating plugin validation commands.

## Possible Integrations

- Optional `plugin-scanner verify` integration.
- More target adapters through the existing adapter interface.
- Richer portability reports for hooks and MCP server behavior.
