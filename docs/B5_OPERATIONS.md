# B5 operations — Mac-hosted private staging

> **DEFERRED — optional future reference, not active next steps.** Mike’s September 28 direction makes the existing localhost app the sole current target. All setup/checklist requirements below are inactive for current local use, including hosting/LAN HTTPS, device tests, managed startup/reboot and external backup infrastructure. Preserve prior evidence; do not execute this runbook unless that scope is reopened. The [current roadmap](ROADMAP.md) takes precedence.


**Current host: Mike's Mac, with test phones on the home network.** [The active closeout checklist](B5_DEPLOYMENT.md) replaces Render setup. B5 remains OPEN for final endpoint, restart/backup operation and actual-device observations. Existing results retain their original candidate identities; no cloud or phone result is inferred from local emulation.

## Selected architecture and cost

The authenticated app is Django 5.2 / ASGI / Uvicorn with one web process, one independent database-backed worker and PostgreSQL 17 on the Mac. Preserve the legacy FastAPI app, original SQLite/JSON collection, review app on 8011 and earlier loopback rehearsal on 8443. Use isolated synthetic staging data for qualification. No new hosting subscription or registry publication is required. The Mac must be awake and connected for access; record outage/sleep and restart behavior. Independent backup storage may use an existing external drive or encrypted destination; do not purchase hardware or services implicitly.

Private normalized JPEGs remain PostgreSQL BYTEA served through authorization checks. A consistent database backup includes accounts, inventory, catalogs, photos, consent, operations and spending reservations. Preserve the existing $1 global / $0.50 account lifetime ceilings and $0.05 reservations. No counter reset is part of setup or recovery.

## Package and required configuration

Reuse runtime `0f17cc9` and the retained image identified in [B5_DEPLOYMENT.md](B5_DEPLOYMENT.md). Any source change or rebuild requires its own exact identity and affected checks. The prepared Render blueprint is an inactive alternative; see [historical Render instructions](B5_RENDER_REFERENCE.md) only if cloud hosting is explicitly reopened.

Both local staging services use securely supplied configuration:

- `DATABASE_URL`: the isolated PostgreSQL target. Keep the database unreachable from phones/public networks. Preserve existing data and reservations.
- `DEX_SECRET_KEY`: retain the target's existing secure key across restarts and restores. Do not rotate it merely because another unused key was generated during Render preparation.
- `DEX_PUBLIC_ORIGIN`: the exact phone-facing HTTPS origin. No certificate-warning bypass counts as qualification.
- `DEX_PROFILE=staging`, `DEX_INGRESS=proxy`, and `DEX_PROXY_NETWORKS`: only the actual narrow proxy peer addresses. If the proxy connects over loopback, trust that loopback peer only; Docker networking must be observed rather than guessed. The proxy replaces forwarded headers and the backend must not be directly reachable from the LAN.
- `DEX_DATABASE_SSLMODE=require` by default; the existing implementation permits disabling database TLS only for loopback. Never weaken that check to accommodate a different network arrangement.
- `OPENAI_API_KEY` only for the separately bounded real evaluation when suitable images are available. Missing configuration leaves recognition manual/simulated.

The fixed loopback review profile remains unchanged. Staging continues strict Host/Origin, secure cookies, CSRF, throttling, no-store and CSP. The loopback rehearsal proxy and browser test exception are prior test tools, not a ready phone-facing deployment. Actual endpoint/startup configuration and certificate trust still need implementation and observation. No public tunnel or router port forwarding is part of the selected home-network scope.

## Synthetic seed, migrate and start

**Default: synthetic staging only.** Run `uv run python -m pokemon_hunter.beta.synthetic --output /private/NEW_SYNTHETIC_ROOT` in the pinned checkout, or use `/app/.venv/bin/python` in the image. This refuses an existing output directory, reads only packaged permitted catalogs, and generates two random-password accounts, six copies including provisional photos, private/shared request consent, four frozen goals, 12 catalog publications with rollback history and a retained $0.05 synthetic reservation. The photos are original geometric fixtures, not evaluation cards. The output includes `synthetic.copied.sqlite3`, its scan-config sidecar and a mode-600 `credentials.json`. No invitation is sent; this is not actual B1 owner provisioning.

