# Interface design

Dex uses system typography, neutral surfaces and a red, white and black palette.
Red identifies primary actions and selection. Shared primitives live in
`beta/static/glass.css`; application styles live in `collection.css` and `public.css`.
Django templates and plain CSS/JavaScript require no external design workspace.

This guide describes the source interface. Installed runtimes can differ from the
checkout; [local development](local-development.md) explains runtime selection.

## Navigation and access

The header offers My Cards, Card Library, Pokédex, Shopping and Add Card. The menu
opens Collection tools, Settings, authorized Administration and Sign out. Collection
tools contains Goals, physical copies and Overview. Settings contains import/source
maintenance and available catalog requests/coverage. Administration rechecks roles.
Add Card offers catalog selection or available photo entry without starting a job.
Ordinary card browsing and detail use the main navigation without a duplicate
collection task bar; collection tools remain in Menu. My Cards also offers a direct
Add many cards shortcut.

Shopping leads with Pokémon/card name, optional Set and Find lots, in that order.
The ordinary lot finder uses US mixed lots and ending-soonest order; broader
controls remain hidden under the ordinary flow. Stop stays beside
Find lots while a search runs. Explicit eBay search supports loose mixed lots, singles and
auctions. Check a listing/lot remains directly available, with secondary links
to the lot calculator, retained saved finds, Packs to open, independent Pack lookup
and saved pack research. Classic hunt/missing pages direct new searches to Shopping;
they do not offer retired live/sample or continuation actions. Packs
to open asks for an account-owned goal when none was supplied. Following navigation
does not search a provider, refresh prices, start recognition or change inventory.

| Capability | Signed out | Signed in |
| --- | --- | --- |
| Species #001–251 and published card metadata | Public | Private progress where supported |
| General Pack lookup and dated offers | Public | Also supports private goals and saves |
| Owned/missing filters, copies, goals and import/export | Sign-in required | Account scoped |
| Photos, eBay searches and saved research | Explanation or sign-in | Account scoped; capability/provider configuration applies |
| Catalog publication and review | Sign-in required | Role and capability checks apply |

Guests never select an account, infer zero ownership or receive private source/photo
records. Sign-in honors safe return destinations. Sign-out invalidates private browser
state across tabs. Brand home reopens only a successfully rendered, finite,
reauthorized collection destination; invalid memory falls back to My Cards.

## Cards

`/cards/` is My Cards; `/card-library/` is the separate catalog. Both group variants
beneath a literal card identity. Each compact tile opens its canonical card page
without choosing an exact child printing. Search and Set are direct controls; sort
and variant filters are secondary. Complete filter options include owned archived
sets and do not depend on a single result page.

Card Library and My Cards use a neutral canvas, aligned controls and restrained red
emphasis. Images retain a fixed area and honest fallback. Ownership badges remain
readable independently of artwork. Optional grey unowned artwork is a local visual
preference; hover/focus restores color and never changes collection state.
This preference appears in Card Library, where unowned cards are present. Owned-card
counts and catalog counts use distinct labels. Unavailable artwork uses a quiet card
outline and an explicit unavailable label instead of an implied image.

Card detail leads with name, set/number, ownership, known quantity and Add/Edit.
On narrow screens these facts and actions precede artwork. Show the reference-image
qualification once. Your collection follows with compact copy records and direct
Edit; edition/removal actions remain available. Broad ownership requires no copy,
variant or quantity. Exact copy creation requires an explicit supported printing.

Known card facts and value evidence have separate areas. Omit absent nonessential
rows and empty removed-copy history. Record details exposes internal references,
image diagnostics, relevant history and operation/undo access. The editor retains
binder, purchases, dates, grading, certificates and notes; closing advanced fields
preserves their stored values.

Unknown totals stay unknown, independently of recorded copy counts. A card total is
not a variant quantity or valuation multiplier. Reference scans, exact-child assets
and private copy photos have [different roles](artwork.md). Missing artwork never
changes identity, status or destination.

## Pokémon and completion scopes

Pokédex shows canonical species #001–251 with Pokémon artwork, number, name and
current collection status for signed-in users. Progress sits with the heading.
Search, Region and Show within scope stay direct; card criteria, saved goals and
catalog/date coverage are secondary disclosures. Select reveals batch controls;
search-hidden selections are counted, and region/goal changes clear them.

