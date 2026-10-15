# Continuous integration and testing

## Workflows

`.github/workflows/tests.yml` validates pull requests and pushes to `main` through
`validate.yml`. `assurance.yml` runs weekly and supports manual dispatch. Scheduled or
compatibility dispatches add runtime combinations; they do not publish or deploy.

The required aggregate depends on six independent jobs:

| Job | Checks |
| --- | --- |
| Source quality | Locked setup, actionlint/ShellCheck, Ruff lint/format, Python compilation, JavaScript syntax, current renderer authority/recovery contracts and portable documentation links |
| Behavior | Entire `tests/` suite with external sockets blocked; JUnit and branch/line coverage |
| Distribution | Wheel/sdist contents and hashes, repeat build, fresh isolated install and synthetic startup |
| Browser | Chromium public/private journeys plus current Card Library, Pokémon, edit cancellation, contextual Shopping and error recovery on generated synthetic state |
| Security | Redacted Gitleaks history/authored-input scan, Bandit and pip-audit; outages and incomplete reports fail |
| Staging PostgreSQL | Empty PostgreSQL 17.11 service, copied SQLite migration, retained values/configuration, account isolation, routes/CSRF and reviewed confirm/retry/undo |

Normal behavior entries are Ubuntu Python 3.12/3.14 and macOS 15 Python 3.12.
Compatibility also adds Ubuntu 3.13 and macOS 15 Python 3.14. Matrix fail-fast is
disabled so all results remain visible. The behavior job has a 30-minute timeout,
including setup and coverage. Source, distribution, browser, security and staging jobs
use Ubuntu Python 3.12. These are configured checks; consult the actual run for results.
Branch protection is configured separately.

The aggregate rejects missing, malformed, cancelled or unexpected skipped results. It
downloads only this run/attempt’s `ci-*` artifacts, reads bounded JSON without executing
artifact content, requires eight reports (ten for compatibility), and rejects stale
candidate/attempt identities and duplicate job/runtime records. Use **Re-run all jobs**
for a fresh qualification. Re-running only failed jobs leaves successful jobs’ prior-
attempt artifacts outside the accepted boundary; the aggregate will fail with missing
reports until all jobs run in one attempt. Each report must agree with its native
outcomes; a PASS label cannot override a failed test or scan. Failed records remain
visible in the consolidated summary. Security policy blocks all dependency advisories,
all secret findings and high/medium Bandit findings with high confidence. Other Bandit
findings remain reported. Tool and download failures are failures rather than zero
findings. `browser.py` uses one localized `E402` exception to import its helper after
bootstrapping the direct-script module path.

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

The source check and renderer contracts require Node **22.18.0**, pinned in both source
and behavior jobs. Behavior tests invoke the real JavaScript engine; relying on the
hosted image's incidental Node version would leave part of the suite unqualified. Run
`node scripts/verify_cx05_races.js`, `node scripts/verify_cx06_races.js` and `node
scripts/verify_cx06_source_tools.js` for the standalone renderer contracts. Browser
checks also require Chromium:

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

The installer supports Linux x64 and macOS arm64. ShellCheck is supplied by the locked
CI extra. Tool downloads and dependency audits use external services; ordinary offline
component tests do not. Exact distribution and security commands live in `validate.yml`;
do not run every job for a documentation-only change.

Use focused tests for ordinary changes. Keep CI environments separate from an installed
app's runtime. Synthetic helpers must never target a personal root. The integrated
package helper, `scripts/verify_cx08_package.py`, combines archive, smoke and installed
journeys when a distribution change warrants those checks.

## Test and runtime inputs

Reviewed public packages, source licenses, synthetic fixtures and runtime assets are
required repository inputs. `pyproject.toml` selects wheel/sdist data explicitly;
`runtime_data.py` resolves source and installed layouts without searching private state.
Preserve package bytes and hashes unless changing the reviewed data itself. A new demo
needs no private export, species sidecar or ignored evidence directory.

Mutation tests use temporary synthetic databases. Installed smoke uses an isolated
interpreter, scrubbed provider variables, a temporary home and an ephemeral local
listener. The browser wrapper generates its own root and uses `serve_e4a.py`, which
refuses ordinary roots and blocks acquisition. Never aim these tools at an existing
collection. Original-app tests use a synthetic source root containing `web/`; that app
is not a standalone installed-wheel website.

## Reports and permissions

`scripts/ci/package_artifacts.py` inspects wheel/sdist inputs without extraction;
`smoke.py` owns isolated startup and teardown. `scripts/ci/report_readers.py` parses
bounded native results; `report.py` owns job and aggregate commands, identity and safe
summaries. Direct-script and module entry points are supported. Required-suite checks
discover every candidate `tests/test_*.py` module, including Shopping, history, body
limits, health, original-app security and initializer tests. Job-report and aggregate-
gate tests are separate suites sharing `tests/ci_reporting_helpers.py`; health imports
that helper rather than a test module. Each module must execute at least one test;
missing or all-skipped modules fail.

