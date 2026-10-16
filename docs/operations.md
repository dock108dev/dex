# Operations

## Existing local installations

Select the existing private root and installed interpreter using
[local development](local-development.md#existing-installations). The authenticated
server binds to `127.0.0.1:8011`. Verify the current process, interpreter and root before
an update; restart normally afterward. Initialization and bootstrap are not startup
commands. The repository does not install a managed service for the authenticated app.

### Source updates and runtime rollback

Stop the app before a data/schema update. Preserve a compatible previous runtime,
back up protected state under the exclusions below, and retain file permissions.
Updating a checkout does not update a separately installed package.

Runtime rollback uses a verified compatible interpreter against the latest root and
current independent registries. Never overlay an older database, authentication state,
journal or reservation record over later writes. If older code cannot interpret the
retained schema or operations, preserve the latest state and repair forward using a
copy first. Check collection, goals, drafts, histories and authentication after restart.
[Failure recovery](ERROR_HANDLING.md) describes uncertain outcomes.

## Invited accounts and recovery

The local operator creates private one-use links without sending messages. Set
`DEX_APP_ROOT` and `DEX_APP_PYTHON` to the existing installation first:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" invite USERNAME --link-file "$DEX_APP_ROOT/invite-link.txt"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" recovery USERNAME --link-file "$DEX_APP_ROOT/recovery-link.txt"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" revoke USERNAME
```

Choose a new link filename; overwrite is refused. Share links privately before their
30-minute expiry. Revocation invalidates account access, sessions and outstanding links.

## Optional PostgreSQL/HTTPS profile

Staging uses an operator-managed PostgreSQL database, HTTPS origin, verified proxy
trust and separate web/worker processes. Configuration alone does not establish a
working hosted deployment.

| Environment variable | Requirement |
| --- | --- |
| `DEX_PROFILE` | `staging` |
| `DATABASE_URL` | PostgreSQL URL |
| `DEX_SECRET_KEY` | Private secret of at least 50 characters |
| `DEX_PUBLIC_ORIGIN` | Exact HTTPS origin without a path |
| `DEX_INGRESS` | `proxy` by default, or `render` with matching provider environment |
| `DEX_PROXY_NETWORKS` | Verified proxy CIDRs for `proxy`; no all-address network |
| `DEX_DATABASE_SSLMODE` | `require` by default or `verify-full`; `disable` only on loopback |

`beta/staging_config.py` validates these settings. Render ingress requires its service
identity and matching external hostname; do not invent proxy networks. Staging disables
live Shopping acquisition and CLI recognition. Scan configuration and reservations
persist in the database.

Inspect the operator before using a configured staging environment:

```sh
uv run --no-sync python -m pokemon_hunter.beta.deployment --help
```

It supports explicit migration/copied import, catalog publication, web/worker serving,
backup/restore, diagnostics, scan disablement and cleanup. Copied import requires an
empty target, a `.copied.sqlite3` backup and its complete `.scan-config.json` sidecar.
Restore requires an empty target. Cleanup and restore are mutations, not startup steps.
Container inputs live in `deploy/Dockerfile`; no workflow publishes or deploys an image.

## Provider configuration and inspection

Configure eBay in the selected server environment or supported configuration root.
Nonempty environment values take precedence over `.env`. Restart after environment
changes. Readiness checks local configuration; credential presence does not prove OAuth
success, provider access, remaining quota or storage rights. See [Shopping](hunts.md)
and [photo entry](photo-entry.md) for provider-specific requirements.

Some price reads perform cleanup: `price_snapshots.current` and `display_current` can
remove expired or withdrawn managed records. Use bounded metadata reads and read-only
database connections for a nonmutating investigation. Do not suspend expiry processing
or copy removable prices into diagnostic output.

## Snapshot retention and backups

Back up the protected database, authentication secret, photos, configuration, drafts
and permitted history before a data-changing update. Git and ordinary copy/goal exports
are not complete collection backups. Preserve current independent journals separately.

**Exclude the entire `price-snapshots/` directory from backups and exports**, including
staging files and version fingerprints. Do not retain removable package values in logs,
reports, exports or screenshots. Permanent saves require independently admitted surviving
rights. Source-specific acquisition staging outside the managed directory is unsupported.

Keep `.dex-price-revocations/` beside the application root outside app restore, including
its source registries (`*-sources.json`). Never replace it with an older backup. Restored
expired/revoked packages are excluded and managed copies removed before use. Missing
independent registry or version manifest fails closed. Permitted independent history
is not rewritten.

The expiry worker runs while serving; startup and access also check expiry. These checks
cannot guarantee deletion while the machine is stopped, external copy removal or complete
browser/OS-cache erasure. Source retention obligations must be compatible before admission.
The `price-remove-source --contract-sha256 DIGEST` command withdraws a source across
releases. Do not restore old source registries or fingerprints to reverse that withdrawal.
See [price snapshots](price-snapshots.md) for the full command set.

The group-metadata collector's canonical result and noncontent journal live outside the
installation. Preserve `.dex-tcgcsv-metadata/attempts.json` independently; restoring the
app must not renew an attempt. Failure and Stop remove managed body copies without
resetting consumption. Stop also removes a completed managed metadata result. Interrupted
supervisors may leave a pending validated copy for cleanup after the bounded child exits.

## Shopping discovery

Search, Next and assisted Load are explicit finite actions with independent Stop.
Opening, local typing/search, set changes, reveal, filtering, correction and comparison
do not acquire provider data. Discovery-to-review transfers only a checked temporary
summary under its original account/session and expiry; additional detail loading
remains explicit. Stop or expiry invalidates that origin.
The old `/api/hunts/` POST returns 410 directing callers to Shopping; historical reads
remain available. Request ceilings and source policies are documented in [Shopping](hunts.md).

Preserve `.dex-shopping-discovery/<root-path-sha256>/attempts.jsonl` beside the root
independently of database restoration. Admitted, in-flight and uncertain attempts remain
consumed after Stop, failure or recovery. Never reset this journal to renew an allowance.
Discovery results, listing details and review inputs live only in temporary server memory
and are excluded from saved history, exports and backups. Existing saved research retains
its original admission rules.

## Manual bulk entry and recovery

`enable-bulk` explicitly initializes the draft/replay schema through existing transactions;
startup and reads never migrate. Check the selected installation before enabling a
capability. `bulk-cleanup` is explicit maintenance rather than a scheduler.

Protect the latest database, drafts, replay aliases and receipts in backup. The copy/goal
export cannot restore all current state. Keep a runtime that understands confirmed bulk
and group-bound copy operations; older runtimes may not. Recovery must preserve later
writes, revocations and consumed reservations. The [collection contract](effective-collection.md)
owns review, confirmation, duplicate handling and Undo semantics.

## Photo-batch recovery

Photo batches require explicit local enablement through `enable-photo-batches`, with
scan support and the bulk schema already present. Startup and browsing do not migrate.
Staging is unsupported. `photo-batch-cleanup` provides explicit maintenance; the scan
worker also reapplies expiry, revocation and owned-payload cleanup.

Preserve the latest database, private image blobs, credentials and sibling
`.dex-photo-batches/<root-path-sha256>/` directory. Keep current admissions, consumed
attempts, deletion tombstones and the payload registry independently of app restore.
Never overlay an older journal or reset an uncertain attempt. Recovery must use the
same root identity and compatible cleanup before serving or dispatch. Moving a root
requires explicit journal preservation and rebinding. API dollar reservations and
single-card CLI usage records remain separate.

Unconfirmed images expire seven days after admission; edits do not extend retention.
Cancellation, deletion, Undo, copy removal and revocation withdraw image access. Only
explicitly retained crops associated with active copies can survive confirmation;
originals are removed. Database rollback must not restore deleted access. Cleanup removes
only registered owned temporary directories after 90 seconds while the shared CLI lock
is free. Hard termination cannot recall transmitted images or prove provider deletion.
See [photo entry](photo-entry.md) for consent, recognition and image-serving behavior.
