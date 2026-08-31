# Standards Sync

Satchel watches upstream host plugin documentation so adapter drift is visible
before it becomes a release problem.

The source registry lives in `standards/sources.yaml`. It tracks canonical
official Markdown documentation for Codex, Claude Code, GitHub Copilot CLI,
and Antigravity, plus optional non-mutating CLI help probes. Markdown sources
avoid navigation and client-rendering churn that does not change a host
contract.

Run the watch locally:

```bash
uv run satchel standards check .
```

Update snapshots after intentionally accepting upstream changes:

```bash
uv run satchel standards check . --update
```

Run optional local CLI probes:

```bash
uv run satchel standards check . --include-commands
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | All checked sources match committed snapshots. |
| `1` | A required source could not be fetched. |
| `2` | One or more sources are new or changed. |

The scheduled `Standards Watch` workflow runs weekly and on demand. When it
detects a changed source, it updates snapshots in the workflow workspace and
opens or comments on a `standards-watch` issue with the machine-readable report.
The workflow does not commit changes automatically. A maintainer should review
the upstream diff, update Satchel adapters or docs if needed, run validation,
and commit the refreshed snapshots.

## Claude PR Generation

Satchel also includes a gated `Standards Claude PR` workflow. A maintainer runs
it manually with the number of a reviewed `standards-watch` issue. This keeps
the detection step automatic while leaving the code-writing step behind an
explicit review decision.

Required repository secrets:

| Secret | Purpose |
| --- | --- |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code OAuth token generated locally with `claude setup-token`. |

Install the official Claude GitHub App on the repository before enabling the
workflow. The workflow grants `id-token: write` so the Claude Code Action can
authenticate through the official app, and it grants write permissions for
contents and pull requests plus read access to issues and Actions so Claude can
read issue context, create branches, open PRs, and inspect validation failures.

The Claude prompt treats upstream docs and issue content as untrusted source
data. Claude should use those sources only as evidence of external standard
changes, then update snapshots, docs, adapters, fixtures, or tests as needed and
open a PR for maintainer review.

Snapshots intentionally store hashes and source metadata, not full upstream
documentation. This keeps the repository small and avoids copying substantial
third-party docs into Satchel.
