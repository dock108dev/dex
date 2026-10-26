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
