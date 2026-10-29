# PERF-03 account reads

This is the backend contract for the disposable SQLite account representation.
It does not install a successor or change the customer's collection. V1 callers
remain compatible. PERF-04 must adopt V2 before these reads affect the interface;
RUNTIME-DELIVER and owner acceptance remain separate work.

## Representation and authority

`account_read_schema`, `account_read_build`, `account_read_records`,
`account_read_goals`, `account_read_species`, `account_read_select`,
`account_read_queries` and `account_read_views` compose the checked PERF-02 build
with account-local derived records. The existing effective-collection evaluator
and frozen-goal progress evaluator remain authoritative. Their pure evaluation
steps are shared with preparation; arbitrary caller-provided rows cannot obtain
an authenticated read snapshot.

The account key binds internal account ID, collection generation, account-read
revision, retained source digest, catalog revision and ownership-policy version.
The response's `account_revision` is a seal over that identity and derived counts.
It is a consistency token, not a credential. Catalog preparation retains full
policy metadata separately from bounded public display records. Account rows
retain broad possession, nullable established quantity, current/recorded copy
references, exact-variant qualifications, declarations and unresolved evidence.
Broad quantity never becomes a count of an individual variant. All species
quantities remain unknown; current presence and frozen-goal progress are distinct.

`ar_membership` provides compact filtering/sort indexes. Group summaries exclude
artwork and copy arrays. `ar_scope_catalog` and `ar_scope_owned` retain the scalar
facts produced by the existing species evidence policy. SQL implements its
three-valued scope matching: supported, excluded or insufficient evidence.
Date/finish scope counts are aggregated once per catalog revision with exact
weights; other scopes retain per-printing facts. Complete species filter options
are also prepared once, with separate paged reads. Exact
finish requires exact ownership evidence. Date precision remains an interval;
unknown release dates do not establish completion in a dated scope. Goal items
and printing dependencies retain the frozen definition/version rather than
reconstructing membership from today's catalog.

## Mutations and invalidation

Confirmation and Undo capture a compatible prepared revision before authoritative
writes, then refresh in a nested savepoint inside the same transaction. The closure
joins literal and canonical identity conflicts, affected copy IDs and their indexed
operation dependencies. Only changed derived group/card/copy/evidence rows are
written. Species aggregates are refreshed from retained account-card records for
the affected species, not a fresh catalog or full journal. Add, edit, removal,
resolution, broad-card intents, bulk confirmation and controlled manual photo
confirmation use the ordinary mutation path. The confirmation receipt remains the
idempotency authority.

Imports and source replacement may explicitly prepare the entire account in the
mutation transaction. Goal definition changes prepare frozen-goal records. The
existing PERF-02 authority triggers cover maintenance writes independently of
application hooks. Missing prior preparation, a changed catalog, failed refresh
or an oversized dependency closure leaves V2 unavailable. The code never replays
a confirmed mutation to repair reads. Catalog activation requires subsequent
account preparation against the activated build; browsing never repairs it.

Ordinary closure safety bounds are 100 input identities, 2,000 retained dependent
records and 4 MiB of selected dependency payload. Retained source bundles larger than
4 MiB also defer ordinary incremental preparation. Global source/history conflicts
require explicit preparation. These cases return unavailable, not stale or
partial ownership. Whole-account preparation is explicit and separately timed.

Derived writes do not advance authority revisions. Guard triggers mark a ready
account corrupt when derived records change outside a preparation transaction.
Shared derived metadata changes invalidate every ready account. Row digests,
manifest seals, schema version and required triggers are checked; damaged
infrastructure requires explicit repair. These safeguards concern accidental or
unsupported database changes, not hostile access to the database owner account.

## Private HTTP contract

