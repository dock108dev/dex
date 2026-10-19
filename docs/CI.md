# Continuous integration and testing

CI checks source quality, behavior, distribution, browser journeys, security and
PostgreSQL integration. It uses disposable state and controlled providers; it does
not validate a user's collection, live marketplace results or a hosted deployment.

## Workflows

| Workflow / job | Responsibility | Trigger |
| --- | --- | --- |
| `tests.yml` → `validate.yml` | Required validation and aggregate | Pull request, push to `main` |
| `validate.yml` / `quality` | actionlint, Ruff, compilation, shipped JS/docs and renderer contracts | Reusable validation |
| `validate.yml` / `behavior` | Full pytest, socket guard, JUnit and line/branch coverage | Reusable validation |
| `validate.yml` / `distribution` | Repeat builds, wheel-from-sdist comparison, fresh hash-locked installation and smoke checks | Reusable validation |
| `validate.yml` / `browser` | Public/member journeys, narrow/enlarged layouts, keyboard and recovery | Reusable validation |
| `validate.yml` / `security` | Gitleaks CLI, Bandit and locked dependency audit | Reusable validation |
| `validate.yml` / `staging` | Disposable PostgreSQL migration, sessions, CSRF and transaction checks | Reusable validation |
| `validate.yml` / `gate` | Required same-run result/report aggregation | After validation jobs, including failures |
| `assurance.yml` | Validation plus compatibility runtimes, image build and bounded health metadata | Sunday 09:23 UTC; manual `full` or `compatibility` |

Normal behavior entries are Ubuntu 24.04 and macOS 15, both using Python 3.14.
Compatibility adds Ubuntu Python 3.13. Matrix fail-fast is disabled. Other required
jobs use Ubuntu Python 3.14 and Node 24 where needed. Python 3.12 remains the
declared package minimum but is no longer exercised in CI.
Behavior has a 30-minute job limit; pytest reports slow tests and emits diagnostic
stacks after a 90-second stall. The diagnostic does not terminate the test.

The scheduled image build checks non-root imports with networking disabled and
never publishes an image. Manual `full` intentionally omits the image and additional
runtime combinations. Health telemetry is advisory and samples at most 30 completed
runs from 30 days, separating event/workflow groups. It does not infer flakiness
from one failed run or claim a missing measurement is zero.

## Local checks

For focused development, install the `dev` extra and select relevant tests. For
socket guards, coverage, browser and scan tooling, also install `ci`:

```sh
uv sync --locked --extra dev --extra ci
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync python -m compileall -q src scripts
uv run --no-sync python scripts/ci/source.py
uv run --no-sync pytest -q --disable-socket --allow-unix-socket
```

Use Node 24 (`.nvmrc`) for the maintained renderer contracts:

```sh
node scripts/verify_cx05_races.js
node scripts/verify_cx06_races.js
node scripts/verify_cx06_source_tools.js
```

Names in these script paths are stable entry points. They test current authority,
stale-response and recovery behavior, rather than defining separate product modes.

`scripts/ci/source.py` validates shipped JavaScript and maintained Markdown links,
including section fragments. Generated `reports/` must not satisfy portable guide
links. Keep private installation paths and local working notes out of maintained
docs. `tests/test_ci_source.py` covers missing, generated and malformed references.

Synthetic account fixtures temporarily use a fast test hasher. A dedicated test
checks Django's production PBKDF2 default, and installed smoke uses real hashing.
No product configuration enables the test hasher. Tests must still enforce account,
CSRF, session and mutation boundaries.

## Browser and service checks

Install the locked Playwright browser when a browser check is needed:

```sh
uv run --no-sync playwright install chromium
uv run --no-sync python scripts/ci/browser.py --help
uv run --no-sync python scripts/ci/staging.py --help
uv run --no-sync python scripts/ci/smoke.py --help
```

Inspect arguments and side effects before launching these tools. Browser checks
create synthetic private state and block provider operations. PostgreSQL checks
require a disposable service and empty destination. Distribution checks install a
built wheel in a separate runtime, verify package inputs and run against generated
state. Never point engineering harnesses at a personal installation.

The Hunter-specific runner `scripts/qualify_hunter_ui.py` also creates disposable
state. It separates process ownership from `hunter_ui_journey.py` and hashes both
files. Controlled responses test races and image availability without establishing
real provider behavior. Its guard/unit tests do not require a full browser run.

## Reports and permissions

