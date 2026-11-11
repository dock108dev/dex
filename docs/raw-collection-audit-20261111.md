# Raw-first detailed audit — November 11, 2026

This is a read-only source and installation-metadata audit, not an interactive product walkthrough, implementation or complete call-graph proof. See [direction and milestones](raw-collection-direction-20261111.md) and [first engineering prompt](raw-collection-engineering-prompt-20261111.md). `main`/local `origin/main` were at `b1a14fd`; the working tree already contained the owner's preceding documentation edits. No network acquisition or account mutation occurred.

## Findings and engineering implications

1. **Unknown listing status currently becomes raw in important paths.** `discovery_comparison._clues` detects literal grade/slab wording but returns `grade="raw"` when it finds none. `hunter_catalog` marks a single ungraded when that detector is negative and the provider's localized Graded aspect is not affirmative. Absence of evidence is not an affirmative ungraded claim. Shopping's `discovery_singles.classify` is a release/identity classifier and explicitly treats grading conflicts as non-identity issues; it is not a raw-status classifier. Implement evidence-backed raw/graded/unknown outcomes; preserve negative/contradictory claims and provider-aspect evidence, and prevent unknown or graded singles from silently getting raw-specific prices. Lot-level claims need scoped treatment, not a blanket single-card inference. The precise presentation and compatibility with historical saved runs require end-to-end tracing.
2. **The surface extends beyond the first plan.** `static/collection.js` copy forms; `static/bulk_entry.js` fields and certificate duplicate handling; CSV import/export (`collection_imports.py`, `bulk_formats.py`); `static/parity.js` collection estimates; `static/shopping.js` and `templates/beta/shopping.html` grade/grader inputs; `static/lot_calculator.js` and its template (raw/8/9/10); `static/listing_check.js` value-basis/grader controls; `static/hunter-review.js` grading claims; and discovery/Hunter rendering and old saved research all need explicit off-mode review. Related server code includes `shopping_inputs.py`, `shopping_views.py`, `lot_calculator.py`, `lot_guides.py`, `listing_check.py`, `hunter_lots.py` and `discovery_comparison.py`. This is an inventory of likely affected paths, not a guarantee of completeness.
3. **Data preservation requires omission, not empty form fields.** `collection_plans.py` edit merges provided attributes with stored `FIELDS` before validation. That can preserve omitted grade data, but a hidden UI that submits empty values could still overwrite it. `account_read_records.py` carries grade, grading company and certificate; `bulk_input.py` checks paired grade/company and unique certificate semantics. Verify all edit/import/export/preview/confirm/undo and saved-state paths, including stale clients and direct requests, rather than assuming the merge protects them. Existing graded copies still count as owned. Off mode needs a truthful, non-editable indication when relevant; don't present slabs as raw or expose cross-account details.
4. **Flag design is new.** `settings.py` exposes B1–B4 marker-backed installation capabilities, not an identified graded-feature switch. Use one centrally owned, server-authoritative, default-off policy and propagate it consistently to templates, scripts and relevant projections. Do not repurpose capability markers or impose a customer data migration just to hide the feature. Keep on-mode accessible through a documented operator configuration and prove parity through focused tests. Configuration must be private/portable and fail safely.
5. **A raw guide is not automatically a comparable sale.** `valuation_evidence.py` treats v2 and publisher-native v3 records as raw-specific under their admission contracts; `sold_estimates.py`, `lot_guides.py` and snapshots maintain separate source and lifecycle semantics. Preserve these owners and do not pool or relabel native mixed-condition guides as condition-matched sales. Require exact physical identity, condition scope, source rights, currency, cost basis and original observation dates for a numeric comparison. Independently address the admission of an ambiguous listing, rather than disabling all useful raw guides.
6. **Prior resale workflows remain present.** `hunter.html` and related calculations discuss resale; the old tracker UX-10 asks for a 10% net-return demonstration. This is deferred as a product priority, not authority to delete the calculation or invent a new resale gate. Separate the raw collector's next action and ordinary navigation from legacy direct/saved access, with coherent off-mode handling.

