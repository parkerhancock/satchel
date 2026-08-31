# Security Policy

## Supported Versions

Satchel is pre-1.0. Security fixes are released on the latest minor version.

## Reporting a Vulnerability

Report security issues through
[GitHub private vulnerability reporting](https://github.com/parkerhancock/satchel/security/advisories/new).
Include the Satchel version, operating system, a minimal package that reproduces
the issue, and the expected impact. Do not open a public issue for an
unresolved vulnerability.

## Package Handling Model

Satchel parses package files and writes generated output. It does not execute
plugin package code during `generate`, `check`, `report`, or `smoke`.

Path handling is intentionally strict:

- Component and output paths must be relative to the package root.
- Paths that escape the package root are rejected.
- Symlinked files are skipped when copying generated Antigravity package trees.
- `satchel smoke` copies the package to a temporary directory before generating
  outputs, so it can validate a clean package without mutating the source tree.

Host validators are optional and run only when explicitly requested with
`--host`. Satchel uses non-mutating validators where known. Targets without a
documented non-mutating validator fall back to structural checks and emit a
warning.
