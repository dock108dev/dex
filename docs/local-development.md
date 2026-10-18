# Local development

Dex uses Python 3.12 or later, [uv](https://docs.astral.sh/uv/) and Node.js 24
(selected by `.nvmrc`). The frontend uses Django templates and plain JavaScript/CSS;
there is no bundler or Node build.

From the repository root:

```sh
uv sync --locked --extra dev
```

A checkout environment and an installed application's runtime are independent.
Updating one does not update the other.

## Existing installations

Current installed catalog: **22,389 identities / 187 sets, 4,722 eligible /
17,667 unpriced** after 51 additive existing-set packages / 5,101 additions.
Established root and URL are unchanged. The ordinary helper now selects
`/Users/michaelfuscoletti/.local/share/dex/runtimes/catalog-additive-release-20261017/bin/python`; wheel SHA-256
`115a336d4e36df4a64e268f587311810f71bc8f4a7396471d601c21290b2609f`, listener **81008**.
The exact release passes 169 focused socket-blocked tests and 326 S6 helper tests;
all passing packages were rehearsed and published in six bounded checkpoints.
Latest data, secret and existing Safari session survive the necessary restart;
one legitimate hourly renewal is separately verified. No migration/provider request.
[Combined delivery](../reports/catalog-additive-batch-20261017/closeout.md),
[installation](../reports/catalog-additive-batch-20261017/installation.json),
[current S6](../reports/catalog-additive-batch-20261017/s6-continuation.md).

The following dated delivery notes and package identities are historical.

LOCAL-AUTH-01 and REFERENCE-R2/A were installed October 17, 2026 in the established
owner root `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local`,
at `http://127.0.0.1:8011/`. The ordinary saved helper then selected
`/Users/michaelfuscoletti/.local/share/dex/runtimes/catalog-reference-capacity-20261017/bin/python`.
The exact repeat-built wheel SHA-256 is `4488bbea1f637e7386c24ebfafc627d4c4b49b9aed9989b6b09153e3dcff2749`.
It passed 1,339 selected socket-blocked tests, the 65,536-row composed capacity
check and persistent Chromium close/reopen/restart/logout qualification. The
actual installed reader still returns 4,694 observations across seven sources.
CATALOG-C1/B subsequently published the reviewed 115 Black & White numbered parents,
bringing the catalog to **7,768 identities / 69 sets**, with **4,722 eligible / 3,046
unpriced**. All 115 additions remain unpriced with unknown physical variants.
207 owned copies, three frozen goals and all original rows survive. All 59 table
schemas are unchanged; publication adds rows in seven catalog tables. No new
reference import or provider operation occurred. The previous qualified S5 and
initial auth runtimes remain preserved.

Ordinary local sign-in uses a persistent 30-day cookie, renewed through Django
at most hourly during authenticated successful visits. Browser closure and normal
server restart retain a valid session in the same persistent browser profile;
expiry is within one hour of 30 days after the last visit. The session key and
navigation binding are stable during renewal. Staging explicitly retains its
one-hour browser-session policy. HttpOnly, SameSite Strict, CSRF, POST logout,
fixation/revocation and loopback restrictions remain in force. Hunt leases,
temporary results, source expiry and budgets are independent. No secret or cookie
identity was regenerated. See [delivery and evidence](../reports/local-auth-catalog-capacity-20261017/closeout.md).

The owner completed ordinary sign-in in native Safari. That same ordinary profile
remained authenticated after Dex tab close/reopen, a normal server restart, and a
full Safari quit/relaunch. My Cards still showed 283 owned groups; native services
confirmed 207 copies and three unchanged frozen goals. No further sign-in is
needed for this session. Credentials and cookie/session values were not copied or
reset. See [actual publication and Safari evidence](../reports/catalog-c1b-20261017/closeout.md).
The subsequently reviewed **101 BW Black Star Promos parents are now published**
in this same installation: **7,869 identities / 70 sets, 4,722 eligible / 3,147
unpriced**. Fresh protected backup, installed-byte checks and guarded native
preview/verify/publish passed with zero old edits/archives. All 59 schemas and
original rows were preserved at publication; seven catalog tables received the
exact additive rows. Owner/goal meaning and every reference decision survive.
Safari's profile/session was not manipulated. A later ordinary hourly renewal
changed only the existing session's renewal marker and expiry, preserving its key,
owner and navigation. No runtime install, migration or restart occurred; listener
56688 is unchanged. See [current publication and preservation](../reports/catalog-bwp-20261017/closeout.md).
The launcher requests the OS default browser/window (`new=0`) at
one canonical origin; exact tab reuse is browser-controlled. Do not switch browser
profiles expecting shared cookies. Test browsers require their own user-data
stores; changing only the port does not isolate cookies.

The selected S6 continuation is rebound to this successor, with the same 300
children, resource history and unused 14-request ceiling. Its actual resource
window remains October 18, 20:04:24.557753 UTC (4:04 p.m. Eastern), followed by a
strictly newer publisher build. Its catalog binding now includes C1/B while its
package, targets and accounting remain unchanged. Its latest catalog binding also
includes BW Black Star Promos; use the [current successor continuation](../reports/catalog-batch-20261017/s6-continuation.md).
Historical S5/S6 reports and helpers are preserved.

The earlier S1 interpreter remains preserved at
`/Users/michaelfuscoletti/.local/share/dex/runtimes/hunt-11-s1-delivered-20261017/bin/python`.
The previous HUNT-09/10 interpreter remains preserved at
`/Users/michaelfuscoletti/.local/share/dex/runtimes/hunt-09-10-delivered-20261017/bin/python`
as historical delivery evidence. Its wheel was
`02f6b096f4189e8e2bddea37fac03abece93e730347b9ebf0ab0db9f149f0b3f`.
The earlier HUNT-08 interpreter remains preserved at
`/Users/michaelfuscoletti/.local/share/dex/runtimes/hunt-08-delivered-20261017/bin/python`.
The earlier SHOP-04 interpreter also remains preserved at
`/Users/michaelfuscoletti/.local/share/dex/runtimes/shop-04-delivered-20261016/bin/python`
as historical delivery evidence. Its October 16 delivery evidence is
historical under `reports/shop-04-20261016/`. The expanded catalog requires the
qualified S5 final runtime or a separately qualified compatible successor for
recovery against latest state: old code can expand normal-card attestations or
fail frozen publication membership. Retain current data and independent journals;
do not overlay an older backup to make older code run. Updating the checkout does
not update the installed interpreter. Preserve private provider configuration, current data
and independent journals through recovery. ON-02 real-photo evaluation and batch
delivery remain deferred; installed source modules do not enable their schema.

Reuse the existing private data root and its installed interpreter. Check the running
process and listener before starting another server. This installation uses:

```sh
export DEX_APP_ROOT="/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local"
export DEX_APP_PYTHON="/Users/michaelfuscoletti/.local/share/dex/runtimes/catalog-additive-release-20261017/bin/python"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" serve
```

Open [Dex](http://127.0.0.1:8011/) and sign in normally. The server binds to fixed
loopback port 8011 and does not reload source changes automatically. Stop a server
you started with Ctrl-C. Photo-enabled roots also start a scan worker. Ordinary
serving admits only single-card jobs explicitly submitted or retried in that
server process; old queued jobs do not dispatch automatically after a restart.
The ordinary worker does not dispatch deferred photo-batch recognition. Existing
expiry/revocation cleanup remains active, and startup and browsing never enable a schema.

Never rerun `init` or `bootstrap` to restart an existing collection. Do not replace
its data with a synthetic root. Back up private state before data-changing updates;
[operations](operations.md) covers exclusions, independent journals and recovery.
Starting the app does not refresh prices or acquire provider data.

The complete selected **117-set / 9,419-record catalog batch is now published**
in this same running installation: **17,288 identities / 187 sets, 4,722 eligible /
12,566 unpriced**. Listener 56688 and all 242 installed wheel members are unchanged;
no installation, restart or migration was needed. All 59 schemas, original rows,
207 active copies, three frozen goals and reference decisions survive. One new
catalog identity resolves the already explicit Eevee #84 / Dark Explorers broad
owner declaration; it creates no copy or exact-variant ownership. The other 9,418
rows are unowned. All 9,419 remain unpriced and physically unspecified.

The existing authenticated Safari profile is used for actual product checks;
no repeat login or persistence exercise. To avoid artwork acquisition, the live
walkthrough uses the twelve missing-image records in EX trainer Kit 2 (Minun),
with name/number search, Trainer/Energy, detail, unspecified variant and retained-
price absence checks. Native installed services additionally qualify all selected
sets, all-generation identities, literal/prefixed/padded numbers and image binding
precision above 10,000 identities. See the [combined closeout](../reports/catalog-batch-20261017/closeout.md).
S6 is bound once to the final catalog; the [current continuation](../reports/catalog-batch-20261017/s6-continuation.md)
preserves its same 300 targets/history and zero consumed / 14 remaining. Next
catalog work is the [additive existing-set batch](../reports/catalog-batch-20261017/next-batch-handoff.md).

## Engineering fixtures

A fresh checkout contains public inputs and code, without personal holdings or login.
Create a synthetic development instance in a nonexistent directory:

```sh
export DEX_DEMO_ROOT="$HOME/.local/share/dex/synthetic"
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output "$DEX_DEMO_ROOT"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_DEMO_ROOT" serve
```

The initializer refuses an existing directory. Port 8011 must be free. Passwords for
`admin` and `synthetic-member` are in the new root's private `credentials.json`.
Recognition is simulated and price coverage may be absent. Later launches use only
`serve`. Use synthetic state for engineering checks, and an existing installation
with its real state when someone asks to use their collection.

The lower-level `init --b2 --parity --copied-inventory PATH` initializes a new root
from an explicitly supplied inventory copy. `bootstrap` provisions its owner through
a private interactive terminal. Neither command is required for ordinary startup.
Inspect the available commands before provisioning accounts or enabling capabilities:

```sh
uv run --no-sync python -m pokemon_hunter.beta.cli --help
```

`scripts/init_local.py` initializes the separate [original app](ORIGINAL_APP.md).

## Configuration

| Setting | Purpose |
| --- | --- |
| `DEX_PROFILE` | `local` by default; `staging` selects PostgreSQL/HTTPS settings |
| `DEX_B1_ROOT` | Private root selected by the local CLI |
| `scan-config.json` | Recognition mode and spending ceilings; see [photo entry](photo-entry.md) |
| `hunter-policy.json` | Owner installation marker; select ordinary limits in Hunter usage settings |
| `hunter-installed.json` | Historical closed finite authority; see [operations](operations.md#historical-installed-hunter-authority) |
| `OPENAI_API_KEY` | Server/worker environment for explicitly selected API recognition |
| `PATH`, `HOME`, optional `CODEX_HOME` | CLI executable and its own authentication |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | eBay credentials; nonempty server values override the local `.env` |
| `EBAY_DELIVERY_POSTAL_CODE` | Optional destination override |
| `config/settings.yaml` | eBay environment, marketplace, destination and watcher bounds |

Use [.env.example](../.env.example) and
[settings.example.yaml](../config/settings.example.yaml). The authenticated app reads
only allowlisted eBay values from `.env`; recognition credentials belong in the server
environment. Its eBay reader uses model defaults only when the settings file is absent.
Malformed existing settings fail. The original watcher also supports an optional
outbound webhook. Persisted root marker names are capability contracts.

The authenticated eBay configuration root comes from Django `PROJECT`, independently
of the private data root and working directory. A source launch reads the checkout;
an installed wheel resolves a directory above its package. Do not assume checkout
settings configure an installed server. Readiness checks configuration without a
provider request; configured status does not prove remote access or remaining quota.
Restart normally after changing environment values. See [Shopping](hunts.md).

## Testing

The original HUNT-01–05 and LOT-01 slices were backend-only. Their historical
qualification did not select installation. HUNT-08 now supplies the separately
qualified installed Hunter; use the actual installation above for customer sessions.
The normal authority/CSRF API, finite two-lane service and local identity/reference
adapters can be exercised in engineering tests with `tests/test_hunter*.py`,
`test_discovery_matching.py` and the existing Discovery/reference regressions.
The Hunter backend implementation slices authorize zero provider operations; the exhausted HUNT-01 ledger is
unchanged. Their exact isolated candidate and closeout are retained under
`reports/hunt-02-03-20261016/`. Customer-facing sessions continue
using the actual installation above. The metadata-only `scripts/qualify_hunter.py`
audit may read that root without cleanup or provider acquisition. Genuine backend
qualification uses the saved Production configuration and the independently
consumed allowance described in [Shopping](hunts.md#hunt-01-backend-contract).

The historical bounded traversal/ranking/lot backend candidate is recorded under
`reports/hunt-04-05-lot-01-20261016/`. Its qualification selected no production
allowance. Tests use disposable roots and fake transports with external sockets
blocked. See [service/API contracts](hunts.md#hunt-0405-and-lot-01-backend-contracts)
for explicit continuation, local result cursors and temporary lot correction rules.

Use focused checks for the affected behavior:

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q tests/test_b2.py tests/test_filtered_goals.py
```

Socket guards and browser tooling are in the `ci` extra. When the full suite is needed:

```sh
uv sync --locked --extra dev --extra ci
uv run --no-sync pytest -q --disable-socket --allow-unix-socket
```

[CI](CI.md) documents JavaScript contracts, Chromium setup, distribution checks and
workflows. Browser helpers must use disposable synthetic state; the integrated
`scripts/ci/browser.py` creates its own root and blocks acquisition. Historical hunt
rendering is covered by `tests/test_parity_history_ui.py`.

## Maintenance conventions

The [architecture map](SSOT.md) identifies service owners and persisted contracts.
[Interface guidance](UI_DESIGN.md) covers presentation;
[effective collection](effective-collection.md) owns collection and bulk-review meaning.
Keep account verification at service boundaries and public output allowlisted.

Django templates and assets live under `src/pokemon_hunter/beta/`; `web/` serves the
original app. `collection.css` imports `collection-base.css` before
`collection-browse.css`. Preserve that cascade order. The collection controller owns
editing, dialogs and recovery while card/species renderers own browsing.

`bulk_formats.py` owns pure input formats and fingerprints; `bulk_input.py` resolves
account/catalog identities. `photo_batch_images.py` handles image bytes while
`photo_batches.py` owns admission, leases, journals and transaction sequencing.
`listing_details.py` projects seller responses; `listing_check.py` coordinates temporary
review and workers. Keep related authorization, Stop and transaction boundaries intact
when extracting responsibilities.

Ruff uses a 110-character line setting and E4/E7/E9/F/I rules. Split by responsibility,
not arbitrary chunks or compressed line counts. Shared test fixtures belong outside
collected test modules. Packaging selects public inputs explicitly in `pyproject.toml`;
`runtime_data.py` resolves source and installed layouts. Keep credentials, collection
state, private prices, captures and build output out of Git. Generated checks write to
ignored `reports/`; source checks must not require those local files.

## Manual bulk and photo batches

Manual bulk entry uses `/add-many/`. Its explicit `enable-bulk` command initializes
`collection_drafts` and `collection_replays`; startup and page reads never migrate.
Run enablement only for a root selected for that capability, after backup and a schema
check. The ordinary copy/goal export is not a complete backup of drafts or current
collection intent. `bulk-cleanup` performs explicit expiry/revocation maintenance.

Photo batches at `/add-photos/` require local scan support, the bulk schema and explicit
`enable-photo-batches`. They are unsupported in staging. Source availability does not
enable them in an existing installation. Manual matching remains available without
recognition; real-photo accuracy is unmeasured. See [photo entry](photo-entry.md) and
[photo-batch recovery](operations.md#photo-batch-recovery).

## Private price snapshots

HUNT-11/S4 completed offline reconciliation of all 660 S3 subtype ambiguities.
The ordinary process/root/S1 runtime, catalog and active release remain unchanged;
there was no installation, restart, migration, sign-in or provider request. Every
identity stays explicitly unknown: 355 source records lack variant detail and
305 list alternatives without assigning an existing printing. Price coverage
remains 4,722/7,036. Exact evidence and preservation results are in
[S4 closeout](../reports/hunt-11-s4-20261017/closeout.md).

Reproduce the metadata-only ledger in a new existing report directory:

```sh
uv run --no-sync python scripts/reconcile_tcgcsv_identity.py --root "$DEX_APP_ROOT" --output "$S4_REPORT_DIR"
```

The helper refuses existing output files, uses query-only catalog/publication
reads and blocks network connections. It reads no prices, initializes no app and
writes no customer state. Tests use fabricated metadata separately from the actual
root audit. No executable package contents changed in S4, so S1's installed
package qualification retains its original identity and limits. The checkout-only
reconciliation helper receives its own focused socket-blocked qualification.

HUNT-11/S1 installed the compatible reverse-holo runtime and qualified the finite
batch collector/preparation workflow. S2 added 546 references; **S3 subsequently
added 3,206**, completing four batches across all 63 selected groups. Current
coverage is **4,722 eligible identities / 7,036 printings**, with **2,314 unpriced**.
The active release `fda6cadc-224c-4e64-b88b-d71563f75cd4` contains 4,694 observations
across seven sources, preserving all 1,488 pre-S3 observations and their original
source lifecycle. Reference eligibility still requires seller identity/condition
fit and known costs for a complete listing comparison.

S3 used the established S1 interpreter, ordinary PID 52245, helper, actual root and
port without restart, installation or migration. The full application-tree digest
remains `447984031277cae32d3840c747112c0c51e38a67b5898bca34ba969975a9ff68`.
All 59 database tables/schema/bytes and protected owner state are unchanged.
Exactly 134 HTTP 200 requests completed: 126 product/price GETs and eight build
checks, zero groups metadata/eBay requests. Hunter remains disabled and ordinary
numeric limits remain unselected. Each batch's raw inputs and temporary manifest/
prepared copies were removed before the next capture; normalized source shards
retain ordinary expiry/withdrawal. Original accounting remains preserved.

Use disposable engineering roots for fixture tests and the established query-only
metadata audit for actual coverage. The executed plan, exact mapping decisions and
preservation evidence are in
[the S3 closeout](../reports/hunt-11-s3-20261017/closeout.md).
Earlier future-dated S1/S2 preflights remain historical. The corrected collector
supports explicit `initial_fill` for previously unreserved groups at the same or a
newer publisher build, while preserving `not_before`, the complete durable group
reservation, all finite ceilings and independent Stop. Ordinary `refresh` remains
subject to daily durable request spacing and a strictly newer build, without
requiring a 24-hour gap between build timestamps. Unknown historical scopes,
clock rollback, reused initial-fill groups and hidden retries remain refused.
Routine owner-authorized local work needs no repeated approval conversation.
See [bounded integration](price-snapshots.md#hunt-11-broader-references-offline-integration).

[Price snapshots](price-snapshots.md) documents schemas, source admission and operator
commands. [Backup policy](operations.md#snapshot-retention-and-backups) covers managed
price exclusions and independent revocations. Import and browsing do not acquire
provider data; coverage depends on admitted packages and source contracts.

## Bounded group-metadata collector

`python -m pokemon_hunter.metadata_collector` requests only the configured TCGCSV
Pokémon group metadata. It cannot fetch products or prices or activate a source.
It requires an exact reviewed manifest digest and current acquisition authorization.
Inspect its help before use.

The supervisor bounds worker lifetime and supports an independent Stop request.
Its private canonical result and publisher journal remain outside Git and the app
root. Preserve consumed attempts independently of restores; never reset the journal
to bypass its 24-hour interval. There is no automatic retry or schedule. Raw response
bodies and provider error text are not retained in summaries. On interruption, retain
consumed state, allow the bounded child to exit, then clean managed pending copies.

## Hunter UI engineering qualification

The following HUNT-06/07 records describe historical source and temporary-runtime
qualification. HUNT-08 installs `/shopping/hunter/` and temporary card/lot review
in the ordinary customer runtime listed above. It preserves the qualified Hunter
UI bytes. The exact HUNT-08 wheel passed 312 focused installed cases; ordinary
startup was exercised with disposable 44-table engineering state, while a separate
read-only compatibility check accepted the actual 59-table schema without migration.
Protected backup and latest-state runtime recovery were also rehearsed on disposable
state. These evidence classes remain distinct from actual installed observations.
See the `reports/hunt-08-20261017/closeout.md`.

HUNT-06 originally added Hunter only to the source candidate, while SHOP-04
remained installed. Production traversal was disabled, and HUNT-01 remains
exhausted. Use fabricated state only for engineering qualification.

Run `python scripts/qualify_hunter_ui.py --output reports/hunter-ui-local` in the
checkout engineering environment. This real Chromium harness creates fresh
disposable roots, uses in-process fake provider transport and controlled image/
lifecycle responses, and refuses the ordinary customer port. It records layout,
measured doubled text, API/action boundaries and zero external operations. These
fixtures are engineering evidence, not provider listings or customer acceptance.
The same harness can be invoked with a fresh isolated wheel interpreter; its
report records application origins and exact shipped asset hashes. Focused
renderer contracts use `node scripts/verify_hunter_review.js`.

HUNT-07 repeats the integrated source and fresh isolated-wheel gates and captures a
new query-only current-root preservation baseline under `reports/hunt-07-20261016/`.
The guarded operator/profile is implemented separately under
`reports/hunt-07-boundary-20261016/`. The supported entry is the isolated candidate
interpreter with `-I scripts/hunter_boundary.py preflight --identity PATH
--expected-identity SHA256`; use the exact absolute paths and frozen digest in its
execution handoff. This command imports no startup services before checking package
bytes and does not start workers, create capacity or write a ledger. Production
execution additionally requires independently selected runtime-transition and
finite-provider authority. No customer restart, swap, install or provider work was
selected by that offline qualification. At that point SHOP-04 remained installed;
the later HUNT-08 installation is recorded above.

For disposable engineering qualification, `scripts/qualify_hunter_boundary.py`
accepts an isolated `--python`, exact `--wheel`, `--expected-wheel-sha256`, output,
repeat archives and optional `--test`/`--browser` gates. Its fabricated browser roots
and test-only port adapter never substitute for the production identity. Profile
tests cover normal auth/CSRF, selected routes/workers, exact-plan fake dispatch and
Stop. Operator/transition tests cover pre-start refusal, interruption and latest-state
handback. Ordinary application startup is unchanged outside explicit selection.

On October 17, the owner selected the qualified temporary transition and finite
plan. It returned successfully to ordinary SHOP-04 at the original root/port after
one live Both action (one OAuth/two Browse, all HTTP 200). Browser tab/context loss
prevented the remaining genuine journey; no continuation or lot detail was sent.
The temporary selections are closed and the consumed ledger remains intact.
That execution was partial and did not permanently install Hunter. The subsequent
browser recovery, completion binding and completed bounded genuine gate are
described below; do not restart the completed one-run attempt or reset its
allowance. Historical evidence is under `reports/hunt-07-live-20261017/`.

The subsequent offline browser-recovery pass preserves backend/operator bytes and
repairs only lost 404 status in the Hunter client's non-JSON response handling.
The existing unavailable path can then clear a missing run without acquisition.
Its fresh repeat-built isolated package has a separate identity from the executed
candidate. Follow the [retained-tab procedure](hunter-browser-workflow.md)
for sign-in handoff, renewed per-turn retention, local revalidation and interruption
refusal. Engineering evidence is under `reports/hunt-07-browser-recovery-20261017/`;
real browser observations and simulated cleanup boundaries have distinct scopes.
No customer runtime transition or provider operation occurs in this pass. The
closed original plan cannot be restarted, and the current fixed-plan operator
has a separate reviewed completion binding before any new execution selection.

The narrow `hunt-07-completion-v1` binding preserves the repaired UI and existing
operator architecture. Its package changes only trusted allowance validation,
operator plan/predecessor/authorization checks and profile plan binding. It adds
no startup worker, route or installed capability. The strict plan binds fifteen
additional operations beside the three permanently consumed original operations.
Its exact source/package/runtime/proposal and original unexecuted command are recorded in
`reports/hunt-07-completion-binding-20261017/`; the old frozen candidate remains
unchanged. Use the fresh isolated candidate's hash-pinned bootstrap for read-only
preflight. Preparing/preflighting the proposal creates no actual authorization,
ledger or capacity and does not transition SHOP-04. The later exact selection and
completed execution are separate evidence below; the consumed command cannot be
started again.

### Completed Hunter genuine qualification

The owner selected the exact completion transition and finite plan on October 17.
The retained original browser tab completed one Both Hunt, five explicit Continues,
local lot review and two selected official details. All fifteen operations completed
HTTP 200: one OAuth, twelve Browse and two details. The 2,400 observations yielded
2,391 unique identities, nine duplicates, 800 retained summaries and 1,591 skipped
identities. Every page was advisory-truncated. Results remain a bounded partial
market sample, with no fully comparable offer or complete lot valuation observed.

Local paging/filter/reveal, lot analysis, comparison, Back/focus and reopening added
no acquisition. Actual ambiguous lot contents stayed unresolved; no justified
contents correction was available, so live deliberate correction is unexercised
and retains its separate offline proof. Stop details was clicked from a loading UI
after transport completed; live in-flight Stop suppression is likewise unobserved.
Parent Stop cleared temporary results and reviews before latest-state handback.

The exact ordinary SHOP-04 runtime returned at the existing root and port. Schema,
55 tables, runtime/helper/configuration, protected collection state and source
lifecycle match the fresh baseline. Four authentication/session bookkeeping tables
changed consistently with observed sign-in. The old three operations, journal
prefixes and exhausted HUNT-01 allowance remain preserved; the new fifteen are
permanently consumed. Neither run may restart and no new provider capacity follows.

HUNT-07's bounded genuine gate is complete. Its exact closeout and historical
`HUNT-08-handoff.md` remain under `reports/hunt-07-completion-live-20261017/`.
HUNT-08 subsequently updated the ordinary installed runtime as recorded above;
its separately selected installed allocation supplies no standing future capacity.
Post-execution guide edits are separate from each frozen candidate. Historical
tab-loss cause and missing HUNT-06 start-state/writer evidence remain unresolved;
do not repair those historical limits by restoring older state.
