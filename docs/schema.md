# `satchel.yaml` Schema

Satchel uses one YAML file as the source of truth for every generated target.
The current schema identifier is `satchel/v0`.

This page is the hand-written schema guide. For the exhaustive generated field
reference, see `schema-reference.md`.

## Root Fields

| Field | Required | Type | Purpose |
| --- | --- | --- | --- |
| `schema` | yes | string | Must be `satchel/v0`. |
| `name` | yes | string | Lowercase kebab-case package name. |
| `version` | yes | string | Package version copied to targets that support it. |
| `description` | yes | string | Short package description. |
| `author` | no | string or object | Author metadata copied where supported; strings normalize to an object with a `name`. |
| `homepage` | no | string | Project homepage. |
| `repository` | no | string | Source repository URL. |
| `license` | no | string | Package license identifier. |
| `keywords` | no | array | Search keywords copied where supported. |

## Components

Each component is declared as `{ path: ./relative/path }` or, for simple cases,
as a direct string path. Paths must stay inside the package root.

| Component | Expected Path | Portability |
| --- | --- | --- |
| `skills` | directory | Native in Codex, Claude, Copilot, and Cowork; copied for Antigravity. |
| `mcp` | JSON file | Emitted as `mcpServers` or copied to `mcp_config.json`. |
| `hooks` | JSON file | Native or approximate depending on host event model. |
| `agents` | directory | Native in Claude/Copilot; copied for Antigravity. |
| `commands` | directory | Native in Claude/Copilot. |
| `lsp` | JSON file | Emitted for Copilot as `lspServers`. |
| `rules` | directory | Copied for Antigravity. |
| `apps` | JSON file | Emitted for Codex as `apps`. |

Every skill directory must contain `SKILL.md` with `name` and `description`
frontmatter.

## Targets

Targets live under `targets.<name>`. Set `enabled: false` to disable a target.
When a target's distribution model does not apply to the package, add a
non-empty `notApplicable` reason. Satchel reports that distinction separately
from an ordinary disabled target and rejects `notApplicable` on enabled targets.

```yaml
targets:
  chatgpt:
    enabled: false
    notApplicable: This package has no remote MCP service.
```

### Codex

```yaml
targets:
  codex:
    enabled: true
    manifest: ./.codex-plugin/plugin.json
    marketplace:
      path: ./.agents/plugins/marketplace.json
      patch: true
      source:
        source: url
        url: https://github.com/example/my-plugin.git
        ref: main
    interface:
      displayName: My Plugin
      shortDescription: Shared agent extension.
      category: Productivity
      capabilities:
        - Read
```

### Claude

```yaml
targets:
  claude:
    enabled: true
    manifest: ./.claude-plugin/plugin.json
    displayName: My Plugin
    marketplace:
      path: ./.claude-plugin/marketplace.json
      patch: true
      source:
        source: github
        repo: example/my-plugin
        ref: main
```

### GitHub Copilot

```yaml
targets:
  copilot:
    enabled: true
    manifest: ./.github/plugin/plugin.json
    rootManifest: ./plugin.json
    marketplace:
      path: ./.github/plugin/marketplace.json
      patch: true
      source:
        source: github
        repo: example/my-plugin
        ref: main
```

### Antigravity

```yaml
targets:
  antigravity:
    enabled: true
    experimental: true
    output: ./.agents/plugins/my-plugin
```

Antigravity support is experimental because install and marketplace behavior
still depends on host-side tooling.

### ChatGPT

```yaml
targets:
  chatgpt:
    enabled: true
    manifest: ./chatgpt/app.json
    submission:
      path: ./chatgpt/app-submission.md
    app:
      displayName: My App
      shortDescription: Public data research app.
      mcpUrl: https://example.com/mcp
      privacyUrl: https://example.com/privacy
      termsUrl: https://example.com/terms
      supportUrl: https://example.com/support
      icon: ./assets/icon.png
      category: Research
      safety:
        noClinicalAdvice: true
        noPhi: true
    compatibility:
      requireReadOnlyHints: true
      requireSearchFetch: false
```

The ChatGPT target generates Satchel-owned release artifacts, not an official
OpenAI manifest. It is meant to keep Apps SDK submission metadata, MCP endpoint
details, safety posture, and release checks deterministic while the live MCP
server remains hosted separately.

### Anthropic Connectors Directory

```yaml
targets:
  anthropic:
    enabled: true
    manifest: ./anthropic/connector.json
    submission:
      path: ./anthropic/connector-submission.md
    connector:
      displayName: My Connector
      shortDescription: Public data research connector.
      mcpUrl: https://example.com/mcp
      privacyUrl: https://example.com/privacy
      termsUrl: https://example.com/terms
      supportUrl: https://example.com/support
      icon: ./assets/icon.png
      category: Research
```

The `anthropic` target produces connector metadata and a submission checklist
for a remote MCP server. The `claude` target is the separate Claude Code plugin
package.

### Microsoft 365 Copilot Cowork

```yaml
targets:
  cowork:
    enabled: true
    manifest: ./cowork/manifest.json
    developer:
      name: Example Team
      websiteUrl: https://example.com
      privacyUrl: https://example.com/privacy
      termsOfUseUrl: https://example.com/terms
    icons:
      outline: ./assets/outline.png
      color: ./assets/color.png
    accentColor: "#e5a82f"
    connector:
      displayName: My Connector
      description: Public data research tools.
      mcpServerUrl: https://example.com/mcp
      authType: None
```

Cowork generates a Microsoft 365 Unified App Manifest with `agentSkills` from
the shared skills component and an optional `agentConnectors` entry. Cowork
connectors require a remote HTTPS MCP endpoint; local `command`/`args` MCP
servers cannot back this target. The Microsoft 365 manifest requires developer
metadata, 32x32 outline and 192x192 color PNG icons, and an accent color even
when the package contains only skills.

Set `targets.<target>.marketplace.patch: true` to preserve host-owned metadata
in existing marketplace files while updating generated plugin fields. See
`marketplaces.md` for local-only, remote-ready, and patch-mode marketplace
rules.
