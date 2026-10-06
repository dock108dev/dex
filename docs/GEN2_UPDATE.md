# Gen 2 collection declaration — October 5, 2026

The owner requested an app update from `outputs/gen2-152-251.csv`. The file contains
100 species rows, with 24 species/set presence marks and 76 species unmarked. Its
SHA-256 is `e55ea541a4549ca2de57e5c64dcdf048f2b23dde06ec2e16e2f92bbf6962fd5f`.
The UTF-8 BOM is preserved in provenance and handled only when parsing columns.

Gen 2 is displayed separately from Original 151 in Collection and Goals. The original
133/151 declaration remains unchanged. Presence declarations never create physical
copies, quantities, finishes, editions or frozen-goal membership. Blank rows are not
deletions. Lugia's Plasma Storm `✓EX` marker remains literal and requires review; no
exact EX printing identity is inferred. Gen 2 reviewed printing progress is explicitly
not evaluated by this declaration rather than borrowing Original 151's count.

The existing declaration schema and preview/confirm/undo workflow are reused; no
schema migration is needed. Copied-owner rehearsal demonstrates idempotency, undo,
full backup restoration and preservation of all 207 existing copies. Five marks need
catalog/copy matching review. Private receipts/backups live under
`/Users/michaelfuscoletti/dex-private/gen2-20261005/`; no private inventory rows or
photo bytes are copied into repository evidence.

Actual owner application passed after the copied-owner rehearsal. One new declaration
row was added; the prior Original 151 declaration row is byte-identical. All 207
existing copies, 37 protected tables and non-database file bytes are unchanged.
Private applied receipt and restorable backup: `gen2-20261005/applied/` under the
private evidence root above.

Full suite: **531 passed**, one existing Starlette/httpx warning, 167.33 seconds.
Four declaration tests, repository-wide Ruff lint/format, changed JavaScript syntax,
compilation and whitespace checks passed. No source acquisition occurred.

The guarded owner server is open at `http://127.0.0.1:8011/login/`, with zero
acquisition invocations/external requests. No password or authentication policy was
changed. Authenticated ordinary browser verification of both declarations remains
pending owner sign-in. An initial `/collection/` navigation returned 404 because
the app collection route is `/`; no authenticated browser success is claimed.

All-era catalog, exact printing resolution, PostgreSQL and beta/owner acceptance
remain open. Next: owner sign-in for the authenticated Collection/Goals walkthrough.
New candidate: `evidence/gen2-20261005/validation-final/candidate.json`.
