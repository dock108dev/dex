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

### Recorded customer delivery

The established customer root is
`/Users/michaelfuscoletti/Desktop/dex/.local/customer`, recovered October 18, 2026.
The latest retained installed closeout is SHOP-10, October 20, at port 8011, using
`/Users/michaelfuscoletti/.local/share/dex/runtimes/shop-10-20261020/bin/python`.
This is a delivery record, not a fresh process observation. Verify the actual root,
listener and selected interpreter before any interactive session or update.

SHOP-10 used Python 3.12.15, with all 69 dependency versions matching SHOP-09;
248 installed application members and ten served assets matched its package.
Wheel SHA-256: `a614a5974bded685c70870b3fbe0586b09a8fb0d0a4bbb9b0ab25e3a2940d616`.
Installed tree SHA-256: `7a560f769ed0aaf6bbd1dda0ec05d5164229d0b2506c1ee9db5238b9122a8afc`.
The private installed PROJECT configuration link was preserved; never print secrets.
No migration ran. The record preserves 207 copies, seven declarations, three goals,
protected configuration and independent history. Only normal session renewal and
sanitized provider accounting changed. Its 3 OAuth/5 Browse operations completed;
review/save/Back made no provider requests. These are historical counts, not current
collection totals or available capacity.

Retained local evidence: `reports/shop-10-20261020/closeout.md`,
`candidate-manifest.json`, `final-preservation.json`, `session-renewal.json` and
`rollback.md` in that directory. Protected backup:
`/Users/michaelfuscoletti/.local/share/dex/backups/shop-10-20261020`.
SHOP-09 was retained for rollback. Verify recovery artifacts before use and never
restore older consumed accounting or excluded managed price content.

SHOP-06 recovered an Apple system-Python/Xcode-license startup failure by selecting
Dex's supported interpreter for both launcher stages. No license was accepted and
no database restore was needed. Its historical backup includes a functional
previous-interpreter launcher; do not restore the blocked system-Python wrapper.
Current launcher instructions below govern startup; historical PIDs are not targets.

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
listener on port 8011. It refuses a missing installation and never seeds one.
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
`photo_batch_images.py` handles image bytes; `photo_batches.py` owns leases and
transaction sequencing. Keep Stop, authorization and journals explicit when extracting.

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
sequencing, with image processing separate.

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

## Source maintenance evidence

The following completed source work is distinct from installed SHOP-10. Current
source includes its implementation; retained results qualify only their recorded
candidates. No newer installed delivery is established by these records.

| Work | Completed implementation and recorded verification |
| --- | --- |
| SSOT enforcement, October 20 | Shared listing amount/rounding and timestamp admission; invalid shipping preserves valid price; inert query category parameter removed. `reports/ssot-enforcement-20261020/review.md` records 424 focused tests, 32 new cases and 11 reproduced failures, compilation/lint/docs checks. Scoped digest `6bdb09bf8049d0d2876355eceea931ef35e7fe25927dd6c8718c0dc7c1e14cef`. Domain decisions remain in [SSOT](SSOT.md#listing-value-authority). |
| Interface candidate, October 20 | Adjacent Search/Stop, aligned refinements, clearer amounts and offer-first inspection. `reports/interface-20261020/review.md` and `review.html`: 32 focused pytest checks including 26 discovery/14 inspection client cases, ten browse groups and nine matched-preview groups. Digest `84b273137cb40b04884ad108ab5b7b97a5d799ebb59f1699cb567e8dc37a03ae`. Controlled synthetic 1280/390/320px and 200% text previews, not customer usability; 390px results position changed from 1,485 to 817px. [Interface design](UI_DESIGN.md#shopping) describes this source presentation. |
| CI maintenance, October 20–21 | Minimum-runtime distribution, compatibility/browser checks and dependency updates. [CI evidence](CI.md#recorded-local-qualification) owns the local/hosted distinction. |
| Repository cleanup, October 21 | `discovery_contracts.py` and `hunter_lot_parser.py` separate checked types and bounded parsing; compatible public imports, package guards and behavior-grouped tests remain. Former tracker reported 247 focused checks in worktree/clean export, preserved 57 existing test functions and digest `c77da4c4fb3bcfcdbc2f3517d127bbce9154fe062fba51ec0c338018dcd489a8`. Its referenced `reports/repository-cleanup-20261021/` directory is absent at this reconciliation; those test/digest/preservation claims are tracker-only, not independently verified evidence. |

The first two available reports record no customer-root access, installed update,
provider operations or migration. Their manifests and source deltas remain local
historical evidence. The cleanup tracker reported nine edits/four additions with
573 incoming files reconciled; the missing report prevents checking that claim.

At the October 21 documentation reconciliation, checkout HEAD is `32d6f9f`
(`Enhance Dex.command and update dependencies`), beyond the CI report's `f333366`
base. The old statements that HEAD/index remained unchanged describe those prior
passes only. Current source includes the extracted modules; their presence does not
prove the missing cleanup results or qualify the whole current commit. Recover
missing evidence or rerun appropriate exact-candidate checks if successor delivery
is requested. Do not reuse earlier CI or installed-package results as current proof.
