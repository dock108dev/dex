# SSOT enforcement — October 10, 2026

Source baseline: `7257e502d39300b4878c35cbc3cfc26c55c2072f`, plus the incoming
uncommitted October snapshot, selector and packaging work. This pass changes
source only. HEAD/index are preserved; the existing installation, owner state,
credentials, retained private prices and running server were neither accessed nor
restarted. No acquisition, migration, build/signing, commit, push or deployment.

## Domain authority and known callers

Paths are relative to `src/pokemon_hunter/`.

| Domain | SSOT module/file | Why this is authoritative | Known callers |
| --- | --- | --- | --- |
| Runtime and routing | `beta/staging_config.py`, `beta/settings.py`, `beta/urls.py` | Explicit supported profiles and one selected handler per route/capability | Local CLI, staging deployment, Django resolver |
| Authentication and authorization | Django auth, `beta/accounts.py`, `beta/store.py:verified` | Mapped active principal and account-scoped service queries | Private views, collection, goals, Shopping, scans |
| Persistence and mutations | `inventory.py`, `migration.py`, `beta/transactions.py`, `beta/collection.py` | Additive schema, reviewed idempotent writes and conflict-aware undo | CLI/import, collection views, scan confirmation, publication |
| Catalog and species | `beta/canonical_species.py`, `beta/collection_catalog.py`, `beta/catalog_imports.py`, `beta/sealed_catalog.py` | Pinned species and reviewed published metadata, independent of ownership | Public views, collection, goals, packs, Shopping |
| Frozen goals and ownership | `beta/broad_goals.py`, `beta/goal_filters.py`, `beta/collection_goals.py`, `beta/ownership_declarations.py` | Stored memberships and distinct declaration/exact-copy policies | Collection goal projection, missing picker, lookup, hunts, research |
| Provider configuration | `config.py`, `beta/scan_config.py` | Shared settings precedence and explicit supported recognition modes/ceilings | Watcher/original app, authenticated hunts, workers, copied staging import |
| Scheduling and jobs | `beta/scans.py`, `beta/scan_worker.py`, `beta/refresh.py` | Durable claims/reservations; replay restricted to disposable roots | Local/staging worker, replay routes/tests |
| Retained-reference validation | `reference_policy.py` | One finite capped amount, safe HTTPS source and 30-day age policy; legacy guides require literal boolean verification | `valuation.py`, `beta/hunt_values.py`, Shopping inputs/references, snapshot contract, math age reexport |
| Price identity and schemas | `beta/price_snapshot_contract.py`, `beta/market_identity.py` | Reviewed source contracts, exact mapping and conditional-market fit; one four-scenario tuple | Importer, lifecycle, calculator |
| Snapshot lifecycle and current-page errors | `beta/price_snapshots.py`, `beta/price_snapshot_sources.py` | Managed expiry/removal, independent source rights and integrity; shared explicit unavailable projection | CLI operators, calculator, source-status route, permanent-save admission |
| Shopping arithmetic | `beta/shopping_math.py` | Decimal quantity/coverage/cost arithmetic; strict input precision remains a different boundary from legacy amount coercion | Original research and four-scenario preparation |
| Shopping history | `beta/shopping.py:store_payload/reopen/reevaluate` | Shared schema/account/byte-integrity and immutable parent/child policy | Both editors and saved/current routes |
| Client API and rendering | `beta/shopping_views.py`, templates and static scripts | Thin authenticated routes and distinct format presenters | `/shopping/`, `/shopping/legacy/`, saved comparisons, picker/status APIs |

## Implemented disposition

- Extracted the existing hunt admission rules into dependency-light
  `reference_policy.py`. Removed `hunt_values._source`, `_valid`, `_amount` and its
  separate cap; all callers use the shared policy directly.
- Removed the original valuation's HTTPS-prefix acceptance and separate numeric,
  verification and date checks. It now refuses credential-bearing/local/unsafe
  source URLs, non-boolean verification and above-cap values in the same way as
  hunts. Malformed non-record entries remain unpriced. Existing valid values,
  edition/grade matching, tie precedence, rounding and historical estimate labels
  are preserved.
