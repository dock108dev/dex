# Product roadmap

The current scope is a single-user localhost collection and eBay hunting app.
Accounts, physical copies, binders, imports/exports, undo and catalog requests are
implemented. The original app and existing stores remain supported; there is no
automatic data cutover.

The personal-beta priority is bargain hunting on eBay from the authenticated app.
Search individual cards or lots, compare the delivered price with dated guide
references, and inspect the comparison's basis and coverage before revealing a
seller listing. Collection goals can narrow the search to missing targets; owned
cards remain useful bargain-search candidates.

The product loop is: choose a search or optional goal, search eBay, compare prices,
review seller evidence, and save/reopen a hunt. Unknown lots can have a transparent
scoped catalog-average benchmark; identified lots can have a complete sum or a
clearly labeled partial subtotal. A benchmark does not predict actual contents
or establish the lot's value. Mystery and sealed unknown contents are unvalued.

Goals use a reusable filter builder: available game, selected card sets, card
type, rarity and, for Pokémon, a Pokédex range within the current #001–251 species
catalog. Completion can count species or individual printings. Original 151,
Vintage 251 and Johto are convenient starting points for the same builder; a
goal's game, sets and other filters remain editable before saving. One example
is collecting species #001–151 from selected Pokémon card sets while the overall
Pokédex remains #001–251.

The current build adds authenticated live eBay search, price comparisons and the
expanded goal builder. Local checks cover price/edition/grade matching, unknown
contents, filtering, account-scoped saved hunts, missing-target searches and
provider failures. As of October 3, 2026, both required eBay application credentials
are present in the private, Git-ignored checkout `.env`, and the configured
environment is production. Actual provider access and Mike's personal-use review
remain open. Simulated
provider tests do not establish current listing availability or bargain quality.

## Next steps

1. Resolve the production OAuth HTTP 401 (`invalid_client`) by verifying the
   active matching Production application keyset privately. No further live
   attempt is authorized by the completed October 3 initial/retry allowance.
2. Review real results for delivered-price comparisons, guide coverage and seller
   evidence, then save/reopen the hunt and check spoiler reveal. Mike's personal-use
   review remains pending until this real-result workflow is exercised.

Credential entry is complete; a successful live search is still pending. The app
uses App ID (Client ID) and Cert ID (Client Secret); Dev ID is not required.

Photo upload and recognition code remains available. Further photo integration
and accuracy evaluation are deferred until there are other users or collection
coverage expands beyond the current Pokémon focus. They are not prerequisites
for this personal beta.

Hosting, LAN access, managed startup, real-device qualification and invited-user
rollout are deferred. Retain the optional staging implementation without treating
its unfinished deployment requirements as blockers for local use.

Preserve uncertainty, confirmation before ownership changes, intentional duplicates,
spending reservations, source provenance and safe undo. Search results never add
owned cards automatically. Navigation and wording should support the collection →
goal → hunt loop without overlapping destinations.

[Current setup](local-development.md) · [Catalogs and goals](catalogs.md) ·
[Historical decisions and candidate evidence](history/README.md).

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
