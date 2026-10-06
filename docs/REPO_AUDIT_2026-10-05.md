# Repository and beta-scope audit — October 5, 2026

## In-progress source changes observed during audit

After the verified entry check, concurrent work added `collection_goals.py` / `test_collection_goals.py` and changed goal, collection, hunt and Packs integration. The new code describes an `original151_collection` policy with frozen account-local declaration sources; it still targets 151, not the full251 custom-goal milestone. Preserve it and reconcile its delivery status before M1 implementation. No completed E2d closeout was present at inspection. The 27-test run does not qualify this evolving candidate. Entry-time findings below are retained as the baseline; collection-based151 integration is now **in progress/unqualified**, not wholly absent. Broader #001–251 lookup/custom goals and simplified navigation remain required.

## Audit boundary

Source/evidence/documentation audit of HEAD `16766b5c160c0bac370c1177387662646bf51b42` plus inherited uncommitted work. All **967** files from the E2d handoff matched before editing; entry manifest SHA-256 `92405da6644bf881d641ef9f9c1e4425fd8675c508eb325badb5a0099fe657b1`. Worktree status is retained in `evidence/repo-audit-20261005/entry-audit.json`. No applicable AGENTS.md was found in the repository; the earlier repository audit also recorded no ancestor instructions. No application implementation, owner database, credentials, source observations or historical manifest was changed. This is not a new owner browser or live-source qualification.

## Corrected product contract

Beta card/pack identification covers canonical Pokémon **#001–251 across the full English physical TCG universe, every era and set**, independent of owned sets or missingness. Above-251 species metadata remains compatible but their card/pack research is outside beta scope. US English remains the initial shopping market; other languages are tracked expansion work.

The simple app is **Pokédex, Pack lookup and Sandbox eBay**. Pokédex owns species/card filters and pivots, card details, ownership maintenance, and **visible custom goal creation/progress/goal filters**. Original 151, Original 251 and custom in-scope targets are useful presets/scopes; supported card/set/type/rarity goals retain their policies. Goals also filter pack lookup. Owned species must be browsable for pack contents without declaring them missing. Version/source/review machinery stays underneath, with old records/routes preserved.

Newer-product buying recommendations require sourced exact contents and dated seller evidence, with readable reasons and uncertainty. Coverage is possible species presence, not expected pulls. Sandbox eBay is preserved; Production activation is future work, no longer a simplified-local-beta gate. Sandbox evidence does not establish live listings.

## Findings

| Area | Checked current position | Required follow-on |
|---|---|---|
| Owner collection | Replacement CSV checked: 137 Kanto + 24 Johto = 161 species; 90 missing, 286 marks. Prior owner application/browser closeout preserves 207 copies. | Supported UI import/correction and consistent goal/lookup ownership, not bespoke scripts per export |
| Goals | `collection.py` supports legacy and original151 goals; `broad_goals.py` reviewed policy and progress hard-code 151 and resolved physical copies. | Collection-based 151/251/subset custom goals inside Pokédex; explicit updates and policy separation |
| Pack lookup | `packs.py` accepts only original151 and calls broad_goals progress on physical copies. | #001–251 and goal-filtered lookup, independent owned-species browse, corrected current-missing scope |
| Saved research | `pack_research.py` pins supported goal/version and retained observations; old/new snapshots and filters were qualified historically. | Compatibility with new goal/source policies and simplified entry points |
| Metadata/import | E1c supports full registry/bridge; reviewed atomic publication/correction/rollback exist. | Repeatable useful batch imports and target-specific reconciliation rather than per-small-set milestones |
| Catalog completeness | E1c retained report: 13 numbered-set demonstrations, 192 absent physical sets. Old reports count full-set numbered records. | Compute #001–251 target completeness across the full dated universe; old full-set gaps are not the new target gap |
| Distribution/products | Retained official-content gaps and unresolved variant/Detective Pikachu distribution remain. | Separate sourced printing membership, exact product contents, guaranteed inclusions and mixed uncertainty |
| Offers/refresh | Replay-only refresh and retained stock/freshness/price filters exist. Live acquisition unavailable in ordinary mode. | Reviewed real-source imports and supported access adapters; at least one genuine current compatible offer |
| eBay | Owner explicitly retains Sandbox; historical Production access/compliance gap is separate. | Preserve/labeled Sandbox flow; no forced Production switch or credential changes |
| Interface | Existing parity navigation exposes numerous collection, goal and research pages. | Consolidate ordinary navigation while retaining legacy/admin routes and stored data |
| Acceptance | Many local/offline slices qualified; PostgreSQL, source coverage, live offers, independent review and full owner/beta acceptance remain open. | Product milestone qualification; do not substitute fixture success for live/source evidence |

The supplied missing-90 companion previously matched all missing IDs. Current Kanto missing: Venusaur, Pidgeotto, Pidgeot, Alakazam, Gengar, Hypno, Chansey, Kangaskhan, Mr. Mime, Scyther, Gyarados, Lapras, Jolteon, Moltres. Johto has 76 missing. Original missing-18 and earlier 133/135 counts are historical.

## Current priorities

**M1:** simplified Pokédex/custom goals/ownership → pack lookup → supported recommendation displays → saved reopening, plus preserved Sandbox eBay. E2d is a component. Deliver a usable copied-state candidate, not an isolated correction.

**M2:** repeatable all-era #001–251 catalog pipeline and data collection. Assess every in-scope set, prioritize recent useful and current-missing batches across eras, retain per-set target counts and exceptions. Above-251 rows may pass through without required research.

**M3:** real official product contents and seller offers integrated through reviewed imports/adapters. Research every current missing target and extend the full251 index; explain unavailable or uncertain results. Existing consumed acquisition budgets remain closed; this audit authorizes no new source requests.

**M4:** integrated local owner walkthrough and fixes; retained Sandbox eBay evidence with clear limitations. Production access, hosting and invited-user release are separately scoped. PostgreSQL qualification remains separately recorded.

The lead engineer owns engineering and integration. Codex owns sourced catalog/product/offer research and evidence reconciliation; owner feedback belongs to the owner. Source work and engineering proceed as separate workstreams; no agents were delegated in this audit.

## Verification and document changes

Targeted run started against the entry state: **27 passed in 24.58s** across ownership declarations, broad goals, Packs and saved Pack research. This verifies existing behavior; no M1 implementation is claimed. Historical 533/full-suite and other counts belong to their exact candidates. Documentation whitespace, local links and final manifest are checked separately. Subsequent source changes were observed, so these test results are not a qualification of the closing in-progress source. No new full suite, live request or owner walkthrough occurred.

Updated requirements, roadmap, PM status, architecture/ownership SSOT, catalog guide, README and Desktop handoff. Active histories now explicitly mark older plans/totals/next actions as superseded. The narrow E2d prompt remains with a superseded banner; `docs/M1_LEAD_ENGINEER_PROMPT.txt` is the active broader prompt. Original evidence/manifests remain intact.

Final audit candidate: `evidence/repo-audit-20261005/validation-final/candidate.json` and `candidate.sha256`. This freezes the updated documentation and inherited implementation; it does not claim engineering delivery beyond the audited baseline.
