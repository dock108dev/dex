# Continuous integration and testing

## HUNT-11 offline reference qualification — October 17

`tests/test_tcgcsv_offline.py` qualifies explicit mappings, Trainer/Energy/promos,
variant/language/condition/currency/date conflicts, duplicates, bounded parsing,
68-group input sharding and partial failures. Independent
`tests/test_hunt11_reference_integration.py` joins prepared v2 releases to existing
atomic activation, expiry, withdrawal/source isolation, Hunter singles/lots,
coverage reconciliation and dry-run/staging safeguards. Run these with external
sockets blocked alongside existing TCGCSV, price-snapshot and Hunter reference
tests. Fixtures are engineering inputs and establish no actual source coverage,
rights or customer outcome. Exact package and native test evidence are retained
under `reports/hunt-11-20261017/`; no new hosted-CI/advisory pass is claimed.

The final isolated Python 3.12 wheel run passed **949 tests across 41 modules**
with external sockets blocked. Every application member and wheel RECORD entry
was checked, all loaded application origins were isolated, repeat archives matched,
and source-to-wheel members matched. One existing socket-block warning remains in
the native output; no external transport occurred. Focused Ruff, compilation,
maintained-guide checks and targeted Bandit passed (zero findings/errors). The
first exact-wheel run retained one obsolete subtype-absence assertion; its test
now verifies documented reverse support preserves known-edition conflicts. These
are engineering results on an uninstalled candidate, not customer delivery or
actual source coverage. Earlier focused test totals overlap this final run.

## HUNT-09/10 ordinary policy and comparison coverage — October 17

The repeat-identical successor wheel is
`02f6b096f4189e8e2bddea37fac03abece93e730347b9ebf0ab0db9f149f0b3f`.
All 239 installed application/data members and 243 RECORD entries match.
The exact installed interpreter passed 772 focused offline cases with external
sockets blocked, including policy/time/concurrency/recovery, historical campaigns,
matching/references/lifecycle, lots, HTTP/CSRF/ingress and distribution guards.
The new 51 policy/worker cases are included, not additive. A five-process race
admits only the two selected daily operations; full workers exercise successive
parents, Continue, details, pause and in-flight Stop without genuine transport.

Installed Chromium qualification passed 32 checks, 12 layouts and four measured
doubled-text states on disposable fabricated data. The harness selects ordinary
policy through the real settings API; package/source identity stayed stable.
Local settings/review interactions acquired nothing. Current-root read-only
compatibility accepted all 59 tables without migration. Ordinary startup retained
bounded ASGI, lifecycle and selected-scan behavior with zero outbound attempts on
generated 40-table state. Recovery rehearsal preserved later writes and events.
Actual installed blank settings, disabled Hunt, ordinary collection/Shopping,
Check availability, Back and reopening were observed separately. No genuine
provider operations or ordinary numeric policy were selected; the owner explicitly
left acquisition disabled. Live repeated Hunts/Stop/value and owner acceptance
remain open. Focused lint/format, compilation, Node contracts, guide links,
distribution privacy guards and targeted Bandit passed. No new hosted-CI or
advisory scan is claimed. Evidence: `reports/hunt-09-10-20261017/closeout.md`.

## HUNT-08 ordinary installed delivery — October 17

The successor wheel `3ab5caa9e9cd84e7551cd8a2c7d534239da5056b4f9265ba3fb982a7a61bded9`
and sdist repeat-build identically. All 237 installed members/241 RECORD entries
match. Its fresh installed interpreter passed 312 focused offline cases with
external sockets blocked, including installed finite authority, the full fake
Both/five-Continue/two-detail plan, worker admission, account/CSRF/ingress, source
withdrawal and recovery. Independent final binding/worker review passed 37 cases.
These overlapping runs are separate evidence, not counts to add together.

The ordinary CLI probe retained real setup, routes, bounded ASGI and lifecycle
threads, adapting only the blocking network runner on generated 44-table state;
it observed zero outbound attempts and no startup data/schema change. Both saved
SHOP-04 and the successor accepted the actual 59-table schema read-only without
migration. Disposable backup/pointer/recovery rehearsal preserved later writes and
independent consumed events without applying old state. Unchanged HUNT-07 UI bytes
reuse their exact earlier layout/race evidence; no broad browser suite was repeated.

