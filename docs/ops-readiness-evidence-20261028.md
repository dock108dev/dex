# OPS-READINESS — working candidate and isolated evidence

This is engineering evidence, not customer-app acceptance. The customer installation
was not migrated, prepared, replaced, reseeded or started. No provider acquisition,
recognition, scraping, price refresh, purchase, bid, credential reset, commit, push or
deployment was performed. Existing PERF-02/03/04 and unrelated dirty work remains intact.

## Implemented contracts

- ASGI startup performs bounded shared-catalog validation before ordinary workers.
  Compatible prepared state is reused; missing/incompatible/stale/interrupted/corrupt
  metadata yields fixed safe categories. Validation never prepares or migrates.
- `/livez/`, `/readyz/` and independently authenticated `/api/v2/readiness/` distinguish
  liveness, catalog and account state. Browser usability remains separate. Public
  readiness contains no account identifiers or private records. Existing resource
  409, unavailable-state 503, authorization and no-store contracts remain intact.
- Account policy `effective-collection-2-goal-headers` deliberately rejects old prepared
  goal headers. Explicit preparation is required. Supported catalog-schema repair also
  requires account-schema repair to recreate indexes on replaced catalog tables.
- Ordinary CLI shutdown joins existing workers through ASGI lifespan before Uvicorn
  restores/re-raises signals; its idempotent fallback covers ordinary exceptions.
  No new recognition, expiry or acquisition worker is added. Staging retains its
  separate serving/heartbeat path; no PostgreSQL qualification is claimed.
- Local ASGI admits one dynamic Django request at a time, plus four separately bounded
  static-file requests, waiting at most 500 ms before a
  fixed `runtime_busy` 503. This limits active catalog page-cache allowance to 64 MiB;
  it is not a total-RSS cap. Client concurrency and admission waits remain measurable.
- Bounded sanitized request records separate execute/fetch, service/decoder/serialization
  and overall request elapsed time. A random request ID links responses to retained
  records. Coverage/null labels prevent unavailable phases being reported as zero.
  Storage uses 1 MiB plus two rotations, at most 60 persisted records/minute and a
  256-record memory ring. Existing sanitized failure stderr remains separate.
- Profiling exposed repeated positive-posting evaluation in owned search. Exact count
  retains the complete membership query; page selection uses compact common text plus
  exact residual ranks, following the existing public search strategy. Empty/deep pages,
  all three sort orders, substring/literal searches and ownership parity are checked.

