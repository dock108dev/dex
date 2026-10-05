# Architecture and data ownership

The authenticated product is a Django application served by uvicorn. Templates and
static JavaScript render private, account-scoped projections. SQLite stores local
accounts, catalogs, copies and jobs; the optional staging profile uses PostgreSQL.
The original FastAPI application and lot watcher remain separate supported entry
points with different storage contracts.

| Responsibility | Authoritative source |
|---|---|
| Local setup and server | `src/pokemon_hunter/beta/cli.py`; `settings.py`, `urls.py` select one handler per route based on capabilities |
| Accounts and authorization | Django auth plus `beta/accounts.py`, `beta/store.py`; client identifiers never confer ownership |
| Schema and legacy import | `inventory.py`, `migration.py`; feature initialization extends the schema without renaming stored identities |
| Copies, binders, goals and mutations | `beta/collection.py`, `beta/transactions.py`; preview, explicit confirmation and conflict-aware undo |
| Filtered goal membership | `beta/goal_filters.py`; game/set/type/rarity/dex filters freeze a versioned checklist; `printing_items` also builds set/custom printing items |
| Exact-copy ownership | `beta/collection.exact_owned_printings`; shared by goal progress and goal-scoped hunt scoring |
| Overview, Pokédex and saved hunts | `beta/parity.py`; session-owned copies plus private local evidence |
| Shared hunt validation/scoring | `hunt.SearchRequest`, `hunt.project_results`, `hunt.analyze`; used by both web apps |
| Authenticated live hunts | `beta/ebay_hunts.py`; explicit local-only Browse calls, eBay-only configuration and sanitized provider errors |
| Goal-scoped hunt ownership | `beta/goal_hunts.py`; frozen goal membership with current account-owned copies |
| Hunt price comparisons | `beta/hunt_values.py`; dated USD guide matching, conditional editions, identified subtotals and labeled catalog-average benchmarks |
| Photo lifecycle | `beta/scans.py`, `scan_worker.py`; durable claims around provider I/O; only confirmation adds inventory |
| Recognition configuration | `beta/scan_config.py`; shared defaults/validation for local and persistent adapters |
| eBay settings and environment parsing | `config.read_env`, `config.load_settings`, `models.Settings`; watcher/original app and authenticated hunts share parsing and destination overrides |
| CLI transport | `beta/codex_recognition.py`; provider-neutral clues returned to the ordinary matcher |
| Public canonical/product/offer catalog | `beta/sealed_catalog.py`, `sealed_cli.py`; additive migration, typed `dex-sealed-v1` packages, owner command review/publication, immutable observations and coverage; `config/sealed/2026-10-04/` retains the real bounded input |
| Catalog review/publication | `beta/catalog_requests.py`, `catalog_imports.py`; owner review and explicit photo consent |
| Guide estimates | `valuation.py`; explicit network refresh in `scripts/refresh_values.py` |
| Browser policy and diagnostics | `security.py`, `beta/security.py`, `beta/diagnostics.py` |
| Optional staging | `beta/deployment.py`, `staging_config.py`, `support.py`; separate processes and operations |
| Original app and watcher | `app.py`, `main.py`; watcher bulk-alert policy in `normalize.py` is distinct from collection hunts |

Each physical copy retains uncertain edition/finish/variant fields. Conditional
guide scenarios do not convert those hypotheses into confirmed valuations.
Duplicate copies affect quantities and scenario totals; completion counts distinct
catalog entries/species. Purchase amounts retain their original currency.

Original-app ownership lives in `config/pokedex_251.json` and its hunts in
`data/collection_hunts.db`. Authenticated ownership lives in the selected root's
inventory database. No automatic synchronization or reconciliation exists. Archived
original evidence can supply prices/species/hunt snapshots but is not an ownership
writer. Missing or stale guide data remains unavailable.

Prepared-root markers, old database tables and CLI flags retain compatibility.
Removing them or retiring the original app requires a migration design. Staging
copy import explicitly rejects CLI recognition configuration. Staging metadata
packages do not grant redistribution rights for artwork or price guides.

See [local setup](local-development.md), [eBay hunts](hunts.md), [photo entry](photo-entry.md),
[catalogs](catalogs.md), and [historical records](history/README.md).

## Compatibility and shared policy

Environment parsing keeps the first file value for a key; explicit process values
override it. Authenticated hunts read only their three eBay keys without exporting
them. Original CLI configuration validates the whole file before exporting values.
Absent authenticated-app settings use model defaults; malformed existing files fail.

Exact ownership excludes unresolved catalog and copy identities. Frozen printing
items retain labels, edition, finish, variant and uncertainty. A missing catalog
game fails explicitly rather than assuming Pokémon.

Saved searches without an intent retain missing-target semantics. Older account-only
roots, original-app stores, manual/fixture/API/CLI recognition and optional staging
remain supported. Retiring markers, tables or saved-request defaults requires a
versioned migration; renaming descriptive labels does not change those contracts.

## Required beta architecture work

[Beta requirements](BETA_REQUIREMENTS.md) define outstanding D1–D5/E1–E6 work.
The source table above describes current implementation. Add separate versioned
records for canonical species, language-specific printings, booster membership,
exact sealed-product contents, guaranteed included cards and seller-specific dated
offers. Preserve source URLs, hashes, observation times, manifests and unresolved
relationships. Product existence, booster membership and stock have independent
sources of truth.

