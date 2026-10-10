# Architecture and data ownership

## Entry points and storage

The collection app is Django, served by uvicorn on `127.0.0.1:8011`.
Public browsing uses allowlisted published catalog metadata; signed-in templates
and plain JavaScript consume private, account-scoped projections. A private root holds SQLite inventory, authentication data, the
Django secret and provider configuration. The optional staging profile uses
PostgreSQL and separate web/worker processes; see [operations](operations.md).

The original FastAPI app and daily lot watcher are separate entry points. Their
ownership JSON and hunt database are not automatically synchronized with the
authenticated app. See [original app](ORIGINAL_APP.md) and
[watcher](legacy-watcher.md). Local startup is documented in
[development](local-development.md); validation commands belong to [CI](CI.md).

## Authoritative services

Paths in this table are relative to `src/pokemon_hunter/`.

| Responsibility | Source and contract |
|---|---|
| Local initialization and serving | `beta/staging_config.py` owns runtime profile selection; `beta/cli.py`, `beta/settings.py`, `beta/urls.py` consume it and root capability markers; unsupported profiles/actions fail before local initialization, with no automatic reseeding |
| Authentication and account access | Django auth, `beta/accounts.py`, `beta/store.py`: active mapped account and account-scoped queries; client IDs are selectors, not authority |
| Guest browsing | `beta/public_catalog.py`, `beta/public_views.py`: shared canonical species and allowlisted published card metadata; no default account, ownership or private sources |
| Schema and import | `inventory.py`, `migration.py`: compatible additive schema initialization and explicit legacy import |
| Physical copies and mutations | `beta/collection.py`, `beta/transactions.py`: preview, confirmation, idempotency and conflict-aware undo |
| Collection serialization and shared printing reads | `beta/collection_imports.py`: import shape, version hashes and frozen checklist validation; `beta/collection_catalog.py`: shared metadata queries; account verification and mutation authority remain in `beta/collection.py` |
| Canonical species identity | `beta/canonical_species.py`: hash-pinned public registry; mutable catalog names and private evidence are not identity authorities |
| Frozen collecting goals | `beta/broad_goals.py:species_items` groups species membership for filtered, Vintage 251, Original 151, declaration goals and lookup; `beta/goal_filters.py:printing_items` owns printing checklist shape; callers retain their eligibility policies and stored versions |
| Declaration-based ownership | `beta/ownership_declarations.py`: account-local source revisions separate from physical copies |
| Public catalog publication | `beta/catalog_imports.py`, `beta/sealed_catalog.py`, `beta/sealed_bridge.py`: reviewed packages, atomic publication, journaled correction/rollback |
| Catalog coverage and batch checkpoints | `beta/catalog_coverage.py`: pinned universe/alias inputs and read-only projections; `beta/catalog_pipeline.py`: assessment, reviewed checkpoints and existing publication services |
| Pack lookup and saved research | `beta/lookup.py`, `beta/packs.py`, `beta/product_lookup.py`, `beta/pack_research.py`: possible/guaranteed coverage and frozen account-local snapshots |
| Offer age and eligibility | `beta/offer_filters.py`: original observation age and conservative evidence decisions |
| eBay request validation/scoring | `hunt.py`, `beta/ebay_hunts.py`, `beta/goal_hunts.py`, `beta/hunt_values.py`: explicit search, frozen scope, current ownership and dated guide comparison |
| Photo jobs | `beta/scans.py`, `beta/scan_worker.py`, `beta/scan_config.py`, `beta/codex_recognition.py`: durable claims/reservations, configured provider and explicit inventory confirmation |
| Replay refresh | `beta/refresh.py`: bounded synthetic-only replay; no live acquisition adapter |
| Lot calculator and retained-guide admission | `beta/lot_calculator.py`: vintage account-scoped selector, session-private wants, separate included quantities, four scenarios and the preexisting-guide admission boundary |
| Shopping input validation | `beta/shopping_inputs.py`: shared fields, text, cost and original-research input shapes; `beta/shopping.py` preserves public imports; no database/account reads in validators |
| Shopping arithmetic | `beta/shopping_math.py`: decimal totals, partial coverage, unknown costs and per-card versus group-total scope; both calculator and original research preparation delegate to this evaluator |
| Shopping history | `beta/shopping.py:store_payload/reopen/reevaluate`: one account, byte-integrity and supported-schema policy for old/new saves; `beta/shopping_views.py` delegates both history routes without its own decoding or reevaluation branch |
| Rendering | `beta/parity.py`, public views, templates and static scripts: separate shared metadata and session-owned projections, escaped display text; [UI design](UI_DESIGN.md) |
| Security and diagnostics | `security.py`, `beta/security.py`, `beta/asgi.py`, `beta/diagnostics.py`: ingress, request-byte limits before buffering, URL policy and redacted failures |
| Optional deployment | `beta/deployment.py`, `beta/staging_config.py`, `beta/support.py`: staging configuration, copied import and operational commands |

