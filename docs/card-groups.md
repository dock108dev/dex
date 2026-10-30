# Display card groups and canonical contracts

`beta/card_groups.py` is a read-only display layer over
reviewed catalog metadata and the [effective collection](effective-collection.md).
It creates no ownership authority, mutation event, schema or persistent cache.
`beta/card_group_views.py` owns the HTTP adapters. Printing/copy/goal/source IDs
and literal assertion identities remain independent of display-group IDs.

## Identity

A canonical group ID is `dg1-` plus the full SHA-256 of UTF-8 compact JSON:
`[game_id,set_id,language,collector_number,name,pokemon_dex]`.
The game/set IDs are reviewed catalog identities. Collector number and supported
language remain literal; `1`, `001` and `1a` are distinct. Catalog names retain
named, Dark and Light identities. Applicable Pokémon species identity requires
both a reviewed Pokémon game and Pokémon card type; Trainer/Energy/other games
never populate Pokémon species results. Nonapplicable species is null.

Within a game/set/language/literal-number slot, contradictory names, species or
set labels block that affected slot and produce readable unresolved metadata.
Incomplete identity fields or catalog unresolved identity flags block only their
records. Conflicting duplicate printing IDs also remain unresolved. No first-child,
name-only or fuzzy merge resolves a conflict. Different games, sets, languages and
collector numbers remain independent. Same-number editions/finishes/variants are
children of the supported card identity. Different-number holo/non-holo cards
remain separate groups.

IDs do not depend on child order/count, publication, filters, artwork, source
selection, account, possession or quantities. Restart and adding/removing a finish
child preserve the ID when identity is unchanged. An actual identity correction
requires reviewed authoritative catalog correction: retain the old identity and
its history/references, publish the corrected identity explicitly and document any
reviewed mapping. This display service does not rewrite copy/goal references,
create successor aliases, silently rekey or equate old/new identities. An unknown
old identity remains unavailable until its explicit correction/mapping is reviewed.

## Publication, possession and unresolved evidence

Private catalog scope uses the existing authenticated `collection.catalog` policy:
Publication-enabled roots expose published children in published sets; older
collection roots retain their ordinary private legacy catalog. Supported other-game/language metadata retains
private catalog access. Guest scope uses `public_catalog.entries`: published
Pokémon/en metadata only, with no catalog exposure before reviewed publication. Public detail excludes archived children. Private owned scope includes
supported owned archived identities; private detail also preserves retained
matching-copy identities. A selected archived child remains labelled unavailable;
no edition is substituted. A wholly unavailable unowned/unrecorded group is 404.

Private grouping loads full archived metadata for effective collection mapping.
An assertion maps only when its supported printing set equals the group's complete
child set and its identity is unconflicted. Otherwise ownership and total remain
unallocated and the complete assertion stays separately readable as unresolved
collection evidence. A source assertion never spreads across compatible-looking
groups. Complete literal multi-card cells produce each distinct card once;
repeated assertions do not imply quantity. Incomplete cells retain complete row
and cell evidence. Species/set marks remain species evidence, with no invented
number, language, printing or scan. Unmapped active copies and effective conflicts
also remain separately visible privately.

| Private field | Meaning |
| --- | --- |
| `present` | Current card possession from one mapped effective assertion |
| `established_total_quantity` | Exhaustive positive card total or null; referenced once per group |
| `recorded_copy_count`, detail `recorded_copy_ids` | Deduplicated active matching records, including retained records omitted by current source; neither exhaustive nor an unconditional minimum |
| `current_copy_count`, detail `current_copy_ids` | Deduplicated matching records supported under current source/removal boundaries |
| `exact_variant_count`, detail `exact_printing_owned_ids` | Independently qualified exact current child identities |
| `identity_status` | `resolved` or readable mapping `conflict`; unresolved catalog slots are separate entries |
| Detail `assertion_id` | Private literal assertion reference, never a group/printing/copy ID |

