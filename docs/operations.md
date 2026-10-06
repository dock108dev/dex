# Optional staging operations

The supported product target is localhost. The repository also retains a PostgreSQL
staging implementation, container and deployment examples. These are not a qualified
public deployment or a requirement for local development.

`beta/deployment.py` supplies `check`, `web`, `worker`, `migrate-copy`, backup,
restore, retention and diagnostics commands. Inspect its `--help` before use.
Staging uses PostgreSQL 17, one web process and one independent worker. Local
normalized photos become private database bytes, so database backup includes them.

## Required environment

- `DEX_PROFILE=staging`, `DATABASE_URL`, `DEX_SECRET_KEY` and `DEX_PUBLIC_ORIGIN`.
- `DEX_INGRESS=proxy` with explicit `DEX_PROXY_NETWORKS`, or the retained Render
  ingress configuration. The backend must not be directly publicly reachable.
- `DEX_DATABASE_SSLMODE` defaults to `require`; disabling database TLS is supported
  only for a loopback database.
- `OPENAI_API_KEY` only for explicitly configured API recognition. CLI recognition
  is not supported by the copied staging importer.

The reverse proxy must replace forwarded headers and provide HTTPS matching the
configured origin. Secure cookies, CSRF and exact Host/Origin checks remain enabled.
`/healthz/` checks schema, scan configuration and worker heartbeat; unavailable
prerequisites return 503. Diagnostics contain aggregate state, not private content.

## Data and deployment boundaries

Use a synthetic seed and an empty database for rehearsals. `migrate-copy` consumes
a compatible copied inventory plus scan-config sidecar; it refuses an occupied
target and compares imported rows. It is not an arbitrary SQLite converter.
Backup and restore preserve identities and spending reservations. Restore requires
an empty target; never reset reservations as part of recovery.

`deploy/Dockerfile`, `deploy/render.yaml` and the release manifest describe retained
infrastructure. A recorded image identifies its historical source, not current
uncommitted changes. Any rebuilt image needs its own identity and affected checks.
The loopback rehearsal proxy and browser certificate exceptions do not establish
real-device TLS trust. Hosting, ingress, startup/restart behavior, independent
backup storage and real-device operation remain unverified for a new deployment.

Detailed historical procedures and exact candidate records are retained in
[the operations record](history/2026-09-28-B5_OPERATIONS.md). They describe historical
procedures and candidates; use the current configuration requirements above.

## Current container boundary

The retained Dockerfile copies `config/catalog-imports` only. Current species and
coverage code also reads the hash-pinned `config/sealed/2026-10-04/package.json`
and `config/catalog-pipeline` profiles; these inputs are absent from that image.
Do not treat the historical container as a runnable current beta candidate.
A separate container update must explicitly include the required public inputs
in its build context and COPY steps, then qualify offline species/coverage loading
and staging behavior. The supported local checkout workflow remains independent.