The actual installed journey then consumed fifteen owner-selected HTTP-200
operations: one OAuth, twelve Browse and two details. Local journeys and Stops
passed; 59/59 tables, all measured fields and database bytes match. Genuine
in-flight Stop suppression and deliberate exact-printing correction remain
unobserved and separately offline-qualified. The exhausted installed allocation
is closed; installed delivery is complete, owner acceptance remains open.
Targeted Bandit records three reviewed MEDIUM/LOW-confidence SQL-construction
findings with separately bound values. No current dirty-source hosted-CI or new
dependency-advisory result is implied. Full evidence and the usable installed
paths are in `reports/hunt-08-20261017/closeout.md`.

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
commit/run-attempt identities and duplicate job/runtime records. Use **Re-run all jobs**
for a fresh result. Re-running only failed jobs leaves successful jobs' prior-
attempt artifacts outside the accepted boundary; the aggregate will fail with missing
reports until all jobs run in one attempt. Each report must agree with its native
outcomes; a PASS label cannot override a failed test or scan. Failed records remain
visible in the consolidated summary. Security policy blocks all dependency advisories,
all secret findings and high/medium Bandit findings with high confidence. Other Bandit
findings remain reported. Tool and download failures are failures rather than zero
findings. `browser.py` uses one localized `E402` exception to import its helper after
bootstrapping the direct-script module path.

The guarded Hunter boundary adds `tests/test_hunter_operator.py`,
`test_hunter_transition.py`, `test_hunter_profile.py` and
`test_hunter_profile_acquisition.py`. These use disposable schema-compatible roots,
fake processes/transports and controlled artwork. `scripts/qualify_hunter_boundary.py`
verifies exact archive/RECORD/installed members, import origins, optional installed
tests and a restricted-profile Chromium sign-in/CSRF/route journey. Repeat wheel
and sdist checks and the real saved-runtime read-only compatibility gate are retained
under `reports/hunt-07-boundary-20261016/`. The existing full fake Hunter UI harness
continues to qualify unchanged UI assets. These local gates establish neither
hosted CI for dirty source nor provider/customer/owner acceptance.

## Local checks

`scripts/ci/source.py` checks shipped JavaScript syntax and maintained documentation
links. Relative source/document targets and Markdown section fragments must exist.
Maintained guides must work from a clean checkout without private files or local
reports. Checker and read-only state-helper tests are `tests/test_ci_source.py` and
`tests/test_qualification_state.py`.

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

The source check and renderer contracts use Node **24**, selected by `.nvmrc` in both source
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

## Recorded verification

The following completed slices were reconciled from their retained October 14–16,
2026 closeouts. Counts describe their exact revisions and overlap between campaigns;
they must not be added together or treated as a current full-suite result. Ignored
`reports/` paths below locate optional local evidence and are not prerequisites for a
clean checkout. Dated runtime, launcher and pending-decision statements in those
reports remain historical. Current procedures are in [operations](operations.md),
feature behavior in [Shopping](hunts.md), [collection semantics](effective-collection.md)
and [photo entry](photo-entry.md). Engineering success does not supply owner acceptance.

### Collection interface and manual entry

- **UX-01–03, locally delivered October 14:** compact card hierarchy, stable grouped
  navigation, artwork/natural ordering and multiselect scoped completion. The final
  UX-03 source passed 1,515 cases in independent module batches, renderer contracts,
  reproducible packaging and isolated browser/layout checks including measured doubled
  text. Native Safari observations and engineering restoration/layout checks retain
  distinct scopes. Evidence: `reports/ux-01-20261014/`, `reports/ux-02-20261014/` and
  `reports/ux-03-20261014/closeout.md`.
- **UX-04, locally delivered October 16:** safe invalid-browse messaging and fixed
  recovery, preserving JSON/status/authentication and mutation contracts. Reconciled
  evidence covers 538 source and 582 installed cases, with initial harness failures
  retained and exact passing replacements. Fresh package/browser/layout checks and
  actual Safari read/cancel/navigation/scope journeys passed; provider operations and
  collection/goal writes were zero. Owner UX-05 review remains separate. Evidence:
  `reports/ux-04-20261016/closeout.md`, `evidence-matrix.md` and `UX-05-owner-review.md`
  within that directory.
