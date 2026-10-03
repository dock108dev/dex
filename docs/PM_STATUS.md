# Product status

The [roadmap](ROADMAP.md) owns current scope and priorities. The personal beta is
for Mike on localhost, with the existing collection preserved.

Current build: authenticated eBay bargain search, delivered-price comparisons
against dated guides, and reusable collecting-goal filters. Bargain searches can
include owned cards; filling a goal is a separate search purpose. Identified card
comparisons, partial lot subtotals and catalog-average benchmarks retain their
different evidence limits. Auction comparisons use the current bid, before tax.

Goal filters cover available game, selected sets, card type, rarity and Pokémon
Pokédex range, with species or printing completion and direct missing searches.
The current Pokémon species catalog ends at #251; Original 151 is one preset
within the general goal builder.

Current environment is Sandbox, with a privately checked Sandbox-marked App ID
and both required credentials present. The running server has no eBay credential
overrides. Sandbox OAuth and Browse succeeded, but the narrow $25 query was empty.
The dex Production keyset is visibly **disabled** in the authenticated developer
portal; its account-deletion endpoint and verification token are empty, exemption
is off and Send Test Notification is disabled. The alert email is present.
Earlier Production OAuth returned HTTP 401 (`invalid_client`); that response alone
does not establish its historical cause. Production Browse access remains unverified.
See the [Production setup gate](hunts.md#production-setup-gate-october-3-2026).
Local simulated-provider checks do not establish current listing availability,
provider access or actual bargain quality. Guide comparisons use retained evidence
and explicitly refreshed project snapshots, selecting the newest valid record
with a maximum age of 30 days. Search does not automatically refresh price guides.

Local validation passed: 322 regression tests, then all 32 pricing tests after the
final grade-parser guard. Desktop and 390px Chromium checks use intercepted
provider responses; they do not establish actual eBay delivery or device behavior.

Further photo integration and recognition evaluation are deferred until there
are other users or broader collection coverage. Existing photo code and data
remain preserved.

No hosting, invited-user or real-device readiness claim follows from local tests.
Historical delivery results remain tied to their original candidates in
[engineering history](history/README.md).

## October 3 production verification outcome

First application candidate: `dbaafee7283c9fb81de664738084c69061b16254`.
Repaired/restarted application candidate: `17306fee355091bed082527bee02a01e26cf4f01`
on local main. The running supported CLI server uses the same private installation
at `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local`.
Its parent folder had been moved to Trash while the server remained running;
restored the same folder to its original path without replacing or initializing
files. Mike signed in through ordinary Chrome before the live pass.

Ran one explicit Live eBay individual-card batch for
`pokemon base set pikachu 58/102`, Find bargains, Vintage 251 scope, All focus,
$25 delivered ceiling. The first attempt failed in OAuth before Browse. The
existing content-free diagnostic did not identify the HTTP status, so a bounded
repair now exposes only stage, HTTP status and allowlisted OAuth error codes;
arbitrary response text, credentials, tokens and request details stay hidden.
After local verification, restarted through the supported launch path with the
same private root and retained authenticated session. The single explicit retry
returned **eBay OAuth HTTP 401 (`invalid_client`)**. Stopped live attempts.

Outcome: two submitted batches (initial plus one retry), zero successful batches,
no Browse search reached and no results saved or samples substituted. Credential
presence/production configuration is confirmed; production authentication failed.
Browse entitlement remains untested. The precise owner action is to verify the
active Production application keyset and matching App ID (Client ID)/Cert ID
(Client Secret) in the private configuration. Dev ID is not used. An environment
or keyset mismatch is possible, not established. See the official
[eBay credential mapping](https://developer.ebay.com/api-docs/static/oauth-credentials.html).
Do not make further live attempts until that external credential issue is resolved.

Validation: all 328 regression tests passed on Python 3.14 (one upstream Starlette
TestClient deprecation warning); Ruff, source compilation, diff whitespace checks
and supported private-root `check` passed. All 40 tables and 13 root files were
unchanged across repair/restart/retry. Before the live pass, the only changes from
ordinary owner login were auth/session/access-log records and their SQLite
sequence. Collection, photos, source evidence, goals, saved hunts, reservations
and secrets were preserved. Sanitized diagnostics and preservation fingerprints
are retained privately under `dex-private/ebay-live-20261003`, outside Git.
No fixture-writing browser harness targeted Mike's data. No purchase, bid or
ownership change occurred.

Real-result delivered-price/guide/printing/grade review, explicit reveal, seller
review, saved-hunt reopening, frozen-scope retention and no-call filter changes
remain unverified because authentication produced no results. Isolated tests are
engineering evidence only. Mike's personal-use acceptance remains pending his
feedback. Hosting, phone access, managed startup, invited users and further
recognition remain deferred.

## October 3 Sandbox follow-up

Mike updated credentials privately to Sandbox. Selected `environment: sandbox`
in `config/settings.yaml`; application code is unchanged from tested candidate
`17306fee355091bed082527bee02a01e26cf4f01` (documentation base `4360ac1`).
The same running private-root app/session was used, without restart or seeding.
One explicit Sandbox batch searched `pokemon base set pikachu 58/102`, individual
cards, Find bargains, All focus, Vintage 251 scope, delivered budget $25.
**Sandbox OAuth and Browse succeeded**, returning zero raw listings and zero
filtered results. One of one planned queries ran, within the existing eight-query
and two-page caps; no coverage warning or further query batch was reported.
No retry or additional query was made.

The empty snapshot was saved, opened from Saved finds with the `eBay sandbox
snapshot` label, and switched to Below guide reference. The original query,
purpose, pool, focus and $25 budget stayed visible. Reopening uses the saved
projection; comparison filtering is browser-only. Neither path invokes provider
search, as verified by source inspection and the previously passed isolated replay
tests. This empty-result pass cannot exercise actual comparison, reveal, seller
review or spoiler reset on populated results. It does not qualify production
availability or bargain quality. Production OAuth and notification setup remain
unresolved; personal-use acceptance remains pending Mike's feedback.

Supported private-root check and diff whitespace check passed. The earlier 328
regression tests remain applicable to unchanged application code. Preservation:
38 unaffected database tables and all 13 root files unchanged; only expected
new saved-hunt/import-batch records were written. Private sanitized evidence is
retained in `dex-private/ebay-sandbox-20261003`, outside Git. Credentials untouched.

## October 3 Production setup audit

The authenticated portal confirms the dex Production keyset is disabled for
account-deletion compliance. Its endpoint/token are empty, exemption is off,
alert email is present and Send Test Notification is disabled. Current local
credentials/configuration remain Sandbox. No new Production call was made;
populated workflow and Mike's acceptance remain pending. No credentials, provider
settings, app source or external settings were changed. The supported private-root
check passed; all 40 tables and 13 root files, plus `.env` and provider settings,
were unchanged. Audit base is `ca4dde5baa18fa05f7c0a48bd9e175886ba628ac`;
application source is still `17306fee355091bed082527bee02a01e26cf4f01`.

[Exact setup, owner action and single queued search](hunts.md#production-setup-gate-october-3-2026).
The current saved-snapshot flow persists eBay data and cannot use the documented
non-persistence exemption. No public callback exists; hosting remains deferred.
Mike should ask Developer Technical Support for the applicable activation/access
path before changing credentials. Sanitized evidence is retained outside Git in
`dex-private/ebay-production-setup-20261003`. Engineering checks do not supply
personal-use acceptance.
