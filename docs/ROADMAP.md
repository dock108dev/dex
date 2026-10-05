# Product roadmap

The supported scope is a single-user localhost collection and eBay hunting app.
Accounts, physical copies, binders, import/export, undo, catalog review, filtered
goals and private saved hunts are implemented. The original app and existing
stores remain supported; there is no automatic ownership cutover.

Prioritize the search → compare → reveal → seller review → save/reopen loop.
Bargain searches include owned cards; goal searches use frozen missing targets.
Keep conditional valuations, partial lot coverage and catalog-average benchmarks
explicit. Search results never add owned cards automatically.

## Required beta scope — October 4, 2026

The owner's primary goal is to collect all original 151 species using qualifying
Pokémon cards from across the full TCG catalog, including modern expansions.
Vintage collecting remains available as a selectable preference and goal.
Expand the catalog across eras and species so other collectors can define their
own goals; the owner's immediate checklist remains #001–151. Keep exact printings
and physical copies distinct from species completion.

Keep eBay discovery for classic cards, singles, lots and vintage sealed products.
Add a sealed-product index that answers: "Which packs can I open for my missing
Pokémon, and where can I buy those products now?" The first useful delivery covers
the owner's missing 18, with Scyther as the end-to-end example. The pinned
original-app ledger currently shows 133/151; authenticated inventory is separate
and must supply its own account-specific missing targets.

### Required remaining implementation: broad goals and packs-to-open index

- Expand reviewed catalog coverage beyond the vintage set selection. Identify
  printings by stable set/card/language identifiers and map them to canonical
  species. Default the first shopping view to US English products; represent
  other markets/languages separately rather than merging their set lists.
- Add an all-era Original 151 goal alongside vintage presets. Version the goal;
  preserve existing frozen checklists, owned copies, saved hunts and exact-card
  history. Make eligibility for special, named and regional forms explicit in the
  goal policy; canonical species-identified Pokémon printings can satisfy the broad
  goal. Preserve vintage policies. Do not infer identity from artwork or substrings.
- Link species → qualifying printing → booster expansion → sealed product →
  retailer offer. Cover individual boosters, bundles, boxes, ETBs, tins and
  collection boxes where their booster contents are documented. Track guaranteed
  included promos separately from possible booster pulls. Mixed or variable
  assortments need exact product/version evidence before claiming coverage.
- For each offer, show seller, market, purchase link, price/currency, pack count,
  price per relevant pack where known, stock status and checked time. Distinguish
  Pokémon Center, retailer-direct and marketplace sellers. An official product
  page or release announcement alone does not establish current stock or active
  manufacture; unverified availability remains unknown.
- On each missing species, show all indexed compatible expansions/products and
  offer filters. Also show how many distinct missing species each expansion can
  contain, rarity and the cheapest qualifying printing where price evidence
  exists. Coverage is a possible target count, not an expected pull count; do not
  invent odds, guaranteed outcomes or expected completion costs from rarity.
- Keep the eBay path usable beside the new sealed-product view, with the owner's
  classic preference. Preserve reveal controls and explicit inventory confirmation.

Acceptance: Scyther leads from the account's missing slot to verified printings,
documented booster contents and dated offers; all 18 missing species have indexed
options or an explicit coverage gap. Saved reopening retains goal identity and
shows offer age. Existing vintage goals, exact ownership and eBay hunts continue
to work. Report imported catalog/retailer coverage explicitly: "all indexed
options" must not imply every product or seller worldwide. Qualify catalog
membership, product contents and live availability separately.

This is required beta scope; its bounded E1 foundation is delivered below and broader implementation remains open. The
[beta requirements](BETA_REQUIREMENTS.md) own acceptance: D1–D5 require real sourced
catalog, membership, product, offer and missing-18 data; E1–E6 require imports,
broad goals, pack discovery, offer refresh, reopening and integrated acceptance.
Complete all-era English coverage and the full species registry as well as the
owner's first walkthrough. The initial shopping market is US English; explicitly
report other-language coverage gaps.

Continue D1/E1b from the assessed universe and partial real Scyther chain below.
Catalog/product work proceeds independently of eBay activation.
A sample-only implementation cannot close data gates; a dataset without app
integration cannot close engineering gates. The Desktop `dex_next_steps.md`
contains the bounded handoff. Hosting and multi-user release remain separate work.

## Remaining work

- Establish populated Production Browse evidence for comparisons, reveal, seller
  review and reopening. Provider access is installation-specific; see [hunts](hunts.md).
- Restore keyboard focus after the reveal dialog closes, including failed reveals.
- Review whether catalog browsing and physical-copy management need clearer navigation
  before changing those destinations.
- Evaluate real-card recognition accuracy and further photo integration when collection
  coverage expands. Existing manual, fixture, API and CLI modes remain available.
- Hosting, LAN access, managed startup, invited users and real-device qualification
  remain deferred. Preserve the optional staging implementation and its separate gates.

Preserve uncertainty, explicit ownership confirmation, intentional duplicates,
spending reservations, source provenance and conflict-aware undo.

