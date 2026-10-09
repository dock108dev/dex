# Continuous integration and testing

## Workflows

`.github/workflows/tests.yml` validates pull requests and pushes to `main` through
`validate.yml`. `assurance.yml` runs weekly and supports manual dispatch. Scheduled
or compatibility dispatches add runtime combinations; they do not publish or deploy.

The required aggregate depends on five independent jobs:

| Job | Checks |
| --- | --- |
| Source quality | Locked setup, actionlint/ShellCheck, Ruff lint/format, Python compilation, JavaScript syntax and documentation links |
| Behavior | Entire `tests/` suite with external sockets blocked; JUnit and branch/line coverage |
| Distribution | Wheel/sdist contents and hashes, repeat build, fresh isolated install and synthetic startup |
| Browser | Chromium public/private journeys on a generated demo with acquisition disabled |
| Security | Redacted Gitleaks history scan, Bandit and pip-audit; outages and incomplete reports fail |

Normal behavior entries are Ubuntu Python 3.12/3.14 and macOS 15 Python 3.12.
Compatibility also adds Ubuntu 3.13 and macOS 15 Python 3.14. Matrix fail-fast is
disabled so all results remain visible. Source/distribution/browser/security jobs
use Ubuntu Python 3.12. These are configured checks, not a claim that a particular
hosted run passed. Repository branch-protection settings are managed separately.

The aggregate rejects missing, malformed, cancelled or unexpected skipped results.
Security policy blocks all dependency advisories, all secret findings and
high/medium Bandit findings. Lower Bandit findings remain reported. Tool and
download failures are failures rather than zero findings.

## Local checks

For ordinary development, use the smaller `dev` extra and focused tests from
[development](local-development.md). To run checks requiring CI tools:

```sh
uv sync --locked --extra dev --extra ci
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync python -m compileall -q src scripts
uv run --no-sync python scripts/ci/source.py
uv run --no-sync pytest -q --disable-socket --allow-unix-socket
```

The source check requires Node on PATH. Browser checks also require Chromium:

```sh
uv run --no-sync playwright install chromium
uv run --no-sync python scripts/ci/browser.py --output reports/ci/browser
```

For workflow changes, install the pinned validator into a disposable directory:

```sh
export DEX_CI_TOOLS="$(mktemp -d)"
uv run --no-sync python scripts/ci/install_tools.py actionlint --destination "$DEX_CI_TOOLS"
uv run --no-sync "$DEX_CI_TOOLS/actionlint" -color .github/workflows/*.yml
```

The installer supports Linux x64 and macOS arm64. ShellCheck is supplied by the
locked CI extra. Tool downloads and dependency audits use external services;
ordinary offline component tests do not. Exact distribution and security commands
live in `validate.yml`; do not run every job for a documentation-only change.

## Test and runtime inputs

Reviewed public packages, source licenses, synthetic fixtures and runtime assets
are required repository inputs. `pyproject.toml` selects wheel/sdist data explicitly;
`runtime_data.py` resolves source and installed layouts without searching private
state. Preserve package bytes and hashes unless changing the reviewed data itself.
A new demo needs no private export, species sidecar or ignored evidence directory.

Mutation tests use temporary synthetic databases. Installed smoke uses an isolated
interpreter, scrubbed provider variables, a temporary home and an ephemeral local
listener. The browser wrapper generates its own root and uses `serve_e4a.py`, which
refuses ordinary roots and blocks acquisition. Never aim these tools at an existing
collection. Original-app tests use a synthetic source root containing `web/`;
that app is not a standalone installed-wheel website.

## Reports and permissions

`scripts/ci/report_readers.py` parses bounded native results; `report.py` owns job
and aggregate commands, identity and safe summaries. Direct-script and module
entry points are supported. Required-suite checks include health, original-app
security and initializer tests so missing extracted tests cannot be hidden by a
passing parent suite.

Jobs write GitHub summaries and metrics under `reports/ci/`. Ordinary reports are
retained for 14 days, browser captures for 7 and historical health for 30. Coverage,
synthetic timings and archive sizes are measurements; comparable baselines and
deltas can remain unavailable. Reports omit owner databases, credentials and
secret/source snippets. Generated output is excluded from Git.

Weekly health reads at most 30 completed runs within 30 days, with bounded job and
first-attempt requests. It separates events, reruns and cancellation, reports
observed runner time rather than billing, and leaves incomplete measurements null.

Actions are pinned to commit SHAs and dependencies to the lockfile. Application
checks use read-only contents permission; only health also reads Actions metadata.
PRs do not use write tokens or inherited secrets. Superseded PR runs cancel;
other events retain their own concurrency groups. Dependabot updates uv and
Actions weekly. No workflow signs, publishes, deploys or changes account settings.

## Limits

Synthetic checks do not establish live provider access, photo accuracy, current
seller availability, screen-reader/device behavior or user acceptance. PostgreSQL,
TLS/proxy and container operation need environment-specific checks. Windows
process cancellation is unsupported. The source tree has no established full
static-typing contract; lint, compilation and input/behavior checks apply.
Known test-client deprecation and SQLite-resource warnings should remain visible
and be addressed through dependency/resource ownership changes.