- **ON-00/01, design and manual entry delivered October 16:** shared
  Checklist/Paste/CSV review, durable drafts, atomic Confirm, receipts/replay and
  conflict-aware Undo qualified with 332 service and 16 package-gate cases. Original
  installation verified all 204 application/data hashes and an additive two-table
  migration with all 57 prior tables preserved. Actual Safari inspected entry choices;
  no customer draft/card was created. The later title/back-link repair passed six
  viewport/text states, 19 focused tests, fresh package checks and genuine before/after
  observation. Title contrast measured 14.44:1 and Back 6.57:1. Evidence:
  `reports/on-00-20261016/`, `reports/on-01-20261016/` (including `local-installation/`)
  and `reports/on-01-contrast-20261016/`.
- **Current-collection Missing repair, delivered October 16:** current Original 151
  species ownership agrees with unrestricted Kanto; explicitly selected saved goals
  retain frozen policy/version. Fifty-eight installed cases and reproducible package
  smoke passed, with genuine read-only Safari and unchanged 59-table/protected-state
  evidence. Counts in that closeout are dated observations, never product constants.
  Evidence: `reports/missing-sync-20261016/closeout.md`.

### Shopping delivery and bounded provider evidence

HUNT-01 adds backend-only offline contracts in `tests/test_hunter.py`,
`test_hunter_query.py`, `test_hunter_catalog.py`, `test_hunter_views.py` and
`test_hunter_coverage_audit.py`. They cover broad two-lane queries, 200/400-summary
and body bounds, UTC eligibility, mixed-option deduplication, account/session/CSRF,
durable exact allowance, Stop/deadline, all-era batching and source lifecycle.
Package inspection requires the five Hunter modules. Fixture and isolated package
success do not establish customer installation, whole-window coverage or a bargain.
Exact HUNT-01 qualification is retained under `reports/hunt-01-20261016/`.

HUNT-02/03 add `tests/test_discovery_matching.py` and
`tests/test_hunter_references.py`, plus extended Hunter catalog cases. Offline
fixtures exercise aliases, number padding/denominators, named forms, sibling and
archived/conflicting identities, all-era published snapshot validation, exact
product/subtype admission, seller-specific condition/grader selection and
source/date/lifecycle gaps. Existing Hunter Stop, deadlines, account/session,
zero-network and lease regressions remain required. Fresh exact-package evidence,
separate synthetic batch timings and bounded actual metadata-only coverage are
retained under `reports/hunt-02-03-20261016/`; this supplies no new genuine provider,
customer-installation, hosted-CI or owner-acceptance gate.
The qualified source passed 433 affected cases, 102 focused installed-package cases,
21 package-harness cases and a repeat-build smoke with 43 HTTP assertions. Counts
overlap and must not be added. Genuine backend qualification consumed one OAuth and
two Browse operations, all HTTP 200; 400 summaries produced 8 conditional and zero
fully comparable results. Its allowance is exhausted/closed; no customer Hunter
installation or hosted-CI result is claimed.

- **SHOP-01B/C/D, completed October 15:** saved Production configuration, separate
  finite prepare/execute/status/Stop operator and observed OAuth/Browse connection.
  Offline operator qualification passed 176 cases with zero provider requests; the
  documented token-label repair passed 229 focused cases. Connection history retains
  four consumed operations, including the earlier Sandbox and Production failures;
  the final OAuth/Browse each returned HTTP 200. Setup and connection are not pricing
  coverage, broader entitlement or a continuing allowance. Evidence:
  `reports/shop-01b-20261015/terminal-resume/`, `reports/shop-01c-20261015/` and
  `reports/shop-01d-20261015/saved-production-verified.md`.
- **SHOP-02, locally delivered October 15:** owned-card deal discovery and
  current/frozen missing policy with temporary rights-aware comparisons, Stop and
  finite Next. Final evidence includes 277 installed cases, 57 focused source cases,
  18 client cases, 67 renderer contracts and responsive/enlarged-text browser checks.
  Five provider operations (two OAuth, three Browse) returned HTTP 200. Observed
  results were conditional/unpriced; final native repair verification covered deals,
  while final missing integration is exact-package evidence. Evidence:
  `reports/shop-02-20261015/closeout.md` and its `verification.json`.
