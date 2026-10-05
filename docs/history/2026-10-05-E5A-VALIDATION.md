# E5a validation — October 5, 2026

**Local synthetic engineering qualified.** Account-local saved Packs research
supports explicit save, list, reopen, editable name and selected removal. This
record qualifies the retained-data portion of E5, not live stock or full beta.

## Identity and inherited preservation

Observed HEAD: `c106b33d6f22df8841e0fea5b0053c54864781c3`.
Before implementation, D5b candidate
`evidence/d5b-20261004/validation-final/candidate.json` SHA-256
`8de0a936ba20906f5dbee71d4e41583f30b413eddb7da9a500aa0be15239f78c`
and all 378 files matched. Inherited PM/roadmap/history changes and untracked
D3/D4a, D5a and D5b packages/docs were preserved. Earlier manifests remain intact.
No owner-root access, acquisition, credentials, provider activation or deployment.

Final candidate: `evidence/e5a-20261005/validation-final/candidate.json` and its
SHA-256 companion. The manifest binds the working code, documents, retained
packages, original evidence and this slice's validation artifacts. HEAD remains
the baseline; no commit, push or release is implied.

## Storage, migration and preserved state

Fresh seed: `/private/tmp/dex-e5a-20261005-seed`.
Initial copy: `/private/tmp/dex-e5a-20261005-copy`.
Final fresh copy: `/private/tmp/dex-e5a-20261005-copy-repair1`.
The copies reconstruct prior reviewed sealed data and D5a erratum through existing
preview → verify → publish services before recording the preservation boundary.

Additive `saved_pack_research` migration, repeat migration, empty-table schema
rollback and reapplication passed on SQLite, with every existing row and photo
byte unchanged. The DDL follows existing SQLite/PostgreSQL feature services;
PostgreSQL execution is not claimed. Explicit local migration is
`beta.cli ... enable-pack-research`; existing staging initialization includes it.
No migration was run against the owner installation.

Final before/after comparison covers **all tables**, not only a hand-selected
subset. Owned copies, frozen goals, existing hunts, scans/reservations, binders,
photos/bytes, catalog audits, imports, bridges, original source records and all
three immutable Target observations remain identical. Intentional differences:
`saved_pack_research` 0 → 2 final rows (whole goal and predecessor); `auth_user`
last-login bookkeeping, `django_session`, three `axes_accesslog` rows and only its
SQLite sequence counter. Temporary archived-product/missing-offer gap fixtures
were restored byte-for-byte before the final comparison.

See `evidence/e5a-20261005/rehearsal-repair1/{migration,before,after,preservation}.json`.
The earlier rehearsal and its failed comparison remain retained.

## Tests and required checks

- Four focused saved-research tests passed: persistence through fresh connections,
  immutable ownership/result context, changing/archived references, exact goal
  version and invalid scopes, cross-account save/list/reopen/rename/remove, CSRF,
  POST-only mutation, selected removal, rename escaping/integrity and migration.
- Full suite: **468 passed**, 149.35 seconds, Python 3.14 local environment. One
  existing Starlette/httpx deprecation warning. No hosted or Python 3.12 run claimed.
- Locked dependency sync, Python source compilation, all six JavaScript syntax
  checks, Ruff lint/format and Git diff whitespace checks passed.

Outputs: `evidence/e5a-20261005/{focused-tests,full-suite,sync,compile,lint-final,format-final,javascript-final,diff-check-final}.txt`.
Tests additionally guard HTTP calls. The ordinary server guards eBay search and
synchronous/asynchronous HTTP-client sends. Its before-restart and after-restart
reports both show zero acquisition calls; no background jobs/adapters were added.

## Actual ordinary browser evidence

Final successful captures and displayed-state assertions are in
`evidence/e5a-20261005/browser-repair1/`; first-run captures remain in `browser/`.
The local authenticated UI, not route tests, demonstrated:

1. Save whole-goal version 2 with 151 possible missing species; save Scyther
   species 123 with expansion filter `tcgdex:en:sv03.5`.
2. Find both in the private list and reopen each exact scope; rename Scyther while
   retaining its original result; default predecessor name includes version 1.
3. Display exact normal/reverse printing IDs, retained goal/catalog hashes, the
   unresolved reverse membership, unknown official quantities/inclusions, unknown
   seller/shipping and no current-stock claim.
4. Keep all three Target checked times:
   `2026-10-04T22:57:28.606483+00:00`,
   `2026-10-05T00:51:59.610643+00:00`, `2026-10-05T02:54:27+00:00`.
   The research saved date is separately labeled. No observation was refreshed.
5. Save/reopen predecessor version 1 with no modern booster match, despite the
   existing version 2; no successor substitution.
6. Stop the started server process, start a new process against the same copy,
   find all three items and reopen both version-2 scopes plus predecessor.
7. Temporarily archive the product and remove its offer on disposable state;
   reopen successfully with explicit product/offer reference gaps and retained
   observations/coverage; restore original reference bytes.
8. Sign in as synthetic-member: list is empty, admin's saved item returns 404.
   Cross-account save/remove/rename and CSRF are separately framework-tested.
9. Remove only Scyther through the ordinary UI; whole-goal and predecessor remain.

`assertions.json` contains exact item URLs and displayed requirements. Console
warning/error capture is empty. The successful browser tab was closed and the local
test server stopped after captures; synthetic copies/evidence were preserved.
The abandoned connection-error tab could not be rebound for explicit cleanup
because the browser blocked its generated data URL; it remains a temporary tab
for normal end-of-turn cleanup. No security policy was bypassed.

## Retained failures and bounded repair

The first browser open preceded server startup and returned connection refused;
a fresh binding to the running server succeeded. An attempted assignment to the
failed tab binding returned an undefined-binding error; selecting created tab 2
resolved it. No application change or credential exposure followed.

The first server restart was rejected by the helper's port bind while the prior
socket was closing; no active listener was present. After the port released,
restart passed without weakening the guard or stopping another process.

The first preservation helper rejected SQLite's authentication-log sequence
counter, alongside already allowed auth logs. A bounded helper repair explicitly
permits only the three auth-log table counters and asserts every other sequence
is identical. Qualification restarted from a fresh copy, repeated the full browser
walkthrough including process restart, and passed the complete preservation check.
This classified bookkeeping without relaxing protected application-row checks.

## Limits and one next action

Official contents/inclusions, current purchasability, seller/shipping, all-era
coverage, separate-person review, populated Production eBay, owner acceptance and
full beta acceptance remain open. Classic eBay routes and selected-goal links are
retained; no new populated-provider evidence is claimed. E4 refresh/live behavior
remains an open dependency for broader shopping.

Next bounded action: **E4a replay-only explicit bounded refresh orchestration**,
retaining immutable observations and per-source failures, with fresh synthetic
qualification and live acquisition disabled until supported access is separately
authorized.
