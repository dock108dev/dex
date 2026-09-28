# Vintage 251

This document describes the **current local implementation**. The [collection-beta roadmap](../dex_next_steps.md) replaces the earlier watcher-first next steps; [BETA_DESIGN](docs/BETA_DESIGN.md) specifies planned accounts, per-copy inventory, scan confirmation and catalog expansion. Those beta features are not implemented. The first planned owner account is `admin`, with the existing collection preserved. Vintage 251 becomes a goal within the future shared collection app.

A local, spoiler-controlled collection journal and discovery app for English vintage Pokémon cards. Card ownership is the authority. The goal is to complete species #001–251 while retaining the experience of discovery, with exact printing completion tracked separately.

## Authoritative collection

`config/pokedex_251.json` contains 251 species and 859 card records from ten complete set catalogs. `cards` stores owned/not owned, first edition, and exact printing identity. `pokedex` contains derived ownership and references to eligible card IDs; no duplicated card objects. The server recomputes the projection on read and write. The original species checklist remains in `config/pokedex.json` only as historical import evidence and a legacy fallback when the new file is absent.

The user's complete September 27 ownership list replaces the truncated attachment: 207 distinct printings, 133 Kanto and 20 Johto species (153/251). `sources/confirmed-ownership.json` preserves the input numbers. Each printing is tracked once; duplicate copies are not recorded. All 207 set/number identities resolve against the catalog. Sabrina's Abra is not imported.

Eligible sets: Base Set, Jungle, Fossil, Base Set 2, Team Rocket, Wizards Black Star Promos, Neo Genesis, Neo Discovery, Neo Revelation, Neo Destiny. All Wizards Black Star Promos are included as requested, rather than applying a calendar cutoff to that set. Both additional Neo sets were added at the user’s request.

Normal Pokémon fill a species slot once. Normal Team Rocket cards count. Dark Pokémon, trainer-owned/named Pokémon, Trainer and Energy cards do not. Unown letter forms count as Unown. Ineligible cards may still be tracked for exact collection purposes.

All 251 species have eligible printings in the expanded catalog. Neo Revelation covers the previous 11 gaps; Neo Destiny supplies additional printing options. Adding sets preserves all recorded ownership. Light and Shining variants remain outside the existing normal-name eligibility rule, alongside Dark and trainer-owned cards; they are still available for exact-card tracking.

Catalog evidence is a local, pinned historical snapshot of PokemonTCG/pokemon-tcg-data. Each source URL and commit are in `config/catalog/sources.json`; no runtime dependency on the deprecated Pokémon TCG API and no pricing claims from this snapshot.

## Implemented user flows

- Overview: separate Kanto, Johto, and total progress; exact-printing count; scope limitation.
- Pokédex: name/number search, owned/missing/unavailable and region filters. Species details show every eligible printing, including Neo alternatives for Kanto species.
- My cards: ten set summaries and ownership and first-edition checkboxes across all card types. Species completion updates automatically. Export downloads the current authoritative JSON.
- Mystery hunt: known lots with hidden contents, true mystery/repacks, and missing singles; region/rare/bulk focus and delivered budget.
- Missing cards: singles pool; queries derived from every eligible printing of currently missing species.
- eBay finds: persistent local search history; sample/live separation and explicit reveal. Reopening a saved search hides identities again and recomputes fit against the current collection.

The local interface uses FastAPI and a small browser frontend. React/Next.js was a suggested stack in the supplied brief; this implementation keeps the existing Python project and avoids a second development server. SQLite persists search snapshots; atomic JSON writes persist ownership.

## Spoiler boundary

Before reveal, the hunt API omits seller title, URL, card identities, and internal score components. UI does not render listing images. Reveal is a separate request. Only the revealed view exposes a validated HTTPS eBay link, with a reminder that eBay itself reveals photos and names. Samples have no purchase link. Counts and candidate yields are intentionally visible.

## Discovery and evidence

Known lots, singles, and mystery products use separate query plans in `config/hunt.json`. The existing Browse API client handles authentication, search pagination, exact decimal prices, destination shipping, retries, and warnings. Live search is opt-in per hunt; no background purchases, bids, or notifications from the app.

A live request runs at most eight queries across both purchase types, using the existing page cap. The UI reports coverage and offers the next query batch. Results are snapshots, not a claim of current availability or exhaustive marketplace coverage. Auctions require a valid future end time. Unknown price/shipping and over-budget results do not qualify.

