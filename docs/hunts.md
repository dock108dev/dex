# Shopping and eBay discovery

Shopping combines local catalog browsing, explicit eBay searches and dated-reference
comparisons. Catalog and reference coverage are partial. Missing identities, costs
and reference values stay unknown. The app never buys, bids or guarantees a bargain.

## Search and browse

Type a Pokémon or card name, optionally choose a set, and select **Search eBay**.
Mixed lots is the default; Singles and Both are alternatives. A goal, exact printing,
collector number, budget or wanted list is not required. Search options and local
catalog exploration are optional. Spelling suggestions allow either a correction
or the original text; neither starts a request automatically.

Results show seller titles, checked links, available photographs, price/current bid,
shipping, known total and auction time. Unpriced and uncertain lots remain browsable.
Seller photographs, catalog scans and private collection photos have distinct roles.
A card named in a query or title does not establish the contents or value of a lot.

## Named search and continuation

Named search uses one official Browse category per request: Mixed lots selects
**183455**, Singles selects **183454**, and Both alternates the two captured lanes.
Category selection is independent of words such as “lot” in the query.

Search eBay captures text, optional set, category choice and sort. It needs no local
catalog match. Set overrides replace conflicting recognized aliases, preserving
Base Set versus Base Set 2. English/vintage words are optional and initially off.
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

## Price Hunter screen and temporary review

`/shopping/hunter/` is the authenticated Hunter journey, linked from Shopping and
its tools navigation. Choose Singles, Lots or Both and explicitly Hunt. No goal,
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

## One visual Pokémon, card and eBay search

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

## Find deals and missing cards

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
price. Summary shipping shows the cheapest explicit supported USD option; review
inputs require an agreed amount/currency across the supplied options. Missing auction
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
Opening a selected discovery offer transfers its checked temporary summary and
original expiry without another provider operation. Extra official details require
**Load additional official details**; manual URL/ID entry remains available. Listing stock,
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
operations. Assisted inputs/results are not saved/exported or written to browser storage,
raw hunt history, logs or backups. The UI explains this restriction; existing saved
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

Completed-sale comparison is not implemented. Active Browse listings and item
details do not establish sold-history access or actual sale prices. Dated catalog
reference values are not sold comparables. Research completed sales separately;
Dex does not infer entitlement, scrape sale history or turn active asking prices
into realized values.