- **SHOP-03, locally delivered October 16:** assisted URL/ID details, exact variation,
  temporary review and separate stock/lot/content quantities. Qualification includes
  313 installed backend cases, six assisted browser contracts and fresh package/layout
  checks. Two actual detail checks consumed one OAuth and two resolution operations,
  all HTTP 200; both reviews produced partial conditional subtotals. The final client
  retention repair reused unchanged backend bytes and acquired nothing further.
  Evidence: `reports/shop-03-20261016/closeout.md` and its `identity.json`.
- **SHOP-04, locally delivered October 16:** merged visual search, distinct Base/Base
  Set 2 refinement, contextual entry, singles/loose lots/auctions and Ungraded review.
  The live-backend candidate passed 373 distinct installed cases, 20 renderer
  contracts, nine client/service cases and 25 isolated browser checks. Final client
  indicator/navigation changes have separate installed repeats and a 43-assertion
  package smoke; acquisition/review bytes match the actual-observation candidate.
  Four provider operations (one OAuth, two Browse, one detail) returned HTTP 200.
  Actual Safari observed an honest unpriced auction review and restored Back. All
  207 installed application/data files and 59-table/protected-state preservation
  matched. ON-02 and unrelated source work were excluded. Evidence:
  `reports/shop-04-20261016/closeout.md`, `identity.json`, `verification.json`,
  `final-client-delta.json`, `api-counts.json` and `owner-journey.md` in that directory.

These qualification allowances are closed; unused capacity does not authorize a new
search. No campaign above established fresh market coverage, a bargain, a complete
lot valuation, automatic bid limit, unattended acquisition or owner acceptance.
Restricted listing/reference content and derived amounts were not retained in reports.

### Qualified photo candidate and security remediation

