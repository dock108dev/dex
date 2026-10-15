# Operations

## Existing local installations

Select the installation's private root and start it using [local development](local-development.md#existing-installations). The authenticated server binds to
`127.0.0.1:8011`. Restart after updating its runtime; never seed, initialize or
bootstrap an existing installation again merely to run it.

Stop the app before a data/schema update and back up the complete private root,
including database, secret, photos, provider settings and journals. Preserve file
permissions. Git is not a collection backup. Rehearse unfamiliar imports or rollback on
a copy. Confirm the affected copies, goals and saved lookups afterward. Do not reset
spend reservations or overwrite later writes to recover a failed step; see
[recovery](ERROR_HANDLING.md).

### Source updates and runtime rollback

Keep a compatible previous runtime available before an update. Verify the selected
interpreter and installed package, and use the same private root through ordinary
stop/start. Updating a source checkout does not update a separately installed package.
Observe collection, pending intents, goals, histories and authentication afterward.

Rollback selects a verified compatible previous runtime against the latest root and
current independent registries. Never overlay an older database, authentication state,
journal or reservation record over later writes. If older source cannot interpret
retained intents/schema, leave the latest state intact and rehearse a compatible forward
repair on isolated state. Compatibility with an arbitrary old revision requires its own
evidence. The managed-price backup exclusion and independent revocation/attempt
preservation below apply to runtime updates too.

## Invited accounts and recovery

