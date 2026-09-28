# B5 Render reference — inactive alternative

> **DEFERRED — optional future reference, not active next steps.** Mike’s September 28 direction makes the existing localhost app the sole current target. All setup/checklist requirements below are inactive for current local use, including hosting/LAN HTTPS, device tests, managed startup/reboot and external backup infrastructure. Preserve prior evidence; do not execute this runbook unless that scope is reopened. The [current roadmap](ROADMAP.md) takes precedence.


**Historical preparation only. Render is no longer the selected B5 host or a closure dependency.** Use [the Mac staging closeout](B5_DEPLOYMENT.md). This reference preserves the prior image/configuration and evidence; do not provision these resources as part of the current plan.

**Prepared, not deployed.** Runtime `0f17cc9ff337ee1ce90cdb32875afd7de6d03e38`, from `9b7e1a1`, is committed on main. The [release manifest](../deploy/release.json) binds the exact source tree, source-content manifest, OCI archive and Linux AMD64 image. Later handoff-only commits do not change this runtime.

- Image: `sha256:46facd36fc6bb15603960722bba10e015bc4189a73ef30a0208be051a6a52c8b`.
- Intended **private**, not-yet-published reference: `ghcr.io/dock108dev/dex-staging@sha256:46facd36fc6bb15603960722bba10e015bc4189a73ef30a0208be051a6a52c8b`.
- Retained OCI archive: `/Users/michaelfuscoletti/dex-private/b5-followup-20260928/dex-b5-0f17cc9-amd64.oci.tar`.
- Archive SHA-256: `fb253b1b7c27640f2066189ed23d384e2de02d665c890f165529fd574a3c6e0b`.
- Configuration: [render.yaml](../deploy/render.yaml), one web, one worker, PG17, Virginia, external database ingress denied, storage autoscaling off, 60-second shutdown allowance. Runtime auto-deployment is off; disable Blueprint auto-sync and do not enable deploy hooks during qualification.

## Minimal missing setup

| Input/action | Exact requirement |
| --- | --- |
| Existing authorized Render target, or owner-provisioned resources | Dedicated staging workspace ID, web/worker/database IDs, actual `onrender.com` hostname, operator service-shell access. No such target, API key or Render CLI account configuration was found; GitHub has no configured environments/secrets for this repo. No resource was purchased. |
| Private registry access | Publish the retained OCI archive without rebuilding or changing its manifest; configure a Render pull credential named `dex-staging-ghcr` for private `ghcr.io/dock108dev/dex-staging`. Verify the registry's manifest digest equals the release manifest before deploying. Publishing and private visibility are still unobserved. |
| Shared secret group | Create `dex-staging-secrets`: securely generated `DEX_SECRET_KEY` of at least 50 characters (for example `secrets.token_urlsafe(64)`), and exact `DEX_PUBLIC_ORIGIN=https://ACTUAL_HOST.onrender.com`. Do not log values. Keep the key stable through restarts/restores. `DATABASE_URL` is supplied from the managed database. |
| Recovery/backup target | Separate **empty** PG17 restore instance/target and restricted encrypted off-host backup destination. Configure daily backup/expiry in the restricted operator environment; no scheduler or storage account is configured by this task. |
| Independent recognition/device inputs | `OPENAI_API_KEY` on worker plus a small consented labeled image set; actual iOS Safari and Android Chrome sessions. Missing recognition does not block manual/synthetic staging. Actual B1 owner provisioning remains independent. |

