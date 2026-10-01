# Product status

The [roadmap](ROADMAP.md) owns current scope and priorities. The personal beta is
for Mike on localhost, with the existing collection preserved.

Current build: authenticated eBay bargain search, delivered-price comparisons
against dated guides, and reusable collecting-goal filters. Bargain searches can
include owned cards; filling a goal is a separate search purpose. Identified card
comparisons, partial lot subtotals and catalog-average benchmarks retain their
different evidence limits. Auction comparisons use the current bid, before tax.

Goal filters cover available game, selected sets, card type, rarity and Pokémon
Pokédex range, with species or printing completion and direct missing searches.
The current Pokémon species catalog ends at #251; Original 151 is one preset
within the general goal builder.

The local production eBay search path is enabled but application credentials are
not configured. Real provider results and Mike's personal-use review remain open.
Local simulated-provider checks do not establish current listing availability,
provider access or actual bargain quality. Guide comparisons use retained evidence
and explicitly refreshed project snapshots, selecting the newest valid record
with a maximum age of 30 days. Search does not automatically refresh price guides.

Local validation passed: 322 regression tests, then all 32 pricing tests after the
final grade-parser guard. Desktop and 390px Chromium checks use intercepted
provider responses; they do not establish actual eBay delivery or device behavior.

Further photo integration and recognition evaluation are deferred until there
are other users or broader collection coverage. Existing photo code and data
remain preserved.

No hosting, invited-user or real-device readiness claim follows from local tests.
Historical delivery results remain tied to their original candidates in
[engineering history](history/README.md).