## Read-only local facts and limits

- `.local/runtime` points to the existing rc39 runtime; installed package metadata reports `0.1.1rc39`. No process was listening on port 8011 when checked. This does not establish currently running UI behavior; the app was not started for this audit.
- A read-only aggregate of the customer database found 209 active copy records, zero with a non-null grade, grading company or certificate. This is a current record count, not a claim about physical cards or historical/other-account records. Use isolated realistic graded records to verify preservation; never create customer records just for a test.
- The installed read-only v3 readiness projection returned 552 eligible publisher-native guide printings, 0 eligible normalized raw guide printings and 0 eligible sold printings out of 33,578 catalog printings; no condition-scoped sold or guide printings qualified. It reports source access and source absence as not established. These are active admitted-reference coverage counts on November 11, not current prices, provider-wide absence or proof that a particular listing can be compared. Native guides can be useful with their actual mixed-condition basis.
- Correction to older documentation: the current `scripts/lot_value_readiness.py` default is version **3**, while the Python `project` default is version **1**. The earlier version-2 statement described an intermediate state.

## Remaining audit within engineering

Trace remaining routes and mutations as each is implemented, including old sessions, export/import, direct endpoints, filters, result labels, comparisons, history, keyboard and narrow-screen interaction. The copy-editor slice established the startup setting and server mutation pattern. Extend the policy at the valuation and comparison boundaries and exercise the actual installed experience through the ordinary customer runtime. Continue source qualification alongside implementation.

## In-progress call-path findings

### Copy-editor flag foundation (incomplete)

The checkout now has one process setting, `GRADING_ENABLED`, defaulting off unless
`DEX_GRADING_ENABLED=1` is set at startup. The ordinary copy editor derives its
controls from the server-rendered setting. The server's edit plan ignores supplied
grading company, grade and certificate while off, including fields submitted by an
older client; the stored values are retained. Confirmation recomputes the plan,
so a changed flag cannot silently apply a differently reviewed edit. Import/export
has not been disabled. This is a foundation, not a complete product flag: valuation,
bulk entry, Shopping, lot and saved/direct paths still require implementation.

An isolated fixture with PSA, grade 9 and a certificate survived a current unrelated
edit containing old-client blank grading fields; an outdated revision was rejected,
and the same data was readable with the flag enabled. This exercises HTTP preview
and confirmation and server-rendered flag states, but does not yet exercise the
ordinary editor in a browser. The relevant domain, review, Discovery, Hunter and
listing-status tests passed (124); Ruff, JavaScript syntax and diff whitespace
checks passed. These are uncommitted, uninstalled results.

The November 11 read-only v3 readiness recheck again found 552 eligible native
guide printings, zero eligible normalized raw guides, and zero condition-scoped
guide or sold printings, among 33,578 catalog printings. It performed no provider
operations or customer writes and does not establish source access or source-wide
absence. Exact-printing, condition-aware source qualification remains open and
does not prevent continuing the flag or UX work.

At the copy-editor checkpoint, collection valuation still built graded scenarios
and the Shopping template still rendered grade and grader inputs with the switch
off. The valuation continuation below addresses the collection calculation.
Shopping still lacks the policy. The HTTP tests establish server behavior for the
tested requests. Browser and customer journey verification remain open.
The agreed delivery plan includes hosted checks and protected installation.
An unavailable eligible source leaves the priced-comparison outcome open.
Once the ordinary journey is verified, the owner can review offer inspection
and the guide-only or unavailable-price state using the available evidence.

### Comparison compatibility follow-up

The uncommitted Discovery/Hunter change now holds a comparison when the seller-status
classifier and the legacy price-selection clues disagree. It also rejects an explicit
reference grade that conflicts with an explicit claimed grade. Lot-review callers may
omit a single-card grade, so the latter check applies only when both are present; this
does not establish that the remaining lot classification paths satisfy RAW-03.
The existing Discovery comparison fixtures now state their intended ungraded seller
aspect explicitly instead of depending on missing status being treated as raw.

