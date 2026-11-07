# Lot-buying walkthrough: observed feature backlog

Subsequent owner feedback rejected the dense options and decision-log workflow. The current default is the [ranked buying list](hunts.md#buying-options), with detailed controls collapsed and the decision journal removed from the ordinary flow. The entries below retain their historical evidence.

Observed in the actual installed customer app on 2026-11-07. Implemented on `release/lot-walkthrough-20261107`; customer-runtime verification
and the Moltres walkthrough are tracked separately below. Personal listing/collection evidence remains in the private
walkthrough log. These priorities express purchase-journey impact, not release gates.
See the [observed how-to](missing-kanto-lot-how-to.md).

| ID | Priority | Observed gap | External work / desired behavior |
| --- | --- | --- | --- |
| FB-01 | High | One fixed optional budget cannot express a baseline with evidence-based exceptions. | Track a $120 low/no-margin baseline outside the app while retaining higher-priced opportunities. Add baseline plus explicit exception criteria, cost/value basis and uncertainty; distinguish estimated collectible value from resale proceeds. An exception never authorizes spending. |
| FB-02 | Medium | Expired lot-search allowance sends the user to a singles-focused Hunter screen. | Configure a finite nonrecurring window there and return. Offer contextual lot allowance/expiry/consumption controls without resetting history or starting acquisition automatically. |
| FB-03 | Medium | A promising result outside the two automatic detail slots requires a hidden additional-details path. | Assess lot → collapsed detail panel → explicit load works. Add a clear “Assess this lot fully” action with bounded request cost and status. |
| FB-04 | High | A fully itemized mixed vintage lot leaves most physical cards unresolved. | Cross-check seller list, shared traits and quantities outside Dex. Explain precisely which traits remain unresolved and support evidence-backed batch confirmation without guessing. |
| FB-05 | Medium | Review budget is populated while the collection-intent heading still says budget not set. | Remember search budget versus review override manually. Show which policy is active, preserve it across navigation and surface explicit overrides. |
| FB-06 | Medium | Applying seller details automatically selected a card but labelled it a user correction. | Track provenance manually. Distinguish automatic proposal/selection, user confirmation and user correction. None authenticates the physical card. |
| FB-07 | Medium | Back to search labels a separately reviewed candidate unprocessed. | Remember reviewed candidates externally. Show a separate checked review status/link with original expiry; preserve truthful original Hunt acquisition accounting. |
| FB-08 | High | Selecting one printing for a mixed-species-family entry assigns the whole family quantity to that printing. | Correct the quantity before Compare. Support physical allocation among printings and unresolved remainder; never silently equate a family count with copies of one variant. |
| FB-09 | Medium | “Correct card” jumps to local search after quantity edits already applied. | Infer save behavior by observing totals. Rename the search action and explicitly announce quantity changes/autosave. |
| FB-10 | Medium | Explicit seller total/per-card condition are not fully reflected; subgroup claims appear as extra unresolved entries. | Read seller description, track total and literal condition outside app. Model total, subgroup, repetition and condition scope separately, with evidence-linked corrections. |
| FB-11 | Medium | Search/review decisions and flexible preferences have no visible consolidated shortlist. | Maintain an external journal of candidates, decisions, unknowns and workarounds. Provide a private decision journal respecting original source retention/expiry; do not turn temporary seller/value content into an unauthorized archive. |

## Acceptance examples for the highest-impact gaps

**Flexible budget (FB-01).** An ordinary $120 all-in baseline remains visible through
search, review and Back. A higher-priced lot can remain eligible when the user's
explicit value/cost rule supports it. Unknown costs, partial contents or a generic
publisher guide do not silently qualify it. Do not invent the user's higher ceiling,
minimum margin or resale assumptions. The $300 cost/$450 value example is illustrative,
not an automatically configured threshold or purchase authorization.

**Physical allocation (FB-08).** A four-card Lapras family containing distinct printings
can be represented as one identified Fossil card plus three unresolved cards, and later
split further. Choosing the Fossil printing cannot silently include four copies.
Show reconciliation and its evidence before valuation; possible species gain remains one.

**Seller reconciliation (FB-04/10).** An explicit total and itemized quantities reconcile
without counting repeated mentions or subgroup prose twice. Shared seller traits can be
confirmed for their actual scope; conflicting or absent traits stay unresolved. Actual
seller photos may support a recorded manual correction, but image alt text must not be
accepted as physical card evidence. Condition claims remain unverified claims.

## Observed strengths to preserve

The real collection supplied missing-species choices. Back restored search context and
focus. Full details were available through an explicit bounded action. The comparison
kept a publisher subtotal separate from condition-specific value, showed unresolved
cards, and withheld all-in totals when costs were unknown. No purchase, bid, ownership
mutation, reseeding or substitute customer runtime was required for the walkthrough.

## Delivery record

All eleven entries have implementation coverage: flexible baseline/rule/value basis;
contextual allowance; visible full-details action; previewed batch trait confirmation;
explicit review budget overrides; automatic versus authored selection labels;
separate search-result review status; multi-printing allocations with remainder;
renamed printing search and autosave feedback; named total/subgroup/repeated-claim
and scoped-condition handling; and a private session shortlist with original expiry.

Focused verification: 248 service, parser, boundary and shipped-interface checks
passed. The browser adapter includes a four-card family split test (one copy of
one printing, two of another, one unresolved). The journal tests cover independent
session authority, Stop, fixed expiry and budget overrides. No acquisition contract,
account/catalog schema, pricing source, credential or collection mutation changed.

Additional verification: 182 focused tests plus two actual-Hunt budget-policy cases
passed. The shipped interface adapter covers 27 cases, including explicit batch
confirmation. All 20 SHOP-17 browser journeys completed their functional assertions.
The local timing aggregate failed its 60 ms non-SQL processing allowance for review
and candidate routes (candidate p95 93.8 ms in the latest run); candidate end-to-end
p95 was 276.4 ms. This is a recorded timing limitation, not a claim of a passing
performance gate. Hosted CI and installed behavior are tracked independently.

The protected existing customer installation received application commit
`c621ea29851047a2143ee49ef0fab550694f4d8b`. The actual Moltres rerun verified
target selection, the flexible baseline, finite usage accounting, explicit detail
loading, one-copy allocations, cost edits, comparison, separate review status,
the two-entry decision journal and restored review. Eleven screenshots are embedded
at the relevant steps of the private walkthrough. Original owned-copy rows and
consumed accounting history were preserved; no purchase, bid or inventory change.

Hosted run 42405202177 identified two stale browser expectations: toggling the
details disclosure now closed it, and the new shared-trait checkbox was mistaken
for a physical printing selection. The browser scripts now assert the expanded
panel, target actual printing controls and explicitly enter two copies. The full
isolated browser script and both focused restoration/expiry tests passed locally.
The hosted volume journey also reported candidate processing over its 60 ms
non-SQL allowance; functional assertions completed. Hosted status is not green.

## Follow-up observations from the Moltres rerun

These are newly observed follow-ups, distinct from the eleven initial fixes.
Personal screenshots, listing IDs, prices and collection details stay outside Git.

| ID | Observation | Next behavior |
| --- | --- | --- |
| M-01 | Full item specifics named one bird while the title and photo showed three. Local search was required for the others. | Reconcile missing title candidates as unconfirmed evidence, without treating mentions as physical cards. |
| M-02 | Source benchmark shipping remained unknown while authored cost calculations used the observed shipping. | Label provider-reported and reviewed costs clearly. |
| M-03 | Broad printing search exposed raw variant attributes and required a more specific set query. | Readable trait labels and clearer set refinement. |
| M-04 | No applicable normalized or condition-specific value supported the chosen lot. | Obtain qualified condition-matched evidence within source rights; preserve unknown values meanwhile. |
| M-05 | Screenshots and the durable how-to were assembled outside Dex. | A walkthrough export with retention-aware screenshots and authored decision records. |
