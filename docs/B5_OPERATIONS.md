# B5 operational foundation — local staging rehearsal

September 28, 2026. **Local staging engineering implemented; B5 hosted and real-device qualification remains OPEN.** No purchase, public deployment, external invitation, real recognition call or authoritative cutover was performed. B4 runtime `9dc074d` and documentation `5bf44b9` retain their original evidence.

## Selected architecture and cost

The authenticated app is **Django 5.2 / ASGI / Uvicorn**, with one web process and one independent database-backed worker. The legacy FastAPI app and SQLite/JSON collection remain preserved. Staging uses **Render paid web + background worker + managed PostgreSQL 17**. There is no framework rewrite, Redis or second deployment platform.

Private normalized JPEGs and archived private evidence use PostgreSQL `BYTEA`, served only through existing authorization checks. This is intentional for at most ten collectors: one consistent database backup includes assets, consent, accounts, inventory, catalogs, operations and spending reservations. No public media directory, ephemeral-disk photo store or separately inconsistent object backup. Reconsider object storage only if measured database size/latency warrants it. Each upload remains capped at two normalized images, daily account quotas and 1600px output.

Current planning estimate: web $7 + worker $7 + Basic-256mb PostgreSQL $6 + 5 GB at $0.30/GB = **about $21.50/month**, before workspace plan changes, taxes, bandwidth/build overages and recognition. This is an estimate, not a purchase or quote; confirm the account's current pricing before provisioning. A larger DB may be needed after measurement. Recognition retains existing $1 global / $0.50 per-account lifetime ceilings and $0.05 reservations. No reservations are reset.

