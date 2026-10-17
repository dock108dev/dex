# Local development

Dex uses Python 3.12 or later, [uv](https://docs.astral.sh/uv/) and Node.js 24
(selected by `.nvmrc`). The frontend uses Django templates and plain JavaScript/CSS;
there is no bundler or Node build.

From the repository root:

```sh
uv sync --locked --extra dev
```

A checkout environment and an installed application's runtime are independent.
Updating one does not update the other.

## Existing installations

The owner installation recorded at SHOP-04 delivery on October 16, 2026 is
`/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local`, served at
`http://127.0.0.1:8011/`. Its saved helper is
`/Users/michaelfuscoletti/.local/share/dex/operations/simple-local/start-dex.py`,
selecting `/Users/michaelfuscoletti/.local/share/dex/runtimes/shop-04-delivered-20261016/bin/python`.
Desktop `Dex.command` was absent at delivery. The recorded installed wheel SHA-256 is
`536a225e7f9c544b94c94c6f516a6c3bbbfa06814412882576d41fee9c683096`.
This is a delivery record, not a current listener/process verification. Recheck before
using or updating the app. Local evidence is in
`reports/shop-04-20261016/closeout.md` and `reports/shop-04-20261016/identity.json`.
Later source commits and the offline ON-02 candidate do not become installed by
updating the checkout. Keep the existing private provider configuration and
compatible recovery runtimes; preserve latest state rather than restoring older data.

Reuse the existing private data root and its installed interpreter. Check the running
process and listener before starting another server. Set these variables to the actual
existing locations; the example locations below are placeholders:

```sh
export DEX_APP_ROOT="$HOME/.local/share/dex/collection"
export DEX_APP_PYTHON="$HOME/.local/share/dex/runtime/bin/python"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

Open [Dex](http://127.0.0.1:8011/) and sign in normally. The server binds to fixed
loopback port 8011 and does not reload source changes automatically. Stop a server
you started with Ctrl-C. Photo-enabled roots also start a scan worker.

Never rerun `init` or `bootstrap` to restart an existing collection. Do not replace
its data with a synthetic root. Back up private state before data-changing updates;
[operations](operations.md) covers exclusions, independent journals and recovery.
Starting the app does not refresh prices or acquire provider data.

## Engineering fixtures

A fresh checkout contains public inputs and code, without personal holdings or login.
Create a synthetic development instance in a nonexistent directory:

```sh
export DEX_DEMO_ROOT="$HOME/.local/share/dex/synthetic"
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output "$DEX_DEMO_ROOT"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_DEMO_ROOT" serve
```

The initializer refuses an existing directory. Port 8011 must be free. Passwords for
`admin` and `synthetic-member` are in the new root's private `credentials.json`.
Recognition is simulated and price coverage may be absent. Later launches use only
`serve`. Use synthetic state for engineering checks, and an existing installation
with its real state when someone asks to use their collection.

The lower-level `init --b2 --parity --copied-inventory PATH` initializes a new root
from an explicitly supplied inventory copy. `bootstrap` provisions its owner through
a private interactive terminal. Neither command is required for ordinary startup.
Inspect the available commands before provisioning accounts or enabling capabilities:

```sh
uv run --no-sync python -m pokemon_hunter.beta.cli --help
```

`scripts/init_local.py` initializes the separate [original app](ORIGINAL_APP.md).

## Configuration

| Setting | Purpose |
| --- | --- |
| `DEX_PROFILE` | `local` by default; `staging` selects PostgreSQL/HTTPS settings |
| `DEX_B1_ROOT` | Private root selected by the local CLI |
| `scan-config.json` | Recognition mode and spending ceilings; see [photo entry](photo-entry.md) |
| `OPENAI_API_KEY` | Server/worker environment for explicitly selected API recognition |
| `PATH`, `HOME`, optional `CODEX_HOME` | CLI executable and its own authentication |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | eBay credentials; nonempty server values override the local `.env` |
| `EBAY_DELIVERY_POSTAL_CODE` | Optional destination override |
| `config/settings.yaml` | eBay environment, marketplace, destination and watcher bounds |

Use [.env.example](../.env.example) and
[settings.example.yaml](../config/settings.example.yaml). The authenticated app reads
only allowlisted eBay values from `.env`; recognition credentials belong in the server
environment. Its eBay reader uses model defaults only when the settings file is absent.
Malformed existing settings fail. The original watcher also supports an optional
outbound webhook. Persisted root marker names are capability contracts.

The authenticated eBay configuration root comes from Django `PROJECT`, independently
of the private data root and working directory. A source launch reads the checkout;
an installed wheel resolves a directory above its package. Do not assume checkout
settings configure an installed server. Readiness checks configuration without a
provider request; configured status does not prove remote access or remaining quota.
Restart normally after changing environment values. See [Shopping](hunts.md).

## Testing

HUNT-01–05 and LOT-01 backend are backend-only; do not install the full checkout to demonstrate them.
The normal authority/CSRF API, finite two-lane service and local identity/reference
adapters can be exercised in engineering tests with `tests/test_hunter*.py`,
`test_discovery_matching.py` and the existing Discovery/reference regressions.
The Hunter backend implementation slices authorize zero provider operations; the exhausted HUNT-01 ledger is
unchanged. Their exact isolated candidate and closeout are retained under
`reports/hunt-02-03-20261016/`. Customer-facing sessions continue
using the actual installation above. The metadata-only `scripts/qualify_hunter.py`
audit may read that root without cleanup or provider acquisition. Genuine backend
qualification uses the saved Production configuration and the independently
consumed allowance described in [Shopping](hunts.md#hunt-01-backend-contract).

The bounded traversal/ranking/lot backend candidate is recorded under
`reports/hunt-04-05-lot-01-20261016/`. Its shared traversal allowance remains
disabled; tests use disposable roots and fake transports with external sockets
blocked. The real SHOP-04 installation, root and startup command above remain
unchanged. See [service/API contracts](hunts.md#hunt-0405-and-lot-01-backend-contracts)
for explicit continuation, local result cursors and temporary lot correction rules.

Use focused checks for the affected behavior:

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q tests/test_b2.py tests/test_filtered_goals.py
```

Socket guards and browser tooling are in the `ci` extra. When the full suite is needed:

```sh
uv sync --locked --extra dev --extra ci
uv run --no-sync pytest -q --disable-socket --allow-unix-socket
```

[CI](CI.md) documents JavaScript contracts, Chromium setup, distribution checks and
workflows. Browser helpers must use disposable synthetic state; the integrated
`scripts/ci/browser.py` creates its own root and blocks acquisition. Historical hunt
rendering is covered by `tests/test_parity_history_ui.py`.

## Maintenance conventions

The [architecture map](SSOT.md) identifies service owners and persisted contracts.
[Interface guidance](UI_DESIGN.md) covers presentation;
[effective collection](effective-collection.md) owns collection and bulk-review meaning.
Keep account verification at service boundaries and public output allowlisted.

Django templates and assets live under `src/pokemon_hunter/beta/`; `web/` serves the
original app. `collection.css` imports `collection-base.css` before
`collection-browse.css`. Preserve that cascade order. The collection controller owns
editing, dialogs and recovery while card/species renderers own browsing.

`bulk_formats.py` owns pure input formats and fingerprints; `bulk_input.py` resolves
account/catalog identities. `photo_batch_images.py` handles image bytes while
`photo_batches.py` owns admission, leases, journals and transaction sequencing.
`listing_details.py` projects seller responses; `listing_check.py` coordinates temporary
review and workers. Keep related authorization, Stop and transaction boundaries intact
when extracting responsibilities.

Ruff uses a 110-character line setting and E4/E7/E9/F/I rules. Split by responsibility,
not arbitrary chunks or compressed line counts. Shared test fixtures belong outside
collected test modules. Packaging selects public inputs explicitly in `pyproject.toml`;
`runtime_data.py` resolves source and installed layouts. Keep credentials, collection
state, private prices, captures and build output out of Git. Generated checks write to
ignored `reports/`; source checks must not require those local files.

## Manual bulk and photo batches

Manual bulk entry uses `/add-many/`. Its explicit `enable-bulk` command initializes
`collection_drafts` and `collection_replays`; startup and page reads never migrate.
Run enablement only for a root selected for that capability, after backup and a schema
check. The ordinary copy/goal export is not a complete backup of drafts or current
collection intent. `bulk-cleanup` performs explicit expiry/revocation maintenance.

Photo batches at `/add-photos/` require local scan support, the bulk schema and explicit
`enable-photo-batches`. They are unsupported in staging. Source availability does not
enable them in an existing installation. Manual matching remains available without
recognition; real-photo accuracy is unmeasured. See [photo entry](photo-entry.md) and
[photo-batch recovery](operations.md#photo-batch-recovery).

## Private price snapshots

[Price snapshots](price-snapshots.md) documents schemas, source admission and operator
commands. [Backup policy](operations.md#snapshot-retention-and-backups) covers managed
price exclusions and independent revocations. Import and browsing do not acquire
provider data; coverage depends on admitted packages and source contracts.

## Bounded group-metadata collector

`python -m pokemon_hunter.metadata_collector` requests only the configured TCGCSV
Pokémon group metadata. It cannot fetch products or prices or activate a source.
It requires an exact reviewed manifest digest and current acquisition authorization.
Inspect its help before use.

The supervisor bounds worker lifetime and supports an independent Stop request.
Its private canonical result and publisher journal remain outside Git and the app
root. Preserve consumed attempts independently of restores; never reset the journal
to bypass its 24-hour interval. There is no automatic retry or schedule. Raw response
bodies and provider error text are not retained in summaries. On interruption, retain
consumed state, allow the bounded child to exit, then clean managed pending copies.

## Hunter UI engineering qualification

HUNT-06 adds `/shopping/hunter/` and the temporary lot review to the source
candidate. It is not installed in the customer SHOP-04 runtime. Production
`TRAVERSAL_ALLOWANCE` remains `None`; HUNT-01 remains exhausted. Do not install the
checkout or use fabricated state for a customer demonstration.

Run `python scripts/qualify_hunter_ui.py --output reports/hunter-ui-local` in the
checkout engineering environment. This real Chromium harness creates fresh
disposable roots, uses in-process fake provider transport and controlled image/
lifecycle responses, and refuses the ordinary customer port. It records layout,
measured doubled text, API/action boundaries and zero external operations. These
fixtures are engineering evidence, not provider listings or customer acceptance.
The same harness can be invoked with a fresh isolated wheel interpreter; its
report records application origins and exact shipped asset hashes. Focused
renderer contracts use `node scripts/verify_hunter_review.js`.
