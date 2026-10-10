# Vintage 251

A local Pokémon collection app for browsing species #001–251, tracking physical
cards, building collecting goals, researching packs and saving eBay searches.
It supports personal collections and invited accounts on the same local installation.

Catalog and product coverage is partial. Seller observations are dated; the app
never buys, bids or treats a listing as proof of ownership.

## Requirements

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/).
- macOS or Linux for the local application. Windows process handling is unsupported.
- Port 8011 for the ordinary local server; reuse an already running installation.

## Run the existing application

Select your existing private application directory and use normal sign-in.
[Local development](docs/local-development.md#existing-installations) explains
startup and separate test fixtures:

```sh
uv sync --locked --extra dev
export DEX_APP_ROOT="/absolute/path/to/your/existing-dex-installation"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

Open [Pokédex](http://127.0.0.1:8011/pokedex/).
Stop a server you started with Ctrl-C. Preserve data before updates; never reseed
an existing installation. [Operations](docs/operations.md) covers backup/recovery.

For engineering tests or an explicitly requested simulation, use the
[synthetic fixture instructions](docs/local-development.md#engineering-fixtures).
Fixtures are not the customer's collection or current prices.

## Capabilities

- Public species, card-printing and general Pack lookup browsing.
- Private copies, intentional duplicates, binders, import/export and reviewed undo.
- Frozen species or printing goals with explicit progress policies.
- Private photo entry, manual matching and optional configured recognition.
- Reviewed catalog publication, product contents and dated seller observations.
- Explicit eBay searches, delivered-price/guide comparisons and saved results with
  identities hidden until reveal.
- Vintage Shopping lots with separate included quantities and wanted targets,
  four independent guide-value scenarios and private saved comparisons.

Real-card recognition accuracy, all-era variant coverage and current buying
availability remain limited. Unknown identity, stock, shipping and coverage stay
visible. Recognition providers and eBay require separate configuration.
Shopping uses dated, admitted retained references; automatic price acquisition
is unfinished. Missing values remain unpriced.

## Development

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q tests/test_b2.py tests/test_filtered_goals.py
```

Select relevant test files for focused work. Tests use temporary synthetic state.
See [development](docs/local-development.md), [CI](docs/CI.md),
[architecture](docs/SSOT.md), [security](docs/SECURITY.md),
[recovery](docs/ERROR_HANDLING.md), [UI](docs/UI_DESIGN.md),
[catalogs and packs](docs/catalogs.md), [photo entry](docs/photo-entry.md) and
[eBay hunts](docs/hunts.md).

The [original FastAPI app](docs/ORIGINAL_APP.md) and [lot watcher](docs/legacy-watcher.md)
use separate storage. Git excludes local collection data and is not a backup.
