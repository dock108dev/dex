# Dex — Pokémon-first collection beta roadmap

Updated: September 28, 2026 (UTC; September 27 evening in America/New_York).

**Status: B0 TECHNICALLY COMPLETE; B1 LOCAL IMPLEMENTATION VERIFIED, ACTUAL OWNER PROVISIONING PENDING; B2 PARITY VERIFIED, INITIAL OWNER FEEDBACK POSITIVE, REVIEW CLOSEOUT PENDING; LOCAL APP PRESERVED; NOT RELEASED.**

This is the authoritative next-steps tracker for `/Users/michaelfuscoletti/Desktop/dex`. It replaces the earlier daily-watcher beta plan. The product is now a personal card-collection app that can expand across games. Pokémon ships first. Vintage 251 becomes a built-in collecting goal, while the current local app remains usable during development.

## 1. Product promise and scope

A collector signs in, photographs or searches for a card, confirms its exact printing, adds their copy, and sees collection and goal progress. They can track complete sets, custom checklists, duplicates and binders. When a scan encounters an unsupported card or set, the app preserves the user's entry and creates a deduplicated onboarding request. New catalog coverage can be added through the same pipeline rather than a new app.

First beta: invite-only, responsive web app for phones and computers. Start with the ten existing English Pokémon sets; display supported coverage explicitly. More Pokémon sets enter through catalog onboarding. Yu-Gi-Oh!, Digimon, other TCGs and sports cards are future game adapters on the shared foundation, not promised launch coverage. No native app, billing, trading marketplace or social network is required.

### Non-negotiable owner requirement

Mike is the first user, with login name `admin` and the owner/admin role. His existing Pokédex, exact-card collection, first-edition selections and saved hunts must survive. New users start empty and never inherit his collection. A username is not an authorization mechanism; permissions attach to the authenticated account's stable ID.

A password was supplied directly for this account. Do not reproduce it in documentation, seed files, fixtures, logs or source. Provision it through the authentication system's supported secure path when accounts are implemented; a password-based implementation stores only a modern salted password hash. If secure delivery to the implementation is needed later, use local secret entry. The actual B1 owner account remains unprovisioned. The disposable B2 review account is separate and does not close that gate.

## 2. Current baseline, verified versus planned

| Area | Current baseline | Remaining gate |
| --- | --- | --- |
| Application | Authenticated local Django review app; original FastAPI app preserved | Hosted operation and deployment remain unqualified |
| Collection | Shared catalog and session-owned physical copies; 859 entries across ten sets | Broader catalog/variant coverage is B4 |
| Owner preservation | Copied-snapshot verification: 207 copies, one first-edition selection, 133 Kanto + 20 Johto = 153 species | Actual owner account binding and eventual cutover remain separate |
| Copies | Intentional duplicates, copy attributes, first-edition selection, reviewed edits/removals and undo | Unknown editions/finishes stay unresolved; photo entry implemented in B3 |
| Goals and organization | Private binders, frozen set/custom/Vintage goals, reviewed set additions | Further owner feedback; no inventory duplication from goals |
| Original experience | Overview, Pokédex, My Cards and rarity/set summaries restored | Focused review closeout; initial owner response was positive |
| Images | Private photo upload, durable jobs, manual/fixture/OpenAI integration and safe confirmation/undo | Live recognition evaluation pending secure API configuration |
| Hunts | Private sample hunts, missing singles, saved-search replay and explicit reveal | New live search disabled pending separate provider qualification |
| Values | Local dated guide scenarios with coverage/interpolation labels | Unresolved variants excluded from confirmed values; hosted source rights pending |
| Accounts | Local sessions/invites/recovery and isolation implemented; disposable review account running | Actual B1 owner provisioning still pending; review account is separate |
| Verification | B3 runtime `a456ab7`: 173 tests, clean checkout, desktop/narrow B2+B3 browser checks passed | Real recognition, real-device and hosted acceptance remain open |
| Source | Private `dock108dev/dex`; development and sync on local/remote `main` | No feature branches unless Mike explicitly requests one |

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

B0 has passed its technical exit on copied data. B1 has a verified isolated local implementation with actual owner provisioning pending. B2 local collection engineering is verified independently of actual-owner provisioning; B3 local photo-entry and B4 local catalog-expansion engineering are implemented; real recognition evaluation and B5–B6 remain open. Engineering proceeds in order where dependencies require it; UI work and catalog-source review can overlap. Finish coherent slices without another broad planning interview. The subsequent B0 execution authorized private repository creation, commits/pushes and copied-data rehearsal. No deployment, account creation, paid API use or live cutover was performed.

