# Original lot watcher

The watcher searches eBay's official Browse API for inexpensive English Kanto/Johto-era
bulk lots. It uses the configured destination and collection gaps, then writes a bounded
digest of qualifying listings. Digests reveal listing titles. It never buys or bids.
For the authenticated collection app, use the [main setup](../README.md).

## Offline demo

From the repository root:

```sh
uv sync --locked --extra dev
uv run --no-sync python scripts/init_local.py
uv run --no-sync pokemon-hunter run --fixture tests/fixtures/demo.json
```

Read `reports/demo/latest.txt`. The synthetic fixture uses a fixed observation time,
`data/demo.db` and `reports/demo/`; it does not call eBay or notification webhooks.
Repeating an already-alerted fixture is silent. To keep a separate demo history:

```sh
uv run --no-sync pokemon-hunter run --fixture tests/fixtures/demo.json --db data/demo-second.db
```

Fixture database names must contain `demo`. The initializer creates missing files
without overwriting existing state.

## Live configuration

1. Configure production keys from your [eBay Developer account](https://developer.ebay.com/api-docs/static/oauth-credentials.html).
   Production and sandbox credentials are distinct; Browse API access is required.
2. Create a private `.env` from [.env.example](../.env.example) if one is not already
   configured. Fill `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` locally. Restrict the file
   to mode 0600. Simple `KEY=value` entries are read as data; process environment values
   take precedence. Never put credentials in arguments, chat or source control.
3. Configure delivery ZIP and search bounds in `config/settings.yaml` or the supported
   environment values, then inspect local readiness:

   ```sh
   uv run --no-sync pokemon-hunter doctor
   ```

   This checks local setup without a provider request. It does not prove remote access
   or remaining quota. An explicit live run acquires provider data:

   ```sh
   uv run --no-sync pokemon-hunter run
   uv run --no-sync pokemon-hunter status
   ```

Qualifying hits create `reports/live/latest.txt` and a dated digest. No-hit runs create
no report or notification; `latest.txt` remains the last digest. Use `status` for the
latest run, including zero-hit days. Failures return nonzero status and remain failed
rather than appearing as successful empty searches.

## Scheduling

The macOS scheduler installs a LaunchAgent after checking `doctor`:

```sh
.venv/bin/python scripts/schedule.py --install --hour 8 --minute 0
```

It runs at 08:00 local time in the login session; the Mac must be available. The plist
contains paths, not credentials. Inspect `data/daily.log` and `data/daily-error.log`.
Remove the schedule with:

```sh
.venv/bin/python scripts/schedule.py --remove
```

Removal does not confirm an in-flight watcher stopped. On another Unix host, configure
a persistent scheduler to invoke the checkout's interpreter with
`-m pokemon_hunter.main --root ROOT run`; use the existing absolute checkout location
for `ROOT`. CI does not run live searches. Preserve `data/pokemon.db` for deduplication
and alert history. Only one run per database executes at once; failed delivery is
reconsidered on the next run, without a hidden polling loop.

## Notifications

The default destination is local text files. Enable `alerts.macos_notification` in
`config/settings.yaml` for a hit-count/report-path banner. The executing application
may need macOS notification permission.

`POKEMON_HUNTER_WEBHOOK_URL` selects an HTTPS endpoint accepting JSON `{"text":"digest"}`.
It receives listing data and collection totals. Failure preserves pending delivery.
The next run rechecks current prices/eligibility and uses the same `Idempotency-Key`.
Exactly-once delivery requires the endpoint to honor that key; a lost response after
acceptance can otherwise cause duplicates. Local digest files use atomic replacement.

## Rules and configuration

The initializer copies these values from `config/settings.example.yaml`:

| Setting | Example configuration |
| --- | --- |
| Delivery / currency | US / ZIP required / USD |
| Fixed-price delivered cost per card | At most $2.00 |
| Auction current delivered cost per card | At most $1.00 |
| Minimum stated cards | 25 |
| Maximum fixed-price / auction purchase | $120 / $150 delivered |
| Minimum priority / digest limit | Medium / 5 |
| Auction repeat | Ending within 24 hours once, or at least 20% delivered-price change; at least 20 hours since the prior alert |

Local settings are authoritative. When omitted, the model defaults for per-card limits
are $1.00/$0.50 and purchase caps are $60/$75. Purchase caps may be null. Sales tax is
excluded. Auction maximum bid is `min(count × threshold, purchase cap) − shipping`,
floored at zero and rounded down to cents. Unknown prices/shipping, unsupported
currencies and unknown auction end times cannot qualify. Dual auction/fixed-price
listings use auction economics and one canonical item record.

The count parser recognizes explicit counts, ranges, `100+`, `lot of 72` and common/
uncommon wording. It does not sum unrelated quantities or multiply pack counts.
Explicit Pokémon quantities take precedence; stated trainers/energy are conservatively
excluded where possible. Unknown species composition remains labeled. Conflicting
counts, selectable quantities, accessories, sealed packs, complete sets, mystery/curated
products and tiny lots are withheld.

`config/sets.yaml` defines eligible sets and later-era exclusions. `pure` means only
eligible set names were detected in seller text, not verified physical purity. The
later-era dictionary is finite; an absent match cannot establish vintage-only contents.
Vague WOTC/Neo claims remain probable rather than verified. Mixed lots use the total
stated-card denominator and receive lower confidence.

Price thresholds gate alerts independently of ranking. Collection gaps influence a
species/set heuristic, not expected missing-species yield. No photo recognition is
performed. Edit exact-card ownership through the [original app](ORIGINAL_APP.md);
`pokemon-hunter pokedex` reads the derived summary. Settings baseline counts do not
override the current collection.

## Coverage and troubleshooting

`config/searches.yaml` controls query strings. The example configuration requests two
pages of 100 newly listed results per query/purchase type and enriches at most 30
promising or vintage results with descriptions. Limits and API warnings remain in run
notes/stderr. Search keywords are not evidence about a listing's sets, and absence from
a bounded search does not establish expiry.

A failed search/detail request aborts notification processing. Transport, HTTP 429 and
server failures have bounded retries; expired tokens permit one refresh. Tokens stay in
memory. The client uses [application OAuth](https://developer.ebay.com/develop/guides/sell/authorization)
and [Browse buying-option filters](https://www.developer.ebay.com/api-docs/buy/static/ref-buy-browse-filters.html),
without HTML scraping or photo downloads.

For rejected candidates, inspect normalized reasons in `listings.payload` and
`listing_observations.payload`. Fixed-price items alert once; a never-alerted rejected
item may qualify later. Auctions expire by explicit end time. Preserve failed runs and
pending digests while investigating; see [failure handling](ERROR_HANDLING.md).

## Testing

```sh
uv run --no-sync pytest -q tests/test_runner.py tests/test_ebay.py tests/test_cli.py
```

These tests use synthetic seller titles and mocked responses. They do not establish
real-market accuracy or current provider access. [CI](CI.md) documents the broader
validation commands.
