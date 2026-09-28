# B1 — isolated accounts and private inventory

Implemented September 27–28, 2026. **Local engineering verified; actual owner provisioning pending. B1 is not marked technically complete.** Owner acceptance and hosted-beta readiness are separate, unearned gates. B0 evidence at `434e5a1` remains historical; B1 uses a fresh copied snapshot.

## Authentication decision

Django 5.2 LTS provides username/password authentication, password validation/hashing, database sessions, login/logout, CSRF protection and one-use password-reset confirmation. django-axes adds database-backed login throttling: five failures per username or IP, with a 15-minute cooldown. The lockfile pins Django 5.2.17 and django-axes 8.3.1. No password or session protocol is implemented here.

Official documentation checked during implementation:

- [Django authentication, password reset and session invalidation](https://docs.djangoproject.com/en/5.2/topics/auth/default/)
- [Django CSRF and Origin verification](https://docs.djangoproject.com/en/5.2/ref/csrf/)
- [django-axes supported integration](https://django-axes.readthedocs.io/en/stable/2_installation.html)
- [Django ASGI deployment](https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/)
- [Django support and BSD licensing](https://www.djangoproject.com/download/)

Django runs as ASGI under the already-used Uvicorn runtime on Python 3.12+. The B1 app is separate from the legacy FastAPI app; it never mounts legacy routes. Django is open-source, with no auth subscription or per-user fee. This local rehearsal has no purchased service. Hosting, database, backups and external recovery delivery have no selected provider or verified total price; those costs and actual HTTPS operation remain B5 gates. SQLite is retained for this disposable rehearsal, not selected for hosted production. PostgreSQL porting of B0 SQL remains future work.

## Identity and recovery

The controlled local bootstrap creates `admin` before any invite and transactionally binds its Django account primary key to the existing stable B0 `OWNER_ID`. It rejects adoption of an already populated authentication database. Repeating bootstrap preserves both identity and password. Authorization resolves the stable mapping and role; renaming either user does not transfer privileges. There is no public registration or Django admin site.

An operator creates an invited account with an unusable password and an empty private inventory. Invitation setup uses Django's `PasswordResetConfirmView`, `SetPasswordForm` and `PasswordResetTokenGenerator`, with a separate invitation purpose salt. Account activation and token revalidation occur under a database transaction. Reissuing an unredeemed invitation preserves its account identity. Tokens expire after 30 minutes, become unusable after password setting, and are also invalidated by replacement or revocation. Password rules require at least 12 characters and Django's similarity/common/numeric checks.

Recovery is **local operator assisted**: after independently verifying the account holder, the trusted machine operator issues a framework recovery link into an owner-only file. No email is invented, and no message is sent. Issuing a link sets an unusable password, immediately invalidating old sessions and earlier links; completing it restores password login. Account revocation disables login, sessions, outstanding links and queued authorization. Ordinary logout destroys the current database session. Recovery delivery to an external person and hosted account recovery are unverified.

Actual Mike credentials were not available to this run. Copied-data and synthetic rehearsals use random memory-only passwords. They are not actual owner provisioning or owner acceptance. The prepared `owner-local` environment has the copied collection and **no authenticated accounts**, ready for the secure entry below.

## Application boundary and coverage

Every private operation resolves an active account mapping from the verified Django session. Client user IDs, headers and query fields cannot select another owner. Inventory notes are the only implemented mutation; ownership fields are rejected. Inventory read/export, preserved hunt list/detail, archive list and archive-byte download all use owner-scoped queries. File downloads read scoped database bytes, never join an incoming path onto the host filesystem. Catalog review checks the account role but grants no private-collection bypass. Catalog publication remains unavailable.

The photo, scan job, goal and request-evidence workflows are **not implemented**. A shared resource authorization function and worker contract are tested using synthetic rows: workers resolve identity from a stored job and recheck active-account state, then scope each resource to that owner. All corresponding HTTP routes remain unavailable. These are boundary tests, not completed workflow coverage; future writers must use the same boundary and will require feature-specific tests.

B1 binds only `127.0.0.1:8011`, requires the exact local Host, rejects foreign origins, non-loopback clients and forwarding headers, and enables Django CSRF. Sessions are HttpOnly, SameSite Strict, expire after one hour or browser close, and responses are not cached. Same-origin referrers preserve Chrome's form Origin while suppressing cross-site referrers. Cookies intentionally lack Secure only in this hard-bound HTTP loopback profile. There is no hosted configuration. Do not expose it through a proxy; qualify HTTPS and Secure cookies before B5. Request/access logging is disabled so setup-link URLs do not enter ordinary logs.

## Local operation

Run from the repository. Keep every root outside the checkout, new and private. Initialization refuses an existing directory. It makes a separate SQLite backup of the supplied **B0 copied rehearsal database**, then adds Django's tables. It does not connect authentication to ownership JSON.

```sh
uv sync --frozen --extra dev
uv run python -m pokemon_hunter.beta.cli --root "$B1_ROOT" init \
  --copied-inventory "$B0_COPIED_INVENTORY"
uv run python -m pokemon_hunter.beta.cli --root "$B1_ROOT" bootstrap
uv run python -m pokemon_hunter.beta.cli --root "$B1_ROOT" check
uv run python -m pokemon_hunter.beta.cli --root "$B1_ROOT" serve
```

`bootstrap` prompts twice without echo. Never put a password in arguments or a document. Open `http://127.0.0.1:8011/login/`. The header always identifies the isolated rehearsal. Do not run `init` again against the prepared root.

Local operator commands (links must be written inside the private root, to a new file):

```sh
uv run python -m pokemon_hunter.beta.cli --root "$B1_ROOT" invite collector \
  --link-file "$B1_ROOT/invitation.txt"
uv run python -m pokemon_hunter.beta.cli --root "$B1_ROOT" recovery admin \
  --link-file "$B1_ROOT/recovery.txt"
uv run python -m pokemon_hunter.beta.cli --root "$B1_ROOT" revoke collector
```

Open a link privately; do not paste it into chat or logs. The operator is trusted with the local database. No web user, including catalog admins, has these account-management powers. Revoked accounts stay disabled; recovery does not silently reactivate a revoked account. A separate audited reactivation workflow is not part of B1.

## Verification and evidence

Synthetic tests cover two independent sessions; anonymous/forged/guessed access; cross-user reads, writes, downloads and exports in both directions; no admin bypass; CSRF and Host/Origin restrictions; expiration/replay/replacement of invitation and recovery links; weak passwords; logout, expiry and revocation; repeated bootstrap; owner-first provisioning; username-independent privileges; failed-login lockout; and future-resource/worker boundaries. Existing tests remain included.

A real Chromium rehearsal uses independent browser contexts, sees the preserved owner collection and initially empty second account, then creates a synthetic member record and denies the owner's read/write/export access to it. It exercises browser invitation, recovery and logout. The reproducible script deliberately requires a fresh environment, uses generated memory-only credentials, and stores only private reports/screenshots. Install its optional test dependency with `uv run --with playwright`; Google Chrome must be installed. It does not use the owner's browser profile.

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
node --check web/app.js
uv run --with playwright python scripts/verify_b1_browser.py --root "$B1_ROOT"
```

Private evidence is retained outside Git under `/Users/michaelfuscoletti/dex-private/b1-20260927/`: fresh snapshot/manifest; copied import, exact comparison and restore; browser reports/screenshots; test/check logs; final preservation report; and `handoff.json` containing exact tested/pushed commit and clean-checkout results. Failed browser attempts remain distinct from the final result. Initial Chrome sign-in exposed a referrer/Origin conflict; the final candidate repairs it. A subsequent browser harness failure was synchronous database access inside Playwright's event loop; the harness now performs that operator action in a separate thread.

The source comparison checks byte hashes for owner/config/source/data/frontend files and full logical contents for live SQLite databases. It also reads the restored legacy app's collection, exports and hunts without modifying the live app. All identities/attributes, first-edition selections, hunts and Vintage 251 are compared again after authentication binding. Unresolved variants remain unresolved.

## Remaining gates and next actor

- **Mike:** enter the real owner password through the prepared local bootstrap and sign in. Until then, actual owner provisioning is pending and B1's full technical exit is not claimed.
- **Engineer after provisioning:** verify the bound identity and preserved collection under that account, record the exact candidate and update B1 status.
- **Later stages:** full collection/goal/photo/job/request workflows, external recovery delivery if selected, hosting/HTTPS, cost and rights qualification, owner acceptance and pilot release. No deployment, cutover, external invitation/recovery message or paid recognition call occurred.