All routes below start with `/api/v2/`, require an authenticated active account
with a supported role, and return `Cache-Control: private, no-store`, including
errors. Account identity comes exclusively from server authority. Every success
includes `read_version: 2`, `public: false`, `account_id`, `generation`,
`catalog_revision` and `account_revision`. Optional revision selectors bind later
pages/subresources. Every request checks authority before reading and after the
coherent SQLite snapshot, immediately before releasing its result.

| Route | Contract |
|---|---|
| `card-groups/` | Private catalog/owned filters and stable set/name/number ordering; exact total and bounded page |
| `my-card-groups/` | Fixed current-owned scope |
| `card-group-filters/` | One `field` and `scope` per page, exact total and `next`; set/language/edition/finish/variant |
| `card-groups/<id>/` | Small group detail plus separate subresource links/counts |
| `card-groups/<id>/variants/` | Paged children; physical exact ownership and declared variant support stay separate |
| `card-groups/<id>/copies/` | Paged active recorded copies with separate current flags |
| `card-groups/<id>/history/` | Paged inactive/removed copy history |
| `card-groups/<id>/evidence/` | Paged relevant unresolved evidence |
| `card-groups/<id>/artwork/` | Only this group's retained artwork descriptor |
| `species/<dex>/card-groups/` | Fixed canonical species 1–251, ordinary group selectors |
| `pokedex-species/` | Paged current/frozen species summaries; query, region, owned, set, era, type, rarity, finish, card and release/date filters |
| `species-filter-options/` | Complete options through continuation for set/era/type/rarity/finish/year |
| `collection-context/` | Small collection counts and read links, no all-copy bootstrap |
| `duplicate-counts/` | Up to 100 distinct literal printing IDs; recorded/current counts remain distinct |
| `catalog/`, `catalog-unresolved/` | Bounded private printing picker (`printings`), q/set/language selectors, stable ID order |
| `evidence/` | Paged account-local unresolved evidence |
| `aliases/<key>/` | Checked alias resolution, collision rejection and accessible group identity |
| `copies/<id>/photos/` | Independently authorized active-copy photos, current tombstone/rights checks |
| `resources/<kind>/<key>/` | Independently authorized full record, explicit JSON attachment |

Pagination defaults/maxima follow PERF-02 (`page`, `page_size`, maximum 100).
Group selectors preserve V1 same-child matching. Private membership is retained
independently of public membership. Optimized public selection is used only after
preparation proves equivalent catalog membership; owned selection always uses the
account representation. Archived owned/recorded groups remain available under
the existing private rules. Unresolved metadata remains separately addressable.

Inline records larger than 1,100 bytes are replaced by an explicit resource link;
filter values over 200 bytes use the same mechanism. Full resources are complete,
not silently truncated. Copy fields are explicitly allowlisted. Resources include
group, copy, card, species, evidence, artwork, goal, printing and filter options.
The original photograph-serving endpoint independently authorizes the actual
image; a cached descriptor cannot grant access. No new provider request occurs.

Invalid/duplicate/unsupported selectors return 400. A supplied stale revision or
a revision changing during a read returns 409. Missing, incompatible, corrupted
or stale derived state returns the contracted `read_state_unavailable` 503.
Missing/foreign resources return 404; inactive/revoked/unauthenticated access
returns 403. All resource routes repeat these checks. Public V2 uses no account
representation, and mutation validation never trusts cached possession.

## Later delivery and recovery

