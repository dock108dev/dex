# Interface design

Dex uses system typography, neutral surfaces and a red, white and black palette.
Red identifies primary actions and selection. Shared primitives live in
`beta/static/glass.css`; application styles live in `collection.css` and `public.css`.
Django templates and plain CSS/JavaScript require no external design workspace.

## Navigation and access

The header offers My Cards, Card Library, Pokédex, Shopping and Add Card. The menu
opens Collection tools, Settings, authorized Administration and Sign out. Collection
tools contains Goals, physical copies and Overview. Settings contains import/source
maintenance and available catalog requests/coverage. Administration rechecks roles.
Add Card offers catalog selection or available photo entry without starting a job.
Ordinary card browsing and detail use the main navigation without a duplicate
collection task bar; collection tools remain in Menu. My Cards also offers a direct
Add many cards shortcut.

Shopping leads with one image-led local search, quick set choices, Find deals and
Find missing cards. Explicit eBay search supports singles, loose mixed lots and
auctions. Check a listing/lot remains available, with links
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

Price Hunter at `/shopping/hunter/` leads with Singles/Lots/Both, Hunt and an
independent Stop, followed by readable scope/progress and image-led received
results. Coverage/accounting detail is secondary. Local result pages and explicit
Continue acquisition have distinct labels and request contracts. Disabled
acquisition explains unavailability before a search. The existing merged visual
search and calculator remain separate Shopping tools.

Temporary lot review leads with Ungraded, quantities and the unresolved remainder.
Attribute/cost corrections, seller provenance and additional official details are
secondary. Input changes withhold obsolete comparisons; stale revisions reload
without resubmission. Back restores a revalidated result, scroll and keyboard
focus. Lifecycle reads preserve focused result controls, and independent detail
Stop remains reachable across Back. Measured text enlargement and narrow-layout
checks are engineering evidence, separate from owner/device acceptance.

Broad Pokémon names show Pokémon artwork and current collection context. Choosing
a Pokémon reveals card references; detailed name/set/number searches show card scans
and leave plausible printings as choices. All supported sets and quick set buttons
apply locally and to the submitted eBay phrase. Images never depict seller contents.
Local edits and Back never acquire listings.

Species, card and goal Find links carry a server-checked context. A group without
an explicit child stays at card-reference scope until a printing is deliberately
selected. Archived or unsupported targets remain unavailable. Entry opens the merged
visual search; quantities, provider search, comparison and saving remain explicit.
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

## Design checks

### Current owner review

UX-05 remains an owner verdict on the genuine installed collection interface.
Use the [recorded installation and existing helper](local-development.md#existing-installations),
not old launcher/runtime instructions from historical handoffs. Review My Cards
versus Library, species/card images, current versus frozen progress, editor cancel,
scope Apply/Clear, Back/filter/focus and narrow/enlarged text. An actual collection
change requires owner-selected real input and complete Review/Confirm.

For delivered SHOP-04, search Hypno, Alakazam or Gengar; choose a Pokémon, refine
by set, and inspect the card references and current Missing context. The
[Shopping guide](hunts.md#one-visual-pokémon-card-and-ebay-search) describes explicit
offer search and Ungraded review. Local browsing alone does not call eBay; another
provider action is separate from closed engineering qualification allowances.
Record acceptance or the page/action, observed result and expected behavior for
a concrete repair. Tests and engineering walkthroughs do not supply the owner's
verdict. Photo-batch real testing remains deferred; the Price Hunter is not yet built.

### Engineering review

Review representative first-use, populated, unavailable and failure states at matching
viewport sizes. Check My Cards versus Card Library, species and card detail, ownership,
unknown totals, artwork fallbacks, direct editing and cancellation. Return through
filters, scopes, page position and keyboard focus. Date and multiset scopes must retain
the selected denominator and distinguish current overall from frozen-goal progress.

Use isolated synthetic state for engineering previews and the existing installation
for customer walkthroughs. Keep missing photos, archived examples and prices explicit;
never substitute fabricated customer data. Inventory changes require an intentional
user action. Technical checks do not establish human usability, recognition accuracy,
provider entitlement or release readiness.
