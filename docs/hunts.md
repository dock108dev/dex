# eBay hunts

The authenticated localhost app supports explicit eBay searches with the same
Browse client as the original app. Search results are private account-scoped
snapshots. The app never buys or bids, and a listing never adds an owned card.

## Search and save

Open **Hunts** at `/hunt/` for lots or **Missing singles** at `/missing/`. Select
**Find bargains** or **Fill a collection goal**, Live eBay or Sample cards, a
search pool, optional collection goal, focus and delivered budget in USD. An
optional search phrase can direct a card or lot search. Search starts only when
you request it. Bargain searches include owned cards; goal-filling searches use
the goal's frozen checklist and your current active copies. Without a goal, the
default collection scope remains Vintage 251.

The search pools are known lots, individual cards and mystery/repacks. Default lot
and mystery searches use Pokémon query pools. Goal-targeted singles use the
selected published game, set, card name and number, including Trainer/Energy or
other game entries when present in the catalog. Focus can narrow Pokémon searches
to Kanto, Johto, missing rares or cheap bulk. A goal's game, sets, card type,
rarity and Pokédex filters come from the saved goal builder. Open a goal's missing
search to use that scope directly.

Each batch saves automatically. **Next eBay batch** continues the captured search
purpose, phrase, goal, pool, focus and budget rather than silently using changed form choices. Saved
finds at `/finds/` can be reopened without a new provider call; they are re-scored
against current ownership and spoiler reveal starts hidden again.

Titles, contents and seller links stay hidden until explicit reveal. Exact hits
from live listings are seller-text candidates, not photo-verified card identity.
Unknown and mystery contents remain unknown. Check the revealed seller page for
current availability and condition.

## Price comparisons

Results show the delivered price, guide reference, difference/discount, evidence
basis, priced-card coverage and source dates. **All search results** preserves
results without guide coverage. **Below guide reference** filters the saved
results without calling eBay again. A low price against a benchmark needs seller
review; it is not an established bargain or profit estimate.

Identified singles use an ungraded guide unless seller grade and grader match
supported graded evidence. Unknown edition uses a clearly conditional standard
edition assumption. General grade 7/8/9 scenarios do not silently become PSA
grade matches; the existing PriceCharting grade-10 reference supports PSA 10.

Identified lots use a conditional standard, ungraded baseline. A first-edition or
graded mention for one card never applies to every card in the lot. Fully priced
identified contents can be summed; partial identification/pricing shows only a
subtotal and leaves other contents unvalued. For known lots with no identified
cards, an average of current guides in the selected catalog scope times the
stated card count is shown as a **benchmark**, with its coverage. It does not
predict the contents or appraise that listing. Mystery, sealed and unopened
unknown contents do not receive this benchmark.

Reference values require current, nonnegative, finite USD evidence from a valid
HTTPS source and a date no older than 30 days. Comparisons use retained guides and
explicitly refreshed project `config/market_values.json` snapshots, selecting the
newest valid observation. An equal-date refreshed snapshot takes precedence.
Searching does not refresh guides. Per-card identities and guide links appear
only after reveal. Auction comparisons use the current bid, which can change;
it is not a settled purchase price. Tax, fees and resale proceeds are not modeled.

## Local provider settings

Use `.env.example` for `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` and optional
`EBAY_DELIVERY_POSTAL_CODE`. Process environment takes precedence over the checkout's
`.env`. App ID is the Client ID; Cert ID is the Client Secret. Select the matching
`environment` in `config/settings.yaml`: the committed example uses `production`.
Sandbox credentials and Production credentials are separate. Marketplace,
destination and bounded search limits share the original watcher's settings model.
The authenticated app reads only eBay credentials from `.env`; staging live hunts
are disabled. Missing credentials disable live search; sample hunts remain available.

## Production access

Credentials do not establish OAuth or Browse eligibility. Resolve disabled keysets
and application access in the eBay developer portal before requesting live searches.
An authentication failure does not establish a specific account-policy cause.
This repository has no account-deletion notification callback or public receiver.
Saved snapshots persist provider data; changing provider compliance or retention
requires a separate integration design. Consult the provider's current requirements
for the selected application. The app does not activate keysets automatically.

[Historical provider observations](history/2026-10-03-VERIFICATION.md) concern exact
older candidates and one installation. They do not establish access for a new
clone. Populated Production comparison, reveal and seller-review behavior still
needs live evidence. Local mocked-provider checks cover engineering behavior only.
