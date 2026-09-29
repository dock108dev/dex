# Original local app — preserved

These commands run the preserved original app, not the authenticated app on port 8011. Run them from the repository root. The initializer only creates missing files; it does not overwrite existing state. Existing installations need only the final launch command.

```sh
uv sync --locked --extra dev
uv run python scripts/init_local.py
uv run pokemon-hunter app --port 8766
```

Visit [Vintage 251](http://127.0.0.1:8766). Everything saves locally. Sample hunts need no credentials. Stop the server with Ctrl-C.

Existing local collections are preserved. Fresh checkouts start empty; examples never contain personal inventory. Local authenticated accounts are implemented in the app on 8011; hosted operation is deferred.

- Browse and filter all 251 species; see every eligible vintage printing.
- Track owned/not owned and first edition in ten sets. Dark and trainer-owned cards never fill a species slot.
- Hunt known lots, mystery/repacks, or missing singles without seeing identities until reveal.
- Filter by focus and delivered budget; revisit saved hunts with spoilers hidden.
- Export the authoritative collection JSON from the sidebar.

**All 251 species now have eligible printings**, with Neo Revelation and Neo Destiny included.

## Original-app data and local files

| File | Purpose |
|---|---|
| `config/pokedex_251.json` | Authoritative exact cards, ownership, first edition, derived species index |
| `config/catalog/` | Ten pinned historical set catalogs and source manifest |
| `config/hunt.json` | Search pools, bounded coverage and scoring weights |
| `config/raw_values.json` | Sourced raw LP/NM prices, when configured |
| `data/collection_hunts.db` | Local search history, including separate sample/live labels |
| `docs/history/2026-09-28-APP_SPEC.md` | Product rules, implemented behavior and remaining integrations |

Preserve the collection JSON and history database when backing up. Updating ownership recomputes species ownership immediately. The old species-only CLI now redirects edits to exact cards, avoiding two competing ownership sources.

## Live eBay

Add your eBay application credentials locally using `.env.example`, then restart the app and choose **Live eBay**. The existing official Browse client is reused. Credentials stay on the server. Never paste secrets into chat. Configuring credentials enables explicit live searches in this original app; it does not enable live hunts in the authenticated app.

Live searches are bounded and report coverage; next-batch search is available for longer query plans. Prices include known shipping and exclude tax. Check the revealed seller page for current availability. The app never buys or bids.

The original lot watcher uses explicit seller text, not photos. Unknown lot contents remain unknown. No automatic raw market-price feed is connected, so value and recommended-bid estimates stay unavailable unless sourced LP/NM records and enough inventory/condition evidence exist. Sample results are synthetic examples, not purchase recommendations.


## Earlier watcher

The original `run`, `doctor`, and `status` commands remain available. They now read species ownership from the new authoritative file, but their historical broader set filter and bulk-lot digest behavior remain separate from the app. **The old digest reveals listing titles.** See [legacy watcher documentation](legacy-watcher.md) for its original behavior; its species-edit instructions are superseded by exact-card editing in the app.

## Original-app collection estimates

The Overview shows ungraded and Grade 7/8/9/10 estimates for one of each owned printing. My cards shows individual estimates. First-edition values follow the checkbox; Base Set 2 and promos do not offer that checkbox. Duplicate quantities are not tracked.

`config/market_values.json` holds dated USD PriceCharting guide snapshots. Grade 10 uses its PSA 10 guide; other grades are general grade scenarios. Grade 7–8 values marked * interpolate geometrically between ungraded and Grade 9 when no direct guide snapshot exists: raw × (grade9/raw)^(1/3 or 2/3). This is a rough heuristic, not observed sales or a predicted card grade. No grading or selling fees included. Records older than 30 days are excluded; partial totals disclose coverage.

The explicit network operation to refresh public guide tables is `uv run python scripts/refresh_values.py`. It stops on HTTP failures, preserves prior records, and records its result in `data/value-refresh.json`. This collection estimate is separate from condition-qualified hunt bid calculations.


These records belong to the original app. The authenticated app tracks physical copies and can retain intentional duplicates; consult [the source-of-truth map](SSOT.md) before changing either store.
