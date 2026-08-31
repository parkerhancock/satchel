---
name: satchel
description: Use when creating, validating, generating, or maintaining Satchel packages that build multi-target agent plugin outputs from satchel.yaml.
---

# Satchel

Use Satchel when a repository should maintain one product-agnostic source
package and generate host-specific Codex, Claude, Copilot, Cowork, ChatGPT,
Anthropic, and experimental Antigravity artifacts.

Distinguish repository-backed package targets from remote service metadata.
Codex, Claude, Copilot, Cowork, and Antigravity can package shared skills and
source code. ChatGPT and Anthropic describe separately deployed remote MCP
services; they do not turn a skill-only repository into one.

## Core Workflow

1. Check for `satchel.yaml` at the package root.
2. Edit `satchel.yaml`, `skills/`, and shared resources as the source of truth.
3. Run `satchel generate <package-root>` after source changes.
4. Run `satchel check <package-root>` before committing.
5. Run `satchel smoke <package-root>` before release or after target changes.
6. Run `satchel report <package-root>` to confirm which targets are enabled,
   disabled, or not applicable.
7. Treat generated `.codex-plugin/`, `.claude-plugin/`, `.github/plugin/`,
   `.agents/plugins/`, `cowork/`, remote-service metadata, and marketplace files
   as build outputs.
8. Use `satchel standards check <package-root>` before changing adapters that
   depend on current host plugin docs.

## Command Selection

Use the command that fits the current environment. For the complete command and
feature map, read `references/features.md`.

```bash
# Inside the Satchel repository
uv run satchel --version
uv run satchel check .
uv run satchel smoke .
uv run satchel pack . --target claude --release
uv run satchel standards check .

# If Satchel is installed on PATH
satchel --version
satchel check .
satchel smoke .
satchel pack . --target claude --release
satchel standards check .

# For one-off use from source
uvx --from git+https://github.com/parkerhancock/satchel satchel check .
```

Request user approval before installing dependencies or running `uvx` when the
environment requires network access.

## Editing Rules

- Prefer adding schema support and tests over hand-editing generated host files.
- Keep paths relative to the package root and beginning with `./`.
- Put shared agent behavior in `skills/<name>/SKILL.md`.
- Keep implementation code in the package repository. `satchel pack` includes
  tracked and unignored source files plus the selected regenerated target
  output, so packages may be skill plus code.
- Put host-specific presentation metadata under `targets.codex` or
  host-specific target mappings.
- Use `satchel report <package-root>` to explain portability status.
- Use `satchel check <package-root> --json` for CI, editor integrations, or
  other machine-readable diagnostics.
- Use `--host` only when host CLIs are installed and non-mutating validation is
  appropriate for the current environment.
- Host validation is registry-based. Use the validator summary in
  `references/features.md` when changing or explaining validator behavior.
- For installable Claude/Codex/Copilot plugin releases, configure remote
  marketplace sources and run `satchel check <package-root> --release --host`.
- Cowork always requires developer metadata, 32x32 outline and 192x192 color
  PNG icons, and an accent color. Its connector is optional, but when present
  it must point to a remote HTTPS MCP server.
- Enable ChatGPT or Anthropic only for a separately hosted remote HTTPS MCP
  service. Otherwise disable the target with a non-empty `notApplicable`
  reason.
- Keep Antigravity enabled outputs marked `experimental: true` and validate
  them with the current `agy` CLI when available.
- Set `targets.<target>.marketplace.patch: true` only when existing marketplace
  files contain host-owned metadata that should survive generation.
- Use `satchel smoke <package-root> --target <target>` to isolate one host.
- Use `satchel pack <package-root> --target <target> --release` to build a
  target-specific ZIP archive from a clean generated copy.
- Use `satchel standards check <package-root>` to compare upstream host docs
  with committed standards snapshots.
- When a reviewed `standards-watch` issue needs implementation help, manually
  dispatch the gated Claude PR workflow with its issue number.
- Change `satchel.yaml` and run `satchel generate <package-root>` whenever a
  generated marketplace JSON file needs an update.

## References

- Read `references/manifest.md` when changing `satchel.yaml` fields.
- Read `references/features.md` when answering what Satchel supports, choosing
  commands, updating docs, or planning roadmap work.
- Read `references/workflows.md` when adding a new dual-target plugin package.
- Read `references/features.md` for host-validator, marketplace, packaging,
  and standards-sync behavior. These references are bundled with the skill and
  do not depend on the Satchel source checkout.
