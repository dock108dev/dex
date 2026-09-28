# B5 operations — deployment preparation and remaining qualification

September 28, 2026. **Deployment preparation implemented; B5 hosted and real-device qualification remains OPEN.** The follow-up starts from `9b7e1a1`; exact runtime/image and setup steps are in [the deployment package](B5_DEPLOYMENT.md). No purchase, public deployment, external invitation, real recognition call or authoritative cutover was performed. B4 runtime `9dc074d` and documentation `5bf44b9` retain their original evidence.

## Selected architecture and cost

The authenticated app is **Django 5.2 / ASGI / Uvicorn**, with one web process and one independent database-backed worker. The legacy FastAPI app and SQLite/JSON collection remain preserved. Staging uses **Render paid web + background worker + managed PostgreSQL 17 in Virginia**. There is no framework rewrite, Redis or second deployment platform.

Private normalized JPEGs and archived private evidence use PostgreSQL `BYTEA`, served only through existing authorization checks. This is intentional for at most ten collectors: one consistent database backup includes assets, consent, accounts, inventory, catalogs, operations and spending reservations. No public media directory, ephemeral-disk photo store or separately inconsistent object backup. Reconsider object storage only if measured database size/latency warrants it. Each upload remains capped at two normalized images, daily account quotas and 1600px output.

Prices checked September 28, 2026: web `0.5c-512mb` $7 + worker `0.5c-512mb` $7 + PostgreSQL `0.1c-256mb` $6 + 5 GB at $0.30/GB = **about $21.50/month**, before workspace plan changes, taxes, bandwidth/build overages and recognition. This is an estimate, not a purchase or quote; confirm the account's current pricing before provisioning. A larger DB may be needed after measurement. Recognition retains existing $1 global / $0.50 per-account lifetime ceilings and $0.05 reservations. No reservations are reset.

