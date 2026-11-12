# Shopping and eBay discovery

Shopping combines local catalog browsing, explicit eBay searches and dated-reference
comparisons. Catalog and reference coverage are partial. Missing identities, costs
and reference values stay unknown. The app never buys, bids or guarantees a bargain.

## Buying options

Shopping starts with a card request and optional budget. **Best matches** returns one
ordered list with the offer cost, a short contents summary, the reason for its order
and a seller link. Search options, allowance, filters and evidence are collapsed.
The decision journal is no longer part of the ordinary buying flow.

Ordering uses request relevance, complete comparable value when available, supported
physical contents and known delivered cost. Random/custom lots come later. A cheap
current bid is labelled as a bid; combined offers use the Buy It Now observation.
Unknown shipping is never zero. Higher-priced opportunities remain available under
the flexible budget policy, without automatically qualifying a purchase.

When no applicable values exist, the list says so and orders the available evidence;
it does not claim a proven bargain. Every received seller summary is parsed locally;
the normal Hunt still fetches fuller details for at most two offers. **Details** reveals sources or
optional contents correction. The review leads with a short cost/value summary and
keeps the full breakdown in a disclosure.

**Best matches** also uses a complete single-cohort publisher guide for estimated
value screening. Within an identical source/date cohort, a lower price-plus-shipping
to guide ratio ranks first. The row shows the actual guide amount, coverage and
mixed-condition basis. A partial guide is labelled as identified-card value and has
no whole-lot ratio. Unknown shipping has no ratio. Native guides do not become
normalized totals, profit, condition-specific prices or bid ceilings. Source expiry
and withdrawal clear these screening ranks together with the underlying evidence.
A fresh authenticated value response clears an earlier failed lifecycle-check state
before requesting a new lifecycle check; a transient failure cannot permanently
hide freshly revalidated prices.

### Free vintage reference import

