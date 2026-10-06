# Pull-request checks

The `Tests` workflow runs on every pull request and pushes to `main`, with stable
job names `test (3.12)` and `test (3.14)`. Both run on Ubuntu with read-only repository
permissions and no application credentials. Superseded runs are cancelled and
each job has a ten-minute limit.

CI pins action revisions and uv 0.9.10. It caches uv downloads against `uv.lock`,
then always synchronizes the environment with `--locked`; stale lockfiles fail
instead of being updated. Later commands use that environment without resyncing:

```sh
uv sync --locked --extra dev
uv run --no-sync python -m compileall -q src
for script in src/pokemon_hunter/beta/static/*.js web/*.js; do
  node --check "$script"
done
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q
```

The JavaScript check uses the Ubuntu runner’s preinstalled Node.js; the
browser scripts have no npm dependencies or separate frontend build. Named steps
make syntax, lint, formatting and test failures easy to identify without changing
the matrix check names.

The suite uses synthetic state and mocked providers. Browser rehearsals, live
provider calls, PostgreSQL staging, packaging and deployment remain separate.
Test failures are available in the job logs; no private app files are uploaded.
Dependabot proposes weekly uv and Actions updates for review; it does not merge
or deploy them.

For local changes, use the relevant test files rather than repeating both runtime
jobs. GitHub must run both jobs on the submitted commit to establish hosted
success. Hosted results qualify their submitted commit, not later working-tree
changes. GitHub-managed CodeQL configuration and repository protection settings
are external to this workflow; dated observations belong in
[verification history](history/2026-10-03-VERIFICATION.md).

## Validation boundaries

Synthetic tests cover imports, conflicts, account isolation, goal versions,
canonical species, distribution/promo separation, dated/unknown offers and
no-call saved reopening. They do not establish catalog completeness, provider
access, seller availability, recognition accuracy or deployment acceptance.

## Portable test and runtime inputs

Ordinary CI uses `tests/fixtures/synthetic-collection.csv`, a generated 251-species
ledger with artificial ownership and card-detail cases. Its counts exercise the
existing goal, import, privacy and frozen-save regressions; it contains no personal
inventory. Tests never need `outputs/`.
Source-reconciliation tests model source receipts and publication references in
memory, fail on unmodeled private reads and retain hash-drift/conflict assertions.
Printing-bridge tests use the public reviewed package instead of private rejection
receipts. Historical operational evidence remains separate from these unit tests.

The current coverage profile packages its reviewed universe and alias review under
`config/catalog-pipeline/m4-20261006/`, preserving their exact hashes and source
timestamps. Runtime and tests no longer require ignored `evidence/` files for these
inputs. These public inputs must accompany source changes in the submitted commit;
GitHub cannot use files that exist only in a local working tree.
