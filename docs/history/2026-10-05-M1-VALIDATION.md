# M1 validation — October 5, 2026

Scope: simplified collection-driven #001–251 Pokédex / Pack lookup and preserved Sandbox eBay. Evidence class: fresh disposable synthetic SQLite, retained public catalog/product evidence and sample eBay UI. Local dates are America/New_York; UTC records extend into October 6. No owner/hosted/PostgreSQL/full beta acceptance.

## Candidate entry and preservation

HEAD verified `16766b5c160c0bac370c1177387662646bf51b42`. E2d entry manifest hash `92405da6644bf881d641ef9f9c1e4425fd8675c508eb325badb5a0099fe657b1`, all 967 listed files checked before editing. The authoritative CSV hash remains `511dec82f4434e1e90ae27ec634e85e546f7559d43cc61d4cabec310d4ccc1b2`.

The later M1 request superseded narrow E2d. Audit final manifest/adjacent hash `e08018f2b85a10e58918c70761368b0d479c0653a59e5bf53e919714b2c900b1` matched. All 975 listed paths were checked: 965 matched, ten were the E2d implementation/closeout changes made in this same session, with no unexplained drift. Retained reconciliation: `evidence/e2d-20261005/m1-entry-reconciliation.json`. E2d was frozen separately with 539 passing tests and manifest hash `78fd5480e6d7dcbc58881a421223ab25732e167604ea21e9b98da22c5d27d785`. Its files/evidence remain historical; its source hashes do not describe the new M1 source revision.

M1 final delta is reconciled against that E2d freeze in `evidence/m1-20261005/final-preservation.json`; inherited unrelated/private paths must match. Final M1 identity is `evidence/m1-20261005/candidate.json` with adjacent `candidate.sha256`. The manifest freezes source, documentation, sanitized evidence and inherited source identity; it excludes itself and its hash to avoid self-reference. No commit or release was created.

## Engineering qualification

- **545 passed**, one existing Starlette/httpx deprecation warning, final full suite in **185.68s** on local Python 3.14. Log: `qualified-suite.txt`. Earlier 545-test runs are retained separately and do not replace the final run.
- **26 focused regressions passed** (28.30s); **6 M1 behavior tests passed** (7.43s). Full-suite final reran all of them after repairs.
- Locked dependency synchronization used `uv sync --offline --locked --extra dev`; no dependency acquisition. Python compile, every app/web JavaScript syntax check, Ruff lint/format and Git whitespace checks passed; exact commands/exit codes in `repository-checks.json`.
- Tests cover supplied 151/251 counts and exact Kanto missing set, owned/Johto targets, catalog/product gaps, Dark/EX source labels, account isolation, frozen legacy/collection research, retained changed-source successors, reselect/undo of an earlier source, exact-copy criteria independence, portable source/goal validation, tampered source rejection, repeat confirmation and save scope-version validation. Relevant existing regressions cover atomic rollback, tampered membership/lineage, journal conflicts, filters, exact contents/quantity uncertainty and classic eBay behavior.
- No local result establishes hosted CI's Python 3.12/3.14 matrix, PostgreSQL or owner acceptance.

## Ordinary browser journey

Fresh root `/private/tmp/dex-m1-20261005-state`, guarded localhost port 8027. Existing owner service at port 8011 was not operated. Synthetic credentials/backups/DB remain private; only sanitized reports and UI screenshots are retained under `evidence/m1-20261005/browser/`.

Screenshots 01–28 retain home; explicit Original 151 preview **137/14**; Original 251 **161/90**; selected 134/136/230/251 **3/4**; Dark Vaporeon details; Vaporeon correction **160/91**, confirm and undo; source import preview; exact 14 Kanto missing species; unknown-stock filtered save; saved reopen after server restart; byte-preserving source reselection; physical Rare Pokémon exact goal **0/325**; retained 251 version 1 and version 2; Dark Flareon/Clefable/Articuno-EX details; owned Eevee evolutions and Kingdra's explicit unverified booster gap; sample search/compare/reveal/save/reopen; filtered card details and scoped printing lookup; current **90 missing** from the supplied source; second-account private-goal isolation and foreign saved lookup denied; final saved 137/14 context.

No external seller link was opened. The eBay browser journey used labeled samples with no purchase link and a visibly unavailable guide comparison. It qualifies the preserved offline interaction and saved reopening, not live Sandbox seller review or current purchasability. Existing fixture regressions cover provider/seller behavior; no live provider was called.

The browser found two product issues and one synthetic setup omission: UTF-8 BOM removal changed the source hash; an inline wrapped printing link overlapped its neighboring button; the fresh setup lacked sample hunt files. Repairs preserved exact BOM/CRLF source bytes and journal source reselection, separated the card link, and included retained sample files in fresh setup. Final checks repeated the affected paths. The normalized intermediate source remains only in disposable history; the final current source is the exact supplied hash. A restore-report comparison was also corrected to normalize binary rows the same way as the original JSON snapshot. These observations are summarized in `qualification.json`.

## Post-browser audit and rollback

`browser/m1-verification.json` compares protected tables, exact copy attributes, photos and credentials (excluding routine last-login timestamps). Original goals, declarations, research and inherited hunts/import batches are retained. New operations/source/goals/research/sample hunt append to the disposable account without changing preserved physical inventory or public catalog/distribution/offer evidence.

The original pre-feature SQLite backup was restored into a second disposable database; **every original table matched** after the snapshot's binary normalization. Photos remain byte-identical in the original disposable root. Operation undo and blocked referenced-source rollback are independently tested. See [M1 reproduction and rollback](../M1.md). Do not restore any disposable database into the owner root.

`browser/provider-calls.json`: **0 calls**. No acquisition, purchases, credential/configuration changes, hosting or owner-installation writes. The guarded disposable servers were stopped after verification. No source budget was reopened. Historical owner state reported 207 physical copies; this milestone did not operate or rewrite it.

## Remaining gates and next action

M1's local engineering loop is delivered. M2 still needs target-specific English physical set/printing/distribution completeness at scale; M3 needs official exact products/quantities, Johto/vintage booster bridges and dated actual seller/stock/shipping/freshness evidence supporting an eligible real offer. M4 requires real-data integration and separate owner acceptance. All-era policy is not full catalog completeness, and source existence is not booster membership or buying availability.

One bounded next action: review the M1 final manifest, then perform a separately reviewed owner update with private backup and explicit 137/151 and 161/251 previews. M2/M3 integration details are in the closeout; new acquisition remains unauthorized.