For the Mac, reuse the existing isolated synthetic PostgreSQL target and its credentials. Generate/migrate a seed only for an explicitly new empty target, never as a restart step. Keep seed files and passwords private, outside Git, and never attach them to provider logs. The migration input below is the synthetic copied database.

Owner-data migration is a **separate later operation**, not part of hosted qualification. The existing `scripts/copy_b5_source.py` remains available only for a separately authorized copied snapshot; this follow-up uploads no owner collection or retained evidence.

With the staging environment securely loaded, run inside the built image or a locked checkout:

```sh
uv sync --frozen --extra dev
uv run python -m pokemon_hunter.beta.deployment migrate-copy --path /private/NEW_SYNTHETIC_ROOT/synthetic.copied.sqlite3
uv run python -m pokemon_hunter.beta.deployment check
uv run python -m pokemon_hunter.beta.deployment web
# A separate supervised process, with the same environment:
uv run python -m pokemon_hunter.beta.deployment worker
```

The destination must be empty. Django creates its own PostgreSQL auth/session schema; application schema conversion preserves text values, original IDs, binary assets, double-precision counters, constraints and sequences. Every copied row is compared before the import transaction commits; auth timestamps are compared as UTC instants. Failed imports leave a non-serving target; investigate privately and use a new disposable database, not a destructive retry over source data. `migrate` applies the idempotent B5 operational tables after a prepared database; it is not an empty-catalog bootstrap or a B0 live cutover command.

For the container, build `docker build -f deploy/Dockerfile -t dex-b5:local .`. Its executable is `/app/.venv/bin/python`, replacing `uv run python` above. Set command to `-m pokemon_hunter.beta.deployment web` or `worker` respectively. Keep PostgreSQL on a persistent managed database or named local Docker volume. Run exactly one worker initially. Web and worker restart independently, reconnect on each unit of work and use persisted jobs. SIGTERM stops new worker claims and lets the current bounded provider call finish; allow 50 seconds for shutdown. A forced interruption becomes failed after 120 seconds and requires explicit retry, with its reservation retained. Provider calls are outside transaction locks.

`/healthz/` verifies DB schema, valid scan configuration and a recent worker heartbeat; it returns only readiness, with 503 on missing/stale dependencies. In Render mode only GET/HEAD `/healthz/` permits plain internal probes with the exact configured Host, because provider health probes do not promise forwarded HTTPS headers. It returns no account data. Every other route still requires exact forwarded HTTPS. Generic proxy mode still requires trusted HTTPS for health too. `diagnostics` emits aggregate state counts, known costs, reserved costs and latency; it excludes identities, messages, photos, links, prompts and credentials. A worker error emits only `worker_iteration_failed`. Application access logging is off. Render Pro+ request logs can retain requested URLs; no documented per-path redaction switch was established. Staging access links therefore carry bearer tokens in URL fragments, exchange them via a CSRF-protected POST body at `/access/start/`, and set passwords at fixed `/access/reset/`. Old token-bearing path routes are absent in staging. Never enable body logging, exception payload logging or verbose proxy logs. Provider log retention/export settings still need account verification.

`deploy/rehearsal_proxy.py --cert PRIVATE_CERT --key PRIVATE_KEY --upstream-port 8000` is a loopback-only HTTPS test harness, listening at `https://127.0.0.1:8443`. It strips incoming forwarded headers before forwarding to the backend. A self-signed local certificate and Chromium's local test exception are not hosted certificate/device observations. The ordinary review app remains at port 8011.

## Backup, restore and release rollback

```sh
uv run python -m pokemon_hunter.beta.deployment backup --path /private/backups/new-unique-name
# Point DATABASE_URL at a NEW EMPTY disposable recovery database first:
uv run python -m pokemon_hunter.beta.deployment restore --path /private/backups/new-unique-name
uv run python -m pokemon_hunter.beta.deployment diagnostics
uv run python -m pokemon_hunter.beta.deployment expire-backups --path /private/backups
```

