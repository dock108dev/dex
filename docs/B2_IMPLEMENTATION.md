# B2 — collection, binders, versioned goals and reviewed operations

Implemented September 27–28, 2026. **B2 local engineering verified independently of B1 actual owner provisioning, which remains pending.** No owner acceptance, live cutover or hosted-beta readiness is claimed. Starting commit: `224eb32` (B1). The final tested/pushed commit, tree, source manifest, check outputs and clean-checkout/browser results are bound in the private `b2-20260928/handoff.json`. This document deliberately does not invent a self-referential commit hash.

## Application and isolation

B2 extends the existing Django application and B0 SQLite inventory. It does not replace or modify the legacy FastAPI application, ownership JSON, hunt stores or frontend. `init --b2` creates a **new** private directory from a copied B0 database, adds revision columns, versioned goals, operation history and account-generation counters, and writes a B2 marker. It refuses any existing directory. There is no in-place owner-local upgrade command. Roots without the B2 marker retain the B1 routes, request limit and interface. The prepared B1 `owner-local` environment was not initialized, reset, bootstrapped or modified.

All collection, catalog, binder, goal, preview, confirmation, history, export and undo endpoints require the existing Django session. Each service re-resolves the active stable account mapping, including inside confirmation and undo transactions. Incoming resource IDs never select a user; ordinary catalog-admin privileges confer no private inventory bypass. The original notes-only writer is unavailable in B2, preventing writes outside the revision protocol. B1's Host/Origin/CSRF/cookie protections remain in force. This is still fixed loopback HTTP at `127.0.0.1:8011`, with no qualified hosting configuration.

## Completed flows

- **Collection:** browse/search the supported catalog by name, number and set; inspect printing scope and uncertainty; preview and add a physical copy. Explicit duplicate choices are reject, skip or intentionally allow. A new intentional addition has a new operation ID. Search owned copies and filter by private binder.
- **Copy attributes:** edit condition, exact purchase amount/currency/date, notes, binder, optional grading company/grade/certificate. Unknowns remain null. Decimal text supports up to 12 integer and 6 fractional digits; no floating-point conversion or inferred value/grade. Amounts require currency; optional dates are validated. Catalog identity remains stable. Unsupported edition/variant resolution is not guessed.
- **Removal and undo:** remove a copy from active inventory; restore it through its operation. A successful undo is itself retry-safe. Added copies are deleted only when their recorded after-images are still unchanged; their operation provenance remains. Removed pre-existing copies and edited records restore their before-images with a higher revision. No original B0 import/archive records are rewritten.
- **Binders:** create, rename, remove empty binders and undo. Assigning a binder moves membership without cloning a copy. A binder used by other copies cannot be undone/removed. Restore a removed copy and move it out before deleting its binder.
- **Goals:** track a set without adding inventory; create a custom checklist from selected supported entries; select Vintage 251 `legacy-v1`. Each goal stores immutable membership, policy and a content-hashed version. Catalog-entry, exact-variant and species counts are distinct. Vintage exclusions apply only to Vintage; Dark/named cards remain in inventory and ordinary set/custom goals. One copy can satisfy multiple goals without increasing quantity or value. Goal removal supports undo; changing membership means explicitly creating a new goal/version.
- **Owned-set addition:** a separate reviewed checklist shows each entry, catalog version/coverage, edition/finish/variant uncertainty, existing copies, duplicate policy and proposed additions. Tracking never calls this writer. Unknown variant coverage never becomes a master-set claim. The batch commits atomically and undo removes only its own additions.
- **Imports/exports:** preview CSV or JSON, see row-level errors, choose duplicate handling, then confirm. Any error blocks the whole import. JSON exports include schema `dex-collection-v2`, active copies and identities, unresolved fields, all attributes, binders and frozen goals. JSON round trips restore supported inventory into an empty isolated account; local IDs are remapped to that account and original copy identity retained in `source_copy_id`. Original migration archives and owner exports remain intact.

The interface uses red/white/black Collection, Goals and Settings navigation, clear manual-add controls, native modal focus behavior, labels, visible errors, empty states and controls at least 44 pixels tall. Operation/printing references are expandable. Review actions remain visible while the checklist scrolls, including on narrow screens. No images, pricing or recognition calls are required.

## Transaction and replay contract

Each preview is a durable owner-scoped operation. Manual IDs are UUIDs namespaced to the session's stable owner; import IDs derive from the owner and exact input/format/duplicate policy. An identical confirmed import returns its saved result even if the caller supplies another UUID. Source-copy identities additionally prevent duplicate re-import into the same account. Changing input is a new reviewed operation; intentional repeated manual additions remain possible.

SQLite `IMMEDIATE` transactions serialize confirmation and undo. The service rechecks identity, catalog intent and the account's mutation generation before applying the complete plan. A change since preview returns a conflict; explicitly previewing again refreshes the stored plan for review. Confirmation never silently refreshes intent. Double confirmation and retry after a lost response return the recorded outcome; interrupted transactions roll back all rows and the journal together.

Edits require the observed record revision. Undo compares every recorded after-image, including revisions, before changing anything. Later edits, including edited-back values, block undo with an explanation instead of overwriting them. Undo does not blindly unwind other operations. Dependent binder membership is also checked. A confirmed operation that has been undone cannot be replayed into a new addition.

Exact-variant goals require resolved checklist entries **and** resolved owned copies; updating catalog metadata cannot quietly turn a still-unresolved copy into exact completion. Vintage import validation preserves the versioned species/exclusion rules. Goal denominators and member IDs do not follow later catalog changes.

## Import format and limits