Removed copies are explicit detail `history`, excluded from active counts. Every
private variant quantity is null. Species totals are not inferred or exposed.
Base Set 2 Ivysaur #44 can be Owned with unknown total and zero recorded copies;
broad declarations do not qualify its child variants. Artwork/price metadata
never supplies identity, ownership, quantity or valuation authority.

## API schemas

Private responses re-resolve principal and check collection generation before and
after assembly. There is no reusable private cache. The internal snapshot has an
account binding; reuse checks reject a foreign/revoked account or changed generation.
Repeated GET/list/detail/resolution performs no persistent writes or provider calls.
Catalog metadata is read fresh each request; catalog publication/correction is a
separate reviewed operation and requires consumers to reload current metadata.

Group summaries explicitly contain `id,url,game_id,set_id,set_name,language,name,
collector_number,pokemon_dex,identity_status,variant_count,published_variant_count,
catalog_available`, plus the five private summary fields above when authorized.
`variant_count` counts all retained children in the caller's internal projection;
`published_variant_count` counts children admitted by that caller's catalog policy
(including legacy private availability on older collection roots); `catalog_available`
means at least one such child exists. Guest counts therefore include only published
children, while authorized private counts can identify archived children separately.
Default summaries omit child IDs, assertion IDs, copies, history and source detail.

List responses contain `public,generation,scope,groups,total,page,page_size,pages,
unresolved`. `generation` is the checked private collection generation; guest
generation is null. `total` counts matching groups before paging; an empty result
has zero pages. Page beyond the last returns an empty group array with unchanged
counts. Pagination applies to groups, never child records. `unresolved` is a
separate evidence array, not an ownership quantity or a catalog group count.

Detail responses contain `public,generation,group,variants,selected_child`; private
detail adds `copies,history,unresolved`. Private detail group includes the four
private reference arrays/fields above. Variants use the existing explicit public
card-metadata allowlist plus language and `available`; private variants additionally
contain null `established_total_quantity` and `exact_printing_owned`.
`selected_child` is the requested child record or null when none was requested.
It never defaults to the first child. Private copy/history rows are account scoped.

Species response contains `public,generation,pokemon_dex,catalog`; private response
adds `owned,unresolved`. Owned and catalog are independent paged list results from
one checked snapshot. Pokémon dex range is #001–251. Unresolved species/card
assertions for that species stay readable separately from mapped groups.

Public output uses explicit group/variant metadata allowlists. Public unresolved
entries contain only metadata conflict kind, printing IDs, missing fields, labels
and allowlisted identity descriptions. No public response includes private
possession/quantity, sources/source text/IDs, operations, copies/photos, purchase
information, raw attributes or raw provenance. Artwork access is unchanged.

## Filters, sorting and errors

