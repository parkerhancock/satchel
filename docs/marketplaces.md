# Marketplaces

Satchel treats marketplace files as host-specific catalogs, not as the neutral
source of truth. The neutral package source is still `satchel.yaml`, `skills/`,
and shared component files.

## Manifest vs Marketplace

| Layer | Purpose | Examples |
| --- | --- | --- |
| Plugin manifest | Describes the plugin package. | `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json` |
| Marketplace catalog | Tells a host how to discover or install one or more plugins. | `.agents/plugins/marketplace.json`, `.claude-plugin/marketplace.json` |

Generated marketplace files should be treated as build outputs. Edit
`satchel.yaml`, then run `satchel generate`.

## Patch Mode

Use patch mode when a host or user needs to keep marketplace metadata that
Satchel should not own.

```yaml
targets:
  claude:
    marketplace:
      path: ./.claude-plugin/marketplace.json
      patch: true
      source:
        source: github
        repo: example/my-plugin
```

When `patch: true` is set, Satchel reads the existing marketplace file, updates
the generated fields for the package's plugin entry, and preserves:

- unknown top-level marketplace fields;
- unknown marketplace `interface`, `metadata`, and `owner` fields;
- unrelated plugin entries and their order;
- unknown fields on the package's plugin entry;
- unknown fields inside a plugin `policy` object.

Satchel still owns generated fields such as the package plugin `name`, `source`,
`version`, `description`, generated skill paths, and generated policy fields.
Invalid marketplace JSON fails instead of being overwritten.

## Package-Relative vs Machine-Local Sources

A package-relative source is release installable when the marketplace and plugin
folder ship in the same repository or archive. Both Claude and Codex support this
layout.

Examples of portable package-relative sources:

```yaml
targets:
  claude:
    marketplace:
      source: ./

  codex:
    marketplace:
      source:
        source: local
        path: ./plugins/my-plugin
```

Absolute paths and paths that escape the package root are machine-local and are
not release installable from another machine.

Examples of remote-ready sources:

```yaml
targets:
  claude:
    marketplace:
      source:
        source: github
        repo: example/my-plugin
        ref: main

  codex:
    marketplace:
      source:
        source: url
        url: https://github.com/example/my-plugin.git
        ref: main
```

Run `satchel check --release` before publishing. It fails if enabled
marketplace-capable targets do not have package-relative or remote sources.

## Claude And Codex Workflow

For a package like `my-plugin`:

1. Configure package-relative or remote marketplace sources in `satchel.yaml`.
2. Run:

   ```bash
   satchel generate .
   satchel check . --release --host
   claude plugin validate .
   ```

3. Commit and push the plugin repository.
4. Test Claude install:

   ```bash
   claude plugin marketplace add example/my-plugin
   claude plugin install my-plugin@my-plugin-marketplace
   ```

5. Test Codex install:

   ```bash
   codex plugin marketplace add example/my-plugin
   ```

   Complete the install through the Codex plugin UI if the host requires an
   interactive step.

## Current Installability Rules

- `remote-ready`: marketplace source is package-relative or points at a GitHub
  repo, Git URL, or HTTP URL, and required owner metadata is available.
- `incomplete (owner missing)`: the Claude or Copilot marketplace has a source
  but no author in `satchel.yaml` or preserved owner in a patch-mode file.
- `local-only`: marketplace source is an absolute path, escapes the package
  root, or is otherwise tied to one machine.
- `not declared`: the target has no marketplace block.
- `unsupported`: the target has no known marketplace flow.

`satchel report` prints this status for every target.