Actions are pinned to full commit hashes; setup uses locked dependencies. Jobs use
read-only contents permission, disable persisted checkout credentials and do not
inherit secrets. Health additionally reads Actions metadata. PR runs superseded by
new work may cancel; main/scheduled runs preserve their configured concurrency rules.

Native JUnit, coverage, security and measurement reports feed job summaries and
sanitized artifacts. Names include run, attempt and matrix identity; workflow files
set explicit retention. Contributors' text is escaped and artifact contents are
parsed as bounded data, never executed to render a report. Do not retain credentials,
private state, unnecessary source archives or bulky routine recordings.

The aggregate requires seven native job reports, or eight for compatibility. It
rejects missing, duplicate, malformed, stale or contradictory reports, unexpected
skips and cancelled required jobs. Expected test modules must execute; all-skipped
modules fail. A report's PASS cannot override failed native tests or scan findings.
Use **Re-run all jobs** so every accepted artifact belongs to the same run attempt;
rerunning only failed jobs leaves earlier successful artifacts outside that boundary.

Security blocks every dependency advisory and secret finding, plus medium/high
Bandit findings with high confidence. Other Bandit findings remain visible. Tool,
network lookup and download failures cannot become zero findings. Gitleaks is the
pinned CLI, not a separate hosted wrapper integration. pip-audit sends dependency
names/versions to PyPI's advisory service; coverage and static analysis need no
new external account. See workflow files and `scripts/ci/security.py` for pins.

## Required-check enforcement

Workflow configuration does not itself enforce branch protection. Repository
administrators can require `CI / Required checks` after observing the check name
on a complete run. A merge queue needs the corresponding event before activation.
No release, signing or publication workflow is provided.

## Limits

Local execution qualifies only the exercised environment. An older run does not
qualify changed source, and a synthetic test does not establish provider access,
recognition accuracy, price freshness or owner acceptance. Full static typing,
JavaScript line coverage and comparable changed-code/performance trend budgets
are not established gates. Native measurements remain visible without invented
baselines or deltas. See [development](local-development.md#testing).

## CI maintenance review — October 17, 2026

Imported from the Desktop tracker during the October 18 documentation cleanup.
This is a historical closeout/decision, not a fresh verification. The active
Shopping repair in [Shopping](hunts.md#active-owner-direction--shopping-repair-first-october-18-2026)
and the Desktop Next Steps plan govern current work. Historical next actions below
do not reactivate deferred work or establish installed delivery.

Local CI maintenance is complete: repaired the hosted PTY descriptor-limit and
retired Shopping-navigation failures, valid-local-ingress transport setup and
catalog replacement-guard query budgets. Added test-only fast fixture hashing
with explicit production-KDF verification, stall/slow-test diagnostics, explicit
Bash execution, portable maintained documentation checks and bounded sdist roots
with an explicit wheel-from-sdist identity comparison. Existing required names,
security policy, platform coverage and reporting identity gates remain.

**3,324 full-suite tests passed, no skips, in 323.35 seconds**; coverage is
87.564% lines / 79.192% branches. Workflow/source/clean-export checks, native
reporting contracts, 68 renderer cases, repeat builds, fresh Python 3.12 install
(43 HTTP assertions), Chromium (51 states / 21 checks), PostgreSQL 17.11
(5 integration checks) and security scans passed. Gitleaks/pip-audit found zero;
Bandit found 72 nonblocking and zero blocking findings. Native warnings and
initial failures/interruption remain retained; no comparable trend baseline or
flake diagnosis is claimed. Disposable PostgreSQL was removed.

[CI guide and full check map](CI.md#ci-maintenance-review--october-17-2026)
records responsibilities, exact candidate/evidence limits, native reports,
service eligibility and bounded historical health. Local evidence is under
`dex/reports/ci-review-20261017/`. The pass began at `d144265`; independent commits
advanced the checkout to `92b9f8b`, followed by local test/document repairs.
No commit, push, workflow dispatch, branch setting, integration activation,
provider operation, customer installation or owner data change was made by this
pass. Customer beta priorities and deferred scope remain unchanged.

**Status: LOCALLY READY — HOSTED UNVERIFIED.** Next CI action, when publication is
requested: publish the reviewed final candidate and inspect all required checks
on its exact SHA/run/attempt. Final hosted Linux/macOS matrix/summary rendering
and the scheduled application-container build remain unverified. Branch protection
was observed absent; enforcement of `CI / Required checks` is recommended after
that exact candidate passes, and was not applied. This is engineering validation,
not customer acceptance or a release.