Jobs write GitHub summaries and metrics under `reports/ci/`. Ordinary reports are
retained for 14 days, browser captures for 7 and historical health for 30. Coverage
targets `pokemon_hunter`; scripts, original-app web code and child processes are not
instrumented by this report even when their behavior is checked. JavaScript behavior is
checked by Node/Chromium assertions; JavaScript line coverage is not instrumented
because this source-rendered product has no established JS coverage/build pipeline.
Changed-code coverage has no comparable baseline. Coverage, synthetic timings and
archive sizes are measurements; comparable baselines and deltas can remain unavailable.
Reports omit owner databases, credentials and secret/source snippets. Generated output
is excluded from Git.

`scripts/ci/health_sources.py` owns bounded read-only API acquisition; `health.py` owns
analysis and summaries, preserving its existing entry points.

Weekly health reads at most 30 completed runs within 30 days, with bounded job and
first-attempt requests. It separates events, reruns and cancellation, reports observed
runner time rather than billing, and leaves incomplete measurements null. `--with-
resources` adds exactly two metadata requests: the first 100 artifacts and repository
cache usage. An incomplete artifact listing is a page subtotal, never total storage.
Advisory API outages preserve error records and do not change the independent required
gate. Required result/report/artifact failures still fail their jobs.

Actions are pinned to commit SHAs and dependencies to the lockfile. Application checks
use read-only contents permission; only health also reads Actions metadata. PRs do not
use write tokens or inherited secrets. Superseded PR runs cancel; other events retain
their own concurrency groups. Dependabot updates uv and Actions weekly, and the
deployment Docker base weekly. No workflow signs, publishes, deploys or changes account
settings.

## Limits

Synthetic checks do not establish live provider access, photo accuracy, current seller
availability, screen-reader/device behavior or user acceptance. The disposable
PostgreSQL gate validates the supported copied migration and Django staging behavior.
Actual TLS termination/proxy networking and container operation still need environment-
specific qualification. The scheduled container build checks the locked non-root image
and packaged registry with networking disabled; it neither publishes an image nor
qualifies a hosted deployment. Windows process cancellation is unsupported. The source
tree has no established full static-typing contract; lint, compilation and
input/behavior checks apply. Known test-client deprecation and SQLite-resource warnings
should remain visible and be addressed through dependency/resource ownership changes.

## Required-check enforcement

The workflow's aggregate is named **CI / Required checks**. To enforce it for merges,
configure branch protection or a ruleset separately using the check context observed in
a successful run. Workflow configuration alone does not protect a branch. If a merge
queue is enabled, add `merge_group` to the caller's events before requiring the check
for queued merges.

Schedules run the default branch and can be delayed; a scheduled pass does not validate
a changed pull request. Manual compatibility dispatch validates its selected ref. No
publishing, signing or deployment is part of these workflows.

## Tools and service boundaries

The workflow uses SHA-pinned GitHub Actions and the locked CI extra. Native summaries,
artifacts and coverage provide results without a separate reporting service.
`scripts/ci/install_tools.py` downloads checksum-pinned actionlint and Gitleaks
binaries. Bandit scans Python locally; pip-audit sends dependency names and versions to
PyPI's advisory service. No owner database or provider credentials belong in uploaded
reports. Dependency audits and tool downloads require network access and fail explicitly
when unavailable.

GitHub account quotas, branch rules and code-scanning settings are managed outside the
repository. Consult the applicable service settings before enabling another integration;
do not infer activation or entitlement from source configuration.


## Scheduled checks

`assurance.yml` runs Sunday at 09:23 UTC on the default branch. Manual scope `full` runs
normal validation plus advisory health; `compatibility` also adds the two interpreter
combinations and a container build. Invalid scopes are rejected. The container job
builds the digest-pinned, non-root `deploy/Dockerfile` image, checks packaged registry
imports with networking disabled and records image size. It does not push an image or
establish OS vulnerability coverage.

## Disposable PostgreSQL checks

For `scripts/ci/staging.py`, use a PostgreSQL 15+ server listening on loopback (the CI
service is pinned to 17.11), an empty database named `dex_ci_*`, and an explicit port.
For example, after creating that disposable database:

```sh
export DEX_CI_DATABASE_URL="postgresql://localhost:5433/dex_ci_local"
uv run --no-sync python scripts/ci/staging.py --database-url "$DEX_CI_DATABASE_URL" --output reports/ci/staging/report.json
```

The helper rejects a populated destination, creates only synthetic source state, checks
copied migration and account boundaries, and refuses repeated migration. It scrubs
provider/connection overrides. The caller must tear down its disposable server; Actions
manages its ephemeral service container. Never pass a personal or production database
URL. Real proxy/TLS deployment needs separate configuration; see
[operations](operations.md#optional-postgresqlhttps-profile).
