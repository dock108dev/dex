# PERF-04 frontend evidence — 2026-10-28

**PERF-04 implementation and isolated qualification are complete.** The final candidate
and final checks are recorded below; earlier failures remain historical evidence. This is engineering
source evidence, not customer installation, hosted CI, owner acceptance or a customer
walkthrough. No customer state, provider, recognition or acquisition was used. The
existing dirty PERF-02/03 and other work remains uncommitted and preserved.

## Earlier candidate measured boundary

`tests/test_perf04_browser.py` runs Chromium against a disposable threaded WSGI server
on a free loopback port. The engineering-only adapter maps Host to the ordinary ingress
Host; production ingress policy is unchanged. Browser requests outside that server are
blocked. Full/2× sizes contain 33,083/66,166 printings, 5,000/10,000 physical copies and
10,000/20,000 historical operations. Data is synthetic and never presented as the
customer experience.

Each of seven private routes has twenty navigation samples. Timing starts before
navigation, includes request dependencies, waits for the primary result to be visible,
and ends after two animation frames. Samples reuse browser/server and warm OS caches.
These are not process-restart or cold OS-cache measurements. Search/filter/page scenarios
navigate their complete URLs; they do not measure every keystroke/selection path.
The p95 is sorted sample 19 of 20. Initial payload counts decoded local resources plus
HTML at primary readiness; it is not a total of all later disclosures. Request count
includes HTML. Resources completing after primary readiness may be absent from that
snapshot. No claim is made that all later optional traffic was captured.

The harness enforces 300 ms p95, 512 KiB initial payload, 128 KiB V2 JSON and no ordinary
V1 bootstrap/list requests on the measured routes. Separate 50 ms scheduling/transfer,
70 ms JSON/DOM/paint, 32 KiB context/options browser gates, one-second restart navigation,
and twenty-sample guest timing remain unqualified here. PERF-03 backend payload gates
are separate evidence and do not satisfy these missing frontend measurements.

## Earlier candidate checks and retained failures

- 157 affected Python tests passed across account reads/photos, public access, species,
  collection/bulk/photo confirmation, browsing performance and UX errors. This run
  preceded the final copy-price/legacy-goal guard edits. One existing dependency warning.
- Broader card/navigation/Shopping checks initially had **185 passed, five failed**.
  Failures were unprepared V1 navigation fixtures after V2 adoption. Explicit isolated
  preparation was added before read-only snapshots; the updated navigation/review and
  PERF-04 contract set passed **111 tests**. Shell revision checks now occur on its
  independently authorized V2 read; stale navigation reauthorization still returns 409.
  Existing socket-blocking warning retained; no provider call was allowed.
- Final bounded-contract rerun: **5 passed**, including unprepared navigation returning
  503 without database writes. Ruff passed for affected backend and test files; all
  eight changed JavaScript files passed syntax checks; `git diff --check` passed.
- Transport checks: **13 passed** (mapping, revisions, cancellation/late responses,
  route/account changes, 403/404/409/503, continuation, no fallback/retry).
- Bootstrap/tool checks: **10 passed**. Confirmed-receipt/read-failure regression passed
  with exactly one mutation. Copy-price unloaded/partial-page regression passed.
- Photo client regression passed: recognition remains disabled, manual review,
  confirmation and Undo are retained. Source-tool and navigation client checks passed.
- **`scripts/verify_cx05_races.js` and `scripts/verify_cx06_races.js` still fail**:
  their legacy mock environments lack `BoundedReads`; their subsequent expectations
  also assume inline child arrays, eager dictionaries and the complete species list.
  They must be migrated without discarding existing scenario coverage. They remain
  required by CI; the new checks do not replace them. Integrated CI is not qualified.
- An earlier expanded browser run failed at 396.75 ms p95 for twice-size card page two,
  with approximately one-second test-server stalls. Increasing the engineering WSGI
  accept backlog to 128 removed that observed bottleneck in the next run (two passed).
  This is not proof that production concurrency is fixed.
