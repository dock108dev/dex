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
| Scalar HTTP selectors | `beta/request_inputs.py:single_values/query`; `card_group_views.query` is the same function export for existing callers |
| Authentication and account scope | Django auth, `beta/accounts.py`, `beta/store.py` |
| Schema and explicit legacy import | `inventory.py`, `migration.py` |
| Collection preview, confirmation and undo | `beta/collection.py`, `beta/transactions.py`; `collection_plans.py` builds plans through account-scoped readers |
| Shared catalog reads and collection serialization | `beta/collection_catalog.py`, `beta/collection_imports.py` |
| Canonical species identity | `beta/canonical_species.py` and its hash-pinned registry |
| Current possession and nullable card totals | `beta/effective_collection.py:project` |
| Reviewed ownership and quantity intents | `beta/collection_intents.py:plan/augment_plan/check_undo` through collection preview/confirm/undo |
| Declaration schemas and source scope | `beta/ownership_declarations.py:header_scope`; parsing, current selection and frozen declaration goals share it |
| Copy edition identity and selection | `beta/copy_editions.py:is_first/require_first_supported/select`; collection creation/import, bulk resolution and photo additions delegate to it |
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
| Official listing money and cost projection | `beta/listing_prices.py`, delegating decimal admission/rounding to `shopping_math`; Discovery, Hunter, official details and Hunter lot reviews share it |
| Shopping history and original research | `beta/shopping.py:store_payload/reopen/reevaluate`, delegated to by `shopping_views.py` |
| Lot selection, wants and guide cells | `beta/lot_calculator.py`; `beta/lot_guides.py` projects supplied admitted records |
| Private price lifecycle | `beta/price_snapshot_contract.py`, `beta/price_snapshots.py`, `beta/price_snapshot_sources.py` |
| Shopping input and temporary state types | `beta/discovery_contracts.py`; `discovery.py` preserves the `Choices`/`Run` imports used by Hunter and other callers |
| Finite Shopping acquisition | `beta/discovery.py`, `beta/discovery_transport.py`, `beta/listing_check.py`; orchestration retains account/session checks, locks, deadlines and accounting |
| Bulk listings Hunter | `beta/hunter.py`, `hunter_views.py`; `hunter_query.py` checks provider parameters; `hunter_traversal.py` captures finite plans/cursors; `hunter_policy.py` owns ordinary owner-selected usage; `hunter_budget.py` preserves independent finite qualification allowances |
| Local Hunter identity/reference batches | `beta/hunter_catalog.py` indexes; shared literal `beta/discovery_matching.py` and `discovery_comparison._project`; admitted `lot_calculator.retained_records`, `lot_guides` and `shopping_math` retain lifecycle, source selection and arithmetic; no second store |
| Hunter opportunity scenarios | `beta/hunter_ranking.py` projects freshly admitted rows through existing Shopping arithmetic and ranks equivalent cost/applicability groups |
| Hunter screen and review rendering | `beta/templates/beta/hunter.html`, `beta/static/hunter.js`, `hunter-review.js`, `hunter.css`; authenticated `hunter_views` resolves checked image bindings and bounded all-era correction choices; services retain arithmetic and authority |
| Hunter lot text and quantity proposals | `beta/hunter_lot_parser.py` interprets supplied authorized text and printing identities; `hunter_lots.parse` remains the compatible export |
| Hunter temporary lot reviews | `beta/hunter_lots.py` reauthorizes leases and supplies all-era adapters to `lot_calculator.prepare`; `hunter_lot_details.py` explicit official details share original lease and durable allowance, disabled by default |
| Listing identifiers and response projection | `beta/listing_details.py`; `listing_check.py` retains compatible public imports |
| Visual local Shopping search | `beta/discovery_catalog.py`, using checked card groups, current/frozen collection scope and image bindings |
| Captured query, category and finite continuation | `beta/discovery_search.py`, `beta/discovery_paging.py`; no ownership or reference-value authority |
| Temporary listing image/time admission and rendering | `beta/discovery_listing.py`, `beta/static/discovery-display.js`, shared `beta/static/listing-time.js`; safe seller URLs remain in `security.ebay_url` |
| Discovery applicability and result order | `beta/discovery_comparison.py:compare`; `beta/goal_hunts.py` supplies collection/goal scope |
| Provider settings and historical hunt projections | `config.py`, `beta/ebay_hunts.py:configuration/status`, `hunt.py`, `beta/hunt_values.py` |
| Manual bulk drafts and replay identity | `beta/bulk_input.py`, `beta/collection_drafts.py`, `beta/bulk_views.py`, with collection mutation authority |
| Photo jobs and batch review | `beta/scans.py`, `scan_worker.py`, `scan_config.py`, `codex_recognition.py`, `photo_batches.py`, `photo_batch_journal.py`, `batch_recognition.py` |
| Synthetic sealed-offer replay | `beta/refresh.py`; no live acquisition adapter |
| Bounded group-metadata acquisition | `metadata_collector.py`; explicit fixed TCGCSV group request, independent Stop and consumed reservation |
| Image identity and private access | `beta/image_mappings.py`, pinned mapping data, `beta/image_bindings.py`; `scans.authorized_photo_rows` owns photo authorization |
| Private navigation and Shopping context | `beta/navigation.py`, `beta/shopping_context.py`, `beta/static/navigation.js` |
| Card/species rendering | `beta/static/card-screens.js`, `species-screens.js`, `public-species.js`; `collection.js:render` dispatches by route |
| Overview, hunt history and retained per-copy guides | `beta/parity.py`, `beta/static/parity.js`; no card/species renderer or new hunt acquisition |
| Ingress, diagnostics and deployment | `security.py`, `beta/security.py`, `asgi.py`, `diagnostics.py`, `deployment.py`, `support.py` |

