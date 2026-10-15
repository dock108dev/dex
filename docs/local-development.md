# Local development

Use Python 3.12 or later and [uv](https://docs.astral.sh/uv/). From the repository root:

```sh
uv sync --locked --extra dev
```

The lockfile is required. The frontend uses Django templates and plain JavaScript/CSS,
with no bundler or Node build. Node is needed for [source and renderer checks](CI.md).
The checkout environment and an installed application's runtime are independent.

## Existing installations

Select the existing private application root and its installed interpreter. Check
whether the server is already running before starting another process; local serving
uses fixed port 8011.

```sh
export DEX_APP_ROOT="/absolute/path/to/existing-dex-installation"
export DEX_APP_PYTHON="/absolute/path/to/installed-runtime/bin/python"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

Open [Dex](http://127.0.0.1:8011/) and sign in normally. The server binds to loopback
and does not reload automatically. Stop a server you started with Ctrl-C. When photo
entry is enabled, serving also starts a scan worker. Older account-only roots remain
supported; optional capabilities require explicit enablement through the CLI.

Never rerun initialization or bootstrap to restart an existing collection. Back up
private state before data-changing updates; [operations](operations.md) covers backup
exclusions and runtime rollback. Verify the running process selects the intended root
and interpreter. Starting the app does not refresh dated prices.

## Engineering fixtures

A fresh checkout contains public inputs and code, without a personal collection or
login. To create a simulated development instance, choose a nonexistent directory:

```sh
export DEX_DEMO_ROOT="$HOME/.local/share/dex-synthetic-demo"
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output "$DEX_DEMO_ROOT"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_DEMO_ROOT" serve
```

The initializer refuses an existing directory. Use port 8011 only when the ordinary
installation is stopped. Passwords for `admin` and `synthetic-member` are in the new
root's private `credentials.json`. Recognition is simulated and price coverage may be
absent. Later launches use only `serve`. Fixtures belong in engineering work; use the
existing installation and actual state for customer walkthroughs.

The lower-level `init --b2 --parity --copied-inventory PATH` creates a new private root
from an explicitly supplied inventory copy. It does not populate an arbitrary empty
catalog. `bootstrap` provisions an owner interactively. Inspect CLI help before creating
accounts or enabling capabilities:

```sh
uv run --no-sync python -m pokemon_hunter.beta.cli --help
```

`scripts/init_local.py` initializes the separate [original app](ORIGINAL_APP.md).

## Configuration

| Setting | Purpose |
| --- | --- |
| `DEX_PROFILE` | `local` by default; `staging` selects PostgreSQL/HTTPS settings |
| `DEX_B1_ROOT` | Private root selected by the local CLI |
| `scan-config.json` | Recognition mode and lifetime ceilings; see [photo entry](photo-entry.md) |
| `OPENAI_API_KEY` | Server/worker environment for explicitly selected API recognition |
| `PATH`, `HOME`, optional `CODEX_HOME` | CLI recognition executable and its own authentication |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | eBay credentials; nonempty server values override the local `.env` |
| `EBAY_DELIVERY_POSTAL_CODE` | Optional destination override |
| `config/settings.yaml` | eBay environment, marketplace, destination and search bounds |

Use [.env.example](../.env.example) and [settings.example.yaml](../config/settings.example.yaml)
for supported names and values. The authenticated app reads only the eBay values from
`.env`; recognition credentials belong in the server environment. The watcher also
supports an optional outbound webhook. Missing settings use model defaults; malformed
existing settings fail. Local initialization rejects staging before creating files.
Persisted marker names are compatibility identifiers.

The eBay configuration root comes from Django `PROJECT`, independently of the private
data root and working directory. A source launch reads the checkout; an installed
wheel resolves a directory above its package. Do not assume checkout settings configure
an installed server. Use the authenticated status refresh to inspect readiness without
exporting private hunt history or credentials. Environment changes require a normal
server restart. See [provider settings](hunts.md#local-provider-settings).

## Testing

The `dev` extra supports lint, formatting and focused tests:

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q tests/test_b2.py tests/test_filtered_goals.py
```

Select tests for the affected behavior. Accounts, collection transactions and photo
jobs are covered by `test_b1.py`, `test_b2.py` and `test_b3.py`; these names are stable
test targets. The full suite needs socket guards from the `ci` extra:

```sh
uv sync --locked --extra dev --extra ci
uv run --no-sync pytest -q --disable-socket --allow-unix-socket
```

[CI](CI.md) documents JavaScript checks, browser setup, packaging and workflow checks.
Browser helpers use synthetic state and must never target a personal root.
`scripts/ci/browser.py` creates its own root and uses `scripts/serve_e4a.py`, which
refuses ordinary roots and blocks acquisition. `qualify_shopping.py` and
`qualify_lot_calculator.py` retain reusable fixture/server helpers; their default
journey commands are retired. Use the CI browser harness for integrated journeys.

## Maintenance conventions

Django UI lives in `src/pokemon_hunter/beta/templates` and `static`; `web/` serves the
original app. The [architecture map](SSOT.md) identifies domain owners and persisted
contracts. [Interface guidance](UI_DESIGN.md) covers hierarchy, navigation and access.
Keep account verification at service boundaries and public output allowlisted.

Packaging selects public catalog inputs and licenses explicitly in `pyproject.toml`;
`runtime_data.py` resolves source and installed layouts. Retain required fixtures,
runtime artwork mappings and authored tools. Keep credentials, collection state,
private prices, exports, captures, build output and working notes out of Git.

Ruff uses a 110-character line setting and E4/E7/E9/F/I rules. Extract responsibilities
when a module becomes hard to maintain, while preserving coupled validation and atomic
transaction boundaries. Do not split bulk data or alter persisted schemas to reduce
line counts. Shared fixture builders belong outside collected test modules.

Collection preview, confirm and undo share revision, generation and before/after
checks. Sealed publication validates cross-record references atomically. Card grouping
uses one literal identity policy; effective ownership uses one generation-checked pass.
Shopping shares source admission and history policy. Preserve these single authorities
rather than adding alternate readers or parallel policy implementations.

The collection controller owns editor/dialog/request state and delegates card/species
rendering. The lot controller owns its request guard, serialized lock writes and
user-input-only draft lifecycle. Styles share an ordered cascade; verify responsive
behavior when reorganizing them. Read-only test fingerprints live in
`scripts/qualification_state.py`; importing it performs no setup or database access.

Generated checks write to ignored `reports/`; PDF previews use `output/pdf/` or
`tmp/pdfs/`. Maintained documentation must explain current behavior without requiring
local reports or private notes.

## Private price snapshots

[Price snapshots](price-snapshots.md) documents schemas, reviewed source admission,
operator commands and focused tests. [Operations](operations.md#snapshot-retention-and-backups)
covers backup exclusions and independent revocation preservation. Import and browsing
make no provider calls. Coverage depends on privately admitted packages and contracts.

## Bounded group-metadata collector

`python -m pokemon_hunter.metadata_collector` is a specialized operator for TCGCSV
Pokémon group metadata. It cannot fetch products or prices or activate a source. It
requires an exact reviewed manifest digest and current acquisition authorization.
Inspect its help before use; it is tied to a configured local installation and is
not a portable general-purpose downloader.

A separate process can request Stop through its request store. The supervisor bounds
worker lifetime. Both the private result and publisher-wide noncontent journal live
outside Git and the application root; preserve consumed attempts independently of app
restores. Never reset the journal to bypass its 24-hour interval. No automatic retry or
schedule exists.

Only a completely validated canonical UTF-8 metadata file is retained. Raw response
bodies, prices and provider exception text stay out of summaries. Metadata identity
does not establish card products, edition, finish or variant. On interruption, preserve
consumed state, let the bounded child exit and clean pending managed body copies.