- A subsequent source-identified run still failed twice-size species detail at
  **300.1905 ms p95**, worst **316.77 ms**. It is a failure, not rounded into a pass.
  Preserved raw artifacts: `reports/perf04/pre-closeout-browser-*.json`; source digest
  `adec1a6b46bc1c8972a5f9e41e481ecc1191724a4d8b94b2ca75fc27dea7a292`.
  Copy-price and legacy-goal safety corrections followed that run; the final measurement
  below is reported separately. Do not erase the earlier variability with a passing rerun.

The browser harness also exercises detail/Back, a failing option disclosure with intact
primary cards, rapid species search, 1280/390/320-pixel layouts and actual 200% text,
bulk page selection with off-page draft retention and its editor, plus guest smoke routes.
No horizontal overflow was allowed in the exercised layout cases. This is limited
coverage: complete keyboard operation, focus/scroll restoration, photo/bulk review and
Undo, all archived/oversized paths and guest/account/revocation recovery remain open.

## Changed surfaces and reproducibility

Implementation and exact remaining V1 calls are in [frontend adoption](perf04-frontend.md).
This slice changes `collection.js`, `card-screens.js`, `species-screens.js`, `scans.js`,
`photo_batches.js`, `bulk_entry.js`; adds `bounded-reads.js`, `public-browse.js` and the
public shell; updates their script inclusions and public/private view routing. Bounded
compatible additions are in `account_read_queries.py`/`account_read_views.py`, plus
navigation and species-selector adaptations. The account read files were already
uncommitted PERF-03 work; this slice does not claim to have created that backend.

Tests include new `test_perf04_browser.py`, `test_perf04_contracts.py`,
`perf04_helpers.py`, `bounded_reads_cases.cjs`, `perf04_mutation_cases.cjs`,
`perf04_prices_cases.cjs`, and updates to existing public/species/navigation/bootstrap
and photo-client checks. Documentation updates append to existing guides and preserve
unrelated plan additions; completed PERF-03 engineering is now linked from the baseline
instead of repeated in the remaining execution list.

