# Failure handling and recovery

## First response

Keep the current data and inspect the saved result before repeating an action whose
response was lost. A failed response can follow a committed collection operation,
submitted provider request or accepted notification. Do not reset attempts, spending
reservations, revocations or operation IDs to repair an uncertain outcome.

| Situation | Recovery |
| --- | --- |
| Collection changed during editing | Reload current data and create a new preview. Confirmation never silently refreshes a stale preview. |
| Confirmation response was lost | Check the existing operation or saved batch result. Reuse its identity; do not create another addition. |
| Provider request failed or was stopped | Retain consumed attempts/reservations. Manual entry remains available; retry only through an explicit supported action. |
| Image or guide is unavailable | Keep identity and ownership unchanged. Missing prices remain unavailable; unknown shipping is not free shipping. |
| Sign-in or account access changed | Sign in normally. Reauthorize before restoring private screen state. |
| Storage or cleanup failed | Check permissions, free space and diagnostics. Preserve the latest database and independent journals before recovery. |

[Operations](operations.md) covers compatible runtimes, backup exclusions and independent
records. Ordinary JSON/CSV exports do not restore the complete application state.

## Diagnostics

The authenticated app, original app and operators emit errors through the `dex.failures`
Python logger to standard error. Records contain a fixed event, exception class and
traceback code locations: file basename, line and function. They omit exception messages,
source lines, locals, exception chains, URLs, payloads, SQL, photos and subprocess output.
Keep standard error when diagnosing a fault. There is no persistent log store, rotation
or alerting service; repeated failures produce repeated records.

| Event | Meaning |
| --- | --- |
| `worker_iteration_failed` | Cleanup, claim, connection or persistence failed. The worker waits and continues without requeuing a claimed provider call. |
| `recognition_failed` | Provider, parsing or matching failed. A fixed job error is saved if the result transaction succeeds. |
| `request_failed` | An unexpected view exception reached Django; expected authorization and not-found exceptions are excluded. |
| `codex_usage_write_failed` | Attempt accounting failed after submission may have occurred. Inspect storage before retrying. |
| `health_check_failed` | Staging readiness could not be evaluated; the response is a content-free HTTP 503. |
| `ebay_configuration_failed`, `hunt_guide_read_failed` | Configuration or retained guide data could not be read or validated. No provider acquisition follows from a readiness check. |
| `watcher_command_failed`, `local_operation_failed`, `staging_operation_failed` | An operator failed; inspect the exception class and code location. |
| `watcher_run_failed`, `watcher_failure_status_write_failed` | A watcher run failed/interrupted, or recording that outcome also failed. Existing observations and delivery may remain committed. |
| `watcher_database_close_failed`, `watcher_client_close_failed`, `legacy_ebay_client_close_failed` | Resource cleanup failed. Inspect committed state before replaying an otherwise successful action. |
| `legacy_request_failed`, `legacy_ebay_search_failed` | The original app returned a safe server/provider failure without private error text. |
| `shopping_search_failed`, `hunter_acquisition_failed`, `shopping_listing_failed`, `hunter_lot_detail_failed` | A background Shopping action failed. The temporary status remains safe; consumed/uncertain operations are not refunded or retried. Explicit Stop is not logged as an acquisition fault. |
| `shopping_dispatch_failed` | An unexpected transport, authorization or journal failure was converted to a safe uncertain provider result. Inspect this record for the original class and code locations. |
| `shopping_transport_close_failed`, `shopping_response_close_failed` | Closing a Shopping client or response failed or timed out. Cleanup preserves an existing acquisition error or cancellation; otherwise it fails the action. |
| `worker_shutdown_incomplete` | The local worker remained alive after its five-second join; this does not certify provider cancellation. |

Request/access logging is suppressed because URLs can contain bearer setup links.
Diagnostics do not observe every failure inside third-party middleware. Debug mode is
disabled. The original FastAPI app returns fixed validation/provider/server errors
without echoing submitted fields. Operator commands expose only their fixed input
instructions; unexpected errors produce safe output and a nonzero exit. Argument-parser
errors and Ctrl-C retain their normal behavior.

## Recognition, accounting and storage

Recognition configuration rejects unknown fields/providers, non-boolean enablement and
invalid or non-finite limits. API spending ceilings are bounded at $1 per root and $0.50
per account. Local omitted fields use manual defaults; staging requires a complete
configuration. Provider selection is explicit, with no automatic CLI/API switching.

