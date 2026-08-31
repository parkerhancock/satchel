# Satchel Workflows

## Add Satchel to a Plugin Repo

1. Create `satchel.yaml`.
2. Put shared skills under `skills/<name>/SKILL.md`.
3. Configure `targets.codex`, `targets.claude`, and any other target adapters
   the package should support.
4. Run `satchel generate .`.
5. Run `satchel check .`.
6. Run `satchel smoke .` for release-sensitive changes.

## Create a Package

```bash
satchel --version
satchel init my-plugin
satchel generate my-plugin
satchel check my-plugin
satchel smoke my-plugin
```

## Update an Existing Package

1. Edit `satchel.yaml`, `skills/`, or shared component files.
2. Run `satchel generate <package-root>`.
3. Run `satchel check <package-root>`.
4. Run `satchel smoke <package-root>` when the change affects targets,
   components, or release behavior.

## Release Validation

```bash
satchel check . --release
satchel check . --host
satchel smoke . --host
satchel smoke . --target claude --host
satchel pack . --target claude --release
```

`--host` runs non-mutating host validators where Satchel knows one. Targets
without a known non-mutating validator use structural checks and emit warnings.
`--release` requires remote marketplace sources for enabled installable targets.

## Make a Repo Recursive

For a repo that is itself a plugin:

1. Add `satchel.yaml` at the repo root.
2. Add `skills/<repo-name>/SKILL.md`.
3. Configure generated manifests and marketplace paths.
4. Generate outputs with `satchel generate .`.
5. Add a regression test that `stale_outputs(build_outputs(...))` is empty.
6. Validate with `satchel check . --host` and `satchel smoke . --host` when
   host CLIs are available.

## Before Release

- Run lint and tests.
- Run `satchel check .`.
- Run `satchel check . --json` if CI or editor tooling consumes diagnostics.
- Run `satchel check . --release`.
- Run `satchel smoke .`.
- Run `satchel pack . --target <target> --release` for each release archive
  target.
- Run release checks for enabled ChatGPT and Anthropic metadata targets.
- Verify enabled Cowork connectors against their remote HTTPS MCP endpoint.
- Run `claude plugin validate .` when Claude Code is installed.
- Confirm the Codex marketplace path and source type match the intended install
  flow.
- Confirm the Copilot marketplace path and source type match the intended
  install flow.
- Keep Antigravity output marked experimental until local host validation has
  been run against the generated package.
