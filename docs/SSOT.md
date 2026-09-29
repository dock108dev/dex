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
| Overview, Pokédex and saved hunts | `beta/parity.py`; session-owned copies plus private local evidence |
| Shared hunt validation/scoring | `hunt.SearchRequest`, `hunt.project_results`, `hunt.analyze`; used by both web apps |
| Photo lifecycle | `beta/scans.py`, `scan_worker.py`; durable claims around provider I/O; only confirmation adds inventory |
| Provider configuration | `beta/scan_config.py`; shared defaults/validation for local and persistent adapters |
| CLI transport | `beta/codex_recognition.py`; provider-neutral clues returned to the ordinary matcher |
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

See [local setup](local-development.md), [photo entry](photo-entry.md),
[catalogs](catalogs.md), and [historical records](history/README.md).
