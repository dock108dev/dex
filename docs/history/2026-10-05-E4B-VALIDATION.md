# E4b validation — October 5, 2026

**Local offline engineering qualified.** Offer filters, deterministic comparison,
explicit link reasons and frozen saved compatibility are implemented. This record
establishes no real purchasable offer, live-source or full-beta acceptance.
[Behavior and policy](../E4B.md).

## Baseline and identity

HEAD remains `16766b5c160c0bac370c1177387662646bf51b42`. At entry, E4a manifest
`evidence/e4a-20261005/validation-final/candidate.json` SHA-256
`8627d3ae53e1db24d1b11231092589861e5d076722be89f4f1823f1596ec7012`
and all **557 files** matched. No applicable AGENTS.md was found at repository or
ancestor paths. Required beta contract, Desktop tracker, E3a/E5a/E4a and validation
records were read. Inherited uncommitted E4a source/docs/evidence remain preserved.
No owner-root access, credentials/provider configuration change, commit or push.

The final working candidate is `evidence/e4b-20261005/validation-final/candidate.json`
with `candidate.sha256`. It binds source, docs, Desktop tracker, inherited packages
and evidence, and this validation/browser/preservation run. Earlier manifests remain
intact; HEAD alone does not identify this uncommitted candidate.

## Tests and checks

Final focused comparison checks: **24 passed**. Relevant regression: **63 passed**
on the preceding policy revision; final full suite covers the final policy refinements.
Final full suite: **499 passed**, one existing Starlette/httpx deprecation warning,
163.36 seconds. Locked dependency synchronization, Python compilation, six JavaScript
syntax checks, Ruff lint/format (188 files) and Git whitespace checks passed.
Final outputs are `full-suite-final.txt`, `sync.txt`, `compile-final.txt`,
`javascript-final.txt`, `lint-final.txt`, `format-final.txt` and `diff-check-final.txt`
in `evidence/e4b-20261005/`.
Local runtime is Python 3.14; no hosted/Python 3.12 result is claimed.

Coverage includes all 128 stock/age/maximum/sort combinations, explicit known zero,
unknown price/currency/shipping/time, comparable and incomparable prices, empty
results without coverage loss, normalized timestamp selection/ties/full history,
exact 24-hour boundary and one-microsecond deviations, future/naive/invalid times,
source failure versus explicit unknown-stock observation, safe/unsafe URLs,
source/offer/purchase policy reasons, synthetic exclusion, hypothetical verified
backend branch, old/new saved snapshots, aging frozen selection, account isolation,
server validation, unchanged ownership and original observations, and no acquisition.
Existing E3a/E5a/refresh tests cover verified exclusive/mixed pack costs, failure
outcomes, predecessor scope, real CSRF and retained eBay behavior. The sealed report's
legacy diagnostic flag now uses the same conservative eligibility function; a
synthetic in-stock override no longer marks buy-now true.

Earlier focused harness attempts exposed a missing imported snapshot fixture and an
unfinished policy-branch implementation, plus import ordering. These were corrected;
initial failures remain in `focused-tests.txt`, and final passing evidence is in
`focused-tests-final2.txt`. The earlier 496-test passing run predates the last URL,
unknown-value and diagnostic refinements; it is retained without substituting it for
the final-candidate suite.

## Disposable state and preservation

Seed: `/private/tmp/dex-e4b-20261005-seed`.
Copied state: `/private/tmp/dex-e4b-20261005-copy`.
E5a's existing copied-state setup reconstructed published reviewed packages and the
predecessor/successor, then explicitly enabled existing saved-research storage.
E4b introduces no schema migration. The helper created one synthetic old v1-shaped
snapshot before the preservation boundary, with E4b fields removed and integrity
hash recomputed; this is compatibility evidence, not an owner's saved research.

Complete all-table comparison and photo-byte verification passed. Protected copies,
goals, hunts, scans/reservations, binders, source records, original Target observations,
imports, catalog audits and mappings are unchanged. The old snapshot row, content
bytes and hash remain identical. Three intentional new research rows hold whole-goal,
Scyther and predecessor scopes. Authentication changes are only last-login,
sessions/auth logs and their SQLite counters; user identities/passwords/permissions
are identical. Reports: `rehearsal/{before,after,preservation,saved-preservation}.json`.
Earlier candidate file hashes also protect inherited saved/evidence bytes.

Acquisition counter is **zero across two server starts**, guarded for HTTP-client
sends, eBay search and URL opening. No live adapter or recurring task was introduced.
PostgreSQL execution remains unqualified; no owner installation was accessed.

## Ordinary browser walkthrough

Actual snapshots/screenshots and assertions are retained in
`evidence/e4b-20261005/browser/`:

1. Whole-goal version 2 shows 151 possible missing species and the retained Bundle.
2. Scyther and English 151 expansion remain selected through out-of-stock/USD 28
   filtering and comparable-price sorting. One confirmed species remains visible.
3. Expand unresolved reverse membership, link reasons and all three Target
   observations. Exact original timestamps, unknown seller/shipping/contents,
   approximate tool-read quality and backend/cache-time uncertainty are visible.
   The validated Target URL is inspected without navigating to it.
4. In-stock, unknown-stock, older/unknown-time and USD 27 filters yield explicit
   empty offers while confirmed Scyther coverage stays one; within-24-hour and
   out-of-stock views retain the offer. Reset retains species, expansion and version.
5. Save/reopen filtered Scyther, whole-goal and predecessor research. The saved
   settings remain visible and the predecessor has no modern membership match.
6. Reopen the synthetic legacy snapshot with all/checked defaults and all original
   history. Stop/restart only the synthetic server; reopen filtered Scyther,
   predecessor and legacy research through the ordinary saved list.
7. Refresh reports live refresh unavailable. Member account sees none of the admin's
   research; direct saved URL returns Not Found. Framework checks also deny cross-account
   Packs and saved access and preserve classic eBay selected-goal links.

Console warning/error capture is empty. An initial tab was opened before the server
started and returned connection refused; a fresh tab to the running server worked.
The attempted assignment to the failed tab binding was undefined; binding the newly
created tab resolved it. No application/security change followed. Temporary tabs were
closed and the two synthetic server processes were stopped; copies/evidence retained.
Browser testing is local synthetic evidence, distinct from owner or separate-person review.

## Remaining gates and one next action

Official contents, seller/backend availability/current purchasability, all-era
coverage, separate-person review, populated Production eBay, owner and full beta
acceptance remain open. E4a/E4b qualify offline engineering only; live refresh remains
unavailable. No source collection/discovery/retry, provider activation, purchase/bid,
hosting or deployment occurred.

Next bounded action: **E6a offline integrated goal → Packs → filtered save/reopen
and retained classic-eBay qualification**, on a fresh synthetic copy with zero
acquisition. Verify the E4b candidate first, preserve protected rows and frozen
snapshots, and report integrated offline results separately from all real-source gates.
