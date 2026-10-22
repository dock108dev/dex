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
| `assurance.yml / ci` | Shared validation with optional compatibility matrix | Sunday 09:23 UTC; manual `full` or `compatibility` |
| `assurance.yml / container` | Non-publishing image build and non-root installed imports without networking | Schedule or manual `compatibility` |
| `assurance.yml / health` | Bounded Actions history and storage metadata | Schedule or manual; advisory collection |

Normal behavior entries use Ubuntu 24.04 and macOS 15 with Python 3.14. Compatibility
adds Ubuntu Python 3.13 and both OSes on Python 3.12. Every PR also installs and
compiles the fresh package on the declared minimum Python 3.12. Other jobs use
Ubuntu and Python 3.14, with Node 24 where needed. Matrix fail-fast is disabled.
Behavior has a 30-minute limit, or 45 minutes on the minimum runtime; pytest prints
slow-test timings and diagnostic stacks after a 90-second stall without terminating
the test. Package inputs and tool versions are defined by the workflows, composite
setup action, `pyproject.toml` and `uv.lock`.

Manual `full` runs normal validation, without the additional runtimes or image.
Schedules use default-branch source and may be delayed or dropped. They do not
qualify another PR. There are no path filters that can strand the required check.
PRs validate the proposed merge; main runs validate merged state. Superseded PR
runs cancel; main/scheduled runs do not cancel unrelated work. Merge queues are
not configured by these workflows; add `merge_group` before requiring queue gates.

## Local checks

Install only the extras needed for the work. Basic development uses `dev`; socket
guards, coverage, browser and security tools also require `ci`:

```sh
uv sync --locked --extra dev --extra ci
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

The aggregate expects seven job reports, or ten for compatibility. It rejects
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
