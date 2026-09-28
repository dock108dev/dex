# Dex — Pokémon-first collection beta roadmap

Updated: September 27, 2026 (America/New_York).

**Status: B0 TECHNICALLY COMPLETE; LOCAL APP PRESERVED; MULTIUSER BETA NOT IMPLEMENTED OR RELEASED.**

This is the authoritative next-steps tracker for `/Users/michaelfuscoletti/Desktop/dex`. It replaces the earlier daily-watcher beta plan. The product is now a personal card-collection app that can expand across games. Pokémon ships first. Vintage 251 becomes a built-in collecting goal, while the current local app remains usable during development.

## 1. Product promise and scope

A collector signs in, photographs or searches for a card, confirms its exact printing, adds their copy, and sees collection and goal progress. They can track complete sets, custom checklists, duplicates and binders. When a scan encounters an unsupported card or set, the app preserves the user's entry and creates a deduplicated onboarding request. New catalog coverage can be added through the same pipeline rather than a new app.

First beta: invite-only, responsive web app for phones and computers. Start with the ten existing English Pokémon sets; display supported coverage explicitly. More Pokémon sets enter through catalog onboarding. Yu-Gi-Oh!, Digimon, other TCGs and sports cards are future game adapters on the shared foundation, not promised launch coverage. No native app, billing, trading marketplace or social network is required.

### Non-negotiable owner requirement

Mike is the first user, with login name `admin` and the owner/admin role. His existing Pokédex, exact-card collection, first-edition selections and saved hunts must survive. New users start empty and never inherit his collection. A username is not an authorization mechanism; permissions attach to the authenticated account's stable ID.

A password was supplied directly for this account. Do not reproduce it in documentation, seed files, fixtures, logs or source. Provision it through the authentication system's supported secure path when accounts are implemented; a password-based implementation stores only a modern salted password hash. If secure delivery to the implementation is needed later, use local secret entry. The account does not exist yet; documentation is not account creation.

## 2. Current baseline, verified versus planned

| Area | Current baseline | Beta gap |
| --- | --- | --- |
| Application | FastAPI and browser frontend; loopback-only request restriction | Account-aware hosted operation and deployment |
| Collection | `config/pokedex_251.json`; 859 catalog records across ten sets | Shared catalog separated from private per-user inventory |
| Owner inventory | September 27 read: 207 owned printings; 133/151 Kanto, 20/100 Johto, 153/251 total; one owned first-edition selection | Preserve exact records, not just aggregate totals |
| Copies | One owned flag per printing, with edition checkbox | Multiple independently editable physical copies |
| Goals | Vintage 251 projection and set summaries | User-selected set goals and custom checklists |
| Images | No upload or photo identification flow | Private upload, recognition, confirmation, corrections |
| Hunts | Local SQLite history; sample/live separation; spoiler-controlled reveal | User-scoped history if exposed in beta; live provider qualification remains separate |
| Values | Dated guide snapshots and labeled grade scenarios | Optional feature; current source redistribution rights and coverage need review before hosted use |
| Accounts | None | First owner account, invite flow, recovery, isolation and admin access |
| Catalog growth | Ten pinned Pokémon snapshots | Versioned ingestion, review, reconciliation and rollback |
| Verification | APP_SPEC records earlier tests and browser checks | Those are historical local evidence, not hosted beta acceptance |
| Source identity | Private `dock108dev/dex`; baseline `08aa566` | B0 implementation commit recorded in Git/private handoff; hosted candidate remains future work |

Ten initial sets: Base Set, Jungle, Fossil, Base Set 2, Team Rocket, Wizards Black Star Promos, Neo Genesis, Neo Discovery, Neo Revelation and Neo Destiny. The legacy watcher's broader search configuration is not the app's catalog coverage.

Current implementation: [README](../README.md), [APP_SPEC](../APP_SPEC.md). Detailed target contracts: [Beta design](../docs/BETA_DESIGN.md). This tracker owns sequence, scope, status and release gates; the design owns data and workflow contracts. Keep them consistent.

