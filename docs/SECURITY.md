# Security boundaries

## LOCAL-AUTH-01 delivered policy — October 17, 2026

Ordinary loopback local authentication uses persistent 30-day Django sessions with
at most hourly renewal on authenticated successful requests. Renewal retains the
session key/navigation binding and avoids ordinary SQLite writes between renewals.
Django login still cycles untrusted keys; logout, password/recovery revocation and
account isolation remain enforced. HttpOnly, SameSite Strict, CSRF/POST logout,
loopback Host/Origin restrictions and private-content clearing remain unchanged.
Staging explicitly retains 3,600 seconds, browser-close expiry and no renewal.
Longer authentication confers no longer Hunt/review lease, source expiry or budget.

The launcher keeps the existing secret/cookie identity and canonical loopback
origin, requesting OS default browser reuse. Engineering browsers require separate
user-data stores; port differences do not isolate cookies. Owner-session absence
is not evidence of profile misuse. See qualified installed evidence (local evidence: `reports/local-auth-catalog-capacity-20261017/browser-diagnosis.md`).

## HUNT-11 offline reference boundary

The new retained-file adapter has no network, admission, source-registry write or
activation capability. It rejects ambiguous mappings, duplicate JSON keys,
unbounded amounts, unsafe relative paths, partial input and finite byte/row/time
overruns. The operator helper reuses read-only audit interfaces and requires
private managed inputs; default execution writes only metadata outside the actual
root. Explicit staging independently checks the reviewed contract digest, current
release and unchanged catalog, preserving other sources through existing snapshot
validation. Staging grants no source rights and never changes the active pointer.
Fixture rights remain synthetic evidence. Managed price-tree exclusions,
independent revocations and consumed Hunter accounting remain unchanged. The
customer's disabled acquisition choice persists; no source or runtime was enabled.

## Everyday Hunter delivery — October 17

HUNT-09/10 adds owner-only session/CSRF policy selection with strict fields,
independent root/account binding, captured parents and shared durable daily limits.
The append-only hash chain and separately fsynced tail anchor detect missing,
truncated or mismatched accounting; admission is durable before transport.
Dispatch/publication enforce pause, withdrawal, expiry, reductions and current
account authority. No reset/refund or HTTP package-rebind endpoint exists.
Routine package compatibility is qualified against an unchanged semantic contract;
changed acquisition behavior requires renewed owner selection.

