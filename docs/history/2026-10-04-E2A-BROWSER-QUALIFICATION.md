# E2a ordinary synthetic browser qualification — October 4, 2026

The remaining E2a browser gate passed after the owner explicitly authorized the
local beta walkthrough in this chat. E2a is qualified for local synthetic engineering;
owner acceptance, full E2 and beta completion remain open.

## Exact candidate and runtime

All 46 files matched the runtime-qualification candidate before closeout, manifest
SHA-256 `823ccf60c42f754cc5a8d914abd4617fb77a444024e53c8fdff5ead125db26d7`.
No implementation or dependency changes were made. The prior synchronized-runtime
458-test pass and code checks remain applicable to unchanged implementation; they
were not rerun for this documentation-only closeout. Original manifests are retained.

The recorded port 8012 command was incompatible with fixed local host/origin policy
in `beta/security.py`. Port 8011 was verified free and used instead, preserving the
app's existing security policy. The disposable root was
`/private/tmp/dex-e2a-20261005-copied-qualified`; its SYNTHETIC_ONLY marker was checked.
No owner installation was read or changed. A test-only server wrapper prohibited
live eBay acquisition and retained a call counter. The temporary server exited on
completion, and the agent-created browser tab was closed.

## Observed browser behavior

A fresh in-app browser session signed into the generated synthetic admin account.
The ordinary goal UI created Browser Original 151, showing policy
`original-151-reviewed-v1`, reviewed catalog references, 151 species, 823 qualifying
printings, account completion 0/151 and no unavailable species. The missing filter
showed 151 targets; unavailable coverage showed zero. No ownership came from the
research seed.

Successor preview displayed zero membership additions/removals and unchanged policy
and progress for this unchanged catalog. Canceling left exactly one version. A new
preview and confirmation created exactly two retained versions. Both reopened with
151 target rows, catalog references and separate content digests:

- Version 1: `3107026043801c24e78f108d5eccdebd441d1a20ead66ffa96f41402e4c7134f`
- Version 2: `70d595dafda42ef7efe327ea60b4c74857978e3630c88e083bd4bc602f58df28`

Each version created a sample-only individual-card hunt. Saved reopening retained
its captured digest and hid contents. Explicit reveal displayed the synthetic
Venusaur candidate; no purchase link existed. Below-guide filtering showed zero
results because guide evidence was unavailable; restoring All search results showed
one. Reopening the predecessor hunt after the successor hunt retained the older
digest. The server counter remained zero. Browser warning/error logs were empty.

This walkthrough qualifies unchanged-catalog successor UX. Actual catalog-growth,
stale-review and policy edge cases retain their separate automated evidence.

## Preservation and retained evidence

Before/after SQLite snapshots and `preservation.json` compare every baseline table.
Protected pre-existing copies, goals, saved hunts, photos and reservation rows were
preserved. Expected additions were two goal versions, three operation journals,
two sample hunt/import batches and login/session/generation bookkeeping. The only
existing authentication-row change was synthetic admin last_login.

Evidence is local and ignored by Git under `evidence/e2a-browser-20261004/`:
creation/progress/filter/cancel/successor/reopened-version screenshots, DOM/text
observations, revealed/reopened sample-hunt screenshots, browser error log, provider
counter and preservation report. Credentials never appear in the captures or logs.
Final candidate: `validation-final/candidate.json` with SHA-256 companion.

## Next bounded slice

E3a: implement a read-only Packs to open view from the selected broad goal or missing
species using retained reviewed catalog/booster/product records. Deduplicate missing
species coverage and distinguish confirmed booster membership, unknown variants,
guaranteed inclusions and unknown product quantities. Preserve goal versions and
account isolation. Initially show retained dated offers honestly, without new retail
acquisition, refresh adapters or Buy now claims. Test Scyther and whole-goal coverage
on disposable state and retain UI evidence. Official contents, current stock, 177
variant-membership gaps and independent review remain open data work; schedule one
separate finite data slice in the next handoff. No owner-root writes or live eBay.
