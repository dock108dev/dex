# Operations

These procedures use the existing private installation. Set its root and compatible
interpreter as described in [local development](local-development.md#existing-installations).
Operator commands can change accounts, schemas or retained data; they are not
ordinary startup steps. Git and collection exports are not complete backups.

## Existing local installations

Use the recorded installation runtime to serve on `127.0.0.1:8011`; reuse an
already running process. Initialization refuses existing roots and is never a
repair for missing personal data. Preserve the authentication secret and session
identity during compatible updates. Do not reseed or replace the user's root.

Local sessions persist for 30 days and renew at most hourly during successful
authenticated visits. Browser restart does not guarantee a temporary Hunt survives:
its lease and in-memory results are separate from sign-in. Logout is a POST action;
expiry, revocation and recovery-link reissue invalidate access.

## Runtime updates and recovery

Keep the private data root separate from the selected installed runtime. Configure
startup through [local development](local-development.md#existing-installations).
Changing a checkout environment does not update an installed application.

Before a compatible runtime update, stop the existing server and back up protected
state as described below. Retain the previous interpreter for rollback. Runtime
rollback uses current compatible data; never restore older independent acquisition
journals, revocations or reservations to regain capacity. Schema changes need their
own migration/restore procedure and are not ordinary startup steps.

## Everyday Hunter policy

An owner selects enabled/paused state, per-Hunt and shared daily limits, timezone,
recurrence and expiry through **Hunter → Usage settings**. Numeric validation
ceilings are not default capacity. Local inspection and filtering do not acquire
provider data. OAuth, Browse and explicitly selected details count before dispatch;
failed, stopped and uncertain requests remain consumed.

`beta/hunter_policy.py` owns append-only usage accounting in
`ROOT.parent/.dex-shopping-discovery/<root-path-sha256>/everyday/`, beside the
private root rather than inside it. Selection, parent capture and admission share
an installation lock; fsync precedes provider I/O. Pause, expiry, reduced limits,
clock rollback, corrupt accounting and package mismatch block further acquisition.
Timezone edits preserve prior usage conservatively. Daily renewal requires explicit
recurrence. Do not edit journals or restore old policy/accounting files to regain capacity.

Package changes can require an explicit compatible package binding. Inspect the
policy and operator implementation before updating; restarting never grants a new
allowance. Fixed qualification/installed allowances have separate identities and
ledgers. Their unused numeric slots are not everyday capacity and cannot be refunded,
renamed or reset. See [Shopping](hunts.md).

## Invited accounts and recovery

The local operator creates one-use links without sending messages:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" invite USERNAME --link-file "$DEX_APP_ROOT/invite-link.txt"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" recovery USERNAME --link-file "$DEX_APP_ROOT/recovery-link.txt"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" revoke USERNAME
```

Choose a new private link filename; overwrite is refused. Deliver it privately
before its 30-minute expiry. Revocation invalidates account access, sessions and
outstanding links. Never put passwords or recovery links in shared logs.

## Optional PostgreSQL/HTTPS profile

Staging requires an operator-managed PostgreSQL database, HTTPS origin, explicit
proxy trust and separate web/worker processes. Configuration is validated by
`beta/staging_config.py`:

| Variable | Requirement |
| --- | --- |
| `DEX_PROFILE` | `staging` |
| `DATABASE_URL` | PostgreSQL URL |
| `DEX_SECRET_KEY` | Private secret, at least 50 characters |
| `DEX_PUBLIC_ORIGIN` | Exact HTTPS origin without a path |
| `DEX_INGRESS` | `proxy` or `render` with matching provider service environment |
| `DEX_PROXY_NETWORKS` | Verified CIDRs for proxy ingress; never all-address networks |
| `DEX_DATABASE_SSLMODE` | `require` or `verify-full`; `disable` only on loopback |

Staging disables live Shopping acquisition and CLI recognition. Its scan settings
and reservations persist in PostgreSQL. Inspect the deployment operator first:

```sh
uv run --no-sync python -m pokemon_hunter.beta.deployment --help
```

Copied import requires an empty target, a `.copied.sqlite3` backup and complete
`.scan-config.json` sidecar. Restore also requires an empty target. Deployment supports
explicit migration/import, catalog publication, backup/restore, web/worker serving,
diagnostics and cleanup. These are mutations, not health checks. Container inputs
are in `deploy/Dockerfile`; CI does not publish or deploy the image.

## Provider configuration and inspection

Configure eBay in the selected server's environment/configuration directory.
Nonempty process values override `.env`. Readiness checks configuration without a
request; it does not prove remote entitlement, quota or storage rights. See
[Shopping](hunts.md#local-provider-settings) and [recognition](photo-entry.md#provider-configuration).

Reference import has no acquisition or activation default. Retained feeds, reviewed
bindings and prepared releases belong in managed private staging. See
[price snapshots](price-snapshots.md). Some price reads, including `current` and
`display_current`, can prune expired/withdrawn files. Use bounded metadata reads and
read-only database connections when an investigation must not mutate state.

## Snapshot retention and backups

Back up the protected database, authentication secret, photos, configuration,
drafts and permitted history before data-changing updates. A copy/goal export
cannot restore complete account, journal or replay state. Preserve independent
journals separately from app restore, including acquisition reservations and
uncertain attempts.

Exclude the entire managed `price-snapshots/` tree, including staging, source shards
and fingerprints, from backups/exports. Do not copy removable values into logs,
screenshots or diagnostic reports. Permanent saved research requires independent
surviving rights for every included source.

Keep the independent `.dex-price-revocations/` directory and source registries
outside app restore. Never replace them with older backups. Missing registries or
version manifests fail closed; restored revoked/expired packages cannot regain
eligibility. The expiry worker, startup and access checks enforce lifecycle while
the app runs. They cannot erase external copies or guarantee deletion while the
machine is stopped. See [source withdrawal](price-snapshots.md#contracts-and-lifecycle).

Preserve `.dex-shopping-discovery`, `.dex-tcgcsv-snapshots` and
`.dex-tcgcsv-metadata` accounting independently. App restore, failure, Stop and
renaming a selection do not renew consumed provider capacity. Raw capture cleanup
must keep noncontent reservation history.

Photo-batch admissions, consumed attempts and deletion tombstones are also outside
the root in `ROOT.parent/.dex-photo-batches/<root-path-sha256>/journal.jsonl`.
Preserve that journal independently and reapply its current state during recovery;
a backup of the customer directory alone cannot preserve these protections.

## Shopping discovery

Named Search/More and explicitly selected details are acquisition actions. Each
named action uses at most one OAuth and one Browse, 20 summaries, 30-second requests
and a 75-second action deadline; a named run ends after four Browse pages total
without renewing its original content lease. Both alternates captured category lanes
within this same total. Unknown/malformed totals end a lane; errors end continuation.
Blank-text catalog batches retain their stricter existing ceilings. Reveal remains
a local compatibility operation; results and reviews are visible without it. Reveal,
local pages, comparisons, Back and reopening make no provider request. Temporary
results, references and derived amounts stay out of persistent exports and browser
storage. Use Stop for active work; do not retry uncertain transport automatically.
An unavailable session is not a successful empty search.

## Manual bulk entry and recovery

Enable bulk capability only through the explicit operator on a compatible root.
Do not rerun schema enablement for ordinary startup. Drafts, replay aliases and
confirmed receipts are durable; inspect the existing receipt after an uncertain
confirmation. Changed input or a genuinely new physical batch requires its explicit
identity. `bulk-cleanup` expires drafts without refunding or replaying mutations.
See [bulk semantics](effective-collection.md#manual-bulk-entry).

## Photo-batch recovery

`enable-photo-batches` is explicit schema enablement. Admission, provider reservations,
Stop, crop deletion and confirmation use durable jobs and tombstones. Preserve them
with drafts and collection state. `photo-batch-cleanup` performs explicit cleanup;
never reset reservations to retry an uncertain model request. The worker and access
paths enforce image lifetime; hard termination may leave private temporary files.
See [photo storage](photo-entry.md#storage-and-shared-review) and
[failure handling](ERROR_HANDLING.md).


## Startup and read diagnostics

The local runtime provides bounded, sanitized request timing and useful
startup/readiness diagnostics. Existing error logging is described in
[recovery](ERROR_HANDLING.md#diagnostics); request timing and derived-index recovery
are implemented by the runtime described below. Do not enable raw access logging
that exposes setup links, search text, credentials or private records.

Readiness signals distinguish process listening, application readiness and
usable catalog reads; document startup time and failures. Browsing must not start
acquisition, recognition, schema migration or catalog rebuilding. Necessary derived
state updates need a versioned, atomic preparation/activation path, bounded recovery
and failure reporting. Local startup must preserve ordinary login and existing
worker/Stop policies. Select concurrency changes only after profiling contention;
additional processes must not duplicate workers or weaken accounting/lease ownership.

Before installing any schema/index change, supply its explicit migration and rollback
compatibility procedure and follow protected-state backups. Validate restart and
recovery in engineering isolation, then verify ordinary startup and read-only browsing
on the actual installation. A code rollback uses current authoritative data and
independent journals; an old cache or backup must never restore revoked data or capacity.

## Derived-state lifecycle

See the [read architecture](card-groups.md#read-architecture) and
[fixed budgets](CI.md#performance-budgets).

An explicit preparation command builds candidate catalog/overlay rows with a unique
build ID, schema/policy keys, authority revisions, counts and content checksum.
Read authority under a consistent database snapshot; do not hold a write lock for
all CPU preparation. Persist candidate rows in bounded transactions. Validate identity,
counts, public allowlists and checksum, then atomically compare the source revision
and switch the active manifest in one short transaction. A changed source rejects
activation. Preserve the prior build until all readers release it; cleanup is explicit.
Never mark a partly prepared build ready. A crash before activation leaves the prior
compatible revision active only if authority still matches; a crash after commit
uses the new manifest. Old authority is never restored to make an index appear valid.

Publication/collection writes advance authoritative revisions transactionally.
A candidate may be prepared before a reviewed publication and activated with it,
provided the compare-and-swap includes the publication's complete expected changes.
Withdrawal takes effect immediately: if replacement preparation fails, affected reads
return an explicit unavailable response instead of old published content. Changes
cannot wait for a TTL. Collection confirmation receipts remain authoritative even
when overlay preparation fails; recovery reconstructs derived state from those receipts.

On ordinary startup, validate schema/policy/authority keys, manifest completeness
and bounded integrity metadata, then reuse compatible derived tables. Do not replay
the entire catalog or account journal at launch. Validate row/page integrity when
read; explicit preparation performs the full checksum/integrity scan. A missing,
corrupt, interrupted or incompatible build produces readiness failure within two
seconds and a fixed repair code. It does not trigger a migration, reseed, provider
call or synchronous rebuild from a browsing GET. The operator's explicit local
repair has a 30-second full-catalog preparation budget on the qualification machine;
report a miss rather than extending startup silently. Recovery tests must distinguish
unsupported schema from data corruption and never delete authority or accounting.

Expose separate liveness and readiness. A listener is not proof that browsing is
ready. Readiness checks active catalog and required account overlay keys without
returning private data; authenticated recovery detail reauthorizes the account.
Return 503 with a fixed `read_state_unavailable` code and bounded retry advice for
unavailable V2 derived state. A supplied stale revision is 409, not 503. The frontend
keeps valid context and offers explicit recovery instead of an endless spinner.

The additive migration creates derived tables, manifests, catalog revision and
account read-revision rows and revision triggers. Run it only through an explicit reviewed maintenance command
with the documented protected-state backup and rollback procedure. Startup and reads never migrate. Older code may ignore additive tables; triggers must still
invalidate newer derived state if older code writes authority. Reuse only compatible
schema versions after returning to a newer runtime. Never roll back collections,
secrets, consumed usage, Stop decisions, tombstones or source revocations. Keep old
runtime selection available, but do not equate its slower V1 reads with readiness
of the new version. PostgreSQL support requires equivalent atomicity and trigger
qualification before claiming compatibility.

Diagnostics contain route templates (never raw URLs/query strings), status, build
schema, hit/miss/unavailable reason, elapsed/query/fetch/projection/serialization
milliseconds, query and decoded-row counts, payload byte count, and startup phase.
Use a per-request random diagnostic ID; omit account IDs, record bodies, SQL
parameters, credential/session values, artwork URLs and provider content. Aggregate
by guest/member and operation type. Bound log size/retention and keep private raw
measurement files outside Git. Instrument SQL fetch separately from execute; cursor
execute time alone misses row materialization. Do not introduce duplicate recognition,
expiry or acquisition workers as a response to slow CPU projection.

Before a controlled customer restart, inspect durable queued/processing jobs and
active acquisition leases, and establish whether in-memory Shopping work must be
preserved. Durable job absence alone cannot establish that all temporary reviews are
safe to discard. Reuse the exact installed interpreter/root/ordinary startup command;
measure process spawn, listening, readiness and first usable page independently.

## Read-schema maintenance

These SQLite-only maintenance commands require a protected-state backup and a
compatible runtime. Require the
existing catalog, collection and declaration schemas. A subsequently installed
catalog-pipeline schema requires re-running the read migration to install its revision
backstop; that transition invalidates older prepared state.

Use the selected compatible installed interpreter and the existing private root:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" migrate
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" prepare
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" activate --build BUILD_ID
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" status
```

`prepare` returns the candidate build ID and does not activate it. It reads a
consistent authoritative snapshot, releases that transaction, computes typed rows,
persists bounded batches, builds/checks the gram index and validates counts, digests,
identity and allowlists. Candidate states are preparing, indexing and validated;
only atomic activation makes a candidate ready. A failed comparison means authority
changed: prepare a new candidate; never force an old revision current. A partial
candidate is not resumable or browseable. Preparation does not modify catalog,
collection, credentials, acquisition accounting or provider state.

Ordinary reads validate schema/policy/revision, trigger infrastructure and the active
sealed manifest and per-build FTS document count. Expanded metadata verifies its row digest. Missing/incompatible/corrupt
state fails explicitly; browsing never repairs it. Full candidate checksum and FTS
integrity validation remain explicit maintenance work, not a startup full scan.
Physical SQLite damage can require normal database recovery; do not mistake a
read-model rebuild for repair of damaged authoritative records.

After readers have switched, the operator can explicitly reclaim an inactive build:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" discard --build OLD_BUILD_ID
```

The active build cannot be discarded. SQLite read transactions retain their snapshot
when inactive rows are deleted (including WAL readers); rollback-journal locking
also prevents reclaiming data underneath a read. Do not discard a candidate while
another preparation process is still writing it. Interrupted candidates can be
explicitly discarded after the writer has stopped. No automatic cleanup runs on GET.

Rollback means selecting the compatible previous runtime, leaving authoritative data
and additive read tables/triggers intact. Older code can continue V1 reads; its
catalog/source/copy writes still invalidate newer prepared state through triggers.
Returning to newer code requires compatible schema/policy and a current revision.
Do not restore old collections, accounting, secrets, revocations, tombstones or Stop
choices to make a derived index appear valid. The runtime provides scoped
readiness, startup validation and bounded timing diagnostics; see the contracts below.

### Explicit derived-state repair

For a damaged FTS index whose external-content records and authority remain intact:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" repair-index
```

This invalidates ready/validated manifests, rebuilds and integrity-checks the FTS
index, and leaves preparation/activation explicit. For missing derived tables or
revision triggers under the same supported schema version:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" repair-schema
```

This transaction recreates only read-model infrastructure, retains account read
revision values and advances the catalog revision. It discards derived candidates,
not catalog/collection authority. It requires the existing catalog revision and
supported schema marker; missing authority revision or an incompatible schema needs
an explicit version transition/database recovery, not a reset. After either repair,
prepare and activate a new candidate and check status before serving V2.

Normal derived-row changes invalidate their ready/validated manifest through
triggers. Full checksums and FTS integrity are checked during explicit validation;
ordinary reads do not promise detection of every possible manual shadow-table or
physical database alteration. A missing FTS document set is rejected by the read
check. Do not write FTS shadow tables or add triggers to them: a development attempt
to do so caused SQLite re-entrant FTS failure and was removed. Use the supported FTS
commands and explicit repair paths above. Failed repair leaves the transaction
rolled back and does not authorize serving known damaged state.

## Account-read lifecycle

[Account reads](account-reads.md#preparation-and-recovery) documents
explicit migrate/prepare/status/discard/repair commands and catalog-before-account
ordering. Use them only during deliberate maintenance, following the backup/runtime
procedures above. A 503 is an unavailable read representation, never a reason to replay a
confirmed operation or reset authoritative collection data.

## Readiness signals

The runtime exposes these read-only signals:

| Signal | Meaning | Failure |
| --- | --- | --- |
| `GET /livez/` | HTTP request handling is alive; no database readiness assertion | Does not certify catalog, account or browser |
| `GET /readyz/` | Shared catalog schema, required object names/types, revision triggers, active manifest seal/policy/revision and FTS document count pass | 503 with `read_state_unavailable`, fixed `category` and explicit `recovery` |
| `GET /api/v2/readiness/` | Same catalog checks plus the signed-in account's schema/infrastructure, manifest seal, generation/revision and representation policy | 403 without current authorization; otherwise scoped 503 |
| Rendered primary cards and usable controls | Browser usability, measured independently | Backend 200 or HTML shell is insufficient |

All signals use no-store. Public results contain no account identifiers, build IDs,
configuration or record content. Account readiness derives its principal exclusively
from the authenticated session and independently rechecks it. `X-Dex-Read-Account`
is an optional mismatch guard, never an account selector. Existing V2 stale-selector
409 behavior remains in the resource APIs. Readiness URLs take no account selector;
use resource APIs for revision-bound reads. Staging's existing `/healthz/` remains
its separate worker-heartbeat contract; it is not local catalog readiness.

The ASGI factory validates once before ordinary CLI worker startup. SQLite checks
use a 500 ms VM progress deadline and 100 ms busy timeout, restoring the connection's
settings afterward. The connection closes after startup validation. A failed derived
check leaves sign-in, recovery guidance and read-only signals available. Resource GETs
still recheck current authority; startup success is not a permanent cached assertion.
No account enumeration, full journal replay, migration, preparation or cleanup occurs
in validation. Metadata and indexed document counts are checked; this is not a full
physical SQLite integrity scan. Payload checks remain at read time, full checksums at
explicit preparation. Do not interpret readiness as proof against arbitrary disk damage
or manual modification of SQLite shadow tables/trigger definitions.

### Failure categories and explicit actions

| Category | Action |
| --- | --- |
| `schema_missing` | Inspect the supported schema prerequisites, then explicit `migrate`; prepare separately |
| `incompatible_schema` | Select a compatible runtime/version transition; never reset a schema marker |
| `incompatible_policy`, `catalog_stale` | Prepare a new catalog candidate, then activate after its revision comparison |
| `manifest_missing` | Explicit catalog preparation and activation |
| `preparation_interrupted` | Stop/identify the interrupted writer; prepare a fresh candidate; only then activate and explicitly discard the abandoned candidate |
| `manifest_corrupt`, `derived_corrupt` | Preserve authority; prepare a new candidate, or use supported derived repair if infrastructure/index damage is established |
| `infrastructure_missing` | Explicit supported derived-schema repair, then preparation; incompatible/missing authority revisions require separate recovery |
| `account_not_prepared`, `account_stale`, `account_corrupt` | Prepare the named account from current authority; never resubmit a confirmed mutation |
| `account_policy_incompatible` | Explicit account preparation for `effective-collection-2-goal-headers` |
| `check_deadline` | Inspect contention, storage and startup diagnostics; no automatic maintenance/retry |
| `storage_unavailable` | Preserve database and independent journals; investigate authoritative SQLite damage/permissions separately |
| `unsupported_database`, `publication_capability_unavailable` | Select a qualified runtime/capability configuration |

A SQLite read error is not evidence that only derived data is damaged. Index rebuilding
cannot repair damaged authoritative rows. Existing raw-data backups are disaster-recovery
inputs, not permission to roll back live accounting, revocations or collection generations.

### Preparation and repair commands

After selecting the compatible installed interpreter and
backing up protected state, use this order (these commands were not run on the customer):

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" migrate
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.account_read_operator --root "$DEX_APP_ROOT" migrate
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" prepare
# Set DEX_CATALOG_BUILD to the build returned by prepare; do not use an older build.
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" activate --build "$DEX_CATALOG_BUILD"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" status
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.account_read_operator --root "$DEX_APP_ROOT" --username "$DEX_ACCOUNT_USERNAME" prepare
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.account_read_operator --root "$DEX_APP_ROOT" --username "$DEX_ACCOUNT_USERNAME" status
```

Status exits nonzero when unavailable and emits a fixed safe recovery category.
Catalog ready status retains its operator-only build/revision fields. Failed commands
emit sanitized code locations, not exception bodies. Full-catalog and whole-account
preparation durations are separate; preparing the catalog does not finish account recovery.
The new account policy deliberately invalidates previous goal-header representations.
Older runtimes may read additive tables or write authority, but their writes still advance
revision triggers; returning to this runtime requires current compatible preparation.

For established FTS-only damage, `catalog_read_operator ... repair-index` invalidates
candidates and rebuilds the search index; next prepare/activate, then prepare accounts.
For missing/damaged derived schema under the supported version:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.catalog_read_operator --root "$DEX_APP_ROOT" repair-schema
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.account_read_operator --root "$DEX_APP_ROOT" repair-schema
```

**Both repairs are required after catalog schema repair**: catalog-table replacement
removes indexes installed by the account migration. Then prepare/activate the catalog
and prepare each intended account explicitly. Account-only corruption may instead use
`account_read_operator ... --username "$DEX_ACCOUNT_USERNAME" discard` and `prepare`;
all-account schema repair is not the default response to one unavailable account.
A failed build never becomes active; revision mismatch cannot be forced current.
Activation/cleanup retain existing snapshot guarantees. Confirmed collection receipts
remain authoritative when read refresh fails; preparation reconstructs from current data
without replaying the mutation or receipt.

### Serving, connection and worker policy

Use one ordinary CLI process, with no reload or multiprocess workers. The ASGI wrapper
admits one legacy dynamic request and reserves one additional lane for bounded
browsing GETs (V2 reads except resources, card/Pokédex shells and readiness).
Mutations and legacy collection, Shopping and Hunter reads cannot enter the browsing
lane. Both lanes have capacity one; total dynamic concurrency is capped at two.
This rc5 policy prevents an expensive legacy comparison refresh from refusing a
card navigation. The fixed `/collection-assets/`
file-serving route has a separate four-slot lane; it never opens a catalog snapshot.
This prevents script/style delivery waiting behind the data slot. Admission waits at most 500 ms, then
returns `503 {"error":"runtime_busy"}` without invoking Django. `Server-Timing: admission`
reports that wait on admitted responses. It does not measure time before the ASGI call,
TCP backlog, browser scheduling, or paint. Cancellation always releases the slot.

Django's zero persistent-connection setting closes request connections. Each catalog
connection retains its existing 64 MiB SQLite page-cache ceiling: at most 64 MiB for
each admitted catalog request (up to 128 MiB across both dynamic lanes).
This is a page-cache allowance, not an RSS ceiling:
Python heaps, SQLite temporary sorting (`temp_store=MEMORY`), sockets, assets and the
existing cleanup-worker connections need additional memory. Do not multiply processes
or assume the cache is always resident. Actual RSS and concurrent timings belong
in measurements for the selected runtime. No additional acquisition/recognition worker is started.

The existing expiry thread and selected-current-process photo worker retain their
selection, leases and Stop behavior. Startup validates before starting them. Shutdown
uses ASGI lifespan shutdown to signal both stop events and join each for up to five
seconds before Uvicorn restores/re-raises signals; an idempotent CLI fallback handles
ordinary exceptions. Incomplete joins emit
the existing fixed failure event. `shutdown/workers_joined` reports whether both joined.
Uvicorn may re-raise SIGTERM after orderly cleanup; signal exit alone is not proof of
worker failure or provider cancellation. Preserve pending work and current independent
accounting before any actual installation restart.

### Bounded request diagnostics

Ordinary CLI startup creates private `diagnostics/reads.jsonl` under the chosen root.
It is size-retained: 1 MiB per file and two rotations (approximately 3 MiB total),
0600 files in a 0700 directory. At most 60 records/minute are persisted; excess records
are dropped, not queued. A separate in-memory ring holds the latest 256 records. There
is no promise that every request ID appears in retained logs, nor time-based archival.
Do not export logs indefinitely or turn on raw web access logging. Existing sanitized
`dex.failures` stderr diagnostics remain separate from this request store.

Each Django-dispatched request has a random `X-Dex-Diagnostic-ID`. Pre-dispatch
ingress/body/admission refusals do not pass through this middleware and have no
SQL/decoder diagnostic record. Records include the Django route
**template**, status, elapsed milliseconds, expected schema/policy, catalog/account
check category, SQL execute and fetch milliseconds separately, query/fetched-row counts,
decoded-row count, service time, measured decoding/composition time, JSON serialization
time and payload bytes. No URLs, query strings, SQL text/parameters, account IDs,
credentials, sessions, records, artwork URLs or provider bodies are recorded.

Fetch timing wraps request cursors, including ORM fetches. Decoded counts/composition
cover the instrumented public/private payload decoders, not every arbitrary JSON call;
the count includes attempted decoder calls on failed reads. Query count is cursor
execution calls (ordinary read queries are individual calls, not batched statements);
`decoded_coverage` labels that limit. `null` means unavailable/not measured. Service
elapsed includes SQL and composition, so these overlapping totals must not be added.
Request elapsed excludes admission, network and browser scheduling. Streaming payload
size is unavailable. `not_checked` differs from `ready`; an HTML shell is never assigned
catalog/account readiness merely because it returned 200.

For slow startup, correlate `startup/catalog_validation` with an external spawn timer
and separately probe liveness/readiness. For slow reads, use the response diagnostic ID,
route template and execute/fetch/serialization durations; compare admission timing and
browser resource/paint measurements rather than attributing the whole gap to SQL. For
unavailable reads, inspect scoped readiness, apply the explicit action, then check again.
The frontend retains its existing visible 503/manual-recovery text and confirmed receipt
recovery; it does not prepare, automatically retry, poll readiness or fall back to V1.
The macOS launcher still detects a listener only. Operators must verify its process/root
and `/readyz/`; launching/opening a page is not a readiness assertion.

The OPS runtime investigation identified duplicate FTS membership evaluation in owned
search (one evaluation for count and another for page selection). Exact totals retain
the complete posting-list check; page selection uses compact common text and only
same-child/substring residual ranks, following the existing catalog search strategy.
It preserves ordering, child semantics and empty/deep pages without reconstructing
ownership or decoding the whole matching catalog. Owned search is now explicitly
qualified alongside catalog search. Four simultaneous Django requests increased SQL
wall time beyond its fixed budget. The original single admission slot bounded that
contention, but installed QA later exposed legacy Hunter refresh blocking browsing.
The rc5 reserved browsing lane above supersedes that policy. Four-client load and
actual legacy-read overlap are recorded in [installed QA](installed-qa-20261029.md);
queue time remains separate from application time.

## Package binding and schema compatibility

`hunter_installed.package_digest()` hashes installed application members, not the
wheel archive. Existing everyday Hunter policy can be rebound with the privileged
`hunter_policy.rebind_package(root, expected_previous=..., package_sha256=...,
contract='hunt-09-daily-v1')` only when the current binding and acquisition contract
match. The appended event preserves policy revisions, parent IDs, debits, expiry
and Stop choices. Never rewrite fixed allowances to renew consumed capacity.

Account storage schema 2 adds a bounded display index; see
[the account guide](account-reads.md#account-storage-schema-2). Stop the server,
back up the database, run the selected runtime's account `migrate` command, and
check readiness before restarting. Valid prepared rows and seals are preserved.
Older runtimes expecting schema 1 are not compatible without an explicit reviewed
schema transition. Do not restore older collections or independent journals as a
shortcut to code rollback.
