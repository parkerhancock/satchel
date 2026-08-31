# Release Process

Satchel publishes from GitHub releases using trusted publishing to PyPI.

## One-Time Setup

1. Create the PyPI project named `satchel-agent`. The CLI command remains
   `satchel`.
2. Configure PyPI trusted publishing for this GitHub repository and the
   `publish.yml` workflow.
3. Confirm the GitHub repository has Actions enabled.

## Preflight

```bash
uv sync
uv run ruff check .
uv run pytest
uv run python scripts/generate_schema_docs.py --check
git diff --check
uv run satchel check . --release
uv run satchel check . --host
uv run satchel smoke . --host
uv run satchel pack . --target codex --release
uv run satchel pack . --target claude --release
uv run satchel pack . --target copilot --release
```

Review the generated root outputs:

```bash
uv run satchel generate .
git diff -- .codex-plugin .claude-plugin .github/plugin .agents/plugins
```

## Tag and Publish

Update `pyproject.toml`, `src/satchel/__init__.py`, and `satchel.yaml` to the
same version, regenerate the checked-in target outputs, then create a matching
`v<version>` GitHub release. The test suite enforces version consistency, and
the `publish.yml` workflow verifies the release tag before publishing to PyPI.

After publish, verify installation:

```bash
uv tool install satchel-agent
satchel --help
```

or:

```bash
pipx install satchel-agent
satchel --help
```

Run the on-demand release smoke workflow for the published version:

```bash
SATCHEL_RELEASE_VERSION=0.4.0
gh workflow run release-smoke.yml \
  --repo parkerhancock/satchel \
  -f version="$SATCHEL_RELEASE_VERSION"
```

The workflow installs from PyPI and from the matching GitHub tag.

## Host Install Checks

After the release smoke workflow passes, verify host marketplace installation
on a machine where the host CLIs are configured:

```bash
claude plugin marketplace add parkerhancock/satchel
claude plugin install satchel@satchel-marketplace
codex plugin marketplace add parkerhancock/satchel
copilot plugin marketplace add parkerhancock/satchel
copilot plugin install satchel@satchel-marketplace
```

These commands may modify local host configuration, so they are intentionally
kept as an explicit manual check rather than a default release workflow step.