Focused local verification: 200 tests passed across listing grading, Hunter catalog,
Discovery comparison, listing check, and Hunter lot review; Ruff passed for the touched
Python files. An initial wider run exposed seven lot/review regressions from applying
the grade guard when the caller supplied no grade; the guard was narrowed and the
same checks passed. These are isolated engineering results, not installed behavior.
The feature flag, stale-client copy preservation, remaining single and lot paths,
UX, source qualification and delivery remain open. No commit, push, installation,
customer data change or provider acquisition was performed in this follow-up.

- `collection.js` serializes every copy-editor field through `FormData`; `collection_plans.build` merges supplied edit attributes over stored fields before validation. Omitting the grading controls preserves existing fields, but stale clients can still submit them. Bulk entry has its own draft/default/row pipeline and can reopen authored attributes; import/export uses the same copy fields and must retain them. Preview, confirmation, undo and account boundaries need explicit checks.
- `parity.projection` calls `estimates`, which constructs conditional and confirmed per-copy and aggregate scenarios. Removing controls in `parity.js` alone cannot suppress server-returned amounts or avoid applying raw valuations to recorded graded copies.
- `lot_calculator` validates all snapshot columns and builds references and totals per column; `listing_check` constructs all those columns for leased comparisons. Shopping accepts selected grade/grader attributes and can reopen saved research. A switch must cover those service projections and direct calls, without changing retained saves or the independent snapshot/source lifecycle.
- Discovery and Hunter share `discovery_comparison._project`, but Hunter additionally ranks and renders rows, and its simple mode formerly filtered away non-ungraded singles. Lot parsing and explicit per-card review have different scopes; a title-wide single-card classifier must not be applied indiscriminately to mixed lots.

### Intended policy boundary

One process configuration, off by default and distinct from B1–B4, should govern server projections and the controls derived from them. Off-mode edits must preserve the stored grading fields even for stale clients; an existing graded copy remains owned and identified as graded. Imports and exports should retain their exact data, with previews explaining preserved grading fields. Reopening a saved graded scenario should retain authored inputs while withholding graded calculations in off mode; enabling the switch should recover the prior behavior without rewriting the record. This is a proposed design, not a delivered switch.

Single-card seller evidence should distinguish explicit ungraded, explicit graded and unknown/conflicting claims, including the provider's Graded aspect. All are claims rather than physical authentication. Unknown or conflicting singles remain inspectable and receive no raw reference comparison. Mixed lots require separately scoped per-card evidence. An initial source change implements this distinction for shared discovery/Hunter single projections and retains single results in Hunter's simple view; other listing, saved-state and lot paths still need tracing and verification before this can be called complete.

## Collection valuation continuation — November 11

The uncommitted parity projection now filters grade records before valuation when
`GRADING_ENABLED` is off, exposes only raw scenario keys, and excludes copies with
recorded company, grade or certificate from raw estimates while retaining them in
ownership and coverage counts. The enabled calculation remains available. The
collection overview and copy price disclosure use raw-only wording when disabled.
An isolated graded copy was checked through off/on projections. The parity suite
and the existing copy-review, listing-grading, Discovery and Hunter checks passed
(114 tests; one expected socket-block warning). This is not complete flag coverage:
lot calculator, Shopping, bulk entry, saved research and direct paths still need
server and presentation treatment and transition tests.

The off-mode collection view currently omits the recorded purchase-cost summary
and the raw per-copy guide link and age guidance shown in the previous view.
Retain those details as applicable during the remaining UI work.

The ordinary launcher started the existing `.local/customer` root using the rc39
runtime; its listener and root were verified. In Chrome, the recorded copy editor
opened and still showed its grading disclosure. That is an observation of the old
installed build, not the uninstalled candidate. The editor was closed without a
mutation. No candidate installation, provider acquisition, or acceptance occurred.