Commands, safe failure actions, retention and the concrete later delivery procedure are
in [operations](operations.md#ops-readiness-local-contracts). Ordinary GETs and retries
never perform those maintenance commands or resubmit a confirmed collection operation.

## Candidate and measurement conditions

Working beta-source digest:
`a1f09f920b26b86dc7337ce378a779108519344f8653df865629238bceae6b57`.
The digest hashes sorted `.py/.js/.html/.css` bytes under `src/pokemon_hunter/beta`;
it is not a wheel hash or a commit. Base HEAD is
`e90b63f33955cb93c9ccbadd7c8fdfdc1eac92ac`; the integrated checkout remains dirty.

macOS 27.0.1 arm64, Mac15,6, 11 logical CPUs, 18 GiB RAM; checkout Python 3.14.0,
Django 6.1.2, Uvicorn 0.54.0 and SQLite 3.50.4. This is not the installed customer
Python/package. SQLite engineering roots have 33,083/66,166 printings, 5,000/10,000
additional copies and 10,000/20,000 synthetic historical edits on top of the retained
small policy fixture. Catalog group counts are 19,013/38,024. OS caches remain
warm from explicit preparation; no cold OS-cache claim is made. Full-catalog and
whole-account preparation are measured separately in their existing performance gates.

Ordinary-runtime tests call the actual CLI, ASGI wrapper and existing cleanup workers.
The engineering adapter changes socket/Host mapping to avoid port 8011 and adds safe
query-class/fingerprint and Server-Timing measurement. No private SQL values are emitted.
Runtime HTTP samples use fresh clients/connections; browser tests retain HTTP/1.1
keep-alive, disable browser asset cache by interception and block remote artwork.
Twenty comparable samples are used for each reported p95. All restart observations
are reported individually, without a percentile. Raw evidence remains Git-ignored
under `reports/ops-readiness/`, `reports/perf02/`, `reports/perf03/` and `reports/perf04/`.

## Retained failures and investigation

Earlier candidates and attempts are not silently promoted to final evidence:

- Initial focused run: 61 passed, one failed because catalog schema repair removed
  account indexes. The recovery workflow now explicitly repairs both schemas.
- The changed catalog operator status initially omitted its existing ready-state build
  field; that compatibility field was restored. A corrected combined run passed 125.
- The first ordinary-process assertion expected zero on termination. Further inspection
  showed a real defect: Uvicorn 0.54.0 re-raises SIGTERM before the outer CLI `finally`,
  skipping worker joins. Lifespan cleanup now completes before signal re-raising;
  the process tests verify the worker-join record rather than exit zero alone.
- A contended early performance run passed both catalog gates and full-size account
  qualification, but twice-size incremental/three SQL gates failed. Raw reports were
  copied to `reports/ops-readiness/initial/` before further work.
- A later full-size account run had fresh-owned SQL p95 93.145 ms with typical samples
  around 4 ms; its largest observed fresh-catalog SQL sample was 189.202 ms. These
  elapsed spikes are retained. They do not establish a deterministic payload cost,
  browser scheduling cause or a proven OS-contention explanation.
- Ordinary owned search at twice size originally spent roughly 42 ms executing the
  duplicated count/page search queries. Four concurrent Django requests amplified SQL
  wall time beyond 40 ms. A materialized-full-matching-set experiment also failed; it
  is retained in `materialized-owned-search-66166.json`. The final page strategy avoids
  the second full positive list; one admission slot bounds intra-process contention.
- The earlier WSGI browser run failed a twice-size 300 ms gate at 314.583 ms. That adapter
  is no longer used for navigation timing: the same routes, sample counts, visibility,
  payload, post-readiness traffic and workflow checks now run on ordinary CLI/ASGI.
  Other workflow fixtures can still use the engineering WSGI helper. This is a serving
  boundary correction, not a relaxed budget or smaller workload.
- One process-browser run rejected its own source hash after the lifecycle correction;
  its measurements are not final-candidate evidence. `pre-lifespan/` retains these
  reports. An eventual Python 3.14.0 traceback-dumper stall was confirmed by native sampling:
  the main thread waited in `cancel_dump_traceback_later`, while the dumper spun in
  `dump_frame`. Only that engineering process was terminated. Final tests use
  `faulthandler_timeout=0` with an external 900-second process-group deadline. This
  changes a test diagnostic timer, not any application performance budget.
- An invocation omitted `--allow-unix-socket`; two asyncio tests were blocked while
  creating their local event-loop socket pair. Final invocation uses the existing CI
  policy: `--disable-socket --allow-unix-socket`, with loopback browser allowances.

## Final qualification

**OPS-READINESS is complete in source and the specified local SQLite engineering
qualification.** The checkout is uncommitted and uninstalled. This is not an aggregate
hosted CI result, installed package qualification, customer acceptance or PostgreSQL claim.

- Final runtime/correctness/browser run: **146 passed in 575.86 seconds**, with socket
  blocking, Unix event-loop sockets and explicit loopback allowances. This covers the
  read-only probes, schema/policy/manifest/infrastructure faults, corrupted derived rows,
  interrupted/changed-authority build rejection, explicit repair, stale selectors,
  account isolation/revocation, confirmed-mutation recovery, older-writer invalidation,
  snapshot transitions, admission cancellation, worker lifecycle and diagnostic bounds.
- Final catalog/account performance run: **4 passed in 146.67 seconds**, same fixed
  budgets, final candidate, both scales, warm/fresh connections and twenty samples per
  scenario. Account scenarios now include owned search and short owned queries.
- Renderer regressions: **36 CX05 and 24 CX06 cases passed**. Affected Ruff checks,
  33 shipped/tool JavaScript syntax checks, 18 maintained-document link checks and
  whitespace checks passed. The earlier broader workflow/interface run passed 202;
  that earlier run is supporting regression evidence, not a replacement for these
  final-candidate gates.

### Backend, preparation and memory

| Boundary | 33,083 printings | 66,166 printings | Fixed budget |
| --- | ---: | ---: | ---: |
| Full catalog preparation, one observation | 10,792.514 ms | 24,097.293 ms | 30,000 ms |
| Primary whole-account preparation, one observation | 8,630.088 ms | 18,922.698 ms | Report separately |
| Incremental refresh p95 / worst | 76.140 / 81.953 ms | 179.411 / 191.616 ms | 200 ms p95 |
| Largest catalog API / SQL p95 | 15.132 / 11.502 ms | 24.503 / 21.694 ms | 180 / 40 ms |
| Largest account API / SQL p95 | 28.024 / 18.716 ms | 37.847 / 33.515 ms | 180 / 40 ms |
| Ordinary runtime serial API / SQL p95 | 26.607 / 18.888 ms | 41.888 / 33.950 ms | 180 / 40 ms |
| Ordinary runtime four-client API / SQL p95 | 96.859 / 18.663 ms | 149.681 / 32.409 ms | 180 / 40 ms |
| Runtime RSS after measured reads | 86,752 KiB | 88,240 KiB | Observation, not a peak/RSS cap |

Maximum query counts were 13 for catalog and 20 for account gates. SQL figures include
execute and fetch; runtime logs retain those components separately. Four-client API
worsts were 98.658/150.439 ms. Client concurrency does not multiply the one dynamic
admission slot. Four static-file slots do not open catalog snapshots; their ordinary
authentication connections and workers still consume memory outside the 64 MiB catalog
cache allowance. RSS is an after-load sample, not a peak-memory certification.

| Restart observation | Full-size ms | Twice-size ms |
| --- | ---: | ---: |
| Valid spawn → listener plus liveness/catalog-ready probe, run 1 | 626.920 | 472.670 |
| Same prepared state, run 2 | 304.829 | 284.996 |
| Same prepared state, run 3 | 287.512 | 288.368 |
| Interrupted-state spawn → explicit 503 | 303.794 | 321.365 |

All observations pass 2,000 ms. No percentile is claimed from three/one observations.
These backend probes do not include browser paint or automatically prepare accounts.
The combined engineering preparation helper also prepares a second fixture account;
its duration is not substituted for either the catalog or primary-account measurements.

### Ordinary-runtime browser results

Twenty samples per scenario/scale; 280 navigation samples and 240 actual search/filter/
page actions. Navigation and interaction suites now both use ordinary CLI/ASGI, including
real cleanup workers. Existing visibility, payload, post-readiness traffic, Back/detail,
recovery and layout assertions remain in place.

| Scenario | Full-size p95 ms | Twice-size p95 ms |
| --- | ---: | ---: |
| My Cards navigation | 167.19 | 231.15 |
| Card Library search navigation | 170.15 | 236.37 |
| Pokédex navigation | 199.27 | 253.89 |
| Cards page two navigation | 168.61 | 190.54 |
| Cards filtered navigation | 168.20 | 186.90 |
| Card detail navigation | 165.46 | 168.50 |
| Species detail navigation | 217.69 | 232.96 |
| Guest search action | 107.90 | 70.30 |
| Guest filter action | 77.40 | 75.30 |
| Guest page action | 45.20 | 60.40 |
| Private search action | 115.70 | 134.30 |
| Private filter action | 139.60 | 131.50 |
| Private page action | 132.30 | 131.40 |

All p95s pass 300 ms. First usable navigation after restart, each a single observation:
full-size guest/member **114.684 / 189.945 ms**; twice-size guest/member
**142.617 / 146.185 ms**. All pass 1,000 ms. Largest scheduling/transfer phase p95s were
36.155/32.880 ms (50 ms budget); parse/DOM/paint p95s 15.2/17.3 ms (70 ms budget).
Observed interaction payload maxima were 324,165/324,151 bytes; navigation/primary/
context payload gates also passed without threshold changes.

### Remaining variability and evidence limits

Earlier exact misses remain failures: runtime SQL 41.843 ms, owned-search SQL
40.243 ms, incremental refresh 222.058 ms, and private pagination 329.1 ms.
The last was traced to serial script/style delivery plus a slow primary request;
static assets now have a separate bounded lane. These artifacts are retained under
`serialized-assets/` and the earlier candidate directories. The final independent
runs above pass; they do not prove all latency variability has disappeared.

Final twice-size individual navigation outliers include Card Library **898.654 ms**,
Pokédex **330.275 ms**, and species detail **313.616 ms**. Their route p95s pass. The
898.654 ms sample includes a 706.7 ms primary API and 208.8 ms optional artwork request
without payload growth (primary 33,328 bytes). Retained bounded process profiling
contains a 223.58 ms SQL-execution request, including 215.5 ms in a search query,
and a 75.9 ms membership-query outlier. The navigation artifact does not retain a
request-ID join to those profile records, so they cannot be asserted to be the same
request or used to invent a precise decomposition of the 706.7 ms interval.

The twice-size guest-filter action had one **384.500 ms** observation while its p95
was 75.3 ms. Its phase evidence shows 131.891 ms scheduling/transfer, 1.1 ms parse/paint,
and a static-script request with 102.047 ms admission wait/116.201 ms application time.
That distinguishes request/queueing variability from DOM work; it does not prove a
single OS, SQLite or client cause for every spike. No sample was discarded.

Readiness uses bounded metadata/object-name checks and per-read payload validation,
not a complete physical database scan or protection against arbitrary manual changes
to trigger definitions/FTS shadow tables. Pre-dispatch refusals do not have the Django
SQL diagnostic record. Log rate/size retention can omit individual request IDs; the
legacy sanitized failure stream remains separate. The exact installed interpreter,
package dependencies and actual customer OS-cache/workload behavior need later gates.

## Changed surfaces and next lead

New modules: `readiness.py`, `read_infrastructure.py`, `read_diagnostics.py`, `serving.py`.
Integration changes: ASGI factory, ordinary CLI, settings/middleware and URL registration;
catalog/account manifests, operator status/error handling, representation policy and V2
response instrumentation; the bounded owned-search page-selection adjustment. Existing
PERF-02/03/04 changes in these files were preserved, not recreated.

Qualification changes: `test_ops_readiness.py`, `test_ops_runtime.py`, `ops_server.py`,
owned-search performance cases, ordinary-runtime browser harnesses and worker lifecycle
regression. CI retains OPS reports. Operations, local-development, error/recovery, CI,
account-read documentation and Desktop Next Steps record the implemented contracts.

Next executable slice: **RUNTIME-DEPS**, led by local runtime/integration engineering
with security verification. Its qualified package/interpreter and this candidate feed
CI-VERIFY, then RUNTIME-DELIVER and QA-INTEGRATION. The exact backup, migration,
preparation, readiness and compatible-rollback handoff is in
[operations](operations.md#runtime-deliver-handoff-not-executed). None of those later
stages has been performed by this slice.