[Current setup](local-development.md) · [Catalogs and goals](catalogs.md) ·
[Status](PM_STATUS.md) · [Historical evidence](history/README.md).


## October 4 bounded D1/E1 delivery and next action

[Source assessment and E1 closeout](D1_E1.md) delivers the official 1,025-species
registry, a 220-record English provider manifest (205 physical / 15 digital),
one real partial Scyther chain and all 18 checklist research candidates. Existing
shipped coverage remains 11 sets / 991 printings, distinct from the new public
E1 layer's one printing. Additive typed imports, explicit command review and
publication/rollback, immutable source/offer observations and coverage reporting
are implemented. Original ownership and frozen goals are preserved.

D1–D5 remain partial; full E1 needs corrective metadata review and integration
with existing printing publication. E2–E6 remain outstanding. Official contents,
retailer seller/stock/price and independent Scyther review are open; no fresh
purchasable product has been established.

**Next engineering/data slice: D1/E1b.** Reconcile the English 151
expansion's 207 checklist identities, build the reviewed printing bridge and
metadata-correction path, and research one exact product's official contents.
Budget: one provider / one expansion / at most 207 card-detail requests, two
distinct official product pages and three retailer offers. Stop each denied or
unusable source. Require explicit unresolved/conflict reporting, preserved frozen
goals/copies, dated offer provenance and copied-state rollback/regressions.
See the closeout for executable scope and acceptance; broad goals and pack UI follow.

## D1/E1b — October 4 reviewed 151 publication

[Slice closeout](D1_E1B.md) supersedes the foundation's bridge/correction follow-on
boundary. All 207 English 151 numbered identities are reconciled, with 384 distinct
provider-described variants; 207 standard booster relationships are evidenced and
177 extra-variant membership gaps remain individual. Trainer/Energy records carry
no species mappings. `sealed_bridge.py` publishes 384 compatible collection metadata
records through existing owner review/audit/transaction services; existing IDs,
copies and frozen goals remain intact. Descriptive corrections retain before/after
meaning/provenance, reject stale reviews and refuse conflicting rollback. Identity
remaps and new observations require distinct reviewed records/versions.

The exact Target product retains unknown official pack/guaranteed-card contents.
A dated extracted USD 27.99 out-of-stock observation supplements the old unknown
observation; seller/shipping remain unknown and its approximate original read time
is labeled. No current purchasable offer is established. Missing-18 upstream
printing/standard-booster research progressed; independent chain review and owner
acceptance did not. [Validation](history/2026-10-04-D1-E1B-VALIDATION.md) records
synthetic preservation and exact candidate evidence. Full D1/E1 and beta remain
partial. Next: E2a explicit goal versions over reviewed published printings; no
automatic frozen-goal enrollment or ownership cutover.


## E2a — October 4 explicit Original 151 versions

E2a runtime qualification now passes: locked synchronization, all three process
cleanup cases and the full suite (458 passed, one existing warning), plus compilation,
JavaScript syntax, lint and formatting. Fresh copied-state preservation and zero-call
frozen-hunt service assertions pass. E2a remains partial: renewed explicit browser
permission was requested and is pending; no server, navigation, UI captures or owner
acceptance occurred. [Qualification record](history/2026-10-04-E2A-QUALIFICATION.md)
retains commands, runtime, exact hashes and preservation evidence. Full E2 and beta
remain open.

One next bounded action is **finish the E2a synthetic browser qualification** after
renewed explicit permission. Verify the new final manifest, then run the retained
create/progress/cancel/successor/reopen and sample-hunt walkthrough. Stop at the first
unmet gate; bind any repair to fresh tests/hashes and a fresh browser boundary.
No acquisition, pack-shopping implementation, live providers, owner-root writes or
hosting is authorized by this slice.

## Current execution handoff

E2a broad Original 151 goal versions are locally qualified through runtime checks
and the [synthetic browser walkthrough](history/2026-10-04-E2A-BROWSER-QUALIFICATION.md).
Next: E3a read-only pack discovery from retained reviewed data. Display unknown
product quantities and dated availability honestly; acquisition/retail refresh,
all-era coverage and owner acceptance remain required separate work.


## E3a — October 4 retained-data view

The authenticated Packs to open view is implemented from a selected Original 151
goal version or missing species. Frozen review references and stable publication
bridges bound account-derived missing-species coverage. Confirmed booster species
are deduplicated; unknown variants and guaranteed inclusions are separate. Exact
product contents and dated seller/stock/shipping gaps remain visible. No acquisition,
refresh jobs, inventory change or saved pack research was added.

Qualification is partial: focused/framework checks and copied-state preservation
pass, but browser access and loopback bind were denied; locked sync crashes and
three process-cleanup suite cases are blocked by sandbox denial of ps.
[E3a closeout](E3A.md) and [dated validation](history/2026-10-04-E3A-VALIDATION.md)
record actual evidence and the separate finite D3/D4a data handoff. E2a was already
locally browser-qualified per its browser record; full E2/E3 and beta stay open.

