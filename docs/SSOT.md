# Architecture and data ownership

## Entry points and storage

The collection app is Django, served by uvicorn on `127.0.0.1:8011`. Public browsing
uses allowlisted published catalog metadata; signed-in templates and plain JavaScript
consume private, account-scoped projections. A private root holds SQLite inventory,
authentication data, the Django secret and provider configuration. The optional staging
profile uses PostgreSQL and separate web/worker processes; see
[operations](operations.md).

The original FastAPI app and daily lot watcher are separate entry points. Their
ownership JSON and hunt database are not automatically synchronized with the
authenticated app. See [original app](ORIGINAL_APP.md) and [watcher](legacy-watcher.md).
Local startup is documented in [development](local-development.md); validation commands
belong to [CI](CI.md).

## Authoritative services

Paths in this table are relative to `src/pokemon_hunter/`.

| Responsibility | Source and contract |
|---|---|
| Local initialization and serving | `beta/staging_config.py` owns runtime profile selection; `beta/cli.py`, `beta/settings.py`, `beta/urls.py` consume it and root capability markers; unsupported profiles/actions fail before local initialization, with no automatic reseeding |
| Authentication and account access | Django auth, `beta/accounts.py`, `beta/store.py`: active mapped account and account-scoped queries; client IDs are selectors, not authority |
| Pokémon routes and guest home | `beta/species_views.py:home`: one validated list/detail boundary, including guest home delegation from account-only and collection roots; `beta/species_projection.py` owns current/saved private species reads; `beta/public_catalog.py` owns allowlisted guest metadata. Invalid context does not widen to an unfiltered catalog |
| Guest catalog API and Pack lookup | `beta/public_views.py` delegates to `beta/public_catalog.py`; no default account, ownership or private sources |
| Schema and import | `inventory.py`, `migration.py`: compatible additive schema initialization and explicit legacy import |
| Physical copies and mutations | `beta/collection.py`, `beta/transactions.py`: account boundary, preview journal, confirmation, idempotency and conflict-aware undo; `beta/collection_plans.py` constructs read-only plans through explicit account-scoped reader callbacks |
| Collection serialization and shared printing reads | `beta/collection_imports.py`: import shape, version hashes and frozen checklist validation; `beta/collection_catalog.py`: shared metadata queries; account verification and mutation authority remain in `beta/collection.py` |
| Canonical species identity | `beta/canonical_species.py`: hash-pinned public registry; mutable catalog names and private evidence are not identity authorities |
| Frozen collecting goals | `beta/broad_goals.py:species_items` groups species membership for filtered, Vintage 251, Original 151, declaration goals and lookup; `beta/goal_filters.py:printing_items` owns printing checklist shape; callers retain their eligibility policies and stored versions |
| Display card identity and canonical contracts | `beta/card_groups.py`: deterministic game/set/language/literal card groups, published catalog and checked account-private list/detail/species reads; `beta/card_group_views.py`: canonical/legacy destinations and literal mutation adapters; [group contract](card-groups.md) |
| Current collection presence | `beta/effective_collection.py:project`: verified account-local source/card intents and later supported copy creations; nullable exhaustive card total, recorded copies and exact resolution independent |
| Reviewed collection editing | `beta/collection_intents.py:plan/augment_plan/check_undo` through existing `collection.preview/confirm/undo`; journal-only ownership/quantity, explicit full/regional replacement, effective reviews and dependency protection |
| Finite owner defaults | `beta/collection_defaults.py`: validated owner-only card list, quantity/normal-variant attestation and explicit-exception preservation through the existing operation journal; no copy or catalog rewrite |
| Declaration-based ownership | `beta/ownership_declarations.py`: retained account-local source revisions separate from physical copies and the effective current projection |
| Public catalog publication | `beta/catalog_imports.py`, `beta/sealed_catalog.py`, `beta/sealed_bridge.py`: reviewed packages, atomic publication, journaled correction/rollback; `beta/sealed_contract.py` owns strict package schemas, reexported through the existing service |
| Catalog coverage and batch checkpoints | `beta/catalog_coverage.py`: pinned universe/alias inputs and read-only projections; `beta/catalog_pipeline.py`: assessment, reviewed checkpoints and existing publication services |
| Pack lookup and saved research | `beta/lookup.py`, `beta/packs.py`, `beta/product_lookup.py`, `beta/pack_research.py`: possible/guaranteed coverage and frozen account-local snapshots |
| Offer age and eligibility | `beta/offer_filters.py`: original observation age and conservative evidence decisions |
| eBay request validation/scoring | `hunt.py`, `beta/ebay_hunts.py`, `beta/goal_hunts.py`, `beta/hunt_values.py`: explicit search, frozen scope, current ownership and dated guide comparison |
| Shared retained-reference admission | `reference_policy.py`: HTTPS provenance, finite capped USD amounts, strict variant verification for legacy guides and the 30-day date rule; used by `valuation.py`, hunts, Shopping and snapshot validation. Domain services retain edition, grade, identity and rights checks; `beta/shopping_math.py` reexports the same age policy and cap |
| Photo jobs | `beta/scans.py`, `beta/scan_worker.py`, `beta/scan_config.py`, `beta/codex_recognition.py`: durable claims/reservations, configured provider and explicit inventory confirmation |
| Replay refresh | `beta/refresh.py`: bounded synthetic-only replay; no live acquisition adapter |
| Lot calculator and guide selection | `beta/lot_calculator.py`: vintage account-scoped selector, session-private wants, quantities, preparation and permanent-save admission; `beta/lot_guides.py`: shared guide cells, conflict provenance and unavailable reasons over supplied admitted records; browse/evaluate retain the same selection and historical admission boundary |
| Private price snapshot lifecycle | `beta/price_snapshot_contract.py` owns snapshot schemas and the four scenario names; `beta/price_snapshots.py` and `beta/price_snapshot_sources.py` own independent source shards, rights, expiry/removal, fingerprints and restore exclusion. `display_current` supplies one explicit unavailable-status policy for calculator and source-status views; operator and save admission retain strict errors. Import performs no acquisition; ordinary admission requires separately reviewed private contracts |
| Bounded metadata acquisition | `metadata_collector.py`: standalone, explicitly approved fixed TCGCSV Pokémon group request; durable consumed reservation, streaming/schema limits, worker deadline/independent Stop and private copy cleanup; no product/price collector or installation coupling |
| Shopping input validation | `beta/shopping_inputs.py`: shared fields, text, cost and original-research input shapes; `beta/shopping.py` preserves public imports; no database/account reads in validators |
| Shopping arithmetic | `beta/shopping_math.py`: decimal totals, partial coverage, unknown costs and per-card versus group-total scope; both calculator and original research preparation delegate to this evaluator |
| Shopping history | `beta/shopping.py:store_payload/reopen/reevaluate`: one account, byte-integrity and supported-schema policy for old/new saves; `beta/shopping_views.py` delegates both history routes without its own decoding or reevaluation branch |
| Card screens and local navigation | `beta/static/card-screens.js` owns fixed-owned My Cards, separate Library, canonical focused detail, checked local return/tab/filter/page/scroll state and optional retained per-copy guides; `collection.js` owns shared editing/preview/recovery; no new ownership, price or goal authority |
| Species rendering and collection tools | `beta/static/species-screens.js` owns private Pokémon list/detail rendering; `public-species.js` and public templates consume guest metadata. `pokedex.js` supplies reviewed source/import/goal tools only; it does not wrap parity or supply a second browsing renderer |
| Overview, eBay and retained per-copy guides | `beta/parity.py`, `beta/static/parity.js`: supported Overview, hunt, missing-search and finds projections. Overview requires effective current collection presence; missing current authority is an error. Per-copy guide disclosure remains shared with card screens. Parity never renders card or Pokémon routes |
| Client dispatch | `beta/static/collection.js:render` selects the required species/card renderer by route and awaits it; missing, declined or failed renderers cannot select another collection screen. Shared editing and supported Collection/Goals/Settings tools remain; [UI design](UI_DESIGN.md) |
| Security and diagnostics | `security.py`, `beta/security.py`, `beta/asgi.py`, `beta/diagnostics.py`: ingress, request-byte limits before buffering, URL policy and redacted failures |
| Optional deployment | `beta/deployment.py`, `beta/staging_config.py`, `beta/support.py`: staging configuration, copied import and operational commands |

