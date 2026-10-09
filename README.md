# Vintage 251

A local Pokémon collection app for browsing species #001–251, tracking physical
cards, building collecting goals, researching packs and saving eBay searches.
It supports personal collections and invited accounts on the same local installation.

Catalog and product coverage is partial. Seller observations are dated; the app
never buys, bids or treats a listing as proof of ownership.

## Requirements

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/).
- macOS or Linux for the local application. Windows process handling is unsupported.
- An unused local port 8011.

## Quickstart

From the repository root, create a new synthetic demo outside the checkout:

```sh
uv sync --locked --extra dev
export DEX_DEMO_ROOT="$HOME/.local/share/dex-synthetic-demo"
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output "$DEX_DEMO_ROOT"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_DEMO_ROOT" serve
```

Open [Pokédex](http://127.0.0.1:8011/pokedex/). Browse without signing in, or use
`admin` and its generated password in the demo's private `credentials.json`.
The demo creates test accounts, catalog entries, copies and photos without reading
an existing collection or contacting providers. Recognition is simulated; guide
prices and hunt snapshots may be unavailable.

The seed refuses an existing directory. On later launches, run only `serve`.
Stop with Ctrl-C. For an existing installation, use its private root and follow
[local operations](docs/operations.md); never reseed it.

## Capabilities

- Public species, card-printing and general Pack lookup browsing.
- Private copies, intentional duplicates, binders, import/export and reviewed undo.
- Frozen species or printing goals with explicit progress policies.
- Private photo entry, manual matching and optional configured recognition.
- Reviewed catalog publication, product contents and dated seller observations.
- Explicit eBay searches, delivered-price/guide comparisons and saved results with
  identities hidden until reveal.

Real-card recognition accuracy, all-era variant coverage and current buying
availability remain limited. Unknown identity, stock, shipping and coverage stay
visible. Recognition providers and eBay require separate configuration.

## Development

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q
```

Select relevant test files for focused work. Tests use temporary synthetic state.
See [development](docs/local-development.md), [CI](docs/CI.md),
[architecture](docs/SSOT.md), [security](docs/SECURITY.md),
[recovery](docs/ERROR_HANDLING.md), [UI](docs/UI_DESIGN.md),
[catalogs and packs](docs/catalogs.md), [photo entry](docs/photo-entry.md) and
[eBay hunts](docs/hunts.md).

The [original FastAPI app](docs/ORIGINAL_APP.md) and [lot watcher](docs/legacy-watcher.md)
use separate storage. Git excludes local collection data and is not a backup.
