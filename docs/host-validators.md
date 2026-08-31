# Host Validators

Satchel host validators are non-mutating checks that run after source,
generated-file, structural, and release diagnostics pass.

Use them with:

```bash
satchel check . --host
satchel smoke . --host
satchel pack . --target claude --host
```

## Current Validators

| Target | Validator | Behavior |
| --- | --- | --- |
| Claude | `claude plugin validate <path>` | Runs when the Claude CLI is installed. Failures fail Satchel. |
| Codex | Structural fallback | Codex currently exposes plugin marketplace management, but no non-mutating plugin validator in the local CLI surface. |
| GitHub Copilot | Structural fallback | Reports whether the `copilot` CLI is missing or lacks a documented non-mutating validator. |
| Antigravity | `agy plugin validate <generated-package>` | Runs against the generated Antigravity package when the CLI is installed. Failures fail Satchel. |

Warnings from missing or unavailable host validators do not fail the command.
Validator failures and timeouts do fail the command.

## Adding Validators

Validators live in `src/satchel/host_validators.py` and implement the
`HostValidatorPlugin` protocol. Prefer `CommandHostValidator` when a host CLI
exposes a stable non-mutating command. Use `StructuralFallbackValidator` when a
host has no safe command yet.

Only add command validators when the command is:

- non-mutating;
- stable enough for CI;
- safe to run on local plugin source;
- deterministic enough to produce actionable errors.

Keep mutating install, marketplace add, update, upgrade, and tag commands out
of automated validation.
