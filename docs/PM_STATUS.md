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

As of October 3, 2026, the local production eBay search path has application
credentials configured: both required values are present in the checkout's
private, Git-ignored `.env`. Credential presence was checked without exposing
values. Live authentication and Browse API access have not yet been verified;
real provider results and Mike's personal-use review remain open.
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

## October 3 local verification boundary

Application candidate: `dbaafee7283c9fb81de664738084c69061b16254` on local
`main`; remote `main` matched this candidate before documentation reconciliation.
The running supported CLI server uses the existing private installation at
`/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local`.
Its parent folder had been moved to Trash while the server remained running;
restored the same folder to its original path without replacing or initializing
files. No restart, seeding, ownership change, purchase or bid was performed.

The ordinary Chrome and Safari sessions were signed out. The live pass stopped
at the existing login page before submitting a search: **zero live batches and
zero provider calls**. Production credential configuration is complete, but OAuth
and Browse access are still unverified. No provider failure or retry occurred.
The next action is Mike signing in at `http://127.0.0.1:8011/hunt/`, then continuing
one explicit narrow individual-card batch (for example, Pokémon Base Set Pikachu
58/102, delivered ceiling $25), retaining the eight-query/two-page caps.

Validation: supported private-root `check` passed; 49 isolated tests passed across
`test_beta_live_hunts.py`, `test_hunt_values.py` and `test_ebay.py` on Python 3.14.
Private before/after fingerprints confirmed all 40 database tables and 13 root
files unchanged during this pass; private checkout credentials were preserved.
No fixture-writing browser harness was run against Mike's data. No application
code defect was established or code repair made.

Real-result delivered-price/guide/printing/grade review, explicit reveal, seller
review, saved-hunt reopening, frozen-scope retention and no-call filter changes
remain unverified on live results. Isolated tests are engineering evidence only.
Mike's personal-use acceptance remains pending his feedback. Hosting, phone
access, managed startup, invited users and further recognition remain deferred.
