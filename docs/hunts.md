# eBay hunts

The authenticated localhost app supports explicit eBay searches with the same
Browse client as the original app. Search results are private account-scoped
snapshots. The app never buys or bids, and a listing never adds an owned card.

## Navigation

Open Shopping for the existing lot calculator, then use its task bar for eBay
searches, Find missing cards, saved eBay finds, Packs to open, independent pack
lookup and saved pack research. The same bar appears on direct legacy destinations.
Packs to open asks for an existing account-owned goal when no goal was supplied.
Opening these pages does not search eBay, refresh prices, start recognition or
change inventory.

## Search and save

Open **eBay** at `/hunt/`, or **Missing singles** at `/missing/`. Select
**Find bargains** or **Fill a collection goal**, eBay search or Sample cards, a
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

Use [.env.example](../.env.example) for `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` and optional
`EBAY_DELIVERY_POSTAL_CODE`. Nonempty server-process values take precedence over
`.env` at `ebay_hunts.configuration_root()`, which currently returns Django
`PROJECT`, not the private data root or working directory. In a source runtime
this is the checkout; an installed wheel resolves a directory above its package
(for example, the runtime's `lib/python3.12`). `config/settings.yaml` is selected
from that same directory.
App ID is the Client ID; Cert ID is the Client Secret. Select the matching
`environment` in `config/settings.yaml`: the committed example uses `production`.
Sandbox credentials and Production credentials are separate. Marketplace,
destination and bounded search limits share the original watcher's settings model.
The authenticated app reads only eBay credentials from `.env`; staging live hunts
are disabled. Missing credentials disable live search; sample hunts remain available.

Use the existing application's matching credential pair privately. Do not put secrets
in command arguments, logs or chat. Refresh authenticated status to check the running
process; another shell's configuration does not prove what the server inherited.
Changing environment values requires a normal server restart. A configured status
establishes credential presence, not OAuth success, access rights or remaining quota.

## Discovery integration constraints

The hunt reference path reads legacy parity evidence and optional
`PROJECT/config/market_values.json`. It does not consume the private Shopping
snapshots described below. Source identity, condition/edition compatibility, dates
and comparison/storage rights need independent validation before connecting them.
Removable prices and derived discounts cannot enter permanent history without
surviving save rights. Unknown language, edition, finish and condition stay
conditional or unpriced. Literal grader and grade are independent of generic guide
scenarios.

A hunt batch can dispatch up to eight queries across two buying options and two
pages each, with transport retries and 401 reauthentication. Successful batches
persist raw listings automatically. There is no durable consumed-attempt ledger
for failed hunts or independent hunt Stop. Search is a multi-operation workflow;
it is unsuitable as a one-request access probe. Unknown shipping is excluded from
hunts rather than shown as an incomplete comparison.

Applicable provider access, request allowance and storage/derivative rights must
be established for the selected application. Saved history does not confer those
rights. Consult current provider terms before live use; local credentials and
mocked responses do not establish authorization. Reopening a save does not refresh
its contents or renew its age.

The current eBay HTTPS validator checks link safety; it does not parse item IDs
or load pasted listings. The client supports REST-item details, but no legacy-ID
conversion or pasted-listing route is exposed. Automated sold comparables and
assisted listing/lot entry are unavailable.

## Production access

Credentials do not establish OAuth or Browse eligibility. Resolve disabled keysets
and application access in the eBay developer portal before requesting live searches.
An authentication failure does not establish a specific account-policy cause.
This repository has no account-deletion notification callback or public receiver.
Saved snapshots persist provider data; changing provider compliance or retention
requires a separate integration design. Consult the provider's current requirements
for the selected application. The app does not activate keysets automatically.

Provider availability must be checked for the configured installation. Mocked
responses and sample searches verify behavior, not Production access or seller
availability.

## Shopping lot calculator

`/shopping/` compares explicitly included quantities with a lot price. Search the
vintage card selector, add cards, lock wanted targets, fill in the remaining lot
and compare. Clear lot removes current contents and costs while keeping
locked wants. Locks belong to the signed-in session; they are not evidence of
seller contents or owned cards. Only included quantities contribute to totals.

The selector covers Base Set, Jungle, Fossil, Base Set 2, Team Rocket, Gym Heroes,
Gym Challenge, Neo Genesis, Neo Discovery, Neo Revelation and Neo Destiny.
Selectable entries depend on the installation's published catalog. Owned cards
remain selectable; this scope does not restrict unrelated all-era browsing or goals.

**Missing** opens the saved Original 151 collection goal first when
available. Select a missing card, then its printing; change goals under **Goal**. Missing
status uses that goal's frozen membership and existing ownership policy. These
choices may include supported printings from other eras; classic vintage sets
appear first. **All cards** retains the ordinary eleven-set selector.
**Lock** adds a session wanted target with zero included in the current
lot. **Add** adds the displayed quantity to the lot. Neither changes ownership
or goal membership. Edition, finish and variant labels distinguish printing choices.

The picker shows one printing and one quantity row at a time. Switching printings
uses the loaded results immediately; missing-card requests omit unrelated goal-update
reports while retaining source and ownership checks. Reopening restores wanted cards
in one batch. Collection and goal pages retain their full update reports.

Ungraded / Grade 8 / Grade 9 / Grade 10 are independent scenarios with
quantity-aware totals. They are not added together or treated as the card's
certified grade. The calculator displays eligible retained values automatically;
missing values remain unpriced. Estimated grades or unknown graded basis are
excluded. Source, date and grader details remain available. Unknown shipping,
tax or other costs prevent a complete delivered comparison; a known subtotal is
shown separately. Results are dated reference differences, not profit estimates.

Automatic scheduled acquisition is not connected. Legacy guide admission remains
supported; versioned private snapshots require reviewed exact source contracts.
The repository does not contain private price snapshots.
[Price snapshots](price-snapshots.md) describes the supported importer and source policy.
Searching or reopening a comparison does not fetch prices. Source identity,
grade meaning, valuation date and applicable use/storage rights must be resolved
before connecting new data. No price-refresh schedule is provided.

Saved comparisons retain their captured inputs and results privately. Reopening
preserves the snapshot; evaluating current references creates a separate child
result. Research, locks and bid intent never change ownership or frozen goals.
The original editor at `/shopping/legacy/` remains available for per-card/group
values and goal-based research. Both formats share account-scoped history policy;
see [architecture](SSOT.md). Saved history requires the explicit `enable-shopping`
operator command on collection-enabled installations; back up before enabling it.

## Price availability

Empty graded cells and grade totals stay hidden until eligible values exist. All
four scenarios remain enabled. Price dates, condition/edition assumptions and
source links are available under each card's **Price details** disclosure; the
source record is collapsed separately. Coverage depends on privately activated
sources and is not included with the repository. A publisher build date does not
become a provider valuation date. Exact identity conflicts remain unpriced.

Current display/arithmetic rights do not imply permanent-save or export rights.
Saving may therefore remain disabled even when values can be compared. Graded
coverage requires supported grade/grader evidence independently of raw references.

## Contextual collection entry and lot drafts

Species and card Find links and Goals' Find cards for this goal carry a finite,
server-checked scope. Fields are `species` OR `group` with optional member `child`,
optional paired account-owned `goal` and retained `version`, checked `generation`,
and safe `return`. Opening a current species does not adopt the first saved goal.
The label distinguishes current collection status from retained saved-goal units.
A group without child remains a printing-selection task; archived/unavailable or
unsupported entries do not choose siblings or widen calculator catalog policy.

Explicit All cards, Missing and goal changes update the visible active picker scope
and saved progress/policy units from the latest checked response. The original
collection return stays separate. Loading removes old picker actions.

Inputs survive collection navigation and reload within the authenticated account,
installation and browser origin. The private per-tab draft holds only user input
amounts/dates, listing/name, printing IDs, included/wanted quantities, lock choices
and picker UI. No guide cells, source records or computed results are stored.
Identities and admitted local references are reread; restored inputs require
explicit Compare and missing references stay unpriced. Draft wanted choices that
differ from this session are visible and require explicit confirmation; reopening
never changes session wants automatically. Clear retains wanted targets while
resetting included quantities and costs under the existing explicit action.

Logout, revoked authority, stale collection/goal context and late requests cannot
restore private results to another account. Existing source-status and expiry
checks remain active. Captured saves remain immutable, and explicit current
reevaluation creates a separate child. See [navigation and Shopping adapters](SSOT.md#navigation-and-shopping-adapters) for service ownership.


## Limits

Catalog coverage, reference-price coverage and provider availability are independent.
The calculator's vintage selector does not imply all-era pricing. Graded values need
exact printing, literal grader/score and supported dates; missing grades are not
interpolated. Conflicting product/subtype identities remain unpriced. Publisher-build
dates never become provider valuation dates.

There is no scheduled price refresh, automatic listing matching, whole-lot photo
recognition or automatic buy/bid action. Pack offers are retained observations;
live sealed-offer acquisition is unsupported. See [catalogs and Pack lookup](catalogs.md)
and [price snapshot operations](price-snapshots.md) for supported local inputs.

## Completed data-path investigation

The October 15 source investigation established two separate reference paths: hunts
use retained parity/project guides, while the calculator uses the managed private
snapshot lifecycle. Both share basic reference admission, but hunts do not yet consume
private snapshots. Seller/catalog compatibility and surviving storage rights must be
checked before reusing `market_identity`, `lot_guides`, Shopping arithmetic and history;
a third price store would introduce competing policy.

A bounded metadata-only audit recorded 901 conditionally eligible English/USD raw
references across eleven vintage sets, with an October 9 publisher build, October 10
capture, null provider valuation dates and November 9 expiry. That dated finding is
not current availability, a fresh price, exact physical condition or all-era coverage.
The recorded contracts admitted current display/arithmetic and managed storage, without
permanent comparison-save, backup or export rights. Do not copy the values into docs.
See the optional [data-path investigation](../reports/shop-01-20261014/data-path-map.md)
and [readiness findings](../reports/shop-01-20261014/readiness-coverage-matrix.md).

Installed readiness was subsequently observed as unconfigured; secure setup stopped
before any provider call. [Operations](operations.md#existing-ebay-setup-prerequisite)
explains that access prerequisite and the supported recovery procedure. No actual
assigned/remaining quota, successful OAuth, Browse entitlement or comparison/ranking/
retention rights were established by these investigations.

## Backlog

These are optional extensions rather than prerequisites for the current local scope:

- Complete graded 8/9/10 pricing from permitted observations with exact printing,
  literal grader/score and source dates. Missing coverage must stay unpriced; no
  interpolation or paid-service assumption.
- Additional raw product/subtype reconciliation for Base Set Machamp #8; Neo Destiny
  Dark Exeggutor #33; Gym Challenge Rocket's Mewtwo #14, Blaine's Charizard #2 and
  Brock's Vulpix #37; Gym Heroes Rocket's Hitmonchan #11, Misty's Psyduck #54 and
  Misty's Seadra #9. These are retained identity gaps, not freshly checked prices.
- Automatic refresh schedules, unattended monitoring/alerts, sold-history integration,
  broader catalog publication, live sealed-offer acquisition and public/hosted release.
- Named completion views, exact pack-family/origin relationships and additional date,
  language, physical-variant or category metadata beyond current admitted coverage.
- Further detail-image resolution/remote availability work, described in [artwork](artwork.md#remaining-image-limits).

Select and bound any of these separately. The active discovery and onboarding work
belongs in the remaining execution plan, not this optional list.
