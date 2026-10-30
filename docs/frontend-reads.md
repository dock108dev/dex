# Bounded frontend reads

## Implemented consumers

- My Cards and Card Library use private V2 group pages directly, without a collection
  bootstrap or a filter-dictionary dependency. Search controls precede the primary
  request. Primary results include server-owned status and nullable quantities.
- Card detail uses the V2 summary. Variants, copies, removed-copy history and unresolved
  evidence are explicit paged disclosures. Matching variant filters have a separate
  disclosure; list filters are not reapplied as ownership rules. Detail artwork is one
  independent request. Copy photos are independently authorized on expansion.
- Public Card Library, card details, Pokédex and species cards use a public shell and
  public V2 reads. Missing public ownership fields never become zero ownership.
- Private Pokédex uses compact V2 collection context and bounded species summaries.
  Species detail requests identity and a bounded owned-card page, with server-evaluated
  scope qualification. More owned cards are explicit; evidence has a complete-record
  link. Species quantities remain unknown. Saved species-goal progress remains distinct
  from current ownership.
- Manual printing search and custom goal membership use private `printings` pages.
  Public V2 pickers retain their separate `cards` contract. Custom goal selections are
  retained across searches, sets and pages. Filtered-goal membership is evaluated by
  server preview instead of projecting a downloaded catalog in JavaScript.
- Scan correction uses a paged private picker and bounded duplicate-count reads instead
  of full catalog/all-copy bootstraps. Photo-batch correction uses V2 group search and
  bounded candidate-ID resolution. Candidate sets above 100 require manual correction;
  they are not silently truncated or fetched in an unbounded loop.
- Bulk entry uses paged game/set dictionaries and V2 group pages. Draft rows survive
  moving off-page. Its visible selection button now explicitly selects **this page**.
  Variants and binders load on explicit request. Review/confirm/Undo continue through
  the existing mutation authority. Isolated workflow checks cover saved drafts, confirmation, recovery and Undo.

`bounded-reads.js` owns cancellation, revision binding, explicit continuation and
oversized-record expansion. It validates response version/publicness/account/revisions,
rejects obsolete channels/routes, and does not fall back to V1. Rejected access clears
private screen content. A 409 requests reload; a `read_state_unavailable` 503 explains
that explicit preparation/recovery is needed. No GET prepares state. Secondary errors
retain primary results. Confirmation saves its receipt before refreshing derived reads;
a failed refresh does not resubmit the write.

Card/species return selectors are kept separate from API filters. Existing private
focus/scroll/tab memory remains account-bound. Public browsing has per-tab Back memory.
Filter-option pages expose explicit continuation; selected literals remain selectable
when absent from a loaded option page. No automatic complete dictionary download runs.

## Supporting API resources

These `/api/v2/` resources are independently authorized, revision-bound reads
using the prepared private representation.

| Resource | Purpose |
|---|---|
| `species/<dex>/owned-groups/` | Paged current-owned groups with three-valued, server-evaluated scope qualification |
| `goal-options/` | Paged saved-goal summaries for Pokédex selection |
| `binders/` | Paged account binder choices for physical-copy editing |
| `selection-groups/?ids=...` | At most 100 distinct literal printing candidates, with bounded server group summaries |
| `entry-options/?field=game` or `field=set&game=...` | Paged manual-entry dictionaries |
| `goals/`, `goals/<id>/items/`, `goal-sources/` | Authorized saved headers, frozen progress, and source choices |
| `labels/?items=...`, `selected-groups/?ids=...` | Bounded retained labels and visible saved-draft identities |
| Public/private `group-artwork/`, `species-artwork/` | Bounded authorized reference descriptors; never private-photo discovery |

Species responses also carry frozen-goal progress and supported species units. Public
and private card shells no longer perform the old group projection before returning
HTML. Canonical alias and remembered-detail authorization were connected to V2 reads.
V1 JSON endpoints, exports, workers and mutation-validation services remain available.

## Goals, retained selections and bulk equivalence

