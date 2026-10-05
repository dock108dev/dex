# E3a — retained-data Packs to open

**E3a is qualified for local synthetic engineering.** The authenticated ordinary
`/packs/?goal=ID` whole-goal/species view, local filters and retained-version navigation
passed the browser walkthrough and synchronized-runtime checks. See
[qualification](history/2026-10-04-E3A-QUALIFICATION.md). Full E3/beta and owner
acceptance remain open. [Original validation](history/2026-10-04-E3A-VALIDATION.md)
retains earlier restricted-runtime failures.

Enter from **Packs to open** on an Original 151 goal card, or its missing-species
progress checklist. The selected goal ID stays in every filter, species, reset and
eBay link. Retained-version links explicitly select another version in the same
account-local lineage. Unsupported goal types show a limitation; inaccessible
versions return 404. There is no default successor selection or inventory action.

`beta/packs.py` obtains the goal through the existing account boundary, computes
missing species from active resolved account copies and its frozen printing IDs,
and resolves metadata through the goal's retained review import/hash/version.
Stable `sealed_bridges.catalog_id → printing_id` links preserve collector number,
language, finish, variant, canonical species and Pokémon category. Later catalogs
cannot add printings to an older goal. Missing/archived sealed records or unavailable
review journals exclude joins and are reported as gaps. Archived collection metadata
can retain exact frozen reviewed booster meaning; current selectable status is
shown separately. Descriptive corrections show the frozen name/rarity alongside
current reviewed descriptions, without changing identity or goal membership.

Expansion coverage is the set union of missing canonical species with confirmed
reviewed booster membership. Unknown/non-booster relationships are detailed separately;
Trainer/Energy and guaranteed cards never add to this union. Matching printings show
rarity without translating rarity into pull probabilities. The primary counts are
possible missing-species coverage, not expected pulls or guaranteed completion.

Products preserve exact identity/version/market/language and pack relationships.
Unverified associations have unknown product coverage and quantities, even if the
expansion matches every target. The retained UPC 820650853210 / Target TCIN 88897904
Bundle remains officially unverified. Its retailer six-pack description cannot
establish an official count. Guaranteed records are separate, and zero records with
unknown inclusion review cannot prove no guaranteed cards. Verified mixed products
show quantities and total cost; no cost allocation to one expansion is invented.
Price per relevant pack appears only for verified, exclusively relevant pack contents.

All retained offer observations show retailer, actual seller/direct-or-marketplace
status, stock, price/currency, shipping, original checked time and timestamp notes.
Freshness is the existing inclusive 24-hour rule (future timestamps are not fresh).
Even within that window this view does not assert current availability. Source links
are for manual review, with no Buy now claim. Filtering/reopening changes no dates.
No acquisitions, provider calls, recurring jobs or saved pack research were added.

## Actual retained coverage

The disposable synthetic predecessor freezes 477 vintage printings: 151 missing
species, no reviewed sealed bridge match. Its successor freezes 823 printings:
477 vintage plus 346 qualifying Pokémon variants from English 151. It yields one
compatible expansion, **151 distinct possible missing species**, **185 confirmed
Pokémon booster printings** and **161 unresolved Pokémon variant memberships**.
The package's full counts remain 207 confirmed membership rows and 177 unresolved
variant rows, including Trainer/Energy records excluded from species goals.
Scyther yields one species, one confirmed standard printing and one unresolved
reverse variant. Exact calculations and versions are in
`evidence/e3a-20261004/browser/version-{1,2}.json`; these counts concern synthetic
account ownership, not the owner's missing-18 seed or complete all-era coverage.

The 151 collection review version remains `2026-10-04-151-v2`, package file SHA-256
`250d0c61aea496d0854c831f62edb1030e1cd3acf91db59d239185528401a45f`;
normalized review hash
`12ed07eb96fe8b3db79e33521028c12f19188ccb31eb0b17b97014644129ec34`.
Original source packages, observations, gaps and earlier evidence remain untouched.

## Reproduce setup and the qualified browser walkthrough

