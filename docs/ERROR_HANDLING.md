# Failure handling and recovery

## Diagnostics

The authenticated app, original app and operators emit ERROR records through Python's `dex.failures` logger,
which reaches the server/worker's standard error under the supplied configuration.
Each record contains a fixed event, exception class and traceback code locations
(file basename, line and function). It omits exception messages, source lines,
locals, exception chains, URLs, request payloads, SQL, photos and subprocess output.
Keep the server's standard error when investigating failures; there is no new
persistent log store or alerting service. Repeated failures emit repeated records.

| Event | Meaning and response |
| --- | --- |
| `worker_iteration_failed` | Cleanup, claim, connection or persistence failed. Check local storage/permissions and the indicated code location. The worker waits two seconds and continues; this does not requeue a claimed provider call. Emitted in local and staging modes. |
| `recognition_failed` | Unexpected provider, parsing or matching failure. The job receives a fixed failed message if the result transaction succeeds. Manual selection remains available. |
| `request_failed` | An unexpected view exception reached Django. Django retains its normal error status/response. Expected authorization and not-found exceptions are excluded. |
| `codex_usage_write_failed` | CLI attempt accounting could not be written/flushed/synced. Submission or recognition may already have completed. Check storage before retrying; manual selection avoids another provider call. |
| `health_check_failed` | Staging readiness could not be evaluated. The response remains content-free HTTP 503; investigate the corresponding exception class/location. |
| `ebay_configuration_failed`, `ebay_search_failed`, `ebay_response_failed` | Local settings, provider I/O or listing projection failed. Searches fail explicitly without saving a successful snapshot or substituting samples. OAuth/Browse HTTP errors expose only stage, status and allowlisted OAuth codes. |
| `ebay_client_close_failed`, `legacy_ebay_client_close_failed` | Closing the owned provider client failed. An active search error remains primary; after an otherwise successful search, cleanup failure prevents snapshot saving. |
| `hunt_guide_read_failed` | The refreshed guide file could not be read or parsed. Retained dated evidence may still be used under the normal matching/age rules; missing coverage remains unavailable. |
| `watcher_command_failed`, `local_operation_failed`, `staging_operation_failed` | An operator command failed. Use class/location to identify configuration, storage or integration failures. Ordinary output does not echo arbitrary exception messages, paths, SQL, credentials or submitted values. |
| `watcher_run_failed` | A watcher run failed or was interrupted. Earlier observations or external delivery may already have occurred; inspect the durable run and digest state before retrying. |
| `watcher_failure_status_write_failed` | Recording the failed/interrupted run also failed. The original failure propagates. A durable `RUNNING` row is incomplete/unknown, not evidence of an active process or success. |
| `watcher_database_close_failed`, `watcher_client_close_failed` | Watcher cleanup failed. Active failures and interruptions remain primary; cleanup errors otherwise propagate as command failures. A previously committed run/digest status is not rolled back by a later close failure. |
| `legacy_request_failed`, `legacy_ebay_search_failed` | The original app encountered an unexpected server failure (HTTP 500) or a typed eBay failure (HTTP 502). Responses and diagnostic records omit private error text. |
| `worker_shutdown_incomplete` | The local worker remained alive after the five-second shutdown join. An optional API call can outlast that bound; check the job's durable state on reopening. This event does not certify provider cancellation. |

Django/axes request logging and access logging remain suppressed because URLs may
contain bearer setup links. The independent diagnostic channel restores view
failure visibility without recording those URLs. It does not observe every error
inside third-party middleware. No debug mode is enabled.

The original FastAPI app handles unexpected view failures at its request middleware
boundary, returning a safe 500 with browser security headers before the exception
can reach the ASGI server's ordinary traceback logging. Invalid request fields
return a fixed 422 without FastAPI's default echo of submitted values. Only the
dedicated ownership-input error type is exposed as a 400; corrupt stored JSON or
unexpected code failures remain server errors. Typed eBay failures return a fixed
502; unrelated runtime errors remain 500. Late streaming or third-party server
failures are outside this view boundary.

The legacy watcher CLI prints fixed input-validation instructions only for its
dedicated CLI input type; all other failures produce a fixed message plus redacted
diagnostics and a nonzero exit. The local beta operator has the same safe terminal
boundary. Argument-parser usage errors and intentional Ctrl-C/SystemExit behavior
remain standard. The local server does not automatically reload source changes; restart it to apply updates.

## Watcher durability and cleanup

