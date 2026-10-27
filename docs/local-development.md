# Local development

Dex has three separate entry points: the authenticated collection app, the
[original FastAPI app](ORIGINAL_APP.md), and the [lot watcher](legacy-watcher.md).
Their data stores do not synchronize. Use the authenticated app for accounts,
physical copies, collecting goals and Shopping.

## Requirements

Use Python 3.12 or later and uv on macOS or Linux. JavaScript checks use Node.js 24
from `.nvmrc`. Windows process handling is unsupported. Run development commands
from the repository root:

```sh
uv sync --locked --extra dev
```

## Existing installations

An existing installation consists of a private data root and a compatible installed
Python runtime. Set their paths explicitly; do not initialize or reseed the root:

```sh
export DEX_APP_ROOT="/absolute/path/to/existing-dex-root"
export DEX_APP_PYTHON="/absolute/path/to/installed-runtime/bin/python"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

Open [Dex](http://127.0.0.1:8011/) and use ordinary sign-in. Reuse an existing server
instead of starting a second one. A foreground server stops with Ctrl-C. The server
binds only to loopback and rejects foreign Host/Origin and forwarded headers.
Changing the checkout environment does not update an installed wheel.

For a private root under the checkout (such as `.local/customer`), use an installed interpreter.
Launching checkout code through `.venv` or `uv run` would put this root inside
that code's `PROJECT`; `beta/settings.py` refuses that layout. The installed
wheel's `PROJECT` is outside the checkout, so the established root remains valid.
Do not move, copy or reinitialize the collection to work around this guard.

### macOS launcher

`Dex.command` uses `DEX_APP_PYTHON`, or the ignored `.local/runtime/bin/python`
when no interpreter override is supplied. To configure an existing installed
runtime for double-click startup:

```sh
mkdir -p .local
ln -s "/absolute/path/to/installed-runtime" .local/runtime
```

Do not replace an existing runtime link casually. The link selects code, not data;
compatible updates need the backup procedure in [operations](operations.md).
Environment overrides must be available to the process launching `Dex.command`.
The helper uses `DEX_APP_ROOT`, defaulting to `.local/customer/`, and reuses a
listener on port 8011. Its listener test only detects an occupied port; it does not
verify that the process belongs to Dex or uses the selected root/runtime. Verify
the listener's command and root before relying on reuse. With no listener, it
refuses a missing installation and never seeds one.
Both the runtime link and default private root are excluded from Git.
The launcher clears inherited eBay credential/destination overrides so the installed
app reads its configured private `.env`. Direct CLI startup keeps normal environment
precedence.

### Storage and capabilities

Keep the database, authentication secret, photos, configuration and independent
accounting private. Do not run initialization, import, migration or capability
enablement merely to start an existing installation. Historical marker names such
as `B1_ISOLATED` and `B2_ISOLATED` are persisted capability contracts; their names
do not identify a personal collection as a test fixture. Startup checks private
permissions and enabled capabilities. See [recovery and backups](operations.md).

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
`photo_batch_images.py` handles image bytes; `photo_batch_journal.py` owns durable
append/read operations, tombstones and reservation projection. `photo_batches.py`
keeps its public journal imports and owns leases and transaction sequencing. Keep Stop, authorization and journals explicit when extracting.

`discovery_contracts.py` defines checked input and ephemeral run types without
account storage or worker activity. `discovery.py` retains the compatible exports
and the orchestrator's lock/admission/Stop lifetime. `hunter_lot_parser.py` owns
bounded seller-text/quantity interpretation; `hunter_lots.py` owns reauthorized
review leases, corrections and current-reference arithmetic. Parser limits and
the existing `hunter_lots.parse` import remain available to callers.

The discovery orchestrator keeps account checks, consumed-attempt journals,
deadline dispatch and final publication together because Stop must synchronize
with those phases. Hunter review projection stays with its checked lease and
comparison adapters; splitting its individual result fields would hide the
revalidation boundary. Photo jobs similarly retain transactional lease/journal
sequencing, with image processing and journal storage separate.

Snapshot tooling separates execution from `tcgcsv_capture_contract.py`,
`tcgcsv_capture_history.py` and `tcgcsv_capture_transport.py`. Execution retains the
installation lock through reservation, dispatch and terminal accounting. Pilot,
batch and cadence tests share non-collected `tcgcsv_capture_helpers.py` fixtures.
The Hunter browser runner separates process ownership from `hunter_ui_journey.py`;
the ordered journey retains one browser context, held responses and final cleanup.

Packaging selects runtime inputs in `pyproject.toml`; `runtime_data.py` resolves
source and installed layouts. Keep credentials, personal state and removable prices
out of Git. Generated checks belong in ignored `reports/`; maintained instructions
must work without local notes or generated evidence. Specialized acquisition and
runtime-transition operators remain bound to private reviewed installations; they
are not general setup commands.

## Private price snapshots

See [snapshot contracts and lifecycle](price-snapshots.md) for source admission,
activation, expiry and withdrawal. Import performs no acquisition; some current-price
reads prune managed files. [Operations](operations.md#snapshot-retention-and-backups)
describes backup exclusions and independent revocation/accounting state.


## Photo service boundaries

`photo_batch_journal.py` owns durable journal I/O and reservation projection;
`photo_batches.py` re-exports its existing public functions. Journal reads create
no files. Locking, fsync and unsettled-attempt charging remain independent of
recoverable database state.

The photo coordinator retains admission, Stop, publication, deletion and receipt
sequencing because those transitions share revision checks, leases and transaction
ordering. Its independent image processing, matching, addition planning and journal
storage are separate modules. Keep transaction bodies together when refactoring.

Photo lifecycle, recognition protocol and confirmation/report tests live in
`test_photo_batches.py`, `test_photo_recognition.py` and `test_photo_confirmation.py`.
Their synthetic fixtures are in non-collected `tests/photo_batch_helpers.py`.


## Recorded runtime maintenance status

The latest delivery record inspected for the October 27 plan reconciliation selects
`hunter-poc-20261027`, preserving the simplified photo and lot-finder deliveries.
This is a recorded runtime identity, not a fresh inspection of the running process.
Before maintenance, resolve the configured runtime and root using the startup
instructions and inspect its dependency inventory.

The October 25 inventory recorded filelock 4.0.12 and opentelemetry-api 1.45.0;
retained audit findings flagged those versions. Subsequent photo, lot-finder and
Hunter delivery records explicitly report no dependency changes. The dependency
repair therefore remains open unless a newer installed inventory establishes it.
The old SHOP-10 runtime statement is superseded by later delivery records; its
dependency inventory remains historical evidence, not a current measurement.
Evidence is local-only: `reports/docs-audit-20261025/installation-identity.json`
and the delivery closeouts described in [Shopping](hunts.md#delivered-behavior-and-verification-limits)
and [photo entry](photo-entry.md#delivered-verification-and-owner-review).

Select a bounded dependency repair preserving delivered behavior, or explicitly
reconcile a cumulative source successor. Never label a cumulative source update a
lockfile-only change. Qualify the selected package, preserve rollback and independent
journals, then follow [runtime updates](operations.md#runtime-updates-and-recovery).
A code rollback must not restore old consumed capacity or revoked data.
