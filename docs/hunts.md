# Shopping and eBay discovery

## One visual Pokémon, card and eBay search

Shopping starts with local catalog search. Broad Hypno, Alakazam and Gengar names
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

## Navigation

Open **Shopping** at `/shopping/` for visual local search, **Find deals**,
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
manufactured-year facets are not guessed. The supplied 1995/1999/2001 web choices
never become a continuous date rule or change collection membership. Vintage retained
reference coverage and all-era catalog browsing remain independent.

**Find missing cards** defaults to **Current collection · Original 151 · species**.
Current collection also offers exact-printing policy; a frozen goal is optional. A selected goal retains
its captured membership and ownership policy. Broad ownership declarations do not
establish every edition/finish. Search is read-only for inventory and goals.

Search starts only on explicit action. **Stop** cancels acquisition and suppresses
late publication. **Next results** continues the captured choices and next catalog
queries, deduplicating across batches. Edited choices require a new search. Filters,
reveal, Back and reopening perform no provider requests. Titles, identities and seller
links respect reveal preferences; seller text proposes identity, without physical
verification.

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

Discovery results and provider summaries are temporary server memory. They are never
written to raw hunt history, browser storage, exports, reports or backups. Saving
these results is unavailable; the product explains that limitation. Existing saved
research remains available under its original rights checks. Reopening temporary
results requires the same authenticated session and a surviving server run; a restart
requires a new explicit search. Local reads do not renew source rights.

## Finite acquisition

Each explicit Search or Next action admits at most **one OAuth and four Browse
requests**, at most **20 summaries per Browse**, **30 seconds per request** and
**75 seconds overall**. The normal action uses one Browse request. An independent acquisition deadline
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
Opening a revealed discovery offer transfers its checked temporary summary and
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
