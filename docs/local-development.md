# Local development

Run commands from the repository root with Python >=3.12 and uv. CI tests Python
3.12 and 3.14 on Ubuntu; the current local product target is macOS.
`uv sync --locked --extra dev` installs the committed dependencies and rejects a
stale lockfile. There is no Node build or separate type-check command: the frontend
is ordinary JavaScript/CSS and Django templates.

## New demo versus existing installation

The README's `pokemon_hunter.beta.synthetic` command is the portable demo setup.
It generates two accounts, catalogs, copies, goals, request history and geometric
photos in a new private directory. `credentials.json` holds random passwords for
`admin` and `synthetic-member`. It also writes a copied database and configuration
sidecar for optional staging rehearsals. It reads packaged catalog data only.
The simulation includes a retained reservation for testing accounting behavior.

For an existing authenticated installation, set a shell variable to its existing
private root and launch it; do not seed, initialize or bootstrap again:

```sh
uv run python -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" check
uv run python -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

`DEX_APP_ROOT` is a shell convenience, not a runtime configuration key. The CLI sets
`DEX_B1_ROOT` and `DJANGO_SETTINGS_MODULE` internally. The root must be outside the
checkout with mode 0700 and private `inventory.db` and `secret.key` files. Keep
these together across restarts. The server listens only on 127.0.0.1:8011 with no
automatic reload. Restart after changing source. `serve` starts the scan worker
when photo entry is enabled; do not start a second local worker unnecessarily.

The lower-level `init --b2 --parity --copied-inventory PATH` command creates a new
root from a compatible copied inventory database. It is not a general import of
arbitrary SQLite files or a restart command. Empty low-level initialization does
not populate a catalog. Use the synthetic seed for development; importing an
existing collection is a separate data migration. Original-app and authenticated
stores are never automatically synchronized.

## Configuration

| Setting | Role |
|---|---|
| `DEX_PROFILE` | `local` by default; `staging` selects separate PostgreSQL/HTTPS configuration |
| `DEX_B1_ROOT` | Private root set by the local CLI's `--root` argument |
| `scan-config.json` in the root | Provider, enablement and lifetime API reservation ceilings; see [photo entry](photo-entry.md) |
| `OPENAI_API_KEY` | Server/worker environment only, for explicitly selected API recognition |
| `PATH` / `HOME` / optional `CODEX_HOME` | Locates the CLI and its own saved authentication for CLI recognition |
| `.env` and `config/settings.yaml` | Original watcher/app configuration only; `.env.example` documents eBay and optional webhook keys |

The authenticated server does not load the original app's `.env` file. Never put
API credentials in `scan-config.json`. Marker names such as `B1_ISOLATED`,
`B2_PARITY_ISOLATED`, `B3_ISOLATED` and `B4_ISOLATED` are persisted capability
contracts, not steps a new reader must perform. Do not rename or manually fabricate
them. Older account-only roots remain supported.

## Tests and navigation

Use `uv run --no-sync python -m compileall -q src`, Ruff and focused pytest files.
`tests/test_b1.py` covers accounts, `test_b2.py` collection transactions,
`test_b2_parity.py` projections/hunts, `test_b3.py` photo jobs,
`test_codex_recognition.py` fake CLI processes, and `test_ssot.py` shared policy/routes.
Historical names remain stable to avoid breaking commands and fixtures.

Browser scripts under `scripts/verify_*` are optional developer harnesses with
additional Playwright requirements. Read each script's entry-point instructions;
some require fresh accounts and write fixture data. Never aim them at a personal
installation. `scripts/verify_ui_cleanup.py` intercepts data requests for synthetic
presentation checks; its `before` mode reads HEAD, so record HEAD with captures.

Local backup: stop the app and preserve the entire private root with its permissions,
including database, secret, provider settings and local evidence. Git excludes
private state and is not its backup. Staging has separate backup/restore commands.
