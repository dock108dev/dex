# Dex

A local Pokémon collection app for browsing species #001–251, tracking physical
cards, building collecting goals, researching packs and checking eBay listings.
It supports personal collections and invited accounts on the same local installation.
The Python distribution and command-line tool are named `pokemon-hunter`.

Catalog and product coverage is partial. Seller observations are dated; the app
never buys, bids or treats a listing as proof of ownership.

## Requirements

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/).
- macOS or Linux for the local application. Windows process handling is unsupported.
- Port 8011 for the ordinary local server; reuse an already running installation.
- Node.js 24 (see `.nvmrc`) for JavaScript checks. Playwright and other CI tools
  are optional for focused work.

## Quickstart: existing installation

Reuse the existing installation and its compatible runtime; check whether it is
already serving before starting another process. Follow
[existing-installation startup](docs/local-development.md#existing-installations)
and use ordinary sign-in at [Dex](http://127.0.0.1:8011/):

```sh
export DEX_APP_ROOT="/absolute/path/to/existing-dex-root"
export DEX_APP_PYTHON="/absolute/path/to/installed-runtime/bin/python"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

A fresh checkout contains code and public catalog inputs, not a personal collection
or login. For an explicitly simulated development instance, use the
[synthetic setup](docs/local-development.md#engineering-fixtures).

Updating a checkout environment is not an installed-app update. Preserve data
before changes; never reseed an existing installation.
[Operations](docs/operations.md) covers backup/recovery.

## Capabilities

- Public species, card-printing and general Pack lookup browsing.
- Private copies, intentional duplicates, binders, import/export and reviewed undo.
- Current Pokédex completion by date, set and card criteria, plus frozen species
  or printing goals with explicit progress policies.
- Private photo entry, manual matching and optional configured recognition.
- Reviewed catalog publication, product contents and dated seller observations.
- Explicit Shopping searches, assisted listing checks and delivered-price/reference
  comparisons, with discovery identities hidden until reveal. New results are
  temporary; existing saved hunt research remains available.
- Vintage Shopping lots with separate included quantities and wanted targets,
  four independent guide-value scenarios and rights-permitted saved comparisons.

Real-card recognition accuracy is unmeasured; all-era variant coverage and current
buying availability remain incomplete. Unknown identity, stock, shipping and coverage stay
visible. Recognition providers and eBay require separate configuration.
Shopping uses dated, admitted retained references and privately activated source
snapshots. Scheduled acquisition is unavailable. Missing values remain unpriced.

## Development

```sh
uv sync --locked --extra dev
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q tests/test_b2.py tests/test_filtered_goals.py
```

Select relevant test files for focused work. Tests use temporary synthetic state.
The [architecture map](docs/SSOT.md#authoritative-services) identifies domain owners
and shared data contracts.
See [development](docs/local-development.md), [CI](docs/CI.md),
[architecture](docs/SSOT.md), [security](docs/SECURITY.md),
[recovery](docs/ERROR_HANDLING.md), [UI](docs/UI_DESIGN.md),
[catalogs and packs](docs/catalogs.md), [photo entry](docs/photo-entry.md) and
[Shopping and eBay](docs/hunts.md).

The [original FastAPI app](docs/ORIGINAL_APP.md) and [lot watcher](docs/legacy-watcher.md)
use separate storage. Git excludes local collection data and is not a backup.