The watcher closes its database even if creating the run record fails. If a later
error occurs, it attempts to persist `FAILED`; a propagated KeyboardInterrupt or
other process-level interruption attempts `INTERRUPTED`. If that write fails, the
original error remains primary and the secondary storage failure is logged.
Neither bookkeeping nor cleanup errors can replace an active failure. SIGKILL,
power loss and process termination before bookkeeping can still leave `RUNNING`.

Observations and digest delivery use separate existing transactions. A failed run
does not erase already committed observations or pending digest evidence. An
external notification may have been accepted before a lost response or failed
delivery-status write. There is no automatic assurance of exactly-once external
delivery: inspect the retained digest and use the existing idempotency key and
current-listing recheck. Do not mark uncertain delivery successful or discard its
pending record as part of recovery.

Owned database/provider resources close on ordinary failures and interruptions.
A close error is logged separately; when work otherwise succeeded, it propagates
instead of reporting an unqualified success. Already committed database state may
therefore show completion even though the command exits unsuccessfully during
cleanup. Inspect durable state before replaying the operation.

## Recognition, accounting and storage

Local and staging scan configuration rejects non-object configuration, unknown
providers, non-boolean enablement, and invalid/non-finite spending limits. Global
and per-user limits remain bounded at $1 and $0.50. Invalid configuration stops
processing before the job is claimed or spending is reserved. Local omitted fields
retain the documented manual defaults; staging requires all four fields.

Provider selection is explicit: no automatic CLI/API switching. API reservations
are retained after uncertain outcomes. CLI subscription attempts remain separate
from API dollars. At most two explicit attempts per job remain allowed.

CLI usage records are flushed and synced before a successful recognition return.
If accounting fails after otherwise successful recognition, the job fails with a
safe message explaining the uncertain submission outcome. If recognition already
failed, that original error is preserved and the accounting failure is separately
logged. The CLI lock closes in either case. A partial usage-log line can remain
after a write failure; retain it as incomplete evidence, not a completed attempt.
These records do not establish provider billing or remaining subscription capacity.

Job claims and completion writes use separate transactions around provider I/O.
A failed completion write propagates to the worker; the durable job can remain
`processing` even if a provider call completed. After 120 seconds, a subsequent
worker iteration marks stale claims failed and requires an explicit retry. Do not
reset attempts, reservations, or copy state to repair a failure. Check the saved
job/operation before retrying a mutation whose response was lost. Confirmation
and undo retain the existing idempotency and conflict checks.

CLI cancellation/deadline handling still terminates the process group and removes
temporary images. Manual entry remains available on provider failure. The separate
API adapter retains its existing HTTP timeout behavior; instantaneous cancellation
of an in-flight API request is not promised.

## Deliberate resilience retained

- Missing, stale or invalid prices remain unavailable, with partial valuation
  coverage; unknown shipping is never converted to free shipping.
- eBay transport/429/server retries remain bounded; auth refresh is attempted once.
  API/page-cap warnings remain visible in saved coverage. OAuth responses require
  a nonempty string token and a positive integer lifetime; invalid responses fail
  before either field is cached, including during a 401 refresh.
- The legacy watcher records failed runs and preserves pending digest delivery.
  Retry rechecks current listing evidence; external delivery can remain uncertain
  when an endpoint accepts a request but its response is lost.
- The optional legacy LaunchAgent scheduler tolerates an unloaded agent's bootout
  failure, but reports the nonzero exit without printing subprocess output.
  Removing a schedule file explicitly does not confirm an in-flight watcher has
  stopped. Managed startup for the current authenticated app remains deferred.
- Catalog review may omit photos that were deleted, expired or are no longer
  authorized. Import previews collect row errors before any confirmation.
- Invalid images fail validation; decompression warnings are promoted to errors.
  CLI non-JSON progress lines are ignored, but a completion event and validated
  final result are still required.
- Frontend failures remain visible in the existing status surfaces. Optional
  display metadata fallbacks do not create ownership records.

## Operational limitations

Remaining limitations: diagnostics have no rotation/alerting service; repeated
worker faults can generate recurring stderr output. Local graceful shutdown still
has a five-second worker join, while the optional API request can outlast it;
interrupted claims rely on the existing stale-claim recovery. Legacy file writes
use replacement but do not provide a cross-file transaction or power-loss
qualification. Authenticated beta endpoint validation still uses the existing ValueError/TypeError
contract; migrating it to dedicated typed validation errors is a separate change.
