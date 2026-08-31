# Satchel Feature Map

Use this reference when choosing Satchel commands, explaining current
capabilities, or checking whether the skill docs are complete.

## Targets

Satchel currently supports:

- `codex`: native manifest, marketplace output, skills, MCP, apps, and hooks
  references.
- `claude`: native manifest, marketplace output, skills, commands, agents, MCP,
  and hooks.
- `copilot`: native manifest, optional root manifest, marketplace output,
  skills, agents, commands, hooks, MCP, and LSP.
- `cowork`: Microsoft 365 Unified App Manifest with agent skills and an
  optional remote HTTPS MCP connector.
- `chatgpt`: ChatGPT app metadata, submission checklist, and MCP
  release-readiness output.
- `anthropic`: Anthropic Connectors Directory metadata and submission
  checklist for a remote MCP server.
- `antigravity`: experimental local package output under `.agents/plugins/`,
  including native host validation when `agy` is installed; marketplace
  behavior is unsupported.

## Components

Shared source components live under `components` in `satchel.yaml`.

| Component | Purpose |
| --- | --- |
| `skills` | Portable skill directories with `SKILL.md`. |
| `mcp` | JSON MCP server config. |
| `hooks` | Hook config copied or referenced per target. |
| `agents` | Agent definitions for targets that support them. |
| `commands` | Command definitions for targets that support them. |
| `lsp` | LSP server config for Copilot. |
| `rules` | Rule files for Antigravity output. |
| `apps` | Codex app config. |

## Commands

| Command | Use |
| --- | --- |
| `satchel --version` | Confirm the installed CLI version. |
| `satchel init <path>` | Create `satchel.yaml` and a minimal example skill. |
| `satchel generate <path>` | Write enabled target manifests and marketplace files. |
| `satchel check <path>` | Validate source and fail on missing or stale generated outputs. |
| `satchel check <path> --json` | Emit machine-readable diagnostics with stable codes. |
| `satchel check <path> --host` | Run non-mutating host validators where available. |
| `satchel check <path> --release` | Require remote marketplace sources for release installability. |
| `satchel smoke <path>` | Validate a clean temporary regenerated copy. |
| `satchel smoke <path> --target <target>` | Smoke only one enabled target. |
| `satchel pack <path> --target <target>` | Build `dist/<name>-<version>-<target>.zip` from a clean regenerated copy. |
| `satchel pack <path> --target <target> --release` | Pack only after release marketplace checks pass. |
| `satchel report <path>` | Print target, marketplace, and component portability status. |
| `satchel standards check <path>` | Compare upstream host standards sources with committed snapshots. |

## Standards Automation

The scheduled `Standards Watch` workflow opens or updates a `standards-watch`
issue when upstream host docs drift from committed snapshots. After reviewing
the issue, a maintainer can manually dispatch the gated Claude Code workflow
with its issue number. The workflow refreshes snapshots, updates Satchel as
needed, runs validation, and opens a PR for review.

## Marketplace Patch Mode

Set `targets.<target>.marketplace.patch: true` to preserve host-owned metadata
in an existing marketplace file while updating Satchel-owned fields for the
package's plugin entry.

Patch mode preserves unknown top-level fields, unrelated plugin entries,
unknown fields on the package plugin entry, and unknown fields in plugin
`policy` objects. Satchel still updates generated fields such as `name`,
`source`, `version`, `description`, skill paths, and generated policy values.

## Validation Surface

`satchel check` and `satchel smoke` cover:

- schema and required manifest fields;
- freshness of generated schema reference docs;
- safe relative component and target paths;
- skill directory shape and required `SKILL.md` frontmatter;
- generated-file missing/stale detection;
- structural output checks for enabled targets;
- marketplace release checks for Codex, Claude, and Copilot;
- release metadata checks for ChatGPT and Anthropic;
- remote HTTPS connector checks for Cowork;
- optional host validators, currently including `claude plugin validate` and
  `agy plugin validate` when available through the host validator registry.
- upstream standards drift when `satchel standards check` is run against
  committed snapshots.

Warnings do not fail the run. Errors fail the run.

## Output Ownership

Treat generated target manifests and marketplace files as build outputs. Change
`satchel.yaml`, shared components, and target config, then rerun
`satchel generate`.

Target archive builds do not mutate the source package. `satchel pack` copies
the package to a temporary directory, removes generated outputs in that copy,
regenerates only the selected target, validates it, then writes a ZIP archive.
