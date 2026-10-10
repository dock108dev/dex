# Interface design

Dex uses system typography, light surfaces and a red, white and black palette.
Red identifies primary actions and selection; neutral surfaces group records and
comparison facts. Shared primitives live in `beta/static/glass.css`; application
styles live in `collection.css` and `public.css`. Templates and styles are
repository-owned and require no external design workspace.

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

Pokédex puts search and region controls before species results. Optional set, era
and card-type filters stay in a disclosure. Card details distinguish set, number,
finish, variant, edition and rarity; unresolved fields remain visible.

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