A native custom-format `pg_dump` shares an exported repeatable-read snapshot with the row/content manifest. It includes private assets atomically with consent and inventory. The bundle has a SHA-256 checksum and seven-day expiration. Restore is transactional, refuses any nonempty target and verifies all table counts/content hashes. PostgreSQL client version must support the server version; use the built container for PostgreSQL 17. Backups contain sensitive data: use private encrypted operator storage, keep access restricted, never attach them to Git or issue reports. Store deployment secrets separately in the secret manager, not in backups.

Run a logical backup daily and before schema/release changes; schedule `expire-backups` in the restricted operator environment. Keep a protected copy on an independent physical device or existing encrypted backup destination. Backup scheduling and that independent copy have not yet been observed. Stop rollout if backup or restore checks fail. Render PITR is not a dependency for the Mac target.

**Do not roll back data by overwriting the current database with an old backup.** For a compatible application rollback, redeploy a previous B5 image against the current PostgreSQL schema, preserving new writes. B4's SQLite runtime is not a compatible PostgreSQL rollback image. If a data rollback is needed, stop writes and worker, retain a final current backup, restore the earlier backup into a separate database, then reconcile all intervening operations, accounts, deletions, photo consent, catalog changes and spend reservations. Reapply deletions and revoked consent before allowing access; never re-enable a deleted account from an old dump. Do not reduce spending counters. Keep both databases and do not switch until reconciliation is reviewed. A restored engineering test database containing synthetic accounts is never authoritative. The original SQLite copy remains the before-migration rehearsal fallback; it cannot accept post-cutover competing writes.

## Privacy and support

Staging links **Privacy and support** from the collection navigation. Feedback is private, capped at 2,000 characters/ten messages per day, expires after 30 days, and is removed with the account. Read feedback only through a restricted DB/operator session; diagnostics never export message text.

Account deletion requires the authenticated account's current password and typing DELETE. It removes auth credentials, sessions, matching login-attempt records, inventory, binders, goals, private archives/hunts, operation evidence, submissions/consent, photos and feedback. Shared catalog/publication integrity and other accounts remain. A non-login, non-identifying account tombstone and scrubbed job counters remain so deletion cannot release lifetime spending reservations. Shared catalog audit actor attribution is anonymized. Owner deletion removes the owner login; restoring admin access requires a deliberate operator action, not public registration/bootstrap adoption.

Worker cleanup expires unconfirmed photo bytes/evidence after seven days, removes unavailable-copy/revoked-account photos, expires feedback and clears expired sessions. Confirmed photos stay until explicitly removed, copy removal or account deletion. `cleanup` also runs manually. Job cost/reservation counters are not retention-resettable. Deleted bytes may remain in restricted backups until their seven-day expiration; apply deletions to any restored backup before use. Prior B0–B4 retained engineering snapshots are separate private historical evidence, not automatically deleted by the new backup cleanup command.

## Operator actions

```sh
uv run python -m pokemon_hunter.beta.deployment disable-scanning
uv run python -m pokemon_hunter.beta.deployment cleanup
uv run python -m pokemon_hunter.beta.deployment diagnostics
# Existing mature account tools, with staging environment still loaded:
uv run python -m pokemon_hunter.beta.cli --root /private/operator invite USERNAME --link-file /private/operator/invite-link
uv run python -m pokemon_hunter.beta.cli --root /private/operator revoke USERNAME
uv run python -m pokemon_hunter.beta.cli --root /private/operator recovery USERNAME --link-file /private/operator/recovery-link
```

Create `/private/operator` privately (700), use a fresh filename (600), and never place links in logs. Tools only write a one-use link; they do not send it. Delivery and invitations are outside this task. Recovery requires independent identity verification. Revoke immediately invalidates login/password-based sessions and links. Bootstrap remains private interactive entry and never resets an already bound owner's password. Actual B1 owner provisioning remains pending; a copied review account is not that owner qualification.