Job claims and completion writes occur in separate transactions around provider I/O.
A completion write can fail after submission, leaving a durable `processing` job.
After 120 seconds a worker iteration marks a stale claim failed; another attempt requires
an explicit action. At most two provider attempts are allowed per single-card job.
Reservations survive failed or uncertain API outcomes. CLI subscription attempts remain
separate from API dollars; usage records do not establish billing or remaining capacity.

CLI usage records are flushed and synced before successful return. If accounting fails,
the job reports the uncertain outcome; a prior recognition error remains primary. Keep a
partial usage-log line as incomplete rather than completed accounting. The CLI lock closes
on ordinary exit. Cancellation/deadline handling terminates the process group and removes
temporary images, but cannot recall transmitted images. An API request can outlast the
local server's five-second worker join. Manual matching remains available.

Photo batches also retain independent consumed attempts and deletion tombstones;
[photo-batch recovery](operations.md#photo-batch-recovery) describes restore requirements.
Invalid images fail validation, including decompression warnings. CLI progress text is
not a result: a completion event and schema-valid final output are required.

## Watcher durability and cleanup

The watcher closes its database even when creating a run record fails. Later failures
attempt to persist `FAILED`; process-level interruption attempts `INTERRUPTED`. A failure
to record the outcome is logged without replacing the original error. SIGKILL or power
loss can leave `RUNNING`, which does not prove an active process or success.

Observations and digest delivery use separate transactions. Failure does not erase
committed observations or pending delivery. An endpoint may accept a notification before
its response is lost. Preserve the pending record, current-listing recheck and idempotency
key; exactly-once external delivery depends on the receiver honoring that key.

Cleanup errors are logged separately. They propagate when no earlier error exists, so a
command may exit unsuccessfully even though its database operation committed. Inspect
durable state before replaying it. Removing the macOS schedule file does not confirm an
in-flight watcher has stopped. File replacement is atomic per file, not a cross-file
transaction or a guarantee against power loss.

## Provider retries and unavailable data

The original app/watcher eBay client bounds transport, HTTP 429 and server-error retries
and permits one authentication refresh. Shopping discovery and listing checks use their
own finite transport with no retry, redirect or reauthentication. Search coverage remains
bounded and warnings stay visible. Invalid OAuth tokens or lifetimes fail before caching.

Deleted, expired or unauthorized photos are omitted from catalog review. Import previews
report row errors before confirmation. Optional display metadata and missing images never
create ownership. Frontend failures remain visible with recovery actions and retained
input where supported.

## Shopping cancellation and cleanup

Discovery, listing checks, Hunter and selected lot details share redacted async
cleanup. Client and response closing use a 0.5-second timeout. This relies on
cooperative cancellation in the async transport; it is not process termination or
proof that the provider did not receive a request. When acquisition and cleanup
both fail, the acquisition error remains primary and cleanup has its own diagnostic.
A cleanup failure after a successful response fails the action without replaying it.
Listing worker errors use fixed text rather than arbitrary `ValueError` messages.

A cancelled in-flight dispatch records `uncertain` with `cancelled_in_flight`;
explicit Stop records `stopped_in_flight`. Admissions remain consumed. Late task
outcomes are retrieved after the bounded 0.25-second cancellation wait so asyncio
does not print private transport exceptions. Their result is deliberately discarded
because the action has already recorded an uncertain outcome; no late result is
published and no retry follows. Keep the journal and diagnostics together when
investigating. A failed journal write can leave only the earlier admitted/in-flight
record: that is incomplete accounting, never evidence of unused capacity.

## Maintenance review boundary

The October 17, 2026 source pass surveyed exception/suppression patterns across
application Python, browser clients and operator/CI scripts, then traced Shopping
workers, transport ownership, journals and cancellation. It also checked existing
request boundaries, recognition worker recovery, watcher durability, source/usage
fail-closed behavior, image validation and logging configuration. Existing broad
catches that erase temporary data and re-raise, deliberate unavailable-image or
price fallbacks, authorization revocation, safe CLI boundaries, and content-free
request logging remain intentional. Decompression warnings remain validation errors.
No global warning suppression or new debug-mode fallback was added.

The implemented changes are source maintenance against Git baseline
`d144265df0eb132d836186a2441c23d9096d2d0b`, alongside preserved pre-existing
snapshot scripts/tests and documentation edits. Focused tests use temporary state
and fake transports. This pass does not qualify or replace the installed wheel,
observe customer journeys, enable deferred recognition/acquisition work, or establish
owner acceptance. Retain the tracker-recorded installed identity until a separately
qualified compatible update is delivered. Persistent log retention/alerting and
unobserved installed cancellation journeys remain separate follow-up work.
