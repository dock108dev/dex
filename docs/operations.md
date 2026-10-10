# Operations

## Existing local installations

Select the installation's private root and start it using
[local development](local-development.md#existing-installations).
The authenticated server binds to `127.0.0.1:8011`. Restart after source changes;
never seed, initialize or bootstrap an existing installation again merely to run it.

Stop the app before a data/schema update and back up the complete private root,
including database, secret, photos, provider settings and journals. Preserve file
permissions. Git is not a collection backup. Rehearse unfamiliar imports or
rollback on a copy. Confirm the affected copies, goals and saved lookups afterward.
Do not reset spend reservations or overwrite later writes to recover a failed step;
see [recovery](ERROR_HANDLING.md).

## Invited accounts and recovery

Local operator commands create private one-use links; they do not send messages:

```sh
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" invite USERNAME --link-file "$DEX_APP_ROOT/invite-link.txt"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" recovery USERNAME --link-file "$DEX_APP_ROOT/recovery-link.txt"
uv run --no-sync python -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" revoke USERNAME
```

Set `DEX_APP_ROOT` to the existing root first. Choose a new link filename; the
operator refuses overwrite. Links expire after 30 minutes and must be shared
privately. Revocation invalidates account access, sessions and outstanding links.
Separate installations can have independent provider configuration and storage.

## Optional PostgreSQL/HTTPS profile

The staging profile is implemented separately from local serving. It requires an
operator-managed database, HTTPS origin, proxy trust and separate web/worker
processes. These settings alone do not establish a working hosted deployment.

| Environment variable | Requirement |
| --- | --- |
| `DEX_PROFILE` | `staging` |
| `DATABASE_URL` | PostgreSQL URL |
| `DEX_SECRET_KEY` | Private secret of at least 50 characters |
| `DEX_PUBLIC_ORIGIN` | Exact HTTPS origin without a path |
| `DEX_INGRESS` | `proxy` by default, or `render` with matching provider environment |
| `DEX_PROXY_NETWORKS` | Verified proxy CIDRs for `proxy`; no all-address network |
| `DEX_DATABASE_SSLMODE` | `require` by default or `verify-full`; `disable` only for loopback |

`staging_config.py` validates these settings. Render ingress also requires its
service identity and matching external hostname; do not invent proxy networks.
Staging disables live hunts and CLI recognition. Scanning configuration and
reservations persist in the database.

Inspect operator commands before using a configured staging environment:

```sh
uv run --no-sync python -m pokemon_hunter.beta.deployment --help
```

The operator supports explicit migration/copied import, public catalog publication,
web/worker serving, backup/restore, diagnostics, scan disablement and cleanup.
Restore and cleanup are operational mutations, not startup commands. Backups
contain private state and need restricted storage. Container build inputs are in
`deploy/Dockerfile`; there is no repository-owned registry, Render account,
release identity or automatic publication configuration.

For provider settings use [photo entry](photo-entry.md) and [eBay hunts](hunts.md).
For original-app scheduling use the [watcher guide](legacy-watcher.md).
