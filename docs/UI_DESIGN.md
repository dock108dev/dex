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

Shopping's task bar links the lot calculator, eBay searches, missing-card search,
saved finds, Packs to open, independent Pack lookup and saved pack research. Packs
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

Species, card and goal Find links carry a server-checked context. A group without
an explicit child requires a printing choice. Archived or unsupported targets remain
unavailable. Entry never fills quantities, changes collection/goals, searches, compares
or saves automatically. Current possession and frozen goal policy remain distinct.

The calculator keeps search beside the working lot and four independent grade
scenarios. On narrow screens search comes first, then the lot, then matching cards.
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
Empty/unavailable states explain the limit and a supported next action. Guide dates,
unknown attributes and missing images remain explicit without repeating full policy
text throughout the page.

For changes, check keyboard use, cancellation, Back/reload, long labels, empty/error
states, image failure, account isolation and actual text enlargement. The [CI browser
harness](CI.md) uses synthetic data; it does not establish native-device, screen-reader
or human usability results. Customer walkthroughs use the existing installation and
its actual available state.

## Owner review of the installed app

Use the existing installation and ordinary sign-in. Confirm My Cards and Card Library
have distinct meanings; open Pokédex, a species, Your Cards and a card. Check ownership,
unknown totals, artwork fallbacks, optional details, direct Edit/cancel and numeric card
ordering. Return through filters, scopes, page, scroll and keyboard focus. Compare
pre-2000, 2000-onward and multiset scopes while keeping the same target denominator;
current overall and frozen goal progress must remain separately labelled.

Check the expanded menu at narrow width and enlarged text. Open contextual Shopping,
inspect its scope and return without a provider request or automatic quantity change.
Existing copy photos, archived examples or prices may be unavailable; report that limit
rather than supplying simulated customer data. Inventory writes require an owner-selected
real change. A later Shopping/onboarding review also checks the newly delivered tasks
against their completion checks.

The owner accepts the ordinary-use experience or identifies a specific rejected journey,
including perceived responsiveness. Engineering checks and sign-in assistance do not
supply that verdict. Acceptance of local use does not establish provider entitlement,
complete pricing, recognition accuracy or public release readiness.
