# Proposed macOS performance qualification environment

Status: superseded by the owner's October 29 decision: Linux hosted CI plus
actual-Mac compatibility. The owner initially approved this dedicated-macOS-15
design, then selected Linux as the required hosted target after discovery found
no registered dedicated runner. The local Mac is macOS 27.0.1 arm64.

The current contract is in [CI](CI.md#required-local-mac-compatibility): complete
Ubuntu Python 3.12/3.13/3.14 coverage, existing container/security/distribution/
staging/browser/quality checks, plus complete installed Python 3.12/3.14 suites
on the actual Mac. All product budgets, samples and datasets remain unchanged.
No dedicated-runner provisioning or proposed frame-calibration requirement was
implemented. The historical proposal and evidence below remain for traceability.
CI-VERIFY remains open until fresh exact-candidate hosted and local gates pass.

## Controlled evidence

Candidate `2478922b62dd5511696886664c59d55d4358fd6b` completed focused run
[40949304876](https://github.com/dock108dev/dex/actions/runs/40949304876).
Both Linux and macOS diagnostic jobs retained all probes and budget reports.
Linux backend and navigation gates pass; interaction scheduling fails. macOS
retains picker/OPS SQL, navigation and interaction phase failures. Those failures
remain failures; this proposal does not excuse the SQL or Linux findings.

The macOS runner reports macOS 15.7.9/arm64, Python 3.14.10, SQLite 3.50.4 and
Chromium 156.0.8078.4. Graphics telemetry reports SwiftShader software rendering,
disabled GPU compositing and disabled multiple raster threads. Linux also uses
software rendering but has multiple raster threads enabled. These differences
are observations, not a complete causal explanation by themselves.

Within one browser session, three visible empty-document controls each captured
120 frame observations. Their frame-gap p95 values were 50.0, 33.4 and 83.4 ms;
the final control's worst gap was 133.3 ms. The first observation measures initial
callback scheduling rather than a complete frame-to-frame interval; excluding
that startup observation leaves the final control's p95/worst unchanged. The
successor diagnostic records 120 complete intervals instead. No acceptance
sample is excluded or normalized.

The empty document has no product layout, data rendering or backdrop effects.
A required 70 ms parse/DOM/paint phase cannot be reliably attributed to product
work when a visible empty document's next-frame delivery alone can exceed that
budget. Product guest-filter DOM-to-readiness p95 reached 116.4 ms in the repeated
arm while JSON parsing p95 was 0.9 ms. Removing backdrop effects did not produce
a consistent improvement across the A/B/A comparison and is not a product fix.
This establishes a measurement-environment limitation for frame-based timing;
it does not prove that every navigation, transfer or SQL miss has that cause.

Raw evidence is retained in the run's `diagnostic-only-macos-15-40949304876-1`
artifact and locally under `reports/ci-verify-20261029/repair8/hosted-after/`.
The complete local Python 3.12.15/SQLite 3.53.1 installed suite passed 3,619 tests
with zero failures/errors/skips. Its different OS/runtime is supporting evidence,
not a replacement for the required macOS 15 matrix.

## Concrete alternative for owner review

Use an approved, dedicated macOS 15 arm64 machine for the existing macOS behavior
matrix entries (Python 3.12 and 3.14), with exclusive execution during measurement.
No machine or paid capacity is assumed available; do not provision, purchase or
change workflow routing until the owner approves the environment and its use.
An isolated CI account must have no access to the customer installation or its
credentials. Use disposable engineering roots and the existing offline tests.

Retain the pinned dependency lock and Playwright/Chromium version, ordinary CLI
workers, complete datasets, all twenty samples, existing percentiles, complete
functional/renderer/security coverage and every current performance threshold.
Keep browser launch settings unchanged initially. Record graphics configuration,
OS/interpreter/SQLite/browser versions, visibility, CPU/load and frame controls.
Keep Linux, distribution, staging, security and container requirements intact.
The complete macOS behavior suite, including its existing timing assertions,
remains required; it is not replaced with a timing-only subset or local success.

Add a separately reported environment-validity gate before and after the suite:
360 complete visible empty-document frame intervals, proposed p95 at most 25 ms
and worst at most 50 ms. This is a proposed calibration requirement, not a
relaxation of a product limit. An invalid environment fails qualification; it must
never convert a failed product sample to a pass or justify rerunning unchanged
code until green. Retain every failed/invalid attempt and raw sample.

Native reports and aggregates must retain exact commit/tree, run/attempt, matrix
and package correspondence. The standard hosted macOS results can remain visible
as additional evidence, but changing which environment supplies the required
macOS performance result needs explicit approval. After any approved workflow
change, run fresh complete PR, full and compatibility qualification on one final
candidate. Do not combine old or diagnostic artifacts into that result.

If this proposal is not approved, preserve the current required environment and
continue investigating its scheduling behavior. Do not raise budgets, remove
paint, change percentiles, skip macOS timing or silently substitute another OS.