A species opens as a normal page in one click. Your Cards follows identity/status
and shows each current owned group once; its card opens in a second click. Explore
species cards links to Card Library. Empty, unindexed and species-only evidence
remain useful states without fabricated cards. Species quantity is unknown.

Current completion supports multiselect sets/eras, card category, rarity, finish
and release periods, plus custom inclusive date ranges. Choices within a dimension
combine with OR; dimensions combine with AND on one evidence record. Searchable
checkboxes prepare a draft; Apply evaluates it. Applied chips describe the result.
Removing a chip or Clear card scope applies immediately and discards unapplied edits.
Clear retains the target/search/display choices.

The target checklist and denominator stay stable: Original 151 shows N/151 even if
some species have no eligible indexed printing. Duplicates count once. Overall
ownership, current scoped progress and frozen saved-goal progress retain distinct
labels. Unknown metadata, no eligible indexed printing and ordinary missing ownership
have different states. Filtering never edits ownership or a goal policy.

Pre-2000 means before January 1, 2000; 2000 onward includes that date. Use only
admissible release evidence for the printing/language. Unknown dates qualify only for
an explicit Unknown choice. Coverage details stay visible for dated scopes. Set
choices do not establish the pack an owned card came from. See [catalog date
policy](catalogs.md#scoped-release-evidence).

Species details separate qualifying owned cards, owned cards outside the scope and
unresolved evidence. Scope values and the editor's expanded state survive validated
navigation and reload. These are current views; named-view persistence is unavailable.

## Shopping

The lot finder aligns name, optional Set and Find lots/Stop in one desktop row.
Narrow layouts preserve that same field-to-action reading order. Hidden broader
refinements consume no layout space. Short selected values
need no repeated caption; a measured clipped native selection receives its complete
wrapped caption, including at enlarged text sizes. The Set control remains a native selector on narrow screens. Idle readiness
needs no instructional paragraph. Progress, blockers, errors and Stop remain visible.

Desktop received offers pair compact thumbnails with complete titles; narrow
layouts retain larger loaded photos and reduce unavailable-image placeholders.
Keep unknown costs readable and preserve access to larger offer imagery in inspection.
Desktop review costs share an aligned row and local card search sits beside its action;
these controls stack on narrow screens. Routine counts use neutral separators rather
than warning surfaces.

Received offers retain stable photo areas and complete titles. The listing amount
has stronger emphasis than ancillary costs; unknown costs stay explicitly readable.
Results filters and counts sit together. Inspection leads with the offer, price and
seller action; review is secondary, and closed setup/research disclosures use simple
rows instead of separate empty panels. Review inputs stack on narrow screens. The
zero/unknown remainder distinction stays beside its field; extended help stays in
one named disclosure. Calculations, temporary retention and source rights are unchanged.

Price Hunter at `/shopping/hunter/` leads with Find cards and an independent Stop.
The ordinary page searches ungraded singles; editable cost assumptions support a
conditional net estimate. Unknown inputs leave the estimate unavailable. Usage
settings and local result pages remain distinct from new acquisition actions.

The heading and compact action row precede one Cost assumptions disclosure.
Listing price and numeric net estimates carry the strongest weight; unavailable
estimates remain readable without oversized emphasis. Reference date and condition
stay visible. Reference & costs contains the source, capture time and itemized
costs. An unmatched seller title appears once, and unavailable artwork uses a compact
reference placeholder. Empty progress containers take no space.

Shopping and Hunter share the temporary listing-analysis panel. Editable claims
sit beside their quoted evidence in a responsive field grid; warnings and unknowns
remain visible, with complete original seller text in one disclosure. Stop clears
the panel, announces the stopped state and returns focus to the analysis button.
Edits remain temporary and do not apply collection or price changes.

Temporary lot review leads with Ungraded, quantities and the unresolved remainder.
Attribute/cost corrections, seller provenance and additional official details are
secondary. Input changes withhold obsolete comparisons; stale revisions reload
without resubmission. Back restores a revalidated result, scroll and keyboard
focus. Lifecycle reads preserve focused result controls, and independent detail
Stop remains reachable across Back. Enlarged text and narrow layouts must retain
readable controls, focus and recovery actions.

The retained catalog explorer shows Pokémon artwork for broad names and current collection context. Choosing
a Pokémon reveals card references; detailed name/set/number searches show card scans
and leave plausible printings as choices. Its set controls apply to local catalog filtering. The ordinary lot finder uses
a separate seller-set facet for provider search. Images never depict seller contents.
Local edits and Back never acquire listings.

Species, card and goal Find links carry a server-checked context. A group without
an explicit child stays at card-reference scope until a printing is deliberately
selected. Archived or unsupported targets remain unavailable. Entry opens the contextual lot finder; provider search, comparison and saving
remain explicit.
Current possession and frozen goal policy remain distinct.

The compact assisted review leads with Ungraded and included quantities. Printing,
condition, grading and cost corrections are optional disclosures. Current auction
bids, buy-now asking prices, planned manual bids and final purchase costs remain
distinct. Unknown contents or reference coverage produce a priced subtotal.

The secondary manual calculator keeps search beside the working lot and four
independent grade scenarios. On narrow screens search comes first, then the lot, then matching cards.
Search submission moves to matches; grade values use two columns. Compare is primary;
add, clear and history use quieter treatment. Full selected printing names wrap below
native controls.

Only evaluated totals appear. Quantity, price, date and cost edits hide stale results
until explicit Compare. Search and wanted-target edits retain the calculation. Empty
graded values stay hidden until eligible references exist. Unknown costs, dated prices,
partial coverage and condition/edition assumptions remain beside the relevant result.

Per-tab drafts retain user inputs only. Reentry revalidates identity and local
references, then requires Compare. Price cells, source records and results never
enter draft storage. A draft's wanted choices require confirmation if they differ
from current session wants. Withdrawn/expired references disappear without losing
user-authored quantities and costs. [Shopping](hunts.md) documents full behavior.

Pack lookup puts target coverage before products and dated offers. Possible pulls
and guaranteed contents remain separate. Unknown costs or old stock observations do
not become current purchase evidence. Full reasons and history stay in disclosures.

## Adding many cards

Add Card offers batch entry and single-card selection as clear choices; existing
photo entry is secondary. Manual bulk leads with input method, Set and action. Keep
one emphasized Review action in the batch summary beside the desktop checklist and
before the long list on narrow screens. Selected rows and their Edit actions remain
directly visible. Preserve selections across searches and sets without nested scrolling.

Draft recovery, cancellation, separate physical batches and checked-row tools appear
only in their relevant states. Review separates rows and actual effects; internal IDs,
revision and generation stay in record details. Unknown totals, copy evidence, excluded
rows and row errors retain their meaning. Confirmation still applies exactly the
reviewed batch. A failed catalog load leaves selection unavailable with focused recovery;
an in-flight action locks conflicting edits. Close/Escape and Save return focus to
their respective originating or saved-row controls.

## Photo entry

Add from photos uses the same neutral surfaces, red primary action and readable
control sizes as Shopping. The working column is limited to 52rem. New photo opens
on first use, then collapses when analysis or review begins, retaining the file and
notes. The provider/account disclosure remains beside Identify. Stop and failures
stay outside the collapsible upload area.

Review leads with card count, images, identity, Include and optional corrections.
Results receive keyboard focus when first shown. Missing images have an explicit
fallback; unknown matches remain excluded and open for correction. Import/duplicate
policy, consent, confirmation and Undo remain unchanged. Empty saved-photo history
and redundant idle/review instructions are omitted. Reports keep itemized effects;
retry and Undo use secondary styling.

## Interaction and accessibility

Ordinary browsing uses pages; focused editing and confirmation may use dialogs.
Back restores the originating tab, validated filters/scope, page, scroll and focus.
UI return context never becomes an API filter or canonical identity. Route, account,
session and generation guards reject obsolete responses. Cancellation never confirms;
uncertain writes recover saved operation status.

Use consistent type sizes, margins, input heights and content widths. Keep controls
at least 44px high, labels associated, keyboard focus visible, skip links usable and
dialog handback predictable. Long selected values need complete wrapped captions.
The expanded header menu participates in document flow. At 320 CSS pixels and enlarged
text, controls and identifiers must wrap without covering content or scrolling sideways.
Respect reduced motion/transparency and provide opaque fallbacks.

Loading removes old actions; errors retain inputs and focus an actionable message.
Invalid card-browsing filters or return links give fixed browsing guidance and a safe
My Cards recovery destination (`/cards/`), without import instructions or submitted
values. Existing JSON responses remain JSON; rendered errors retain Back to cards.
Actual imports and mutations keep their existing format/review guidance.
Empty/unavailable states explain the limit and a supported next action. Guide dates,
unknown attributes and missing images remain explicit without repeating full policy
text throughout the page.

For changes, check keyboard use, cancellation, Back/reload, long labels, empty/error
states, image failure, account isolation and actual text enlargement. The [CI browser
harness](CI.md) uses synthetic data; it does not establish native-device, screen-reader
or human usability results. Customer walkthroughs use the existing installation and
its actual available state.

## Checking interface changes

Use disposable synthetic data for engineering layout checks and the established
installation for a user's own collection. Check desktop/narrow layouts, enlarged
text, keyboard focus, long names, unavailable images and slow/error states. Cover
collection versus Library, current versus frozen progress, deliberate confirmation,
Stop and Back/reopen without new acquisition. Automated or synthetic checks do not
establish real recognition accuracy, source freshness or marketplace outcomes.


## Responsiveness contract

Guest and signed-in browsing share responsiveness requirements across My Cards,
Card Library, Pokédex, filters, pagination and details.

Navigation and search controls must appear promptly. Primary card results must not
wait for secondary filter metadata or remote artwork. Use stable placeholders and
progressive rendering without flashing false empty results or wrong ownership.
Distinguish loading, empty, unavailable, stale/conflicted and failed states, with
useful bounded recovery. Navigation preserves valid filters, page, scroll and focus;
late responses cannot replace a newer route, account or query. Keyboard navigation,
narrow screens and enlarged text must remain usable. A failed secondary request
must not erase valid primary results or enable unsupported filter choices.

Targets on the ordinary local installation are useful cards within one second of
navigation after server restart, and routine local search/filter/page/detail updates
within 300 milliseconds. Useful cards means correct text, ownership where authorized,
and working primary actions; remote artwork may complete separately. A loading shell
alone does not meet the target. Measure startup-to-ready separately so moving work
into startup cannot conceal a long launch delay. The startup budget is two seconds; measure it separately from navigation.
[Qualification](CI.md#browsing-performance-qualification) defines repeated measurements.

[Startup, API, payload and client budgets](CI.md#performance-budgets)
and the [V2 read contract](card-groups.md#versioned-bounded-api). Clients render
primary cards as soon as their authorized response is ready, independently of filter
options and art. Disable only unfinished secondary controls; do not delay the whole
screen with `Promise.all`. Fetch account context once per navigation authority epoch,
reuse complete filter choices only at matching account/catalog/collection revisions,
and avoid requesting both full species identity and full group projections.

Use separate paged detail/evidence sections without implying the first page is the
complete record. A 409 invalidates the retained revision and permits one fresh read;
a 503 shows unavailable state and explicit recovery; neither may cause an automatic
retry loop. Empty means a successful current query returned zero matches. Preserve
valid results on secondary errors, with clear retry for that failed section.

## Bounded interface behavior

The [frontend implementation](frontend-reads.md) renders card text, ownership and primary
actions from a bounded response before filter choices, children, copy records or art.
Choices and detail records have explicit continuation; bounded label resolution retains
selected IDs and readable labels off-page, through reopening, reload and Back. Bulk
has separate this-page, all-matching and cross-page range actions, preserving off-page
draft rows with an explicit whole-batch limit and revision-consistent selection.

Goals uses saved headers, frozen target pages and source-choice pages. Missing historical
filters are never inferred: rename preserves the exact checklist/version, and replacement
creates a separate goal. Frozen declaration progress is labelled separately from current
possession and qualified-current-copy progress.

Prices distinguish unloaded copy records from absent evidence. Open Recorded copies
first, then inspect retained guide scenarios for those loaded copies; additional pages
require reopening the price disclosure. A partial page never claims complete evidence.
List and detail artwork loads independently with reserved layout, reviewed source rights,
bounded descriptor batches and visible-image concurrency. Secondary failure preserves
usable primary results. Access revocation clears private results and provides sign-in;
confirmed receipts remain recoverable and undoable when derived browsing is unavailable.

Check keyboard focus, scroll restoration, narrow screens and enlarged text with
the [frontend test commands](frontend-reads.md#renderer-and-workflow-tests).
