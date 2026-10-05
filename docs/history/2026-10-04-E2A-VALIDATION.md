# October 4, 2026 — E2a local engineering validation

Eastern closeout date; execution timestamps use UTC. Baseline HEAD remains
`fba1be13135b0b3bbb6cb674de5586e0f3c80740`. No applicable repository/ancestor
AGENTS.md exists. Initial E1b manifest SHA-256
`01d35fcbf7cdc6c467df540149c7568cef309ef20c8e8202d95831a1d62610cd`
and all 34 files matched. Earlier changes were preserved. No owner installation,
owner database, credentials, reservations or evidence was read or modified.

Implementation is in the ordinary authenticated goal UI and existing services.
E2a acceptance is **partial**: ordinary browser evidence and unrestricted-runtime
checks are blocked below. Full E2 and beta are not complete.

## Candidate and data

Final manifest: `evidence/e2a-20261004/validation-final/candidate.json` with
`candidate.sha256`, `candidate.patch`, test logs and source hash snapshot. It covers
all changed/untracked deliverables, inherited E1/E1b files and the Desktop handoff.
The companion, rather than baseline HEAD alone, identifies the uncommitted tree.
It is frozen after documentation. Test source hashes are retained separately and
must equal the final implementation file hashes.

151 data SHA-256:
`250d0c61aea496d0854c831f62edb1030e1cd3acf91db59d239185528401a45f`.
Normalized service fingerprint:
`12ed07eb96fe8b3db79e33521028c12f19188ccb31eb0b17b97014644129ec34`.
Foundation package SHA-256:
`ec4c1f062ec822e44793de381390c626da4b8c59d0935879a52c5e6b74e85313`.
All real public input packages retain their previous bytes. No network acquisition,
provider activation, purchase, hosted change or commit occurred.

## Engineering checks

Final focused suite: **64 passed** (nine E2a checks plus filtered-goal, live-provider
mock and parity regressions). Final full local Python 3.14 suite: **455 passed,
three environment failures**, one existing Starlette/httpx warning. Compilation,
all browser-script syntax checks, repository Ruff lint/format and diff whitespace
checks passed. The final test-source snapshot has 130 files; every recorded
implementation hash still matches. Results are bound in the frozen manifest and
retained logs. Focused checks
cover fixed denominator/unavailable coverage, special/named/regional canonical
identity, Trainer/Energy/unresolved exclusions, evolved species, duplicates/exact
copies, account isolation, cancellation/idempotency/stale preview, explicit
successors and legacy conversion, catalog growth/removal, blocked destructive undo,
frozen saved-hunt scope, local reopening, archived-version recognition and
old-root/export/import compatibility. Compilation, all browser-script syntax,
repository lint/format and diff whitespace checks are required locally.

The full suite in this sandbox has three environment failures in
`test_codex_recognition.py::test_termination_and_cleanup[cancel|timeout|shutdown]`:
its existing `ps -o stat= -p ...` subprocess is denied with `Operation not permitted`.
These tests were not altered or skipped to manufacture a full pass. The existing
Starlette/httpx deprecation warning is retained. The final manifest records the
actual pass/fail counts; no hosted or PostgreSQL runtime result is implied.

`uv sync --locked --extra dev --offline` could not complete: the macOS
system-configuration runtime panics with `Attempted to create a NULL object` under
this restricted environment. Using a writable UV cache resolved its initial cache
permission error for `uv run --no-sync`; sync itself remains unqualified. No
network download or dependency modification was performed. Checks ran in the
existing local Python 3.14 environment. Re-run locked sync and blocked process checks
in the next bounded qualification runtime.

## Disposable copied-state evidence

Seed: `/private/tmp/dex-e2a-20261005-seed`.
Final copied root: `/private/tmp/dex-e2a-20261005-copied-qualified`.
Final rehearsal output: `/private/tmp/dex-e2a-20261005-evidence-qualified`.
Retained report/projection copies: `evidence/e2a-20261004/` in this checkout.

No E2a schema change was necessary. The existing catalog and sealed feature
migrations ran twice on a copy; pre-existing rows remained identical. The report
hashes all baseline tables. It preserves ownership, goals, photos, account/binder
rows, older hunts and reservation-bearing scan jobs; explicitly synthetic imports
add copies only to the second synthetic account. Existing owner-account synthetic
copies remain byte-for-byte unchanged. SQLite before/after backups remain in the
disposable evidence directory. Goal creation, cancelled update, fresh successor,
repeated confirmation, version reopening and remapped lineage import succeeded.
Both older vintage and broad hunts reopened with provider calls prohibited and
captured scope unchanged. A separate `file-preservation.json` comparison confirms all 12 pre-existing
non-runtime-database files (including synthetic photos, credentials, secrets and
evidence) retain their seed bytes. Before/after SQLite backups are also copied into
the ignored local evidence directory. Current coverage recognizes 823 printings / 151 species;
resolved account completion is 0/151, with no research-seed import.

An initial rehearsal passed behavior/preservation assertions and then failed while
serializing a datetime in evidence hashing. Reporting was corrected; subsequent
rehearsals used fresh copies. Initial failing directories were retained. Focused
fixture-development errors were corrected before the recorded final runs.

## Ordinary browser and acceptance blocker

The computer-use permission review rejected opening
`http://127.0.0.1:8012/goals/`, reporting that permission was declined. No alternate
browser, indirect navigation or screenshot substitute was attempted. A separate
loopback server start then failed binding `127.0.0.1:8012` with `Operation not
permitted` under this sandbox. The server exited; no owner server was restarted.
An access question was presented while independent engineering continued.

No synthetic browser captures or successful ordinary browser walkthrough exist.
[The closeout](../E2A.md) gives the exact disposable-server command and pending
walkthrough. Authenticated route/service tests and JavaScript syntax qualify local
engineering; they cannot substitute for this acceptance gate. Owner acceptance,
full all-era coverage, official contents, 177 membership gaps, independent Scyther
review, live eBay/retailer evidence, hosting and beta acceptance remain open.

The requested `/Users/michaelfuscoletti/Desktop/dex_next_steps.md` write was
denied with `Operation not permitted`. Its complete proposed replacement is saved
as `docs/E2A_NEXT_STEPS.md`. The Desktop original retains its initial hash; both
files are listed in the final manifest. No filesystem workaround was attempted.