## October 4 E3a qualification

E3a passed synchronized-runtime checks (464 tests, one existing warning), the
[ordinary synthetic browser walkthrough](history/2026-10-04-E3A-QUALIFICATION.md)
and protected-state/photo preservation. Zero provider calls and no implementation
repairs. The owner installation was untouched. Next is the separate bounded
D3/D4a exact 151 Bundle contents/offer collection. Full E3/beta, owner acceptance
and the documented data/provider gates remain open.


## October 4 D3/D4a bounded source closeout

[Closeout](D3_D4A.md): four of seven maximum source attempts, no retries; official
gallery/151 and Pokémon Center unusable. Target exact UPC/TCIN/DPCI yielded a new
dated USD 27.99 out-of-stock observation; actual seller/shipping remain unknown.
Walmart/Best Buy/GameStop lack retained exact-product URLs and remain explicit gaps.
Official pack quantities and guaranteed inclusions remain unknown/unpublished.
Reviewed publication, rollback and descriptive correction rollback passed on a fresh
synthetic copy with protected rows/photos/old observations preserved. Focused browser
filter/reopen checks passed with zero acquisition calls; 46 relevant tests and required
checks passed. No implementation repair or owner-installation access occurred.
Full D3/D4/E3/beta remains open. Next: independent retained-evidence Scyther chain
review, recording downstream contents/seller gaps, with no new acquisition.


## October 4 D5a retained-evidence chain review

[D5a closeout](D5A.md) reconstructs Scyther #123, exact normal English 151 printing,
standard membership, retailer-described exact Bundle association and all three
immutable Target observations from hash-verified retained bytes. Reverse membership,
official quantities/inclusions, actual seller/shipping and current purchasability
remain unresolved. English product-version designation lacks an explicit SKU-language
label in the retained bytes. Codex reconstruction does not establish separate-person
review. The checklist has no parallel-set columns: an additive source annotation and
reviewed coverage erratum preserve the original evidence and correct that wording.
Official indexed-existence attribution is unsupported by the retained challenge.

Fresh synthetic publication/idempotency/rollback, protected rows/photo preservation,
46 relevant tests, six framework routes and ordinary browser Scyther/filter/reopen
checks passed; zero acquisition calls. No application code repair, owner-root access
or new acquisition. D3/D4a budget stays closed. Full D5, all-era coverage, 177 variant
memberships, populated eBay and beta/owner acceptance remain open. Next: separately
authorized D5b official exact-Bundle contents qualification, proposed two exact source
reads total, no retries/discovery; see D5a for references and stop rules.


## October 4 D5b exact official contents qualification

[D5b closeout](D5B.md): two exact official source reads consumed, zero retries;
both returned tool-inaccessible errors with HTTP status unknown. Exact official
contents/inclusions, US/English/version applicability and Pokémon Center SKU
equivalence remain unresolved. Two unusable source records only were validated,
reviewed, published and rolled back on fresh synthetic state; no product
relationship, quantity, guaranteed card or observation changed. The three Target
observations, frozen goals, exact printings, reverse gap, D5a erratum and protected
rows/photo bytes remain intact. Six projections are identical; the conditional
ordinary browser check was not triggered. 46 relevant tests and required checks
passed; six framework routes and zero application acquisition calls qualified.
A local evidence-helper repair restarted on a fresh copy; consumed reads stayed
closed. No application repair or owner-root access. Full D5/all-era/177 gaps,
separate-person review, populated eBay and beta acceptance stay open.

Current next action: **E5a retained-data saved Packs research**, pinning a frozen
goal version and immutable observation references for save/reopen/filter with
zero acquisition. Preserve uncertainty and original checked times; qualify on
fresh synthetic state with browser/preservation evidence. No identical official
source retry cycle. D3/D4a's budget remains separate and closed.

## E5a — retained-data saved Packs research, October 5

[E5a](E5A.md) implements account-local save/list/reopen/rename/remove for whole-goal
and species Packs research. Hash-checked server snapshots retain frozen goal/version,
reviewed catalogs, exact identities, selected filters, ownership context, unresolved
relationships and original observation times. Missing/archived/changed references
are explicit gaps; reopening substitutes neither current data nor a successor.

468 tests and required code checks passed. Fresh synthetic SQLite migration,
repeatability/rollback, actual browser save/reopen, server restart, three Target
timestamps, predecessor, uncertainty, account isolation and selected removal are
qualified. All protected application rows and photo bytes are preserved; research
rows and login bookkeeping are classified separately. Zero acquisition calls.
[Validation](history/2026-10-05-E5A-VALIDATION.md) retains both the initial helper
failure and fresh repaired qualification. The owner installation was untouched.

E5a locally synthetic qualified; full E5/E4 and beta remain open. Official contents,
current purchasability, all-era coverage, separate-person review, populated eBay
and owner acceptance remain open. Next bounded action: E4a replay-only explicit
bounded refresh orchestration; no live adapter activation/acquisition until a
supported source path is separately authorized.
