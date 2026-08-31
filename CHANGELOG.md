# Changelog

All notable changes to Satchel are tracked here.

## 0.4.0 - Unreleased

- Added the `cowork` target: generates a Microsoft 365 Copilot Cowork plugin
  manifest (`cowork/manifest.json`, M365 Unified App Manifest v1.28) with
  `agentSkills` from the shared `skills` component and a remote-MCP-only
  `agentConnectors` entry from `targets.cowork.connector.mcpServerUrl`.
  Cowork's connector transport has no local/stdio equivalent, so validation
  now flags (`SATCHEL_COWORK_MCP_NOT_REMOTE`) any `mcp` component server
  declared via `command`/`args` instead of a `url` when the `cowork` target
  is enabled, and requires the configured connector URL to be HTTPS
  (`SATCHEL_COWORK_MCP_NOT_HTTPS`) rather than only warning.
- Aligned the Python package, CLI, recursive Satchel package, generated plugin
  manifests, and release workflow on one version.
- Updated Copilot marketplace source output to the current `source`
  discriminator while normalizing the legacy `type` form with a warning.
- Added required marketplace-owner checks for Claude and Copilot, including
  support for string-form authors.
- Added Claude manifest mappings for custom commands, agents, hooks, MCP, and
  LSP component paths.
- Added `agy plugin validate` as the Antigravity host validator and moved the
  standards registry to stable canonical Markdown sources.
- Replaced private-project examples with neutral fixtures and replaced the
  bundled copy of Anthropic's live form with a source-linked preparation guide.
- Restricted the write-capable standards maintenance workflow to manual
  maintainer dispatch before public release.

## 0.3.0 - 2026-05-31

- Added the `chatgpt` target: generates ChatGPT Apps SDK app metadata
  (`chatgpt/app.json`) plus a submission checklist and MCP release-readiness
  output.
- Added the `anthropic` target: generates Anthropic Connectors Directory
  connector metadata (`anthropic/connector.json`) plus a manual submission
  checklist. Distinct from the `claude` target, which builds a Claude Code
  plugin. Mirrors the `chatgpt` metadata/checklist target shape.
- Added `satchel standards check`, a standards source registry, baseline
  snapshots, and a scheduled Standards Watch workflow for upstream host docs.
- Added a maintainer-gated Claude Code workflow that can draft PRs from
  standards-watch issues.

## 0.2.0 - 2026-05-20

- Added `satchel --version`.
- Added `satchel check --json` with machine-readable diagnostics and stable
  diagnostic codes.
- Added release smoke workflow support for PyPI and GitHub-tag installs.
- Added public install badges and PyPI-first quick start docs.
- Added marketplace installability docs and `satchel check --release`.
- Added release diagnostics for missing or local-only marketplace sources.
- Added `satchel smoke --target` and `satchel pack --target` for target-scoped
  validation and archive builds.
- Added marketplace patch mode with preservation of host-owned marketplace
  metadata.
- Added generated schema reference docs from `schemas/satchel.schema.json`.
- Added a host validator plugin registry for non-mutating CLI validators and
  structural fallback checks.
- Hardened CI and publish workflows with release checks, host-aware smoke
  tests, schema-doc checks, and target archive builds.

## 0.1.0 - 2026-05-20

- Initial public alpha release.
- Added `satchel.yaml` source manifests.
- Added Codex, Claude, GitHub Copilot, and experimental Antigravity target
  adapters.
- Added generation, drift checks, structural validation, and clean-copy smoke
  tests.
- Added fixture suite, JSON Schema, CI, release workflow, and release-auditor
  demo.
