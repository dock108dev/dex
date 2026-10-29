# Security boundaries

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
- Workers derive the account from durable jobs and keep photo processing separate
  from inventory confirmation. Codex and OpenAI execution paths are removed; analysis
  requests fail explicitly. Uploads and prior reviews remain private. Future Ollama
  recognition must preserve authorization, revision and publication checks. Historical
  reservations and deletion journals are never reset by provider removal.
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

Audit installed dependencies separately from the checkout. Updating `uv.lock` or
passing source scans does not update a separately installed environment. Apply
compatible runtime updates using the backup procedure in [operations](operations.md).

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

Local authenticated Discovery additionally admits only temporary official-summary
image URLs on the exact `https://i.ebayimg.com` origin, restricted to the checked
image path/extension in `discovery_listing.seller_image`. A page-specific marker
adds that exact CSP origin; staging and other pages do not gain it. Seller photos
are labelled, use no-referrer, retain fixed failure space, and are never downloaded,
stored or exported. Arbitrary URLs, credentials, ports, query strings and fragments
are rejected. This does not grant catalog-image or physical-identity authority.

## Local sessions and acquisition

Local sign-in uses a persistent 30-day session, renewed at most hourly during
successful authenticated visits without rotating the session/navigation identity.
Logout, expiry, account revocation and link reissue invalidate access. Staging uses
its separate one-hour browser-session policy. Hunt leases, source rights and
acquisition limits are independent of sign-in lifetime.

Ordinary Hunter selection is owner-only. Durable consumption is written before
transport and shared across workers. Pause, expiry, package mismatch, corrupt
accounting and clock rollback fail closed. Restoring the app must not restore old
acquisition allowances or price revocations. Temporary results are not saved,
exported or logged. See [operations](operations.md) and
[recovery](ERROR_HANDLING.md).

## PERF-03 private read review

The account-read adapters resolve the server principal on every request and
recheck role/activity plus collection/account/catalog revisions before returning.
All pages, artwork, photo references, evidence and oversized JSON downloads are
independently authorized and private/no-store. Foreign account selectors are
rejected. Public V2 does not import account overlays. Copy display records use an
explicit allowlist; retained possession never authorizes a mutation. Derived
integrity failure returns unavailable rather than falling back to stale data.
See `perf03-account-reads.md` and the isolated logout/account-switch/revocation,
concurrent-write and failure-injection tests. This review is source/local evidence,
not a claim of hosted or installed verification.

## RUNTIME-DEPS advisory review — October 29, 2026

The read-only installed inventory still selects `hunter-poc-20261027`, Python
3.12.15 and package 0.1.0. It is unchanged. A fresh strict PyPI audit of its
installed dependencies returned 55 finding entries across four packages (aliases
and duplicate advisory records are not 55 distinct vulnerabilities):

| Dependency path | Installed | Candidate lock | Audit finding entries |
| --- | --- | --- | ---: |
| HTTPX → certifi | 2026.7.22 | 2026.10.19 | 2 |
| CI pip-audit → CacheControl[filecache] → filelock | 4.0.12 | 4.2.1 | 13 |
| FastAPI → opentelemetry-api | 1.45.0 | 1.45.1 | 1 |
| Dex → Pillow | 12.3.0 | 13.0.0 | 39 |

The checkout already locked these repaired versions before this slice. Retain them;
`tool.uv.constraint-dependencies` now prevents older certifi, filelock and
opentelemetry-api resolution. The existing Pillow >=13 requirement already provides
its floor. No dependency version was upgraded relative to the starting lock. The
candidate's runtime-only installation omits development/audit/browser tools and
therefore filelock; the separate qualification environment includes fixed filelock.
No vulnerability ignore or scanner policy was added.

Authoritative responses were fetched afresh from PyPI for each installed version.
See the [filelock advisory](https://github.com/advisories/GHSA-v4x8-3wr5-3wq8),
[OpenTelemetry advisory](https://github.com/advisories/GHSA-xcq7-p3pf-p88h),
[certifi version advisories](https://pypi.org/pypi/certifi/2026.7.22/json) and
[Pillow version advisories](https://pypi.org/pypi/pillow/12.3.0/json).
Complete returned IDs, aliases, fixed versions and descriptions are retained in
`reports/runtime-deps-20261029/*-advisories.json` and `installed-audit.json`.
The locked candidate audit has zero findings; this does not secure the older
customer installation. Bandit and full-history/worktree Gitleaks results and exact
package identities are recorded in [CI qualification](CI.md#runtime-deps-local-qualification).
An initial scan could not locate Gitleaks; that failed report is retained separately
from the completed run using the repository's retained Gitleaks 8.30.1 executable.

## CI-VERIFY security boundary

October 29 integrated verification restored nested card-return account/goal-version
authorization and the private card-shell cache directive. Existing adversarial tests
retain foreign-account and stale-goal denial; no provider or inference path was
restored. Final fresh Python advisory and worktree/history secret scans have
zero findings; Bandit has 184 visible findings and zero blocking findings under the
existing policy. The runtime-only Python and npm test-dependency audits also have
zero findings. No scanner exclusion or vulnerability ignore was added. Final local
source/package identities and retained reports are recorded in
[CI-VERIFY evidence](ci-verify-20261029.md). Hosted security and CodeQL passed for predecessor `d66e16f`; the subsequent
SQLite planner and connection-lifecycle repairs require fresh exact-candidate security and aggregate results. These checks do not update or establish security of the customer runtime.
