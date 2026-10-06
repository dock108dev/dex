# E4a — bounded refresh with a replay-only adapter

October 5, 2026. **Locally qualified synthetic engineering.** See the
[validation record](history/2026-10-05-E4A-VALIDATION.md). Live acquisition remains
unavailable; this slice establishes no current retailer stock or purchasability.

The Packs page links to **Refresh**. Ordinary owner mode displays “Live refresh
unavailable” and makes no acquisition request. Replay forms appear only in local
`SYNTHETIC_ONLY` state, after explicit additive migration, for an authenticated
catalog owner. Members cannot see controls or other accounts' histories. Every
operation re-resolves account authorization. POST actions require CSRF.

The development form selects an exact published product, 1–7 distinct replay
sources and a fixed 1–30 second per-source timeout (default 2). The service pins
the exact product and offer identities plus source scope, account and initiating
actor. One attempt per source is established before execution; sources execute
sequentially with no automatic retries. Another run requires explicit Start.

Runs retain created/start/end times, final completed/failed/stopped status and
reason. Each attempt has an independent ID, source/offer identity, reservation
start, deadline, execution token, terminal time/outcome, candidate or specific
failure, timestamp quality and review reference. Consumed attempts are derived
from durable reservation starts, including timeout, cancellation and interruption.
Stop never refunds these starts; remaining planned attempts become cancelled.
Completed candidates remain available even when another source fails or the run
is stopped. Unknown-stock candidates contain observations; denied, malformed,
identity-mismatched and failed sources supply none.

A conditional database claim permits one executor per run. Reservations commit
before adapter execution. Compare-and-set delivery accepts each running attempt's
execution token once; stopped/interrupted/late/duplicate delivery cannot overwrite
its outcome. Replay checkpoints honor cancellation and the fixed deadline. Final
validation and delivery also check the deadline. Only the cooperative replay
adapter is registered; this is not a hard timeout guarantee for arbitrary future
blocking HTTP adapters.

Restart does not execute queued or interrupted work. On explicit outcomes-page
view, expired running work becomes stopped/interrupted with consumed attempts
retained; an unexpired execution is left alone until its deadline. No lease is
reclaimed, budget reset or automatic resume occurs. A queued run that never began
can be stopped; another execution requires a new explicit run.

## Immutable observations and review

The adapter returns only sources and observations for the pinned offer. New
products, sellers, mappings, corrections, bridges or product relationships are
rejected. Existing sealed validation checks provenance, applicability, identities,
source times, archived conflicts and immutable records. No observation is
published during execution. **Preview for review → Verify candidate → Publish
reviewed fixture** uses the existing sealed review/publication service. A repeated
identical package reuses its prior reviewed import, without creating observations
or changing original checked times. This structural/local review does not establish
separate-person review or actual source truth.

Fixture observation identities and checked times are deterministic, independent
of run/execution time: January 1, 2020 for the out-of-stock fixture and January 2,
2020 for the explicit unknown fixture. Sources, notes, timestamp quality and the
interface label them synthetic. No fixture supplies an in-stock purchase claim,
verified seller, price, shipping or official contents. Replaying does not update
source retrieval/check times or make old evidence fresh. Saved E5a snapshot bytes,
hashes, goal versions, original observations and uncertainty remain unchanged.

## Reproduction and additive migration

Use unused disposable paths; do not use an owner installation:

```sh
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output NEW_SEED
uv run --no-sync python scripts/rehearse_e4a.py prepare --seed NEW_SEED --root NEW_COPY --output NEW_EVIDENCE
uv run --no-sync python scripts/rehearse_e4a.py exercise --root NEW_COPY --output NEW_EVIDENCE
# After the reserved one-second deadline passes, use a NEW process:
uv run --no-sync python scripts/rehearse_e4a.py recover --root NEW_COPY --output NEW_EVIDENCE
uv run --no-sync python scripts/serve_e4a.py --root NEW_COPY --output NEW_EVIDENCE
# Complete browser start/outcomes/review/stop/reopen, then verify:
uv run --no-sync python scripts/rehearse_e4a.py verify --root NEW_COPY --output NEW_EVIDENCE
```

Explicit migration for an already initialized synthetic local root:
`beta.cli --root DISPOSABLE_SYNTHETIC_COPY enable-replay-refresh`. The two additive
run/attempt tables are not automatically enabled in ordinary owner or hosted
state. SQLite copy migration, repeatability and empty-table schema rollback were
exercised. PostgreSQL execution is **unqualified**. Server helpers guard HTTP-client,
URL-opening and eBay acquisition and persist the acquisition counter across server
restarts. No credential, provider, recurring-job or deployment change is included.

Next bounded action: **E4b retained-offer stock/freshness/price filters and explicit
purchase-link eligibility**, tested on disposable offline state using this refresh
failure/observation distinction. Keep live acquisition unavailable. E4 live sources,
official contents, current purchasability, all-era coverage, separate-person review,
populated eBay, owner walkthrough and full beta acceptance remain open.