## Ownership and goal contracts

A printing is catalog metadata; a physical copy is an account-owned object.
Species declarations record supplied ownership independently of quantities,
condition, edition or exact printing resolution. They never create copies.
Goal progress follows its stored policy: declaration-based species goals and
resolved-copy/printing goals are intentionally distinct. Completion counts
species or distinct printings; duplicate physical copies do not enlarge those
checklists. Purchase amounts retain their original currency.

Goal definitions freeze membership, policy, source references and version hashes.
Publishing metadata does not enroll new items into an old goal. A successor
requires explicit review. Historical version-1 labels include `#250 Ho-oh` because
labels participate in persisted hashes; canonical display uses `Ho-Oh`. This is
compatibility behavior, not a second species registry. Archived metadata remains
recognizable inside retained goal scopes; current selectable coverage is separate.

Original-app ownership lives in `config/pokedex_251.json`; original saved hunts
live in `data/collection_hunts.db`. Authenticated state belongs to the selected
private root. Retained guide/hunt evidence is not an ownership writer or a species
identity authority. Missing or stale guide evidence remains unavailable.

## Public evidence and private research

Canonical species, printings, booster membership, product versions, contents and
seller observations are separate records. The canonical registry contains 1,025
species; card/pack browsing covers #001–251. A source association or retailer
description does not prove official product contents or distribution.

Catalog publication requires the owner role. Reviewed changes retain exact
identities, source URLs/hashes, journals and observation timestamps. Descriptive
correction and identity remapping have distinct semantics. Rollback refuses to
clobber later changes. Public metadata publication never rewrites physical copies
or frozen research. See [catalog workflows](catalogs.md).

Saved pack lookups retain selection, ownership, coverage, goal references and
dated offers. Reopening can report current-reference gaps and recompute age
without rewriting the snapshot or its original timestamps. Comparing current
indexed data opens a separate lookup. Offer freshness uses the original check
and a 24-hour window; future/unknown timestamps are not fresh. Recommendation
eligibility remains distinct from purchase attestation. Purchase-ready is currently
false; no backend purchase attestation contract is implemented.

## Jobs, configuration and compatibility

Photo workers claim durable jobs before provider I/O. Provider requests may consume
reserved authority even if the response is interrupted. Only confirmation adds
inventory; recovery does not reset spending or repeat an uncertain provider call.
The local server starts one scan worker when enabled. Staging runs it separately.
Manual, fixture, API and authenticated CLI recognition are explicit local modes,
with no automatic fallback. `beta/scan_config.py` owns the accepted fields, modes,
ceilings and staging restriction. Persistent staging reads, initialization and
copied import use that validator; CLI recognition is local only. Unknown config
keys fail instead of appearing to select an unused flag. See
[photo entry](photo-entry.md) and [recovery](ERROR_HANDLING.md).

Sealed-offer refresh runs only on disposable synthetic roots through the replay
adapter. Ordinary lookup/reopening does not fetch offers. The eBay flow separately
supports explicit provider requests in local mode. Environment parsing and model
validation are shared across the watcher/original app and authenticated hunts;
process values override file values, and malformed existing settings fail.

Persisted root markers, schema names, goal policies, routes and CLI flags remain
compatible contracts. Saved searches without an intent retain missing-target
semantics. Staging copied import rejects CLI recognition configuration. Retiring
these contracts requires a migration rather than cosmetic renaming. Metadata
availability grants no artwork, guide or trademark redistribution rights.

Shopping history explicitly supports `dex-shopping-v1` (original per-card/group
research) and `dex-lot-v2` (four independent scenarios). Unknown/missing schemas
fail before saving, rendering or reevaluation; they never select the original
format implicitly. Reopening preserves original bytes and captured results.
Current-reference evaluation creates a separate child using that format's
preparation contract. The original editor at `/shopping/legacy/` and its APIs
remain supported for group values, frozen goals and retained history; they are
not alternate implementations of the four-scenario calculator.

Shopping displays admitted retained guides; complete automatic four-grade price
coverage is unavailable. Partial source coverage and source-specific retention
limits remain separate from arithmetic and UI behavior. There is no general
new-provider purge mechanism or automatic price collector.
