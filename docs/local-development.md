# Local development

Run commands from the repository root with Python >=3.12 and uv. The
[README](../README.md) provides the new-demo quickstart. Dependencies are locked:

```sh
uv sync --locked --extra dev
```

A stale lockfile makes this command fail. The frontend is plain JavaScript/CSS and
Django templates, with no Node build, asset bundler or separate typing command.
Node is needed for the optional syntax check in the [CI guide](CI.md).

## New demos and existing installations

`pokemon_hunter.beta.synthetic --output DIRECTORY` creates a new private demo
outside the checkout. It reads packaged public metadata and generates accounts,
copies, goals and geometric photos. Passwords are in `credentials.json`; keep it
private. The seed refuses an existing directory and must not be used to restart
an installation.

For an existing authenticated installation, select its private directory:

```sh
export DEX_APP_ROOT="$HOME/.local/share/dex"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" check
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

Use the directory that actually holds your installation. `DEX_APP_ROOT` is a shell
variable; the CLI sets `DEX_B1_ROOT` and `DJANGO_SETTINGS_MODULE`. The root must be
outside the checkout, have mode 0700, and contain its database and secret. The
server binds to `127.0.0.1:8011`, starts a scan worker when photo entry is enabled,
and does not reload automatically. Restart after a source update; do not launch
a duplicate worker.

The lower-level `init --b2 --parity --copied-inventory PATH` creates a new isolated
root from a compatible inventory database. It neither imports arbitrary SQLite
files nor populates an empty catalog. Use the demo for development. Migrating a
real collection requires the supported import workflow and a backup.

## Configuration

| Setting | Purpose |
| --- | --- |
| `DEX_PROFILE` | `local` by default; `staging` selects PostgreSQL/HTTPS settings; other values fail |
| `DEX_B1_ROOT` | Private local root selected by the CLI |
| `scan-config.json` | Recognition enablement, provider and lifetime ceilings; see [photo entry](photo-entry.md) |
| `OPENAI_API_KEY` | Server/worker environment for explicitly selected API recognition |
| `PATH`, `HOME`, optional `CODEX_HOME` | Locates the CLI recognizer and its own authentication |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | eBay credentials; process environment overrides the local `.env` |
| `EBAY_DELIVERY_POSTAL_CODE` | Optional destination override |
| `config/settings.yaml` | eBay environment, marketplace, destination and bounded search settings |

Use `.env.example` for local credential names. Recognition credentials belong in
the server environment, not `scan-config.json`. The authenticated app loads only
the three eBay settings from `.env`. The original watcher also supports its
optional outbound webhook. [eBay hunts](hunts.md) explains Sandbox/Production
credential separation. Missing settings use model defaults in the authenticated
app; malformed existing settings fail.

`staging_config.profile` owns profile selection. Local initialization rejects
staging before creating files. Persisted capability-marker names are compatibility
contracts, not instructions to fabricate files. Older account-only roots remain
supported. Use [operations](operations.md) for backup and optional staging setup.

## Tests and optional tools

Select focused tests for the behavior you change:

```sh
uv run --no-sync pytest -q tests/test_b2.py tests/test_filtered_goals.py
```

Accounts are covered by `test_b1.py`, collection transactions by `test_b2.py`,
photo jobs by `test_b3.py`, shared policy by `test_ssot.py`, and public browsing by
`test_public_access.py`. CI reporting and historical metrics have separate suites.
Original-app collection, ingress/privacy and initializer tests are also separate.
Numeric test names remain stable command targets, not setup steps.

Browser harnesses under `scripts/verify_*` require Playwright. Read their help
before use: they can generate accounts, mutate synthetic data and write captures.
Never point them at a real collection. `scripts/ci/browser.py` creates its own
synthetic root and starts `scripts/serve_e4a.py`, which refuses ordinary roots and
blocks acquisition. UI comparison harnesses use either HEAD or a saved source
copy as their baseline; follow the selected harness's instructions.

`scripts/init_local.py` initializes only the separate original app. It creates
missing private files and never replaces existing state.

## Repository conventions

`beta/templates` and `beta/static` implement the Django UI; `web` implements the
original app. [Architecture](SSOT.md) describes module ownership and persisted
contracts; [UI guidance](UI_DESIGN.md) describes presentation and accessibility.
Keep account verification at service boundaries and public output allowlisted.

Public catalog packages, source licenses, synthetic fixtures and runtime assets
are repository inputs. Packaging selects public data explicitly in `pyproject.toml`;
`runtime_data.py` resolves the source or installed layout. Do not replace those
inputs with private sidecars. Keep secrets, exports, reports, screenshots and local
working notes out of Git. Put generated captures in `reports/` or `evidence/`;
authored public media can be tracked normally.

Ruff uses a 110-character line setting and E4/E7/E9/F/I rules. Review cohesion when
Python exceeds 500 lines, JavaScript/styles 300 or templates 250; above
1,000/600/500 respectively, extract a real responsibility or explain its necessary
coupling. Dense render strings also need review. Do not split bulk data, change
persisted schemas or compress formatting merely to reduce line counts.

Collection confirmation/undo stays together to expose recomputation, revision and
before/after-image invariants. Sealed package types and cross-record validation
share a publication service. Installed-artifact probes stay inside their isolated
interpreter rather than importing ambient checkout helpers. Frontend route
presenters still share dialog state and classic-script globals; changing that
ownership or the stylesheet cascade requires focused behavior checks.