Goals now uses compact context, paged saved summaries, indexed frozen target progress,
and paged collection-source choices. Ordinary creation, editing, source selection and
Pokédex goal creation do not fetch `/api/collection/`. Goal preview/confirmation remains
the server authority for membership. Large goal headers and individual targets require
explicit complete-record expansion; no list silently downloads full definitions.

A saved filtered definition is reused as saved. A checklist without historical filters
supports a name-only edit that retains its exact definition and version, plus an explicit
separate replacement while the original remains. No historical filter reconstruction is
attempted. Original-151 successor previews and source-based successor controls remain.

Private selected-label reads resolve at most 100 IDs across authorized kinds. Public
set choices support exact selected-value resolution. Literal values remain unchanged;
labels load independently of primary results. Bulk row labels resolve only the visible
tray page, including saved off-page rows. Binder and printing choices retain selections
while further choices are paged explicitly.

Bulk provides separate “this page”, “all matching” and cross-page range actions. The
latter two explicitly traverse bounded revision-bound pages, collect the result before
changing the draft, and enforce the existing 2,000-row limit. Range endpoints must share
the same query. Saved drafts retain off-page membership. Receipt recovery runs before
catalog reads, so a confirmed operation remains visible and undoable during derived-read
unavailability; recovery never repeats confirmation.

List artwork is progressive: one bounded descriptor batch, only visible/nearby images,
and at most four image loads at once per rendered list. Existing reviewed mappings and
source policy remain authoritative. Primary readiness does not await images, image space
is reserved, missing art stays unavailable, and failed metadata offers explicit retry.
Private photos still use their independently authorized per-copy resources.

## Remaining V1 calls

- `collection.js` retains `/api/collection/` for the explicit physical-copy, Settings,
  import/export and maintenance screens, plus retained parity workspaces (Overview,
  Hunt, Missing and Finds) outside the migrated browsing routes. These are existing tool
  consumers, not error fallbacks. `withCollectionTools` remains a compatibility helper
  with no current ordinary consumer; Goals/Pokédex goal editors no longer call it.
- `/api/parity/` remains an explicit retained-price/tool read, with existing source rights
  and valuation checks. Lists and primary detail do not request it. Price disclosure
  identifies the loaded copy subset rather than implying all copies were read.
- `/api/pokedex-species/` remains in the legacy source-maintenance disclosure in
  `pokedex.js`; ordinary Pokédex browsing uses V2.
- Scan/photo/bulk mutations, saved-operation, draft/history and recovery endpoints keep
  their existing contracts. They are not full-catalog browsing fallbacks.

## Renderer and workflow tests

Renderer scripts exercise shipped assets and revision-bound transport in a DOM.
Workflow tests cover Goals, bulk selection and receipts, manual photo correction,
access revocation and secondary failures. Install the development dependencies
listed in [CI](CI.md#local-checks), then select the affected checks:

```sh
uv run --no-sync pytest -q tests/test_perf04_browser.py tests/test_perf04_interactions.py --disable-socket --allow-unix-socket
uv run --no-sync pytest -q tests/test_perf04_workflows.py --disable-socket --allow-unix-socket
uv run --no-sync pytest -q tests/test_perf04_contracts.py --disable-socket --allow-unix-socket
npm ci --ignore-scripts --no-audit --no-fund
node scripts/verify_cx05_races.js
node scripts/verify_cx06_races.js
node tests/bounded_reads_cases.cjs
node tests/perf04_mutation_cases.cjs
node tests/perf04_prices_cases.cjs
node tests/browsing_performance_cases.cjs
node scripts/verify_photo_client.js
```

The browser test listens only on a free loopback port and blocks nonlocal browser
requests. Its WSGI test adapter maps that port's Host to the ordinary local ingress
Host without changing production security. It uses 33,083/66,166 synthetic printings
and 5,000/10,000 recorded copies, with 10,000/20,000 historical operations. It never
opens the customer root or starts a provider/recognition worker.
