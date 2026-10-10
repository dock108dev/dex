# Local development

Run commands from the repository root with Python 3.12 or later and uv:

```sh
uv sync --locked --extra dev
```

The lockfile is required; `--locked` fails when it is stale. The frontend uses
Django templates and plain JavaScript/CSS, with no bundler or Node build.
Node is needed for the syntax and documentation check in [CI](CI.md).

## Existing installations

Set `DEX_APP_ROOT` to your existing private application directory outside the
checkout. It contains `inventory.db`, `secret.key`, capability markers and any
provider configuration. Check whether its server is already running before
starting another process; the local CLI uses the fixed port 8011.

```sh
export DEX_APP_ROOT="/absolute/path/to/your/existing-dex-installation"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

Open [Pokédex](http://127.0.0.1:8011/pokedex/) and use ordinary sign-in. The server
binds to loopback and does not reload automatically. Stop a server you started
with Ctrl-C. When photo entry is enabled, serving also starts a scan worker.
Older account-only roots remain supported; optional capabilities may require
explicit enablement. Inspect the CLI's help rather than fabricating marker files.

Back up the private root before data-changing updates; see [operations](operations.md).
Never rerun initialization or bootstrap merely to restart an existing collection.
Use that installation's current state for product walkthroughs. Test accounts,
prices and copied roots belong in engineering checks or an explicitly requested
simulation. Starting the app does not refresh dated prices.

## Engineering fixtures

For a new isolated test environment, choose a nonexistent directory outside the
checkout. The synthetic initializer refuses an existing directory:

```sh
export DEX_DEMO_ROOT="$HOME/.local/share/dex-synthetic-demo"
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output "$DEX_DEMO_ROOT"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_DEMO_ROOT" serve
```

Use port 8011 only when the ordinary installation is not running. The generated
`admin` and `synthetic-member` passwords are in the fixture's private
`credentials.json`. Recognition is simulated; price coverage may be absent.
Later launches use only `serve`. This fixture is not a new personal collection.

The lower-level `init --b2 --parity --copied-inventory PATH` creates a new private
root with an explicitly supplied inventory copy. It does not populate an arbitrary
empty catalog. `bootstrap` provisions an owner interactively; invitations and
capability enablement are explicit operator actions. See CLI help and [operations](operations.md).
`scripts/init_local.py` instead initializes the separate [original app](ORIGINAL_APP.md).

## Configuration

| Setting | Purpose |
| --- | --- |
| `DEX_PROFILE` | `local` by default; `staging` selects PostgreSQL/HTTPS settings; other values fail |
| `DEX_B1_ROOT` | Private root selected by the local CLI |
| `scan-config.json` | Recognition mode and lifetime ceilings; see [photo entry](photo-entry.md) |
| `OPENAI_API_KEY` | Server/worker environment for explicitly selected API recognition |
| `PATH`, `HOME`, optional `CODEX_HOME` | Locates CLI recognition and its own authentication |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | eBay credentials; process environment overrides the local `.env` |
| `EBAY_DELIVERY_POSTAL_CODE` | Optional destination override |
| `config/settings.yaml` | eBay environment, marketplace, destination and bounded search settings |

Use `.env.example` and `config/settings.example.yaml` for supported names and
values. Keep secrets local. The authenticated app reads only the three eBay
settings from `.env`; recognition credentials belong in the server environment.
The watcher also supports an optional outbound webhook. Missing authenticated-app
settings use model defaults; malformed existing settings fail. Local initialization
rejects the staging profile before creating files. Persisted marker names are
compatibility contracts, not a description of whether a collection is real.

## Testing

The `dev` extra supports lint, formatting and focused tests:

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q tests/test_b2.py tests/test_filtered_goals.py
```

Accounts, collection transactions and photo jobs are covered by `test_b1.py`,
`test_b2.py` and `test_b3.py`; numeric names are stable test targets, not setup steps.
Public browsing, shared policy, Shopping and CI reporting have separate suites.
`tests/ci_reporting_helpers.py` supplies shared reporting fixtures outside collected
modules. Some tests need socket guards from the `ci` extra; use it for the full suite:

```sh
uv sync --locked --extra dev --extra ci
uv run --no-sync pytest -q --disable-socket --allow-unix-socket
```

Browser harnesses under `scripts/verify_*` require Playwright. Read their help:
they use synthetic data and write captures. Never point them at a real collection.
`scripts/ci/browser.py` creates its own root and uses `scripts/serve_e4a.py`, which
refuses ordinary roots and blocks acquisition. The `qualify_shopping.py` and
`qualify_lot_calculator.py` modules retain fixture/server helpers; their default
journey commands are retired. Use the current CI browser harness for journeys.

## Maintenance conventions

`beta/templates` and `beta/static` implement Django UI; `web` implements the
original app. [Architecture](SSOT.md) describes module ownership and persisted
contracts; [UI guidance](UI_DESIGN.md) describes presentation and accessibility.
Account verification belongs at service boundaries; public output is allowlisted.

Public catalog packages, source licenses, synthetic fixtures and runtime assets
are repository inputs. Packaging selects them explicitly in `pyproject.toml`;
`runtime_data.py` resolves source and installed layouts. Keep credentials, collection
state, price snapshots, exports, captures, reports and working notes out of Git.
Git is not a backup of private application state.

Ruff uses a 110-character line setting and E4/E7/E9/F/I rules. Review cohesion when
Python exceeds 500 lines, JavaScript/styles 300 or templates 250; above
1,000/600/500 respectively, extract a responsibility or explain necessary coupling.
Do not split bulk data, change persisted schemas or compress formatting to reduce
line counts. Collection confirmation/undo shares revision and before/after checks;
sealed publication shares atomic cross-record validation. Preserve those boundaries.
Shopping input validation is independent of persistence; saved-history policy is
shared. Archive checks and installed process lifecycle live in separate CI modules.
