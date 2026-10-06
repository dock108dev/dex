# Catalogs, collecting goals and pack lookup

## Scope and identity

The beta researches Pokémon #001–251 across indexed English physical TCG eras.
Original 151, Original 251 and custom in-scope targets are collecting scopes,
not claims of complete catalog coverage. The canonical public registry also
retains species through #1025 for metadata compatibility. Digital, unreleased or
other-language records do not establish English physical booster coverage.
US English is the initial shopping market.

Catalog entries describe printings; physical copies describe owned objects.
Species declarations are separate source-based ownership records. Unknown
finish, edition, language, distribution or exact identity remains unknown.
An expansion's numbered checklist, supplied variants, target-species coverage
and confirmed booster relationships are different measures.

The synthetic seed publishes packaged vintage metadata and explicit synthetic
entries. The original app uses separate catalogs under `config/catalog/`.
Metadata availability grants no artwork or pricing redistribution rights.

## Collection and goals

Pokédex provides region, ownership, indexed set/era, card name/number, card type
and rarity filters. Missing metadata can remain visible. Create/name a goal,
select 151/251/subset targets or supported physical card criteria, inspect
progress and open pack lookup from a species, printing or selected targets.
Compatibility Collection and Goals routes remain available.

Collection additions, edits, removals, batches and imports use preview and
confirmation. Operation IDs prevent duplicate confirmation; undo refuses to
clobber later edits. Imports report invalid rows before confirmation. Exports
retain copy identity, goals, binders and unresolved attributes.

Goal definitions freeze exact membership, source references and policy. Published
catalog growth can be reviewed into a successor version; old checklists remain
fixed. Declaration-based species completion and resolved physical-copy/printing
completion follow their respective stored policies. Trainer/Energy identities do
not create species completion. Legacy vintage goals retain their name/eligibility
rules; broader species goals can include identified regional or named Pokémon.

## Reviewed publication

Users can request missing catalog coverage from a scan or provisional copy.
Reviewers can see private photos only with explicit consent. Owner-role review
uses versioned packages, preview, verification, publication and rollback.
Resolving a provisional copy updates that object rather than creating a second copy.

`beta/catalog_imports.py` validates collection packages;
`beta/catalog_requests.py` owns request access. The offline
`scripts/prepare_tcgdex_package.py` converts a saved provider response; it does
not fetch data, establish source rights or publish a catalog.
`beta/sealed_catalog.py` validates species, printing/distribution, exact product
versions, pack counts, included cards and immutable dated seller observations.
`beta/sealed_bridge.py` publishes compatible collection metadata transactionally.
`uv run --no-sync python -m pokemon_hunter.beta.sealed_cli --help` describes
offline validation and explicit review.

`/catalog-pipeline/` coordinates existing import journals with resumable batch
checkpoints. `/catalog-coverage/` reports reviewed universe/alias coverage and
unassessed sets; current profile inputs are under `config/catalog-pipeline/`.
Corrections retain before/after sources, reject stale reviews and refuse conflicting
rollback. Identity remaps and new observations require distinct reviewed records.

## Pack lookup and saves

`/lookup/` accepts a goal, target species or exact printing, with all/missing scope.
It supports owned species as well as missing targets. Confirmed booster membership
bounds possible species coverage. Exact documented product contents determine
which boosters are relevant; guaranteed included cards are counted separately
from possible pulls. Unknown/mixed contents and out-of-scope included species do
not add target guarantees. Coverage and rarity do not establish pull odds or
expected completion cost.

`/product-review/` supports reviewed products, distribution corrections and seller
observations; `/api/product-coverage/` distinguishes indexed metadata from missing
bridges. Stock, price, seller, shipping and tax can remain unknown. Freshness uses
the original check time, never page load, import or report generation. Only
supported dated evidence can qualify a recommendation. Purchase-ready remains
unavailable; a source link is not a purchase attestation.

Save lookup retains selection, ownership, coverage, references, filters and offer
timestamps privately. Reopening makes no provider calls and keeps its snapshot
fixed, even if current catalog references are unavailable. Comparing current
indexed data opens a separate lookup. Renaming/removing a saved lookup does not
change ownership or public catalogs. Live sealed-offer acquisition is unsupported;
refresh tools provide synthetic replay only.

All-era variant/distribution coverage and current purchasability remain incomplete.
Inspect catalog gap reports and individual evidence rather than treating a missing
match as proof that no card or product exists. Broader staging/deployment and
real-provider qualification are separate from synthetic behavior tests.
