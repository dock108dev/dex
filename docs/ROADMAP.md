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
provider failures. Current local eBay configuration lacks application credentials;
actual provider access and Mike's personal-use review remain open. Simulated
provider tests do not establish current listing availability or bargain quality.

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