Use the JSON export for a full inventory/binder/goal round trip. A plain JSON array of copy rows is also supported. CSV accepts `printing_id` plus optional `id`, `condition`, `purchase_amount`, `purchase_currency`, `purchase_date`, `notes`, `binder_id`, `grading_company`, `grade` and `certificate`. Printing references appear in catalog/add review and JSON exports. CSV binder IDs must already belong to the importing account. CSV does not define binders/goals; JSON exports carry those definitions.

Imports are bounded to 1.5 MB of text, 2,000 copies and 200 binders/goals each. The B2 HTTP body limit is 2 MB. Money must be text in JSON, e.g. `"12.340001"`, not a numeric floating-point token. Unknown or incompatible catalog identities require reconciliation; import never silently remaps them. Every row is validated even under skip-duplicates policy. Importing a saved export does not import credentials, original private archive bytes, hunts, operation history or another user's authorization.

## Verification and preservation

Private evidence is under `/Users/michaelfuscoletti/dex-private/b2-20260928/`, outside Git:

| Evidence | What it establishes |
| --- | --- |
| `before/`, `rehearsal/report.json`, restored snapshot | Fresh snapshot, exact source records, repeat B0 import, byte-equal archive restore and database integrity |
| `preservation.json` | Owner/config/source/frontend hashes unchanged, all three original databases logically equal, restored legacy collection/export/hunt reads pass |
| `copied-preservation.json` | Original copied owner identities, attributes, first-edition choice, hunts and Vintage result still match the fresh source after B2 exercise |
| `regression-final.txt`, `b2-final.txt`, check logs | Regression and targeted synthetic B2 checks; exact final count recorded in handoff |
| `browser-final/` | Working-tree browser flow and visual inspection; two separate Chromium contexts at 1280px and 390px |
| `clean-browser-release/`, `clean-*.txt` | Exact committed candidate in a clean checkout, independent browser contexts, checks and copied-data verification |
| `handoff.json` and source manifest | Exact tested/pushed commit and tree, source hashes, repository visibility and evidence paths |

The fresh source contains 859 catalog records, 207 owned copies, one first-edition selection, two saved hunts and Vintage progress 133 Kanto + 20 Johto = 153/251. These were reconciled from the current authority, not forced from historical totals. All 207 copied records retain some unresolved detail. Browser-created records are explicitly synthetic additions; original owner records are compared individually, not inferred from aggregate totals.

Synthetic tests cover double submits, same-ID different-input rejection, simultaneous confirmation, stale revision/preview conflicts, interrupted confirmation and undo, retry, deliberate duplicates, scoped undo, binder dependencies, frozen/exact/species goals, malformed imports, decimal errors, stable import receipts, full export/import round trip, anonymous access, CSRF, revoked actors, forged IDs, and every new feature across two accounts in both directions. B1 and legacy regressions remain included. The existing FastAPI/Starlette TestClient deprecation warning remains; it is not a runtime failure.

Browser automation performs complete manual flows in both accounts: binder creation, invalid amount feedback, add with duplicate acknowledgment, retry, edit, remove/undo, set/custom/Vintage tracking, reviewed owned-set batch/undo, invalid and valid CSV/undo, JSON round trip, exports, keyboard focus and cross-account denial. Screenshots were inspected. Narrow mode is Chromium viewport/touch emulation; real iOS Safari and Android Chrome remain B5 observations. Earlier failed attempts are retained: one ambiguous harness selector and an amount-validation ordering issue (now validated before duplicate handling). The first committed-candidate browser attempt also exposed a harness text read from a collapsed disclosure; the harness now reads the saved reference independently of visibility. Earlier failed attempts are not passing evidence.

## Launch the prepared isolated review app

From the checkout, initialize no further environment. `review-local` already contains a fresh copied database and no credentials. Choose a disposable rehearsal password in the private terminal prompt, then launch:

```sh
uv run python -m pokemon_hunter.beta.cli --root /Users/michaelfuscoletti/dex-private/b2-20260928/review-local bootstrap
uv run python -m pokemon_hunter.beta.cli --root /Users/michaelfuscoletti/dex-private/b2-20260928/review-local serve
```

Open `http://127.0.0.1:8011/login/` and sign in as `admin` using that rehearsal password. Do not launch B1 and B2 simultaneously on this fixed port. Bootstrap refuses password replacement for an already-bound account. This B2 rehearsal account is not B1 actual-owner provisioning. The separate browser roots use random test-only passwords and must not be reset for a new verification run.

To reproduce from a new private root and copied B0 database:

```sh
uv sync --frozen --extra dev
uv run python -m pokemon_hunter.beta.cli --root "$B2_ROOT" init --b2 --copied-inventory "$B0_COPY"
uv run python -m pokemon_hunter.beta.cli --root "$B2_ROOT" check
uv run python -m pokemon_hunter.beta.cli --root "$B2_ROOT" serve
# Separate terminal; requires local Google Chrome and a fresh root with no accounts:
uv run --with playwright python scripts/verify_b2_browser.py --root "$B2_ROOT"
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
node --check src/pokemon_hunter/beta/static/collection.js
node --check web/app.js
```

## Remaining gates and next actor

**Mike:** review the isolated B2 collection flow using a disposable rehearsal credential. Separately, B1 still requires actual owner provisioning and actual-account preservation verification in its prepared environment. No test substitutes for either owner feedback or actual owner provisioning.

**Engineer after review:** address focused B2 feedback, then proceed to the separately authorized B3 photo-entry stage. Photo storage/recognition is B3; catalog onboarding and unresolved variant qualification are B4; hosting, production database, HTTPS, privacy/rights/cost qualification and real-device observations are B5; owner acceptance/pilot is B6. No deployment, live cutover, paid service, external message or change to Mike's credentials occurred.
