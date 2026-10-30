# Continuous integration and testing

CI checks source quality, behavior, packaging, browser journeys, security and
PostgreSQL integration using disposable state and controlled providers. It does
not validate personal collections, live marketplace results or a hosted deployment.

## Workflows

| Workflow / job | Responsibility | Trigger |
| --- | --- | --- |
| `tests.yml` → `validate.yml` | Shared validation and required aggregate | Pull request and push to `main` |
| `validate.yml / quality` | actionlint, Ruff, compilation, shipped JS/docs and renderer contracts | Shared validation |
| `validate.yml / behavior` | Full pytest, socket guard, JUnit and line/branch coverage | Shared validation |
| `validate.yml / distribution` | Repeat builds, wheel-from-sdist equality, empty hash-locked install and smoke checks | Shared validation |
| `validate.yml / browser` | Public/member, collection, Shopping and listing-review journeys | Shared validation |
| `validate.yml / security` | Gitleaks, Bandit, locked dependency audit and license metadata | Shared validation |
| `validate.yml / staging` | Disposable PostgreSQL migration, sessions, CSRF and transactions | Shared validation |
| `validate.yml / gate` | Required native report and job-result aggregation | Always after the validation jobs |
| `assurance.yml / ci` | Shared validation; compatibility additionally selects the separate container job | Sunday 09:23 UTC; manual `full` or `compatibility` |
| `assurance.yml / container` | Non-publishing image build and non-root installed imports without networking | Schedule or manual `compatibility` |
| `assurance.yml / health` | Bounded Actions history and storage metadata | Schedule or manual; advisory collection |

Normal hosted behavior uses Ubuntu 24.04 with Python 3.14. Compatibility
adds the Linux container build, not obsolete Python versions. Every PR also installs
and compiles the fresh package on the declared Python 3.14 runtime. Other jobs use
Ubuntu and Python 3.14, with Node 24 where needed. Matrix fail-fast is disabled.
Behavior has a 45-minute limit on every runtime; pytest prints
slow-test timings and diagnostic stacks after a 90-second stall without terminating
the test. Package inputs and tool versions are defined by the workflows, composite
setup action, `pyproject.toml` and `uv.lock`.

Manual `full` runs normal validation, without the additional image.
Schedules use default-branch source and may be delayed or dropped. They do not
qualify another PR. There are no path filters that can strand the required check.
PRs validate the proposed merge; main runs validate merged state. Superseded PR
runs cancel; main/scheduled runs do not cancel unrelated work. Merge queues are
not configured by these workflows; add `merge_group` before requiring queue gates.

## Platform coverage

Hosted checks use Ubuntu 24.04 and Python 3.14. macOS is supported locally;
validate platform-sensitive changes there with the same locked dependencies and
disposable test state. Local results do not substitute for hosted checks, and
engineering tests do not establish behavior of a separately installed runtime.

Manual `performance-diagnostic` runs profiling and representative budget suites;
`native-diagnostic` runs bounded GDB controls and the full suite. Both emit summaries
and preserve failed or missing results as failures. Neither replaces normal validation.

## Local checks

Install only the extras needed for the work. Basic development uses `dev`; socket
guards, coverage, browser and security tools also require `ci`:

```sh
uv sync --locked --extra dev --extra ci
npm ci --ignore-scripts --no-audit --no-fund
uv run --no-sync playwright install chromium
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync python -m compileall -q src scripts
uv run --no-sync python scripts/ci/source.py
uv run --no-sync pytest -q --disable-socket --allow-unix-socket
```

For a small change, select the relevant test files instead of running the full suite.
`source.py` checks shipped JavaScript syntax and maintained Markdown links, including
section anchors. Generated reports cannot satisfy a required documentation link.
The renderer contracts also run independently:

```sh
node scripts/verify_cx05_races.js
node scripts/verify_cx06_races.js
node scripts/verify_cx06_source_tools.js
node scripts/verify_photo_client.js
node scripts/verify_hunter_net.cjs
```

