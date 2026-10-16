# Catalogs, collecting goals and pack lookup

## Scope and identity

The authenticated app researches Pokémon #001–251 across indexed English physical TCG eras.
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

The authenticated local image adapters distinguish canonical Pokémon artwork,
card-group identification references, explicitly unavailable exact selected-child
assets and authorized private copy photos. The [image contract](artwork.md)
defines the four roles, pinned mappings, source restrictions and fallback behavior.
References remain mapped independently of possession. Literal names such as Dark,
Light and named Pokémon do not change species art or canonical identities.
Mapping coverage and remote image availability remain independent of catalog coverage.
Catalog entries stay visible if artwork is unavailable.

Wizards promo identities retain individual date evidence and gaps. Numbering and
set-wide dates do not establish through-2001 coverage. Standard set/number scans establish no edition, finish or
physical-copy image. Source software/metadata licenses grant no artwork rights;
private reference use remains local, with public/staging remote
reference exclusions and no bundled/exported image bytes.

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
match as proof that no card or product exists. A catalog match alone does not
establish current provider availability.

## Scoped release evidence

Scoped completion reads the hash-checked current coverage profile and reviewed aliases through
exact provider/language/set mappings. Its retained English dates describe that
source's English set release; US/UK and physical-edition applicability remain
unresolved. ISO year/month/day precision is an interval. Only fully contained
intervals confirm dated eligibility; a boundary-spanning interval stays unresolved.
Pokémon generation, copyright and capture time never substitute for release dates.

Rolling promo-series start dates are excluded from individual-card dating. Published
card attributes and exact-date joins may lack an admissible per-card release record;
those cards remain Unknown. Sets without a reviewed exact provider-key join also
remain unknown. The Pokédex reports printing coverage separately from its stable
target count.
No acquisition or catalog publication runs. Unknown date can be selected explicitly;
unknown records never confirm a dated criterion. A conflicting conjunction returns
zero confirmed completion without removing targets.

Sets/expansions implement pack type. Product-family membership and the pack an owned
card came from are not inferred. Card category, rarity and literal finish choices
use indexed values only. This catalog supplies Pokémon as its species category;
EX/GX/V subcategories and elemental types are not established by the retained
published attributes. Unsupported categories remain a coverage gap.

## Catalog choices during entry

Manual and photo-assisted entry read the published catalog through
`collection_catalog.catalog_entries` and `card_groups.build_groups`. Artwork mappings
and retained source enumeration do not publish a set or make a printing selectable.
A missing provider-key mapping is an identity or coverage gap, not proof that the
physical set does not exist. Supplied variants do not enlarge a numbered checklist.

Entry uses exact set names and uniquely retained `catalog_sets.aliases` or external
set mappings within the chosen game and language. Collector numbers match exactly
first, then use bounded padding and prefix-before-slash aliases; denominators remain
part of the retained literal identity. Current child combinations, catalog hashes and
binder state are captured in the review and rechecked at confirmation. Entry never
publishes or corrects catalog metadata.

| Dimension | Entry rule |
| --- | --- |
| Language and game | Offer only supported published combinations. Trainer and Energy cards can be physical records but never add Pokémon species completion. |
| Edition | Offer exact editions only on compatible children. Unknown edition does not imply unlimited, and an absent first-edition stamp does not establish another edition. |
| Finish | Retain literal identities such as `normal`, `nonfoil`, `reverse` and `reverse-holo`, even when friendly labels overlap. A set-wide holo switch cannot describe every card. |
| Variant | Use the actual supported combinations per printing. Opaque identifiers and unspecified variants do not establish physical characteristics or distribution. |
| Not applicable | Standard first-edition selection is unavailable for Base Set 2 and Wizards Black Star Promos. Null catalog fields remain Unknown; they do not create other exclusions. Copy-only fields do not apply to broad ownership or total actions. |
| Physical origin | Set membership, stamps and distribution metadata do not establish which pack an owned card came from. |

Per-printing distinctions remain necessary. Numbered holo and non-holo cards are
separate identities; rarity alone cannot fill missing finish metadata. A card with
multiple holo or stamped children needs an explicit supported combination. Literal
numbers such as `001/165` retain their denominators. Missing metadata stays explicit
through [reviewed collection entry](effective-collection.md) and
[photo entry](photo-entry.md); entry grants no artwork or pricing redistribution rights.
