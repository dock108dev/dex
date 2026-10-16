# Original local app

The original FastAPI app uses separate ownership and hunt storage from authenticated
Dex. Use the [main setup](../README.md) for accounts and physical-copy tracking.

## Run locally

Run from the repository root:

```sh
uv sync --locked --extra dev
uv run --no-sync python scripts/init_local.py
uv run --no-sync pokemon-hunter app --port 8766
```

Open [Vintage 251](http://127.0.0.1:8766). Stop with Ctrl-C. The initializer creates
only missing state files from examples, without overwriting an existing collection.
Existing installations need only the final launch command. Samples are synthetic and
require no credentials.

The app browses species #001–251 and eligible vintage printings, tracks exact-card
ownership/first edition, exports collection JSON, and supports spoiler-controlled
known lots, missing singles and mystery/repack research. Duplicate physical quantities
are not tracked. Dark and trainer-owned variants do not fill a species slot.

## Original-app data and local files

| File | Purpose |
| --- | --- |
| `config/pokedex_251.json` | Exact cards, ownership, first edition and derived species index |
| `config/catalog/` | Pinned historical set catalogs and source manifest |
| `config/hunt.json` | Search pools, bounded coverage and scoring weights |
| `config/raw_values.json` | Sourced raw LP/NM prices, when configured |
| `config/market_values.json` | Dated collection guide records, when configured |
| `data/collection_hunts.db` | Private search history with sample/live labels |

Back up the collection JSON and hunt database. Species ownership is derived from exact
cards; the CLI directs edits to the app rather than maintaining a second ownership source.
The [watcher](legacy-watcher.md) reads the same exact-card state for its separate digests.
Authenticated Dex never synchronizes these stores automatically.

Only loopback clients using `127.0.0.1` or `localhost` with matching Origin are accepted;
forwarded headers and test hostnames are rejected. There is no login boundary against
other local processes. Use authenticated Dex for account isolation.

New state and hunt databases are created with mode 0600. Collection writes use a unique
private temporary file and atomic replacement. Failed replacement preserves the original
and may leave a `.tmp` file for inspection. Symlinked collection-write and hunt-database
destinations are refused. Preserve existing permissions in backup and recovery.

## Live eBay

Configure credentials locally using [.env.example](../.env.example), restart and choose
**Live eBay**. Credentials remain server-side. The official Browse client is reused;
searches are bounded, and longer query plans offer an explicit next batch. Prices include
known shipping and exclude tax. Seller-text evidence does not establish exact contents,
authenticity or current availability. The app does not buy, bid, scrape listing HTML or
analyze seller photos.

Unknown contents and unavailable prices stay unknown. Bid/value estimates require sourced
LP/NM records and enough identity, count and condition evidence. Samples are synthetic
examples rather than buying recommendations.

Authenticated Dex uses the shared configuration reader for its separate finite
[Shopping](hunts.md) flow. Its new listing results are temporary; this original app retains
its own private search snapshots. An optional authenticated PostgreSQL/HTTPS profile is
described in [operations](operations.md#optional-postgresqlhttps-profile).

## Original-app collection estimates

Overview and My cards show dated ungraded and Grade 7/8/9/10 guide scenarios for one of
each owned printing. First-edition guide selection follows the checkbox; Base Set 2 and
promos have no first-edition checkbox. Grade 10 uses the PSA 10 guide; other grades are
general scenarios. Retained Grade 7–8 geometric estimates are explicitly labeled and
are not regenerated. No scenario establishes a card's grade or observed sale value.
Grading and selling fees are excluded; duplicate quantities are not included.

Records older than 30 days are excluded, and incomplete totals disclose coverage.
`reference_policy.py` shares finite capped USD, safe HTTPS provenance, variant-verification
and date rules with authenticated research. Edition/grade eligibility remains specific
to each projection. Unsafe, stale or incomplete records stay unpriced. New managed
Shopping snapshots use the [private importer](local-development.md#private-price-snapshots).
