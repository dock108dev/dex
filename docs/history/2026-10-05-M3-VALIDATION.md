# M3 validation — October 5, 2026

Evidence timestamps are October 6 UTC; delivery date follows America/New_York. Baseline HEAD is `16766b5c160c0bac370c1177387662646bf51b42`. Entry M2 manifest SHA-256 `424e25975469216a44c5a68113e08a36b484a163fa45bfeb74ab9eea2db97b5d` and all 1,433 files matched. `evidence/m3-20261005/validation/entry-and-drift-reconciliation.json` records entry and the 16 explained inherited-file changes; source packages are unchanged, with no unexplained drift.

## Final checks

Final full suite: **560 passed**, one retained dependency deprecation warning. The final full-suite result is retained in `evidence/m3-20261005/validation/full-suite.txt`. Focused final distribution/product tests: **33 passed** (`focused-distribution-final.txt`). Repository lint and formatting passed; locked offline dependency audit, pinned M2 input check, Python compilation and JavaScript syntax checks passed. Local Python is 3.14; hosted Python 3.12/3.14 and PostgreSQL execution are not claimed. The full-suite's existing Starlette/httpx deprecation warning is retained with its output.

## Ordinary browser evidence

Fresh root `/private/tmp/dex-m3-20261005-2`, copied synthetic SQLite, loopback `127.0.0.1:8033`; no owner installation access. Synthetic credentials stay in the private root. The source guards recorded **zero acquisition calls across five server starts**.

- `01-review.png`, `02-publication.png`: exact retained/manual schema review, explicit verify/publication and unknown fields.
- `03-mixed-lookup.png`, `mixed-dom.txt`: owned Vaporeon, missing Jolteon, Johto Kingdra; exact product/version/market, mixed quantities, guarantees and unknown official real-product contents.
- `04-saved.png`, `05-restart-reopen.png`, saved/restart DOM: filtered USD/max-item-price/sort comparison, save and new-process reopen with original references/times.
- `06-goal-filter.png`, `printing-dom.txt`, `12-missing-target.png`: explicit source-bound custom goal, exact Vaporeon printing lookup and missing-only Jolteon scope.
- `07-correction-preview.png`, `09-readable-conflict.png`, `10-rollback.png`: before/after preview; two verified alternatives; first publication; second refused with readable reason; rollback. The saved snapshot retained its original distribution and explicit changed-reference gap during correction (`corrected-saved-dom.txt`).
- `11-account-isolation.png`, member DOM: second account's private saved list excludes owner research. Focused endpoint regressions verify direct saved access 404, owner review 403 and CSRF enforcement.
- `13-offer-outcomes.png`, `offer-outcomes-dom.txt`: dated in-stock, out-of-stock, stale and unknown offers; direct versus marketplace sellers, known/unknown shipping, separately guaranteed inclusion.
- `14-final-correction-publication.png`, `15-final-correction-rollback.png`: final stricter evidence rule replayed through browser publication/rollback with explicitly new distribution evidence.
- `16-current-synthetic-behavior.png`, `fresh-behavior-dom.txt`: within-window synthetic behavior eligibility is true, while real recommendation eligibility remains false. Earlier fixture observations were future-dated relative to early browser steps and correctly did not qualify then; the final check used the same immutable dates after that instant, without refreshing or rewriting them.
- `current-comparison-dom.txt`: explicit new current-data lookup carries saved scope/filters without changing saved bytes. `product-comparison-final.png` is the compact comparison preview.

Every synthetic case is behavior-only; no real stock or official contents evidence was manufactured. No external retailer/source links were opened. Detailed reproduction is `evidence/m3-20261005/REPRODUCTION.md`.

## Coverage, journals and preservation

`retained-target-product-coverage.json` enumerates all 251 targets from pre-synthetic retained records: 251 with catalog metadata, 152 with sealed printing identities, 151 with unverified product associations, zero documented product chains and zero eligible current offers. The missing sealed bridges are distinct from researched absence; no absence was established. M2 remains 916 target identities / 1,077 supplied variants, 192 unassessed physical sets plus 15 digital, 132 Gym Heroes mapping exceptions and unresolved variant/distribution completeness.

`target-product-coverage.json` records the separately fabricated cases; `catalog-coverage.json` records M2. `publication-correction-rollback.json` is a sanitized four-journal summary with stable IDs, package hashes, state and before/after records. The conflicting review remains verified and refused; both distribution corrections are rolled back. The base synthetic product package remains published solely in disposable state. `saved-reference-audit.json` retains snapshot hashes, goal versions, filters and original observation times.

`preservation.json` verifies protected table rows, all disposable copies, photo hashes, credentials and inherited goals/research, and restores every table from the original database backup to a separate fresh SQLite file. Collection source remains **137/151 Kanto, 161/251 total, 14/90 missing and 286 marks**. The owner's 207 copies were not accessed or changed; this is not an owner-state rehearsal/application.

## Retained failures and boundaries

Setup attempt 1 used checkpoint mode but asserted whole-batch publication; its evidence was retained under `attempt-1/`, and the helper selected atomic mode before fresh-root restart. Initial browser opening before server start returned connection refused. Verification attempt 1 omitted a test goal's collection source and failed before publication; `verification-attempt-1.txt` retains the limitation, and explicit-source verification passed. Initial JSON conflict feedback did not render in the in-app browser; the readable page repair passed the repeated browser journey. Final evidence audit retained a three-failure regression run under `validation/retained-failures/`; corrected claims now require newly added applicable official evidence, and the fabricated deck fixture supplies explicit distribution support.

Real source/product completeness, current purchasability, independent review, PostgreSQL/hosted matrix, owner installation application and owner acceptance remain open. No acquisition, purchase/bid, Production eBay activation, hosting or credential/environment change occurred. Existing budgets stay closed. Final candidate: `evidence/m3-20261005/candidate.json` with adjacent `candidate.sha256`.
