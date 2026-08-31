# Satchel Manifest Reference

Use `satchel.yaml` as the package source of truth. The schema is `satchel/v0`.

Required root fields:

- `name`: lowercase kebab-case package name.
- `version`: package version.
- `description`: short package description.

Common optional fields:

- `author`
- `homepage`
- `repository`
- `license`
- `keywords`

Components are declared under `components` and must point to relative paths
inside the package root. Supported components are `skills`, `mcp`, `hooks`,
`agents`, `commands`, `lsp`, `rules`, and `apps`.

Targets live under `targets`. The current adapters are `codex`, `claude`,
`copilot`, `cowork`, `chatgpt`, `anthropic`, and experimental `antigravity`.

Codex output:

```yaml
targets:
  codex:
    enabled: true
    manifest: ./.codex-plugin/plugin.json
    marketplace:
      path: ./.agents/plugins/marketplace.json
      patch: true
    interface:
      displayName: My Plugin
```

Claude output:

```yaml
targets:
  claude:
    enabled: true
    manifest: ./.claude-plugin/plugin.json
    marketplace:
      path: ./.claude-plugin/marketplace.json
      patch: true
    displayName: My Plugin
```

Copilot output:

```yaml
targets:
  copilot:
    enabled: true
    manifest: ./.github/plugin/plugin.json
    marketplace:
      path: ./.github/plugin/marketplace.json
      patch: true
```

Cowork output:

```yaml
targets:
  cowork:
    enabled: true
    manifest: ./cowork/manifest.json
    connector:
      displayName: My Connector
      mcpServerUrl: https://example.com/mcp
```

ChatGPT release metadata:

```yaml
targets:
  chatgpt:
    enabled: true
    manifest: ./chatgpt/app.json
    app:
      displayName: My App
      mcpUrl: https://example.com/mcp
      privacyUrl: https://example.com/privacy
      termsUrl: https://example.com/terms
      supportUrl: https://example.com/support
```

Anthropic Connectors Directory metadata:

```yaml
targets:
  anthropic:
    enabled: true
    manifest: ./anthropic/connector.json
    connector:
      displayName: My Connector
      mcpUrl: https://example.com/mcp
      privacyUrl: https://example.com/privacy
      termsUrl: https://example.com/terms
      supportUrl: https://example.com/support
```

Experimental Antigravity output:

```yaml
targets:
  antigravity:
    enabled: false
    experimental: true
    output: ./.agents/plugins/my-plugin
```

Marketplace `source` values are target-specific. Codex, Claude, and Copilot use
different source object conventions. ChatGPT and Anthropic generate submission
metadata for separately hosted remote MCP servers. Cowork generates a Unified
App Manifest whose connector also references a remote HTTPS MCP server. Use
`marketplace.patch: true` when an existing marketplace file contains host-owned
metadata that should survive generation. Keep Antigravity marked experimental
until the generated package has been tested against the current host.

Prefer `docs/schema.md` for the human guide, `docs/schema-reference.md` for the
generated field reference, and `schemas/satchel.schema.json` for editor
integration.