Official sources reviewed: [Render pricing](https://render.com/pricing), [small-application cost breakdown](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses), [PostgreSQL](https://render.com/docs/postgresql), [private networking](https://render.com/docs/private-network), [HTTPS web services](https://render.com/docs/web-services), [backup/recovery](https://render.com/docs/postgresql-backups). Paid Hobby PITR has a three-day window; exported provider backups expire after seven days. This is independent of locally retained engineering evidence.

## Package and required configuration

`deploy/Dockerfile` builds the locked app with Python 3.12, PostgreSQL client tools and a non-root runtime. `deploy/render.yaml` describes the two services and database, using the pinned Linux AMD64 image and automatic deploys off. Image-based services do not automatically rebuild from Git; keep Blueprint auto-sync and deploy hooks disabled too. No owner data, photos, secrets, source archives or local config enter the Docker context. The blueprint is prepared, not applied. PostgreSQL 17 and the container are exercised locally; account-level validation and real Render ingress remain unobserved. The previous ARM64 `9b7e1a1` image is not a Render-compatible rollback artifact.

Both services need the same secure environment group:

- `DATABASE_URL`: selected managed database's internal connection URL, injected by Render. Keep it out of arguments, Git and ordinary logs.
- `DEX_SECRET_KEY`: one newly generated random secret of at least 50 characters, securely shared between web and worker. Retain in the secret manager across restarts and restores. It is distinct from the preserved local secret.
- `DEX_PUBLIC_ORIGIN`: exact HTTPS origin without a trailing slash, e.g. `https://dex-staging-web.onrender.com` or the chosen custom origin.
- `DEX_INGRESS=render`: uses Render’s documented edge TLS/forwarded-protocol contract and dedicated workspace private-network boundary. It requires provider-injected `RENDER=true`, `RENDER_SERVICE_ID`, and web/worker service type; web hostname must equal the configured origin. Do not supply `DEX_PROXY_NETWORKS` on Render. Generic local rehearsal keeps `DEX_INGRESS=proxy` and an explicit narrow CIDR allowlist.
- `DEX_PROFILE=staging`; `DEX_DATABASE_SSLMODE=require` (default). TLS may be disabled only for a database on loopback in local rehearsal. `PORT` comes from Render.
- `OPENAI_API_KEY` only when securely available for the explicitly bounded evaluation. It is absent from the current process; suitable consented evaluation photos are also required. No secret files or unrelated credential stores were searched.

Missing configuration fails startup; there is no SQLite, weak-cookie or HTTP fallback. The original loopback profile retains its exact Host/peer/forwarding guard. Staging validates exact Host, Origin and forwarded HTTPS; generic proxy mode also validates peer CIDRs. Render mode trusts the isolated provider workspace network, not a guessed IP range; secure host-only cookies, one-hour sessions, CSRF, Axes throttling, no-store and CSP remain enforced. HSTS is one hour without subdomain/preload opt-in; Django's two warnings for those deliberate domain-wide settings are documented, not silently suppressed.

## Synthetic seed, migrate and start

**Default: synthetic staging only.** Run `uv run python -m pokemon_hunter.beta.synthetic --output /private/NEW_SYNTHETIC_ROOT` in the pinned checkout, or use `/app/.venv/bin/python` in the image. This refuses an existing output directory, reads only packaged permitted catalogs, and generates two random-password accounts, six copies including provisional photos, private/shared request consent, four frozen goals, 12 catalog publications with rollback history and a retained $0.05 synthetic reservation. The photos are original geometric fixtures, not evaluation cards. The output includes `synthetic.copied.sqlite3`, its scan-config sidecar and a mode-600 `credentials.json`. No invitation is sent; this is not actual B1 owner provisioning.

The precise first-boot sequence for an empty managed database is in [B5_DEPLOYMENT.md](B5_DEPLOYMENT.md). Keep seed files and passwords private, outside Git, and never attach them to provider logs. The migration input below is the synthetic copied database.

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

- **Original ten-set metadata:** replaced for staging by 859 minimal records from MIT-licensed [TCGdex cards-database](https://github.com/tcgdex/cards-database/tree/309aab7060b165925fee48573e730275dfbd737c), pinned at `309aab7060b165925fee48573e730275dfbd737c`. The [license](https://github.com/tcgdex/cards-database/blob/309aab7060b165925fee48573e730275dfbd737c/LICENSE), attribution, source-file hashes and explicit mapping package are retained under `config/catalog-imports/`. Three name differences were individually reviewed; gender-spacing/Unown typography is normalized for comparison. Existing printing IDs (including first-edition identity), copies, frozen goals and original provenance survive. Multiple variant candidates stop rather than guess. `publish-staging-catalog` runs the normal preview/verify/publication journal on an already prepared database; repeated calls are idempotent. No legacy PokemonTCG data redistribution permission is assumed.
- **Gym Heroes metadata:** TCGdex MIT database license and retained attribution support the minimal imported metadata; source/version/hash stay attached. Staging can browse/add the 132 entries. Package imports contain no artwork/rules text/prices. Synthetic Orbits is original fixture coverage, labeled synthetic. Other arbitrary providers are excluded from staged shared browsing.
- **Artwork:** no hosted grant established for Pokémon/provider artwork; no external image URLs, hotlinking or artwork service is enabled. Private user-uploaded photos retain account/consent authorization. CSP permits same-origin content only.
- **Prices:** existing dated `market_values.json`/raw guide scenarios are local private inputs, not a redistribution license; staging does not read or expose those guides. No TCGplayer, eBay or replacement pricing API is activated. Recorded purchase amounts remain exact inventory fields.
- **Hunts:** local sample/history inputs remain preserved; hosted guide/search projections are unavailable until their individual source permissions are resolved. No live marketplace search.

Missing recognition, images or prices never blocks supported manual add/edit/remove/export, provisional photo entry, goals or catalog requests. Staging now supports **991 Pokémon entries across eleven sets plus two explicitly synthetic Orbits variants**, and all 251 named Pokédex projections. Precise differences from local: no dated guide estimates, per-card price scenarios, marketplace/sample hunt projections or external artwork; rarity labels follow TCGdex (for example Rare, without inferring holo finish); only the explicit supplied English catalog coverage is qualified. Unknown variants stay unknown. The original local app and its guides/hunts are unchanged; this is not full local feature parity.

## Acceptance matrix and remaining gates

| Gate | Local observation | Actual hosted / real device |
| --- | --- | --- |
| Copied migration | All source table values compared on PostgreSQL 17, including IDs, bytes, auth, catalog, history, consent and reservations | Not observed |
| Restore | One-snapshot native dump restored to empty PG17 DB; all table manifests match; password, photo/consent authorization, copies/catalog/journal read back | Not observed |
| B2/B3/B4 | Concurrent exactly-once add, private photo confirmation, request consent, publish/rollback/republish; desktop/narrow HTTPS browser exercised | Not observed |
| Security | Separate HTTPS profile, secure login cookies, CSRF, trusted-peer/host/origin rejection, account isolation | Render ingress/network/managed certificate pending |
| Operations | Container build, independent web/worker, persisted interrupted-job handling and no automatic billed retry; health/diagnostics | Provider restart/backup jobs pending |
| Privacy/spend | Deletion preserves other users/catalog and reservation sum; retention and backup expiry tests | Provider deletion/expiry observation pending |
| Recognition | Manual/fixture engineering only; no key available; zero real calls, cost $0, correct/wrong/unresolved/latency unmeasured | Consented evaluation photos + secure key needed |
| Devices | Desktop and 390px Chromium emulation only; [phone walkthrough](B5_PHONE_CHECKS.md) prepared | Actual iOS Safari and Android Chrome not run |

Private evidence: `/Users/michaelfuscoletti/dex-private/b5-20260928/`. Exact candidate identity, image identity and final regression/clean-checkout results are recorded in `handoff.json`; original source/review preservation records remain outside Git. Failed preliminary attempts are retained separately and are not qualified results.

The follow-up local observations and exact image are recorded in [B5_DEPLOYMENT.md](B5_DEPLOYMENT.md) and `/Users/michaelfuscoletti/dex-private/b5-followup-20260928/`. Prior observations above retain their original identity; they are not relabeled hosted results.

Next action: supply the existing authorized Render workspace/target and registry access, or have the owner provision the listed paid resources. The engineer then applies the pinned package and performs the hosted checks. There is no new routine code approval gate. B5 remains open; B6 and actual B1 owner provisioning do not advance from these local results.
