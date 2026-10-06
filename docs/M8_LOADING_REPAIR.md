# M8 copied-state loading repair — October 6, 2026

The narrow legacy identity batching repair renders the complete expanded Pokédex in **4.011 seconds** on a fresh authenticated copy. The owner app/data remain untouched. Exact owner review and installation remain separate.

## Diagnosis and repair

The owner personally signed into the separate test copy. Only ordinary `auth_user.last_login`, session and one login-audit append/sequence changed; credentials, permissions and all other 53 tables/file bytes stayed exact. A complete authenticated boundary was backed up, independently restored and copied for baseline and repaired runs. Entry verification matched M8 candidate `4d9884a1a74f631971ceda8748fda1e2ae0a3e78f31dddf09648d3dc88964a82` and all 2,402 files.

After sign-in, actual collection/parity responses completed200 in16.368s and5.788s respectively; the full DOM completion time was unmeasured. The remaining charged baseline timed navigation still had loading and zero rows at20.621s and21.734s. Its collection response was generated later, with cancellation recorded during bounded shutdown; this does not establish successful browser delivery. All failed/cancelled/invalid attempts are retained.

One profile per initial-data route showed repeated older-set reconciliation driving **32,260 collection queries / 10,845 parity queries**. `catalog_imports.rows_for` batched modern identities but used per-card legacy mapping, number, row and conflict reads. Frozen-goal validation and current coverage projections repeated those calls.

The repair batches legacy evidence locally within each `rows_for` call. It retains both legacy mapping suffixes, all candidates sharing a number, globally mapped rows, provenance matching, ambiguity refusal, provider mapping conflicts, global-ID repurposing guards and distinct nullable edition/finish/variant values. There is no cache across requests/accounts, schema/ID/policy change, source refresh or variant suppression. The source changes are limited to `catalog_imports.py` and `catalog_reconcile.py`; original bytes are archived and the repaired source identity was frozen before qualification.

| Profiled complete response | Baseline queries | Repaired queries | Repaired profiled time |
|---|---:|---:|---:|
| Collection | 32,260 | 1,696 | 3.400s |
| Parity projection | 10,845 | 657 | 1.679s |

Baseline profiled times139.799s/43.110s include substantial instrumentation overhead and are not ordinary browser timings. Both full JSON responses compare exactly after canonical JSON encoding. Private full responses/profiles/query details remain in the recovery evidence; public receipts retain hashes/counts.

## Actual browser qualification and limits

The valid repaired navigation began **2026-10-06T20:10:41.494Z**, on a freshly restored complete authenticated copy after the source freeze and copied runtime restart. One external monotonic clock measured navigation and actual DOM observations, including transport/polling overhead. Acknowledgement0.140s; loading at1.179s,2.200s,3.220s; complete rendering observed at **4.011s**.

The completion observation verifies **251 species rows,161 owned/90 missing,137/151 Kanto,24/100 Johto, both original version-1 goals and loading absent**. It meets the unchanged21-second gate. This is one valid full-render pass, not two.

The second charged repaired navigation was an operator error: reloading the visible tab after its current page moved to `/lookup/`. The server completed the independent251-target lookup200 in2.372s; the observer continued to21.133s seeking a nonexistent Pokédex grid. It provides **no second Pokédex timing result** and no evidence of a Pokédex regression. No further initial navigation occurred. The original assignment permits at most two navigations and requires a complete timely render; the first valid fresh-copy pass satisfies that loading requirement. A subsequent owner review should use a dedicated hidden tab and explicit `/pokedex/` navigation, with immediate wrong-route/authentication detection.

The shared combined four-target response was checked within the two-request bound. An older D9 HTML receipt has independently generated publication-journal IDs and derived scope IDs, so exact cross-root equality was incompatible. Its mismatch is retained without masking identity fields. The final same-state comparison uses the retained original source and repaired source on identical copied rows, with a common historical semantic clock and only CSRF-mask normalization. The [combined parity receipt](../evidence/m8-resume-20261006/combined-parity.json) records its outcome. Actual offer age is evaluated separately; no historical clock is claimed as current freshness.

## Regression, publication and preservation evidence

**107 distinct focused tests pass:101 existing and6 new.** The six new tests cover scalar/batch legacy identity equivalence, bounded batch query growth with1,001 cards, missing mappings, cross-set evidence, wrong provenance and ambiguous variants. Existing M7 null/global-ID/conflict guards, importer, frozen-goal, declaration, account-isolation, ordinary collection and saved-research checks pass.

The first test command referenced a nonexistent file and ran no tests. The first executed run had five new-test fixture failures because its synthetic snapshot contained no legacy cards;101 existing tests and the new batch-count test passed. Only the test fixture/mapping-variant mutation was corrected; all six new tests then passed. The first run completed its107 tests but was interrupted during final garbage collection. These operator outcomes remain retained, not silently replaced.

On repaired source, a separate fresh retained-owner publication copy passes all13 completed prerequisite inspections, exact D9 sealed/checkpoint publication, idempotency, invalid-reference/stale-conflict refusal and protection of historical data. Supported reversal checkpoint→sealed restores active sealed records, retains predecessor catalog rows and audit history, and preserves all33 protected tables/13files. Independent expanded complete-root restoration matches all57tables; it is distinct from supported reversal.

Every row in **all57tables and all13file bytes** matches the authenticated expanded baseline after baseline profiling/browser, repaired profiling/full-render browser, wrong-route restart observation and completed response comparisons. Source packages remain immutable:20sets/871numberedtargets/1,468records; expanded coverage68/220,3,975targets/6,535records. Copies207, marks286, original goals and allfour frozen saves including`8d2b8956-3e96-4fb1-a246-b63b2faa9a06` remain exact. New printings never enter historical frozen goals.

TokenMTG retains`2026-10-06T16:20:21.204089+00:00` and the inclusive24hpolicy. At20:13:47.465872UTC its retained observation is fresh, one recommendation remains eligible, shipping/tax/destination unknown and purchase-ready0. Stellar versions and Crown448descriptive status are unchanged. No provider/source acquisition, purchases, Production, owner update or hosted/PostgreSQL work occurred.

All copied runtimes are stopped; the owner-requested visible tab is retained for handback. Full private recovery roots remain under `/Users/michaelfuscoletti/dex-private/m8-resume-20261006`. Operator/source lint, format and compilation checks are retained. Current candidate/checksum is `evidence/m8-resume-20261006/candidate.json`; historical manifests and prior tracker/source bytes remain preserved.

One next assignment: [M9 exact repaired-candidate review and dedicated copied-browser qualification](M9_REVIEW_ASSIGNMENT.txt), only when dispatched. Verify the repair and fresh dedicated-tab loading before preparing a separate backed-up owner installation assignment. This repair does not install itself or establish broader beta/release acceptance.
