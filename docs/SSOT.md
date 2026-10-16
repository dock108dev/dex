# Architecture and data ownership

This map identifies the owner of each shared policy. Domain guides define the
full contracts; callers should delegate to these owners rather than create
parallel readers, validators or mutation paths.

## Entry points and storage

| Entry point | Storage and runtime | Guide |
| --- | --- | --- |
| Authenticated collection app | Django and uvicorn on local port 8011; private root with SQLite inventory, auth, secret and provider configuration | [Local development](local-development.md) |
| Optional hosted profile | PostgreSQL with separate web and worker processes, explicit HTTPS configuration | [Operations](operations.md#optional-postgresqlhttps-profile) |
| Original FastAPI app | Separate ownership JSON in `config/pokedex_251.json` and saved hunts in `data/collection_hunts.db` | [Original app](ORIGINAL_APP.md) |
| Daily lot watcher | Separate local watcher configuration, observations and notification state | [Watcher](legacy-watcher.md) |

These stores do not synchronize automatically. Public browsing receives
allowlisted published metadata; private projections require a verified account.
Source checkouts contain code and public inputs, not a personal installation.

## Authoritative services

Paths are relative to `src/pokemon_hunter/`.

| Responsibility | Owner |
| --- | --- |
| Runtime profile and initialization | `beta/staging_config.py`; `beta/cli.py`, `settings.py` and `urls.py` consume the selected profile and capability markers |
| Authentication and account scope | Django auth, `beta/accounts.py`, `beta/store.py` |
| Schema and explicit legacy import | `inventory.py`, `migration.py` |
| Collection preview, confirmation and undo | `beta/collection.py`, `beta/transactions.py`; `collection_plans.py` builds plans through account-scoped readers |
| Shared catalog reads and collection serialization | `beta/collection_catalog.py`, `beta/collection_imports.py` |
| Canonical species identity | `beta/canonical_species.py` and its hash-pinned registry |
| Current possession and nullable card totals | `beta/effective_collection.py:project` |
| Reviewed ownership and quantity intents | `beta/collection_intents.py:plan/augment_plan/check_undo` through collection preview/confirm/undo |
| Declaration schemas and source scope | `beta/ownership_declarations.py:header_scope`; parsing, current selection and frozen declaration goals share it |
| Finite card defaults | `beta/collection_defaults.py`, through the existing operation journal |
| Frozen goal membership | `beta/broad_goals.py:species_items`, `beta/goal_filters.py:printing_items`; callers retain their stored eligibility policies |
| Display groups and literal mutation adapters | `beta/card_groups.py`, `beta/card_group_views.py` |
| Species routes and private projections | `beta/species_views.py`, `beta/species_projection.py`, `beta/species_scope.py` |
| Guest metadata and lookup | `beta/public_catalog.py`, delegated to by `beta/public_views.py` |
| Reviewed publication | `beta/catalog_imports.py`, `beta/sealed_catalog.py`, `beta/sealed_bridge.py`; `sealed_contract.py` owns sealed package schemas |
| Coverage and publication checkpoints | `beta/catalog_coverage.py`, `beta/catalog_pipeline.py` |
| Pack lookup and saved research | `beta/lookup.py`, `beta/packs.py`, `beta/product_lookup.py`, `beta/pack_research.py` |
| Offer age and eligibility | `beta/offer_filters.py`, using original observation times |
| Retained-reference admission | `reference_policy.py`; domain services add printing, grade and source-rights checks |
| Shopping arithmetic and input shapes | `beta/shopping_math.py`, `beta/shopping_inputs.py`; `shopping.py` preserves established validator imports |
| Shopping history and original research | `beta/shopping.py:store_payload/reopen/reevaluate`, delegated to by `shopping_views.py` |
| Lot selection, wants and guide cells | `beta/lot_calculator.py`; `beta/lot_guides.py` projects supplied admitted records |
| Private price lifecycle | `beta/price_snapshot_contract.py`, `beta/price_snapshots.py`, `beta/price_snapshot_sources.py` |
| Finite Shopping acquisition | `beta/discovery.py`, `beta/discovery_transport.py`, `beta/listing_check.py` |
| Listing identifiers and response projection | `beta/listing_details.py`; `listing_check.py` retains compatible public imports |
| Visual local Shopping search | `beta/discovery_catalog.py`, using checked card groups, current/frozen collection scope and image bindings |
| Captured provider query and product eligibility | `beta/discovery_search.py`; no ownership or reference-value authority |
| Discovery applicability and result order | `beta/discovery_comparison.py:compare`; `beta/goal_hunts.py` supplies collection/goal scope |
| Provider settings and historical hunt projections | `config.py`, `beta/ebay_hunts.py:configuration/status`, `hunt.py`, `beta/hunt_values.py` |
| Manual bulk drafts and replay identity | `beta/bulk_input.py`, `beta/collection_drafts.py`, `beta/bulk_views.py`, with collection mutation authority |
| Photo jobs and batch review | `beta/scans.py`, `scan_worker.py`, `scan_config.py`, `codex_recognition.py`, `photo_batches.py`, `batch_recognition.py` |
| Synthetic sealed-offer replay | `beta/refresh.py`; no live acquisition adapter |
| Bounded group-metadata acquisition | `metadata_collector.py`; explicit fixed TCGCSV group request, independent Stop and consumed reservation |
| Image identity and private access | `beta/image_mappings.py`, pinned mapping data, `beta/image_bindings.py`; `scans.authorized_photo_rows` owns photo authorization |
| Private navigation and Shopping context | `beta/navigation.py`, `beta/shopping_context.py`, `beta/static/navigation.js` |
| Card/species rendering | `beta/static/card-screens.js`, `species-screens.js`, `public-species.js`; `collection.js:render` dispatches by route |
| Overview, hunt history and retained per-copy guides | `beta/parity.py`, `beta/static/parity.js`; no card/species renderer or new hunt acquisition |
| Ingress, diagnostics and deployment | `security.py`, `beta/security.py`, `asgi.py`, `diagnostics.py`, `deployment.py`, `support.py` |

## Cross-cutting invariants

- Client IDs and browser context are selectors, not authority. Services verify
  account access and relevant collection generation before returning private data
  or accepting a mutation.
- Catalog metadata, current possession, physical copies, frozen goals and retained
  research are distinct records. A source observation or image never grants ownership.
- Preview, confirmation and undo share the operation journal. Revisions, generation
  checks and replay identity prevent stale or repeated input from becoming another
  addition; recovery inspects the saved operation rather than assuming success.
- Unknown identity, quantity, condition, price, stock and costs remain unknown.
  Recorded copies are not an exhaustive total, and a card total is never allocated
  to variants or multiplied into a valuation.
- Source identity, original dates and rights survive projection. Reading a page,
  receiving a response or importing a file does not establish freshness or permission.
- Provider requests require explicit supported actions. Deadlines and Stop suppress
  late dispatch/publication; consumed or uncertain attempts are not refunded or reset.
- Initialization, migrations and operational writes are explicit. Browsing does not
  reseed an installation, enroll items into an old goal or migrate its schema.
- Private credentials, prices, uploads and acquisition content stay outside public
  metadata and repository inputs. Recovery preserves independent reservations,
  revocations and deletion records; use the documented backup exclusions.

## Ownership and goal contracts

Current collection projection and reviewed editing belong to
[effective collection](effective-collection.md). Goal definitions freeze membership,
source references, policy and version hashes; catalog publication does not enlarge
a saved checklist. [Catalogs and goals](catalogs.md#collection-and-goals) describes
the distinction between species and exact-printing completion.

## Public evidence and private research

Public publication and account-private research have separate admission and storage
boundaries. Saved lookup/history preserves captured inputs and dates; reevaluation
creates a separate result. See [catalog publication and lookup](catalogs.md) and
[private price snapshots](price-snapshots.md).

## Jobs, configuration and compatibility

Workers claim durable authority before provider I/O. Recognition modes, configuration
validation and job recovery are defined in [photo entry](photo-entry.md),
[operations](operations.md) and [recovery](ERROR_HANDLING.md).
Persisted schema names, root markers, routes and CLI flags are compatibility contracts;
retiring them requires a migration or explicit support decision.

## Image authority

The [image contract](artwork.md) defines species art, group references, exact-child
availability and private copy photos. Mapping and access adapters consume checked
identity and authorization; they do not supply possession, totals or navigation policy.

## Card flow and request authority

[Card groups](card-groups.md) owns canonical identity, API fields, filtering and literal
mutation adapters. [Interface design](UI_DESIGN.md#cards) owns the screen hierarchy,
control behavior and Back/focus rules. Card browsing and editing use these contracts
independently of parity valuations.

## Pokémon screens and read authority

Species views combine canonical identity, current collection and saved-goal services
at a checked account/generation. Guest metadata has no inferred personal status.
See [collection semantics](effective-collection.md) and
[Pokémon interface behavior](UI_DESIGN.md#pokémon-and-completion-scopes).

## Navigation and Shopping adapters

`navigation.py` validates finite local destinations and reauthorizes private targets.
`shopping_context.py` binds species or group/optional child, goal/version, generation
and return context without inventing ownership or quantities. Client drafts retain
only permitted user inputs and require explicit comparison after restoration.
See [navigation and access](UI_DESIGN.md#navigation-and-access),
[card return context](card-groups.md#list-controls-and-return-context) and
[Shopping context and drafts](hunts.md#contextual-collection-entry-and-lot-drafts).

## Pokédex scoped completion

`species_scope.py` matches finite criteria against one evidence record using
three-valued results. Display filters never change target membership or frozen goal
policy. [Scoped release evidence](catalogs.md#scoped-release-evidence) defines dates;
[Pokémon interface behavior](UI_DESIGN.md#pokémon-and-completion-scopes) defines controls.

## Shopping discovery

[Shopping](hunts.md) defines visual local search, Search/Stop/Next, singles/loose lots/auctions, reveal, temporary
results and acquisition ceilings. `discovery_comparison.compare` owns applicability
and sorting; response projection preserves that order. Authenticated `/api/hunts/`
POST returns 410; historical schemas and read/reveal routes remain supported.

## Assisted listing and lot checks

`listing_details.py` validates supplied identifiers and official response bodies;
`listing_check.py` owns finite loads and session-private reviews. Comparisons delegate
to the admitted-reference calculator. See [listing checks](hunts.md#check-a-listinglot)
and [snapshot lifecycle](price-snapshots.md); temporary review has no save operation.

## Manual bulk entry

Bulk input joins the same collection preview/confirm/undo authority, with revisioned
drafts, stable replay aliases and explicit separate-batch identity. The complete
[bulk entry contract](effective-collection.md#manual-bulk-entry) defines formats,
duplicates, quantities, errors and recovery.

## Multiple-card photo batches

Photo batches retain independent jobs, reservations and deletion tombstones while
binding selected crops through ordinary collection confirmation. See
[photo storage and shared review](photo-entry.md#storage-and-shared-review) and
[photo rows in collection review](effective-collection.md#photo-rows-in-the-shared-review).
