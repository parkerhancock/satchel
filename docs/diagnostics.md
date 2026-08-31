# Diagnostics

`satchel check --json` emits stable diagnostic codes for CI systems and editor
integrations.

```json
{
  "ok": false,
  "summary": {
    "errors": 1,
    "warnings": 0
  },
  "diagnostics": [
    {
      "severity": "error",
      "code": "SATCHEL_GENERATED_STALE",
      "message": "generated claude output is stale",
      "target": "claude"
    }
  ]
}
```

## Codes

| Code | Meaning | Usual Fix |
| --- | --- | --- |
| `SATCHEL_SCHEMA_INVALID` | `satchel.yaml` uses the wrong schema value. | Set `schema: satchel/v0`. |
| `SATCHEL_FIELD_REQUIRED` | A required root field is missing or empty. | Add `name`, `version`, or `description`. |
| `SATCHEL_NAME_INVALID` | Package name is not lowercase kebab-case ASCII. | Rename with lowercase letters, digits, and hyphens. |
| `SATCHEL_COMPONENTS_TYPE` | `components` is not a mapping. | Use YAML mapping syntax under `components`. |
| `SATCHEL_COMPONENT_PATH_INVALID` | A component path is absolute or escapes the package root. | Use a relative path inside the package. |
| `SATCHEL_COMPONENT_PATH_MISSING` | A declared component path does not exist. | Create the file/directory or fix the path. |
| `SATCHEL_COMPONENT_PATH_TYPE` | A component path has the wrong filesystem type. | Use a directory for directory components. |
| `SATCHEL_TARGETS_TYPE` | `targets` is not a mapping. | Use YAML mapping syntax under `targets`. |
| `SATCHEL_TARGET_TYPE` | A target entry is not a mapping. | Configure target fields under the target name. |
| `SATCHEL_TARGET_FIELD_TYPE` | A target field has the wrong type. | Use the documented field shape for that target. |
| `SATCHEL_TARGET_UNKNOWN` | A target has no adapter. | Remove it or install/add an adapter that supports it. |
| `SATCHEL_TARGET_EXPERIMENTAL_UNMARKED` | Experimental target is enabled without `experimental: true`. | Mark it experimental or disable it. |
| `SATCHEL_TARGET_NOT_APPLICABLE_TYPE` | `notApplicable` is present but is not a non-empty string. | Write a concise reason or remove the field. |
| `SATCHEL_TARGET_NOT_APPLICABLE_ENABLED` | An enabled target is marked not applicable. | Disable the target or remove `notApplicable`. |
| `SATCHEL_MARKETPLACE_MISSING` | `satchel check --release` found an enabled target with no marketplace block. | Add `targets.<target>.marketplace` or disable the target. |
| `SATCHEL_MARKETPLACE_SOURCE_MISSING` | `satchel check --release` found a marketplace without a source. | Add a remote marketplace source. |
| `SATCHEL_MARKETPLACE_LOCAL_SOURCE` | Marketplace source is local-only. | Use a remote GitHub repo, Git URL, or HTTP URL before release. |
| `SATCHEL_MARKETPLACE_OWNER_MISSING` | A Claude or Copilot marketplace has no author metadata for its required owner. | Add `author` as a name string or object. |
| `SATCHEL_COPILOT_MARKETPLACE_SOURCE_LEGACY` | A Copilot marketplace source uses the legacy `type` discriminator. | Rename `type` to `source`; Satchel normalizes it during generation. |
| `SATCHEL_CHATGPT_RELEASE_FIELD_MISSING` | A required ChatGPT release metadata field is missing. | Add the named field under `targets.chatgpt.app`. |
| `SATCHEL_CHATGPT_URL_NOT_HTTPS` | A ChatGPT release URL does not use HTTPS. | Use an HTTPS MCP, policy, or support URL. |
| `SATCHEL_ANTHROPIC_RELEASE_FIELD_MISSING` | A required Anthropic connector release field is missing. | Add the named field under `targets.anthropic.connector`. |
| `SATCHEL_ANTHROPIC_URL_NOT_HTTPS` | An Anthropic connector release URL does not use HTTPS. | Use an HTTPS MCP, policy, or support URL. |
| `SATCHEL_ANTHROPIC_BRAND_IN_NAME` | Connector naming includes a reserved Anthropic brand term. | Choose a connector name without the reserved brand term. |
| `SATCHEL_COWORK_MCP_NOT_REMOTE` | Cowork is enabled with a local command-based MCP server. | Configure `targets.cowork.connector.mcpServerUrl` for the deployed server. |
| `SATCHEL_COWORK_MCP_NOT_HTTPS` | A Cowork connector MCP URL does not use HTTPS. | Use the deployed server's HTTPS endpoint. |
| `SATCHEL_COWORK_FIELD_MISSING` | Required Cowork developer, icon, or app metadata is missing. | Add the named field under `targets.cowork`. |
| `SATCHEL_COWORK_ACCENT_COLOR_INVALID` | Cowork `accentColor` is not a CSS hex color. | Use a value such as `#e5a82f`. |
| `SATCHEL_PATH_TYPE` | A path field is not a string. | Use a relative path string. |
| `SATCHEL_PATH_INVALID` | A target path is absolute or escapes the package root. | Use a relative path inside the package. |
| `SATCHEL_SKILLS_EMPTY` | The skills directory has no skill folders. | Add `skills/<name>/SKILL.md` or remove the component. |
| `SATCHEL_SKILL_FILE_MISSING` | A skill folder lacks `SKILL.md`. | Add the file. |
| `SATCHEL_SKILL_FRONTMATTER_MISSING` | Skill frontmatter lacks `name` or `description`. | Add both fields to `SKILL.md`. |
| `SATCHEL_SKILL_NAME_MISMATCH` | Skill name differs from its folder. | Rename the folder or frontmatter. |
| `SATCHEL_GENERATED_MISSING` | A generated output is missing. | Run `satchel generate`. |
| `SATCHEL_GENERATED_STALE` | A generated output differs from current source. | Run `satchel generate`. |
| `SATCHEL_OUTPUT_FIELD_MISSING` | A generated manifest lacks a required field. | Fix source metadata or the target adapter. |
| `SATCHEL_OUTPUT_FIELD_TYPE` | A generated manifest field has the wrong type. | Fix source metadata or the target adapter. |
| `SATCHEL_OUTPUT_PATH_TYPE` | A generated path field is not a string. | Fix the source component or adapter. |
| `SATCHEL_OUTPUT_PATH_STYLE` | A generated path does not use Satchel's relative path style. | Prefer paths beginning with `./`. |
| `SATCHEL_HOST_CLI_MISSING` | A requested host CLI is not installed. | Install the host CLI or run without `--host`. |
| `SATCHEL_HOST_VALIDATOR_UNAVAILABLE` | No non-mutating validator is known for the host. | Rely on structural checks until host support lands. |
| `SATCHEL_HOST_VALIDATOR_TIMEOUT` | A host validator timed out. | Retry or raise `--host-timeout`. |
| `SATCHEL_HOST_VALIDATOR_FAILED` | A host validator returned a failure. | Read the validator output and fix the generated host files. |