The exact installed successor passed 772 focused offline tests, real-process
shared admission cases and ordinary-policy Chromium checks on disposable data.
Targeted Bandit scanning of changed Hunter/matching modules reported zero findings.
No new hosted-CI or dependency-advisory result is claimed. The owner left genuine
acquisition disabled; no ordinary policy, provider request or source refresh was
selected. Prior source rights and consumed ledgers are preserved. See
[policy operations](operations.md#everyday-hunter-policy) and the local
`reports/hunt-09-10-20261017/closeout.md` for exact scopes.

## Surfaces and trust boundaries

- The Django collection app binds to `127.0.0.1:8011`. Its outer middleware
  checks exact Host, loopback peer, Origin and absence of forwarded headers.
  Canonical Pokémon browsing, allowlisted published card details, general Pack
  lookup, the eBay explanation, login, recovery and invitation entry are public.
  Public views do not select an account or read private ownership. Inventory, exports, photos,
  operations and scan jobs require a session plus an active mapped account.
- `store.principal`, `store.verified` and account-scoped SQL are the ownership
  boundary. Client IDs are selectors, not authorization. Catalog import,
  publication and review require the owner role. Sharing private photo evidence
  requires explicit submitter consent. Database values are passed as parameters;
  dynamic table/column choices come from internal allowlists.
- Django owns password hashing, password validation, reset tokens, sessions and
  CSRF. Axes limits login attempts. Invitations and recovery have distinct token
  purposes; reissue invalidates previous tokens/sessions. Local operator commands
  are privileged and are not exposed as anonymous HTTP routes.
- The original FastAPI collection app is unauthenticated and loopback-only.
  It accepts only `localhost` or `127.0.0.1` with a valid optional port, a loopback
  client address, no forwarded headers and a matching Origin when present.
  Duplicate Host headers and the test hostname `testserver` are rejected.
  These checks restrict browser requests; this is not isolation from another
  local process. Do not expose that app to a LAN or proxy it publicly.
- Uploads are private database bytes. Image validation bounds size, dimensions and
  formats, rejects animation, and re-encodes images without metadata. Downloads
  authorize the record rather than concatenating an untrusted filesystem path.
- Workers derive the account from durable jobs, recheck account state, and keep
  provider work separate from inventory confirmation. Recognition may send photos
  to OpenAI through the explicitly configured provider. CLI subprocess arguments,
  environment, temporary-directory permissions and execution restrictions remain
  as documented in [photo configuration](photo-entry.md). There is no automatic API
  fallback or spending reset.
- eBay and guide data, uploaded images, imports, model output and seller strings
  are untrusted. Templates/JavaScript escape display text; catalog identities are
  generated internally. Seller links receive a separate server-side URL policy.
  There is no payment endpoint or third-party callback/webhook receiver. Optional
  legacy notification delivery is outbound and operator-configured.
- The optional staging profile requires HTTPS, PostgreSQL,
  secure cookies and explicit proxy/Render ingress assumptions. The container runs
  as a non-root user. These source controls do not establish deployment security.

## Input and browser policy

The supported Django local, staging and synthetic-browser launchers use
`beta.asgi.get_asgi_application`. In the local profile it checks the exact Host,
loopback peer, Origin and absence of forwarded headers before reading the body or
entering Django. Missing/duplicate Host, duplicate Origin and empty/foreign Origin
are refused with a fixed 403 carrying the shared security headers. Requests without
Origin remain supported for ordinary navigation and local clients. The local
middleware repeats the shared policy for defense in depth and alternate callers.
Staging retains its separate trusted-proxy middleware policy; local ingress checks
do not replace staging qualification. The wrapper also bounds declared and streamed
request bytes before Django buffers them or runs middleware/views. Ordinary requests use
`DATA_UPLOAD_MAX_MEMORY_SIZE` (16,384 bytes for account-only roots; 2,000,000 for
collection/staging roots). Enabled `POST /api/scans/` allows 16,100,000 bytes,
including multipart overhead. Photo-batch upload/retake requests allow 8,100,000
bytes; each photo has a separate 8,000,000-byte validation limit. Bulk save/parse
requests allow 32,000,000 bytes for JSON expansion, while parsed text remains
limited to 1.5 MB and manual drafts to 2,000 rows. These larger allowances apply
only to their enabled POST endpoints. Oversized bodies return a fixed 413 and close Django's temporary
spool; invalid/duplicate Content-Length values return 400. Limits apply without
Content-Length and cannot be bypassed by understating it. Custom launchers that
call Django's factory directly bypass this guard. This is a per-request size bound,
not a request-duration, connection-concurrency or aggregate disk quota.

The shared `security.ebay_url` validator requires HTTPS and ebay.com, and rejects
backslashes, whitespace/control characters, credentials and malformed/nonstandard
ports. Invalid links cannot qualify for watcher alerts and become unavailable in
hunt responses. This prevents URL-parser disagreement from creating unsafe links.

Authenticated schema/type/domain errors return fixed HTTP 400 messages rather than
echoing submitted data or internal errors; conflicts return 409. The original app
returns fixed 422 schema errors and exposes only its dedicated ownership-validation
messages as 400. JSON mutation parsers require `application/json` (charset
parameters are permitted); other media types fail before mutations or provider
construction. Body-free original-app reveal operations remain supported.
The original app's search `demo` controls require JSON booleans and continuation offsets require
integers, excluding booleans, strings and fractional values. Saved requests already
use normalized booleans/integers; this does not reinterpret stored hunt state.
Both Shopping comparison routes also require a JSON boolean for optional `save`.
Only `true` requests persistence; `false` or omission calculates without saving.
Invalid save intent is refused before comparison evaluation or storage.
Both apps share no-store, nosniff, DENY framing,
CSP base/object restrictions and same-origin camera permissions. Inline scripts are
disallowed; existing inline styles are allowed. Denials receive these headers too.
HSTS and Secure cookies are staging-only because local serving uses HTTP.
`X-Robots-Tag` discourages indexing but is not an access-control mechanism.

## Private files and operational limits

Collection replacements use unique mode-0600 temporary files independent of umask.
The initializer creates new local state exclusively at 0600; new original hunt
databases also use 0600. Symlinked collection-write and hunt-database destinations
are rejected. Failed replacements retain the original and a private temporary
file; inspect that file after resolving the failure. Existing databases, exports
and backups are not retroactively made private. Parent directories also need
restricted access.

Local HTTP uses HttpOnly/SameSite cookies without Secure; staging enables Secure.
Request/access logs are suppressed because recovery URLs can contain bearer tokens.
Redacted diagnostics retain code locations without request URLs or exception data.
A process running as the same OS user can read files or replace executables; these
controls are not an OS-user sandbox.

Synthetic tests cover ingress, account isolation, roles, token expiry/revocation,
CSRF, private files and mocked providers. Actual staging TLS, proxy header
stripping, backup access and PostgreSQL operation require deployment-specific
verification. Locked dependencies are reproducible, not guaranteed vulnerability-free.
Older private files require a permission review independently of source changes.

Endpoint validation uses fixed responses for domain `ValueError`/`TypeError`;
dedicated validation types could better distinguish programming errors. Shutdown
and uncertain writes retain the recovery limits described in
[error handling](ERROR_HANDLING.md). Do not reset claims or spending reservations
merely to retry uncertain provider work.

## Private image adapters

[Image adapters](artwork.md) require checked current account, authoritative
catalog and complete current overlay equality. Local private pages permit only
self plus the exact TCGdex/PokeAPI asset origins in one effective `img-src`.
Public/staging remote references remain excluded. Remote tags escape alt text
and use no-referrer. Private photo descriptors and serving share authoritative
account/job/copy associations and lifetime checks, with private no-store preserved
through security middleware. Rendering starts no provider attempt or collection write.

## Hunter qualification and installed-runtime reconciliation

HUNT-08 delivered the reviewed source probe members and a qualified successor
package to the ordinary installation on October 17. All 237 installed members and
241 wheel RECORD entries match. The reviewed probe changes clarify public endpoint
and response-limit metadata names; no newly demonstrated credential leak is claimed.
The successor changes only ordinary startup, current-process scan admission and
the optional installed Hunter allowance/checks. Its fixed new allocation binds
root, account, exact package, private document bytes, expiry and durable consumed
accounting. Every send and publication rechecks that authority. Invalid or expired
optional authority disables acquisition while collection startup remains available.
Deferred batch recognition is not started by ordinary serving.

The independent review and 312 exact-wheel offline tests passed. Targeted Bandit
retains three MEDIUM/LOW-confidence B608 findings: two fixed-column queries and one
internal placeholder-count query; values remain separately bound. These are
reviewed nonblocking findings, not suppressed scans or a new hosted-CI result.
The new owner-selected installed check consumed all fifteen operations and is
closed. Prior ledgers and source lifecycle remain unchanged. See the
`reports/hunt-08-20261017/closeout.md`.

Hunter's authenticated local reads/actions preserve session/CSRF authority,
private no-store responses, original leases, finite consumed accounting and
independent Stop. Production traversal/detail dispatch remains disabled without a
trusted separately authorized allowance. The source fix revision and current
CodeQL evidence do not update an older installation. Historically HUNT-07 compared selected
security-module/member hashes and dependency identities against actual SHOP-04;
older installed probe modules were an HUNT-08 delivery responsibility, now reconciled above. Absent
photo/bulk modules are not evidence that those new routes are installed.

The supported guarded boundary uses the hash-pinned `scripts/hunter_boundary.py`
bootstrap with an isolated interpreter. Exact installed package members are checked
before application import; dependency bytes, candidate and saved runtime trees,
profile/actions/workers/write set, minimum schema, private configuration and
root/account/origin/plan are checked before setup or workers. It exposes no HTTP
configuration or authorization endpoint and has no authority-creation command.
Private digest-bound runtime-transition selection and exact finite provider-plan
selection are checked independently. Expiration/withdrawal is checked during
dispatch/publication. Production remains disabled outside explicit selection.

Restricted sign-in rejects another account before successful authentication writes;
existing sessions are rechecked against the expected active mapping. Django owns
sessions, CSRF and login throttling. The restricted URLconf enforces selected
routes; only required price lifecycle starts automatically. The minimum supported
SHOP-04 schema's public table/column contract is `hunter_execution_schema.json`;
the exact schema is additionally bound. Incompatibility refuses without migration.
Offline tests use disposable roots/fake transport and establish no live authority.
Ordinary candidate serve starts expiry and, on a photo-enabled root, a scan worker;
it is not permission for a temporary customer runtime swap.
Preserve configuration and independent journals. Keep allowance activation,
current-root execution and permanent installation as explicit distinct decisions.
Fresh query-only preservation captures all current tables without copying private
row values; it does not repair missing historical start-state evidence.

Hunter history retains only session/account/generation-bound opaque navigation
handles. A new authenticated tab cannot enumerate or recover another tab's run;
same-tab reload revalidates the original handle and lease. A missing server run
fails closed without dispatch, rights renewal or content reconstruction. The
[browser retention procedure](hunter-browser-workflow.md) addresses the documented
turn-scoped tooling marks; the historical disappearance has no confirmed cleanup
cause. Offline browser-recovery qualification preserves backend/operator bytes,
customer state and the closed attempt's three consumed records. The minimal
client-only repair preserves HTTP 404 when a missing run returns non-JSON, reaching
the existing unavailable/clear-context path. It adds no recovery dispatch,
authority, durable content, rights renewal or capacity.

## Completion execution binding

The additional fixed `hunt-07-completion-v1` identity is accepted only with its
exact numeric allocation. Production still starts without an active allowance.
The trusted operator verifies the strict completion document and predecessor
linkage; HTTP and environment inputs cannot select plans or limits. Original
proposal/wheel identifiers, closure receipt, root-hashed ledger byte digest and
semantic consumed counts are pinned. Binary shared-lock reads preserve exact
ledger identity, including line endings. The original partial attempt cannot be
restarted, and any consumed completion capacity prevents a replacement Start.

Independent runtime and provider selections must match the new proposal, plan
ID and document digest. Old authorization does not select repaired/new package
bytes. Completion dispatch/publication rechecks predecessor/authorization and the
captured allowance; details resolve it through the matching live parent owner
tuple. Existing session, UTC window, lease, deadlines, Stop, routes, workers and
write set remain authoritative. Handback validates immutable identity and skips
mutable ledger health; it never restores accounting or starts another Hunt.
Offline qualification creates only report/package artifacts and no actual
authorization, completion ledger, provider operation or customer transition.

## Security maintenance review — October 17, 2026

This source review follows Git baseline
`d144265df0eb132d836186a2441c23d9096d2d0b` and the preceding uncommitted error-handling
pass. Existing snapshot scripts/tests, docs, customer installation and all private
state were preserved. This section records source evidence, not installed security
qualification or a claim that the repository has no vulnerabilities.

### Fixed hardening opportunity: reject local ingress before body buffering

- **Category:** resource exhaustion / browser-to-loopback boundary.
- **Severity:** medium; **confidence:** high; **status:** fixed in source.
- **Evidence:** `beta.asgi.BoundedBodyApplication` previously entered Django after
  checking only body size. Django creates/reads its body spool before
  `beta.security.LocalOnlyMiddleware` checks Host, Origin, forwarded headers and
  peer. Thus disallowed requests could consume upload buffering up to each route's
  finite cap (32 MB for bulk), before their eventual denial.
- **Realistic abuse:** a foreign website, where browser policy permits loopback
  requests, or a client with disallowed headers can repeatedly send bodies to
  upload routes. This can waste memory, temporary disk and request capacity.
  Existing per-request limits bound each request; this is not evidence of an
  authentication bypass, cross-account data access or an unbounded single upload.
- **Fix:** share the existing local policy between ASGI and middleware and reject
  before the first body read. ASGI additionally rejects ambiguous repeated
  Host/Origin fields rather than depending on header joining. Blank Origin is
  refused consistently. Valid canonical requests, originless local clients, body
  limits, CSRF, account authorization and staging policy remain supported.
- **Tests:** disallowed Host/Origin/peer/forwarded and duplicate-header cases read
  zero body chunks and never dispatch downstream. A real Django regression fails
  if a foreign-origin request creates any body spool. Canonical IPv4/IPv6 peer,
  staging separation, upload limits, security headers and session behavior pass.

### Intentional acceptable patterns

The inspected trust boundaries include public browsing/authentication entry,
session-authenticated collection and file endpoints, owner catalog/usage actions,
account-scoped SQL, temporary provider workers, normalized photo uploads, browser
rendering and storage, outbound integrations, local configuration/subprocesses and
optional staging ingress. `urls.py`, `store.py`, `accounts.py`, `views.py`,
`collection_views.py`, `catalog_views.py`, `catalog_imports.py`, `scan_views.py`,
`photo_batch_images.py`, `discovery_transport.py`, `codex_recognition.py`,
`staging_config.py` and the shared security modules provide the reviewed controls.

- Authentication/CSRF and framework token generation remain Django-owned. Resource
  selectors are checked against the active account; owner services enforce role
  checks. Public catalog data is distinct from private copies/photos.
- Browser state conveys navigation/preference selectors, not backend authority.
  Display escaping and the existing script CSP remain. Noindex is indexing policy,
  never authorization.
- Loopback HTTP retains non-Secure HttpOnly/SameSite session cookies; staging keeps
  HTTPS/Secure cookies and HSTS. Same-OS-user processes are outside this isolation
  boundary. No hosted authentication stack was added.
- Private archive downloads use authorized database bytes, and static/package
  paths use allowlists. Image normalization and size/dimension limits remain.
  SQL values use parameters; dynamic identifiers are internally selected.
- Provider transport uses fixed official endpoints and finite counted actions.
  No incoming third-party webhook exists. Recognition subprocesses use argument
  arrays, private temporary files and a restricted inherited environment. No
  recognition, source acquisition or external notification was exercised.

These are reviewed design patterns, not a new penetration-test result. No additional
confirmed authentication, injection or secret-leak vulnerability is claimed by this
pass. No credential values were inspected or printed.

### Prioritized remaining work and manual verification

1. **Moderate hardening opportunity — aggregate ingress capacity; needs decision.**
   Even valid local headers or staging requests reach body buffering before
   authentication. Per-request limits do not cap concurrent uploads, duration or
   total spool disk. If actual contention appears, select a connection/concurrency
   budget and receive deadline at the supported server boundary, with cancellation
   cleanup tests. Headers are not proof of a trusted process. Blanket request-rate
   throttling has not been added to ordinary beta use.
2. **Installed successor — manual qualification required.** These source changes
   do not update the recorded installed wheel. Build/qualify a compatible successor
   with current data-preservation evidence before any future delivery. This review
   did not restart, install, migrate or inspect customer state.
3. **Deployment/dependency verification — deferred outside this local pass.**
   Verify real TLS/proxy stripping and backup permissions if staging is selected.
   Run the existing advisory/secret/static CI checks against the exact future
   candidate when publication/qualification is requested. No advisory lookup,
   dependency audit, hosted CI or full security campaign was run; no package
   vulnerability or clean-dependency claim is made. Focused tests reported one
   existing Starlette TestClient deprecation warning, not a vulnerability finding.

Validation: **100 focused tests passed** in `test_asgi_limits.py`,
`test_security.py`, `test_local_sessions.py` and `test_original_security.py`, using
disposable data and in-process clients. Affected Python compilation, Ruff lint and
format checks and diff whitespace validation passed. No live browser walkthrough,
provider request or customer acceptance is claimed.