| Stage | Deliverable and dependencies | Completion evidence | Status |
| --- | --- | --- | --- |
| B0 — Preserve and design migration | Snapshot current owner files/history; implement catalog/copy schema and migration rehearsal on copies | Exact-record comparison, repeat-import check, rollback rehearsal; no owner source changes | TECHNICAL PASS — owner acceptance separate |
| B1 — Accounts and private inventory | First `admin` owner account, invites, sessions/recovery; B0 schema | Two-user isolation including photos/jobs/exports/admin endpoints; owner import preserved; other user empty | LOCAL CHECKS PASS — actual owner provisioning pending |
| B2 — Collection and goals | Mobile inventory, copies, binders, set/custom goals, imports/exports/undo; B1 | End-to-end manual collection use; existing Vintage 251 result preserved; no duplicate inventory from goals | LOCAL ENGINEERING PASS — owner review separate |
| B3 — Photo entry | Private upload, asynchronous OpenAI recognition, catalog candidates, confirm/cancel/undo; B1–B2 | Exactly-once confirmation and uncertain/failure states verified locally; live recognition quality/cost unmeasured | LOCAL ENGINEERING IMPLEMENTED — API setup/evaluation pending |
| B4 — Catalog expansion | Game adapter contract, unknown scan queue, admin ingestion/review/publish/reconcile; B0/B3 | English Gym Heroes through ordinary ingestion/rollback; synthetic Orbits through shared request/matching/inventory paths | LOCAL ENGINEERING IMPLEMENTED — hosted qualification separate |
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

**Next: use the delivered B4 request-to-resolution loop; configure a key and suitable images for bounded B3 real recognition evaluation when available. Continued pre-alpha work is authorized without another routine approval checkpoint.** Actual owner provisioning and subsequent binding verification remain a separate pending B1 gate. B0 is complete. B1 authentication uses a separate copied database; the live collection remains authoritative and unchanged.

Read this tracker, BETA_DESIGN and APP_SPEC before implementation. Use the current collection at execution time, not only these dated counts. Preserve credentials and data, continue the first incomplete stage, and update this file with evidence as stages finish. Routine implementation choices do not need another broad planning interview. Resolve concrete required secrets, provider costs or deployment details at the step that needs them.

For every stage record: date, exact candidate/source identity, changed behavior, checks, evidence paths, limitations and next actor. Mark technical completion separately from owner acceptance. Use `READY FOR INVITED BETA` only after B0–B5 pass and Mike approves the owner walkthrough; use `INVITED BETA ACTIVE` only after actual invitations/deployment. Neither status is currently earned.

## 9. Documentation update record

September 27: replaced the obsolete watcher-first roadmap with the collection-beta scope; reconciled current local source and collection counts; recorded owner-first `admin` migration and Pokémon-first multi-game expansion. README and APP_SPEC link to this plan and the design. No runtime code, credentials, ownership, database, account or hosted service was changed. Existing test results were not rerun or relabeled as beta evidence.

## B0 execution result — September 27, 2026

Repository: https://github.com/dock108dev/dex (private). Baseline: `08aa5662088f326f86483b0fa4b2e026845316de`. [Implementation and reproducible checks](../docs/B0_IMPLEMENTATION.md).

All B0 technical exit requirements passed: 87-file verified backup, exact comparison of 859 records / 207 physical copies, one first-edition selection, Vintage 251 at 133 Kanto and 20 Johto, two owner-scoped saved hunts, identical repeat import, full restore and unchanged local owner data/UI. All 207 copies retain explicit unresolved finish/variant information; none was guessed. No current identity conflicts. Tests use sanitized synthetic ownership; private evidence remains outside Git.

Local evidence: `/Users/michaelfuscoletti/dex-private/b0-20260927/`; final rehearsal: `rehearsal-final/report.json`; tested commit and checks: `handoff.json`. Owner acceptance and hosted-beta readiness remain unestablished. That B0 handoff is historical. See the B1 execution record below for the current next action.


## B1 execution result — September 27–28, 2026

**B1 full technical exit remains OPEN: actual owner provisioning is pending.** Local authentication and isolation are implemented and verified using isolated test identities. Owner acceptance and hosted-beta readiness are not established. [Implementation, auth decision, local launch and recovery](B1_IMPLEMENTATION.md).