List accepts short text (up to 160 characters): `scope` (`catalog` default or
`owned` privately), `generation` (private nonnegative integer), `q`, `set` (exact
set ID), `language`, `edition`, `finish`, `variant`, `species` (#1–251), `page`
(1-based, default 1), `page_size` (1–100, default 40), and `sort` (`set` default,
`name`, `number`). Unknown/duplicate fields reject. Query matches case-insensitive
name/set/collector-number text. Other metadata filters are literal equality.
Integer text accepts decimal ASCII digits, including leading zeros. Empty optional
pagination/species values use defaults; malformed or out-of-range values reject.

Variant filters include a group once if an eligible child matches. Such rows add
`matching_child_ids`; group possession, total and counts remain complete and
unchanged. Catalog filters match only catalog-available children; owned filters can
match retained archived children. Set and Name sorting compare text case-insensitively.
Collector-number ordering compares digit runs numerically before pagination, both
within sets and for explicit Number ordering: 1, 2, 9, 10, 11, 100. Prefixed,
suffixed and zero-padded numbers retain their literal identities. After the selected
sort field, ties use case-folded set name, natural collector number, case-folded card
name and stable group ID.

List/detail agree for unchanged metadata at the checked collection generation.
Consumers can supply the list generation on subsequent private list/detail reads;
a changed generation returns 409 and requires a fresh list. Catalog corrections
or publication are independent of collection generation: reload metadata after
such an operation rather than reusing a pre-publication count. There is no cache
that can combine old/new private account projections.

Invalid filters/request fields/duplicate query keys return 400. Unknown or foreign
children/groups return 404. Ambiguous aliases, affected identity conflicts and stale
collection generations return 409. Private sign-in, revocation (403), methods (405)
and CSRF retain existing behavior. API 400/409 responses contain
`{"error": "readable message"}`; public 400 uses a fixed catalog-filter message.
404/403 and method/CSRF failures retain ordinary Django HTML/empty responses;
unauthenticated private requests redirect to login. Consumers must inspect status
and content type before parsing an error as JSON. Global middleware applies `Cache-Control:
no-store` to reads, including private routes. No endpoint supplies acquisition.

## Canonical destinations and mutations

| Route | Contract |
| --- | --- |
| `/api/card-groups/` | Private catalog list |
| `/api/my-card-groups/` | Private fixed-owned list; caller scope is rejected |
| `/api/card-group-filters/` | Private complete filter options; optional `scope` (`catalog` default or `owned`) and checked `generation` only |
| `/api/card-groups/<dg1-id>/` | Private detail; optional `child` and `generation` |
| `/api/species/<dex>/card-groups/` | Private owned/catalog results; list filters excluding redundant `scope`/`species` |
| `/api/public/card-groups/` | Guest published-metadata list |
| `/api/public/card-groups/<dg1-id>/` | Guest detail; optional `child` |
| `/card-groups/<dg1-id>/` | Canonical private HTML detail; optional `child`, checked `generation` and validated local `return`; direct access/refresh works |
| `/cards/<child-or-alias>/` | Compatible temporary redirect preserving selected child, where existing parity card routes are enabled |
| `/api/card-groups/<dg1-id>/preview/` | Private/CSRF POST literal adapter → existing authoritative preview |

Supported child aliases are exact printing ID, `catalog-<printing-id>` and retained
`provenance.legacy_id`. The inventory maps every alias to its deduplicated candidate
IDs. Unknown aliases are 404; duplicates and collisions with reserved canonical
namespace are readable 409, never first-match/overwrite. Parity's ordinary browse
keys retain unique child destinations and expose ambiguous aliases separately.
A requested child must belong to the accessible group.

Group preview accepts exactly `kind,request,operation_id` and optional `child`.
Card intents resolve the literal set/name/number/language through collection transaction authority;
replacement identity values reject. Exact child addition/photo preview requires
selected child and matching printing ID. Copy edit/remove/edition/resolve validates
matching group/copy and selected-child scope. Set/checklist and source replacement
operations remain their existing ordinary endpoints, not a card-group shortcut.
The adapter creates no event; collection preview/confirm/retry/undo owns mutation.
Pending previews confer no ownership. Existing quantity invalidation, preserved
copy metadata/history, source boundaries, strict zero/unknown semantics, atomicity
and protected undo remain unchanged.

The three goal policies remain effective current collection, frozen declaration
snapshot, and frozen membership with current qualified-copy rules. No automatic
refresh/successor, goal rewrite, synthetic copy, price pooling or artwork authority
is introduced. See [architecture](SSOT.md) and [interface design](UI_DESIGN.md).

## List controls and return context

`/cards/` is owned-only My Cards and `/card-library/` is its adjacent Card Library
destination. The list APIs retain their existing filter contract: UI-only `return`
and `scroll` are never forwarded to them, and My Cards never sends `scope` to
`/api/my-card-groups/`.

The private filter-options adapter returns `public:false,generation,account_id,
scope,sets,languages,editions,finishes,variants`. Sets are `{id,name}` objects sorted
by case-folded name then literal ID; the remaining arrays contain supported literal
nonempty metadata values, deterministically sorted. Options come from the complete
authorized scoped group projection, independently of search, active filters and
pagination. Catalog scope includes available catalog children; owned scope includes
retained owned archived sets/children. Empty private owned scope returns empty
arrays. Null/unspecified edition and finish are not invented selectable identities.
The endpoint rejects list filters, UI state, duplicate fields and stale generation.
It performs no writes, provider requests or ownership inference.

Private HTTP list/detail/species/filter-options responses include `account_id` for
discarding responses after an account change. This is the verified current actor's
account binding, never a caller-selectable authority. Public group output omits it.
Generation and account must both match the active frontend context before a late
response can be rendered.

Canonical HTML detail accepts a bounded `return` to My Cards, Card Library,
canonical Pokémon pages and Shopping. Each destination uses its existing finite
field validator; Library page context can retain generation, goal/version and a
species return. ASCII integer `scroll` ranges from 0 through 10000000. Duplicate
and unknown keys, unsupported values, external URLs, fragments and literal control
characters reject. Every referenced private target is reauthorized; stale retained
generation or goal version conflicts. Return context never selects a child or becomes part
of group identity; optional `child` retains independent strict membership checks.
Normal canonical links omit `child`. Explicit child links retain their exact
archived/unavailable context.

The existing group mutation adapter remains authoritative: broad `mark_owned`
requires no copy or child; recording/clearing quantity uses `card_quantity`; whole
card removal, physical copy removal and declaration correction remain separate
intents. Copy addition requires explicit supported child selection. Partial `edit`
attributes merge with the stored copy, preserving closed purchase, grading and
certificate fields; metadata edits preserve card totals, while copy-support
changes and their undo invalidate previously attested totals. No mutation event,
schema, goal policy or ownership authority is added by list rendering.

## Image fields

Private local summaries/details add `reference_image`, a checked card-group
reference descriptor independent of possession. Detail adds `selected_child_image`
with explicit exact-asset unavailable evidence for the requested child; it remains
null when selection is null. Archived selected children retain their context.
Active copy rows add `photo_references` from the authoritative serving association;
history does not restore photos. Public/staging remote projections omit these
reference fields; authenticated staging photos keep the existing access policy.
The [image contract](artwork.md) defines availability, source and fallback precision.

## Bounded browsing reads

Ordinary card/species pages use V2 pages and compact, revision-bound context.
[Frontend reads](frontend-reads.md) describes current consumers and remaining
V1 tools. `/api/collection-context/` and the full `/api/collection/` endpoint remain
compatibility services; they are not fallbacks for unavailable V2 state.

V2 selection pages indexed metadata before expanding returned records. Private
queries validate account authority and collection/catalog revisions before and
after their snapshot. Artwork descriptors load separately for bounded accessible
identities; filter options bind no images. Counts, archived context, unresolved
evidence and exact identity retain the collection service’s semantics.

## Connected Shopping returns

Species Explore cards opens the indexed Card Library with `species`, optional
single `set`, checked `generation`, explicit `goal`/`version` when selected and a
validated species `return`. These page-only context fields do not become catalog
filters. Search/filter/pagination and Clear filters retain that original return.
A Library/card return reauthorizes the referenced goal/version and generation.

Shopping catalog choices expose separate selection buttons and **Card details**
links to canonical groups. Only an explicitly chosen child enters the card route.
A bounded `/shopping/` return contains user query/refinements, collection context,
scroll/focus and an opaque temporary run handle. It contains no seller content,
prices or imagery. Card details' Shopping action reuses this original state.
Restoration rereads the existing authenticated temporary service without acquiring
or renewing its lease. See [connected entry](hunts.md#connected-pokémon-and-card-entry)
for scope changes and qualification boundaries.


## Read architecture

V2 browsing selects bounded pages from indexed catalog metadata and current account
overlays. Derived records are disposable representations, never ownership or
publication authority. V1 routes remain available for explicit compatibility tools;
ordinary V2 reads do not fall back to full projections.

### UI, backend and database boundary

The UI and database remain separate layers. Browser JavaScript calls authenticated
or public HTTP APIs; backend Python services own all database reads/writes and
policy checks. The existing private `inventory.db` SQLite database stores the
application's authoritative records. Shared catalog indexes and account overlays
are server-side derived tables in that database, not browser storage or UI-owned
state. The browser receives bounded results and keeps only transient display state.

This design does not introduce a separate database-server process. SQLite is a
local database file accessed by the backend; PostgreSQL remains the separately
qualified staging option. Logical UI/database separation does not require another
database engine, service or copy of the customer's data. The API boundary allows
backend read implementation changes without moving authority into the UI.

### Authority and revision keys

Keep `games`, `catalog_sets`, `printings`, reviewed aliases/publication heads,
collection sources/declarations, copies, operations and frozen goals authoritative.
Do not put prices, provider content, session credentials or private photos into the
catalog index. Retain complete archived identity metadata internally; a publication
flag controls availability, not whether a retained copy's identity exists.

Add a durable monotonic catalog revision in an explicit additive schema migration.
The derived catalog key is `(catalog_revision, read_schema_version,
identity_policy_version, publication_policy_version, image_mapping_version)`.
A package digest identifies the builder in diagnostics; unrelated package changes
need not invalidate an identical declared read schema/policy. The existing
`catalog_heads` set/import pairs alone are insufficient: they do not cover every
identity/alias change. No file mtime, row count or process lifetime is a revision.

Use the existing per-account `collection_generations.value` for collection revision,
with an explicit source revision/digest and a new `account_read_revision` backstop
in the overlay manifest. The overlay key is `(internal_account_id,
collection_generation, account_read_revision, source_revision, catalog_key,
ownership_policy_version)`. Keep the existing collection generation semantics intact;
new read-revision triggers must not make a just-created preview stale. Goal-scoped results additionally key on the immutable
goal ID/version and finite scope criteria. Never enlarge a frozen goal when a new
catalog revision appears. An account ID supplied by the browser cannot select an
overlay. Authentication, active-account state and role are read on every request,
including hits, and checked again before response release alongside revisions.

### Shared indexed representation

Use additive tables in the existing database, with build IDs on every derived row
and an active-manifest pointer. This avoids a second database transaction boundary.
Prepare typed, allowlisted printing metadata; groups; group-child membership;
all alias candidates (including collisions); unresolved catalog evidence; species
membership; filter dictionaries and postings. Store archived and published child
membership separately. Store the exact `dg1` hash inputs and resulting ID unchanged.

Precompute three deterministic group order ranks using the existing Python
case-folding/natural-number comparator and stable ID tie-break. Index
`(build_id, scope, sort_rank, group_id)`, membership by printing/group, aliases by
literal alias, and filter postings by `(build_id, field, literal_value, group_id)`.
Prepare case-folded searchable text and 1/2/3-character gram postings; intersect
query grams in SQL and apply exact existing substring semantics as a residual.
Do not change substring search to word-prefix matching. The older printing API's
all-token matching and variant-label search remain a separate compatibility policy.
Search counts and sort/page selection operate on compact indexed IDs, never decoded
whole-catalog Python records. Verify common one-character searches, empty queries,
Unicode, punctuation and deep pages, not just selective names.

Expand metadata only for the returned page or selected detail. Filter options use
complete scoped dictionaries/postings, independent of the current page and query.
Owned options join account membership, including archived owned children. Counts
remain exact; no approximate totals or fabricated selectable edition/finish values.
Prepare aliases and conflict detection once per catalog revision, not on each list.
Image descriptors are resolved only for returned rows; remote artwork is outside
primary response readiness and retains its existing access/source rules.

### Account composition

The account service owns disposable account-group, account-species, copy-reference and unresolved
evidence tables. Derive these from the existing effective-collection policy, including
operation history/source boundaries. Persist the result of that policy, not another
interpretation of possession. Broad presence, established total, recorded/current
copies and exact variants remain separate. Never allocate broad quantities to children.

Recompute the affected literal identity/copy/species dependency closure on ordinary
confirmed edits and Undo. Source replacement/import may require a whole-account
rebuild; perform that work in the authoritative operation/preparation path. Catalog
identity changes rebuild affected overlays against the candidate catalog revision.
Store full evidence once and page references separately. A list must not replay the
entire operation journal or reconstruct every catalog printing to validate a trusted
internal snapshot. Replace equality against freshly loaded whole-catalog inputs with
an internal revision-bound snapshot type; arbitrary caller-supplied rows still reject.

Update authoritative state, generation and applicable derived rows atomically when
the bounded incremental path succeeds. If preparation fails, do not serve the old
revision as current: mark the overlay unavailable and expose explicit recovery.
A durable confirmed operation remains confirmed; a derived failure must never replay
it. Simultaneous reads select one build/revision snapshot, and a final authority check
returns 409 if that snapshot became stale. Cached possession is never mutation authority.

### Invalidation ownership

| Authoritative event | Owning path | Required derived action |
| --- | --- | --- |
| Catalog publish, rollback/withdrawal, corrected identity, variant children | `catalog_imports.transition/write`, `catalog_variants`, pipeline publication adapters | Advance catalog revision in the same transaction; invalidate public/private catalog and affected overlays; retain old IDs/history without invented aliases |
| Catalog set/game/printing/alias writes outside publication | Explicit migration/import/deployment operators | Database revision triggers provide a backstop; operator prepares a compatible build before readiness |
| Copy add/edit/remove/resolve, quantity/declaration correction, source replacement, import, bulk/photo confirmation | `collection.confirm`, `collection_plans`, `collection_intents`, `collection_drafts` | Advance account generation and update/rebuild affected overlay; receipts and source semantics unchanged |
| Undo | `collection.undo` | New generation and recomputation from resulting authority, never restore an old cached snapshot |
| Source/declaration or copy changes through maintenance | Import/deployment/operator paths | Invalidate account overlay transactionally; triggers on relevant authority tables catch bypasses of `collection.bump` |
| Goal creation/successor/edit | Collection confirmation and `collection_goals` | Key scoped result by new goal version; preserve frozen membership and old version behavior |
| Account revocation/deletion/role change | Existing account/CLI/support authority | Reject access immediately; discard account reuse; current principal checks remain mandatory |
| Logout/session expiry/account switch | Django session authority and frontend navigation | Stop client reuse and discard late responses; never rely on cached account state |
| Image mapping/package policy update | Explicit installed package update | Change relevant mapping/policy key; rebind page descriptors without changing identity/ownership |

Revision triggers must cover inserts, updates and deletes of catalog authority and
account source/copy/declaration authority and committed operation changes. Catalog
triggers advance catalog revision; account triggers advance only the new
`account_read_revision`, not `collection_generations`. Exclude preview-only operation
changes and derived-table writes. Multiple read-revision increments in one transaction
are harmless; equality, not consecutive numbering, is the contract. Existing
confirmation/Undo generation checks and operation ordering remain compatible. Tests must enumerate trigger coverage and all mutation adapters above.

### Versioned bounded API

Keep current routes and JSON contracts for compatibility. Add `/api/v2/` equivalents
for card groups, owned groups, group filters, species groups and Pokédex summaries;
add `/api/v2/public/` equivalents for guest groups, filters and species. V2 list
selectors retain current semantics and page sizes (default 40, maximum 100), with
an optional opaque `catalog_revision` token alongside private `generation`.
Each response supplies `read_version:2`, `catalog_revision` and `public`; private
responses also supply checked `account_id` and `generation`. A supplied stale token
returns 409. Unknown/duplicate selectors retain 400; authorization/404 policy stays.

V2 lists return group summaries, exact total/page counts and
`unresolved:{total,url}`. The URL addresses a separately paged evidence endpoint
(default 40, max 100), bound to the same revision/account/scope. Evidence is never
silently dropped. Detail supplies the primary summary and selected child immediately;
variants, copies, history and oversized evidence use individually paged subresources
with the same revision checks. A complete evidence record exceeding the response
budget uses an explicit authorized detail/download path; never truncate original text.
Filter dictionaries are complete across independently paged option resources when
they exceed the payload limit; report total and continuation, not a partial list as
complete. The UI can search these choices without transferring the full dictionary.

Do not add `return`/scroll/goal UI state to catalog filter authority. Preserve local
return validation, child membership and exact unavailable-child handling. V1 full
arrays remain available to explicit legacy tools until their callers migrate; no
ordinary V2 navigation may invoke them. Private output stays no-store and explicitly
allowlisted; public endpoints never read account overlays.

Rejected alternatives: caching JSON by URL alone leaks/stales account state; per-process
memoization leaves restart cold and duplicates memory; paginating after projection
retains the measured cost; skipping ownership validation changes correctness; TTLs
cannot make publication withdrawal safe; a new database/framework or more worker
processes adds operational risk without removing repeated work. Compression can
reduce transfer bytes but cannot fix full-catalog decoding or ownership projection.

## Shared read services

SQLite V2 public services preserve V1 response shapes and authority checks.
Private composition is described in [account reads](account-reads.md); browser
consumers and remaining V1 calls are in [frontend reads](frontend-reads.md).

`catalog_read_schema` owns the explicit migration and database revision triggers.
`catalog_read_build` snapshots authority, uses `catalog_read_records` to build typed
candidates outside the write transaction, validates the complete candidate and switches the manifest only when
the authoritative revision still matches. `catalog_read_compact` shares rows only
when their complete derived values are identical. Distinct public and retained
conflicts remain distinct; sharing is not fuzzy identity resolution. Public grouping
uses precisely published Pokémon/English inputs, independently of archived conflicts.
Internal printing metadata also retains unresolved identities and archived records.

Group IDs still come from `card_groups.build_groups` and its literal dg1 inputs.
Three global ranks preserve its natural-number/case-fold ordering and ID ties.
`catalog_read_select` counts, filters and pages compact SQL records before expanding
returned metadata. It never decodes the catalog or operation journal on a GET.
`catalog_read_internal` offers checked snapshots, bounded literal printing reads,
paged alias candidates and the account read-revision key for downstream integration.
These backend-only primitives confer neither account access nor ownership.

### Search storage adjustment

An initial ordinary table with one row per gram/group exceeded the fixed preparation
budget. The compatible adjustment uses SQLite FTS5 as a compressed inverted index
of explicit, hex-encoded **1-, 2- and 3-character grams**, not a word/prefix search
engine. Grams are generated within whitespace-separated tokens, matching the
existing query tokenization; cross-whitespace grams cannot satisfy a query token.
Query grams intersect in SQL; the existing case-folded all-token substring
predicate remains the residual, including punctuation and Unicode. Encoded scope and
build terms prevent another build or archived scope from supplying candidates.
Document IDs encode the build-local group rank and public child count, avoiding a
large metadata join merely to recover candidate IDs and printing counts. Exact
common-word substring postings accelerate positive matches; words longer than 24
characters and variant-only matches retain the complete gram/residual path. This
accelerator cannot turn a match on different children into a same-child match.
`catalog_read_search` selects at most page-offset-plus-page-size candidate groups
for a printing page before joining compact child rows; exact totals still count the
complete matching postings. Alternate sorts page directly through ordered compact
common text plus residual matching ranks, without materializing every positive match.
Variant selectors use covering partial indexes; child pages explicitly select the
group-membership index before fetching metadata. Broad counts and deep pages can visit catalog-scale
compact indexes, but metadata fetching/JSON expansion stays page-bounded. Full integrity validation checks the FTS index against its
external-content records. SQLite must include FTS5; PostgreSQL V2 is explicitly
unavailable pending separate implementation and qualification.

Read snapshots use deferred SQLite transactions, leaving the established immediate
mutation transactions unchanged. Read connections use a bounded 64 MiB SQLite page
cache and in-memory compact SQL temporary results; these are disposable engine state,
not a catalog authority or a Python full-catalog cache. Preparation separately reuses
typed records and identical encoded terms within that single build; the bounded
word-token cache is discarded when preparation finishes. Memory measurements must account
for that per-connection memory when choosing concurrency.

### Public V2 contract

All following paths begin with `/api/v2/public/`. Every successful response includes
`read_version: 2`, `public: true`, and an opaque `catalog_revision`. Return that token
on subsequent pages and subresources. Responses are `no-store`. Duplicate/unknown
selectors return 400; a stale token returns 409; unavailable derived state returns
503 with `code: read_state_unavailable`. Neither failure initiates a migration,
rebuild, provider request or fallback full-catalog transfer.

| Path | Contract |
| --- | --- |
| `card-groups/` | Existing group selectors, exact `total/pages`, bounded `groups`, and `unresolved: {total,url}` |
| `species/<dex>/card-groups/` | Same list for canonical species 1–251; caller cannot override species or scope |
| `card-groups/<dg1>/` | Group summary, checked optional `child`, and separately paged `variants: {total,url}` |
| `card-groups/<dg1>/variants/` | Complete child metadata in pages; optional query and edition/finish/variant selectors stay on the same child |
| `card-group-filters/` | One complete dictionary through pages; `field=set` by default, also language/edition/finish/variant; exact total and `next` |
| `pokedex-species/` | Paged canonical species with current published printing/group counts; V1 public species query/set/era/type/region semantics |
| `catalog/` | Bounded resolved printing picker, with a separate unresolved-printing resource; retains exact IDs across pages |
| `catalog-unresolved/` | Paged printing metadata that cannot form a resolved group; optional all-token query |
| `evidence/` | Paged unresolved group evidence, retaining every record |
| `aliases/<literal>/` | Literal resolution; conflicting candidates return 409, unavailable destinations 404 |
| `resources/<kind>/<id>/` | Explicit complete JSON download for oversized group, printing, evidence or option records |

List resources default to 40 and cap at 100. An oversized item is an explicit
`{id, oversized:true, url}` reference (options use their resource URL); the complete
original value is available through that revision-bound download. It is never
truncated. Primary page summaries and metadata are limited independently of the
number of variants/evidence items. Search/variant-filtered group summaries expose a
`matching_variants.url`, so a client need not transfer an unbounded child-ID array.
Append the response-level `matching_filters` selectors to that URL to get the
matching subset; the URL alone returns every accessible variant of the group.
Filter pages are independent of search results and the current group page. Follow
`next` until null; never label the first dictionary page as the entire dictionary.

Example sequence: fetch `card-groups/?q=ivysaur`, retain its revision, open a returned
group with `?catalog_revision=<token>`, then follow its variants URL. Select a child
by supplying both `child=<literal-id>` and the same revision to detail. A stale token
requires reloading the current selection; a 503 requires explicit operator recovery.
Clients keep return/focus/scroll state in the browser/navigation layer and must
not send it as catalog selectors. Private scope remains the account service’s responsibility.

## Private and frontend consumers

See [account reads](account-reads.md) for private HTTP contracts, revision checks
and mutation invalidation, and [frontend reads](frontend-reads.md) for current
consumers, explicit continuation, selected labels, artwork and retained V1 tools.
