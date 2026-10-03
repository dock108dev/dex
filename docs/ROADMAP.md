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

1. Run one explicit, bounded Live eBay search in the existing local app to verify
   authentication and Browse API access. Record the outcome without credentials
   or tokens; on failure, retain the sanitized error and resolve it before retrying.
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

## October 3 local verification boundary

Application candidate: `dbaafee7283c9fb81de664738084c69061b16254` on local
`main`; remote `main` matched this candidate before documentation reconciliation.
The running supported CLI server uses the existing private installation at
`/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local`.
Its parent folder had been moved to Trash while the server remained running;
restored the same folder to its original path without replacing or initializing
files. No restart, seeding, ownership change, purchase or bid was performed.

The ordinary Chrome and Safari sessions were signed out. The live pass stopped
at the existing login page before submitting a search: **zero live batches and
zero provider calls**. Production credential configuration is complete, but OAuth
and Browse access are still unverified. No provider failure or retry occurred.
The next action is Mike signing in at `http://127.0.0.1:8011/hunt/`, then continuing
one explicit narrow individual-card batch (for example, Pokémon Base Set Pikachu
58/102, delivered ceiling $25), retaining the eight-query/two-page caps.

Validation: supported private-root `check` passed; 49 isolated tests passed across
`test_beta_live_hunts.py`, `test_hunt_values.py` and `test_ebay.py` on Python 3.14.
Private before/after fingerprints confirmed all 40 database tables and 13 root
files unchanged during this pass; private checkout credentials were preserved.
No fixture-writing browser harness was run against Mike's data. No application
code defect was established or code repair made.

Real-result delivered-price/guide/printing/grade review, explicit reveal, seller
review, saved-hunt reopening, frozen-scope retention and no-call filter changes
remain unverified on live results. Isolated tests are engineering evidence only.
Mike's personal-use acceptance remains pending his feedback. Hosting, phone
access, managed startup, invited users and further recognition remain deferred.
