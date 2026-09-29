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
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q
```

The suite uses synthetic state and mocked providers. Browser rehearsals, live
provider calls, PostgreSQL staging, packaging and deployment remain separate.
Test failures are available in the job logs; no private app files are uploaded.
Dependabot proposes weekly uv and Actions updates for review; it does not merge
or deploy them.

For local changes, use the relevant test files rather than repeating both runtime
jobs. GitHub must run both jobs on the submitted commit to establish hosted
success. CI is not owner acceptance or release approval. At the September 28,
2026 inspection, `main` had no required status checks or active rulesets; changes
to that repository policy require separate authorization.
