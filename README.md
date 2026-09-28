# Vintage 251

A local vintage Pokémon collection app with a spoiler-controlled hunt experience.

## Current local pre-alpha

The [roadmap](docs/ROADMAP.md) targets Mike alone on his Mac. The authenticated app at [Overview](http://127.0.0.1:8011/overview/) includes collection/Pokédex parity, copies, binders, goals, imports/exports/undo, photo entry and catalog requests. Preserve the existing login and data; do not initialize it again. [Local launch instructions](docs/B2_PARITY.md#launch-the-revised-review-app) apply if it is stopped.

[Scan/Add](http://127.0.0.1:8011/scan/) currently has documented simulated/manual recognition; real API setup and a small evaluation are next. See [photo configuration](docs/B3_PHOTO_ENTRY.md). Hosting, LAN HTTPS and phone/operational qualification are deferred. [PM status](docs/PM_STATUS.md) records current priorities.

## Original local app — preserved

The commands below run the original app, not the authenticated app on 8011. Preserve existing environments; no reinitialization is required for the current task.

```sh
uv sync --frozen --extra dev
uv run python scripts/init_local.py
uv run pokemon-hunter app --port 8766
```

Visit [Vintage 251](http://127.0.0.1:8766). Everything saves locally. Sample hunts need no credentials. Stop the server with Ctrl-C.

Existing local collections are preserved. Fresh checkouts start empty; examples never contain personal inventory. B0 preservation and copied-data migration passed; see [implementation results](docs/B0_IMPLEMENTATION.md). Local authenticated accounts are implemented in the app on 8011; hosted operation is deferred.

- Browse and filter all 251 species; see every eligible vintage printing.
- Track owned/not owned and first edition in ten sets. Dark and trainer-owned cards never fill a species slot.
- Hunt known lots, mystery/repacks, or missing singles without seeing identities until reveal.
- Filter by focus and delivered budget; revisit saved hunts with spoilers hidden.
- Export the authoritative collection JSON from the sidebar.

**All 251 species now have eligible printings**, with Neo Revelation and Neo Destiny included.

## Data and local files

| File | Purpose |
|---|---|
| `config/pokedex_251.json` | Authoritative exact cards, ownership, first edition, derived species index |
| `sources/confirmed-ownership.json` | Complete ownership input confirmed September 27 |
| `config/catalog/` | Ten pinned historical set catalogs and source manifest |
| `config/hunt.json` | Search pools, bounded coverage and scoring weights |
| `config/raw_values.json` | Sourced raw LP/NM prices; currently empty |
| `data/collection_hunts.db` | Local search history, including separate sample/live labels |
| `APP_SPEC.md` | Product rules, implemented behavior and remaining integrations |

Preserve the collection JSON and history database when backing up. Updating ownership recomputes species ownership immediately. The old species-only CLI now redirects edits to exact cards, avoiding two competing ownership sources.

## Live eBay

Add your eBay application credentials locally using `.env.example`, then restart the app and choose **Live eBay**. The existing official Browse client is reused. Credentials stay on the server. Never paste secrets into chat. No credentials were configured and no live calls were made during this implementation.

Live searches are bounded and report coverage; next-batch search is available for longer query plans. Prices include known shipping and exclude tax. Check the revealed seller page for current availability. The app never buys or bids.

Current recognition uses explicit seller text, not photos. Unknown lot contents remain unknown. No raw market-price feed is connected, so value and recommended-bid estimates stay unavailable unless sourced LP/NM records and enough inventory/condition evidence exist. Sample results are synthetic examples, not purchase recommendations.

## Verification

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Tests cover exact ownership, eligibility, duplicate printings, persistence, query derivation, spoiler projections/reveal, budget filtering, raw-value rules and the original watcher regressions. API tests use temporary copies and do not change your collection.

## Earlier watcher

The original `run`, `doctor`, and `status` commands remain available. They now read species ownership from the new authoritative file, but their historical broader set filter and bulk-lot digest behavior remain separate from the app. **The old digest reveals listing titles.** See [legacy watcher documentation](docs/legacy-watcher.md) for its original behavior; its species-edit instructions are superseded by exact-card editing in the app.

## Collection estimates

The Overview shows ungraded and Grade 7/8/9/10 estimates for one of each owned printing. My cards shows individual estimates. First-edition values follow the checkbox; Base Set 2 and promos do not offer that checkbox. Duplicate quantities are not tracked.

`config/market_values.json` holds dated USD PriceCharting guide snapshots. Grade 10 uses its PSA 10 guide; other grades are general grade scenarios. Grade 7–8 values marked * interpolate geometrically between ungraded and Grade 9 when no direct guide snapshot exists: raw × (grade9/raw)^(1/3 or 2/3). This is a rough heuristic, not observed sales or a predicted card grade. No grading or selling fees included. Records older than 30 days are excluded; partial totals disclose coverage.

Refresh public guide tables with `uv run python scripts/refresh_values.py`. It stops on HTTP failures, preserves prior records, and records its result in `data/value-refresh.json`. This collection estimate is separate from condition-qualified hunt bid calculations.

## Isolated B1 accounts

Django authentication, invite setup, local recovery and private inventory now run separately on loopback. Actual owner provisioning is pending; the original app remains authoritative. See [B1 local launch and verification](docs/B1_IMPLEMENTATION.md). Do not expose the legacy unauthenticated app.


## B2 isolated collection app

B2 extends the authenticated application with physical copies, private binders, versioned goals, previewed set additions and CSV/JSON imports, complete JSON export and conflict-aware undo. The original local app remains unchanged. **B1 actual owner provisioning remains pending; B2 engineering checks do not establish owner acceptance or hosted readiness.**

Follow [B2 launch, implemented flows and verification](docs/B2_IMPLEMENTATION.md) to use the prepared private `review-local` root. A new B2 root uses `init --b2 --copied-inventory` with a copied B0 rehearsal database; existing roots are refused. Never initialize or upgrade the prepared B1 `owner-local` root for B2. The authoritative next-steps record is [ROADMAP](docs/ROADMAP.md).

### B2 restored-experience review

The authenticated parity revision restores Overview, Pokédex, My Cards, copy edition controls, local guide scenarios, sample hunts and spoiler-safe saved finds alongside existing B2 flows. Follow the [parity matrix and fresh review launch](docs/B2_PARITY.md). Stop for Mike's focused review before B3. B1 actual-owner provisioning remains a separate pending gate.

### B3 photo entry

The authenticated isolated review app now includes Scan/Add: private photos, durable recognition jobs, catalog/manual review, provisional copies, safe confirmation and undo. See [B3 behavior, setup and evidence limits](docs/B3_PHOTO_ENTRY.md). The default needs no API key; live recognition requires secure configuration. Simulated review results are explicitly labeled.

### B4 catalog expansion

Catalog requests connect unsupported scans/provisional copies to owner-role review, explicit photo consent, versioned publication/rollback and resolution of the existing copy. English Gym Heroes adds 132 metadata entries through the ordinary importer. [Behavior, source rights, setup and limits](docs/B4_CATALOG_EXPANSION.md).

## B5 staging operations

The authenticated Django app now has a PostgreSQL 17 staging package, independent web/worker operation, consistent database/photo backup and restore, account erasure, retention and private feedback. See [B5 operational runbook](docs/B5_OPERATIONS.md) for exact configuration, commands, source gates, cost estimate and acceptance matrix. Local staging checks do not establish hosted or real-device acceptance; no deployment or collection cutover has occurred. The original local app remains preserved.
