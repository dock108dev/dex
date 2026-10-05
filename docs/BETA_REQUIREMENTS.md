# Pokédex beta requirements

Updated October 4, 2026. Required product scope; data collection and engineering
are both outstanding. The [roadmap](ROADMAP.md) owns priorities; this document owns
the beta acceptance contract. Existing implementation and evidence are described
in [PM status](PM_STATUS.md). This does not qualify hosting or invited-user access.

## Goal and scope

Collect the original 151 using qualifying Pokémon cards from any era. Expand the
underlying catalog to the full Pokémon TCG universe across eras and species,
rather than making the owner's 151 checklist the catalog limit. Vintage presets,
classic eBay hunts and exact-printing collecting remain supported.

The first beta shopping market is US English, a planning default. Keep language
and market in every relevant identity so other catalogs can be added without
merging different release lists. Record the complete intended catalog universe
in a versioned manifest, including known missing eras, languages and sets. A
partial import cannot be described as a complete worldwide catalog. Beta requires
all-era English catalog coverage reconciled against the chosen dated set registry;
other-language coverage remains explicitly tracked expansion work.

Full species metadata must no longer stop at #251. Use a sourced, versioned
canonical registry. The broad Original 151 goal counts one owned qualifying
printing per canonical species; ex, V, GX, Dark, named/trainer-owned and regional
forms can count when their canonical identity establishes that species. Trainers,
Energy, artwork cameos and unresolved mappings do not count. Evolved species do
not fill pre-evolution slots. Preserve the narrower policy of existing vintage
goals. Users can choose printing-specific or narrower goals separately.

Create a versioned all-era goal; do not silently rewrite a frozen checklist.
Catalog growth must offer an explicit goal update with a membership/progress
preview, retaining earlier versions. Duplicates do not increase species progress.
No search result or product purchase is an ownership confirmation.

## Required data collection

| ID | Deliverable | Completion evidence |
|---|---|---|
| D1 | Species, set and printing catalog spanning all eras; versioned universe/coverage manifest | Dated registry, source URLs, retrieval times, source hashes, stable provider-to-internal ID mapping, counts and unresolved gaps; English set coverage reconciled |
| D2 | Species-to-booster-expansion membership | Exact printing, language, canonical species, rarity and eligibility; official checklists/card pages corroborate the missing-18 mappings; distinguish booster pulls from promo/deck-only cards |
| D3 | Official sealed-product catalog | Exact SKU/version/market, official product URL, product type, expansion-specific pack counts and separately included guaranteed cards; mixed assortments documented or marked uncertain |
| D4 | Retailer offers and availability observations | Seller identity, retailer-direct versus marketplace, offer URL, market/currency, price, known shipping, stock status, checked time and retained observation evidence |
| D5 | Missing-18 coverage report | Every missing species traced through printing → booster set → sealed product → offer, or a specific documented absence/unknown; Scyther fully traced and independently reviewed |

Use official Pokémon card lists and product descriptions for membership/contents;
use a documented structured catalog provider for bulk metadata after reviewing
source usage terms and coverage. Do not assume metadata access grants artwork or
price redistribution rights. Record source applicability and conflicts rather
than selecting the most convenient value. Preserve prior source observations.

Retailer discovery begins with Pokémon Center US and direct-sold listings from
Target, Walmart, Best Buy and GameStop. These are research targets, not verified
stock or promised integrations. For each, record the available permitted access
method, coverage and failures; build supported adapters or reviewed manual
imports. Classic eBay listings remain a separate required provider path. A
marketplace page on a retailer site is not a retailer-direct offer.

The original-app ledger currently has these 18 missing species: Venusaur,
Pidgeotto, Pidgeot, Clefable, Alakazam, Gengar, Hypno, Chansey, Kangaskhan,
Mr. Mime, Scyther, Gyarados, Lapras, Vaporeon, Jolteon, Flareon, Articuno and
Moltres. This is a research seed from `config/pokedex_251.json`, not a write into
authenticated inventory. Recompute the live account checklist from its copies
and selected goal; reconcile any difference explicitly before an owner walkthrough.

An official released product is not necessarily in stock or still manufactured.
Keep in-stock, out-of-stock, preorder, unknown and stale observations distinct.
“Buy now” requires a current purchasable offer; preorder must be labeled separately.
Define and show an offer freshness policy before live qualification (initial
maximum age: 24 hours). Reopening does not reset checked time. Missing prices,
shipping, counts and contents remain unknown; no fabricated zeros.

Data completion requires real sourced records. Fixtures can test engineering but
cannot close D1–D5. A documented unavailable product can explain a species gap;
an unresearched gap cannot count as completed data collection.