| Requirement | Actual status | Evidence / limitation / next actor |
| --- | --- | --- |
| Mature authentication | PASS locally | Django 5.2 LTS + django-axes; official auth/CSRF/ASGI/license documentation verified; no auth subscription; hosted infrastructure cost unselected |
| Stable owner binding | Rehearsal PASS; actual owner PENDING | Transactional owner-first bootstrap binds existing B0 ID; repeat preserves credentials/identity; username changes do not transfer role. Mike must enter the actual credential locally |
| Working account boundary | PASS for implemented surface | Sign-in/out, invite redemption, local operator recovery, collection view, notes mutation, inventory export, preserved hunts and archive downloads |
| Later-resource boundary | PASS boundary only | Synthetic photo/job/goal/request-evidence and worker checks; unfinished routes unavailable; full workflows remain B2–B4 |
| Copied owner preservation | PASS | Fresh B0 snapshot, exact attributes/identities/edition/hunts/Vintage comparison, repeat import and restore; second account starts empty |
| Adversarial/lifecycle checks | PASS locally | Anonymous/forged/guessed/cross-account access, admin separation, file/worker scope, token expiry/reuse/replacement, session expiry/logout/revocation, login limits and CSRF/Origin checks |
| Two real browser sessions | PASS locally | Independent Chromium contexts, preserved owner view, empty second account, synthetic reverse-isolation check, invite/recovery/logout |
| Original app preservation | PASS | Owner/config/frontend hashes and complete logical SQLite comparisons; restored legacy app collection/export/hunt reads; no live cutover |
| Candidate and clean checkout | Recorded in private handoff | Tested/pushed commit and clean-checkout checks are bound in `b1-20260927/handoff.json`; repository remains private |
| External delivery / hosting | NOT VERIFIED | No outbound invitation/recovery message, deployment, service purchase or paid recognition; later-stage qualification required |

Private evidence: `/Users/michaelfuscoletti/dex-private/b1-20260927/`. `before/` is the fresh snapshot; `rehearsal/report.json` is exact import/restore evidence; `browser-final-candidate/` holds the passing browser report and screenshots; `preservation.json` verifies live files; `handoff.json` records exact tested/pushed identity and checks. Earlier browser attempts are retained as failed attempts, not passing evidence.

Secure owner entry, from the repository (prepared root already initialized; do not rerun init):

```sh
uv run python -m pokemon_hunter.beta.cli --root /Users/michaelfuscoletti/dex-private/b1-20260927/owner-local bootstrap
uv run python -m pokemon_hunter.beta.cli --root /Users/michaelfuscoletti/dex-private/b1-20260927/owner-local serve
```

The password prompt does not echo or accept a password argument. Open `http://127.0.0.1:8011/login/`. This is a copied, visibly labeled rehearsal, not the authoritative collection. Next actor: Mike for credential entry, then engineer for the actual-account verification; B2 may build on the tested local boundary, while B1 actual-owner status remains explicit.


## B2 execution result — September 27–28, 2026

**B2 local engineering is verified; B1 actual owner provisioning remains PENDING. Owner acceptance and hosted-beta readiness are NOT established.** See [B2 implementation, evidence and launch](B2_IMPLEMENTATION.md). Starting candidate: B1 `224eb32`; the exact tested/pushed B2 commit, tree and source manifest are recorded in the private `b2-20260928/handoff.json` and Git history.

- Extended the same authenticated Django application and B0 inventory: manual catalog search/add, intentional duplicates, exact copy attributes, edit/remove/undo, private binders, set/custom/Vintage goals and frozen checklists. Legacy app and prepared B1 owner-local are preserved.
- Track-set adds no copies. Add-owned-set reviews catalog/variant coverage, existing ownership and duplicate policy, then confirms atomically under one durable operation ID.
- CSV/JSON import previews validate rows and duplicate handling; errors block the whole batch. Complete JSON exports round-trip supported copies, attributes, uncertainty, binders and goals into an empty isolated account. Original archive/migration evidence stays intact.
- Rechecked session ownership for every new read, mutation, batch, export and undo. Tested concurrent confirmation, retries, interrupted transactions, stale edits, scoped undo and later-edit conflicts.
- Completed desktop and 390px Chromium browser flows in independent accounts, including cross-account denial. Keyboard focus, readable errors, empty states, touch-sized controls and screenshots checked. This is browser emulation, not real-device acceptance.
- Fresh copied preservation reconciles 859 source records, 207 owned copies, one first-edition selection, two hunts and 153/251 Vintage species. All owner/config/frontend hashes and original databases remain unchanged; restored legacy app reads pass.
- Evidence remains private under `/Users/michaelfuscoletti/dex-private/b2-20260928/`; exact committed-candidate regression, clean-checkout and browser results are in the handoff. No cutover, deployment, external message, paid recognition or credential change occurred.