Do not run these against the customer root as part of PERF-03. Later delivery must
follow the backup and runtime-selection rules in `operations.md` and
`local-development.md`. On an approved existing installation, use the selected
application Python and root, after PERF-02 migration/preparation/activation:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.account_read_operator --root "$DEX_APP_ROOT" migrate
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.account_read_operator --root "$DEX_APP_ROOT" --username "$DEX_ACCOUNT_USERNAME" prepare
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.account_read_operator --root "$DEX_APP_ROOT" --username "$DEX_ACCOUNT_USERNAME" status
```

`discard` removes only the named account's disposable records. `prepare` rebuilds
from current authority and never replays receipts. `repair-schema` explicitly
removes all account-derived tables/shared policy metadata and recreates the
schema; every account then requires preparation. Authority, users, copies,
receipts, goals, source text and revision counters remain intact. No command
creates a new installation, resets credentials or silently runs on GET/startup.

PERF-04 should use response links/revision selectors, clear private screen state
on logout/account changes, cancel obsolete requests, fetch artwork separately,
and render unknown quantities and 503 recovery honestly. Use paged filter options
instead of assuming first-page completeness. Keep UI focus/scroll selectors out
of data requests. The printing picker returns `printings`, not the public
adapter's `cards`; map that explicitly. No V1 JavaScript adoption is in this slice.

OPS-READINESS should orchestrate catalog activation then account preparation,
expose readiness per active account/revision, make recovery an explicit operation,
and distinguish a listening process from browsing readiness. Source replacement
and large closure preparation can take longer than an ordinary edit. SQLite
qualification does not establish PostgreSQL compatibility, hosted CI, installation
or owner acceptance. See `CI.md` for exact-candidate measurements and limitations.

## PERF-04 compatible interface additions

Ordinary Goals reads now use `goals/` (paged headers and indexed progress counts),
`goals/<id>/items/` (paged frozen targets), and `goal-sources/` (paged selectable
collection sources). No request rebuilds membership. Large headers/targets use explicit
`resources/goal-header/<id>/` or `resources/goal-item/<id>/` reads. A full single goal
resource is reserved for an explicit successor editor. `goal-options/` carries only
ID, name and supported status; it does not include editor filters or frozen items.

`labels/?items=[{"kind":"set","id":"…"}]` resolves at most 100 retained literals;
private binder/goal labels remain account scoped. Exceptional labels expose an explicit
complete-record reference. `selected-groups/?ids=…` resolves at most 100 accessible
saved-draft identities. `entry-options/` pages at most 50 game/set choices and represents
large choices with explicit resources. `game_key` only applies to game choices.

Public/private `group-artwork/?ids=…` and `species-artwork/?ids=…` accept at most 100
unique identities. Public group descriptors use digest-checked published prepared groups
and the existing reviewed mapping/source policy. Private group descriptors require
account-accessible groups. Neither route exposes private copy photos. All new private
reads retain account authentication, revision checks, no-store and unavailable-state
behavior. `X-Dex-Read-Account` is an optional mismatch guard for an already-open page;
it cannot choose an account or grant access.

Species scope includes `progress_basis` so frozen declaration progress is labelled
separately from qualified-current-copy progress. Goal edits with `preserve_membership`
accept only ID, revision, name and unchanged kind, and retain the exact stored definition
and version. Replacement is a separate goal; it never reconstructs historical filters.

Deploying these consumers requires explicit account preparation with this candidate.
An older goal representation without the new header is unavailable (503), rather than
being mislabelled as a historical definition without filters. No GET upgrades it.
The ordinary entry-picker page includes at most 50 choices; oversized choices on its
first page remain reachable through explicit complete-record expansion as well as
later-page choices.

## OPS representation and runtime follow-up

OPS versions the prepared representation policy as `effective-collection-2-goal-headers`.
Old goal headers now fail account readiness even when the old manifest is otherwise
intact; explicit preparation is required. No additive schema-version reset is needed.
Catalog-schema repair must be followed by account-schema repair because indexes on
replaced catalog tables belong to both read services.

Ordinary-runtime profiling also exposed repeated positive FTS posting selection in
owned search, which the earlier catalog-search performance case did not exercise.
Count remains exact; page selection now uses common-text matches plus exact residual
ranks, following the existing public-search strategy. New owned-search/short-query
performance cases and ordering/empty/deep-page parity checks qualify that adjustment.
See [OPS evidence](ops-readiness-evidence-20261028.md) for retained budget failures;
prior PERF-03 qualification does not automatically qualify this integrated candidate.
