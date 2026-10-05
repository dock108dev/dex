# Local development

The expanded beta requires [data collection and engineering](BETA_REQUIREMENTS.md).
Start the D1 source/universe assessment and E1 schema/import slice in the Desktop
`dex_next_steps.md` handoff. Use disposable roots and copied state; do not seed or
rehearse migrations on the owner installation. Retain real data provenance even
when functional checks use synthetic fixtures.

Run commands from the repository root with Python >=3.12 and uv. CI tests Python
3.12 and 3.14 on Ubuntu; the current local product target is macOS.
`uv sync --locked --extra dev` installs the committed dependencies and rejects a
stale lockfile. There is no Node build or separate type-check command: the frontend
is ordinary JavaScript/CSS and Django templates. CI checks browser-script syntax
with Node; the [CI guide](CI.md) owns the exact validation commands.

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
| `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` | Server-only eBay application credentials for explicit local live hunts; environment values override the local `.env` |
| `EBAY_DELIVERY_POSTAL_CODE` | Optional eBay destination override from the server environment or local `.env` |
| `config/settings.yaml` | Shared eBay environment, marketplace, destination and bounded search settings; also used by the original watcher/app |

Local authenticated eBay search reads only the three eBay keys listed above from
the checkout's `.env`; it does not load recognition or webhook credentials from
that file. Both consumers use `config.read_env` / `config.load_settings`; the original
CLI requires its settings file, while beta can use model defaults if it is absent.
Malformed existing settings fail rather than selecting a fallback environment.
Map App ID (Client ID) to `EBAY_CLIENT_ID` and Cert ID (Client Secret)
to `EBAY_CLIENT_SECRET`; Dev ID is not required. Credentials must match the
`environment` selected in `config/settings.yaml`. The committed example selects
Production; Sandbox requires a separate Sandbox credential pair. Access depends
on the application keyset and provider permissions, not merely nonempty keys.
Use `.env.example` for names and keep real secrets private. Live hunts
are disabled in the optional staging profile. See [eBay hunts](hunts.md) for the
explicit search workflow and result limits. Never put API credentials in
`scan-config.json`. Marker names such as `B1_ISOLATED`,
`B2_PARITY_ISOLATED`, `B3_ISOLATED` and `B4_ISOLATED` are persisted capability
contracts, not steps a new reader must perform. Do not rename or manually fabricate
them. Older account-only roots remain supported.

## Tests and navigation

Use the [CI guide](CI.md) for compilation, browser syntax and Ruff commands,
and select focused pytest files for the component you change.
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

## Frontend and repository conventions

Django templates and `beta/static` own the authenticated UI; `web` owns the
original app. Keep results and primary actions ahead of optional breakdowns.
Show guide dates, incomplete coverage, unresolved variants and auction uncertainty
alongside comparisons. Browser harnesses use synthetic data and cannot establish
provider access, real-device behavior or recognition accuracy.

`verify_search_clarity.py` intercepts all requests in the actual beta shell for
configured/disabled, failed/empty/populated searches and long saved history.
It records source hashes with captures. Both presentation harnesses support desktop
and narrow viewports; consult their help before creating disposable output.

`scripts/init_local.py` provides an import-safe `initialize(root)` entry point.
Missing examples fail before creating destinations. Existing files are never
replaced; new local files use mode 0600. Git excludes private state, evidence and
media. Public catalog inputs, examples, synthetic fixtures and runtime assets are
tracked. Add public authored media through a path-specific ignore exception.


## E2a runtime qualification — October 4

E2a runtime qualification now passes: locked synchronization, all three process
cleanup cases and the full suite (458 passed, one existing warning), plus compilation,
JavaScript syntax, lint and formatting. Fresh copied-state preservation and zero-call
frozen-hunt service assertions pass. E2a remains partial: renewed explicit browser
permission was requested and is pending; no server, navigation, UI captures or owner
acceptance occurred. [Qualification record](history/2026-10-04-E2A-QUALIFICATION.md)
retains commands, runtime, exact hashes and preservation evidence. Full E2 and beta
remain open.


E3a retained-data pack discovery: see [setup and remaining browser qualification](E3A.md).
Only use fresh synthetic/copy roots. The current execution sandbox denies loopback
bind and process inspection; do not substitute an owner root or weaken security.
