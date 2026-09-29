# Security boundaries

## Surfaces and trust boundaries

- The authenticated Django app binds to `127.0.0.1:8011`. Its outer middleware
  checks exact Host, loopback peer, Origin and absence of forwarded headers.
  Login, recovery and invitation entry are public; inventory, exports, photos,
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
- The preserved FastAPI collection app is unauthenticated and loopback-only.
  Host/Origin checks restrict browser requests; this is not isolation from another
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
- Staging remains deferred. Its separate configuration requires HTTPS, PostgreSQL,
  secure cookies and explicit proxy/Render ingress assumptions. The container runs
  as a non-root user. These source controls do not establish deployment security.

## Input and browser policy

The shared `security.ebay_url` validator requires HTTPS and ebay.com, and rejects
backslashes, whitespace/control characters, credentials and malformed/nonstandard
ports. Invalid links cannot qualify for watcher alerts and become unavailable in
hunt responses. This prevents URL-parser disagreement from creating unsafe links.

Authenticated schema/type errors return fixed HTTP 400 messages rather than echoing
submitted data or internal errors. Deliberate domain validation messages and
conflict responses remain visible. Both apps share no-store, nosniff, DENY framing,
CSP base/object restrictions and same-origin camera permissions. Inline scripts are
disallowed; existing inline styles are allowed. Denials receive these headers too.
HSTS and Secure cookies are staging-only because local serving uses HTTP.
`X-Robots-Tag` discourages indexing but is not an access-control mechanism.

## Intentional acceptable patterns

| Pattern | Classification / status | Rationale and evidence |
| --- | --- | --- |
| Local HTTP cookies without Secure | Informational, high confidence, accepted for loopback | Strict SameSite, HttpOnly session cookies, CSRF and exact local ingress checks remain; staging enables Secure. |
| Same-origin inline styles | Low, high confidence, accepted | Current templates and rendering use inline styles. CSP continues to prohibit inline scripts; removing styles would require a UI refactor. |
| Request/access logs suppressed | Informational, high confidence, accepted | Local recovery URLs can contain bearer tokens. The separate redacted failure channel records code locations without request URLs or exception payloads. |
| Account-scoped IDs and SQL | Informational, high confidence, retained | Server-side ownership and owner-role checks remain authoritative, including photo evidence and workers; existing isolation tests are retained. |
| Local operator environment/PATH and private roots | Informational, high confidence, accepted trust boundary | A process already running as the same OS user can read that user's files or replace executables. These controls are not a sandbox against a compromised Mac account. |

## Prioritized follow-up and manual verification

1. **Before any external exposure:** staging ingress, TLS, proxy header stripping,
   backup access and invite-only operation need deployment-specific verification.
   Severity high if misconfigured; confidence high in the need for verification;
   status deferred by current local-only scope. Test the actual deployment when
   that scope is authorized; source-only middleware tests are not qualification.
2. **Dependency maintenance:** lockfile and locked installation are retained, without
   a claim that locked packages are vulnerability-free. Severity unassessed; confidence
   high in the verification gap; status deferred. Run a lockfile advisory check
   and assess fixes before a future release rather than updating dependencies blindly.
3. **Broader validation error contract:** remaining domain `ValueError` messages
   intentionally reach clients. Severity low, confidence medium, status deferred
   hardening. Introduce explicit public validation exception types if new adapters
   or externally supplied error messages enter those paths; preserve useful field
   feedback and never expose provider exceptions.
4. **Local operational recovery:** existing worker shutdown timing and legacy
   file-write limitations are documented in [error handling](ERROR_HANDLING.md).
   Severity medium for interrupted operations, confidence high, status deferred
   reliability work. Keep claims/reservations and reconcile persisted operation
   state rather than automatically retrying uncertain provider calls.