Local operator commands create private one-use links; they do not send messages:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" invite USERNAME --link-file "$DEX_APP_ROOT/invite-link.txt"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" recovery USERNAME --link-file "$DEX_APP_ROOT/recovery-link.txt"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" revoke USERNAME
```

Set `DEX_APP_ROOT` and `DEX_APP_PYTHON` using the startup instructions first. Choose a
new link filename; the operator refuses overwrite. Links expire after 30 minutes and
must be shared privately. Revocation invalidates account access, sessions and
outstanding links. Separate installations can have independent provider configuration
and storage.

## Optional PostgreSQL/HTTPS profile

The staging profile is implemented separately from local serving. It requires an
operator-managed database, HTTPS origin, proxy trust and separate web/worker processes.
These settings alone do not establish a working hosted deployment.

| Environment variable | Requirement |
| --- | --- |
| `DEX_PROFILE` | `staging` |
| `DATABASE_URL` | PostgreSQL URL |
| `DEX_SECRET_KEY` | Private secret of at least 50 characters |
| `DEX_PUBLIC_ORIGIN` | Exact HTTPS origin without a path |
| `DEX_INGRESS` | `proxy` by default, or `render` with matching provider environment |
| `DEX_PROXY_NETWORKS` | Verified proxy CIDRs for `proxy`; no all-address network |
| `DEX_DATABASE_SSLMODE` | `require` by default or `verify-full`; `disable` only for loopback |

`staging_config.py` validates these settings. Render ingress also requires its service
identity and matching external hostname; do not invent proxy networks. Staging disables
live hunts and CLI recognition. Scanning configuration and reservations persist in the
database.

Inspect operator commands before using a configured staging environment:

```sh
uv run --no-sync python -m pokemon_hunter.beta.deployment --help
```

The operator supports explicit migration/copied import, public catalog publication,
web/worker serving, backup/restore, diagnostics, scan disablement and cleanup. Restore
and cleanup are operational mutations, not startup commands. Backups contain private
state and need restricted storage. Container build inputs are in `deploy/Dockerfile`;
there is no repository-owned registry, Render account, release identity or automatic
publication configuration.

For provider settings use [photo entry](photo-entry.md) and [eBay hunts](hunts.md). For
original-app scheduling use the [watcher guide](legacy-watcher.md).

## Provider configuration and inspection

Configure eBay in the selected server environment or its supported configuration
root, then restart normally if environment values changed. Inspect authenticated
readiness without exporting search history or credentials. A configured status
means credentials are present; it does not establish OAuth success, provider access,
remaining quota or permission to store results. See [eBay hunts](hunts.md#local-provider-settings).

Some price reads perform cleanup. `price_snapshots.current` and `display_current`
can remove expired or withdrawn managed records. For a nonmutating investigation,
use bounded metadata reads and read-only database connections; do not suspend the
ordinary expiry worker or copy removable prices into diagnostic output.

## Snapshot retention and backups

Versioned prices use the explicitly selected local root. Back up protected collection,
goals, authentication and permitted history before updating the ordinary installation.
**Exclude `price-snapshots/` from all backups/exports**, including its staging files and
version fingerprints. Source-specific acquisition staging outside that managed location
is not supported. Do not duplicate a removable package or retain its values in logs,
reports, exports or screenshots. Immutable saves require independently reviewed
surviving rights; otherwise current display/arithmetic can work while saving is refused.

The random-version revocation registry lives in `.dex-price-revocations/` beside the
application root and remains outside app restore. Preserve it independently; do not
replace it with an old backup. Restored expired/revoked packages are excluded and
managed copies removed before use. An active release without its independent registry or
version manifest fails closed. No historical guide or existing comparison is purged.

The one-second worker runs while serving; access/startup also checks expiry. These
mechanisms qualify managed application files, not stopped-Mac deletion deadlines,
external exports, filesystem snapshots or complete OS/browser-cache erasure. Qualify an
actual source's copy/deletion obligations before admission; unsupported obligations
require their own repair. Revoke/remove every affected release on a source restriction.
[Price snapshots](price-snapshots.md) documents the current importer and operator
commands. Check the selected root's admitted source contracts and active release for
coverage; test fixtures do not describe a personal installation.

V2 source records and their price fingerprints are independently removable within one
release. Its descriptor keeps only non-price identities. Preserve the additional
`*-sources.json` registry beside the existing version revocations. Use `price-remove-
source --contract-sha256 DIGEST` to withdraw a source across releases; do not restore
its old registry or price fingerprints. This does not delete permitted independent
sources or rewrite immutable history. Restricted sources, including retained conflicts,
cannot enter new permanent saves. The approved TCGCSV raw build date exception concerns
reference age, not storage rights. Exact provider retention obligations and collector
limits still require source qualification before acquisition.

The separate group-metadata collector retains one private canonical metadata file and a
noncontent publisher journal outside the existing installation. It supplies no price or
product access. Preserve `.dex-tcgcsv-metadata/attempts.json` independently; never
restore/reset it to renew an attempt. Source response/error bodies are not retained in
logs, reports, exports or packages. Failure/Stop deletes managed metadata body copies
and leaves consumption intact. Owner Stop also removes a completed managed metadata
result. Cleanup requires a running operator/OS; interrupted supervisors leave consumed
state and possibly a pending validated copy for cleanup after the self-bounded child
exits. No automatic retry is permitted.

## Recorded local delivery

The latest retained installation record is the October 14 scoped-completion delivery,
with the compact card page, grouped navigation, card references, numeric ordering and
explicit finite collection defaults. Genuine Safari exercised browsing and return/
cancel flows on the existing collection. The recorded update preserved protected
collection, goals, photos, credentials, journals and independent source registries;
ordinary sign-in changed authentication activity only. See [verification scope](CI.md#recorded-verification)
and the optional [local delivery record](../reports/ux-03-20261014/closeout.md).

This is a dated record, not a current process check. Later interface and authority
changes exist in source without a recorded replacement of that installed runtime.
Before another delivery or walkthrough, verify the root, interpreter and listener
from the installation's local instructions. Follow the runtime-update and recovery
procedure above against the latest state. Never reuse a historical PID as authority
or restore an old database over later activity. Owner acceptance remains unrecorded.

## Existing eBay setup prerequisite

The October 15 local investigation observed enabled/unconfigured/Production after
ordinary sign-in. At least one required credential was missing; no credential value
was inspected. The installed configuration directory was independent of the private
root and checkout. The ordinary developer portal was signed out, so the selected
existing application's nonsecret Production-keyset/Browse association could not be
verified. Setup stopped before provisioning or interrupting the app. OAuth, searches,
item details, quota requests and price acquisition were not performed. The optional
[setup record](../reports/shop-01b-20261015/closeout.md) describes that observation;
current readiness must be checked again before operational work.

To resume the already selected setup, the owner privately opens the existing access
record with credential fields hidden. Verify the application/environment association
and the available access, allowance and usage facts without retrieving secret values.
A valid keyset is not proof of every downstream workflow right.

Before stopping the app, establish owner availability at a trusted private terminal,
the supported launch context, same-runtime recovery, startup queues and a finite
interruption window. Quiesce normally; back up protected state with the managed-price
exclusion and independent-registry preservation above. The owner supplies the existing
matching pair through hidden input into the ordinary server environment. Do not copy
checkout credentials or store secret literals in arguments, logs or runtime files.
Verify local configured status after normal startup; it does not authenticate remotely.

For recovery, use the verified compatible runtime and latest same root with newly
supplied eBay inputs omitted. Preserve current authentication and independent journals.
Process-environment credentials need secure input again on later launches unless an
established secret manager is separately selected. The optional [operational template](../reports/shop-01a-20261015/next-handoff.md)
contains the original hidden-input procedure; verify its historical paths before use.
The current search workflow still lacks an independent Stop/consumed-attempt boundary,
so setup alone does not make it suitable for a tiny access probe.
