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
It downloads only this run/attempt’s `ci-*` artifacts, reads bounded JSON without
executing artifact content, requires seven reports (nine for compatibility), and
rejects stale candidate/attempt identities and duplicate job/runtime records.
Use **Re-run all jobs** for a fresh qualification. Re-running only failed jobs
leaves successful jobs’ prior-attempt artifacts outside the accepted boundary;
the aggregate will fail with missing reports until all jobs run in one attempt.
Each report must agree with its native outcomes; a PASS label cannot override a
failed test or scan. Failed records remain visible in the consolidated summary.
Security policy blocks all dependency advisories, all secret findings and
high/medium Bandit findings with high confidence. Other Bandit findings remain reported. Tool and
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

`scripts/ci/package_artifacts.py` inspects wheel/sdist inputs without extraction;
`smoke.py` owns isolated startup and teardown.
`scripts/ci/report_readers.py` parses bounded native results; `report.py` owns job
and aggregate commands, identity and safe summaries. Direct-script and module
entry points are supported. Required-suite checks discover every candidate `tests/test_*.py` module, including
Shopping, history, body limits, health, original-app security and initializer tests.
Job-report and aggregate-gate tests are separate suites sharing
`tests/ci_reporting_helpers.py`; health imports that helper rather than a test
module. Each module must execute at least one test; missing or all-skipped modules fail.

Jobs write GitHub summaries and metrics under `reports/ci/`. Ordinary reports are
retained for 14 days, browser captures for 7 and historical health for 30. Coverage targets `pokemon_hunter`; scripts, original-app web code and child
processes are not instrumented by this report even when their behavior is checked.
Changed-code coverage has no comparable baseline. Coverage,
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

## Required-check enforcement

The workflow's aggregate is named **CI / Required checks**. To enforce it for
merges, configure branch protection or a ruleset separately using the check
context observed in a successful run. Workflow configuration alone does not
protect a branch. If a merge queue is enabled, add `merge_group` to the caller's
events before requiring the check for queued merges.

Schedules run the default branch and can be delayed; a scheduled pass does not
validate a changed pull request. Manual compatibility dispatch validates its
selected ref. No publishing, signing or deployment is part of these workflows.

## Tools and service boundaries

The workflow uses SHA-pinned GitHub Actions and the locked CI extra. Native
summaries, artifacts and coverage provide results without a separate reporting
service. `scripts/ci/install_tools.py` downloads checksum-pinned actionlint and
Gitleaks binaries. Bandit scans Python locally; pip-audit sends dependency names
and versions to PyPI's advisory service. No owner database or provider credentials
belong in uploaded reports. Dependency audits and tool downloads require network
access and fail explicitly when unavailable.

GitHub account quotas, branch rules and code-scanning settings are managed outside
the repository. Consult the applicable service settings before enabling another
integration; do not infer activation or entitlement from source configuration.
