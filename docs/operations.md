# Operations

## Existing local installations

Select the installation's private root and start it using [local development](local-
development.md#existing-installations). The authenticated server binds to
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