## 3. Required beta experience

- Sign in, recover access, sign out and use the same private inventory on another device.
- Browse supported Pokémon cards, search manually and add/edit/remove a physical copy.
- Store copy condition, optional purchase amount/currency/date, notes, front/back photos, binder and optional grading-company/grade/certificate details. Unknown values stay unset.
- Distinguish physical copy count, unique printings, set completion and species completion.
- Photograph one card, see candidates and unresolved details, confirm printing/edition and add exactly once. Ask for a close-up or back image when needed.
- Warn about existing copies while allowing intentional duplicates. Cancelled scans never change ownership. Undo accidental additions.
- Track a set without marking it owned. Bulk-add a reviewed complete-set checklist or import inventory with preview and undo.
- Create a custom goal; one owned copy can satisfy multiple goals without being duplicated in inventory.
- Save an unidentified card privately and optionally contribute evidence to an unsupported-set request. Explain pending coverage without claiming identification or value.
- Export inventory and goals, delete an account and its private photos, and send in-app beta feedback.
- Admin can review catalog requests, merge duplicate requests, ingest and publish verified catalogs, see failures/costs and pause scanning.

Suggested navigation: Collection, Scan/Add, Goals, Requests and Settings; Catalog review is visible only to admins. Keep the familiar red/white/black visual direction for the Pokémon experience; shared components must not require Pokémon species fields.

## 4. Sequenced implementation and completion gates

B0 has passed its technical exit on copied data. B1–B6 remain planned, not completed. Engineering proceeds in order where dependencies require it; UI work and catalog-source review can overlap. Finish coherent slices without another broad planning interview. The subsequent B0 execution authorized private repository creation, commits/pushes and copied-data rehearsal. No deployment, account creation, paid API use or live cutover was performed.

| Stage | Deliverable and dependencies | Completion evidence | Status |
| --- | --- | --- | --- |
| B0 — Preserve and design migration | Snapshot current owner files/history; implement catalog/copy schema and migration rehearsal on copies | Exact-record comparison, repeat-import check, rollback rehearsal; no owner source changes | TECHNICAL PASS — owner acceptance separate |
| B1 — Accounts and private inventory | First `admin` owner account, invites, sessions/recovery; B0 schema | Two-user isolation including photos/jobs/exports/admin endpoints; owner import preserved; other user empty | OPEN — NEXT |
| B2 — Collection and goals | Mobile inventory, copies, binders, set/custom goals, imports/exports/undo; B1 | End-to-end manual collection use; existing Vintage 251 result preserved; no duplicate inventory from goals | OPEN |
| B3 — Photo entry | Private upload, asynchronous OpenAI recognition, catalog candidates, confirm/cancel/undo; B1–B2 | Measured recognition quality and cost, exactly-once confirmation, useful uncertain/failure states | OPEN |
| B4 — Catalog expansion | Game adapter contract, unknown scan queue, admin ingestion/review/publish/reconcile; B0/B3 | One additional Pokémon set through ordinary ingestion; one synthetic second-game adapter without core forks | OPEN |
| B5 — Hosted beta qualification | Staging deploy, restore, privacy/data controls, support, mobile checks; B1–B4 | Acceptance matrix below; candidate manifest; actual hosted observations; cost limits verified | OPEN |
| B6 — Invite pilot | Owner review, then small invited cohort; B5 | Owner verdict and pilot outcomes recorded separately; known issues and rollback instructions delivered | OPEN |

### B0 — Preserve the existing collection first

