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
B4 roots expose published children in published sets; early B2 roots retain their
ordinary private legacy catalog. Supported other-game/language metadata retains
private catalog access. Guest scope uses `public_catalog.entries`: published
Pokémon/en metadata only, with no catalog exposure on roots without reviewed B4
publication. Public detail excludes archived children. Private owned scope includes
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
(including legacy private availability on early B2 roots); `catalog_available`
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

Variant filters include a group once if a eligible child matches. Such rows add
`matching_child_ids`; group possession, total and counts remain complete and
unchanged. Catalog filters match only catalog-available children; owned filters can
match retained archived children. Sorting is lexicographic, with primary selected
field case-folded, then case-folded set name, literal collector number, case-folded
name and stable group ID tie-break. Numbers are not numerically normalized.

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

Canonical HTML detail accepts a `return` destination only at `/cards/` or
`/card-library/`. It allows the ordinary list-filter keys excluding `scope` and
`generation`, plus ASCII integer `scroll` from 0 through 10000000. Duplicate and
unknown keys, unsupported filter values, external URLs, fragments and literal
control characters reject. Return context never selects a child or becomes part
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

`/api/collection-context/` is an authenticated, account-bound, generation-checked
browsing bootstrap. It returns only authority, binder choices, copy identity pairs
for duplicate counts and goal labels/versions. It excludes full effective printing
maps, source/history bodies, goal checklists and inventory attributes. It accepts
no query selectors and retains private/no-store policy.

My Cards, Card Library and card/species pages use this small context before their
existing scoped/paged APIs. Explicit collection tools load the full existing
`/api/collection/` response on demand. Late tool responses must still match the
active data object, route, account and generation before merging or opening a
form. Card editing uses its already checked detail summary; server preview and
confirmation remain authoritative.

Grouping/filtering still reads authoritative metadata and current ownership on
each request, without a shared private cache. Artwork descriptors are bound only
for a returned page/detail after filtering and pagination. Filter-option reads
bind no images. Counts, conflict handling, archived context, exact identity and
account/generation checks remain unchanged.
