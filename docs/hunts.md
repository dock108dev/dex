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

Set `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` in the server environment or private
checkout `.env`, using `.env.example` for key names. Never paste credentials into
chat or commit them. Server environment values take precedence. The authenticated
app reads only these credentials and optional `EBAY_DELIVERY_POSTAL_CODE` from
`.env`; recognition and webhook keys are not loaded.

`config/settings.yaml` selects production or sandbox, marketplace and delivery
destination. Sandbox status is labeled and does not establish real offer
availability. The page reports configuration status without exposing credentials.
Configured credentials alone do not prove successful eBay access. Live hunts are
available only in the local profile.

## Coverage and evidence limits

A batch runs at most eight planned queries, with at most two provider pages per
query and buying option. Coverage shows the executed portion and whether provider
warnings limited results. Longer plans can continue in another explicit batch.

Delivered budget uses known item price plus known shipping and excludes tax.
Listings marked unavailable or lacking sufficient price/shipping information
are excluded from results. Prices and availability can change after a search.
Recommended bids remain unavailable when condition, complete contents or sourced
raw-price evidence is missing. A guide comparison or benchmark does not establish
those inputs.

Provider failures show a safe error and require an explicit retry. They do not
silently substitute sample results. Local simulated-provider tests qualify the
application behavior; actual eBay access and Mike's personal-use review remain
separate checks.
