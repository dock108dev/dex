# Dated verification references: October 3, 2026

These observations apply only to the candidates and installation examined.
They are not setup prerequisites or current qualification of later source.
Existing archived records remain unchanged.

## Provider observations

Production candidate `dbaafee7283c9fb81de664738084c69061b16254` received OAuth
HTTP 401 (`invalid_client`) on the initial submission and one retry. No Browse
results were available. Repaired application source was
`17306fee355091bed082527bee02a01e26cf4f01`; its regression run passed 328 tests.

With that unchanged application source and documentation base `4360ac1`, one
explicit Sandbox batch authenticated and completed Browse with zero raw and zero
filtered listings. The empty snapshot was saved and reopened. This did not exercise
populated comparisons, reveal or seller review, or qualify Production access.

A later developer-portal observation on audit base
`ca4dde5baa18fa05f7c0a48bd9e175886ba628ac` found the examined Production keyset
disabled for account-deletion compliance, with no configured endpoint/token and
exemption off. This is a dated observation, not the default state of this repository
or a proven cause of the earlier authentication failure. Private sanitized evidence
remains outside Git; no collection or credentials are included in these records.

## Hosted baseline

Both Python Tests jobs and GitHub-managed CodeQL checks passed on
`13fa6dc5e8c1cccb3704d5d3c0e96633299a9ade`:
[Tests run](https://github.com/dock108dev/dex/actions/runs/37128759135).
CodeQL default setup covered Python and Actions with weekly scheduling and check
names `Analyze (actions)` and `Analyze (python)`. Read-only inspection found no
required branch checks or active rulesets. These external settings may change.
Later uncommitted maintenance has focused local evidence, not a fresh hosted matrix,
provider qualification, device acceptance or release approval.

## Evidence locations and presentation observations

Provider provenance is retained outside Git in `dex-private/ebay-live-20261003`,
`dex-private/ebay-sandbox-20261003` and `dex-private/ebay-production-setup-20261003`.
These paths identify historical private evidence, not dependencies or launch roots.

Ignored synthetic captures in `evidence/ui-clarity-20261003/` compared the beta UI
against source base `13fa6dc5e8c1cccb3704d5d3c0e96633299a9ade` at 390×844.
The Overview search link moved from document y=1220 to y=337, the first My Cards
entry from y=1073 to y=864, and reopened results with 13 history rows from y=1810
to y=411. These are layout measurements, not task-speed or user-acceptance results.
The captures and reports bind their source hashes; this record does not requalify
later edits. The observed reveal-dialog focus-return issue remains in the roadmap.