Disabling scans updates the shared persisted configuration immediately for both services. In-flight requests may already be billed. Manual collection operations remain available. To re-enable, the operator edits the `beta_operations` row `scan_config`, preserving ceilings and every job reservation; choose manual, fixture or openai deliberately. Fixture mode is visibly simulated. A missing key never triggers a call. Real evaluation remains **zero calls / $0 spent; accuracy, uncertainty, real latency and usage cost unmeasured**.

## Source-by-source hosted boundary

- **Original ten-set metadata:** replaced for staging by 859 minimal records from MIT-licensed [TCGdex cards-database](https://github.com/tcgdex/cards-database/tree/309aab7060b165925fee48573e730275dfbd737c), pinned at `309aab7060b165925fee48573e730275dfbd737c`. The [license](https://github.com/tcgdex/cards-database/blob/309aab7060b165925fee48573e730275dfbd737c/LICENSE), attribution, source-file hashes and explicit mapping package are retained under `config/catalog-imports/`. Three name differences were individually reviewed; gender-spacing/Unown typography is normalized for comparison. Existing printing IDs (including first-edition identity), copies, frozen goals and original provenance survive. Multiple variant candidates stop rather than guess. `publish-staging-catalog` runs the normal preview/verify/publication journal on an already prepared database; repeated calls are idempotent. No legacy PokemonTCG data redistribution permission is assumed.
- **Gym Heroes metadata:** TCGdex MIT database license and retained attribution support the minimal imported metadata; source/version/hash stay attached. Staging can browse/add the 132 entries. Package imports contain no artwork/rules text/prices. Synthetic Orbits is original fixture coverage, labeled synthetic. Other arbitrary providers are excluded from staged shared browsing.
- **Artwork:** no hosted grant established for Pokémon/provider artwork; no external image URLs, hotlinking or artwork service is enabled. Private user-uploaded photos retain account/consent authorization. CSP permits same-origin content only.
- **Prices:** existing dated `market_values.json`/raw guide scenarios are local private inputs, not a redistribution license; staging does not read or expose those guides. No TCGplayer, eBay or replacement pricing API is activated. Recorded purchase amounts remain exact inventory fields.
- **Hunts:** local sample/history inputs remain preserved; hosted guide/search projections are unavailable until their individual source permissions are resolved. No live marketplace search.

Missing recognition, images or prices never blocks supported manual add/edit/remove/export, provisional photo entry, goals or catalog requests. Staging now supports **991 Pokémon entries across eleven sets plus two explicitly synthetic Orbits variants**, and all 251 named Pokédex projections. Precise differences from local: no dated guide estimates, per-card price scenarios, marketplace/sample hunt projections or external artwork; rarity labels follow TCGdex (for example Rare, without inferring holo finish); only the explicit supplied English catalog coverage is qualified. Unknown variants stay unknown. The original local app and its guides/hunts are unchanged; this is not full local feature parity.

## Acceptance matrix and remaining gates

The active [Mac closeout checklist](B5_DEPLOYMENT.md) is the source of truth. Existing exact-image PostgreSQL migration, backup/empty-target restore and post-backup write/reservation preservation were actually observed on this Mac under `/Users/michaelfuscoletti/dex-private/b5-followup-20260928/`; these need no repeat solely because Render was removed. Earlier foundation evidence remains under `/Users/michaelfuscoletti/dex-private/b5-20260928/` with its own candidate identity.

Still required: the final trusted home-network HTTPS endpoint and account/photo/core-flow checks through it; managed service startup, process/Mac restart persistence and sleep behavior; observed recurring backup plus an independent protected copy; actual iOS Safari and Android Chrome walkthroughs. Render ingress, provider billing, cloud restart and managed backup checks are not applicable to the selected target. Unavailable devices remain an open observation, not an emulation pass.

Real recognition remains a separately reported B3 evaluation gap if its key/images are absent. Operational B5 completion would not imply live recognition, owner acceptance, actual B1 provisioning, full local feature parity or B6 readiness. No invitations or authoritative cutover are authorized by this closeout.

Next action: engineer configures the Mac endpoint using the preserved synthetic setup. Mike supplies the actual phones, an available backup destination and a convenient time for a Mac restart check. No Render account or additional routine engineering approval is needed.
