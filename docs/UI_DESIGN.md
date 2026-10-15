# Interface design

Dex uses system typography, light surfaces and a red, white and black palette.
Red identifies primary actions and selection; neutral surfaces group records and
comparison facts. Shared primitives live in `beta/static/glass.css`; application
styles live in `collection.css` and `public.css`. Templates and styles are
repository-owned and require no external design workspace.

## Local-use completion requirements

The agreed collection goal is a useful, owner-accepted local app: owned cards,
catalog browsing and Pokémon pages have distinct meanings, predictable normal-page
navigation and readable optional detail. All-era Original 151 collecting, Kanto/
Johto views, classic eBay and Packs-to-open remain supported within indexed coverage.
The separate Cards I own gallery is retired; My Cards is the owned-card destination.

Completion requires coherent current ownership across My Cards, species and
current missing views; unknown totals stay unknown and saved goals keep their
frozen policies. Card variants group without merging stored printing IDs. Pokémon
artwork, card references and private copy photos retain their separate roles;
missing artwork cannot change status or destination. Existing collection data,
credentials, source history, prices/retention and saved research survive updates.

My Cards → card takes one click; Pokédex → species takes one, then → card takes a
second. Advanced attributes are disclosed on demand and copy editing is at most
two steps from its card. Back restores tab, filters, scope, page and scroll.
Guest routes expose no private collection/source/photo data. Keyboard operation,
320px layouts, enlarged text, error/empty/loading states and image failures must
remain usable on the delivered app. The owner confirms the final ordinary-use
experience; automated checks do not supply that acceptance.

