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
provider failures. As of October 3, 2026, the current private credential pair
and configured environment are Sandbox. Sandbox OAuth/Browse succeeded with an empty result.
The developer portal confirms the dex Production keyset is disabled pending
account-deletion notification compliance. Production results and Mike's
personal-use review remain open. Simulated provider tests do not establish
current listing availability or bargain quality.

## Next steps

Sandbox authentication and Browse access succeeded on October 3; the narrow
Pokémon query returned an empty saved snapshot. Resolve the disabled Production
keyset through the [exact setup steps](hunts.md#production-setup-gate-october-3-2026)
before one explicit populated-result pass. Nonempty comparison/reveal/seller-review
verification and Mike's personal-use acceptance remain open. See the outcome below.

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
