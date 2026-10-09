# Original lot watcher

This is the original watcher, with separate storage from the authenticated beta.
For the current product and setup, start at the [repository README](../README.md).

A small daily eBay watcher for inexpensive English Kanto/Johto-era bulk lots. It searches eBay's official Browse API, uses the configured shipping destination and collection gaps, and saves up to five qualifying listings in one digest. It never buys or bids.

## Ready now

- 15 overlapping searches, each run separately for auctions and fixed-price listings.
- Ownership is derived from exact-card records in `config/pokedex_251.json`.
- Exact decimal money, conservative card counts, set aliases, mixed-era warnings, bulk-product filtering, and optional description enrichment.
- SQLite observations, persistent deduplication, auction ending reminders, retryable notifications, and optional macOS daily scheduling.
- Offline demo and automated tests; no credentials required for either.

**Live setup is incomplete until you add eBay application credentials.** The default delivery destination is local report files; optional macOS notifications and an HTTPS webhook are supported.

## Try the offline demo

From this project folder:

```sh
uv sync --locked --extra dev
uv run python scripts/init_local.py
uv run pokemon-hunter run --fixture tests/fixtures/demo.json
open reports/demo/latest.txt
```

The demo is synthetic, uses the fixture's fixed observation time, writes `data/demo.db` and `reports/demo/`, and never calls eBay or notification webhooks. Its expected first result is **3 hits from 5 unique listings**. Repeating the command is silent because those items have already been alerted. To replay from fresh history, use a new demo database filename:

```sh
uv run pokemon-hunter run --fixture tests/fixtures/demo.json --db data/demo-second.db
```

## Enable live use