1. Inventory source, JSON, all existing databases and photos/assets; preserve current UI/history and credentials without exposing secrets. Create a dated backup manifest and verify readable copies before migration work.
2. Separate shared catalog from private ownership. Rehearse migration using a copied snapshot and a disposable database. Map every owned card and edition selection to a stable printing and one initial copy; missing cards become no inventory rows. The old boolean does not imply extra duplicates.
3. Preserve legacy IDs and import provenance; where edition/variant identity cannot be established from legacy data, keep it unresolved and visible rather than guessing. Preserve Mike's first-edition choice explicitly.
4. Compare every owned identity and all relevant attributes, plus 207 unique owned legacy records and 153 species on the current snapshot. Re-read current source at actual migration time; if Mike has edited it, reconcile the new snapshot instead of restoring stale counts.
5. Make repeat imports idempotent and retain a reversible migration mapping. Rehearse restore. Never run collection rebuild/import scripts against the owner's live data merely to create a test fixture.
6. At actual cutover, briefly pause writes, capture the final snapshot, import once, verify, and switch the authoritative store. Do not allow old JSON and the hosted database to accept competing writes. Retain the original files and a documented rollback path, including any new writes after cutover.

**B0 exit:** no lost records or flags; exact migration and restoration evidence available; current local collection remains usable until cutover.

### B1 — Accounts and isolation

Use a mature authentication component/provider rather than inventing password/session protocols. Preserve the chosen `admin` login and provide recovery without fabricating an email address. Choose the provider during this slice based on that requirement, deployment compatibility and cost. Provision the owner before accepting other users; the first public registrant must never become admin.

Every inventory item, scan, photo, goal, export, hunt and private request evidence belongs to a user. Enforce authorization on the server, including background jobs and file access. Admin catalog permissions do not silently make private collections public. Scope troubleshooting access explicitly and audit it. Configure HTTPS, secure sessions, request-origin/CSRF protection appropriate to the auth flow, and bounded login/upload/scan rates before exposing the app. Do not simply remove the local Host guard and publish today's unauthenticated endpoints.

### B2 — A useful collection before scanning

Deliver search/manual add first so recognition outages never prevent collection use. Support copies, binders, editing, removal/undo, set goals and custom goals. Separate track-set, own-set and upload-new-catalog actions. A complete-set addition must show the exact checklist, edition/variant scope, existing ownership and proposed changes, then apply atomically with a reversible batch ID. Missing variants or unknown checklist coverage cannot be labeled complete.

Support previewed CSV/JSON inventory import with row errors, duplicate policy and stable import IDs. Export copy identity, unresolved records, attributes, goals and schema version. Preserve the original owner export separately. Keep raw values and hypothetical graded values clearly distinct; pricing is not required to use inventory.

### B3 — Scan, confirm and improve

Implement the workflow in BETA_DESIGN. Use the OpenAI API on the server; keep model choice, prompts and result schema versioned. Start with a single card front and optional back/close-up. Output is evidence for catalog matching, not automatic authority. No automatic ownership changes, authenticity certification, condition grade or price claims from a photo.

Record user corrections as reviewable feedback. Maintain a held-out recognition evaluation set; measure changes before enabling improved prompts/matching. Repeated guesses or user votes do not establish catalog truth. Improvement can use corrected lookup mappings and reviewed reference examples; automatic model retraining is not a beta dependency. Photo reuse for shared improvement is optional and separate from private photo storage.

Set scan quotas, upload limits, timeouts, capped retries, per-user/global spend limits and a kill switch. Measure actual cost and latency on representative inputs before setting a public allowance. Provide clear failure/retry/manual-entry states.

### B4 — Expand by catalog, not by rebuilding

Unsupported scans create deduplicated requests with provisional game/set identifiers, evidence status, distinct-requester count and admin disposition. Do not auto-publish an entire set from one scan. The user can retain a private provisional copy while onboarding proceeds.

Ship admin states: new, needs evidence, ready for ingestion, importing, verified, published, rejected/merged. Admin actions: inspect evidence, correct game/set, merge, attach catalog source, preview import, publish/rollback and resolve waiting users. Rank demand by unique users plus review quality, not repeated uploads.

Onboard one additional Pokémon set through the same importer and validate a synthetic second-game adapter using a non-Pokémon numbering/variant scheme. This proves extensibility without claiming Yu-Gi-Oh! or Digimon coverage. Real future games each require source review, identity rules, representative scans and a bounded catalog pilot. Sports use the same machinery with sport/season/brand/player/parallel attributes.