A public documentation check found that [eBay Marketplace Insights](https://developer.ebay.com/api-docs/buy/static/ref-marketplace-supported.html)
is restricted and not open to new users, and its [API agreement](https://developer.ebay.com/support/api-license-agreement)
requires express written consent for pricing tools using Restricted API data.
This does not establish this account's access, an approved use, or an exact-card
condition mapping. [TCGplayer's pricing documentation](https://docs.tcgplayer.com/reference/pricing)
describes price endpoints, but access, contract rights, condition and money basis
were not established in this check. No source was admitted or activated. The
condition-matched numeric comparison remains open; this source gap is separate from
the unfinished engineering and does not itself prevent review of usable unpriced
shopping flows.

## Subsequent local continuation (uncommitted, not installed)

The lot preparation boundary now calculates only the raw scenario with grading
off, including direct and listing-review callers; its catalog projection omits
graded guide cells. A saved modern comparison is projected with its raw result
only while the stored snapshot and original graded inputs remain intact. Legacy
Shopping rejects graded requests while off and presents retained graded history
as unavailable; enabled-mode history remains intact. Listing review hides its
graded controls in off mode while retaining any existing claim. Bulk entry hides
grading controls and retains hidden values during ordinary row edits. Collection
valuation again shows purchase totals, guide age and the raw guide source link.
These are a partial implementation, not proof of all flag paths or the journey.

The first affected test run failed one existing four-scenario test because it
implicitly assumed grading was enabled. The test was given that explicit setting;
the affected suite subsequently passed 193 tests, including saved-lot and legacy
off/on preservation. Two isolated browser checks passed for hidden bulk controls
and the existing bulk save/confirm/undo flow. Ruff, JavaScript syntax and diff
whitespace checks passed. Full bulk draft transitions and import/export, legacy
and listing browser interactions, mixed-lot evidence, accessibility, real-app
behavior and delivery remain to be verified; the current tests do not prove them.

Further public documentation describes the [Pokémon TCG API's deprecation and
closed new registrations](https://docs.pokemontcg.io/getting-started/authentication/)
and its [price fields](https://docs.pokemontcg.io/api-reference/cards/card-object/).
This does not establish pricing rights, account access or exact condition and
printing mappings. No provider request, admission or activation was made. The
condition-matched priced comparison remains open independently of the local UX.

The next continuation should exercise the paths that can still affect persisted
records or user decisions. Bulk's hidden controls still serialize draft fields,
so verify unrelated edits and explicit clears through the draft lifecycle,
including re-enable and import/export. Verify saved research reevaluation in
addition to reopening. Hunter's publisher-guide subtotal handles missing grade
values separately from the normalized comparison, so exercise both paths with
the same mixed lot, including corrections. These are specific open compatibility
checks. Existing local tests and the earlier rc39 observation do not establish
candidate browser behavior.

## Integrated continuation — November 11

The bulk draft service now preserves the existing row and default grading fields
when an off-mode client saves unrelated changes, including a direct old-client
payload. New imported rows retain their authored fields. Isolated browser and
service checks exercised a graded draft through save, review, confirm, undo,
re-enable, stale submissions and a full JSON export/import to a separate test
account. The bulk suite and three browser checks passed (57 tests), and a further
default-preservation check passed. Exploratory test setup failures involved
async test access, an active-only undo reader, settings setup and a deliberately
changed fixture catalog identity; the corrected tests passed without customer data.

Saved modern and legacy research was reopened and reevaluated off and on. The
original snapshot remained intact, off-mode projections withheld graded values,
and enabled mode recovered authored scenarios. Legacy raw history also no longer
exposes unused graded alternatives while off. Shopping and calculator checks passed
(42). Two preliminary synthetic-guide tests failed because their fixture identity
and admission digest did not match; corrected fixtures passed.

Mixed-lot parsing now keeps absent or conflicting per-card grading claims unknown.
Direct listing and Hunter tests covered raw, graded and uncertain cards, corrections,
normalized comparisons and publisher-native subtotals; only supported raw cards
contributed to the raw subtotal. The focused listing, Hunter and Discovery suite
passed 219 tests. The Hunter renderer contract initially failed because its old
fixture did not include the new explicit raw status; the fixture was updated and
missing/unknown status exclusions were added, and the same check passed. Four
historical lot fixtures also needed explicit seller evidence before their rerun passed.

An installed-workflow test initially failed because the calculator accessed
unconfigured Django settings. The shared flag reader now defaults off for a truly
standalone consumer while preserving configured-settings errors. The installed,
transition and package suite passed 81 tests on rerun. The assembled affected
service suite passed 402 tests. The collection/Discovery/lot browser suites
passed 40 tests, and four collection-to-Shopping return/focus checks passed.
These are isolated engineering results; customer installation and owner review
are separate. The earlier four-scenario failure and rerun above remain recorded.

Source qualification remains open. eBay's [Marketplace Insights access page](https://developer.ebay.com/api-docs/buy/static/ref-marketplace-supported.html)
describes restricted access; its [condition filters](https://developer.ebay.com/api-docs/buy/static/ref-buy-browse-filters.html)
are category-dependent. [TCGplayer condition-SKU pricing](https://docs.tcgplayer.com/reference/pricing_getmarketpricebyproductconditionid-1)
is a possible lead, but account access, license/display rights, exact printing and
condition mappings, and money basis are not established. No source was admitted
or activated and no provider operation was performed. This gap prevents the
condition-matched priced outcome; it does not prevent review of a verified journey
with accurately labelled guide or unavailable evidence.

The rc40 wheel was built separately from the selected rc39 runtime. A standard
transition rehearsal failed at an isolated assertion with both rc39 and the
available rc8 interpreter; the retained reports record the failure, not a pass.
That rehearsal expects the previous reader to reject the candidate schema. A
separate generated-state rehearsal for the actual rc39-to-rc40 path instead
verified that both readers remain ready on the shared schema, preserved 40
authoritative tables and the consumed usage prefix, rebound package identity,
rolled back using current authority, and re-upgraded with zero provider calls.
It passed. This does not itself install or validate the customer runtime.

The rc40 customer installation used the existing root and preserved the independent
Hunter usage journal. The initial launch did not see eBay configuration because
the private runtime-local configuration had not been copied; copying the same
private configuration from rc39 restored the configured state. One bounded,
nonrecurring two-operation window preserved six earlier operations and used an
OAuth and one Browse operation. Acquisition was paused afterward with all eight
operations retained. The real browser went from a missing Pokédex entry to singles,
reviewed a received offer and displayed asking price, shipping, unknown tax and
an unavailable condition-matched comparison. The seller link opened; Back and
reload restored the offer, filters and focus. A narrow view was inspected. No
purchase, detail request or source admission occurred. The original lease-expiry
behavior is covered by isolated checks, not by waiting out this real offer.

The real collection overview then stalled while loading a large existing catalog.
The server returned its data, and the browser remained busy. The renderer repeatedly
searched the catalog for each card while grouping sets; the rc41 continuation uses
an indexed lookup. A new 5,000-card renderer check verifies set counts; its first
run failed only because the enclosing suite expected the previous test count. After
updating that count, 71 SSOT and parity tests passed. Installed rc41 verification
and hosted checks remain separate and were not established by that local test.

The rc41 wheel built from `198d455` was byte-identical on rebuild, passed the
Python 3.14 installed smoke and the rc40-to-rc41 same-schema rollback rehearsal.
After a second stopped-server backup with matching database checksums, the private
configuration and append-only usage binding were preserved and rc41 was selected
on the existing root. The ordinary runtime reported ready. The real overview
eventually rendered with purchase costs, guide date and age rule, and an unavailable
estimate. It still took tens of seconds to load its full catalog, so this is not a
performance qualification. The earlier browser stall remains recorded above.

Hosted runs for `6158cc1` showed GitHub startup failures for CodeQL and dependency
graph without jobs or logs; its Tests run was still queued at this observation.
Tests, CodeQL and dependency graph for `198d455` were also queued. Hosted CI was
therefore not verified as passing, and these statuses must not be treated as local
test failures or a passing hosted result. No cause was exposed by the run details.
