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
Search `demo` controls require actual JSON booleans and continuation offsets require
integers, excluding booleans, strings and fractional values. Saved requests already
use normalized booleans/integers; this does not reinterpret stored hunt state.
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