These stable script names test current request authority, stale responses and
recovery. They do not select historical product modes. Synthetic account fixtures
use a test-only fast password hasher; production hashing has a dedicated check and
installed smoke uses the actual default.

## Browser, package and service checks

Inspect arguments and side effects before running integration tools:

```sh
uv run --no-sync playwright install chromium
uv run --no-sync python scripts/ci/browser.py --help
uv run --no-sync python scripts/ci/smoke.py --help
uv run --no-sync python scripts/ci/staging.py --help
```

Browser checks create a fresh synthetic root, block acquisition and cover keyboard,
narrow-screen, enlarged-text, named Search/More/Stop, seller-link and review behavior.
Failures retain the failing stage, traceback and completed checks. The separate
Hunter runner `scripts/qualify_hunter_ui.py` owns disposable process setup while
`hunter_ui_journey.py` owns its ordered browser interactions.

Distribution checks validate required files, reject private inputs, compare repeated
wheels and the wheel rebuilt from the sdist, then install locked runtime dependencies
in an empty environment. Installed compilation, imports, console entrypoints,
synthetic initialization, loopback HTTP behavior and cleanup must succeed.

PostgreSQL checks require an empty disposable database and generated synthetic source.
They verify copied migration, account isolation, sessions, CSRF, idempotent confirmation,
undo and occupied-destination refusal. Never point these tools at a personal or
production installation. Container checks do not publish, sign or deploy anything.

## Reports and failure policy

JUnit, coverage, sanitized security findings and tool measurements feed versioned
JSON records and native GitHub job summaries. Records include the tested merge SHA,
PR head, ref/event, run/attempt, runtime, tool versions and actual outcomes. Missing
values stay unavailable; a previous successful run does not qualify changed source.

The hosted aggregate expects six job reports. The compatibility container reports
separately and must succeed for its assurance workflow to pass. It rejects
missing, duplicate, malformed, stale or contradictory evidence, unexpected skips
and cancellations. Every discovered `tests/test_*.py` module must execute; zero-test
or all-skipped modules cannot pass. A retained PASS cannot override failed tests,
blocking findings or a failed measurement. Use **Re-run all jobs** for a new attempt;
reports from earlier attempts are deliberately rejected.

Artifacts have unique run/attempt/matrix names. Quality, behavior, distribution,
security and container reports retain 14 days; browser captures retain seven days;
health records retain 30. Contributor text is escaped, bounded artifacts are parsed
as data, and no artifact is executed to render a report. Credentials, personal state
and unnecessary source archives are excluded.

Security blocks every secret and dependency advisory, plus medium/high Bandit
findings with high confidence. Other findings remain visible. Tool, download or
advisory-service failures cannot become zero findings. pip-audit sends package
names/versions to PyPI's advisory service; the other local checks need no external
analysis account. License metadata is an inventory, not a legal approval.

Health collection samples at most 30 completed runs from 30 days and separates
PR/main and workflow groups. Cancelled first attempts stay outside the pass-rate
denominator. Rerun recovery alone is not a flake diagnosis. Median requires five
comparable observations and p95 twenty. Job-time sums are resources, not elapsed
run time or billed minutes. Queue, critical path, billing and per-run storage may
remain unavailable. An incomplete artifact listing cannot establish total storage.
Telemetry failure does not erase or block independent correctness results.

## Permissions and repository enforcement

External actions and downloaded tools are pinned; dependency installation is locked.
Jobs use read-only contents access, disable persisted checkout credentials and do
not inherit application secrets. Health additionally reads Actions metadata.
Correctness does not depend on a warm cache. Cache keys include the lockfile,
platform/architecture and runtime, and PR cache scope is separate from trusted branches.
There is no privileged `pull_request_target`, artifact-executing `workflow_run` chain,
or self-hosted PR runner.

Workflow configuration alone does not enforce branch protection. Administrators
can require the observed `CI / Required checks` check on `main` after a complete
successful run. Repository settings, service activation and release operations
remain separate administrative actions. No additional coverage dashboard or
hosted analysis service is required by the current workflows.

## Limits