A one-time TCGCSV capture can provide ungraded, mixed-condition market guides in
USD. Retain the publisher build and capture dates, exact product/subtype identity,
missing prices and reviewed source permission. MP/LP/NM and graded prices are not
present in this feed and must not be manufactured from a multiplier. See
[TCGCSV documentation](https://tcgcsv.com/docs) and [FAQ](https://tcgcsv.com/faq).

The vintage matcher binds exact English set/name/number pairs, rejecting duplicate
or conflicting identities. Source group 604 represents Base Set Unlimited; 1663
retains a separate Shadowless attribute. Jungle/Fossil use their explicit edition
subtypes. These group semantics are retained in the admitted provider identity and
checked against the actual offline shard. Physical alternatives are additive;
existing numbered parents and owned copies are unchanged.

For the original English Base Set, Jungle and Fossil, the known collector-number
lists establish holo versus normal finish. This narrow catalog inference is recorded
separately from seller assertions. It never supplies missing language, edition,
condition, quantity or a special printing. Other sets retain their existing rules.

The 2026-11-07 import captured five groups in 13 operations and produced 565 dated
CSV rows, 562 populated and three without prices. Of these, 552 exact current
references were admitted to the existing customer installation after independent
mapping/contract review. Promo and special-error rows remain in the dated CSV when
no exact installed identity exists. The current app references expire after 30 days;
this is a one-time snapshot, not an automatic refresh subscription.

## Provider integration

The implementation uses these eBay REST operations:

| Dex capability | Current API contract |
| --- | --- |
| Application authentication | OAuth client credentials, `/identity/v1/oauth2/token`, `api_scope` |
| Shopping and Price Hunter searches | `GET /buy/browse/v1/item_summary/search` |
| Exact listing details | `GET /buy/browse/v1/item/{item_id}` |
| Numeric listing/variation resolution | `GET /buy/browse/v1/item/get_item_by_legacy_id` |

The legacy-ID endpoint resolves numeric identifiers through Browse; it does not
use the traditional XML API. Provider access requires separate configuration.

## Find lots

The ordinary Shopping page leads with Pokémon/card name, optional set
and **Find lots**. That action submits the versioned automatic Hunt:
one independent BIN search, one search for auctions ending within 72 hours, then
full seller details and the existing local assessment for at most two unique
candidates. It requires current ordinary Hunter usage authority and five available
shared operations. It neither selects settings nor revives an old allowance.
See the finite contract below. Runtime installation and active source coverage are
verified separately; neither is inferred from a source checkout.

Seller details are the primary assessment evidence. No per-listing Load Details or
Interpret click is required for the two selected candidates. Photos are optional
and are not processed. Other received summaries stay visible as unprocessed. Clear
supported quantities and identities can contribute existing normalized or separate
publisher-native projections; unavailable references leave facts visible and values
unknown. Deterministic contents resolution and the shared calculator supply the
automatic results. Assess lot remains available for optional review/correction. Dual offers
retain the current bid and Buy It Now costs independently. Local reads revalidate
reference eligibility; no price acquisition occurs during a Hunt.

A selected catalog set reaches official Browse as the category's `Set` aspect,
with the Pokémon/name as the keyword query, rather than merely appending the set to
keywords. Named continuation preserves the facet. Other catalog set labels may differ from seller taxonomy; no fallback broadening is
performed. A selected set is seller metadata, not physical content verification.

**Year manufactured** is a search filter for lots and singles. **Before 2000**
sends eBay the years 1996–1999. **Through 2000** includes 2000. Dex sends the
category's `Year Manufactured` aspect with every Browse page and combines it
with the other aspects on that page. Changing years requires a new explicit
search. Listings without those seller-entered years can be omitted. A year on a
mixed lot describes the seller's listing. Individual card printings may still
need review. On a missing-species Hunt, rows flag other missing species named
in seller titles so the collector can check the contents.

The automatic auction page is ending-soonest and the independent BIN page uses
provider best match. The default local auction view is 72 hours, with BIN available
independently. Local filters and sorts only rearrange received results; they cannot
expand the two-page batch or its two-candidate detail cap. No result is a market-wide
best-value claim. The server supplies independent lane ranks and separate native cohort ranks;
the client displays distinct assessment groups and independent buying views.

## Shopping singles

Choose **Singles** in Shopping or **Find listings** on a supported species or
card page. Selecting the card page's exact printing prepares its name, number
and set. Search stays explicit. A selected set narrows the provider keywords
and Dex checks the catalog set against the returned seller evidence. An exact
printing choice requires seller evidence that distinguishes the child printing.

Singles uses eBay Browse category 183454 in the US marketplace, with US item
location and delivery. Buy It Now and Auction use the documented buying-option
filters. Selecting both starts with a Buy It Now page. **More results** can
then request an Auction page, with available pages alternating between the
formats. The next format is displayed before each request. One click sends at
most one Browse request with up to 20 summaries, plus OAuth when needed. The
original run holds at most four pages. All sends debit the existing shared
allowance. Stop, continuation and the original temporary lease still apply.

Leaving the name and set blank samples seller-classified Pokémon TCG singles
in Base Set, Fossil and Neo Genesis. That request uses `Pokemon` and the
verified Game and Set aspects. An explicitly selected catalog set uses
keywords because seller taxonomy can use a different name. Counts describe the
received pages, including duplicates and other exclusions. Seller metadata can
omit listings and admit incorrect matches.

Singles still show the retained catalog's language-specific release evidence.
A dated set can support its original numbered issue when seller name, set and
number agree. Special releases and reprints need their own dated evidence.
Later releases, unknown dates and conflicting claims have separate counts.
Original numbered English Fossil Lapras #10 and #25 carry distinct holo and
non-holo identities. Edition remains unresolved when the listing does not
distinguish it. Opening or returning from review uses zero provider operations.

## Named search and continuation (legacy explicit contract)

The following remains supported for callers that do not submit the automatic Hunt action
contract. It is not the ordinary automatic Find lots job and cannot continue one.

Named search uses one official Browse category per request: Mixed lots selects
**183455**, Singles selects **183454**, and Both alternates the two captured lanes.
Category selection is independent of words such as “lot” in the query.

Find lots captures text and optional set with the page's mixed-lot category and
ending-soonest order. The service also supports explicit category and sort choices. It needs no local
catalog match. Set overrides replace conflicting recognized aliases, preserving
Base Set versus Base Set 2. Compatibility callers can supply English/vintage refinements.
Venasaur/Venusaur and Gyrados/Gyarados appear as visible suggestions: **Use** changes
text locally, **Keep as typed** retains it; Search remains a separate explicit action.
Neither is evidence of seller contents or exact printing identity.

Named Search and each **More results** send one Browse request with at most 20
summaries. The run stops after **four pages / 80 received summaries total**, on
conservative exhaustion or on error, whichever comes first. Offsets are server-owned
multiples of 20. Both captures two category lanes and alternates lots/singles, one request per
explicit action, within the same four-page total. An exhausted lane is removed.
A full page and an integer total beyond that page are needed to offer continuation;
missing/malformed totals end the lane. Provider `next` URLs are never followed.

More accepts only the account/session-bound opaque run handle. It retains the same
run, captured choices, deduplication set and original 30-minute content expiry.
Concurrent More cannot fork the cursor or renew its lease. Exact item/variation
identities deduplicate across pages; distinct variations remain separate. Edited
acquisition choices require a new Search. Already received listings and filters are
local; displaying them never acquires another page. Blank-text catalog discovery
remains a separate finite explicit batch over captured catalog queries, with the
same checked category transport; it does not page a named query.

Results expose titles, checked HTTPS eBay destinations and supported identity
proposals immediately. The old Reveal endpoint remains a local compatibility
operation, with no visibility or review prerequisite. Category-admitted mixed lots
cannot receive an entire-lot value from one named card, even when the title looks
like an exact single. Optional inspection/comparison retains the existing quantity,
reference applicability, account, current/frozen scope and original lease services.
Unknown shipping, contents and reference values remain unknown and browsable.

Seller photos are temporary official-summary image URLs restricted to the exact
`https://i.ebayimg.com/images/g/.../s-l<number>.<jpg|jpeg|png|webp>` contract, with no
query, fragment, credentials, alternate host or port. Only local authenticated
Discovery pages admit that CSP origin. There is no download, image store, export,
proxy, retry or fallback acquisition. Catalog scans retain their independently
checked identity adapter and are visibly labelled separately. Both image types
keep a fixed fallback area; local result updates preserve unchanged image nodes.

Hunter and Discovery share the countdown helper `listing-time.js`; Discovery also
validates aware timestamps on the server. Missing, malformed, unzoned or invalid
calendar/timezone dates show unknown; ended auctions say ended. Current bids remain
provisional. Seller destinations must pass the shared HTTPS eBay URL validator.

## Ungraded Price Hunter

Price Hunter focuses on individual ungraded cards. The ordinary page submits
Singles, excludes graded/lot results from the ordinary display, and presents card identity,
current bid/Buy It Now, time remaining, inbound shipping, admitted ungraded reference,
reference date/capture time/source and potential net. Seller links are immediately
visible. No graded comparison or bulk calculation is part of this flow.

Potential net is a conditional resale scenario, not probability-weighted EV:
raw reference minus purchase amount, inbound shipping, purchase tax, resale fees,
outbound postage, supplies and other costs. Free resale shipping is assumed. The
calculator implements US non-Store fee assumptions: 13.25% through $7,500 of the fee base,
2.35% above; $0.30 through a $10 order, otherwise $0.40. Resale buyer tax increases
fees but is not seller revenue. The fee schedule is described at
[eBay selling fees](https://www.ebay.com/help/selling/fees-credits-invoices/selling-fees?id=4822).
Default assumptions are visibly 0% purchase/resale tax, $5 resale postage, $0.50
supplies, zero other costs. One cost disclosure makes them editable in memory;
this does not establish actual tax liability or shipping cost. Extra seller charges
or promotion costs belong in Other costs. Negative estimates stay negative.

Existing reference admission/matching, original source dates and lifecycle remain
in force. Missing shipping/reference/cost input or expired listings leave net
unavailable. Conditional references label the estimate conditional. Capture time
is shown only if actually recorded; reading an old reference is not a fresh price
check.

Unconfigured owners can explicitly enable a one-day test capped at three operations,
without recurrence. This only saves usage settings; Find cards remains separate.
Existing configured policies and all consumed accounting remain authoritative.
Reopening, cost edits and reviewing its results make no provider requests.
The underlying service also supports multiple categories; those compatibility
capabilities do not change the ordinary page's Singles submission.

## Everyday Price Hunter

Use **Hunter → Usage settings** to enable/pause acquisition and explicitly select
1–15 operations per Hunt, 1–1,000 shared daily operations, timezone, one window or
daily recurrence, and expiry. These are validation ceilings, not default capacity.
OAuth, searches and selected official details consume their dispatched requests.
Failed, uncertain and stopped in-flight requests remain consumed. Inspection,
local paging, reveal, filters, comparisons and Back make no provider requests.

Each Hunt captures its window, parent, ceiling and lease. Concurrent Hunts share
durable daily accounting. Pause, expiry, withdrawal and reductions apply before
sends and publication. Timezone changes preserve prior usage conservatively;
day boundaries account for daylight saving. Clock rollback or invalid accounting
blocks acquisition. See [policy operations](operations.md#everyday-hunter-policy).

Pausing acquisition does not itself withdraw an already completed automatic lot
Hunt. Local review remains available only while its original seller-content lease,
captured policy authority, account and session remain valid. Pause still prevents
new requests and late publication; Stop, expiry, withdrawal and applicable policy
or account changes continue to remove or withhold content.

## Hunter service and temporary review

`/shopping/hunter/` is the authenticated Hunter page. The service supports Singles,
Lots or Both, while the ordinary page submits Singles. No goal,
wanted list or card entry is required. It retains US/English Pokémon TCG across
all years/generations, including owned cards and supported Trainer/Energy singles.
The captured auction window is the next 24 hours; available Buy It Now offers are
separate. Ordinary acquisition remains unavailable until the owner selects usage limits
in the installed settings. An unavailable screen is not an empty search.

The screen shows progress, limited coverage, image-led received results and dated
backend comparisons. Applicable BIN, conditional BIN and auction scenarios keep
their own cost bases and equivalent-group ranks. Unknown costs remain Unknown.
Fetched observations, unique identities, duplicate observations, retained and
skipped identities, malformed rejections, local offer rejections and advisory
truncation remain separate in Coverage and request details. This never implies a
complete marketplace scan, resale EV or a maximum bid.

**Show more received results** reads local result pages. **Continue acquisition**
uses only the captured continuation cursor after an explicit click. Local filters,
revealing seller text, Inspect card, Analyze lot, Back and reopening do not acquire
listings. A stale local cursor clears the old projection and reloads the first
local page with current ranks. Scope changes need a new Hunt. The prior parent is
stopped before a replacement Hunt starts; late responses cannot restore cleared
content. Parent Stop clears received results and dependent reviews immediately.

Inspect card opens a temporary local inspection. Analyze lot analyzes already
received seller text and opens the compact Ungraded review. Proposed cards,
quantities, printing choices, reference images, seller clues, stated total and
unresolved contents remain visible. The local all-era card search can correct
missing proposals without a provider request. Printing, condition, grading and
cost corrections are secondary disclosures. Only a deliberately edited/confirmed
relevant attribute resolves an applicability conflict; inherited seller clues are
not silently confirmed. Repeated mentions, seller stock and lot units do not
multiply contents. Owned duplicates contribute their included quantity normally.

A blank unresolved remainder sends `unknown_contents: null`; entering 0 explicitly
confirms no remainder. Corrections send the current revision; a conflict reloads
the current review and never retries the write. Editing inputs withholds the old
comparison until Compare corrected contents. Only fully reconciled and priced
contents with all required known costs permit a complete delivered comparison;
otherwise the screen labels the priced subtotal and missing coverage. A correction
is the user's decision, not verification of physical seller contents.

Additional official details first prepares a non-dispatching plan. **Load official
details** is a distinct explicit action, unavailable without captured capacity.
**Stop details** remains independent and visible while a detail action is active,
including after returning to received results. Parent Stop/expiry clears dependents.
All local reads/corrections preserve the original 30-minute lease. Visible polling,
Back and tab resumption recheck current authority and references; stale values are
withheld during revalidation. History retains only opaque handles and UI context;
provider text, prices and comparisons never enter browser storage or exports.

Catalog images use the existing checked image-binding adapter. They remain
reference scans, separate from seller photographs and exact edition/finish claims.
Missing, blocked or broken images keep fixed neutral space and readable identity.
Seller text is rendered as text. Existing visual card search, assisted listing
checks and manual calculator remain available independently.

## Connected Pokémon and card entry

A Pokémon page places **Explore cards** and **Search mixed lots for this Pokémon**
next to Your Cards and its empty state. Both work for owned or missing species.
Explore opens that species' indexed Card Library choices; named Shopping prefills
its readable name and mixed lots. Neither link acquires listings or changes ownership.
No indexed choices and unavailable artwork keep truthful, readable fallback states.
A declaration of a species never supplies an exact card, quantity, edition or finish.

Library retains its original species return, collection generation and explicitly
selected goal/version. Its supported single set survives filtering and pagination.
Shopping maps one inherited supported set; Base Set and Base Set 2 remain independent.
A visible scope note explains multiple/unavailable sets or other collection card
criteria that Shopping cannot apply. It also explains a chosen card/search set that
replaces the original set. Back retains the original collection criteria. These
are search refinements, separate from `shopping_context.FIELDS`; they do not create
new provider filters or change current/frozen ownership policy.

Local Shopping tiles have a selection button and a separate **Card details** link.
Selecting a group does not select its first child. An explicitly chosen printing
survives Card details and Back. Internal details and external seller listings remain
separate links with separate keyboard focus. Card details returns to the originating
Shopping state; its Shopping action reuses that same destination instead of nesting
repeated return chains. Query, refinements, original collection return, scroll/focus
and eligible opaque run handle survive. Result content never enters URLs or browser
storage; restoring a handle rereads the authenticated, session-bound temporary service
with the original lease. Stopped, expired or unavailable handles do not start another
search or restore removed results.

Server return validation remains restricted to canonical local destinations and
finite fields, with a 4,096-character destination bound and at most six nested edges
for species → Library → card → Shopping → card inspection. It reauthorizes every
referenced private target and checks retained generation/goal version. Legacy species
links without a version still open through the existing current policy; new links
retain the explicit version. Logout, revocation and cross-account result access use
the existing authentication/navigation boundary.

## Compatibility catalog exploration

These retained catalog controls are hidden on the ordinary Find lots page.

Shopping starts with a named eBay search, defaulting to mixed lots. Local catalog
exploration is available under **Explore local Pokémon and cards**. Broad Pokémon names
show Pokémon artwork, current collection context and matching-card counts. Choosing
a Pokémon reveals card references. Detailed names, sets and collector numbers show
matching card scans with readable set/number labels. Multiple plausible cards and
exact printings remain explicit choices; a group never chooses its first child.
Unavailable images retain visible results and an honest fallback. Reference scans
are separate from exact printing images, private copy photos and seller photographs.

All supported sets and quick Base Set / Base Set 2 / Jungle / Fossil / Team Rocket
buttons refine local results and the submitted provider query. Ordinary `base` and
`base 2` aliases remain independent. A typed phrase cannot bypass the selected set.
Fractional numbers may use the numerator to find plausible references; the UI asks
for the full numbering/set to be checked and does not establish exact identity.
Local browsing stays useful when provider access is unavailable.

The checked context from Pokédex, species, Library, card and goal pages opens this
merged search. Query, set, current/frozen ownership scope, optional exact child,
filters, scroll and focus survive validated Back navigation. Only finite user UI
choices and opaque result handles enter URLs; provider content/values do not.
The secondary manual calculator retains its existing user-input drafts independently.

## Returning from inspection

Inspect → Back keeps received offers and accumulated More results in the existing
temporary server run. Ordinary deals match current authorized catalog identity
without rebuilding unused ownership; missing-card and frozen-goal searches retain
their ownership projection. Image binding processes only requested identity groups,
including all conflicting siblings. Back still checks authority, context, original
expiry and source admission, using no marketplace search. Options/run reads start
together, and a closed local explorer loads when opened. Optional work preserves
restored scroll/focus after results are usable. Review changes follow the save rules below.

## Edited review saves

Autosave and internal Back share a single writer. Edits made during a pending save
are coalesced to the latest revision; Back waits for that revision to succeed.
Failed saves retain the current input and keep the review open. An unchanged review
needs no write. Server validation reads only the reviewed printing IDs through the
same publication and eligibility policy, and reuses the selected offer context
within that save. Later reads revalidate independently; no lease is renewed and
no provider request is made by saving or Back.

## Navigation

Open **Shopping** at `/shopping/` for **Search eBay**, optional visual local search, **Find deals**,
**Find missing cards** and **Check a listing/lot**. Assisted checks are at `/shopping/check/`; the manual
calculator is at `/shopping/calculator/`. Contextual collection links retain their checked printing selector and Back destination.
Saved research and Packs remain reachable. Opening any of these pages does not
request provider data, refresh prices or change collection/goals.

## Compatibility deal and missing-card scopes

These service scopes remain available to compatibility callers; the ordinary lot
finder does not expose their refinements.

**Find deals** generates searches from the supported catalog and includes owned
cards. It needs neither a goal nor manual card entry. An optional USD spending
budget, search phrase, set and Kanto/Johto scope narrow the search. Discovery uses
singles, loose mixed lots and supported auctions. Choose Singles / Mixed lots /
Both and Ending soon / Best match. English/vintage uses search words; US marketplace,
US listing location and US delivery use supported official fields. Language and
manufactured-year facets are not guessed. Release-period controls do not change
collection membership or imply unsupported provider facets. Vintage retained
reference coverage and all-era catalog browsing remain independent.

**Find missing cards** defaults to **Current collection · Original 151 · species**.
Current collection also offers exact-printing policy; a frozen goal is optional. A selected goal retains
its captured membership and ownership policy. Broad ownership declarations do not
establish every edition/finish. Search is read-only for inventory and goals.

Search starts only on explicit action. **Stop** cancels acquisition and suppresses
late publication. **More results** continues the same named query/category and original lease,
within the four-page total described above. Blank-text catalog discovery advances
its captured catalog queries instead. Edited choices require a new search. Filters,
Back, review and reopening perform no provider requests. Titles, supported identities
and checked seller links are visible immediately; seller text proposes identity
without physical verification.

## Comparisons and temporary results

Discovery reads admitted references through `lot_calculator.retained_records`,
private snapshot admission/lifecycle, `market_identity`, `lot_guides` and
`shopping_math`. It rechecks lifecycle on local reads. Open pages also remove expired/withdrawn
reference values and derived differences using local lifecycle checks. Expired, withdrawn, conflicting
or inapplicable references remain unavailable; searching never acquires prices.
Ranked comparisons use admitted reference arithmetic rather than the legacy hunt score.

Cards show listing price, shipping and delivered total when known. Unknown shipping
stays unknown. Comparable below-reference candidates, conditional comparisons and
unpriced/ambiguous results stay distinct. Source/capture dates and unknown provider
valuation dates remain explicit. Edition, finish, language, condition and literal
grader/grade affect applicability. Generic grade scenarios do not establish exact slab
matches. References are dated observations, not fresh quotations or profit estimates.
Auction current bids, if encountered, do not become final prices.

All current listing consumers use the same bounded Shopping decimal policy. Invalid
amounts stay unknown independently, so invalid shipping cannot hide a valid asking
price. Compatibility single-card summary shipping shows the cheapest explicit
supported USD option; lot benchmarks and review inputs require an agreed
amount/currency across the supplied options. Missing auction
bids never use buy-now prices. Supplied invalid official-detail end times fail with
an availability error; missing/invalid summary times stay unknown.

Discovery results and provider summaries are temporary server memory. They are never
written to raw hunt history, browser storage, exports, reports or backups. Saving
these results is unavailable; the product explains that limitation. Existing saved
research remains available under its original rights checks. Reopening temporary
results requires the same authenticated session and a surviving server run; a restart
requires a new explicit search. Local reads do not renew source rights.

## Finite acquisition

Each named Search or More action admits at most **one OAuth and one Browse
request**, at most **20 summaries per Browse**, **30 seconds per request** and
**75 seconds overall**. Named continuation has a four-Browse total for its original
30-minute run. The separate blank-text catalog batch retains the existing ceiling
of one OAuth/four Browse per explicit action; the ordinary client requests one Browse. An independent acquisition deadline
suppresses late dispatch/publication even when local authorization is slow. Valid tokens can
be reused. No retries, redirects, reauthentication, hidden pages or fallback calls
are permitted. Failure ends that action. Admitted, in-flight and uncertain attempts
are durably recorded without provider content; cancellation does not refund them.
The old `/api/hunts/` POST returns 410 directing users to Shopping. Historical reads
remain local. Discovery makes no item-detail, quota, sold-data or scheduled calls. Assisted checks use the separate explicit detail operations below.

## Local provider settings

Shopping reads the local provider configuration and the private configuration-root
`.env`. App ID maps to `EBAY_CLIENT_ID`, Cert ID to `EBAY_CLIENT_SECRET`.
Nonempty process environment values take precedence over file values; restart the
ordinary runtime after changing its environment. Keep credentials server-side and
outside source control. See [local startup](local-development.md#existing-installations)
and [provider operations](operations.md#shopping-discovery).

Discovery and assisted checks require Production credentials and use
**EBAY_US / US country-only** delivery, without a postal code. Local configuration
or provider failures remain explicit. Reading configuration does not verify access
or issue a provider request.

## Discovery integration constraints

Catalog coverage, admitted reference coverage and provider availability are
independent. Discovery uses the calculator's managed private snapshot lifecycle,
guide selection and arithmetic. Saved historical hunts retain their original read
path. Seller/catalog compatibility and source rights are checked independently;
conditional arithmetic does not establish a verified physical identity.

Arbitrary seller URLs, shorteners and sold data are unsupported. Discovery makes
no purchase, bid or inventory mutation. Both acquisition paths support fixed-price and auction buying options, including
mixed options. Loose mixed lots are eligible candidates without receiving a
misleading single-card reference. Sealed, mystery, random, curated and other
unsupported products remain excluded. Imperfect identity can remain a visibly
uncertain discovery candidate independently of reference-price applicability. Manual cost
entry remains available and never places a bid or establishes a final purchase price.

## Check a listing/lot

Open **Check a listing/lot** at `/shopping/check/`. Paste a supported HTTPS eBay item
URL, numeric ID or literal `v1|item|variation` ID and choose **Load listing**. Long
tracking/encoded links, shorteners, unsafe hosts and unresolved parent listings are
rejected; use the plain numeric ID or exact variation URL instead. Only official
getItem/getItemByLegacyId operations run. No seller page is fetched.

Loading opens a preview and keeps your existing review. **Use these details** explicitly
replaces its contents/costs; **Keep my review** discards the preview. Available title,
current bid or asking amount/currency, shipping and condition claims are proposed.
Buy-now amounts and the owner's planned manual bid remain separately labelled.
Opening a selected discovery offer transfers its checked temporary evidence and
original expiry without another provider operation. For automatically enriched candidates,
this includes the acquired full details and seller-selected quantities; **Use
offer in review** retains those quantities without per-card confirmation. Unenriched
summaries remain labelled separately. Extra official details outside that automatic
job require **Load additional official details**; manual URL/ID entry remains available. Listing stock,
eBay lot units and seller-stated card count are separate. Proposed ambiguous printings
have zero included. Review leads with **Ungraded** and reference images. Include, remove or correct
proposed cards and quantities; expand optional printing/condition/grader details
when needed. Ambiguous or conflicting proposals remain unconfirmed. A selected
search printing stays visible as a target and does not establish seller contents. Find cards locally adds/corrects catalog choices.
Manual/in-person entry is available without any provider request; the independent manual
calculator and saved research remain in the final disclosure.

**Compare reviewed lot** invokes the existing admitted-reference calculator and Shopping
arithmetic. The whole-lot observed amount is counted once, with current auction bid and
buy-now asking amount kept distinct from the owner's optional planned manual bid. Only included card quantities
receive applicable values; unrecognized cards receive none. Blank remainder quantity
means unknown, while zero explicitly states all contents are identified. Partial contents
or pricing produce only a priced subtotal. Blank shipping/tax/other costs and foreign
currencies prevent a complete USD delivered comparison. There is no currency conversion,
price refresh, physical verification or inventory/goal/wanted-target mutation. Literal
grader/grade applicability is preserved; generic guides remain separate scenarios.

Reviews and details are temporary account/session-bound server memory, for at most 30
minutes or until restart. Navigation restores the remaining review lifetime; reads and
edits never renew the lease. Expired provider details cannot be retained under a new
lease. Stop, expiry and session revocation suppress later dispatch/publication. Local
search, corrections, reopen, comparison and reference-lifecycle checks use no provider
operations. Review edits do save temporarily to server memory so autosave and Back
can restore them within the original lease. Assisted inputs/results are not saved
as permanent research, exported or written to browser storage, raw hunt history,
logs or backups. The UI explains this restriction; existing saved
research retains its existing rights checks.

Each explicit Load admits at most one OAuth and two combined detail/resolution calls,
30 seconds per request and 75 seconds overall, with finite bodies and independent Stop.
The normal path needs one detail/resolution call and reuses an eligible application token.
No Browse fallback, retry, redirect or reauthentication occurs. Consumed/uncertain attempts
remain in the independent sanitized ledger.

## Shopping lot calculator

`/shopping/calculator/` compares explicitly included quantities with a lot price. Search the
vintage card selector, add cards, lock wanted targets, fill in the remaining lot
and compare. Clear lot removes current contents and costs while keeping
locked wants. Locks belong to the signed-in session; they are not evidence of
seller contents or owned cards. Only included quantities contribute to totals.

The selector covers Base Set, Jungle, Fossil, Base Set 2, Team Rocket, Gym Heroes,
Gym Challenge, Neo Genesis, Neo Discovery, Neo Revelation and Neo Destiny.
Selectable entries depend on the installation's published catalog. Owned cards
remain selectable; this scope does not restrict unrelated all-era browsing or goals.

**Missing** defaults to **Current collection · Original 151**, using the same current
species ownership as the unrestricted Kanto Pokédex. No saved goal is required.
Select a missing Pokémon, then its printing. Under **Collection or saved goal**, an
explicit saved goal instead uses its frozen membership and existing ownership policy.
Saved declaration snapshots retain their original ownership and can differ from the
current collection. Lot drafts retain user-authored rows and amounts independently
of the active picker.
Missing choices may include supported printings from other eras; classic vintage sets
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
A group without child keeps its card-reference scope and optional printing choice; archived/unavailable or
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

There is no scheduled price refresh, whole-lot photo
recognition or automatic buy/bid action. Pack offers are retained observations;
live sealed-offer acquisition is unsupported. See [catalogs and Pack lookup](catalogs.md)
and [price snapshot operations](price-snapshots.md) for supported local inputs.

## Interrupted browser sessions

Temporary Hunt results belong to the authenticated account, browser session and
original lease. The tab history holds only opaque handles and UI context; a new
tab cannot discover another tab's run. If a handle is missing or a run has expired,
the app shows an unavailable state. Back, reopening and local revalidation do not
renew leases or refund consumed requests. Stop clears received results and dependent
reviews; late responses cannot republish them. An interrupted session never starts
a replacement Hunt automatically.

## Completed-sale guidance

The checkout can consume independently admitted, qualified comparable-sold
estimates through the shared calculator. Sold evidence requires its own source
admission; no sold-history
acquisition is implemented by this work. Active Browse listings and item details
do not establish sold-history access or actual sale prices. Dated guides are not
sold comparables. Dex does not infer entitlement, scrape sale history or turn
active asking prices into realized values.


## Listing interpretation boundaries

Local-model extraction of card details is implemented for Shopping and Price Hunter.
`ollama_gateway.py` owns the bounded transport; `hunter_lot_parser.py` validates
source-linked proposals from already authorized titles, descriptions and item specifics.
The deterministic parser, exact catalog matching, parent leases and financial services
remain authorities. Ambiguity and manual correction remain explicit rather than
silently choosing an identity or quantity. Connectivity alone is not extraction qualification.

Seller condition/grade/authenticity statements remain claims. Structured listing
prices stay authoritative; an asking price is not market value. Missing costs and
unknown values remain unknown. Interpretation must not acquire more listings, scrape
pages, buy/bid, infer ownership or create collection records. Requests are explicit,
bounded and cancellable; partial, stale or invalid model results cannot be published
as verified facts. No Codex/OpenAI execution fallback is permitted.


## Local text adapter and listing review

The backend reads owner-only `ollama.json` from the existing installation root.
Its fields are `provider`, `app`, `base_url`, `api_key`, `model`,
`timeout_seconds`, `max_tokens`, `temperature`, `reasoning_effort` and `stream`.
Create this file only in the private installation root, with owner-only permissions
(`chmod 600`). Replace the example URL, key and model with values for your configured
gateway; this is not a direct Ollama server URL:

```json
{
  "provider": "openai-compatible",
  "app": "dex",
  "base_url": "https://your-gateway.example/apps/dex/v1",
  "api_key": "replace-with-private-key",
  "model": "your-model-id",
  "timeout_seconds": 240,
  "max_tokens": 512,
  "temperature": 0.3,
  "reasoning_effort": "none",
  "stream": true
}
```

Do not commit this file or expose it to the browser. The URL path must be
`/apps/dex/v1`; redirects and alternate-provider fallbacks are disabled. The timeout
and output caps are 240 seconds and 512 tokens. Configuration readiness checks
only local settings and do not send a model request. Missing or invalid settings
leave interpretation unavailable; photo recognition remains unavailable regardless.

Shopping and Price Hunter result cards offer **Interpret listing with local AI**.
Only that explicit action sends already-authorized seller title, available
summary/description and item specifics. Missing descriptions are not fetched.
No provider price, account, collection or credential data is sent as prompt text.
One analysis may run at a time. Stop cancels it. Navigation, changed seller content,
account/session changes and the original source lease invalidate results. Results
are temporary, expire within four minutes and are not stored with research/history.
Restart neither restores them nor launches inference.

Streaming text is buffered until the entire response finishes successfully and
validates. Each suggested field requires a literal source quotation; unsupported
fields and malformed, incomplete or oversized outputs fail closed. Card/set names
are checked against the existing catalog; printing matching stays with the existing
deterministic lot parser. Ambiguous identities and missing fields remain explicit.
Seller condition/grade assertions are claims, not authentication or grading evidence.
Prices, fees, profitability, ownership and acquisition allowances are unchanged.

The review shows editable suggestions and their evidence. Corrections remain in
that temporary panel; use the existing card/lot review to apply chosen cards.
No suggestion automatically updates cards or financial calculations. This version
can abstain on useful details even when they occur in seller text. Explicit “One
card” is either recovered or visibly flagged when omitted. The model is an aid to
manual review, not an authoritative card identifier.

## Optional extensions

Photo recognition, broader provider/catalog coverage, stronger relevance ranking,
fresh-price guarantees, graded/bulk Hunter workflows and probability-weighted EV
are outside the current local-product completion goal. Existing manual photo and
ungraded workflows remain supported. Framework/database replacements, cloud hosting,
public release automation and enterprise administration require a separate need and
compatibility plan. Portability of the installation-bound acquisition/qualification
operators is a separate maintenance change; their guards must not be weakened merely
to remove local paths. None of these extensions is a prerequisite for accepting the
current scoped product.

## Loading and recovery

The lot finder displays received seller summaries while the bounded automatic job
gathers selected details and invokes catalog/reference assessments. Contents and collection fit remain unassessed at that point; unknown
shipping and currency stay unknown. Assess lot requires the checked review admission.
Optional search settings and a closed explorer do not delay received results. Section
reload controls make local reads.

Legacy Search and official-detail actions use account/session/operation-bound request
correlations. The automatic Hunt additionally retains a durable noncontent correlation
and progress record as described below. A lost response is reconciled against its original run, never replayed.
A missing correlation, including after process restart, remains unknown and cannot
refund consumed attempts or authorize a retry. Stop can reconcile a lost run identity
before completing the requested Stop; a failed Stop stays unconfirmed and retryable.
Original deadlines, leases, revocations and durable acquisition accounting apply.

Candidate assessment narrows complete name/alias families before decoding metadata.
The explorer filters and pages through prepared indexes while preserving selected-group
ambiguity. Checked account/catalog snapshots and final revision, Stop and original-lease
checks govern publication. See [account read preparation](account-reads.md#representation-policy).

These source capabilities require a separately qualified and delivered runtime.
Verify customer installation, current-reference usability and owner acceptance separately;
see [delivery and owner review](operations.md#shopping-owner-review-after-delivery).

## Collection intent

Find missing cards offers one current missing Pokémon per explicit search, or a species
in a retained goal. The picker reads the prepared account index independently of catalog
exploration. Select a region, target and optional all-in USD budget. Vintage preference
does not exclude other eras. General Shopping and explicit card/printing selection
remain available.

Target, scope, budget, preference, collection generation and goal version travel with
the temporary run and review. Back preserves authored form choices. Local recovery
neither acquires more results nor extends the lease. Changed ownership or an unavailable
or changed frozen goal requires explicit revalidation, never a replacement version.
Unsupported or stale prepared state remains unavailable.

Received, shown and filtered counts describe only the bounded provider batch. An
observed price below budget does not confirm all-in affordability. Unknown shipping,
tax and contents stay unknown. Assessment separates title mentions from included review
identities and counts each potentially new missing species once. Applied proposals and
selected identities remain unverified seller contents. Exact-printing ownership is
separate; possible collection fit does not establish reference value.

## Seller contents review

Opening an offer shows seller-text entries before the review forms. Each entry separates
stated quantity, unverified printing alternatives, identity cautions and source wording.
Repeated mentions need not mean extra copies. Expand a printing family or choose a local
correction; positive included quantities affect only the temporary review and its
conditional collection fit. Stock, lot units, seller card count and unknown remainder
remain separate. Correction search is paged; a contents family retains all alternatives.
Opening an offer or correcting a printing makes no new detail or model request.

## Returning from an assessed eBay lot

Compare shows the validated destination from the original offer. Auction ending time
uses the browser's timezone, or remains unknown. Opening eBay leaves Dex in its own tab.
On return Dex checks the saved comparison against the original review and source leases.
A changed or unavailable reference removes the prior ceiling and identifies the affected
card. Compare again uses eligible saved inputs. An expired review requires reopening
Shopping.

## Deciding on a lot

Use **Search options → Find missing cards** to choose one missing Pokémon, the current
collection or a frozen goal, a budget and vintage preference. **Assess lot** opens seller
entries. Expand **Source evidence**, then **Use offer in review** and **Correct identity
and quantity**. Include only printing identities and units supported by your review.
The scope line separates title mentions from possible gain on included identities.
A frozen goal can exclude a printing even when its species is missing.

Under **Bid, budget and purchase costs**, enter the planned bid and known charges.
**Compare** separates observed and planned all-in costs. Reference evidence identifies
each applicable printing, raw condition or literal grader/grade, quantity, source and
dates. Partial evidence supports only a subtotal. An auction ceiling requires complete
eligible value and costs and uses the lower of the reference and budget limits at whole
cents. Read the reason when it is unavailable. The next required bid and actual condition
still need checking. This is a conditional reference comparison, not a guarantee of value.

## Publisher-native guide projection

The existing lot assessment can expose publisher-native guide totals/subtotals in a
separate result field when independently admitted references and scoped seller
identity evidence exist. Unknown shipping/tax and condition remain visible. The
Publisher guide sort orders complete contents within a compatible source/date group;
partial contents stay separate. It makes no delivered-cost subtraction, savings or
bid-ceiling claim. Normalized comparisons retain their own outputs.

Numbered parents retain evidenced child alternatives. Missing seller traits leave
selection empty, including when only one alternative has a price. Alternatives are
not extra cards or automatic price ranges. Local expiry/withdrawal clears dependent
amounts while retaining these choices. No opening, sorting or filtering action
acquires prices or changes catalog data. Report actual active coverage from the
installation; supported source formats do not establish available prices.

## Automatic Hunt contract

`dex-lot-hunt-v2` deliberately replaces per-candidate clicks for this action. The
ordinary Find lots POST includes that contract and a fresh action UUID; the visible
form discloses its complete finite batch. Legacy Search/More, single-card Hunter,
manual listing checks and explicit detail contracts remain supported unchanged.
The new action consumes the existing `hunt-09-daily-v1` ordinary policy journal;
it creates no new allowance, increases no policy ceiling and cannot use historical
qualification/capture grants. A policy/package binding must already be valid.
An owner-selected per-Hunt limit of three cannot run this five-operation contract.

| Bound | Implemented maximum |
| --- | --- |
| Summary acquisition | Two pages, 20 summaries each; 40 received total; offset zero, no continuation |
| Buying lanes | BIN first, then auction; one page and one unique detail slot reserved for each |
| Auction eligibility | Aware future end, more than zero and at most 72 hours away; available offer |
| BIN eligibility | Available fixed-price option; no auction countdown requirement; ended/malformed explicit end rejected |
| Detail candidates | Two stable exact item/variation identities; unused lane slots are not transferred |
| Requests | One OAuth, two Browse, two detail, zero legacy-ID resolution; five total across the entire job |
| Response bytes | OAuth 32 KiB; each summary/detail response 2 MiB; 8 MiB + 32 KiB aggregate streamed bytes |
| Time | 30 seconds per request, 120 seconds from job admission for acquisition/assessment publication |
| Concurrency | One automatic job per installation across processes; one provider request at a time; zero model/photo calls |
| Content retention | Original 30-minute account/session lease; details, reads and optional review never renew it |
| Status payload | At most 40 fact rows; oversized assessment projections are withheld with an explicit reason |

Both discovery lanes run before any detail spending. Exact duplicate identities
(including a dual-option offer seen in both lanes) use one detail request; distinct
variations remain distinct. Out-of-window auction-only offers are rejected before
detail selection. Resolution is zero: numeric/unresolved parent identities are
skipped instead of buying extra resolution requests. Evidence reuse is confined to
the same valid original job; no cross-job content cache or lease refresh is created.

The saved, validated US destination is captured privately and sent through permitted
Browse context. It never enters status, URLs in Dex, or durable progress records.
Without a destination, calculated/unspecified shipping is withheld; explicit fixed
shipping may remain known. Full details replace summary market fields. Missing or
conflicting detail shipping never inherits a summary quote and never becomes free.

Every send reserves through existing durable Hunter accounting before transport,
then records its noncontent progress. Failed, uncertain and stopped in-flight
attempts remain consumed. No retry, reauthentication, redirect, provider fallback,
model call or recurring acquisition is added. Other authorized actions may consume
the shared daily capacity; a job then terminates exhausted rather than extending it.
The optional local assessment cannot grant provider or pricing-source authority.

Progress has `searched` (successful page responses), `received`, `unique`, `eligible`,
`enriched`, `assessed`, `ready`, `partial`, `unprocessed` and fixed reason counts.
Request counts separately include failed/uncertain admissions. `assessed` means the
available interface ran; it does not mean a complete monetary assessment. `ready`
requires an existing complete normalized or explicitly separate native result.
Missing prices/contents remain partial. Current reads recompute source-dependent
amounts and readiness, including withdrawal; no reference amounts are journalled.

Active states are queued, discovering, fetching_details and assessing. Terminal
states include success, partial, busy, exhausted, failed, stopped, expired,
conflict, unauthorized and restart_uncertain. Busy ends without a send; a later
explicit Hunt can use remaining policy capacity after contention clears. Polling
never drives work or retries a busy job. Deadlines/Stop prevent late publication;
account, login session, catalog/account revision and listing-content revision are
rechecked. A revision conflict removes content rather than silently rebasing.

The hashed append-only progress journal is beside independent Hunter accounting,
with private permissions and the same cross-process policy lock. It stores opaque
owner/correlation digests, counters, phases, original expiry and content revisions,
not query, postcode, seller text, prices, credentials or reference derivatives.
Replay is rejected by both the progress correlation and the existing parent record.
A process restart preserves progress/consumption but discards ephemeral content;
unfinished work reports restart_uncertain, never resumes or sends again. A completed
job after restart explicitly reports content unavailable. Corrupt progress fails
closed. There is no new customer schema or recovery from backed-up consumption.

Filtering, sorting, Back, polling, local value reload and optional review acquire no
provider data. Actual coverage, pricing admission, compatible delivery and customer
acceptance remain separate outcomes.


## Seller-stated contents

The automatic Hunt uses the existing deterministic parser/catalog path for full
seller title, description and structured aspects. It does not invoke a model or
process photos. Clear supported contents are selected automatically, including cards
unrelated to the search target. Optional review/correction stays in the existing
account/session-bound temporary review, with the original lease and revision checks;
no ownership or permanent research record is written.

Supported text includes hyphenated totals such as “37-card”, explicit per-card
multiplicities, natural numeric/word lists, copies, suffix quantities and conjunctions
between distinct card names. Literal catalog punctuation and names containing “and”
are preserved. Explicit all/both/each-card assertions and recognized structured
set/language/edition/finish aspects can supply shared seller scope. A name plus set
may resolve a unique numbered catalog family when no number is stated; an explicit
conflicting number, multiple numbered candidates, or missing physical traits cannot.
No edition, finish, language, checklist or set completeness is invented.

The versioned `dex-seller-contents-v2` projection separates seller total,
parent-identified quantity, physically selected/identified quantity, priced quantity,
identified-unpriced quantity and unresolved physical remainder. Provider stock,
platform lot units and explicitly stated lots offered remain separate. Repeated
mentions across fields do not add cards. Contradictory quantities withhold a numeric
remainder; a stated total alone never establishes complete contents. Printing
alternatives share one physical quantity, retain unpriced choices, and supply neither
a selected identity nor an automatic monetary range.

Each item carries literal mentions and separate scope mentions. `source_field`,
`start`, `end` and `span_basis: sanitized_text` reference Unicode character offsets
in the parser's sanitized `source_fields`; `aspect_names` maps aspect indices to
seller-specific field names. Markup, hidden script/style content and figure captions
are discarded without loading resources. These are ephemeral seller assertions, not
authentication, condition guarantees or photograph interpretation. Listing identity,
observation, expiry and content revision remain bound by the automatic Hunt envelope.

Specific sealed/mystery/random product claims are excluded; graded lines do not
enter automatic ungraded selection. Incidental packaging or unrelated graded-product
prose does not reject an ordinary binder. Negative, illustrative and instruction-like
claims stay outside selected contents. A complete-set claim remains an unresolved
checklist assertion even when individual listed cards can be selected. Unsupported
language/grammar, catalog gaps and work limits require optional correction; there is
no automatic model, cloud, photo or acquisition fallback.

Results distinguish unenriched summaries from enriched but unresolved contents and
from resolved contents lacking references. Identified cards remain visible when
prices expire or are absent. Normalized and publisher-native references preserve
their separate capabilities; native amounts never become savings or bid ceilings.
The finite Hunt contract is two 20-summary pages, one detail slot per
lane, at most two unique details, five total requests including OAuth, no retries.
Parser tests use authored seller evidence. They do not establish actual source
coverage or the contents of a live offer.


## Values, costs and ordering

The existing server calculator now selects one qualified comparable-sold estimate
per exactly selected ungraded printing, otherwise an eligible normalized guide.
Automatic Hunt assessments and corrected temporary reviews use the same path.
The result carries **Sold estimate / Guide / Mixed**, per-card evidence identity,
source, condition, valuation/build/capture dates, method and applicable sample
count, effective count, exclusions, sale span and descriptive spread. Guides have
no invented transaction counts. Card postage is not intrinsic value; guides and
their underlying sales are never averaged. Sample spread is not summed into a
statistical lot interval. Unresolved printing alternatives have no automatic price
or range and a sole priced alternative cannot select a physical card.

Seller total, parent-identified, physically selected, normalized-priced,
native-priced, identified-unpriced and unresolved quantities remain distinct.
Full normalized values require complete reconciled contents and compatible references
for every included unit. Corrected totals that disagree with the seller count stay
partial. Other results carry an identified-card subtotal and explicit gaps; missing
prices preserve identified cards. Native publisher numbers retain unknown shipping,
tax and condition and use separate compatible source/date-cohort sums. They cannot
enter normalized totals, delivered differences, savings or bid ceilings.

`dex-lot-value-v3` exposes independent observed `benchmark_costs.auction` and
`benchmark_costs.buy_it_now`: base, applicable shipping, delivered-before-tax cost,
full difference or separately named subtotal difference, eligibility and cost issues.
Missing bids never inherit BIN. Unknown/ambiguous shipping is not free. Currency
mismatch, invalid money and totals over the shared cap withhold comparison. Arithmetic
uses bounded Decimal inputs, sums exact terms and rounds the comparison once.
Ended/unavailable offers, invalid dates and ineligible auction windows have no numeric
comparison. Available BIN has no auction-window prerequisite; auctions require an
aware future end with at most 72 hours remaining, inclusive at exactly 72 hours.
These are before-tax benchmark differences, not resale profit or guaranteed savings.
Personal planned bids, tax-aware reviews and strict condition-specific ceilings
retain their existing separate requirements. A sold median is not a strict ceiling.
The optional review backend exposes `benchmark` beside its existing strict assessment.

`dex-lot-order-v1` supplies auditable ranks over the currently acquired batch:

1. Each eligible lane independently groups complete normalized comparisons, partial
   subtotals, unknown costs, then unpriced results. All groups remain accessible.
2. Within complete and partial groups, sort by that lane's supported amount minus
   its delivered-before-tax cost, descending, retaining negative differences.
   A partial score is explicitly not a whole-lot bargain score.
3. Ties use priced physical quantity descending, oldest contributing reference date
   descending, auction end ascending for the auction lane, then stable item/variation
   identity ascending. BIN ties never use the bid or auction countdown.
4. Native ranks are separate for each lane/cohort. Complete native contents precede
   partial contents; compatible totals/subtotals sort descending with the same
   coverage/date/end/identity tie breaks. Incompatible cohorts have no common money rank.
5. The compatibility combined view uses BIN whenever that offer has an eligible BIN
   lane, otherwise auction. It never chooses the better of a dual offer's two prices.
   The client consumes server ranks; sorting/filtering acquires nothing.

References are recomputed on reads. Operation-local contributing-evidence hashes
are rechecked against the existing source lifecycle before publication, including
changes to underlying sold samples with an unchanged aggregate. Source expiry,
withdrawal and changed admission cannot reuse previous derivatives. Client pruning
clears dependent totals, differences and ranks while retaining identities and valid
unrelated card references/native cohorts. Late responses undergo the same pruning.
Original leases, Stop, account/session/revision checks and restart uncertainty remain.
No reference store, persistent value cache, provider action or allowance is added.
The Hunt retains two 20-summary pages, one detail slot per lane, at most two unique
details and five total requests including OAuth, with no retries or capacity transfer.

Qualified calculation tests do not establish real priced coverage. Report eligible
native guides, normalized guides and sold references separately from the active
installation, with their actual expiry and source limitations.


## Automatic results experience

Enter a Pokémon/card name, optionally select a set and choose **Find lots**. General
search needs neither collection ownership nor a missing-species goal. Search options
start collapsed for ordinary entry; an inherited missing-species journey opens its
selected controls. No listing-by-listing Load, Interpret or Compare is needed for the
available automatic assessment. **Assess lot · optional correction** reuses the
existing temporary review and original source lease.

The result controls select auctions within 24, 48 or **72 hours maximum**, available
Buy It Now offers, or the compatibility combined view. Auction and BIN ranks are
independent server-issued `dex-lot-order-v1` ranks. Combined ordering selects the BIN
comparison when available, otherwise auction; it never chooses the better dual price.
Legacy longer-window return URLs are capped at 72 hours. Local evidence filtering
supports Sold estimate, Guide, Mixed, native guides and the default all-evidence view,
which includes unavailable results. Local controls never acquire or refresh data.

The repaired Find lots list groups **Complete assessments**, **Partially assessed**,
**Unknown delivered cost**, **Assessed without a normalized value** and **Unprocessed**
separately. Negative comparisons stay
visible. A partial difference is labelled identified-card subtotal minus delivered
cost, not a whole-lot bargain score, and leaves the remainder unvalued. The client
consumes `dex-lot-value-v3` amounts and server ranks; it does not calculate financial
values or retain a separate valuation cache. Ending-soonest is a local time sort.
The old client-side highest-total sort is no longer offered.

Each card immediately shows value or identified-card subtotal, evidence basis,
normalized-priced versus seller-stated count, selected physical quantity, observed
price, shipping, delivered-before-tax cost, applicable differences, observation time,
auction timing and the main uncertainty. Both observed costs stay visible on a dual
option even when one buying lane is selected. Unknown is not free or zero. Current
bids are provisional and BIN observations are not reservations.

The authenticated list response fits within 120 KiB. **Cards and value evidence**
reads one assessed listing from its original local lease. This read checks the account,
session, catalog, content revision and contributing sources again. It opens all
supplied identified contents, including cards
outside the search target, card-level reference condition/source/dates/method and
applicable sale counts, effective samples, exclusions and descriptive spread. It also
shows literal seller evidence, unresolved alternatives and optional correction.
Seller assertions do not authenticate a card or guarantee its condition. Numbered
parent identities, selected physical cards, normalized-priced, native-priced,
identified-unpriced and unresolved quantities remain distinct; the overlapping measures
must not be added. Stock and lot units are not physical card counts. Alternatives are
not extra cards, automatic selections or price ranges.

Publisher guides remain separate source/date cohorts. **Publisher guide contents**
shows a heading for each compatible cohort and uses only its server rank: larger
publisher contents sums first, complete before partial. The page explains that this
is not best-deal ranking. Unknown shipping/tax basis and condition limitations remain
visible. Native amounts are never pooled with normalized amounts or used for delivered
differences, savings or bid ceilings; incompatible cohorts have no common money rank.

Progress names queued, discovering, fetching details, assessing and terminal outcomes.
It shows successful pages searched, summaries received, enriched, assessed and
unprocessed counts. The unchanged `dex-lot-hunt-v2` allows **two 20-summary pages,
one detail slot per lane, at most two unique details and five requests including
OAuth**. The selector first maximizes distinct eligible lane slots. Among feasible
pairs it favors seller summaries without explicit random or mystery wording, then
mixed lots naming the target with itemization signals. Selected-set mentions,
collector fractions, quantities and structured contents help resolve ties. Stable
offer IDs break remaining ties. Selection is a reason to read details. Only the
seller-content parser can select a physical card. Busy, exhausted capacity,
partial acquisition, assessment failure and restart uncertainty give finite outcomes
and explain that reads do not retry. An all-unavailable batch remains visible;
summary-only listings differ from fetched but unresolved contents. Status reload is
local, not acquisition. The browser bounds a local request wait to 12 seconds and
retains uncertain acquisition status for reconciliation rather than resubmitting.

Completed visible results recheck their original run locally every five seconds;
existing one-second source/expiry checks remain. Returning to the tab withholds
previous monetary values/ranks while current run authority is checked. Stop clears
the visible result contents immediately while confirmation is pending. Sequence,
account/session, revision and original-lease checks reject late responses. Source
withdrawal removes dependent totals and ranks without inventing replacements. Local
patching preserves evidence expansion and keyboard focus when a result remains.
Back restores checked filters and the opaque run handle, then rereads the service;
no seller contents or monetary result enters browser storage.

Optional corrected review shows its supported **Before-tax benchmark** above the
separate strict tax-aware assessment, personal planned bid and conditional ceiling.
A missing strict ceiling does not hide a supported benchmark. Editing invalidates
both; return checks compare both projections, and their contributing references share
the existing withdrawal/expiry handling. Corrections preserve reconciliation and
original leases and never change collection ownership.

The checked exact seller offer opens deliberately in a new tab. Dex does not buy or
bid. Browser/keyboard/narrow-layout tests use authored isolated fixtures; they establish
engineering behavior only. Source admission, authorized acquisition, activation,
compatible delivery and real useful-price acceptance remain separate.

## Release boundary

The complete automatic Hunt is packaged separately for release qualification. The
finite five-request contract, independent lanes, original leases and accounting are
unchanged. Native guide content remains separate from normalized deal ranking. The
release record must distinguish local artifacts from hosted checks, installation
and actual useful-value proof. Follow [runtime delivery](operations.md#runtime-updates-and-recovery)
and [source lifecycle](price-snapshots.md) within existing authorization. Neither
procedure alone establishes live acquisition permission or owner acceptance.

Automatic assessment reads reference ranges for the complete candidate families
identified in seller text. Final publication rereads contributing evidence and checks
withdrawal, expiry and current authority. It does not retain prices between requests.
Status publication serializes with worker content changes; session authorization
preserves an active database read transaction and rechecks the session before return.

Each assessed listing uses its own catalog candidates in catalog order, so list summaries and local evidence expansion have the same evidence identity regardless of the other selected lot. A changed evidence reply closes its disclosure before refreshing local status; it cannot reopen itself in a request loop. Explicit `SET / EDITION: All ...` seller headers apply to the supplied contents while literal card variants remain required.

Per-card multiplicity accepts an explicit number followed by `x` or `×` after the card name, as well as a leading count. Multiplicity does not become a collector-number claim; invalid counts remain unresolved and explicit conflicting collector numbers remain conflicts.

Standalone official-detail loads under ordinary usage settings capture their own temporary policy binding. OAuth and details, including legacy-ID resolution, debit the same preserved shared accounting. They do not require a legacy Hunter parent; Stop, policy pause, expiry and per-action limits remain enforced.

Indented numbered-card attribute lists attach to their own explicit card heading. Dated headings do not become quantities; explicit copy counts retain priority. Literal multi-finish aspect lists remain choice sets and cannot override per-card finish evidence. Separate numbered sections retain their allocations; broader matching repetitions do not add copies. Conflicts and unsupported sections remain unresolved. Native guide evidence is shown beside the selected card even when no normalized reference exists.

Standalone official details now use the same seller-selected contents projection as automatic Hunt details. Reviewed comparisons and local Back/return carry the separately labelled native benchmark as well as the strict assessment; neither route exposes save payloads or refreshes prices.

### Quick lot filters and value badges

The results toolbar offers All lots, With estimates, and Below estimated value.
With estimates retains partial estimates, explicitly labeled as known cards only.
Below estimated value requires a whole-lot estimate and known price plus shipping;
unknown shipping and partial contents never produce a discount badge. Green means
at most 90% of the estimate, amber is above 90% but below 100%, and muted red is
100% or more. These are ungraded reference comparisons, before tax, not profits.

Value filters operate on received results without acquiring more listings and
survive navigation through temporary review. Details retain the full evidence.
Rows show three card names, a count of remaining names, seller photo, price,
estimated value and a badge. Response compaction preserves seller image URLs.
