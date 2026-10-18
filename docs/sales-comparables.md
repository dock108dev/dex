# Sold-price comparables

The owner selected completed eBay sales as an additional comparison/guidance
source on October 17, 2026. This is separate from cached catalog reference
snapshots and active-listing acquisition. No sold-data request or sales-comparison
integration has been executed by this preparation.

## Current capability

Dex's proven eBay integration uses application authentication and Browse search
and item details. Those operations establish active-listing access, not sold-history
entitlement. Existing credentials are not evidence of every eBay product's access.

The official [Buy API filter reference](https://developer.ebay.com/api-docs/buy/ref-buy-browse-filters.html)
states that Marketplace Insights is restricted and not open to new users. The
owner may have existing entitlement; that remains unknown. Verify existing account
capability evidence before choosing an automated route. Do not use a speculative
production call as an entitlement test.

[Product Research](https://www.ebay.com/help/selling/selling-tools/terapeak?id=4853)
provides sales research, including accepted Best Offer amounts, through eBay's
seller tools. Browser availability does not establish automatic API access or a
supported bulk-export interface. Do not silently substitute UI scraping. The old
Finding API is decommissioned; see [eBay's deprecation table](https://developer.ebay.com/develop/get-started/api-deprecation-status).

This capability check does not block public cached reference snapshots, require
new credentials, enable Hunter or select fresh eBay capacity.

## Record and identity requirements

Use a distinct sales-observation source path. Preserve a stable source sale/event
identifier, sale date, currency, quantity and price basis, capture date, source
provenance and mapping confidence. Distinguish advertised asking price, reported
sold price, exact accepted offer and unavailable accepted-offer amount. A listing
ending or disappearing is not evidence of a completed sale or settlement.

Map game, card/set/number, language and supported edition/finish/variant evidence.
Raw-condition cohorts and literal grading-company/grade cohorts remain separate:
PSA 10, BGS 10, BGS Black Label and CGC 10 are not interchangeable. Unknown
printing/condition/grading evidence stays unknown. A seller claim is not physical
or certification verification. Keep unsupported other-card identities visible;
do not force them into a Pokémon identity.

Exclude vague lots, sealed products and selectable listings from single-card
comparables unless their exact scope is established. Do not divide a lot price
into invented per-card prices. Preserve whether shipping is included, excluded
or unknown; never manufacture taxes, buyer fees, returns or settlement status.

## Guidance and cache behavior

Show recent matched-sale count, observed date range, median/range where meaningful,
cohort identity and cost basis. Label sample coverage and uncertainty. Sparse,
ambiguous or heterogeneous cohorts do not establish a precise market price.
Keep asking-price references, condition-mixed provider market references and
completed-sale comparables visibly distinct. None is guaranteed resale EV or a
maximum bid.

Prefer permitted bounded batch capture into source-governed snapshots, with local
comparison afterward. Define API/source rights, request/body/time/retention limits,
consumed attempts, duplicate handling, expiry and withdrawal before acquisition.
No hidden per-card requests, refresh on reveal/Back, retry, fallback or automatic
bidding is implied. Preserve source/capture/valuation times separately.

## Next implementation boundary

First establish the owner's actual sold-data capability from existing account
evidence. If a supported route is available, implement and qualify a finite cached
sales adapter plus exact identity/cohort projection. If entitlement is unavailable
or unknown, retain that specific limitation and a Product Research owner route;
do not call active Browse results sold comparables. A wider card universe requires
its own canonical identity coverage, not just more sale rows.
