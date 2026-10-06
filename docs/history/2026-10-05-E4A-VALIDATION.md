# E4a validation — October 5, 2026

**Local synthetic replay engineering qualified.** Live-source acceptance remains
open. Implementation and reproduction are in [E4a](../E4A.md).

## Exact baseline and candidate

Requested historical HEAD: `c106b33d6f22df8841e0fea5b0053c54864781c3`.
Observed clean HEAD: `16766b5c160c0bac370c1177387662646bf51b42`.
The intervening FastAPI/Ruff dependency commits and E5a commit were preserved.
E5a candidate SHA-256 matched
`d82d794866b42457d75507d89200e5a4b4535a298c8880094ddb2a7841e1d550`;
482 of 483 files matched. The sole inherited mismatch was `uv.lock`, accounted
for by the dependency commits. No reset, commit, push or release occurred.

New candidate: `evidence/e4a-20261005/validation-final/candidate.json` and its
SHA-256 companion. It binds current source, documentation, inherited packages and
historical evidence plus new test/browser/rehearsal outputs and Desktop handoff.
The baseline identity report records the before-work drift explicitly.

## Engineering qualification

Seven focused tests pass: explicit review/publication; repeated playback with
fixed original checked times; duplicate delivery; no observation overwrites;
partial success; independent denied, malformed and identity-mismatched failures;
explicit unknown-stock observation; timeout; cancellation; no retry; consumed
attempt preservation; expired recovery; fresh connection persistence; account and
second-owner isolation; cached-principal revocation; POST/CSRF; owner-mode
unavailability; unsupported relationships; additive repeat migration. Two actual
concurrent database claims produced exactly one executor.

Full suite: **475 passed**, local Python 3.14. One inherited Starlette/httpx
warning. Locked dependency sync, source compilation, all six JavaScript syntax
checks, Ruff lint/format and Git whitespace checks passed. No hosted CI, Python
3.12 or PostgreSQL execution claimed. Logs are under `evidence/e4a-20261005/`.

The initial focused run retained two failures: repeated publication attempted to
verify an already-published import, and a test imported a scripts-only helper.
The bounded repair reuses the existing published review state and uses a local
SQLite dump for repeat-migration comparison. Focused and full checks were rerun.
The concurrency/isolation regression was then added; final focused/full results
qualify the final test set. No existing publication rule was weakened.

## Copied state, migration, restart and preservation

Fresh seed: `/private/tmp/dex-e4a-20261005-seed`.
Fresh copied root: `/private/tmp/dex-e4a-20261005-copy`.
Existing E3a/E5a setup publishes inherited reviewed data, freezes version 2
research and then records the preservation boundary. Additive refresh migration,
repeatability, empty-table schema rollback and reapplication preserve every prior
row/photo byte. PostgreSQL execution remains unqualified.

The exercise process exited with a running, reserved slow attempt (1/2 consumed).
A later new process terminalized it as interrupted/stopped after deadline;
consumed count stayed 1, the remaining source was cancelled and execute could not
retry that run. `interrupted-before-process-exit.json` and
`restart-recovery.json` retain exact run/attempt evidence. This supplements browser
server restart/reopening, rather than inferring crash recovery from normal Stop.

All-table comparison passed. Existing owned copies, frozen goals, hunts, scans,
reservations, binders, photos/photo bytes, mappings, bridges and saved research
rows are identical. All three original Target observations remain byte-identical.
Only a new synthetic source/observation, sealed import and three catalog audit
rows were appended through explicit reviewed publication; 7 runs and 14 attempts
were added. Authentication last-login, sessions, three auth logs and only their
SQLite sequence counters are separately classified. Reports and complete synthetic
before/after rows are in `rehearsal/{before,after,preservation,refresh-migration}.json`.
No owner installation was accessed or operated.

## Ordinary local browser walkthrough

Actual authenticated browser evidence is in `evidence/e4a-20261005/browser/`:

1. Start success+denied replay. Observe completed candidate and independently
   retained denied failure, 2/2 consumed and failed final run.
2. Inspect historical synthetic provenance, explicitly preview, verify and publish
   the valid candidate. The source failure remains visible and supplies no observation.
3. Start success+slow with a fixed 30-second timeout. Stop while slow is active;
   completed success remains, slow is cancelled, 2/2 consumed is retained.
4. Explicitly start success again. The same observation ID and January 1, 2020
   checked time appear; preview reuses its published review with no new stock check.
5. Reopen the E5a research saved before replay. Original Target timestamps and
   scope remain; no synthetic observation substitutes into that frozen snapshot.
6. Stop/restart only the synthetic server. Reopen that research and all durable
   completed/stopped/failed histories, with original checked times and attempt counts.
7. Sign in as synthetic-member: no controls/history or owner's saved research.
   Remove the synthetic marker temporarily on this disposable copy, sign in as
   admin and verify ordinary owner mode shows only live-refresh unavailability;
   restore the marker. Authorization/CSRF and cross-owner mutations are also tested.

DOM captures, screenshots and console output are retained. Browser error/warning
log is empty. Application acquisition calls: **zero**, retained across both server
starts; rehearsal actions also record zero. Acquisition guards cover HTTP-client
sends, eBay search and URL opening. No live adapter exists. Saved browsing/filtering
makes no acquisition request. Browser testing used only loopback synthetic state.
The initial browser open preceded server startup and returned connection refused;
a fresh tab to the running server succeeded. The first server interruption emitted
ASGI cancellation diagnostics for shutdown; persisted application state and the
new-process reopen/preservation checks passed. No security or port guard was bypassed.

## Limits and next action

Only replay lifecycle engineering is qualified. E4 live acquisition, official
contents, seller/shipping/current purchasability, all-era coverage, separate-person
review, populated eBay, owner acceptance and full beta remain open. No live source
read, discovery, credential/provider change, recurring job, purchase, bid, hosting
or deployment occurred. Earlier acquisition budgets remain closed.

Next bounded action: **E4b retained-offer stock/freshness/price filters and explicit
purchase-link eligibility**, using offline retained data and failure/observation
semantics now established by E4a. Keep live acquisition unavailable.
