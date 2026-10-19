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

## Everyday Hunter policy

An owner selects enabled/paused state, per-Hunt and shared daily limits, timezone,
recurrence and expiry through **Hunter → Usage settings**. Numeric validation
ceilings are not default capacity. Local inspection and filtering do not acquire
provider data. OAuth, Browse and explicitly selected details count before dispatch;
failed, stopped and uncertain requests remain consumed.

`beta/hunter_policy.py` owns append-only usage accounting under the root's independent
`.dex-shopping-discovery` directory. Selection, parent capture and admission share
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

## Shopping discovery

Search, Continue and explicitly selected details are acquisition actions. Reveal,
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

## Deferred — resume only on later owner direction

Imported from the Desktop tracker during the October 18 documentation cleanup.
This is a historical closeout/decision, not a fresh verification. The active
Shopping repair in [Shopping](hunts.md#active-owner-direction--shopping-repair-first-october-18-2026)
and the Desktop Next Steps plan govern current work. Historical next actions below
do not reactivate deferred work or establish installed delivery.

- **Real data pipelines and further reference acquisition/refresh automation**,
  source integration/operationalization, sold-history capability and HUNT-12.
- **REFERENCE-R3/RESIDUAL-1 and coverage/identity expansion:** the 319 unpriced
  children, two S6 missing prices, 13,399 unpriced parents and retained
  edition/denominator/physical/product holds remain recorded limitations. Their
  ledgers are preserved, not an active engineering queue. No target coverage
  percentage remains to be achieved for beta.
- **Catalog policy/remainder:** Detective Pikachu, Generations aliases and other
  retained-source/physical/catalog gaps. No new catalog campaign for this beta.
- **Photo onboarding and recognition expansion:** ON-02/D3 and ON-02/DEL remain
  owner-deferred. Revisit relevant model lifecycle facts when that work resumes or
  if an actually used recognition feature needs maintenance; historical notices
  are not treated as current verified facts.
- **Graded/sold-price modeling, resale EV, other games/countries and broader
  product expansion**, unattended Hunts/notifications and public/hosted release.
- Historical full collection/Shopping/photo combined-delivery and full-goal
  acceptance branches remain separate from the narrower current beta scope.

None of these deferred items blocks use or evaluation of the selected current beta.
A future resumption starts from actual latest state and preserved source rights,
reservations and histories, without resetting or replaying consumed selections.

## Operating rules for the active beta

Imported from the Desktop tracker during the October 18 documentation cleanup.
This is a historical closeout/decision, not a fresh verification. The active
Shopping repair in [Shopping](hunts.md#active-owner-direction--shopping-repair-first-october-18-2026)
and the Desktop Next Steps plan govern current work. Historical next actions below
do not reactivate deferred work or establish installed delivery.

Use the ordinary installation and real current state for interactive work. Preserve
customer data and any existing authenticated session; never reseed or substitute
a copied/synthetic customer installation. Keep reference dates, conditional market
meaning, missing prices, unknown costs and partial lot coverage honest.

The recorded batch-1 supplemental full-source check sequencing deviation remains
in the delivered closeout. It passed; it does not create a new coverage campaign.
Future relevant admission changes must put complete checks before activation.

Update only the selected beta work and fix observed issues. No automatic residual
repair, pipeline work, acquisition, schedules, purchase/bid or deployment is selected.

Pre-scope tracker archive: `reports/reference-r3-acquire1-20261018/tracker-before-beta-scope.md`
retains the earlier full backlog and historical evidence. The owner's current scope
above replaces its active priorities; historical next handoffs are not instructions
to resume deferred work. Repository operating guides were updated before this tracker.