## Scalar request authority

`request_inputs.single_values` checks Django multi-value containers before they
become plain dictionaries. `query` applies that rule to GET selectors. Card,
species, navigation and Shopping adapters retain the existing `card_group_views.query`
import, which exports the same function; public catalog and guest/private Pack
lookup use it directly. Lookup save applies `single_values` to its scalar form.
Repeated fields (even equal or blank values) and unknown allowlisted fields fail
before projection or saving. Domain owners still validate values and account scope.
Discovery/Hunter status reads, listing-load status and bulk template selection also
use this boundary. Original Shopping catalog filters reject repeated and unknown
fields before catalog/reference reads; offset validation precedes those reads too.
Intentional lists, such as listing/catalog restore IDs, refresh source choices and
photo uploads, retain their own multi-value schemas.

## Engineering tool boundaries

Snapshot execution stays in `scripts/capture_tcgcsv_snapshot.py`; its pure
contract, read-only history and HTTP/watchdog adapters are the sibling
`tcgcsv_capture_contract.py`, `tcgcsv_capture_history.py` and
`tcgcsv_capture_transport.py` modules. They share one `CaptureRefused` type and
preserve serialized plans, immutable reservations and fixed historical identities.
Browser qualification separates `qualify_hunter_ui.py` process ownership from
`hunter_ui_journey.py`'s ordered checks. The journey retains one browser context,
held responses and final cleanup.
See [maintenance conventions](local-development.md#maintenance-conventions) for
structure, fixture ownership and retained lifecycle boundaries.

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
and return context without inventing ownership or quantities. `validate_identity`
shares bounded syntax with existing return validation; only `resolve` reauthorizes.
Card Library retains a checked species return and goal/version/generation. Shopping
catalog selection and internal Card details are separate controls; detail returns
reuse the original authenticated Shopping state and temporary handle. The existing
return validator allows at most six nested edges and 4,096 characters, reauthorizing
each private object; it never renews result leases or acquires listings.
`discovery_catalog.entry_refinements` maps inherited single-set context and explains
unsupported collection criteria. Search refinements stay outside identity fields.
Client drafts retain
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

[Shopping](hunts.md) defines primary named Search/Stop/More, optional visual local search, singles/loose lots/auctions, immediate recognizable temporary
results and acquisition ceilings. Named runs use one checked category page per explicit
action, at most four pages total, preserving original expiry and captured choices.
Reveal remains a compatibility read action. `discovery_comparison.compare` owns applicability
and sorting; response projection preserves that order. Authenticated `/api/hunts/`
POST returns 410; historical schemas and read/reveal routes remain supported.

## Listing value authority

`listing_prices.py` owns supplied official listing amounts, auction/buy-now selection
and shipping projections. `shopping_math.amount/money` owns decimal strings, precision,
the amount ceiling and rounding. Discovery comparison, Hunter minimum bids, official
details and Hunter lot review inputs delegate to this policy; the original watcher's
`pricing.py` remains specific to its separate threshold/count contract.

Unsupported numeric shapes, precision, negative/nonfinite amounts and amounts above
the ceiling remain unknown. An invalid shipping amount does not erase a valid listing
price. An auction's missing current bid never uses its buy-now amount. Foreign detail
amounts remain labelled display inputs and cannot become USD comparisons.

Two shipping projections remain intentional: a summary can show the cheapest explicit
supported USD option; review inputs require one agreed amount/currency across supplied
options. Both use the same amount admission. Unknown shipping never means free.
`discovery_listing.end_timestamp`, backed by `hunter_query.utc_time`, is the shared
timestamp admission path. Invalid summary times remain unknown; a supplied invalid
official-detail end time fails explicitly before the detail can be used.

Search text normalization belongs to `discovery_search.submitted_query` and takes no
product-category option. Actual Singles/Mixed lots/Both choices remain active through
`discovery_paging` and the captured acquisition plan.

## Assisted listing and lot checks

`listing_details.py` validates supplied identifiers and official response bodies;
`listing_check.py` owns finite loads and session-private reviews. Comparisons delegate
to the admitted-reference calculator. See [listing checks](hunts.md#check-a-listinglot)
and [snapshot lifecycle](price-snapshots.md). Temporary edits are saved to the
account/session-bound in-memory review through `listing_views.review` and
`listing_check.review`; autosave/Back share its original lease. Permanent saved
research and export are unavailable for these temporary reviews.

## Manual bulk entry

Bulk input joins the same collection preview/confirm/undo authority, with revisioned
drafts, stable replay aliases and explicit separate-batch identity. The complete
[bulk entry contract](effective-collection.md#manual-bulk-entry) defines formats,
duplicates, quantities, errors and recovery.

## Copy edition policy

`copy_editions.is_first` recognizes both retained catalog spellings (`first_edition`
and `1st-edition`) for creation, bulk resolution and import. Import must accept
an edition that creation can export. `require_first_supported` rejects first-edition
selection for the retained Base Set 2 and Wizards promo identities; selection and
import share this restriction. `select` owns per-copy edition uncertainty and
revision changes. Import still validates its serialized flag and uncertainty fields;
shared policy does not rewrite an exported identity or silently resolve it.

## Multiple-card photo batches

`photo_matching.py` owns visible-evidence normalization and catalog suggestions;
`photo_additions.py` plans photo-specific duplicate skips and edition updates through
`copy_editions`, with confirmation/Undo still owned by collection transactions.
Photo batches retain independent jobs, reservations and deletion tombstones while
binding selected crops through ordinary collection confirmation. See
[photo storage and shared review](photo-entry.md#storage-and-shared-review) and
[photo rows in collection review](effective-collection.md#photo-rows-in-the-shared-review).