- Removed the second `fresh` implementation and cap literal from Shopping math.
  Its established `fresh` and `CAP` imports reexport the same authority; the strict
  decimal-string input validator still owns Shopping precision.
- Removed the duplicate four-scenario tuple from the calculator; it consumes
  `price_snapshot_contract.COLUMNS`.
- Removed the separate exception branches in calculator and source-status view.
  Both delegate to `price_snapshots.display_current`, returning no current prices
  with explicit `invalid_snapshot` status for validation/filesystem failures.
  Operator validation and permanent-save admission continue to use strict
  `current`. Independently admitted historical guides remain separate.
- Deleted `scripts/refresh_values.py`. Caller/config/scheduler/CI searches found
  no active invocation; maintained documentation already called it unsupported.
  It bypassed source rights/lifecycle, generated interpolated grades and substituted
  capture day for source valuation. There is no automatic fallback or replacement
  fetch. Exact prior bytes are retained in the ignored local report's `before/`.
- Updated README, architecture, local development and original-app documentation
  to describe the supported paths. Existing historical closeouts remain unchanged.

## Tests and validation

Added `tests/test_reference_policy_ssot.py`: shared invalid-evidence rejection,
0/30/31-day and future boundaries, delegation, strict operator errors versus
explicit display unavailability, scenario authority and removal guards.
Updated hunt cache instrumentation to observe the shared validator. Added a
snapshot test proving calculator and authenticated source-status route delegate
to the same display policy. Existing tests continue covering Grade 7 historical
estimates, retained graded scenarios, private snapshot rights, source deletion,
account isolation, frozen goals, routes and Shopping arithmetic.

The initial affected-suite run passed 183 tests. The first post-change run passed
203 and failed three snapshot rights/time cases: forwarding explicit `now=None`
bypassed the fixtures' default evaluation clock. The display wrapper now preserves
an omitted clock argument. These were regressions from this pass and were repaired.
No owner data or financial/source policy was altered to make them pass.

Final focused command:

```sh
.venv/bin/pytest -q --disable-socket --allow-unix-socket tests/test_reference_policy_ssot.py tests/test_hunt_values.py tests/test_collection_app.py tests/test_shopping.py tests/test_lot_calculator.py tests/test_price_snapshots.py tests/test_tcgcsv_snapshot.py tests/test_ssot.py --junitxml=reports/ssot-enforcement-20261010/final-junit.xml
```

Final result: **207 passed**, one existing FastAPI/Starlette test-client deprecation
warning. Python source compilation and Ruff lint/format checks passed for the 13
changed Python modules. `.venv/bin/python scripts/ci/source.py` passed for nine
JavaScript files and fourteen maintained documents; `git diff --check` passed.
Tests used disposable synthetic state with network sockets disabled.

Evidence and exact before/after hashes are in
`reports/ssot-enforcement-20261010/`. No full matrix, browser walkthrough,
installed-runtime, provider, wheel, hosted-CI or owner-acceptance qualification is
claimed. The running app has not loaded or demonstrated these source changes.

## Retained contracts and bounded follow-ups

Account-only roots, B-series persisted marker/CLI names, local/staging profiles,
explicit manual/fixture/API/CLI recognition and synthetic replay remain supported.
Their absence on one installation does not prove that they are dead. Retiring
any of them needs a defined support boundary and preservation of durable jobs and
consumed reservations.

Original FastAPI/watcher entry points use distinct storage. Original per-card/group
research and `dex-shopping-v1` history remain distinct from four-scenario
`dex-lot-v2`; old snapshot-v1 import is still validated and tested. The original
valuation's Grade 7 and labelled retained interpolation are historical input
compatibility, not new grade acquisition or an authenticated grade estimate.
Retiring these formats requires a product decision and a history/storage migration;
there is no silent reinterpretation here. The `raw_values` USD/standard defaults
remain only in the established hunt adapter; new Shopping inputs require explicit
fields. Same semantics with different input contracts do not justify erasure.

Current graded evidence, eight raw identity gaps, owner feedback and the exact
hosted candidate remain with the Desktop tracker. A future replacement acquisition
adapter must satisfy source-specific identity, date, rights and purge rules; the
removed scraper supplies no permission or supported execution path.