### B5 — Make the beta operable

Proposed architecture: keep FastAPI and the current frontend where practical; shared PostgreSQL inventory/catalog, private object storage for photos, and a database-backed job queue/worker for scans/imports. Managed auth, database and storage may share a provider. No microservice platform or frontend rewrite is required. Lock provider selection after a small deployment/cost proof rather than maintaining multiple implementations.

Before pilot: configure staging/production separation, secrets, migrations, health/error monitoring, redacted logs, backups and an observed restore. Support account/photo deletion and a stated retention policy. Confirm rights/terms for each hosted catalog, image and pricing source; existing local snapshots do not establish hosted redistribution rights. Omit unavailable images or pricing features rather than guessing permission. Keep pending catalog/image rights visible as a coverage blocker, not a reason to stop unrelated engineering.

Provide start/deploy/rollback, disable-scanning, restore, invite/revoke and incident/support instructions. Collect errors, scan latency/cost and user-confirmation outcomes without placing private images or credentials in ordinary logs. Keep admin operations audited and reversible where possible.

### B6 — Owner then invited users

Default pilot size: owner plus up to nine invited collectors. No public signup or paid tier required. Mike first reviews his preserved Pokédex and the actual phone scan/add experience. Record his verdict; tests cannot supply it. Then each pilot user should add cards, correct a scan, track a set, handle an unsupported item, reopen on another device and export their collection. Record task success, friction and actual support burden. Stop new invites for ownership loss, cross-account access, unbounded spend or repeated unusable scans; repair and requalify the affected gate.

## 5. Beta acceptance matrix

These are planned release thresholds, not measured results. Tune only with an explicit recorded reason; do not silently lower a target after a failure.

| Gate | Required observation |
| --- | --- |
| Owner preservation | Full identity/attribute comparison and read-back; expected current counts; first-edition selection and saved hunts preserved; restore exercised |
| Isolation | Account A cannot read/write Account B inventory, goals, photos, jobs, exports or private evidence; non-admin cannot publish catalogs |
| Collection integrity | Retry, double-tap, interrupted request and repeat import never duplicate a single operation; intentional extra copies work; concurrent edits cannot silently overwrite changes |
| Mobile usability | Real camera/library input on iOS Safari and Android Chrome, plus desktop; readable confirmation, keyboard access, focus and touch targets |
| Supported recognition | Held-out set of at least 100 photos across all initial sets and representative edition/foil/number ambiguities; at least 95% exact top-choice matches on the declared clear/readable supported subset; report subset size and overall coverage |
| Uncertainty | Separate unreadable/unsupported/ambiguous cases; any ambiguous case with insufficient identifying evidence requests review instead of claiming certainty; report confident wrong matches separately |
| Confirmation | Every add requires user review; model output alone never mutates ownership; cancelling adds nothing; confirming twice adds once; undo removes only the selected addition |
| Catalog onboarding | New Pokémon set can be previewed, verified, published and rolled back; no orphaned copies or forced false matches; second-game fixture uses unchanged core inventory/scan workflow |
| Runtime | Hosted sign-in/recovery, upload, scan worker, retry, export and restart exercised; unavailable API leaves manual entry working |
| Cost | Actual per-attempt and per-success scan costs plus latency measured; pilot budget and caps recorded; global stop verified with no uncontrolled retries |
| Privacy/source rights | Private uploads, retention/deletion behavior and optional reuse consent verified; licensed/allowed data scope recorded for published content |
| Release | Exact tested source/configuration/catalog/model/prompt identities and known issues recorded; no secrets in evidence |
| Owner/pilot | Mike's preservation/usability verdict and pilot task outcomes recorded independently of engineering checks |