Complete four-grade prices, new automatic acquisition, broader catalog publication,
shared hosting, installer/notarization and public release are outside this local
collection goal. Retained ideas and pricing gaps are in the [Shopping backlog](hunts.md#backlog).

## Access and navigation

| Capability | Signed out | Signed in |
| --- | --- | --- |
| Browse species #001–251 and indexed printing details | Available, including catalog gaps | Available with private collection progress |
| General Pack lookup and dated seller observations | Available | Available |
| Owned/missing filters and collecting goals | Requires sign-in | Account scoped |
| Copies, photo entry, import/export and undo | Requires sign-in | Account scoped |
| Save, reopen, rename and remove Pack research | Requires sign-in | Account scoped |
| eBay searches, saved finds and reveal | Explanation only | Account scoped, subject to provider configuration |
| Catalog publication and review | Requires sign-in | Role and capability checks apply |

Guest projections never select an account, infer zero ownership or expose private
provenance. Sign-in honors safe return destinations; sign-out returns to public
browsing. Physical-copy management has its own `/collection/` route.

## Screen hierarchy

My Cards shows owned card groups with Card reference images or stable placeholders; Card Library is an explicit
catalog tab with variants grouped beneath each card. Pokédex uses Pokémon artwork,
species identity and Collected/Not collected. Species clicks always open species
pages with Your Cards first; card clicks always open normal single-card pages.
Private copy photos and individual attributes belong beneath the card.

Search and core filters come first. Batch selection appears after Select;
condition, edition, grade, purchases, prices, provenance and source history are
available through labelled disclosures or settings. Keep quantity unknown where
unestablished without describing an owned card as zero/missing. Browsing cards
or species opens no dialog; focused editing/confirmation may use dialogs. Back
preserves the list's filters, scope, page and scroll.

The collection app uses `/cards/` for owned groups and `/card-library/` for the separate
catalog. Both work without parity. The shared header owns this adjacent pair;
lists do not repeat the same navigation below it. One compact tile links directly to its canonical
`/card-groups/<id>/` page without selecting a child. Search/Set lead; sort and variant
filters are disclosed. Complete options include owned archived sets and are not
derived from a result page. Nullable card totals appear once; copy counts belong
beneath Your Copies. Unresolved-only evidence is distinct from empty/no matches.

Long selected card-filter values retain a complete wrapped caption associated
with the native control. Captions update when a selection changes and default
filter captions stay hidden. Duplicate-policy controls likewise show their full
selected meaning beneath the control, including in the physical-copy dialog.
Enlarged text must keep the complete choice readable; captions do not change
submitted values, filtering, ownership or mutation policy.

The card page has one Card reference, identity, ownership, quantity and useful
Add/Edit action. Variants, Your Copies, Details, Prices and sources, and History
start closed. Exact edition/finish images remain unavailable. Copies expose Edit,
Edition and Remove this copy; Edit is two steps from the card. Basic dialog fields
come first; copy reference, purchases and grading/certificate are optional. Closed
fields retain their stored values. Broad Add requires no copy/variant/quantity;
owned editing requires an explicit choice before clearing a total or removing a
card. Optional guide details reuse existing per-copy evidence and never multiply
the card total.

Local card list URLs carry filters/page; a separate validated `return` carries the
list destination and bounded scroll. Each account's My Cards and Card Library
header destinations retain their own state through ordinary Back/refresh. UI context never enters API filters or
canonical identity. Route/account/generation guards reject obsolete responses;
missing authority is an explicit reload state. Review cancellation never confirms,
uncertain responses recover saved operation status and focus returns to a current
card/list control after refreshed dialogs close. Narrow navigation wraps enlarged
account text without covering the brand. Finite home memory and cross-app context use the same guarded destinations.

Pack lookup puts selection and target coverage before products and offers.
`packs.html` owns scope and saved research; `pack_filters.html`,
`pack_product.html` and `pack_offer.html` render their respective sections.
Possible pulls and guaranteed included cards are separate. Price, shipping,
observed stock and original check time align for comparison; full reasons and
history remain available in disclosures. Unknown costs or old observations cannot
be presented as current purchasing evidence.

Shopping uses a compact search area beside the current lot and four independent
grade comparisons. On narrow screens, search controls precede the lot; matching
cards follow it so a long catalog cannot bury the comparison controls. Search
moves to matching cards when submitted on narrow screens. Grade values use two
columns rather than sideways scrolling. The shared red accent identifies the
main comparison action; add, clear and history controls use neutral treatment.

Only evaluated totals are shown. Changes to lot quantities, prices, dates or costs
hide stale results and prompt a fresh comparison; searching or changing wants
leaves the calculation visible. Routine feedback clears after five seconds;
errors retain entries and focus an actionable message. Adding retains search
focus, and comparison/clear actions restore their control's focus. Guide dates,
missing prices, partial coverage and unknown costs remain distinct. Full
provenance, locks help, saving and older comparison tools remain available.

Primary actions remain distinct from references and optional detail. Long names,
exact IDs and unavailable results must fit both wide and narrow layouts. Use
clear empty states, fixed safe error messages and a visible retry path.

## Accessibility and change checks

Keep controls at least 44px high, labels programmatically associated, keyboard
focus visible, skip links usable and disclosure/dialog handback predictable.
Respect reduced motion and transparency, and provide opaque fallbacks. Layouts
must accommodate narrow screens and enlarged text without horizontal overflow.

For interface changes, check public/private access, keyboard operation, long
content, empty/error states, saved reopening and text scaling on synthetic data.
The [CI browser harness](CI.md) exercises automated Chromium flows. It does not
replace screen-reader, native-device or human usability testing, and cannot verify
recognition accuracy or current seller availability.

## Pokémon pages

Pokédex lists all 251 canonical Pokémon by default, with species artwork or stable
neutral space, dex number, canonical name and private current Collected status.
Search, Region and explicit current/saved scope lead; collection progress and
matched results have separate labels. Printing/source counters and row Pack
actions are absent. Card filters, saved policy and tools remain labelled
disclosures. Select reveals checkboxes and batch actions; hidden search selections
are counted, and changing region/goal clears them. Selection never edits ownership.

`/pokedex/<dex>/` opens one normal species page in one click; its owned compact
card opens in a second click. Your Cards follows canonical identity/current status
immediately and shows each current owned group once. Explore species cards is a
secondary Card Library link. Empty/unindexed/uncollected species remain useful;
species-only evidence has Card details needed without a fabricated card. Species
quantity is unknown. Saved source/copy-qualified/printing policy and units remain
explicit, with current possession independent of frozen past progress.

Canonical/legacy routes, refresh and Back retain validated list context and focus.
Guest species pages show no private status or quantity and invite sign-in for
Your Cards; published metadata is optional exploration. Artwork failure and staging
exclusions preserve identity. Browsing never opens a dialog. Focused card editing,
source import and goal actions retain their existing reviewed dialogs and cancellation.


## Collection navigation and Shopping

Signed-in B2 starts at My Cards; its adjacent Card Library stays separate. The
header presents My Cards, Card Library, Pokédex, Shopping and Add Card. Settings
and tools retain physical copies, Goals, Pack lookup, Packs to open, saved research,
source/import/history and supported role-specific reviews. Add Card opens the
catalog; it creates no preview, copy, photo or recognition request. Add to
collection remains distinct from Add to lot.

Brand home reopens only a successfully rendered, finite, reauthorized collection
destination. Optional per-tab memory binds origin, installation, account and auth
session. Explicit links and safe sign-in returns take precedence. Invalid storage
falls back to My Cards. One header section is active: a species-origin card stays
within Pokédex; My Cards/Library-origin detail stays within cards. Ordinary Back
retains completed filters, scope, child, selection, page, scroll and focus. Cached
private pages reload for fresh authorization; logout invalidates the same auth
session across open tabs.

Find links on species, card and goal pages open a labelled Shopping scope. Current
presence and frozen saved-goal policy/units remain distinct. Groups without an
explicit child require a printing choice before a reference appears. Archived or
unsupported targets remain unavailable. Entry/return never populates quantities,
changes collection/goals, searches a provider, compares or saves automatically.

Picker labels track the latest checked active scope. The opened-from context and
Back link remain separately labelled; loading removes old Add/Lock choices before
a newer catalog response can appear.

Lot drafts retain user-authored inputs only, independently of local guide values
and computed results. Reentry revalidates printing IDs and local references; a
restored lot requires explicit Compare. Missing/withdrawn/expired references are
removed without losing input quantities/costs. Draft wanted choices that differ
from current session targets are disclosed and require explicit confirmation.
Source-status polling and expiry protections remain active. Restricted price/source
records and comparison derivatives never enter browser draft storage.

## Presentation conventions

My Cards pairs its heading with the result count and keeps one shared navigation
row. The neutral page background, white header, consistent radii and restrained
red action/selection treatment carry through Shopping. Library alone is selected
on its own page; remembered filters and scroll remain account scoped.

Pokémon detail keeps its Find action beside identity/status and brings Your Cards
closer. Narrow artwork captions use the available line width without enlarging
the image. Unknown artwork and quantities remain explicit.

Shopping aligns with collection page margins. Picker selection is quieter than
Compare; the selected printing's full name/set/number wraps beneath its native
control. On narrow screens, search comes first, then the working lot, then the
printing picker. Unpriced results show one unavailable value and priced-unit
coverage; costs/bid detail remains available. A successful comparison clears the
restored-draft notice while retaining user inputs and wanted-target distinctions.


## Known installed interface limitations

The October 14 genuine walkthrough found card thumbnails overlapping the expanded
Settings & tools menu at 320px with doubled text. No later installed observation
closes that discrepancy. Later source presentation checks cover compact headers,
long labels and narrow layouts but do not establish that this installed menu issue
is repaired. Frozen-goal and current-progress labels are distinct; whether their
repeated headings are clear remains an owner-feedback question, not an established
new product requirement.

The installed speed repair's recorded data-ready samples were 1,139ms for filtered
My Cards and 552ms for Pokédex, after replacing the 6,150,820-byte full bootstrap
with a 22,027-byte context. These are individual local samples, not latency
promises. The owner called the earlier app painfully slow; no post-repair
acceptance is recorded. See [recorded delivery](operations.md#recorded-local-delivery)
and [verification boundaries](CI.md#recorded-verification).

## Owner review of the delivered app

Use the actual existing installation at its ordinary URL and sign in normally.
Review My Cards, Card Library, Pokédex → species → Your Cards, a card and its
optional copy details. Check that unknown quantities and missing images remain
honest; test Back, filters and scroll with ordinary collection state. Open and
close editing without confirming an inventory change unless a genuine card and
change have been selected by the owner.

Check Settings & tools at narrow width and enlarged text after its repair. Enter
Shopping from a species/card, inspect its scope and return without automatic
quantities, provider requests or collection changes. Use actual available data;
missing private photos, archived examples or prices remain explicit gaps rather
than simulated customer cases.

The owner records whether recognition, ownership clarity, click paths, optional
detail, navigation and perceived responsiveness are acceptable on the delivered
version. Record a specific rejected journey if further repair is needed. Acceptance
of this local collection experience does not imply full price coverage, real-card
recognition accuracy, provider entitlement or public release readiness.