## Required engineering

| ID | Deliverable | Dependencies |
|---|---|---|
| E1 | Versioned schema, import validation, source/coverage reporting and review/publication for species, printings, expansions, products and offers | D1 schema and representative D2–D4 records |
| E2 | Full species registry and all-era goal builder; explicit goal updates; broadened eligibility with canonical mapping | E1 and D1–D2 |
| E3 | Missing-species “Packs to open” view and expansion/product coverage comparison | E2 and D2–D3 |
| E4 | Retailer offer ingestion/refresh, filters, purchase links, dated stock and price comparisons | E1 and D4 access assessment |
| E5 | Saved/reopened pack research and preserved classic eBay flow | E3–E4; eBay live qualification additionally needs provider access |
| E6 | Integrated beta evidence and owner walkthrough | D1–D5, E1–E5 and existing eBay populated-live gate |

Model species → printing → booster expansion → sealed product → retailer offer
as separate relationships. Use stable IDs, source versions and account-scoped
saved goal/research references. Public product metadata must not expose private
copies, photos, saved searches or credentials. Add schema migrations through
existing services; rehearse on copied state and retain rollback evidence.

“Packs to open” must support entry from a missing species and from the whole goal.
Show all indexed compatible expansions and products, their cheapest qualifying
rarity where known, distinct missing-species coverage, documented pack contents,
price, seller, stock and checked time. Coverage is the union of possible missing
species, deduplicated across printings and packs; included guaranteed cards have
their own count. Do not turn either count into an expected pull count.

Compare price per pack of the relevant expansion using documented quantities.
For mixed products, show total product cost and known pack breakdown without
inventing an allocation of cost to individual expansions. Shipping/tax uncertainty
must stay visible. No invented pull probabilities, completion costs, best-value
claims or sealed-content valuation from rarity or average singles prices.

Refresh must be explicit and bounded in the first beta, retain observations,
report errors per source, and keep old results with their actual age. Saving,
reopening and local filtering must make no provider calls. Saved research retains
the selected goal version and source observations; any comparison against current
ownership is labeled and does not overwrite the saved context. Do not introduce
background monitors or recurring jobs as part of this requirement.

Keep eBay search/compare/reveal/seller-review/save/reopen usable, including vintage
preferences and uncertainty. Pack discovery should show the target Pokémon and
possible set contents openly; existing eBay mystery-result reveal remains explicit.
All buying, bidding and inventory confirmation remain user actions.

## Beta acceptance gates

1. D1–D5 artifacts exist, are validated and reviewed. Reconcile English set coverage
   across eras and full species metadata; report every remaining coverage limitation.
2. E1–E2 pass copied-state migration/rollback, import idempotency/conflict checks,
   species mapping and meaningful vintage-goal/ownership regression checks.
3. E3–E5 pass functional checks for missing-species unions, promo separation,
   mixed contents, stale/unknown offers, partial provider failure, account privacy,
   versioned goals and saved reopening without network access.
4. Real source evidence demonstrates Scyther and the complete missing-18 report.
   At least one compatible sealed product has a genuinely current purchasable
   offer and works through the beta UI. Do not require stock to exist for every
   species: researched absence is valid, but must be visible. Fixtures do not
   substitute for live purchase availability.
5. Populated Production eBay evidence establishes the retained classic flow.
   The October 3 access blocker remains unresolved until rechecked; data and
   engineering work above continue independently.
6. Mike completes the walkthrough: choose the broad 151 goal, inspect missing
   targets, compare packs and classic listings, save, reopen and confirm the
   meaning of coverage and availability. Record owner feedback separately from
   automated and live-source evidence.

All gates are required for this beta scope. Record exact revision, dataset hashes,
goal version, market, observation times and evidence class at closeout. A finished
UI with sample data or a collected spreadsheet without app integration is partial
delivery. Keep hosting, LAN/phone access, managed startup, invited users and release
qualification separate; broader product eligibility does not imply deployment.

## Required closeout

Deliver the versioned catalog/coverage manifest, normalized data packages with
source evidence, missing-18 report, access/refresh limits, migration evidence,
focused test results and UI captures, live observations and owner feedback.
Update this document's work status through [PM status](PM_STATUS.md), the
[roadmap](ROADMAP.md) and the Desktop `dex_next_steps.md` handoff after every slice.
Stop a source attempt on access denial, unusable evidence or its finite budget;
retain the gap and continue independent work. Never change provider credentials,
private ownership, spending reservations or source rights to force a gate closed.
