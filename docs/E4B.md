# E4b — retained offer comparison and link eligibility

October 5, 2026. Locally qualified offline engineering on disposable synthetic
state; [validation and preservation](history/2026-10-05-E4B-VALIDATION.md).
Live refresh remains unavailable. Real-source shopping and full beta remain open.

## Local comparison

Packs to open defaults to all retained offers, sorted by original checked time,
newest first. Server validation accepts stock all / in-stock / out-of-stock /
unknown and observation age all / fresh / older / unknown. Preorder remains its
own known stock state and appears under all. Future timestamps appear under all,
never fresh or older. Unknown includes missing/invalid/naive times. Fresh uses the
existing inclusive interval `0 <= now - checked_at <= 24 hours`.

Each offer uses its newest original aware timestamp, compared as an instant.
Timestamp ties use observation ID ascending; unknown times sort after dated times
and then by ID. If no observations exist, its representative is empty, not a
fabricated unknown-stock observation. Checked-time sorting follows that same key,
then offer ID. Each visible offer retains its full original history, including
older unknown-stock records; a historical unknown does not override a newer
out-of-stock representative. Failed acquisition creates no stock observation.

Maximum item price is optional, nonnegative, at most two decimal places and requires
an explicit uppercase three-letter currency. Comparable item-price sorting also
requires that currency. Maximum filtering excludes unknown prices/currencies and
other currencies. Price sorting orders comparable prices ascending, then offer ID;
unknown/other-currency prices follow by offer ID, explicitly labeled incomparable.
No conversion, shipping total or delivered-cheapest ranking is performed. Zero is
an explicit known price, never the replacement for a missing value. Item price and
shipping are separate; price per relevant pack retains E3a's requirement for verified
quantities and exclusively relevant expansion contents.

Sorting operates on offers within each exact product, without combining different
product identities. Filtering never changes the selected goal or confirmed printing,
species or expansion coverage. Products/coverage stay visible with an explicit empty
offer result. Reset clears only offer comparison settings, retaining the exact frozen
goal/version, species and expansion. Scope changes remain explicit form choices.

## Server link decision rules

`beta/offer_filters.py::eligibility` is the sole offer-link policy, also used by the
sealed diagnostic report's retained `buy_now` compatibility field. It returns
source / offer / purchase_ready booleans and concrete reasons for each level.

- **View source** requires a syntactically safe HTTP/HTTPS URL with a valid host,
  no embedded credentials, whitespace, backslash, invalid port or encoded control
  characters. This is a manual-review URL; no request is issued to validate it.
- **View offer** additionally requires exact product/offer association, usable
  retailer provenance supporting the offer observation with the exact offer as a
  subject, a named actual seller and direct/marketplace status. Synthetic/replay
  evidence is excluded, including product provenance.
- **Purchase-ready** additionally requires exact usable official product-identity
  evidence, resolved contents, observed in-stock status, an original checked time
  inside the inclusive 24-hour window, and an explicitly verified fresh backend
  availability time. The supported schema and replay adapter cannot attest that
  time, so purchase-ready is always false. The unused caller-supplied timestamp
  interface has been removed; enabling purchases requires a separately reviewed
  evidence contract and supported backend adapter.


Recent tool-read time is not a backend-stock attestation. Timestamp notes remain
visible with the full history. The retained Target offer has unknown actual seller,
unknown official contents, dated out-of-stock observations and unresolved backend
availability. It exposes View source and explicit reasons, with no View offer or
Buy now. Replay fixtures never establish a real purchasable offer. Fixture tests qualify the supported blocked-purchase behavior only. No network request is made by
rendering, filtering, saving or reopening a link.

## Frozen saved research and compatibility

New E5a snapshots store validated offer settings along with the exact displayed
offers and their full histories, using the existing v1 extensible context. Reopening
uses only those retained observations and references. It updates derived age and
eligibility labels but does not rerun offer selection as timestamps age, reproject
ownership, substitute newer observations or choose a successor goal. No saved bytes
are rewritten. Old snapshots without settings receive all/checked defaults in memory;
all their original offers remain visible. No E4b schema migration is needed. Existing
classic eBay URLs retain their frozen goal IDs and existing saved hunts are preserved.

## Reproduction

Use unused disposable paths; do not operate an owner installation:

```sh
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output NEW_SEED
uv run --no-sync python scripts/rehearse_e4b.py prepare --seed NEW_SEED --root NEW_COPY --output NEW_EVIDENCE
uv run --no-sync python scripts/serve_e4a.py --root NEW_COPY --output NEW_EVIDENCE
# Exercise whole goal, Scyther, filters/reset, uncertainty, save/reopen,
# predecessor, legacy saved research and member isolation in the ordinary UI.
# Stop/restart only this synthetic server to verify durable saved reopening.
uv run --no-sync python scripts/rehearse_e4b.py verify --root NEW_COPY --output NEW_EVIDENCE
```

The helper constructs one explicitly synthetic pre-E4b v1-shaped snapshot before
its preservation boundary, and checks that row byte-for-byte afterward. The existing
server helper guards and counts acquisition across restarts. No live adapter, source
read/discovery/retry, credential/provider activation, recurring job, purchase/bid,
hosting or deployment is part of this work. PostgreSQL execution remains unqualified.

Next bounded action: **E6a offline integrated goal → Packs → filtered saved research
and retained classic-eBay walkthrough**, on fresh disposable synthetic state. The
component slices are ready for one integrated path with explicit ownership and
frozen-version transitions; use retained/sample eBay only, with zero acquisition.
Real availability, official contents, current purchasability, all-era coverage,
separate-person review, populated eBay and full beta acceptance remain open.