## Ownership and goal contracts

A printing is catalog metadata; a physical copy is an account-owned object. Species
declarations record supplied ownership independently of quantities, condition, edition
or exact printing resolution. They never create copies. Goal progress follows its stored
policy: declaration-based species goals and resolved-copy/printing goals are
intentionally distinct. Completion counts species or distinct printings; duplicate
physical copies do not enlarge those checklists. Purchase amounts retain their original
currency.

The shared [effective current collection contract](effective-collection.md) supplies
current card/species views and no-goal missing selectors. Explicit source
selection/reselection is ordered by confirmed operation generation; older omitted copies
cannot revive presence, and metadata edits do not cross that boundary. Total quantity
remains unknown unless an exhaustive total is established; itemised records and exact
variant qualification remain separate. Artwork consumes presence. Frozen declaration
goals keep their saved source/species snapshot, while other saved goals retain
membership and current qualified-copy progress. Raw copy/history exports, valuation and
original-app state remain separate. Collection editing provides reviewed mark-owned,
remove-card, exhaustive-total/unknown and explicit source replacement through existing
journal transactions, with effective preview deltas and undo dependencies for operations
that change no rows. Removing a card retains matching copy IDs/photos/history as removed
records; removing one copy retains any other ownership support. Copy changes invalidate
an older total, including after their undo; metadata changes preserve it. Card totals
are never allocated across candidate variants or used as a price multiplier. Historical
JSON/CSV remains copy/goal history rather than an operation-journal backup. Stable
display groups sit above unchanged printing/copy/assertion IDs. My Cards uses effective
owned groups; Card Library uses the existing published metadata policy; species detail
returns owned and catalog results separately. Canonical detail URLs preserve explicit
child selection. Unknown/ambiguous legacy aliases and foreign children never select a
substitute. Owned archived metadata remains privately accessible while guest/catalog
publication remains unchanged. Nullable card totals are referenced once;
recorded/current counts and exact child qualification stay independent. Unmapped
card/species evidence remains separate. Group adapters delegate literal scope to
collection previews; no new ownership writer, schema, goal policy, price/artwork
authority or persistent GET path is introduced. Global navigation, contextual Shopping
and user-input-only drafts use these same collection contracts; see [navigation and
Shopping adapters](#navigation-and-shopping-adapters).

Goal definitions freeze membership, policy, source references and version hashes.
Publishing metadata does not enroll new items into an old goal. A successor requires
explicit review. Historical version-1 labels include `#250 Ho-oh` because labels
participate in persisted hashes; canonical display uses `Ho-Oh`. This is compatibility
behavior, not a second species registry. Archived metadata remains recognizable inside
retained goal scopes; current selectable coverage is separate.

Original-app ownership lives in `config/pokedex_251.json`; original saved hunts live in
`data/collection_hunts.db`. Authenticated state belongs to the selected private root.
Retained guide/hunt evidence is not an ownership writer or a species identity authority.
Missing or stale guide evidence remains unavailable.

## Public evidence and private research

Canonical species, printings, booster membership, product versions, contents and seller
observations are separate records. The canonical registry contains 1,025 species;
card/pack browsing covers #001–251. A source association or retailer description does
not prove official product contents or distribution.

Catalog publication requires the owner role. Reviewed changes retain exact identities,
source URLs/hashes, journals and observation timestamps. Descriptive correction and
identity remapping have distinct semantics. Rollback refuses to clobber later changes.
Public metadata publication never rewrites physical copies or frozen research. See
[catalog workflows](catalogs.md).

Saved pack lookups retain selection, ownership, coverage, goal references and dated
offers. Reopening can report current-reference gaps and recompute age without rewriting
the snapshot or its original timestamps. Comparing current indexed data opens a separate
lookup. Offer freshness uses the original check and a 24-hour window; future/unknown
timestamps are not fresh. Recommendation eligibility remains distinct from purchase
attestation. Purchase-ready is currently false; no backend purchase attestation contract
is implemented.

## Jobs, configuration and compatibility

Photo workers claim durable jobs before provider I/O. Provider requests may consume
reserved authority even if the response is interrupted. Only confirmation adds
inventory; recovery does not reset spending or repeat an uncertain provider call. The
local server starts one scan worker when enabled. Staging runs it separately. Manual,
fixture, API and authenticated CLI recognition are explicit local modes, with no
automatic fallback. `beta/scan_config.py` owns the accepted fields, modes, ceilings and
staging restriction. Persistent staging reads, initialization and copied import use that
validator; CLI recognition is local only. Unknown config keys fail instead of appearing
to select an unused flag. See [photo entry](photo-entry.md) and
[recovery](ERROR_HANDLING.md).

Sealed-offer refresh runs only on disposable synthetic roots through the replay adapter.
Ordinary lookup/reopening does not fetch offers. The eBay flow separately supports
explicit provider requests in local mode. Environment parsing and model validation are
shared across the watcher/original app and authenticated hunts; process values override
file values, and malformed existing settings fail.

Persisted root markers, schema names, goal policies, routes and CLI flags remain
compatible contracts. Saved searches without an intent retain missing-target semantics.
Staging copied import rejects CLI recognition configuration. Retiring these contracts
requires a migration rather than cosmetic renaming. Metadata availability grants no
artwork, guide or trademark redistribution rights.

Shopping history explicitly supports `dex-shopping-v1` (original per-card/group
research) and `dex-lot-v2` (four independent scenarios). Unknown/missing schemas fail
before saving, rendering or reevaluation; they never select the original format
implicitly. Reopening preserves original bytes and captured results. Current-reference
evaluation creates a separate child using that format's preparation contract. The
original editor at `/shopping/legacy/` and its APIs remain supported for group values,
frozen goals and retained history; they are not alternate implementations of the four-
scenario calculator.

Shopping displays admitted retained guides; complete automatic four-grade price coverage
is unavailable. Partial source coverage and source-specific retention limits remain
separate from arithmetic and UI behavior. The versioned private store has managed
expiry/removal and restore exclusion; source-specific copy/deletion obligations must be
met before admission. No scheduled price collector is installed.

## Image authority

The [image contract](artwork.md) owns consumer image semantics. `beta/image_mappings.py`
plus pinned `beta/data/cx04_image_mappings.json` own species/group/unsupported exact-
child mappings. `beta/image_bindings.py` owns current account/catalog/generation
adapters and copy descriptors; `beta/scans.py: authorized_photo_rows` is shared with
existing photo serving. `image_bindings.enabled` owns local/staging availability for
remote descriptors and the private collection shell's image policy. Both catalog
groups and literal declarations use `image_mappings._card_mapping` over the same
hash-checked index; missing or duplicate literal identities remain unavailable.
`owned_artwork.py` retains the active parity adapter using checked canonical mappings
and fresh projection equality. It has no URL constructor or normalized-name image
lookup; its set order is presentation only. None supplies possession,
totals, variant qualification or navigation identity. Remote species/card references are
private-local only; public/staging exclusions and existing private photo lifetime rules
remain. Card and species screens consume the same image descriptors and canonical
destinations independently of collection presence.

## Card flow and request authority

The collection app owns `/cards/`, `/card-library/`, canonical card detail and legacy card destinations
with one handler each, independently of parity. My Cards uses fixed owned groups;
Library uses catalog groups. Full scoped filter options include owned archived sets.
Private HTTP projections bind verified account plus checked collection generation;
effective current collection exposes the checked generation as a read-only field.
Missing/changed authority blocks editing and late responses cannot replace newer state.
The adapter uses the existing schema and collection mutation authority.

Canonical identity stays group plus optional explicit child. A validated local `return`
and account-scoped per-tab URL/scroll state are UI context, never API filters or child
selection. Group quantity, recorded/current copies and removed history remain distinct.
Core screens do not require parity; optional Prices and sources loads existing per-copy
admitted guides only when opened on supported installations. No total-to-value
multiplication or provider acquisition occurs.

The shared editor keeps basic fields focused and closed advanced values intact. Existing
literal/group preview-confirm-undo remains the sole mutation path; broad ownership,
total record/clear, copy removal, card removal and declaration correction retain their
semantics. Edition remains a per-copy operation. Stable references and saved operation
status recover uncertain confirmations/refreshes without creating another addition.
Stale conflicts require an explicit new preview. Cancellation, route/account guards and
focus restoration survive asynchronous rendering.

## Pokémon screens and read authority

`beta/species_projection.py` is a thin read adapter over canonical_species,
effective_collection and the existing saved goal services. `beta/species_views.py` owns
the canonical Pokédex/species route boundary in every supported profile and the
authenticated `/api/pokedex-species/` contract. It verifies account and checked
generation before returning; it owns no persisted identity, ownership, schema, mutation
or snapshot policy. Private collection browsing does not depend on parity valuations. Guests retain
published allowlisted metadata with no inferred personal status.

`species-screens.js` joins that checked projection with the existing species group API
at the same account/generation and renders normal species pages. Your Cards contains
current owned groups once, through the compact card-tile renderer. Current and saved
policy units are explicit; frozen past progress never creates a current owned tile.
Species totals remain unknown. Select is explicit, account/goal/region bound, search-
hidden selections are counted, and scope changes clear selection. Existing Pack links
carry intended species/goal without writes.

Shared refresh awaits species rendering and invalidates prior work; parity is omitted
for core Pokémon browsing. Finite client/server return validators permit only documented
card lists, Pokédex lists and canonical species, with bounded UI context and one nested
species-to-list return. API filtering remains separate. Operation IDs,
preview/confirmation/undo and saved-status recovery stay shared.

## Navigation and Shopping adapters

`beta/navigation.py` owns finite destination validation, recursive private-object
reauthorization and an opaque installation/account/auth-session binding. Its read-only
`/api/navigation/home/` endpoint validates optional browser memory; `navigation.js` owns
successful-render-only home/tab memory, header sections, explicit collection-to-Shopping
links and logout/cached-page invalidation. Root uses the existing collection shell;
initial resolution opens `/cards/`. Django safe sign-in returns and legacy profiles
remain authoritative.

`beta/shopping_context.py` resolves canonical species OR group plus optional explicit
member child, optional paired saved goal/version, checked generation and finite return.
Existing canonical/effective/group/goal/catalog services decide membership and meanings.
It supplies no ownership, quantities or price policy. `shopping_views.py` rechecks
account/session/generation/applicable goal version around local reads and explicit
writes. Null child stays null; unavailable targets are never replaced. Existing
calculators, arithmetic, sources, retention and immutable history retain their single
authorities.

`lot_calculator.js` stores only an account/origin/session-bound allowlist of user-
authored draft inputs and UI choices. Restoration rereads admitted local references,
never persists cells/source records/results and never issues an automatic POST. Session
wants and local draft choices remain distinct; disagreement is visible and requires
explicit confirmation. Included units, wanted units and collection quantities are
independent. Stale context discards price derivatives and requires reopening while
retaining inputs; source expiry/withdrawal remains enforced. Persistence, source
identity, ownership and financial calculation belong to the existing domain services.

`navigation.py:context/task_home` supplies read-only collection, Add Card
and owner-only administration entry pages. Shared `task_navigation.html` groups
existing routes without granting access or becoming another workflow service.
`packs_views.py` supplies an account-scoped goal chooser when no goal was requested;
explicit goal projection/authorization still belongs to `packs.py`. Card Library
retains its primary section through detail/Back. Optional card focus memory holds
only a destination within the current account; existing response/session/generation
checks and logout invalidation remain authoritative. Existing filter meanings and
completion denominators are unchanged.

## Pokédex scoped completion

`beta/species_scope.py` owns the finite multivalue/date contract, retained-date
identity joins, three-valued matching and owned-card evidence policy.
`species_projection.project` consumes only verified effective current possession;
all dimensions match one evidence record. Broad literal cards can establish common
set/date/category/rarity facts without an itemised copy; finish requires an explicit
owner declaration or qualified exact evidence. Unknown quantity preserves possession.
Species-only evidence is unresolved in restricted scopes. Duplicate cards count once.

Target membership comes from canonical region or the supported saved species goal's
frozen membership. Search and ownership-display filters affect rows only. Card
criteria never remove target species. `scoped_progress` describes current qualifying
cards, `current_progress` overall possession, and `progress` retains the original
goal-policy result. Unsupported printing/legacy policies stay in Goals.

Single-value URLs remain supported. Multivalues use a JSON array inside the existing
field; values are deduplicated/sorted, at most eight per dimension, 160 characters
per value, 1,400 per field and 1,500 encoded characters for criteria, reserving room within 1,800 per list context. Fields are
set, era (indexed series), type (catalog category), rarity, finish, released and year;
`date_from`/`date_to` are inclusive ISO dates. OR within dimensions, AND across them.
Invalid calendar dates, reversed ranges, repeated query keys, unsupported release
periods, excessive inputs and unsupported contexts fail closed. No printing ID or
saved-goal storage is rewritten. Species details inherit criteria and target region
from their validated list return. Their card classification is keyed by canonical
group IDs using the complete-child identity join, independently of internal
effective assertion IDs; only current owned groups receive classifications. Card, header and Shopping return chains retain the
same finite nesting, account/session/installation and generation checks.
