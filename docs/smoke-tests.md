# Smoke Tests

Satchel has two levels of release checks.

## Local Structural Smoke

`satchel smoke <path>` copies a package to a temporary directory, regenerates
all enabled outputs, and validates the generated copy. It does not mutate the
source package.

```bash
uv run satchel smoke .
```

Use `--target` to validate one enabled target:

```bash
uv run satchel smoke . --target claude
```

Run all fixture smoke tests through pytest:

```bash
uv run pytest
```

## Host-Aware Smoke

Add `--host` to run non-mutating host validators where Satchel knows one:

```bash
uv run satchel check . --host
uv run satchel smoke . --host
```

| Target | Automated Host Check |
| --- | --- |
| Claude | Runs `claude plugin validate <package>` when `claude` is installed. |
| Codex | Uses a structural fallback until a stable non-mutating validator is exposed. |
| GitHub Copilot | Uses a structural fallback until a stable non-mutating validator is available. |
| Antigravity | Runs `agy plugin validate <generated-package>` when `agy` is installed. |

Warnings from unavailable host validators do not fail the build. Host validator
errors do fail the build.

See `host-validators.md` for the validator registry and extension rules.

## Package Archives

`satchel pack <path> --target <target>` builds a clean regenerated package copy
and writes a target-specific ZIP archive to `dist/` by default.

```bash
uv run satchel pack . --target claude --release
```

`--release` adds remote marketplace-source checks before the archive is written.
`--host` can be combined with `pack` when local host validators are installed.
The source package is not mutated. In Git repositories, the archive contains
tracked and unignored package files, including implementation code, and
regenerates the selected target in a clean copy. Patch-mode marketplace files
are preserved because they may contain host-owned metadata. Outside Git,
Satchel copies the package tree while excluding its built-in cache, build, and
environment paths.

## Manual Release Smoke

For a tagged release, test clean installs from the published repository:

```bash
claude plugin marketplace add parkerhancock/satchel
claude plugin install satchel@satchel-marketplace
codex plugin marketplace add parkerhancock/satchel
copilot plugin marketplace add parkerhancock/satchel
copilot plugin install satchel@satchel-marketplace
```

Only run Antigravity install testing against a known current Antigravity CLI or
IDE build because the adapter is still marked experimental.

## Package Install Smoke

After publishing to PyPI, run:

```bash
SATCHEL_RELEASE_VERSION=0.4.0
uvx --from satchel-agent satchel --help
uvx --from "git+https://github.com/parkerhancock/satchel@v${SATCHEL_RELEASE_VERSION}" satchel --help
```

The `release-smoke.yml` GitHub workflow runs both checks on demand for a
specific version.
