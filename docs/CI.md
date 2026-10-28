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


## Available verification and remaining boundaries

The October 27 local CI review passed 3,526 locked-environment tests, 51 browser
states plus 33 journey checks, security, reproducible package installation,
PostgreSQL and a Linux ARM container. The later journal extraction/test split
passed 164 focused tests, 34 package-guard tests and 25 recognition tests, retaining
all 46 original test functions. Documentation/link and syntax checks also passed.
These local records cover their recorded source versions, not every later commit
or installed runtime. Evidence is local-only in `reports/ci-review-20261027/`
and `reports/repository-cleanup-20261027/`. The shared policies, journal boundaries
and test organization are described in [architecture](SSOT.md) and
[maintenance conventions](local-development.md#maintenance-conventions).

At the October 27 reconciliation, HEAD was `61e9f0a7228b3632a7f9f352f095d01658c2f1f1`.
[Tests](https://github.com/dock108dev/dex/actions/runs/40571257581) and
[CodeQL](https://github.com/dock108dev/dex/actions/runs/40571257148) were inspected.
CodeQL passed; Tests failed in Ubuntu Python 3.14 behavior and the required
aggregate. The reported discovery deadline test assumed dispatch would start
within a 50 ms wall-clock window. Its local repair advances a controlled clock
only after dispatch and checks both timeout limits, cancellation and consumed
attempt accounting. Production deadlines are unchanged. The repair was committed in
`1b63f95b7415bc521b9163a48f1ebae6066c6538`; the later documentation inspection
confirmed a clean checkout at that commit before edits. A newer hosted result was
not inspected, so the old failure is historical evidence, not the status of this head.
The repair still needs an attributable exact-candidate hosted result. Complete normal and compatibility results must
be attributed to the chosen source/package candidate. Prior passing `3cd1eb2`
results do not establish that candidate's result. Documentation edits made during
reconciliation are not included in those already-running checks.

An earlier tracker referenced an absent `reports/repository-cleanup-20261021/`
folder. Its historical test-count/preservation claims remain unverified and are
not needed to reconstruct current source. Use current candidate checks; do not
reopen completed implementation merely to recreate a missing historical report.


## Browsing performance qualification

The next-version responsiveness targets in [interface design](UI_DESIGN.md#next-version-responsiveness-contract)
are required acceptance criteria, not existing passing CI gates. The initial
[installed observations](card-groups.md#october-27-browsing-diagnosis) are not a benchmark.

Record exact source, installed package, dependency/runtime versions, machine,
browser, catalog size/revision, account scope and startup conditions. Separate browser
reload, server restart with existing derived state, warm navigation and deliberate
derived-state rebuild. Measure startup-to-ready, document/API time, query count/time,
projection CPU, payload bytes, image time and time to usable results. Include guest
and authenticated catalog, owned cards, species, filters, paging and detail, plus
simultaneous reads and a collection change. Collect at least 20 samples per reported
scenario for p95; keep individual failures and worst-case results visible. Gate p95
against the one-second/300-ms targets, and report cold launches separately. Freeze
numeric startup, payload and query-work budgets during baseline design rather than
selecting thresholds after seeing the optimized result.

Automated regression fixtures belong only in engineering tests. Use representative
full-size catalogs and additional scale cases to catch whole-catalog work hidden
behind small responses. Verify identity, counts, complete filters, archived ownership,
unresolved evidence, publication changes, source replacement, edit/Undo, revocation,
account isolation and late-response handling. Exercise cache/index invalidation,
interrupted rebuild, missing/corrupt derived state and concurrent update/read behavior.
No provider operations are needed for these tests.

Final customer-facing qualification uses the existing installation and ordinary login,
with no synthetic substitute. Keep private benchmark details outside Git; repository
evidence contains sanitized aggregates, identities and limits. Test any mutation or
failure injection in isolation first; actual customer changes require selected intended
actions. A budget miss, missing measurement or unexplained correctness difference
keeps the affected slice open. Exact-candidate CI, installed behavior and owner
acceptance remain separate statuses.

## PERF-01 performance budgets

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

## PERF-01 baseline evidence

The baseline investigation uses the actual customer installation, not fixture data.
Source inspected: `1b63f95b7415bc521b9163a48f1ebae6066c6538` with pre-existing
uncommitted documentation edits preserved. The selected installed distribution is
`pokemon-hunter 0.1.0`, runtime `hunter-poc-20261027`, Python 3.12.15, macOS 27.0.1
arm64, Mac15,6 with 18 GiB memory and 11 logical CPUs. HTTP/render probes used
the in-app browser reporting Chrome 156.0.0.0; the independent guest visual check
used Safari 27.0.1 private browsing. The listener was verified against its interpreter, root and open database.
The actual catalog contains 33,083 printings in 187 sets and produces 19,011 public
display groups. Package version alone does not identify code: 30 beta source/asset
files differ from the checkout. The measured card/group/catalog/effective-collection
modules and card/species assets match; installed Shopping/photo code must be reconciled
before a cumulative runtime delivery.

Raw measurements, diagnostic scripts, package comparison and query plans remain
in the ignored private `.local/perf-01/` directory. No credentials or response record
contents are logged. The browser uses its existing authenticated session; no session
extraction or fabricated principal is used. Public profiling runs the installed
package against the existing database with SQLite `query_only` enabled, without
launching workers or replacing the server. Profiled times include profiler overhead
and must not be pooled with HTTP latency measurements.

The initial authenticated page observation had context 8.7 ms/22,233 bytes, filters
11,188.7 ms/1,398 bytes and owned cards 12,293.7 ms/64,240 bytes. These are individual
resource timings, not percentiles or proof of rendering completion. Eight observed
remote art requests had zero observable decoded bytes; their 2.6–3.3 ms resource
entries do not prove successful image delivery. Primary requests were already slow
before artwork started. The existing UI waits for both list and filter responses.

Three instrumented public projection samples took 1,858–2,046 ms. Each made three
queries and materialized the full printing catalog. SQLite's plan scans printings,
looks up each set by primary key and uses a temporary B-tree for ordering. SQL
execute was 67–88 ms; measured `fetchall` was 80–102 ms. Group construction took
599–770 ms, alias inventory 346–442 ms and JSON decoding 295–325 ms (132,332 loads).
These cumulative phase times overlap and must not be summed. This is strong evidence
of repeated decoding/grouping/alias work, not evidence that adding one SQL index
will fix the screen. The profiler ran during early browser sampling; those overlapping
observations must be labelled diagnostic contention rather than controlled serial runs.

Private source inspection shows three catalog loads in each group projection:
archived input, an authoritative reread inside `effective_collection.project`, and
published input. Effective projection also reloads active copies and reads operation
history. Filter and list requests each perform this work; species screens request
both identity and groups. Private ownership CPU attribution remains separate from
the measured public cProfile phases. A native server stack sample can show Python,
SQLite and waiting threads but does not identify Python ownership functions reliably.
No causal claim about recognition-worker contention follows from that sample.

Canonical detail has an additional source-confirmed waterfall: `card_group_views.home`
assembles detail before returning HTML, then `card-screens.js` fetches the detail API
again. PERF-04 must remove redundant full detail work while retaining HTML route,
return-target and selected-child authorization. The initial shell itself is therefore
not necessarily cheap. Full-catalog consumer migration is inventoried in
[card groups](card-groups.md#consumer-migration-inventory).

### Repeated ordinary-runtime HTTP results

Each scenario has 20 clean serial browser-fetch samples, measured from fetch dispatch
through complete response bytes, without JSON parsing or rendering. Member sampling
uses the existing signed-in session; guest sampling omits credentials. Nine member
paths ran in fixed round order, then eight guest paths, then two replacement member
rounds. The first two member rounds are retained privately but excluded because they
overlapped exploratory diagnostics. Thus 358 raw samples were retained: 340 selected
for the table and 18 exploratory. All returned HTTP 200. The initial unretained probe
had a browser-tool timeout; it is not treated as an HTTP failure or percentile sample.

Nearest-rank p95 is sorted sample 19 of 20; median is the middle-pair average. These
are small local samples, not population confidence bounds, and the user's other
host activity was not controlled. No API sample establishes usable-screen latency.
Search uses `pikachu`, page uses page 2, private species uses #25, guest filter uses
English, and detail uses a published canonical Base Set group. Default page size
is 40. Guest Pokédex/species rows measure rendered HTML response transfer, not paint.

| Scenario | n | Median ms | p95 ms | Worst ms | Response bytes | HTTP failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| owned | 20 | 3658.5 | 4229.6 | 4235.9 | 64240 | 0 |
| filters | 20 | 3788.2 | 4390.3 | 4406.7 | 1398 | 0 |
| context | 20 | 4.4 | 6.2 | 10.9 | 22233 | 0 |
| library | 20 | 3774.1 | 4175.6 | 4240 | 64413 | 0 |
| search | 20 | 3812.8 | 4271.3 | 5346.2 | 66927 | 0 |
| page | 20 | 3810.1 | 4322 | 4351.6 | 64396 | 0 |
| species | 20 | 3757.3 | 3931.1 | 3957.2 | 77789 | 0 |
| pokedex | 20 | 3364.9 | 3543.2 | 3953.6 | 229152 | 0 |
| detail | 20 | 4204.8 | 4515.3 | 4538.3 | 3434 | 0 |
| guest_catalog | 20 | 947.0 | 1049.9 | 1427.2 | 19711673 | 0 |
| guest_groups | 20 | 1127.0 | 1254.6 | 1520 | 28585 | 0 |
| guest_search | 20 | 1065.3 | 1143.7 | 1317.4 | 31137 | 0 |
| guest_filter | 20 | 1098.0 | 1289.7 | 1460.8 | 28585 | 0 |
| guest_page | 20 | 1129.0 | 1280.6 | 1355.4 | 28582 | 0 |
| guest_detail | 20 | 1402.0 | 1509.2 | 1537 | 1405 | 0 |
| guest_pokedex | 20 | 896.0 | 999.1 | 1041.2 | 124684 | 0 |
| guest_species | 20 | 928.1 | 996.4 | 1030.2 | 191317 | 0 |

The 1,398-byte filter response and 3,434-byte private detail still take seconds.
Their dominant delay is server work, not transfer volume. Public catalog transfer
is independently excessive at 19,711,673 bytes; guest grouping/detail remain slow
with much smaller responses. Account context is fast. These findings support a
shared catalog/read-model change across guest and member browsing, not an admin-only
patch or artwork-only optimization.

### Private server phase attribution

A temporary content-free wrapper launched the **same installed CLI/package/root**
for nine diagnostic requests through the ordinary authenticated browser session.
It timed existing functions and cursor execution; it added no endpoint, skipped no
authorization, and wrote no application source/configuration/data. The ordinary
CLI launch was restored before the restart/navigation samples below. Instrumented
samples are not pooled with normal-runtime timings. Three samples per route are
ranges, never percentiles. Nested phases overlap.

| Phase | My Cards, ms | Owned filters, ms | Detail, ms |
| --- | ---: | ---: | ---: |
| View total | 3,845–4,290 | 4,003–4,208 | 4,215–4,488 |
| Group projection, inclusive | 3,796–4,242 | 3,954–4,164 | 3,748–4,022 |
| Effective ownership, inclusive | 2,123–2,374 | 2,182–2,469 | 2,123–2,416 |
| Three catalog reads/decodes combined | 1,200–1,427 | 1,260–1,362 | 1,157–1,226 |
| SQL execute | 208–272 | 218–295 | 323–378 |
| Store rows: execute/fetch/dict materialization | 566–719 | 591–691 | 724–837 |
| JSON decode | 408–579 | 448–501 | 599–733 |
| Alias inventory | 375–387 | 357–370 | 330–370 |
| Group builds | 202–336 | 194–235 | 194–359 |
| JSON encode | 78–170 | 155–283 | 62–266 |

My Cards executed 29 SQL calls, filters 30 and detail 45. Each decoded approximately
331,300 JSON values. My Cards made 41 group-build calls (main projection plus page
artwork validation); filters made one and detail two. Removing image requests alone
would leave the expensive whole-catalog and effective-ownership work intact. The
wrapper measures inclusive function elapsed time, not exclusive CPU; ownership
includes one of the three catalog loads. Native sampling showed waiting threads
but did not establish a causal worker-contention fault. No active recognition jobs
were present and no acquisition/recognition action was performed.

### Controlled restart and browser reload

The owner confirmed there was no unfinished temporary Shopping work to preserve.
Before each restart, read-only checks found no queued/processing scan or batch stage.
The same root/interpreter/package was stopped gracefully and started normally;
no migrations, replacements, reseeding or configuration edits occurred. Three
ordinary starts listened after **373.2, 373.5 and 375.0 ms**. TCP polling did not
warm any application endpoint. Listening is not an application-readiness measurement:
the current app has no derived-index readiness signal.

| My Cards condition | n | Individual usable-result times, ms | Worst, ms |
| --- | ---: | --- | ---: |
| First navigation after server restart | 3 | 8,001.5; 8,177.6; 8,845.2 | 8,845.2 |
| Following warm browser reload | 3 | 7,513.4; 7,983.9; 8,462.5 | 8,462.5 |

Usability probe: observe the real card list, then two animation frames; the observer
attached 48–170 ms after navigation and before API completion. Forty card tiles were
present. Eight visible images were successfully loaded at readiness; 32 lazy images
were still incomplete. The interval from the final API response end to this marker
was 14.4–26.1 ms, including polling and frame scheduling. It is not an isolated DOM
CPU measurement, and it does not establish an artwork-network percentile.

On the first warm reload, cards arrived at 5,222.5 ms but filter options arrived at
7,494.7 ms; `Promise.all` withheld cards for approximately 2,272 ms. Both calls redo
projection independently and overlap in the same process. Serial API timings and
paired screen timings must not be pooled. The repeatable seconds-long warm delay
shows a general read-path problem; a special restart-only defect is not established.
There is no persistent derived browsing representation in this installed version,
so a distinct derived-state rebuild benchmark is not applicable yet. PERF-02 must
measure preparation separately against its fixed budget.

Three separate ordinary starts followed by a first **guest group API** read returned
HTTP 200 in 1,067.4, 1,034.8 and 1,048.7 ms (28,585 bytes each). Their listener times
were 422.5, 264.2 and 266.4 ms. These are response-completion samples, not guest paint
measurements or percentiles. Guest Pokédex and Pikachu were also visibly checked in
a separate Safari private window: signed-out navigation and published metadata were
present; species artwork was explicitly unavailable. The temporary window was closed.

Additional actual member navigation probes: Library search 8,030.3 ms (n=1), followed
by search-page reloads 8,046.5 and 7,453.4 ms (n=2); English filter 8,063.6 ms (n=1);
page 2 7,618.8 ms (n=1); canonical detail 7,520.3 ms (n=1); Pokédex 3,112.7 ms (n=1);
species #25 7,898.3 ms (n=1). Do not pool navigation and reload into a percentile.
Detail HTML itself finished at 3,825.8 ms, followed by a 3,620.6-ms detail API call,
confirming the duplicate waterfall. Pokédex's final-response-to-marker interval
was 98.1 ms; species was 14.5 ms. Client rendering can matter on the larger species
list, but it does not explain multi-second server delays.

### Baseline closeout and verification limits

PERF-01 establishes the full-catalog baseline, attributes the dominant costs and
fixes the implementation contract. It does **not** qualify the product as responsive.
All selected API samples succeeded, but most substantially missed the new budgets.
The six ordinary restart checks preserved the installed package/root and ordinary
sign-in; the final server uses the original CLI command, without the phase wrapper.
No acquisition, recognition, collection mutation, schema migration or installation
update was performed. Private raw evidence is not part of the repository change.

Remaining verification belongs to the downstream slices and is explicit: current
readiness has no application-ready signal; derived-state preparation/recovery does
not exist yet; no installed mutation/fault-injection test was authorized; browser
paint/restart samples are too few for p95; guest paint and complete remote-art timing
are not quantified; host background activity was uncontrolled. QA-INTEGRATION must
collect the required 20-sample end-to-end scenarios on the delivered successor,
including actual control actions and Back, not substitute API p95 for usability.
Correctness/invalidation/fault tests use engineering isolation before delivery.

A special restart-only fault or recognition-worker contention was not established.
The measured warm reconstruction, duplicate projection and detail waterfall are
sufficient causes for the present delay; avoid guessing at a separate cold-start
cause. The design intentionally leaves no cache authority/invalidation decision to
implementation guesswork. PERF-02 is the next implementation slice; exact-candidate
CI, runtime dependency reconciliation, delivery and owner acceptance remain open.


## PERF-02 isolated qualification

PERF-02 adds shared SQLite catalog reads and public V2 adapters; this section records
source/engineering qualification only. It does not qualify the installed UI or the
customer installation. Account composition, browser adoption, readiness orchestration,
integrated hosted/compatibility checks, installation and owner acceptance remain
separate downstream work.

Reproduce in a disposable engineering root using the checkout's locked environment:

```sh
uv run --no-sync pytest -q tests/test_catalog_reads.py
uv run --no-sync pytest -q -s tests/test_catalog_read_performance.py --basetemp=/tmp/dex-perf02-qualification
```

Use a fresh dedicated temporary directory for each concurrent qualification attempt;
never point these tests at the customer root. The scale test creates 33,083 and
66,166 printings, a 187-set expansion, natural-sort/name ties, Unicode names, multiple
variants, an archived identity, an alias collision and unresolved metadata. It
checks 20 route/selector scenarios in two separately reported conditions: reused
SQLite connections and a new connection before every request. Each condition has
20 comparable samples; nearest-rank p95 is sample 19 of 20. This is 800 requests per
scale, with preparation/activation measured separately once per scale, not as a
percentile. Fresh connection does not mean a cold OS file cache or a server restart.

The scale test uses pytest-cov's `no_cover` marker so branch tracing does not enter
the wall-clock budgets when the full suite runs with coverage. It still executes
in the required Behavior job, with the same 30-second preparation limit and all
request, SQL, payload and decoding limits. `test_catalog_reads.py` remains covered
for functional correctness and integrity checks. Run timing qualification without
an external profiler as well; profiling is diagnostic, not comparable budget evidence.

Requests go through Django's test client, middleware and JSON serialization. Timing
includes connection setup; SQL instrumentation includes execution plus fetch/dict
materialization and transaction statements. SQL counts exclude separate EXPLAIN
queries. The first sample captures query plans, so its API time includes that extra
inspection; SQL/fetch timing excludes it. This conservative API worst sample is
retained. Rows fetched are rows returned to Python, not the number of compact index
entries SQLite visits. Expanded-row counts instrument the public payload decoder.
Exact broad counts, gram intersections and deep offsets can visit catalog-scale
compact indexes; no ordinary read reconstructs or decodes the complete catalog.

Generated evidence stays under ignored `reports/perf02/`: `scale-33083.json` and
`scale-66166.json` contain every timing, p95/worst, query count, fetched/expanded-row
count, payload byte count, query plans, builder digest and preparation phases. The
reports are regenerated evidence, not required checkout files or private customer
captures. The test enforces the unchanged budgets in the PERF-01 table, including
40 ms SQL p95, 20 queries, 180 ms API p95 and 30-second preparation.

### Development failures and resolved query paths

Initial per-gram/group rows made full-size preparation exceed 100 seconds. Compressed
FTS gram postings replaced those rows without changing substring semantics. Early
plans also scanned full child tables for paged lookup and materialized every broad
positive search match. Explicit membership/covering indexes and bounded positive
candidate pages replaced those paths. Mixed public/archived preparation initially
took 33–35 seconds at 2×; per-build reuse of typed metadata and encoded word terms
removed duplicate work. Broad variant/alternate-sort requests initially exceeded
the 40 ms SQL limit and were optimized without changing filters, counts or budgets.

One contended attempt observed host load averages above 170, preparation of 122.4
seconds and individual requests lasting seconds; its partial/full-size evidence is
retained as `contended-33083.json`, not counted as a passing run. A JavaScript syntax
check timed out during that contention and was rerun successfully. An experimental
FTS shadow-table trigger caused a native SQLite failure and was removed; supported
FTS operations, explicit integrity checks and repair now own that boundary. No
customer data or runtime was involved in these failures.

### Qualified final source results

The final local run passed both scale gates on macOS arm64, Python 3.14.0 and SQLite
3.50.4 with FTS5. The source base is `1b63f95b7415bc521b9163a48f1ebae6066c6538`
plus the uncommitted PERF-02 changes. The beta-source digest recorded in both final
manifests is `2ed05b9b3d99ff766b961274ee468f751ceab74190bde5a5137a003f220be271`.
These are local results; no hosted CI, package installation or owner acceptance is claimed.

| Printings / groups | Connection | Highest API p95, ms | Worst API, ms | Highest SQL p95, ms | Worst SQL, ms |
| --- | --- | ---: | ---: | ---: | ---: |
| 33,083 / 19,013 | Reused | 14.04 | 16.30 | 11.37 | 14.09 |
| 33,083 / 19,013 | Fresh | 13.67 | 18.71 | 11.11 | 14.02 |
| 66,166 / 38,024 | Reused | 24.21 | 25.26 | 22.10 | 23.29 |
| 66,166 / 38,024 | Fresh | 24.93 | 26.52 | 21.66 | 23.29 |

Explicit prepare **plus activation** took **11.29 seconds** at full size and
**24.70 seconds** at 2× (one measured build each; 30-second budget).
Across all scenarios: at most **13 SQL queries**, **108 rows returned to Python**
(including manifest/count/health rows), and **100 expanded result rows**. Maximum
primary payload was **69,380 bytes**, including the 100-result case; the default
page was **27,972 bytes**, detail **1,037 bytes**, and filter options **2,677 bytes**.
All final 1,600 responses succeeded and every fixed budget passed. Full-size and
2× reports each retain 40 independently measured conditions, rather than pooling
fast and slow routes into a single percentile.

Plans show compact covering/partial indexes for ordering, variants and species,
FTS posting intersections for search/counts, and indexed group/unresolved membership
before page metadata fetches. Exact counts can scan matching postings. Returned
metadata expansion stays bounded; the query/fetch figures alone are not the proof.

Correctness qualification passed **198 relevant regression tests**, covering the
existing public/group/catalog/publication/collection/declaration/pipeline behavior
and 20 new read-service tests. After the final unresolved-page index selection,
the 20 read-service tests and both scale gates passed again. Coverage includes V1
parity, literal dg1 identity, Unicode/substring and same-child semantics, natural
ordering and arbitrary deep pages, complete 206-option/207-variant resources,
oversized original-text downloads, alias collisions, archived/public conflicts,
publication/rollback and older raw SQLite writes, preview/confirm/Undo revisions,
WAL concurrency and active-reader reclamation, interrupted/stale activation,
missing/corrupt/incompatible state, optional-trigger repair, explicit schema/index
repair, public allowlists and unsupported-database rejection. The operator test
runs migrate/prepare/activate/status/discard against an existing engineering root
and proves that a missing root is rejected rather than initialized.

Final local checks passed: Ruff lint; format checks for 433 Python files; links and
anchors in 18 maintained documents; syntax for 29 shipped JavaScript files; and
`git diff --check`. PostgreSQL, other Python/OS combinations,
real HTTP/network overhead, server restart/readiness, installed browser latency and
owner acceptance are not qualified by this run. The passing final run does not erase
the earlier failures or establish responsiveness under arbitrary host contention.
PERF-02 is locally complete; PERF-03 is the next backend/integration slice, with
security review. PERF-04 and OPS-READINESS use the concrete contracts and explicit
maintenance primitives in the linked guides.
