# October 5, 2026 — D1c retained coverage validation

Baseline HEAD `16766b5c160c0bac370c1177387662646bf51b42` and E6a candidate
SHA-256 `0a9f5f263fb7799b9997ffd6f6dff0ebd907932cfc187bb6791b6f8f6c405883`
matched; all **755 files matched before work**. No applicable AGENTS.md was found
in repository/ancestors. Existing implementation, evidence and uncommitted work
were preserved. Only the inherited PM status, roadmap, history index and Desktop
tracker are intentionally changed; all other inherited hashes must still match.

[D1c](../D1C.md) and `evidence/d1c-20261005/` contain the exact retained-input lock,
per-set reconciliation, exact gaps, human-readable 193-set missing list, derived
series summary, source verification and check outputs. All 220 IDs occur exactly
once; 205 physical / 15 digital, 12 complete numbered sets, 193 absent physical
sets, 15 absent digital sets, zero observed conflicts. Physical totals:
21,484 expected provider cards = 1,198 reviewed numbered identities + 20,286 gap.
Combined physical/digital totals: 23,964 = 1,198 + 22,766. Reviewed catalog records
are 1,375, distinct from numbered count; 207 standard 151 booster memberships are
supported and 177 extra-variant relationships remain individually unresolved.
Variant completeness is unknown/partial for all 12 covered sets.

Actual validation:

- `python3 scripts/reconcile_d1c.py --check`: regenerated JSON and exact missing-set
  text match retained outputs; all input hashes, raw universe/series counts and IDs,
  151 raw-detail retained hashes, 384 bridged publication identities and aggregate
  totals pass. No database or network access.
- `uv run --no-sync pytest -q tests/test_d1c_reconciliation.py`: **5 passed**.
  Tests use retained inputs, reject source drift before any output and inject
  series-count, duplicate-printing and wrong-language conflicts. Affected joins
  contribute zero confirmed numbered coverage while unrelated sets remain intact.
  Digital promo labels remain digital; all 177 membership gaps stay represented.
- Focused lint, format and Python compilation pass. `git diff --check` passes.
  No full application suite was rerun; application implementation is unchanged.
- A reporting-helper edit attempt failed locally before writing a file; it was
  corrected and all focused checks rerun. No source data or acquisition involved.

No new source reads, browsing/discovery, imports, publication, provider activation,
credentials, catalog refresh, purchases, hosting or deployment. Retained file reads
only; owner installation was not accessed. Raw historical Gym Heroes and pinned
September source checkout hashes are referenced as historical claims; package and
manifest bytes are reverified, not substituted for a fresh source collection.

The selected next tranche is English Detective Pikachu `tcgdex:en:det1`, 18 expected
numbered cards, new Sun & Moon series coverage. Its exact card/species/variant and
membership data are absent. D1C.md carries the executable separately scoped D1d
handoff: 19 attempts maximum, no retry/discovery, finite time/byte/variant limits,
source normalization, separate unknown membership and fresh synthetic review/
rollback/preservation acceptance. This selection consumes no acquisition authority.

Final candidate: `evidence/d1c-20261005/validation-final/candidate.json`, with its
SHA-256 companion. It carries the inherited 755-file manifest plus all new D1c
artifacts; final preservation evidence classifies the four intentional tracker
changes. Candidate creation excludes its own manifest and SHA companion to avoid
self-hashing. HEAD alone does not identify this working-tree result.

Full D1/all-era coverage, official contents, real availability, separate-person
review, populated Production eBay, PostgreSQL execution, beta/owner acceptance,
hosting and release remain open. No owner or independent source acceptance is claimed.