1. Obtain production application keys from your [eBay Developer account](https://developer.ebay.com/api-docs/static/oauth-credentials.html). Production and sandbox keys are separate. Your application must have access to the Browse API; a local setup check cannot establish API access.
2. Copy `.env.example` to `.env`, restrict its permissions, and fill in `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` locally:

   ```sh
   cp .env.example .env
   chmod 600 .env
   ```

   The file uses simple `KEY=value` entries. It is read as data, never executed. Existing environment values take precedence. Keep secrets out of source control and chat.
3. Check settings and make the first live run:

   ```sh
   uv run pokemon-hunter doctor
   uv run pokemon-hunter run
   uv run pokemon-hunter status
   ```

   Qualifying hits appear in `reports/live/latest.txt` and a dated digest. With no hits, no report or notification is created. `latest.txt` remains the last digest; use `status` to check the latest run, including a zero-hit day. Errors return a nonzero exit code and are recorded as failed runs, never reported as an empty successful search.
4. Install the daily schedule after `doctor` passes:

   ```sh
   .venv/bin/python scripts/schedule.py --install
   ```

   This runs at **08:00 local time** in your macOS login session. Change with `--hour 9 --minute 30`. The Mac must be available; this is a daily snapshot, not auction sniping. Installation refuses missing credentials or ZIP. The generated plist contains paths, not credentials. To remove it:

   ```sh
   .venv/bin/python scripts/schedule.py --remove
   ```

   Logs: `data/daily.log` and `data/daily-error.log`. SQLite lives in `data/pokemon.db`; preserve this file to preserve alert history. Only one run per database can execute at a time. Notifications and search failure retries happen on the next run; no hidden polling loop.

For another Unix host, use cron with the persistent project directory (replace the absolute path):

```cron
0 8 * * * /absolute/path/dex/.venv/bin/python -m pokemon_hunter.main --root /absolute/path/dex run >> /absolute/path/dex/data/daily.log 2>> /absolute/path/dex/data/daily-error.log
```

GitHub Actions validates source, tests, synthetic UI, distributions and security; it does not run the watcher. Daily execution uses local persistent SQLite, avoiding ephemeral CI runners losing deduplication history.

## Notifications

The default is local text digests. To add a macOS banner, set `alerts.macos_notification: true` in `config/settings.yaml`; allow notifications for the executing application if macOS requests it. The banner gives the hit count and report path.

To deliver elsewhere, set `POKEMON_HUNTER_WEBHOOK_URL` in `.env` to an HTTPS endpoint accepting JSON `{"text": "digest"}`. The endpoint receives listing data and your collection totals. Failed delivery leaves the digest pending and does not mark listings alerted. The next run rechecks current prices and eligibility before retrying. A retry uses the same `Idempotency-Key`; exactly-once external delivery requires the endpoint to honor it. A timeout after remote acceptance can otherwise cause a duplicate. Local files are replaced atomically.

## Rules and configuration

The watcher retains a bulk-alert contract with mystery/repack exclusions. For
spoiler-controlled hunts, use the collection app. Watcher digests reveal titles.

| Setting | Default |
| --- | --- |
| Delivery / currency | US / no ZIP configured / USD only |
| Buy It Now delivered per card | ≤ $2.00 |
| Auction current delivered per card | ≤ $1.00 |
| Minimum count | 25 cards |
| Maximum BIN purchase | $120 delivered |
| Maximum auction purchase | $150 delivered |
| Minimum alert priority / digest limit | MEDIUM / 5 hits |
| Auction repeat | Ending within 24h once, or ≥20% delivered-price change; at least 20h since prior alert |

Defaults come from `config/settings.example.yaml` and `models.Settings`; your local
`config/settings.yaml` may override them. Set the delivery ZIP there or through
`EBAY_DELIVERY_POSTAL_CODE` before comparing destination-dependent shipping.
Purchase caps may be `null`. Sales tax is excluded. Auction maximum bid is `min(count × threshold, purchase cap) − shipping`, floored at zero and rounded down to cents. Unknown prices/shipping, unsupported currencies, and unknown auction end times cannot qualify. A dual auction/BIN listing uses auction economics and gets only one canonical item record.

The parser handles `100+`, `90–100`, comma-separated counts, `lot of 72`, and common/uncommon wording. It never sums unrelated quantities or multiplies pack counts. Explicitly separated Pokémon quantities take precedence; stated trainers/energy are conservatively excluded when included in the total. Unknown species composition stays labeled as unknown. Conflicting counts, selectable quantities, accessories, sealed packs, complete sets, mystery/curated products, and tiny lots are withheld.

`config/sets.yaml` contains the 15 eligible English sets and a configurable later-era exclusion dictionary. `pure` means **only eligible set names detected in seller text**, not verified purity. The later-set dictionary is deliberately finite: absence of a match cannot prove absence of modern cards. Vague WOTC/Neo text is `probably_pure`. Mixed lots use the total stated-card denominator, label that uncertainty, and need to be especially cheap and Neo-related to reach MEDIUM. Unknown vintage composition remains lower confidence. Keyword negations and unusual seller phrasing can cause conservative false negatives.

Price thresholds gate alerts independently of ranking. Generation gaps influence the collection heuristic. Rocket/Gym is penalized for Dark/owner-named variants. Played/damaged, no duplicates, and certain composition claims get small ranking bonuses; “unsearched” is neutral. At the price threshold a pure listing can still qualify even with a zero price-efficiency score.

This is a **generation/set heuristic**, not an estimate of how many missing species a lot contains. The watcher does not perform photo recognition or estimate expected new species from unknown lot contents.

## Collection updates

Edit exact-card ownership through the original app. The watcher derives species
ownership from those records; it does not write species-only ownership. Inspect
the current summary with `uv run pokemon-hunter pokedex`. Historical baseline
counts in settings do not override the current collection.

## Search coverage and troubleshooting

Queries are configurable in `config/searches.yaml`. Each purchase-type/query pair fetches up to two pages of 100 results, sorted newly listed. Up to 30 promising or vintage results without a parseable count get `getItem` description enrichment. Page caps and API warnings are recorded in run notes and stderr. A cap means partial marketplace coverage, not an exhaustive scan. Search keywords never count as evidence about a listing's sets.

A failed search or detail request aborts notification processing for that run. HTTP 429/5xx and transport failures get bounded retries; expired tokens get one refresh. Token values stay in memory. The client uses [eBay's client-credentials application token flow](https://developer.ebay.com/develop/guides/sell/authorization) and [Browse buying-option filters](https://www.developer.ebay.com/api-docs/buy/static/ref-buy-browse-filters.html). No HTML listing scraping or photo downloads are used.

Not seeing an expected hit? Inspect `listings.payload` and `listing_observations.payload` in SQLite for normalized evidence and rejection reasons. The same BIN alerts once; a previously rejected, never-alerted item can alert when it crosses the threshold. Auctions are expired by their explicit end time. Absence from a bounded search alone does not prove that a listing expired.

## Verification

```sh
uv run pytest tests/test_runner.py tests/test_ebay.py tests/test_cli.py -q
```

The [CI guide](CI.md) owns full-suite, compilation, syntax, lint and formatting
commands. Select the relevant test files for maintenance.

Tests use constructed seller titles and mocked eBay responses, explicitly **not harvested real-listing fixtures**. They cover counts and ranges, composition, sets, purity, exact landed prices, max bids, hard thresholds, currency/shipping unknowns, OAuth and pagination, retries, SQLite persistence, alert suppression, ending reminders, failed delivery, stale-price rejection, description reclassification, and collection totals. Real-market false-positive quality still needs observation after credentials are configured.
