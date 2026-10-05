# October 4, 2026 — D1/E1b validation

Local slice closeout (America/New_York date; acquisition timestamps are UTC).
Baseline HEAD remained `fba1be13135b0b3bbb6cb674de5586e0f3c80740`. Initial
D1/E1 candidate SHA-256 `c6cb7a3aa6123db3c71499fe2cb86cb54027968525b6d798267efbab62348f53`
matched and all 23 files were checked before changes. No applicable AGENTS.md was
present in this repository or its parent path. Existing edits were retained.
The previous manifest/patch, normalized packages and private evidence are unchanged;
a separate private restoration of its 22 repository files reproduced their hashes.

Final file manifest and its SHA-256 companion are at:

- `/Users/michaelfuscoletti/dex-private/d1-e1b-20261004/validation-final/candidate.json`
- `/Users/michaelfuscoletti/dex-private/d1-e1b-20261004/validation-final/candidate.sha256`
- `/Users/michaelfuscoletti/dex-private/d1-e1b-20261004/validation-final/candidate.patch`

The manifest covers every changed/untracked deliverable plus the Desktop handoff,
including preserved earlier changes. It is frozen after documentation closeout.
The patch retains final tracked/untracked repository source. No commit or remote
publication was made; the baseline HEAD alone does not identify this candidate.

## Data identity and classification

Package file SHA-256:
`250d0c61aea496d0854c831f62edb1030e1cd3acf91db59d239185528401a45f`.
Service fingerprint (normalized optional schema fields):
`12ed07eb96fe8b3db79e33521028c12f19188ccb31eb0b17b97014644129ec34`.
`config/sealed/2026-10-04-151/hashes.json` pins package, reconciliation, source index
and missing-18 report. Offline reproduction in private `reproduced-final` matched
all five public artifacts byte-for-byte, without network access.

207 numbered identities: 185 Pokémon, 21 Trainer, one Energy. 384 normalized
provider-described variants: 346 Pokémon variants with canonical mapping,
36 Trainer variants and two Energy variants without fabricated species identity.
151 distinct Pokémon species; 207 standard booster memberships; 177 individual
extra-variant membership gaps. Source descriptions do not establish that every
provider variant is a separate US physical issue. All 384 have stable reviewed
collection publication mappings in the synthetic rehearsal. These totals are not
added to old shipped catalog counts as complete all-era coverage.

The baseline's 1,025-species / 220-provider-set registry is retained. Product
contents are unknown, guaranteed-card rows absent with completeness unknown.
Two Target observations retain separate original times; the newer extracted
USD 27.99 out-of-stock check is `2026-10-05T00:51:59.610643+00:00`, an explicitly
approximate original tool-read time. Seller, direct-versus-marketplace and shipping
remain unknown. No current purchasable offer was established.

206 new provider detail requests plus one reused Scyther detail, no retries.
Two distinct official page attempts stopped on access-error/iframe-only evidence.
One retailer offer page was read. Private source bytes, request outcomes, source
hashes and the dated extracted web observation remain under the slice source root.
No credential changes, bypasses, purchases or background acquisition occurred.

## Engineering checks

- Full local Python 3.14 suite: **449 passed**, one existing Starlette/httpx
  deprecation warning. No dependency change was made for that warning.
- Focused E1/E1b run before final additional conflict assertions: **38 passed**.
  The final full suite includes **25 foundation + 15 expansion checks**.
- Locked dependency synchronization, Python compilation, six JavaScript syntax
  checks, repository lint/format and diff-whitespace checks passed.
- New meaningful checks cover all 207 numbers, 384 variants, Trainer/Energy mapping,
  individual membership gaps, stable expansion/printing mappings, repeated imports,
  atomic failure after collection publication, metadata correction provenance,
  stale sealed/collection reviews, conflicting rollback, unrelated later observation
  preservation, frozen goals/copies and refusal of unbridged metadata drift.
- The full suite includes vintage, eBay, importer, account-isolation and existing
  collection/goal regressions. Hosted CI was not run.

## Synthetic copied-state evidence

Final root:
`/Users/michaelfuscoletti/dex-private/d1-e1b-20261004/rehearsal-final-3`.
Final evidence:
`/Users/michaelfuscoletti/dex-private/d1-e1b-20261004/rehearsal-evidence-3`.
Final recovery import ID: `28eb8fac-646d-456c-9209-914e55977740`.

`preservation.json` retains baseline row hashes and passing migration-repeat,
pre-existing-row preservation, idempotency, correction/reversion, rollback and
copied SQLite recovery assertions. `publication-mapping.json` retains 384 mappings
and additions/updates/archival impact. `report.json` separates numbered identities,
normalized variants, canonical mappings, evidenced memberships, actual bridges,
unknown contents and dated observation freshness. `synthetic-correction.json` and
`correction-review.json` retain the explicit before/after correction example.
The final root holds the real package under fresh sealed/bridge recovery versions;
the synthetic label correction was reverted.

Every pre-existing noncatalog account/copy/goal/photo/hunt/reservation row was
compared exactly; old catalog identities/mappings were preserved as reviewed
metadata was appended. Before/copied/recovered SQLite files are private. An initial
rehearsal failed during report hashing of a date after all preservation assertions;
that output was retained, report serialization repaired and fresh roots used for
subsequent runs. No owner root was read, migrated, reseeded or modified.

## Evidence and acceptance boundary

Real sources establish numbered identities, provider-described variants, canonical
mapping and standard checklist membership. Operator review is recorded; independent
Scyther end-to-end review was **not performed**. Automated checks and copied-state
SQLite rehearsals qualify engineering behavior only. Product source-access gaps
remain documented; current offer purchasability remains unestablished. PostgreSQL
runtime, hosted/device/release checks, owner installation and owner acceptance
were not exercised. Full D1/E1, all-era data and beta acceptance remain partial.
Next bounded work is E2a explicit Original 151 goal versions, as described in
[the slice closeout](../D1_E1B.md) and Desktop handoff.
