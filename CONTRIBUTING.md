# Contributing to Satchel

Satchel is a small Python project with generated plugin outputs. Keep changes
deterministic, source-first, and easy to validate.

## Setup

```bash
uv sync
uv run satchel report examples/basic
```

## Development Flow

Edit `satchel.yaml`, source code, fixtures, or docs first. Generated host files
should be updated with `satchel generate`, not hand-edited.

Run the local checks before opening a pull request:

```bash
uv run ruff check .
uv run pytest
uv run satchel check .
uv run satchel smoke .
```

Use host validators when the host CLIs are installed:

```bash
uv run satchel check . --host
uv run satchel smoke . --host
```

## Fixtures

The `fixtures/` directory is the conformance suite. Add or update a fixture when
you add a target, component, or portability rule.

## Generated Outputs

The repository root is itself a Satchel package. If you change `satchel.yaml`,
`skills/`, or target adapters, regenerate the root outputs:

```bash
uv run satchel generate .
```

Do the same for examples that commit generated host output.