**Superseded review environment:** use the new [B2 parity review launch](B2_PARITY.md#launch-the-revised-review-app) for the restored experience. The prior `b2-20260928/review-local` data and credentials remain preserved. Separately, Mike still owns actual B1 credential entry, followed by engineer actual-account verification. B3 and B4 are implemented as documented below; do not mark hosted release or owner acceptance from these checks.


## B2 owner feedback — local feature parity revision required

Owner feedback after opening the isolated B2 app: “its fine but its missing a lot of features we had locally.....” This is feedback on incomplete product coverage, not owner acceptance. The B2 engineering checks above remain valid for the implemented slice; they do not establish parity with the original local application.

The feedback identified these gaps in the original B2 slice (implemented by the subsequent revision below):

- Rich overview with separate Kanto/Johto progress, set summaries and rarity breakdowns.
- Interactive Pokédex with species search, region and owned/missing/unavailable filters, and eligible-printing detail.
- My Cards set/type/rarity browsing, owned/missing summaries and explicit first-edition selection controls.
- Collection estimates and per-card ungraded/graded scenarios, dated sources, interpolation labels and coverage/uncertainty. Purchase amounts in B2 do not replace these estimates.
- Mystery hunt and missing-singles search, budget/focus controls and spoiler-safe reveal.
- Readable saved-find history and reopening/re-scoring against the user's current collection; the preserved raw hunt endpoint is not equivalent UI functionality.

**Revision scope (now implemented):** restore the existing local experience within the authenticated application before adding photo-entry functionality. Retain B2 physical copies, binders, versioned goals, imports and safe undo; derive all restored views from the same session-owned inventory. Do not reopen unauthenticated legacy writers or create a second authoritative collection. Preserve unknown edition/variant information, distinguish recorded purchase costs from value estimates, and retain sample/live and spoiler boundaries. Existing provider access and hosted source-rights gates remain in force; no live search or paid call is authorized by this feedback.

Next actor: engineer for bounded real recognition evaluation when credentials are available. No further B2 review approval is required. B1 actual-owner provisioning and hosted qualification remain separate pending items.


## B2 parity revision — September 28, 2026

[Completed parity matrix, behavior differences, evidence and exact launch](B2_PARITY.md). The same authenticated inventory now supplies Overview, Pokédex, My Cards, per-copy edition selection, local guide scenarios, sample hunts/missing singles and spoiler-safe saved-find replay. B2 collection/binder/goal/import/export/undo flows remain. The fresh copied baseline agrees on 859 entries, 251 species, 207 copies, 153 species owned and two saved hunts. Unresolved variants have no confirmed value; old guide totals remain explicitly conditional.

Private candidate evidence: `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/`; exact tested/pushed identity and final check results are in `handoff.json`. The original application and all owner sources remain authoritative until separately authorized cutover. **B2 is sufficient to proceed with B3 under Mike’s latest direction; no additional review stop applies.** B1 actual-owner provisioning, provider/source-rights qualification, hosting and real-device acceptance remain separate pending gates.


## PM checkpoint — proceed to B3

The parity candidate is `f2c876b1f70ee4643df70260bd8d2d023fc583c8`. Its 158-test, clean-checkout, browser and GitHub evidence remains bound to that candidate; later documentation updates do not relabel those runs. [PM summary and assigned next steps](PM_STATUS.md).

Mike initially responded “great” to the restored app and subsequently directed continued pre-alpha development without further routine approval requests. This supersedes the earlier B2 review-closeout stop. B1 account engineering and B2 collection/parity engineering are implemented; B3 local photo entry is implemented. Actual B1 owner provisioning remains pending independently and does not block B3 implementation. This does not claim hosted or pilot acceptance.

1. **Engineer:** B3 local engineering is delivered. Configure credentials when available and run a bounded real recognition evaluation; preserve the documented manual/fixture workflow and existing collection.
2. **Mike / engineer, independently:** complete actual B1 owner provisioning and verify its stable binding/preservation; the disposable review login is not that account.
3. **Later:** B5 hosting/source-rights/provider/real-device qualification, then B6 pilot. B4 local engineering is recorded below. Deployment and live cutover are not part of the current local milestone.

**Working convention:** stay on local `main` and sync remote `main`; create no branches unless Mike says otherwise. Preserve review data and credentials. Make routine reversible development decisions autonomously; do not restart or reinitialize the review environment merely for documentation work.

## B3 delivery

[Photo-entry implementation and configuration](B3_PHOTO_ENTRY.md) records the operable local flow, conservative limits, privacy/deletion behavior and verification boundaries. Fixtures are explicitly simulated. Actual owner provisioning remains independent. The later B4 delivery is recorded below; B5 hosted/real-device qualification remains open.

## B4 delivery

[Catalog expansion implementation](B4_CATALOG_EXPANSION.md): private requests and optional evidence sharing; reviewed aliases and distinct-requester merging; admin ingestion and atomic publication/rollback; English Gym Heroes (132 metadata entries); retry-safe resolution of an existing physical copy; synthetic second-game adapter. Frozen goal membership and existing inventory remain intact. B3 recognition remains simulated with zero real API calls; actual owner provisioning and B5 hosted/source/real-device qualification remain separate.
