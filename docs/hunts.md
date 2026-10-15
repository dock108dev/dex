# eBay hunts

The authenticated localhost app supports explicit eBay searches with the same
Browse client as the original app. Search results are private account-scoped
snapshots. The app never buys or bids, and a listing never adds an owned card.

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


## Recorded raw-price integration

The October 10 integration record reports 901 conditional ungraded references for
909 Original 151 priority printings across eleven vintage sets, including Dark,
Light and Shining species independently of completion-eligibility flags. The full
1,314-printing selector was retained; this is neither all-era coverage nor a new
catalog restriction. The provider's October 9 publisher build supplied no grader-
specific 8/9/10 fields. Provider valuation date stayed null and was disclosed; the
admitted publisher-build date governed the existing 30-day rule.

Exact product/subtype joins preceded admission. Physical edition/condition stayed
conditional where unknown, and conflicting variants remained unavailable. The
release permitted current display/arithmetic and managed private storage, without
permanent comparison-save rights or price backups/exports; saved Shopping storage
remained disabled. The genuine Chansey/Scyther two-card comparison was observed
without changing collection/goals. Ninety-one affected tests and a subsequent
46-case snapshot run passed at that integration, not at every later revision.

These are dated observations, not a fresh read of today's installed prices. The
original local closeout is `docs/shopping/CS-OCT2026-DATA.md`; private source
contracts, consumed request journals and runtime receipts remain local. Reference
expiry, source withdrawal and admission still decide availability on access.

## Backlog

This work is outside the local collection-clarity completion goal. Resume pricing
after owner acceptance or when explicitly selected; its data/integration work is
unfinished, rather than part of a completed collector or UI pass.

- **Graded coverage — research/data integration:** find genuine permitted free
  Grade 8/9/10 observations with exact printing, literal grader/score/currency and
  real valuation/sale dates. No interpolation, capture-date substitution, new paid
  service/account or invented coverage. Verify source-specific storage/removal
  rights before integration; lack of a suitable source remains an explicit gap.
- **Raw identity gaps — catalog/data integration:** resolve the eight entries
  below with independently observed unique product/subtype evidence. Do not alter
  ownership, guess a physical edition or admit conflicting variants.
- **Supported new prices — backend/integration:** preview, validate and activate
  only newly supported observations through the existing lifecycle, preserving
  expiry, withdrawal, provenance, independent registries and save limits. Protect
  the existing installation; exclude managed prices from backups.
- **Pricing review — QA with owner acceptance:** check actual versus partial
  coverage and add/lock/fill/compare/clear on the real installation. Keep included
  and wanted quantities distinct; do not enable saving without surviving rights.
- **Optional product expansion:** automatic listing research, refresh schedules,
  broader all-era catalog publication and shared hosting/public release require
  separately selected scope. Existing code or an old proposal does not start them.

| Unresolved raw reference | Evidence still needed |
| --- | --- |
| Machamp — Base Set #8 | Unique matching product |
| Dark Exeggutor — Neo Destiny #33 | Unique matching product |
| Rocket's Mewtwo — Gym Challenge #14 | Unambiguous compatible subtype |
| Blaine's Charizard — Gym Challenge #2 | Unambiguous compatible subtype |
| Brock's Vulpix — Gym Challenge #37 | Unambiguous compatible subtype |
| Rocket's Hitmonchan — Gym Heroes #11 | Unambiguous compatible subtype |
| Misty's Psyduck — Gym Heroes #54 | Unambiguous compatible subtype |
| Misty's Seadra — Gym Heroes #9 | Unambiguous compatible subtype |

The existing instruction permits routine free source work and reversible local
integration when this backlog is selected, subject to source access rules,
publisher cadence and consumed-attempt accounting. It does not authorize spending,
account creation, credential resets, destructive changes, buy/bid or publication.
Paid API proposals and old per-step approval packets are not prerequisites for
that bounded free-data work. No automatic refresh schedule is connected.
