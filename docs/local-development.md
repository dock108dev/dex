# Local development

The authenticated Django app, original FastAPI app and lot watcher have separate
entry points and storage. Start with the authenticated app for physical copies,
accounts and collecting goals. See [architecture](SSOT.md) for service ownership.

## Requirements

Use Python 3.12 or later, uv and macOS or Linux. Install Node.js 24 from `.nvmrc`
for JavaScript checks. Windows process handling is unsupported. Commands below
run from the repository root unless they use an installed interpreter explicitly.

```sh
uv sync --locked --extra dev
```

## Existing installations

An existing installation has a private data root and a compatible installed Python
runtime. Use those paths, rather than a checkout environment, for ordinary use:

```sh
export DEX_APP_ROOT="/absolute/path/to/existing-dex-root"
export DEX_APP_PYTHON="/absolute/path/to/installed-runtime/bin/python"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

Open [Dex](http://127.0.0.1:8011/). Reuse an existing server on that port rather
than starting a second one. Stop a foreground server with Ctrl-C. The server binds
only to loopback and rejects foreign Host/Origin and forwarded headers.

Do not run initialization, bootstrap or capability-enablement commands merely to
start an existing app. Keep its database, authentication secret, configuration,
photos and independent accounting. Updating the checkout does not update an
installed wheel. Back up before data-changing updates; see [operations](operations.md).

Root markers such as `B1_ISOLATED` and `B2_ISOLATED` are persisted capability
contracts. Their historical names do not identify a user's collection as a fixture.
Startup checks private permissions and existing capabilities; browsing does not
migrate, seed or reset an installation.

## Engineering fixtures

A fresh checkout contains code and public inputs, without a personal collection or
login. For an explicitly synthetic development instance, choose a new directory
outside the checkout. The initializer refuses an existing directory.

```sh
export DEX_DEMO_ROOT="$HOME/.local/share/dex/synthetic"
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output "$DEX_DEMO_ROOT"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_DEMO_ROOT" serve
```

Port 8011 must be free. Generated passwords are in the new root's private
`credentials.json`. Recognition is simulated; reference coverage may be absent.
Later launches use only `serve`. Never substitute fixture state for an existing
user's collection.

The lower-level CLI can initialize a new root from an explicit inventory copy and
provision an owner through a private terminal. Inspect its arguments before use:

```sh
uv run --no-sync python -m pokemon_hunter.beta.cli --help
```

`scripts/init_local.py` initializes the separate [original app](ORIGINAL_APP.md),
not the authenticated collection app.

## Configuration

| Setting | Purpose |
| --- | --- |
| `DEX_PROFILE` | `local` by default; `staging` selects PostgreSQL/HTTPS settings |
| `DEX_B1_ROOT` | Private root set by the local CLI |
| `scan-config.json` | Recognition mode and spending limits; see [photo entry](photo-entry.md) |
| `hunter-policy.json` | Owner-selected ordinary Hunter policy marker; use Hunter's Usage settings |
| `OPENAI_API_KEY` | Server/worker environment for explicitly configured API recognition |
| `PATH`, `HOME`, optional `CODEX_HOME` | CLI recognition executable and its authentication |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | eBay credentials; nonempty process values override `.env` |
| `EBAY_DELIVERY_POSTAL_CODE` | Optional delivery destination override |
| `config/settings.yaml` | eBay environment, marketplace, destination and watcher bounds |

Use [.env.example](../.env.example) and
[settings.example.yaml](../config/settings.example.yaml). Keep local secrets private
and untracked. The authenticated app reads only allowlisted eBay keys from `.env`;
recognition credentials belong in the process environment. Missing optional eBay
settings use model defaults; malformed existing settings fail.

The eBay configuration directory is Django's `PROJECT`, independently of the data
root and working directory. For source launches it is the checkout; an installed
wheel derives it above the package directory. See `beta/settings.py` and
`beta/ebay_hunts.py`. Do not assume checkout settings configure an installed server.
Restart after process environment changes. Readiness is a local configuration check,
not proof of provider access or remaining quota.

## Testing

Choose focused tests for the changed behavior:

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q tests/test_b2.py tests/test_filtered_goals.py
```

Socket guards, coverage, security and browser tools are in the `ci` extra:

```sh
uv sync --locked --extra dev --extra ci
uv run --no-sync python scripts/ci/source.py
uv run --no-sync pytest -q --disable-socket --allow-unix-socket
```

Tests use disposable state and controlled providers. [CI](CI.md) lists renderer,
browser, distribution and PostgreSQL checks; they need not all run for a docs edit.

## Maintenance conventions

Ruff uses a 110-character line setting and E4/E7/E9/F/I checks. Split by responsibility,
not equal-sized chunks. Python files above 500 physical lines warrant review;
above 1,000 require extraction or a concrete cohesion constraint. JavaScript/styles
use 300/600 and templates 250/500. Tests follow their language role. Count readable
blanks/comments; exclude generated data, locks and fixed consumer artifacts.

Templates and assets live under `src/pokemon_hunter/beta/`; `web/` serves the
original app. Preserve the `collection-base.css` then `collection-browse.css`
cascade. Client renderers do not own account, possession or price policy.

`bulk_formats.py` parses input; `bulk_input.py` resolves account/catalog identity.
`photo_batch_images.py` handles image bytes; `photo_batches.py` owns leases and
transaction sequencing. Keep Stop, authorization and journals explicit when extracting.

Snapshot tooling separates execution from `tcgcsv_capture_contract.py`,
`tcgcsv_capture_history.py` and `tcgcsv_capture_transport.py`. Execution retains the
installation lock through reservation, dispatch and terminal accounting. Pilot,
batch and cadence tests share non-collected `tcgcsv_capture_helpers.py` fixtures.
The Hunter browser runner separates process ownership from `hunter_ui_journey.py`;
the ordered journey retains one browser context, held responses and final cleanup.

Packaging selects runtime inputs in `pyproject.toml`; `runtime_data.py` resolves
source and installed layouts. Keep credentials, personal state and removable prices
out of Git. Generated checks belong in ignored `reports/`; maintained instructions
must work without local notes or generated evidence.

## Private price snapshots

See [snapshot contracts and lifecycle](price-snapshots.md) for independent source
admission, preview/validate/activate, expiry and withdrawal. The importer performs
no network acquisition. Some current-price reads prune managed files; they are not
read-only inspection helpers. Backup exclusions are in [operations](operations.md).
