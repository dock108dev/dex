# Architecture and data ownership

## Entry points and storage

The authenticated collection app is Django, served by uvicorn on
`127.0.0.1:8011`. Templates and plain JavaScript consume private, account-scoped
projections. A private root holds SQLite inventory, authentication data, the
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
| Local initialization and serving | `beta/cli.py`, `beta/settings.py`, `beta/urls.py`: root capability markers select compatible handlers; no automatic reseeding |
| Authentication and account access | Django auth, `beta/accounts.py`, `beta/store.py`: active mapped account and account-scoped queries; client IDs are selectors, not authority |
| Schema and import | `inventory.py`, `migration.py`: compatible additive schema initialization and explicit legacy import |
| Physical copies and mutations | `beta/collection.py`, `beta/transactions.py`: preview, confirmation, idempotency and conflict-aware undo |
| Canonical species identity | `beta/canonical_species.py`: hash-pinned public registry; mutable catalog names and private evidence are not identity authorities |
| Frozen collecting goals | `beta/goal_filters.py`, `beta/broad_goals.py`, `beta/collection_goals.py`: shared species builder, versioned membership and declaration references |
| Declaration-based ownership | `beta/ownership_declarations.py`: account-local source revisions separate from physical copies |
| Public catalog publication | `beta/catalog_imports.py`, `beta/sealed_catalog.py`, `beta/sealed_bridge.py`: reviewed packages, atomic publication, journaled correction/rollback |
| Catalog coverage and batch checkpoints | `beta/catalog_pipeline.py`: reviewed universe/alias inputs and existing publication services |
| Pack lookup and saved research | `beta/lookup.py`, `beta/packs.py`, `beta/product_lookup.py`, `beta/pack_research.py`: possible/guaranteed coverage and frozen account-local snapshots |
| Offer age and eligibility | `beta/offer_filters.py`: original observation age and conservative evidence decisions |
| eBay request validation/scoring | `hunt.py`, `beta/ebay_hunts.py`, `beta/goal_hunts.py`, `beta/hunt_values.py`: explicit search, frozen scope, current ownership and dated guide comparison |
| Photo jobs | `beta/scans.py`, `beta/scan_worker.py`, `beta/scan_config.py`, `beta/codex_recognition.py`: durable claims/reservations, configured provider and explicit inventory confirmation |
| Replay refresh | `beta/refresh.py`: bounded synthetic-only replay; no live acquisition adapter |
| Rendering | `beta/parity.py`, templates and static scripts: session-owned projections, escaped display text |
| Security and diagnostics | `security.py`, `beta/security.py`, `beta/diagnostics.py`: ingress, URL policy and redacted failures |
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
species; beta card/pack browsing covers #001–251. A source association or retailer
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
Manual, fixture, API and authenticated CLI recognition are explicit modes, with no
automatic fallback. See [photo entry](photo-entry.md) and [recovery](ERROR_HANDLING.md).

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

Dated candidate verification and engineering plans are retained in
[history](history/README.md) and the clearly named status/roadmap records. Their
results qualify their exact candidates, not this evolving checkout.
