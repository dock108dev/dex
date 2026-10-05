# Catalogs and collection workflows

Catalog entries describe printings; physical copies describe what a user owns.
Shared catalog publication never silently rewrites ownership. Copies may retain
provisional identity and unresolved edition, finish or language information.

The synthetic seed publishes packaged metadata for the vintage sets and Gym Heroes,
plus explicitly synthetic test entries. The original app uses its own pinned
catalogs under `config/catalog/`. Metadata availability does not grant image,
pricing or trademark redistribution rights.

Users can request missing catalog coverage from a scan or provisional copy.
Private photos are available to reviewers only with explicit consent. Owner-role
review uses versioned packages, preview, verification, publication and rollback.
Resolved catalog identities update the same copy through the supported service
path; they do not create an extra owned copy. Package schemas and validation live
in `beta/catalog_imports.py`; request access rules live in `beta/catalog_requests.py`.
`scripts/prepare_tcgdex_package.py` converts a saved provider response into that
format; it does not itself qualify source rights or publish a catalog.

Collection additions, edits, removals, set batches and imports use preview and
confirmation. Operation IDs prevent duplicate confirmation; undo refuses to
clobber later edits. Imports report invalid rows before confirmation. Exports
retain copy identity, goals, binders and unresolved attributes.

The goal builder filters published entries by available game, selected sets,
card type and rarity. Pokémon goals can also select a Pokédex range within
#001–251. Species completion counts one eligible printing per species from those
filters; printing completion counts the selected catalog entries. Original 151,
Vintage 251 and Johto are presets in the same builder. Set and custom checklists
remain available.

Saving a goal freezes its membership and catalog version; create a new version
to change its scope. Species without matching printings stay in the denominator
and are shown as unavailable. A duplicate does not inflate unique completion,
and a copy outside the selected sets does not satisfy that goal. Exact-variant
policy requires resolved identity. Goal-scoped [eBay hunts](hunts.md) search the
missing members using current account-owned copies. Bargain searches can include
owned cards and use goals as optional catalog filters; searches never add inventory.

Guide scenarios are conditional, dated estimates with visible source and coverage;
unknown and stale values remain unavailable.

## Planned all-era goals and sealed products

The [roadmap](ROADMAP.md) requires a goal spanning all eras and a pack index
for missing species in the beta. [Beta requirements](BETA_REQUIREMENTS.md) define
D1–D5 data collection and E1–E6 engineering/acceptance. The catalog coverage and
frozen goal behavior above
describe the implementation today. Expansion will keep species completion,
exact-printing ownership, booster contents, included promos and retailer stock
as separate records. Official card/set evidence proves membership; documented
product contents prove which boosters are included; a dated offer check proves
observed availability. No single source establishes all three.

Data work must collect a versioned full species/set universe, all-era English
printings, canonical species mappings, booster membership, official product
contents and dated offers, with URLs, times, hashes and coverage gaps. Promo/deck-only
printings must not be labeled booster pulls. Initial retail scope is US English,
with separate market/language identities. The missing-18 report is a required
first walkthrough, not the catalog ceiling.

The broad goal accepts species-identified special/named/regional Pokémon printings;
existing vintage eligibility remains attached to its goals. Engineering must add
explicit reviewed goal-version updates as coverage grows, preserving existing
checklists, physical copies and exact identities.


## E1 public catalog foundation — October 4

`beta/sealed_catalog.py` now models full canonical species separately from legacy
collection eligibility, language/variant-specific printings, explicit booster
membership, exact product versions, pack counts, guaranteed inclusions and dated
seller-specific offers. Additive feature migration and the `beta.sealed_cli`
operator command provide offline validate, preview, verify, publish, report and
conflict-aware rollback. Imports never write copies or frozen goals; existing
catalog publication and eBay paths retain their behavior. Legacy metadata/goals
still cap at #251 pending E2.

[Versioned data](../config/sealed/2026-10-04/package.json) includes 1,025 official
species, 205 physical and 15 digital provider sets, plus one Scyther normal
printing and booster relationship. Official product contents are inaccessible;
counts and guaranteed inclusions stay unknown. The Target observation preserves
its October 4 checked time, unknown seller/stock/price/shipping and a 24-hour age
policy. Product existence and retailer descriptions do not qualify buy-now.

[Closeout and reproducible review](D1_E1.md) contains provider terms/access
assessment, source limitations, source hashes, existing versus E1 coverage,
missing-18 research, migration/recovery evidence and the next D1/E1b scope.
Full universe reconciliation/all-era printings and full E1 corrective/browser
integration remain open. Raw provider prices and source responses stay private.

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

`original-151-reviewed-v1` uses canonical #001–151 and current reviewed published
Pokémon packages, without the legacy normal-name eligibility restriction. Trainers,
Energy, cameos and unresolved species mappings remain excluded. The reviewed ten
vintage packages, Gym Heroes and English 151 produce 823 qualifying current
printings across 151 species in the disposable copied rehearsal; this is neither
complete all-era recognition nor confirmed distribution of every provider variant.
Frozen goal definitions retain exact memberships and review package references.
Publication only offers an explicit update; account copies alone derive completion.
An earlier version retains recognized resolved ownership after later archival;
current selectable publication coverage remains separate. The 177 extra-variant
booster gaps are unchanged and do not affect the species ownership policy.
[E2a closeout](E2A.md) records versions, references and qualification blockers.


## E2a runtime qualification — October 4

E2a runtime qualification now passes: locked synchronization, all three process
cleanup cases and the full suite (458 passed, one existing warning), plus compilation,
JavaScript syntax, lint and formatting. Fresh copied-state preservation and zero-call
frozen-hunt service assertions pass. E2a remains partial: renewed explicit browser
permission was requested and is pending; no server, navigation, UI captures or owner
acceptance occurred. [Qualification record](history/2026-10-04-E2A-QUALIFICATION.md)
retains commands, runtime, exact hashes and preservation evidence. Full E2 and beta
remain open.


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
