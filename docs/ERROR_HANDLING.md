# Failure handling and recovery

## Diagnostics

The authenticated app emits ERROR records through Python's `dex.failures` logger,
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

Django/axes request logging and access logging remain suppressed because URLs may
contain bearer setup links. The independent diagnostic channel restores view
failure visibility without recording those URLs. It does not observe every error
inside third-party middleware. No debug mode is enabled.

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
  API/page-cap warnings remain visible in saved coverage.
- The legacy watcher records failed runs and preserves pending digest delivery.
  Retry rechecks current listing evidence; external delivery can remain uncertain
  when an endpoint accepts a request but its response is lost.
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
qualification. Endpoint validation still uses the existing ValueError/TypeError
contract; migrating it to dedicated typed validation errors is a separate change.
