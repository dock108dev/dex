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


## Next-version startup and read diagnostics

The responsive local version requires bounded, sanitized request timing and useful
startup/readiness diagnostics. Existing error logging is described in
[recovery](ERROR_HANDLING.md#diagnostics); request timing and derived-index recovery
are not yet established operating capabilities. Do not enable raw access logging
that exposes setup links, search text, credentials or private records.

The implementation must distinguish process listening, application readiness and
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

## PERF-01 derived-state lifecycle

This is a required design for OPS-READINESS; the current installed app does not
implement it. Use the [read architecture](card-groups.md#perf-01-read-architecture-contract)
and [fixed budgets](CI.md#perf-01-performance-budgets).

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
with the documented protected-state backup and rollback procedure. No migration is
performed in PERF-01. Older code may ignore additive tables; triggers must still
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

## PERF-02 read-schema maintenance

The new source provides explicit SQLite-only maintenance primitives. They have not
been applied to the customer installation. Follow the protected-state backup and
runtime-selection procedure above before a later authorized delivery. Require the
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
choices to make a derived index appear valid. Full readiness endpoints, startup
orchestration and bounded sanitized request diagnostics remain OPS-READINESS work.

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