Official sources reviewed: [Render pricing](https://render.com/pricing), [small-application cost breakdown](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses), [PostgreSQL](https://render.com/docs/postgresql), [private networking](https://render.com/docs/private-network), [HTTPS web services](https://render.com/docs/web-services), [backup/recovery](https://render.com/docs/postgresql-backups). Paid Hobby PITR has a three-day window; exported provider backups expire after seven days. This is independent of locally retained engineering evidence.

## Package and required configuration

`deploy/Dockerfile` builds the locked app with Python 3.12, PostgreSQL client tools and a non-root runtime. `deploy/render.yaml` describes the two services and database, with automatic deploys off. No owner data, photos, secrets, source archives or local config enter the Docker context. The blueprint is prepared, not applied. PostgreSQL 17 and the container are exercised locally; Render account networking remains an actual-hosted gate.

Both services need the same secure environment group:

- `DATABASE_URL`: selected managed database's internal connection URL, injected by Render. Keep it out of arguments, Git and ordinary logs.
- `DEX_SECRET_KEY`: one newly generated random secret of at least 50 characters, securely shared between web and worker. Retain in the secret manager across restarts and restores. It is distinct from the preserved local secret.
- `DEX_PUBLIC_ORIGIN`: exact HTTPS origin without a trailing slash, e.g. `https://dex-staging-web.onrender.com` or the chosen custom origin.
- `DEX_PROXY_NETWORKS`: verified ingress peer CIDR(s), comma separated. All-address ranges are refused. The proxy must replace forwarded protocol headers and prevent direct access to the backend. Determine the actual Render ingress peers in the account; do not guess a broad private range or enable `*` to make a failing check pass.
- `DEX_PROFILE=staging`; `DEX_DATABASE_SSLMODE=require` (default). TLS may be disabled only for a database on loopback in local rehearsal. `PORT` comes from Render.
- `OPENAI_API_KEY` only when securely available for the explicitly bounded evaluation. It is absent from the current process; suitable consented evaluation photos are also required. No secret files or unrelated credential stores were searched.

Missing configuration fails startup; there is no SQLite, weak-cookie or HTTP fallback. The original loopback profile retains its exact Host/peer/forwarding guard. Staging validates Host, Origin, TLS-proxy peer and forwarded HTTPS; secure host-only cookies, one-hour sessions, CSRF, Axes throttling, no-store and CSP remain enforced. HSTS is one hour without subdomain/preload opt-in; Django's two warnings for those deliberate domain-wide settings are documented, not silently suppressed.

## Copy, migrate and start

Never run these migration steps against the authoritative collection. Use a quiesced copied B4 environment. Preserve its source and scan configuration. Run `uv run python scripts/copy_b5_source.py --source-root PRIVATE_B4_ROOT --output NEW_PRIVATE_COPY_DIR`. This uses SQLite's consistent backup API and copies the unchanged scan configuration (or the existing manual defaults) alongside it as `review.copied.scan-config.json`. Both belong outside Git, mode 600, parent mode 700.

With the staging environment securely loaded, run inside the built image or a locked checkout:

```sh
uv sync --frozen --extra dev
uv run python -m pokemon_hunter.beta.deployment migrate-copy --path /private/review.copied.sqlite3
uv run python -m pokemon_hunter.beta.deployment check
uv run python -m pokemon_hunter.beta.deployment web
# A separate supervised process, with the same environment:
uv run python -m pokemon_hunter.beta.deployment worker
```

The destination must be empty. Django creates its own PostgreSQL auth/session schema; application schema conversion preserves text values, original IDs, binary assets, double-precision counters, constraints and sequences. Every copied row is compared before the import transaction commits; auth timestamps are compared as UTC instants. Failed imports leave a non-serving target; investigate privately and use a new disposable database, not a destructive retry over source data. `migrate` applies the idempotent B5 operational tables after a prepared database; it is not an empty-catalog bootstrap or a B0 live cutover command.

For the container, build `docker build -f deploy/Dockerfile -t dex-b5:local .`. Its executable is `/app/.venv/bin/python`, replacing `uv run python` above. Set command to `-m pokemon_hunter.beta.deployment web` or `worker` respectively. Keep PostgreSQL on a persistent managed database or named local Docker volume. Run exactly one worker initially. Web and worker restart independently, reconnect on each unit of work and use persisted jobs. SIGTERM stops new worker claims and lets the current bounded provider call finish; allow 50 seconds for shutdown. A forced interruption becomes failed after 120 seconds and requires explicit retry, with its reservation retained. Provider calls are outside transaction locks.

`/healthz/` verifies DB schema, valid scan configuration and a recent worker heartbeat; it returns only readiness, with 503 on missing/stale dependencies. It must pass through the same trusted HTTPS proxy. `diagnostics` emits aggregate state counts, known costs, reserved costs and latency; it excludes identities, messages, photos, links, prompts and credentials. A worker error emits only `worker_iteration_failed`. Disable provider/ingress request logging that would capture invitation/recovery URL paths before hosted use; application access logging is off.

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

Run an off-host logical backup daily and before schema/release changes; schedule `expire-backups` daily in the same restricted operator environment. The prepared scripts implement expiry, but no external scheduler/account was configured by this task. Provider PITR/export retention is separately managed by Render. Stop rollout if backup or restore checks fail.

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

- **Initial ten-set metadata:** legacy [PokemonTCG data repository](https://github.com/PokemonTCG/pokemon-tcg-data) and [API terms](https://dev.pokemontcg.io/terms) reviewed. No explicit redistribution grant established for the pinned repository snapshot. Staging shared browsing/matching excludes those legacy printings; IDs/private owned records remain intact. Local ten-set experience stays unchanged. The provider now marks the API deprecated with a March 2027 shutdown; no replacement subscription or migration was purchased. Broader hosted metadata needs an approved source/provenance mapping, preserving current IDs.
- **Gym Heroes metadata:** TCGdex MIT database license and retained attribution support the minimal imported metadata; source/version/hash stay attached. Staging can browse/add the 132 entries. Package imports contain no artwork/rules text/prices. Synthetic Orbits is original fixture coverage, labeled synthetic. Other arbitrary providers are excluded from staged shared browsing.
- **Artwork:** no hosted grant established for Pokémon/provider artwork; no external image URLs, hotlinking or artwork service is enabled. Private user-uploaded photos retain account/consent authorization. CSP permits same-origin content only.
- **Prices:** existing dated `market_values.json`/raw guide scenarios are local private inputs, not a redistribution license; staging does not read or expose those guides. No TCGplayer, eBay or replacement pricing API is activated. Recorded purchase amounts remain exact inventory fields.
- **Hunts:** local sample/history inputs remain preserved; hosted guide/search projections are unavailable until their individual source permissions are resolved. No live marketplace search.

Missing recognition, images or prices never blocks supported manual add/edit/remove/export, provisional photo entry, goals or catalog requests. Pending metadata rights reduce advertised staged catalog coverage rather than silently granting it.

## Acceptance matrix and remaining gates

| Gate | Local observation | Actual hosted / real device |
| --- | --- | --- |
| Copied migration | All source table values compared on PostgreSQL 17, including IDs, bytes, auth, catalog, history, consent and reservations | Not observed |
| Restore | One-snapshot native dump restored to empty PG17 DB; all table manifests match; password, photo/consent authorization, copies/catalog/journal read back | Not observed |
| B2/B3/B4 | Concurrent exactly-once add, private photo confirmation, request consent, publish/rollback/republish; desktop/narrow HTTPS browser exercised | Not observed |
| Security | Separate HTTPS profile, secure login cookies, CSRF, trusted-peer/host/origin rejection, account isolation | Render ingress/network/managed certificate pending |
| Operations | Container build, independent web/worker, persisted interrupted-job handling and no automatic billed retry; health/diagnostics | Provider restart/backup jobs pending |
| Privacy/spend | Deletion preserves other users/catalog and reservation sum; retention and backup expiry tests | Provider deletion/expiry observation pending |
| Recognition | Manual/fixture engineering only; no key available | Consented evaluation photos + secure key needed |
| Devices | Desktop and 390px Chromium emulation only | Actual iOS Safari and Android Chrome camera/library, sessions and recovery pending |

Private evidence: `/Users/michaelfuscoletti/dex-private/b5-20260928/`. Exact candidate identity, image identity and final regression/clean-checkout results are recorded in `handoff.json`; original source/review preservation records remain outside Git. Failed preliminary attempts are retained separately and are not qualified results.

Shortest next path: obtain authorized Render account/configuration, verify the bill and ingress trust/logging, prepare isolated staging secrets and empty DB, migrate an approved copied snapshot, start the web/worker image, observe real HTTPS health/isolation/backup/restore/restarts, then exercise the actual phones. Those account/provider/device observations keep B5 open. No broad planning interview or further routine local engineering approval is required.