The current recognizer only matches explicit set + normal card name + card number in seller text; these are candidates, not photo-verified inventory. A title is not a complete card list. Random/mystery contents never receive specific species-hit claims. Unidentified composition, unknown rarity guarantees, mystery quality, and missing prices remain unknown.

## Scores and valuation

Lot weights are configurable: Dex yield 30%, exact printing yield 20%, raw value ratio 20%, set fit 15%, mystery quality 15%, with duplicate and ineligible-card penalties. Scores retain the missing weight rather than renormalizing partial evidence into an apparent perfect score. Evidence coverage is displayed. Scores are sorting heuristics, not probabilities or market-value appraisals.

`config/raw_values.json` is intentionally empty until sourced raw LP/NM records are supplied. Format: `{ "base_set-15": { "LP": { "value": "10.00", "source": "source reference", "as_of": "YYYY-MM-DD" } } }`. PSA grades may be stored as references but never enter raw value or bids. Whole-lot value requires complete identified inventory and a supported raw condition; unknowns do not become zeros.

Auction max bid uses the raw value of useful unowned printings, configured completion/mystery premiums, less shipping and configured condition risk, bounded by the delivered budget. Owned printings are discounted entirely. Tax is excluded and displayed as such. With no qualified price records the interface says “Not enough evidence.”

## Remaining local integrations and optional extensions

- Real eBay credentials and observed live-search verification.
- Listing photo recognition and a verified inventory workflow; generic lot titles cannot reveal every card.
- Sourced raw LP/NM pricing with freshness policies and condition evidence.
- Statistical mystery distribution/guarantee analysis. No fabricated expected yield.
- Dedicated singles ranking by rarity/condition/discount; current singles use the same evidence score as lots.
- Optional scheduled collection-app discovery. The older daily watcher remains separate, has broader historical set rules, reveals seller titles, and is not the spoiler-controlled app.

These limitations are functional boundaries of this first version, not completed integrations. They are not the beta work sequence: account isolation, owner-preserving migration, copies/goals, personal-card scanning and catalog onboarding follow the roadmap. Live eBay, listing-photo recognition, mystery analysis and scheduled discovery are optional and do not block the collection beta.

## UI design

Adopted Glass Starter 02 from `/Users/michaelfuscoletti/Desktop/ui-templates` on September 27, 2026. Local baseline: `web/vendor/glass.css`; app adaptations: `web/style.css`. Uses the dashboard result/facts and records layouts, system typography, 44px controls, visible keyboard focus and responsive navigation. The user's requested Poké Ball red/white/black palette overrides the starter's blue palette. Screens use direct functional headings with no motivational copy or decorative hero. Collection provenance is in a disclosure; search costs, uncertainty and sample/live distinctions remain visible.

Verification: 95 tests pass; JavaScript syntax check passes. Browser review covered the overview, all ten sets, set selection, desktop and narrow layout. Existing ownership was preserved. Prior UI source is retained in `docs/ui-before/`; current ownership/value overview screenshot is `docs/owned-values.png`.

Rarity counts are now shown on Overview for Pokémon cards and on My cards for the selected set and card type (Pokémon, Trainer, Energy, or all). Each row shows unique printings owned, catalog total, and missing printings. Counts include ineligible named variants in exact-card tracking. A rarity filter narrows the editable card list; the summary retains the selected set/type scope for comparison. Unknown rarity remains explicitly labeled.

## Collection estimates

Overview and owned-card rows show edition-matched ungraded and Grade 7/8/9/10 estimates from `config/market_values.json`, with dated source links and a 30-day freshness window. Direct guide snapshots are preferred. Grade 7–8 gaps use explicitly marked geometric interpolation between raw and Grade 9. Grade 10 uses the PSA 10 guide. These are hypothetical grade scenarios, not appraisals or claims of actual grades. Missing values stay unavailable, and totals report coverage. The independent raw LP/NM hunt rules remain unchanged.

September 27 price snapshot: 206/207 owned standard-edition printings priced; Machamp Base Set #8 requires edition selection. Ungraded subtotal $1,595.26. Grade 7 and 8 each include 191 explicitly marked interpolations. Desktop (1280px) and narrow (390px) layouts checked; no horizontal overflow and ownership label targets exceed 44px.