Use fresh output paths; never substitute the owner's installation:

```sh
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output NEW_SEED
uv run --no-sync python scripts/rehearse_e3a.py --seed NEW_SEED --root NEW_COPY --output NEW_EVIDENCE
uv run --no-sync python scripts/check_e3a_routes.py --root NEW_COPY --output NEW_EVIDENCE
uv run --no-sync python scripts/serve_e3a.py --root NEW_COPY --output NEW_EVIDENCE
```

`serve_e3a.py` requires SYNTHETIC_ONLY and checks supported port 8011 by binding before
starting. It refuses an occupied port and prohibits/counts eBay and HTTP-client calls.
Run in an ordinary environment permitted to listen on loopback; the previously restricted sandbox
bind was denied. Do not terminate an owner server, change security policy or substitute
another port. Use generated admin credentials from the root's private credentials
file, never put them in captures or prompts. Stop only the server you started.

At `/goals/`, select version 2's Packs to open link. Inspect whole-goal 151 coverage,
open Scyther, expand confirmed printing and uncertainty details, inspect the Bundle's
unknown quantities and both dated Target observations. Verify seller/shipping unknown,
USD 27.99 out-of-stock and approximate-time limitation. Apply species/expansion filters
and reset. Open version 1 using the explicit version link and inspect its empty
membership gap without successor substitution; return to version 2. Enter from the
Scyther missing-species checklist too. Use unsupported legacy-goal and absent-expansion
routes to inspect gap states. Stale offer behavior and verified/mixed/guaranteed edge
cases are fixture-tested; do not rewrite retained observations to produce screenshots.

Retain screenshots, actual displayed-state assertions and browser errors; then run:

```sh
uv run --no-sync python scripts/rehearse_e3a.py --root NEW_COPY --output NEW_EVIDENCE --verify
```

Snapshot verification compares protected copies, goals, hunts, scan jobs/reservations,
photo rows/bytes, binders and original observations. Login/session bookkeeping is
separate. Framework HTML checks are not browser or owner acceptance. Earlier
browser rejection and listener denial remain retained. The subsequent qualification
record contains actual screenshots and displayed-state assertions.

## Next separate data slice

Execute **D3/D4a: exact 151 Bundle official contents and seller-specific dated offers**
separately from E3a qualification. Exact target is
`upc:820650853210:us:en:2023`, UPC 820650853210, version
`2023-US-English-single-bundle`, English/US, expansion `tcgdex:en:sv03.5`.
Retailer target is Target TCIN 88897904 / DPCI 087-12-7190 (retained
identity in D1_E1.md). Never merge different SKUs,
assortments, languages or versions on a similar product name.

Finite budget: at most **two official product-page reads and five retailer product-page
reads, seven total attempts, no retries**. Official targets are the retained Pokémon
product-gallery Bundle page and official English 151 expansion/product page. Retailer
targets are exact-ID Target plus one matching-product page each at Pokémon Center US,
Walmart, Best Buy and GameStop; a missing exact match is a recorded gap, not permission
for wider search/acquisition. Stop that source on denial, CAPTCHA, unusable output,
identity mismatch or exhausted budget. Do not bypass access controls or buy/cart/bid.

Retain raw permitted evidence, URL, actual attempt/check time and time quality,
source hash, language/market, authority, request outcome, identity match and claims
supported. Official quantities/inclusions need exact official usable evidence;
retailer descriptions remain claims. Offers need actual seller, direct/marketplace
status, price/currency, stock, shipping and unknown labels; never infer seller from
retailer branding. Unavailable stock is valid dated evidence. Preserve old observations;
new observations get new identities/timestamps and explicit review/publication.
Use the existing import validation and copied-state rehearsal. Stop before publication
if evidence cannot support the claimed exact relationship; retain unresolved gaps.
This handoff authorizes no refresh adapter or credential/provider activation.

The 177 variant-membership gaps, independent Scyther end-to-end review, all-era
acquisition, populated Production eBay, owner reconciliation/acceptance, E4/E5,
full E3 and beta stay open.
