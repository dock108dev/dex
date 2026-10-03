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

As of October 3, 2026, the local production eBay search path has application
credentials configured: both required values are present in the checkout's
private, Git-ignored `.env`. Credential presence was checked without exposing
values. The explicit live pass failed production OAuth with HTTP 401 (`invalid_client`);
Browse API access remains unverified;
real provider results and Mike's personal-use review remain open.
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

## October 3 live verification outcome

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