**ON-02 Phase A is qualified offline and not customer-installed.** The final retained
candidate passed 247 service/ingress cases, fake-CLI protocol/Stop/recovery checks,
six 1280/390/320px and measured doubled-text browser states, repeat packaging and
41 isolated HTTP smoke assertions. Real recognition calls, customer uploads and
customer migrations/updates were zero. D2 selected the local CLI pilot; the owner
subsequently deferred D3 real-photo testing. The original closeout's unselected-D3
wording is historical. See [current decisions and limits](photo-entry.md#delivered-work-and-owner-decisions)
and local `reports/on-02-cli-20261016/` plus
`reports/on-00-20261016/owner-decisions.md`.

**CodeQL alerts 12–17 are fixed in hosted analysis.** The local repair passed 385
affected cases with external sockets disabled, lint/format, compilation and source
checks. `reports/codeql-alerts-12-17-20261016/verification.json` records that earlier
unpublished candidate and the then-unavailable local CodeQL runner. The changes are
now on `main` at `0d85cd9e6ec2ff0ca738b9cc9761b04ae594dcfd`; fresh CodeQL analyses
`1970980707` and `1970978447` reported zero results and no errors/warnings, and alerts
12–17 were verified fixed. The [successful CodeQL run](https://github.com/dock108dev/dex/actions/runs/38981039186)
qualifies that revision's security analysis. Its independent Tests run must be
assessed separately; CodeQL success is not an all-CI pass or a customer runtime update.

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

The October 16 HUNT-04/05 and LOT-01 backend qualification is retained under
`reports/hunt-04-05-lot-01-20261016/`, bound to its final dirty source and repeat-built
wheel. Offline traversal/ranking/parser/service/authority regressions use external
socket blocking and disposable engineering roots. The report separates these
checks from genuine provider qualification, review UI, customer installation and
owner acceptance. No new live allowance or hosted CI pass is implied.

## Hunter UI offline gates

HUNT-06 adds authenticated UI/image/correction API cases, isolated JavaScript
review race contracts and `scripts/qualify_hunter_ui.py` real Chromium engineering
qualification. The browser helper creates disposable state with fake transport,
blocks external sockets/requests, and checks original leases, independent Stops,
local paging versus acquisition, current-reference removal, correction revisions,
Back/focus, narrow layout and measured doubled text. Package inspection requires
Hunter templates, both scripts and CSS. Qualify a repeat-built wheel in a fresh
isolated interpreter, with installed imports and packaged browser assets checked.
Evidence under `reports/hunt-06-20261016/` is local engineering only; genuine
provider, customer installation, hosted CI and owner acceptance remain separate.

HUNT-07 adds a joined fake-transport traversal/review/detail/accounting suite in
`tests/test_hunter_h07_integration.py`, alongside the HUNT-06 browser and renderer
gates. Native security/dependency/secret reports, current hosted revision evidence,
installed-module reconciliation and fresh all-table preservation remain separate
evidence classes. A green committed-revision run does not qualify later dirty UI
or test changes; local exact-candidate gates do not manufacture a hosted pass.
Genuine execution still requires a resolved, qualified boundary and separate
finite authorization; no provider or installation follows from these tests.

### Authorized partial Hunter execution — October 17

The qualified guarded transition was explicitly selected and executed at the actual
root/origin, followed by compatible latest-state SHOP-04 handback. One Both action
consumed one OAuth and two Browse operations, all HTTP 200, and the live UI showed
400 fetched/unique/retained summaries with ten planned pages remaining. The initial
pages were singles; no lot/details or continuation evidence was obtained.

The active automation tab then became unavailable and a fresh tab lacked its
temporary run context. The attempt ended without another Hunt or hidden recovery.
This observation does not establish a backend defect. Temporary selections were
closed; consumed accounting remains intact. This attempt's genuine qualification
was partial; the separately selected completion below resolves its remaining
bounded gate. Local evidence is under
`reports/hunt-07-live-20261017/`.

Schema and 55 tables match the fresh baseline; only ordinary authentication/session
bookkeeping differs, consistent with observed sign-in. Runtime/configuration,
startup pointers, collection state and independent source rights match. The original
attempt-journal prefix and exhausted HUNT-01 ledger are byte-identical; authorized
append/new-ledger effects are separately recorded. No old state was restored.

### Browser interruption recovery — October 17

`scripts/qualify_hunter_browser_recovery.py` extends the existing disposable
Hunter harness with ordinary sign-in, persistent original Chromium target/history
across controller disconnect/reconnect, same-tab reload, explicit Continue,
local paging/filter/reveal, corrected lot review/Back/focus, fresh-tab refusal and
missing-run recovery. It also retains the prior 30 UI/lifecycle/race checks. Real
Chromium behavior, actual Computer Use API observations and the documented
turn-retention model are separate evidence classes. The model does not prove a
real Codex cleanup event or genuine cross-turn retention.

The missing-run case reproduced an HTML 404 whose status the client discarded
while parsing JSON. Only that parse failure now preserves HTTP status, allowing
the existing unavailable branch to clear stale context. Client contracts cover
immediate and delayed startup metadata without acquisition or renewed authority.
Retained browser attempts 1/2 document the harness error and pre-repair failure;
fresh isolated-wheel evidence qualifies the repaired asset. Backend/operator
bytes remain unchanged, and earlier exact-byte qualification retains its scope.

Final recovery gates pass: 40 fresh-wheel Hunter browser checks/eight layouts/two
doubled-text states, nine restricted-profile sign-in/route checks, 35 focused
isolated-wheel cases, 123 affected source cases and 204 preserved backend/operator
regressions. Main/review client contracts pass 23/24; documentation-checker cases
pass 11 and the source check covers 19 JavaScript files / 19 maintained guides.
Counts overlap and must not be added. Repeat wheel and sdist bytes match; all 236
installed application/data members match, with only `hunter.js` changed from the
executed wheel. Current dirty source has no new hosted-CI claim.

Recovery evidence, reproducible package identities, focused native reports and
read-only actual-state preservation are under
`reports/hunt-07-browser-recovery-20261017/`. Use the
[tested browser procedure](hunter-browser-workflow.md). This pass sends zero
actual provider operations and makes no customer runtime transition. The three
previously consumed operations and closed attempt remain intact. A new finite
execution needs separately qualified fixed-plan binding; the old proposal cannot
be reused with a renamed ledger or edited document. The later completion binding
and genuine execution are recorded below. HUNT-08 and owner acceptance remain open.

### Completion-plan binding gates

`tests/test_hunter_completion_binding.py` exercises the literal completion ID,
strict plan/predecessor documents, byte-exact prior accounting, independent
selection and refusal before side effects. Existing full-plan service/HTTP tests
run for both fixed IDs, including twelve Browse pages and two shared-budget
details. An uncertain OAuth-only admission also prevents completion restart.
Completion detail dispatch must retain a live parent with the same owner tuple
and exact allowance. Invalid mutable accounting still permits handback-only
validation while preserving the damaged journal for repair.

The affected operator/profile/transition, finite-budget and integration suites
remain offline with disposable roots and fake transport. Reproducible new archives,
fresh isolated-wheel installed tests, restricted-profile auth/routes and retained
browser reconnect/404/lifecycle proof bind the completion candidate. The browser
model is simulated turn cleanup; real reconnects do not establish historical
Codex cleanup cause. Exact reports and unexecuted proposal are retained under
`reports/hunt-07-completion-binding-20261017/`. No actual provider operation,
customer HTTP or runtime transition is authorized by these gates; they do not
close HUNT-07, install HUNT-08 or supply owner acceptance.

The final completion candidate passes 223 fresh isolated-wheel cases, nine
restricted-profile browser checks and 40 Hunter browser checks/eight layouts/two
measured doubled-text states. The 40 new binding cases and both fixed-plan full
fifteen-operation fake service/HTTP paths are included in installed qualification.
Forty-seven final focused source cases supplement earlier unchanged affected
passes; counts overlap. Retained failures identify the repaired detail-parent
allowance check and one test-message assertion correction. Targeted Bandit retains
two low findings and zero blocking findings; dependency/security history remains
separate. Ruff, compilation, JavaScript/guide checks and whitespace pass. These
are local exact-candidate results, with no new hosted-CI claim.

### Completed bounded genuine Hunter gate — October 17

The owner selected the exact completion proposal and finite plan. The frozen
wheel SHA-256 is `ceb3abbb1df16abfa49cc07202b6ac2d98ae0d49e84dc2e52c56c71a6f7726eb`;
its proposal SHA-256 is
`eb602c52d7c9a75ec270cf0f2c53685fc2a4ff21587c122cb1f6f567c6a758d9`.
The same original tab retained one Both run, its UTC window and lease across five
explicit Continues, local review and selected details. One OAuth, twelve Browse
and two exact details completed HTTP 200. All twelve pages returned 200 summaries
and advisory truncation. Each captured page has a recorded disposition; partial
coverage never establishes a complete market scan.

The 2,400 observations reconcile to 2,391 unique identities plus nine duplicates;
800 were retained and 1,591 skipped at the retention limit. Fifty retained offers
were locally rejected. The other 750 were 13 conditional, 15 matched-unpriced,
134 ambiguous, 161 unmatched and 427 unsupported, with zero fully comparable
results. Local paging/filter/reveal, lot analysis/comparison, Back/focus and
reopening added no acquisition. Two received lots exposed honest unresolved
contents. No justified contents correction was available, so deliberate correction
was not exercised live; offline corrected-review qualification remains separate.

Stop details was selected while loading, after its transport had completed. Actual
in-flight Stop/late-response suppression remains an offline-qualified race, not a
new live observation. Parent Stop cleared results and dependent reviews. The
operator returned to ordinary SHOP-04 using latest state. Schema and 55 of 59
tables match; four authentication/session bookkeeping changes are consistent with
observed sign-in. Runtime/helper/configuration, protected collection state and
source lifecycle match. The original journal prefix and closed three-operation
ledger are preserved. The new journal contains 52 rows: six action admissions,
fifteen each admitted/in-flight/completed operations and one stopped action.
All fifteen new operations remain consumed, for eighteen across these two HUNT-07
intervals; earlier campaigns remain separate.

Exact authorization/execution, sanitized outcomes, preservation, evidence matrix
and the next `HUNT-08-handoff.md` are under
`reports/hunt-07-completion-live-20261017/`. HUNT-07's bounded genuine gate is
complete. The historical tab-loss cause and HUNT-06's missing start-state/writer
evidence remain unresolved. This local execution supplies no new hosted-CI result,
permanent Hunter installation, owner acceptance or further provider capacity.
Guide edits after execution are separate from the frozen candidate bytes.