Reviewed catalogs own published identities; retailer observations own observed
stock/price. Goal versions freeze membership/policy; current account copies own
completion. Saved pack research retains goal/source versions and offer timestamps.
Reopening/filtering is local; explicit bounded refresh creates dated observations.

Extend existing migration/publication services and rehearse on copied state.
Do not automatically cut over original ownership or rewrite goals. Public product
metadata and private account research remain separate. The full species registry
must replace the #251 metadata ceiling through compatible engineering.


## E1 boundary delivered October 4

The public E1 canonical registry now spans #0001–1025; legacy importer/goal
eligibility remains #001–251. The new tables do not rewrite collection printings,
copies, private evidence or frozen membership. Relationships are validated through
an owner-authorized transactional service; catalog mutations are serialized and
journaled. Normalized source metadata is public; raw/restricted source responses
are retained in a separate private evidence root. Offers retain seller identity
uncertainty and immutable checked timestamps; freshness comes only from checked
age (maximum 24 hours), never import/report generation. Only the latest qualifying
observation can expose buy-now.

The E1 CLI is the current review surface. Full corrective metadata/mapping review,
existing-printing integration, broad goal versions and the pack-shopping UI remain
follow-on work. SQLite copied-state recovery was exercised; PostgreSQL execution,
hosting and owner acceptance were not. [Closeout](D1_E1.md) owns exact slice evidence
and the next finite D1/E1b handoff.

## D1/E1b — October 4 reviewed 151 publication

[Slice closeout](D1_E1B.md) supersedes the foundation's bridge/correction follow-on
boundary. All 207 English 151 numbered identities are reconciled, with 384 distinct
provider-described variants; 207 standard booster relationships are evidenced and
177 extra-variant membership gaps remain individual. Trainer/Energy records carry
no species mappings. `sealed_bridge.py` publishes 384 compatible collection metadata
records through existing owner review/audit/transaction services; existing IDs,
copies and frozen goals remain intact. Descriptive corrections retain before/after
meaning/provenance, reject stale reviews and refuse conflicting rollback. Identity
remaps and new observations require distinct reviewed records/versions.

The exact Target product retains unknown official pack/guaranteed-card contents.
A dated extracted USD 27.99 out-of-stock observation supplements the old unknown
observation; seller/shipping remain unknown and its approximate original read time
is labeled. No current purchasable offer is established. Missing-18 upstream
printing/standard-booster research progressed; independent chain review and owner
acceptance did not. [Validation](history/2026-10-04-D1-E1B-VALIDATION.md) records
synthetic preservation and exact candidate evidence. Full D1/E1 and beta remain
partial. Next: E2a explicit goal versions over reviewed published printings; no
automatic frozen-goal enrollment or ownership cutover.


## E2a — October 4 explicit Original 151 versions

`beta/broad_goals.py` owns `original-151-reviewed-v1`, reviewed publication
membership, coverage, account-derived resolved-copy progress and frozen-import
validation. `collection.py` owns account authorization, lineage in existing JSON
definitions, reviewed create/successor transactions, stale refusal and idempotency.
No schema migration or original-app ownership synchronization was added.
`goal_hunts.py` captures goal ID/digest/kind/definition and retains archived metadata
within a broad frozen scope; current account ownership remains separate.
`collection.js` exposes creation, progress, missing coverage and explicit successor
review through `/goals/`; `parity.js` labels selected/saved versions. Existing legacy
eligibility and defaults remain intact. Confirmed retained versions cannot be
removed/overwritten/undone; undo of a predecessor-dependent operation is refused.
[E2a closeout](E2A.md) supersedes earlier E2a follow-on notes. Runtime checks now pass; ordinary-browser evidence and owner acceptance remain pending.


## E2a runtime qualification — October 4

E2a runtime qualification now passes: locked synchronization, all three process
cleanup cases and the full suite (458 passed, one existing warning), plus compilation,
JavaScript syntax, lint and formatting. Fresh copied-state preservation and zero-call
frozen-hunt service assertions pass. E2a remains partial: renewed explicit browser
permission was requested and is pending; no server, navigation, UI captures or owner
acceptance occurred. [Qualification record](history/2026-10-04-E2A-QUALIFICATION.md)
retains commands, runtime, exact hashes and preservation evidence. Full E2 and beta
remain open.


## E3a — October 4 retained-data view

The authenticated Packs to open view is implemented from a selected Original 151
goal version or missing species. Frozen review references and stable publication
bridges bound account-derived missing-species coverage. Confirmed booster species
are deduplicated; unknown variants and guaranteed inclusions are separate. Exact
product contents and dated seller/stock/shipping gaps remain visible. No acquisition,
refresh jobs, inventory change or saved pack research was added.

Qualification is partial: focused/framework checks and copied-state preservation
pass, but browser access and loopback bind were denied; locked sync crashes and
three process-cleanup suite cases are blocked by sandbox denial of ps.
[E3a closeout](E3A.md) and [dated validation](history/2026-10-04-E3A-VALIDATION.md)
record actual evidence and the separate finite D3/D4a data handoff. E2a was already
locally browser-qualified per its browser record; full E2/E3 and beta stay open.