Local checks qualify only the exercised environment. Synthetic tests do not prove
provider access, recognition accuracy, current prices or production behavior.
Full static typing, JS line coverage, changed-code coverage and comparable performance
trend budgets are not established gates. Package/image sizes are advisory without
an arbitrary budget. Windows launcher support, hosted Linux ARM, container OS
vulnerability scanning, TLS/proxy qualification, signing and publication are outside
these checks. JavaScript, CSS and templates ship in the Python wheel; there is no
independent frontend bundle or generated-source regeneration step.


## Browsing performance qualification

Measure startup, restart navigation and warm interactions separately. Use at least
20 comparable samples for p95, include worst cases, and retain fixed full-size and
2× test datasets. Account isolation, exact counts, unknown quantities, archived
ownership, revision invalidation, interruption and recovery must remain correct.
Use disposable fixtures and blocked providers; do not benchmark by reducing the
real catalog or moving request work into unmeasured startup. Performance suites
are in `tests/test_catalog_read_performance.py`, `tests/test_account_read_performance.py`
and `tests/test_perf04_*.py`. Their filenames are stable test entry points.

## Performance budgets

These are fixed implementation budgets, not passing measurements. Qualify on the
full existing catalog and machine, plus isolated full-size and 2× scale regression
cases. Do not raise the budgets to match optimized results. Milliseconds below are
p95 with at least 20 comparable samples; record worst case and all failures too.
Startup/repair with fewer samples reports every observation without a percentile.

| Boundary | Budget | Rationale / accounting |
| --- | ---: | --- |
| Spawn to browsing-ready with valid prepared state | 2,000 ms | Bounded import/manifest checks; no hidden full rebuild |
| First usable cards after restart navigation | 1,000 ms | Existing accepted product target, including cold client assets and correct primary actions |
| Ordinary search/filter/page/detail action to usable result | 300 ms | Existing accepted target; includes debounce, request, parse and render |
| Ordinary local API including authorization and serialization | 180 ms | Leaves 120 ms for dispatch, local transfer and client work |
| SQL execute plus fetch per ordinary API | 40 ms, at most 20 queries | Includes both authorization checks and exact counts; no N+1 per tile |
| Decoding/ownership composition per ordinary API | 80 ms | Typed shared rows plus selected account overlay; no full catalog or journal decoding |
| Serialization/adapter/other server work | 60 ms | Completes the 180 ms server allocation |
| Client scheduling/debounce plus loopback transfer | 50 ms | Avoid artificial long search delays and waterfalls |
| JSON parse, DOM update and next paint | 70 ms | Completes 300 ms action budget; correct text/actions, not skeleton only |
| Default page/detail primary JSON, uncompressed | 128 KiB | Bounds parse/transfer; child/history/evidence overflow is separately paged |
| Context or filter-options page JSON | 32 KiB | No all-copy bootstrap; complete options via explicit continuation |
| First navigation total local HTML/CSS/JS/primary JSON | 512 KiB | Allows current assets with bounded primary data; excludes remote art |
| Expanded groups per API | 100 maximum | Page cap; SQL membership/count work stays in indexed typed rows |
| Full catalog preparation, explicit maintenance | 30,000 ms | Separate measured repair/publication task, never concealed in startup or GET |
| Incremental account overlay preparation for ordinary edit | 200 ms | Affected identities only; imports/source replacement separately measured |
| Invalid/missing state recognition at startup | 2,000 ms | Fail observably within startup budget; no stale success |

Measure SQLite VM work/query plans and rows fetched as well as query count. Reject
ordinary reads that fetch/decode all printings or replay all operations, even with
few queries. Exact counts may traverse compact posting IDs inside SQL; no claim
of constant-time arbitrary search is implied. Require the time/scale gates for
common-character queries, variant combinations and deep pages. If those fail,
optimize indexes/materialized counts before broadening the accepted scope.

Remote art is not on the primary critical path. Report first visible art, failures
and completed/failed image counts separately; reserve layout dimensions. The 1-second
restart-navigation target is separate from the 2-second startup target: do not add
the latter to the former and call a 3-second navigation a pass.