Recognition metrics use catalog identity including required edition/variant fields. Unknown variants cannot be counted as exact matches. Report top-choice accuracy, alternatives success, abstention/manual-correction rate, failure rate, median/p95 latency and cost per successful confirmed addition. A perfect score from excluding difficult examples is not a complete report.

## 6. Economics and decisions to close during implementation

- Select hosting/auth/storage and document fixed monthly cost, backup/storage growth and provider limits before B5.
- Measure recognition expense as attempts per user × cost per attempt, including retries, plus hosting/storage. Set a pilot-wide monthly ceiling and user allowance before inviting users; amounts are not yet selected.
- Confirm catalog and image rights and source coverage before publishing each set. Do not depend on scraped price tables for the core beta.
- Select the first additional Pokémon set using verified source availability and actual request demand. No need to choose every future game now.
- Decide final public name before broader distribution. Keep Vintage 251 as the owner's goal; naming work must not block collection engineering.
- Invitations and account recovery need a selected delivery mechanism/address at setup; no invented contact details or outbound messages as part of this documentation task.

## 7. Explicitly outside the first beta

Bulk binder-page recognition, video scanning, automatic grading/authentication, automated purchases/bids, probability/rare-odds claims, social trading, payments, push notifications, native app-store releases, automatic training and broad multi-game catalog launches. Add these only after the core loop is useful.

The existing eBay hunt and legacy daily watcher remain preserved, optional modules. eBay approval, real-search qualification and scheduling are not collection-beta blockers. If hunts are enabled in hosted beta, scope all state to users, qualify provider access/terms, preserve spoilers and unknown economics, and show sample/live status. Otherwise keep them local or hidden in hosted beta. No new schedule or reminder is installed by this plan.

## 8. Immediate next action and continuation

**Next: implement B0's shared catalog/copy schema and migration rehearsal against disposable copies, preserving Mike's exact collection and preparing the first `admin` account for B1.** Do not start with a generic signup screen attached to the shared ownership JSON.

Read this tracker, BETA_DESIGN and APP_SPEC before implementation. Use the current collection at execution time, not only these dated counts. Preserve credentials and data, continue the first incomplete stage, and update this file with evidence as stages finish. Routine implementation choices do not need another broad planning interview. Resolve concrete required secrets, provider costs or deployment details at the step that needs them.

For every stage record: date, exact candidate/source identity, changed behavior, checks, evidence paths, limitations and next actor. Mark technical completion separately from owner acceptance. Use `READY FOR INVITED BETA` only after B0–B5 pass and Mike approves the owner walkthrough; use `INVITED BETA ACTIVE` only after actual invitations/deployment. Neither status is currently earned.

## 9. Documentation update record

September 27: replaced the obsolete watcher-first roadmap with the collection-beta scope; reconciled current local source and collection counts; recorded owner-first `admin` migration and Pokémon-first multi-game expansion. README and APP_SPEC link to this plan and the design. No runtime code, credentials, ownership, database, account or hosted service was changed. Existing test results were not rerun or relabeled as beta evidence.

## B0 execution result — September 27, 2026

Repository: https://github.com/dock108dev/dex (private). Baseline: `08aa5662088f326f86483b0fa4b2e026845316de`. [Implementation and reproducible checks](../docs/B0_IMPLEMENTATION.md).

All B0 technical exit requirements passed: 87-file verified backup, exact comparison of 859 records / 207 physical copies, one first-edition selection, Vintage 251 at 133 Kanto and 20 Johto, two owner-scoped saved hunts, identical repeat import, full restore and unchanged local owner data/UI. All 207 copies retain explicit unresolved finish/variant information; none was guessed. No current identity conflicts. Tests use sanitized synthetic ownership; private evidence remains outside Git.

Local evidence: `/Users/michaelfuscoletti/dex-private/b0-20260927/`; final rehearsal: `rehearsal-final/report.json`; tested commit and checks: `handoff.json`. Owner acceptance and hosted-beta readiness remain unestablished. B1 next: select mature auth supporting admin login/recovery, bind the stable owner ID, and implement/prove two-user isolation before any live cutover.
