# October 4, 2026 — E2a runtime qualification, browser gate open

E2a acceptance remains **partial**. Locked synchronization, process cleanup and
required repository checks now pass. Renewed browser permission was requested but
no answer was received during this run. The prior declined navigation to
`http://127.0.0.1:8012/goals/` was respected: no browser navigation, alternate
channel, disposable server start or UI capture occurred. No owner acceptance exists.
Full E2 and beta remain open. No implementation repair or commit was made.

## Candidate and runtime

Baseline HEAD: `fba1be13135b0b3bbb6cb674de5586e0f3c80740`.
Original manifest SHA-256:
`9d7804a99fe6c69fc65b9b7884a79443c2f7f660c4a4dffa91b45299b0b7afb9`.
All 44 repository files matched, and all listed historical evidence matched.
The sole intentional overlay was `/Users/michaelfuscoletti/Desktop/dex_next_steps.md`,
SHA-256 `3989844e701dbc175f1f649ed3cc6c3f483346ef9ab21a8dda3a377a39837a9e`.
Original manifest and evidence remain unchanged. No applicable repository or
ancestor AGENTS.md exists. All inherited E1/E1b/E2a changes were preserved.

Runtime: macOS 27.0.1, Darwin 27.0.0, arm64; Python 3.14.0; uv 0.9.10
(`44f5a14f4`). Execution uses unrestricted local filesystem/process permissions.
This is local synthetic engineering evidence, not hosted/Ubuntu/PostgreSQL evidence.

## Commands and actual results

All uv commands used `UV_CACHE_DIR=/private/tmp/dex-e2a-uv`.

- `uv sync --locked --extra dev`: exit 0; resolved 33, audited 31 packages.
  Lockfile bytes are unchanged. Subsequent checks used this synchronized environment.
- `uv run --no-sync pytest -q tests/test_codex_recognition.py::test_termination_and_cleanup`:
  **3 passed in 1.64 seconds**, cancel/timeout/shutdown. Existing assertions execute
  temporary-directory removal, parent-process absence, child-process inspection
  through `ps`, duration and terminal outcome. No test or cleanup code was changed.
- `uv run --no-sync pytest -q`: **458 passed, 1 warning in 140.84 seconds**.
  The existing Starlette/httpx deprecation warning remains; no dependency change
  was made to suppress it.
- `uv run --no-sync python -m compileall -q src`: exit 0.
- `node --check` for every `src/pokemon_hunter/beta/static/*.js` and `web/*.js`: exit 0.
- `uv run --no-sync ruff check .`: exit 0, all checks passed.
- `uv run --no-sync ruff format --check .`: exit 0, 153 files formatted.
- `git diff --check`: exit 0.

Logs, runtime/baseline report and test-source SHA-256 snapshot are retained in
`evidence/e2a-qualification-20261004/`. All snapshot hashes matched after checks.
The final candidate is frozen after closeout at that directory's
`validation-final/candidate.json`, with SHA-256 companion and patch. It records
this documentation overlay and zero implementation repairs.

## Synthetic state and preservation

The requested `/private/tmp/dex-e2a-20261005-copied-qualified` has its explicit
synthetic marker. Its database rows matched the historical rehearsal's
`after.sqlite3` in every table, and all 12 seed non-runtime-database files matched
byte for byte. Its pre-UI backup is retained as `before-ui.sqlite3`; after this run
all tables remain unchanged. There are zero walkthrough additions.
No credentials, tokens or secrets were included in captures, prompts or logs.
The owner installation was neither read nor changed.

A fresh independent rehearsal used:

```sh
uv run --no-sync python scripts/rehearse_e2a.py --seed /private/tmp/dex-e2a-20261005-seed --root /private/tmp/dex-e2a-qualification-20261004-runtime-copy --output /private/tmp/dex-e2a-qualification-20261004-runtime-evidence
```

Exit 0. Before/after databases, exact first-goal projection and preservation report
are retained there and copied under `runtime-*` evidence filenames. Assertions
establish repeated migration preservation, retained legacy goals/copies/hunts and
reservation-bearing scan rows, cancelled preview without goal writes, idempotent
confirmation, version reopening and remapped imported lineage. Expected additions
are reviewed catalog publications, two broad versions and sample hunts for the
synthetic admin, plus explicitly synthetic imported copies/goals in the second
account. Admin ownership and every protected pre-existing row remain preserved.
Old and new hunt scopes remain identical after successor creation/reopening with
live provider acquisition patched to raise; provider calls are zero. These are
service assertions, not ordinary browser assertions.

## Remaining gate and next action

No ordinary-browser displayed-state assertions, spoiler/reveal/filter captures,
creation/progress/cancel/successor/reopened-version captures or browser error log
can be claimed. Browser permission remains pending; localhost server binding was
not re-tested because the requested server sequence depends on that permission.
No disposable server was started, so none required stopping. Roots and evidence
remain available for reproduction.

**Next bounded action: finish the ordinary E2a synthetic browser qualification**
after renewed explicit permission. Reverify the new manifest and synthetic root,
then use the exact loopback command and walkthrough in `docs/E2A.md`, including
both versions' sample hunts, zero-call reopening/filtering, spoiler reset/reveal
and protected-row comparisons. Any observed source repair needs fresh hashes,
affected checks and a fresh walkthrough boundary. Runtime gates need repetition
only after a relevant environment/source change. Do not advance acceptance or
start pack discovery before the remaining dependent gate passes.

Full all-era coverage, official product contents, 177 variant-membership gaps,
independent Scyther review, current purchasable offers, populated Production eBay,
owner acceptance, full E2 and beta completion remain explicitly open. No acquisition,
provider credentials/activation, ownership action, purchases, hosting or recurring
jobs occurred.