Current [Render prices](https://render.com/pricing): each web/worker `0.5c-512mb` is $7/month; DB `0.1c-256mb` is $6/month plus 5 GB × $0.30 = $1.50. **Baseline $21.50/month**, excluding taxes, variable usage, registry/backup storage and recognition. A same-size separate restore instance adds **$7.50/month while retained**, prorated under provider billing (about $29/month combined while both databases exist). No Pro upgrade is selected. If an existing workspace cannot isolate staging from untrusted private services, use a dedicated workspace rather than silently broadening the trust boundary or buying a plan.

## Provider contract and first boot

The earlier peer-CIDR assumption is not usable for Render: stable ingress CIDRs were not established in primary documentation. Render terminates edge TLS and forwards HTTP with `X-Forwarded-Proto: https`; private peers share a workspace/region network. The explicit Render profile validates provider environment identity, exact origin/host, forwarded HTTPS and CSRF, while treating that isolated private network as trusted. It does **not** claim cryptographic proxy authentication or protection from a compromised same-workspace service. Generic proxy mode retains its narrow CIDR checks. Observe spoofed protocol/host rejection on the real edge before qualification. Sources: [Render web architecture](https://render.com/tutorials/web-service-vs-static-site/web-services), [private networking](https://render.com/docs/private-network), [provider variables](https://render.com/docs/environment-variables).

Only GET/HEAD `/healthz/` allows plain internal probes with the correct Host; all account routes still require forwarded HTTPS. This follows [Render health checks](https://render.com/docs/health-checks). The web binds `0.0.0.0:$PORT`, with Uvicorn's automatic forwarded-header processing and access log disabled. Keep `DEX_DATABASE_SSLMODE=require`; [PostgreSQL connection guidance](https://render.com/docs/postgresql-creating-connecting) documents TLS. Do not turn off TLS on a hosted connection to work around failure.

[Render request logs](https://render.com/docs/logging) can include URLs. No account-specific disable/redaction control has been verified. Recovery/invite tokens now travel in fragments and CSRF-protected POST bodies, never generated server paths/query strings. Application logs omit requests/provider bodies. Check the account's retention, export destinations and shell-output access; do not enable request-body capture.

1. Verify the selected workspace has no untrusted same-region services. Confirm the displayed costs and resource identity; creation requires owner provisioning because purchases are excluded from this task. Use the exact [Blueprint fields](https://render.com/docs/blueprint-spec), not old Starter/Basic names. Provider API validation remains pending access.
2. Publish the archive to the private registry with digest preservation, then verify both service image fields against `release.json`. Render requires [Linux AMD64](https://render.com/docs/deploying-an-image); the old ARM64 image cannot be substituted. Applying an image tag such as `latest` is not an equivalent qualification target.
3. Create the empty database and secret group. For first boot only, temporarily start the worker image with `/app/.venv/bin/python -c 'import time; time.sleep(86400)'` so the operator can use its private service shell before the schema exists. Leave the web suspended/not serving. This temporary idle command makes no database change or recognition call.
4. Inside that worker shell, generate the seed and migrate it, with the same securely injected staging environment:

   ```sh
   /app/.venv/bin/python -m pokemon_hunter.beta.synthetic --output /tmp/dex-synthetic-seed
   /app/.venv/bin/python -m pokemon_hunter.beta.deployment migrate-copy --path /tmp/dex-synthetic-seed/synthetic.copied.sqlite3
   /app/.venv/bin/python -m pokemon_hunter.beta.deployment check
   ```

   The synthetic generator configures its own local preparation process; the shell retains staging variables for migration. `migrate-copy` refuses any nonempty target. Securely retrieve `/tmp/dex-synthetic-seed/credentials.json` into the operator's password store **before redeploying the ephemeral worker**; do not print it into retained command/deploy logs. Never substitute Mike's source database or historical evidence. If initialization fails, investigate the retained failure and use a new empty target; do not drop data to force a retry.
5. Set the worker command back to the exact command in `render.yaml`, deploy the pinned digest, then deploy the web digest. Verify the database migration and worker heartbeat before accepting web health. Retrieve and retain the actual HTTPS URL, service/deploy IDs, digest and sanitized observations.
6. Subsequent compatible releases use `deployment migrate` only on the existing prepared DB; do not regenerate users or seed again. To reconcile the permitted ten-set package into a separately approved pre-existing staging copy, use `deployment publish-staging-catalog`. This keeps IDs, owned copies, goal membership, source history and spending rows; ambiguous variants fail rather than duplicate. This is not authorization for owner-data migration.

## Hosted observation checklist

These are **all pending**, not local pass labels. Use the two synthetic accounts and record timestamp, candidate digest, target IDs, expected/actual result and sanitized evidence for each:

- Valid public HTTPS certificate, HTTP-to-HTTPS behavior, login/logout, one-use recovery/reissue/revocation, secure host-only session/CSRF cookies, incorrect Host/Origin and spoofed protocol headers. Confirm tokens are absent from provider request URL logs.
- Cross-account inventory/export/photo denial; non-admin catalog review denial; photo consent private/shared/revoked behavior.
- Base/Neo manual search/match, duplicate add, preview/cancel/confirm/retry, exact purchase amount, frozen goal and export. Catalog preview/verify/publish/rollback/republish and request resolution must retain the same physical copy.
- Fixture scan queue/worker/confirmation, cancelled upload deletion, refresh and restart recovery. Mark simulation explicitly. Restart web and worker separately; verify copies, jobs and the retained $0.05 seed reservation persist. Disable scanning with `deployment disable-scanning`; verify new uploads stop while manual entry still works. Never clear spending rows to make a test pass.
- `deployment backup --path PRIVATE_NEW_BUNDLE`; restore with `deployment restore --path SAME_BUNDLE` against a **different empty target**. Compare the returned content manifest, then read back accounts, private photos/consent, catalogs, goals and reservations. Make a new source-side write after backup and prove it remains in the original database. Do not switch the application to the restore target or overwrite the current database.
- Run [the actual phone walkthrough](B5_PHONE_CHECKS.md). Record device observations separately from browser emulation.

For real recognition, first record existing global/account reservations and remaining budget. Use at most six consented labeled images covering clear matches, ambiguous/poor images and unsupported cards, only if the remaining existing $1 global / $0.50 account ceilings allow their $0.05 reservations. Keep expected printing IDs/variants and images private. Compare proposed matches **before manual corrections**; record correct, wrong and unresolved counts separately, each job's latency, returned usage cost (unknown stays unknown), model/version and total reservations. Never refund failed/interrupted calls for evaluation. Set `scan_config.mode=openai` only once the secure key and suitable images exist; missing key leaves fixture/manual labels. Current results: **0 real calls, $0 real spend; correct/wrong/unresolved, real latency and accuracy unmeasured**.

## Actual observations and rollback

| Scope | Obtained result |
| --- | --- |
| Local candidate regression | 198 tests passed in working and clean checkouts; lint/format and recovery JavaScript syntax pass. Existing Starlette deprecation and deliberate HSTS subdomain/preload warnings remain. |
| Catalog | 859 explicit reconciliations; preserved printing IDs including first-edition identity, original provenance, copies, nonempty frozen goals and reservations; rollback/republish tested. Synthetic seed has 991 Pokémon entries + 2 synthetic variants, all 251 named species. No staged prices/artwork/hunt parity claimed. |
| Local PostgreSQL/AMD64 | Synthetic migration, secure-session and account/private-photo isolation checks, content-manifest backup/empty-target restore passed locally. Source hashes inside the final image match the committed runtime; it runs as UID 10001. A new source-side write after backup remained present while the separate restored database retained its earlier snapshot; the $0.05 reservation was unchanged. Exact evidence and preliminary failures remain outside Git. |
| New recovery browser flow | Actual local Chromium at 390px: fragment exchanged, fixed reset URL, password reset and subsequent login passed; request URLs token-free, no JavaScript errors; screenshot inspected. Local test certificate exception, not a public HTTPS or phone observation. |
| Hosted/provider restore/restart | **Not run**: no configured authorized Render target or account credentials. |
| iOS Safari / Android Chrome | **Not run**: no usable device session. See walkthrough for specific access findings. |
| Recognition | **Not run**: no configured key/evaluation image set. Geometric fixtures are not recognition evidence. |

No prior Render-qualified rollback image exists. On a failed first deployment, **suspend web and worker and retain the database**, its new writes and reservations; repair in place or restore only to a separate target for investigation. After this candidate is actually qualified, retain this exact digest as the compatible rollback target for the next release. B4/SQLite and the old ARM64 B5 image are not compatible hosted rollback targets. Data rollback requires reconciliation of post-backup writes, deleted accounts/consent and spend; never restore over the current database.

Next actor: owner/operator supplies the missing existing target/access or provisions the listed paid resources; engineer then applies this pinned package and collects hosted observations. B5 stays open and B6 does not advance. Actual B1 owner provisioning remains a separate operation.