Reproduce with the commands in [frontend adoption](perf04-frontend.md#qualification-and-reproduction).
Raw performance artifacts stay Git-ignored under `reports/perf04/`. The final digest is
SHA-256 of sorted concatenated `.py/.js/.css/.html` bytes under `src/pokemon_hunter/beta`;
the test verifies it is unchanged at the end of each passing measurement. It is not a
commit hash, package identity or hash of tests/dependencies. RUNTIME-DELIVER must select
and identify the eventual integrated package separately.

## Delivery handoff

OPS-READINESS should integrate explicit catalog migrate/prepare/activate and account
migrate/prepare/status, distinguish listening/catalog/account readiness, retain sanitized
phase timings and require operator recovery after unavailable state. GETs must not
prepare or migrate; confirmed mutation receipts must not be replayed to repair reads.
The unresolved frontend requirements in the implementation document block delivery.

After implementation and integrated CI qualify, RUNTIME-DELIVER owns backups of the
existing installation and independent journals, package/runtime selection, explicit
preparation and compatible rollback. QA-INTEGRATION owns actual-installed guest/member
restart and interaction timings, real-state visual review, keyboard/focus/scroll,
narrow/enlarged-text workflows and owner acceptance. No stage is completed by this report.

## Earlier candidate browser run (superseded source)

Both scale tests passed (126.82 seconds total test time). Twenty samples per row
per size, 280 measured navigations total. Source digest:
`dbf8a3515083cb9610a8c596ab10c54efb47612dd750e86efe001665499f6185`.

| Scenario | Full p95 / worst ms | 2× p95 / worst ms | Requests full / 2× | Largest initial bytes full / 2× |
|---|---:|---:|---:|---:|
| /cards/ | 183.11 / 265.04 | 235.70 / 362.04 | 12–12 / 12–12 | 278,131 / 278,159 |
| /card-library/?q=pikachu | 162.98 / 163.45 | 165.32 / 205.51 | 12–12 / 12–12 | 278,087 / 278,073 |
| /pokedex/ | 163.98 / 164.08 | 196.64 / 213.68 | 13–13 / 13–13 | 266,660 / 266,662 |
| /cards/?page=2 | 146.78 / 147.25 | 191.42 / 192.33 | 12–12 / 12–12 | 278,103 / 278,088 |
| /cards/?set=perf-set-1 | 158.58 / 180.47 | 182.99 / 183.90 | 12–12 / 12–12 | 266,600 / 278,052 |
| Card detail | 165.64 / 178.82 | 163.55 / 166.66 | 13–14 / 13–14 | 248,441 / 248,441 |
| /pokedex/1/ | 202.75 / 231.32 | 219.50 / 244.54 | 14–14 / 14–14 | 266,668 / 283,830 |

33,083 printings: largest observed V2 response **33,386 bytes**. Raw report: `reports/perf04/browser-33083.json`.

66,166 printings: largest observed V2 response **36,726 bytes**. Raw report: `reports/perf04/browser-66166.json`.

All measured final p95s passed 300 ms and observed initial payloads passed 512 KiB.
This does not close the retained earlier failure variability or missing phase, guest
and restart measurements. No threshold was relaxed.


## Continuation: retained timing failure investigation

The original failing twice-size species-detail samples are retained in
`reports/perf04/pre-closeout-browser-66166.json`. The 300.190541 ms sample included
83.7 ms identity and 87.5 ms owned-groups requests, versus route medians of 26.45 and
29.50 ms. The 316.773916 ms worst sample included a 104 ms owned-groups request and
55.1 ms context request, versus a 17.7 ms context median. Payloads did not grow in
those outliers: the owned-groups response stayed 36,726 bytes. The earlier harness
also counted Python/browser-control waiting plus two animation frames, and reused a
threaded HTTP/1.0 engineering server with fresh TCP connections.

These observations locate the variability in request service/queueing as well as the
measurement boundary, rather than proving a growing payload or a deterministic DOM
cost. The old artifact has no server-phase or connection identifiers, so it cannot
establish whether those requests waited in SQLite, Python scheduling, socket handling,
or browser interception. The 396.75 ms observation predates the source-identified
artifact; its recorded one-second accept stalls and subsequent backlog correction are
engineering-adapter evidence only. Neither a passing rerun nor that adapter setting is
a production concurrency fix. OPS-READINESS must retain per-phase runtime diagnostics;
installed runtime/OS-cache behavior remains a separate qualification.

The continuation adds actual form submission, filter selection and page-link samples,
a fixed 300 ms post-readiness traffic window, response parse timestamps, next-paint
readiness, and application Server-Timing. Its scheduling/transfer measure subtracts
the union of measured server-processing intervals on the critical response window,
not a sum that could double-count concurrent requests. Client parse/DOM/paint begins
at primary JSON parsing and ends at the readiness animation frame. All raw samples,
worst cases and failures remain in reports. Timing starts at submit/page action; human
time spent choosing options or typing is not counted as application latency.

A preliminary HTTP/1.0 process run passed 240 interaction samples plus four restart
navigations (`continuation-first-interactions-*.json`, source
`b2f50655fbe09217d9ad91eecc8ee9fb31e92b2dd9a6cfb73694eafeaa4dc687`). It is superseded
by later source changes. Final process tests use the ordinary bounded ASGI application
and uvicorn, without background workers, on disposable prepared state. Host adaptation
and timing headers are test-only. TCP connection descriptions distinguish keep-alive
reuse from new connections. Process startup-to-listening and first usable navigation
are recorded separately. OS caches stay warm from preparation; no cold OS-cache claim
is made. No customer runtime, provider or recognition worker was started.


## Final candidate correctness and implementation checks

Candidate source digest: `2c540137e9a1abba3a2793c524c33e9d132cd85b5ba4085ed31a399624747707`.

- 443 affected backend/interface regressions passed on this candidate with the socket
  guard. One existing socket-guard warning remains; the attempted socket was blocked.
- 31 isolated workflow/contract checks passed, including Goals, source-era preparation
  rejection/recovery, explicit large-choice expansion, bulk cross-page/range/all-matching
  membership, duplicate decisions, save/reload, one confirmation, receipt recovery and
  Undo; manual photo correction/confirmation/Undo without recognition; off-page set and
  binder labels; custom members and photo labels retained through search changes; saved declaration versus current ownership; archived exact variants;
  complete oversized-record downloads; account switching; visible 400/403/404/409/503
  recovery; partial-secondary retry; keyboard focus/scroll; 320/390 px and 200% text.
- CX05: 36 passed. CX06: 24 passed. The scenario inventory retains every original case
  and documents first-V2 authority, explicit detail pages and progressive-option changes.
- Bounded transport: 13 passed. Bootstrap/tool authority: 10 passed. Source-tool renderer:
  8 passed. Receipt/read-failure, loaded-copy price boundary and manual photo client
  checks passed. No V1 fallback is used on migrated browsing routes.
- Affected Ruff, shipped JavaScript syntax/maintained-document validation and whitespace
  checks passed. CI installs pinned jsdom for the renderer suites and Chromium for the
  required discovered Python suites; loopback-only browser tests retain socket guards,
  and raw performance reports are uploaded. Hosted CI itself has not been run here.

The continuation found and repaired actual blank-403 recovery, successful bulk receipt
recovery blocked by derived 503, stale secondary/primary renderer assumptions, frozen
source-progress wording, missing label hydration and large initial-picker handling.
Test-harness corrections (native DOM behavior, explicit photo Search choices, fixture
identity collisions, complete-record download expectations, and correct control IDs)
are not represented as customer-product failures. Initial subprocess attempts lacked
fixture capability markers; a CSP-incompatible waiting helper was replaced. Those setup
attempts yielded no qualified timing samples. A later navigation run was rejected by
its source-hash guard after the final two contract fixes; its raw
`pre-final-contract-browser-*.json` reports are retained and are not final validation.

### Final private navigation measurements

Twenty navigations per route per scale; 280 total. Threaded HTTP/1.0 engineering server,
fresh connections, warm OS caches; source frozen throughout each test. The fixed 300 ms
post-readiness observation window now includes secondary metadata/artwork traffic.
Readiness still ends before this observation window, after usable primary UI and two
animation frames. No timing or payload threshold was increased.

| Route | Full p95 / worst ms | 2× p95 / worst ms |
|---|---:|---:|
| /cards/ | 168.41 / 259.64 | 219.80 / 301.63 |
| /card-library/?q=pikachu | 165.83 / 165.97 | 200.36 / 215.34 |
| /pokedex/ | 180.67 / 229.99 | 181.93 / 447.93 |
| /cards/?page=2 | 164.92 / 181.27 | 181.05 / 194.83 |
| /cards/?set=perf-set-1 | 169.57 / 260.72 | 172.61 / 180.02 |
| Card detail | 164.71 / 165.53 | 165.44 / 165.67 |
| /pokedex/1/ | 219.34 / 233.01 | 248.72 / 315.30 |

33,083 printings: maximum observed local payload 324,016 bytes; largest V2 response 33,386 bytes; requests including HTML 14–25.

66,166 printings: maximum observed local payload 330,263 bytes; largest V2 response 36,726 bytes; requests including HTML 14–25.


### Final guest/private interactions and restart

The separate process runs use the ordinary bounded ASGI application with uvicorn,
HTTP/1.1 keep-alive and fresh prepared engineering roots. There are twenty controlled
repetitions for each guest/private action at each scale: search inputs alternate
`bulbasaur` and `pikachu`, filter selection chooses `perf-set-1`, and pagination clicks
Next from page one. These are actual input/form/select/link interactions, not navigation
to preconstructed result URLs. Search timing starts at submission, excluding human
input time; the card search has no automatic debounce request. The same alternating
search workload is used at both scales. All 240 samples include a 300 ms secondary
traffic window, resource sizes and connection identifiers.

| Action | Full p95 / worst ms | 2× p95 / worst ms | Scheduling/transfer p95 full / 2× | Parse/DOM/paint p95 full / 2× |
|---|---:|---:|---:|---:|
| guest-search | 56.30 / 81.00 | 89.00 / 111.90 | 31.24 / 39.38 | 10.80 / 13.30 |
| guest-filter | 57.00 / 57.10 | 76.00 / 79.70 | 32.01 / 34.49 | 10.10 / 14.00 |
| guest-page | 42.00 / 42.40 | 72.80 / 92.30 | 20.18 / 20.50 | 7.20 / 16.90 |
| private-search | 99.50 / 124.00 | 171.50 / 263.30 | 18.81 / 30.00 | 15.00 / 16.70 |
| private-filter | 141.80 / 142.00 | 131.90 / 135.40 | 18.25 / 18.20 | 14.50 / 12.00 |
| private-page | 172.00 / 176.10 | 151.60 / 160.40 | 27.64 / 19.17 | 15.90 / 13.60 |

| Scale / account | Process startup to listening ms | First usable navigation ms |
|---|---:|---:|
| 33,083 / guest | 143.37 | 169.10 |
| 33,083 / private | 301.15 | 341.44 |
| 66,166 / guest | 267.86 | 317.48 |
| 66,166 / private | 258.98 | 333.64 |

All twelve interaction p95s passed 300 ms; all client-phase p95s passed 50/70 ms.
All four restart navigations passed one second; four observations do not establish a
restart percentile. Startup-to-listening is not application readiness orchestration.
Maximum observed local payload was 324,165 bytes (512 KiB budget); primary JSON was
at most 37,272 bytes (128 KiB budget). Observed context/filter pages passed 32 KiB.
Every interaction sample recorded TCP reuse (3–6 distinct connections within a sample).
The separate HTTP/1.0 navigation run uses fresh connections. Browser asset caching was
disabled by interception, while OS file/database caches remained warm from preparation.

The fixed budgets are p95, not per-sample absolutes. Final twice-size navigation had
three individual observations above 300 ms: My Cards sample 1 at 301.627 ms, Pokédex
sample 1 at 447.928 ms, and species detail sample 8 at 315.297 ms. The 447.928 ms sample
contained a 241 ms, 962-byte context request: again a duration spike without payload
growth, not evidence of a large bootstrap. Their route p95s still passed, and no sample
was removed. Two interaction scheduling/transfer observations exceeded 50 ms: full-size
guest search sample 15 at 56.041 ms and twice-size private search sample 5 at 56.639 ms.
All parse/DOM/paint observations were below 70 ms. These outliers remain in raw reports;
no claim is made that all timing variability is eliminated.

Final combined browser execution: four scale tests passed in 452.81 seconds. Raw reports:
`reports/perf04/browser-{33083,66166}.json` and
`reports/perf04/interactions-{33083,66166}.json`. This supersedes the preliminary
HTTP/1.0 interaction and pre-final-contract runs, whose artifacts are retained.

## Files and handoff boundary

Frontend work is in `bounded-reads.js`, `goals-screen.js`, `public-browse.js`,
`card-screens.js`, `species-screens.js`, `collection.js`, `bulk_entry.js`, `scans.js`
and `photo_batches.js`, with their template/asset inclusions. Compatible backend work
is in the account-read goal/query/view modules, public catalog query/view modules,
`collection.py`/`collection_plans.py`, `image_mappings.py`, shell/navigation authorization
and route registrations. Existing PERF-02/03 and unrelated recognition-removal work
remain preserved; this report does not claim ownership of every dirty file.

Qualification adds the real-DOM renderer harness, scenario inventory, pinned test-only
npm dependency, bounded client cases, workflow/contract tests, process/phase harness,
loopback socket allowances and required CI browser setup/report retention. Relevant
API, UI, recovery, CI and frontend/evidence documents are updated.

Historical filters that were never retained cannot be recovered from current catalog
state. The qualified preservation/replacement workflow is the supported result, not an
invented reconstruction. Deploying the new goal headers requires explicit account
preparation; an older representation returns 503 until that occurs. No user GET prepares
state. Those lifecycle steps belong to OPS-READINESS and eventual RUNTIME-DELIVER.

No customer installation or state was changed, no recognition/acquisition/provider
request was made, and no commit, push, hosted CI, installation or owner acceptance is
claimed. OPS-READINESS is the next implementation handoff; CI-VERIFY, RUNTIME-DELIVER
and QA-INTEGRATION remain separate gates.
