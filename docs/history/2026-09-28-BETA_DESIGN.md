# Collection beta — data and workflow design

## Collecting presentation maintenance — October 6, 2026

Current source uses the shared Desktop Starter 02 task hierarchy and accessibility
guidance, retaining DEX colors and navigation. This supersedes the earlier statement
that shared requirements were unavailable for that earlier pass.

Pokédex places ownership, common filters and pack actions before compact species
rows. Card filters and collection recovery remain reachable disclosures. Selected
lookup is disabled until a Pokémon is selected. Pack lookup places products before
membership lists; saving remains directly available while naming, references and
history are secondary. Unknown contents, documented-count meaning, stock check
dates, shipping uncertainty and refusal to recommend remain beside the results.
Stored values, forms, calculations, permissions and saved snapshot contracts stay
unchanged. Initial collection failure now offers Reload collection.

Matched current dirty-source previews use actual templates/JavaScript with wholly
synthetic intercepted responses: 1280×900 and 390×844, populated, empty, error,
initial loading shell, saved, missing products and unverified contents. On phone,
first species row moved from y=1196 to 776; first product from y=3191 to 820;
Save lookup from y=822 to 592. Keyboard selection, dialog focus return, disclosures,
44px buttons, no horizontal overflow and 200% desktop text scale pass. The eBay
regression covers 12 synthetic states; its pre-existing reveal focus-return gap
remains a separate follow-up. The initial loading shell is not a delayed runtime
qualification. Backend checks: 61 focused tests passed after restoring retained
saved-result labels; JavaScript syntax, harness Ruff and diff whitespace pass.

Evidence: [matched previews and measurements](../../evidence/collecting-clarity-20261006/),
[repeatable harness](../../scripts/verify_collecting_clarity.py).
Source-only; installed beta, owner data and owner acceptance remain separate.


Updated: September 27, 2026. **B0 migration, B1 local authentication and B2 collection workflows are implemented; B3 local photo entry is implemented; B4 local catalog onboarding is implemented; hosted workflows remain target design. Actual owner provisioning remains pending.**

[B2 implementation and verification](2026-09-28-B2_IMPLEMENTATION.md) records the shipped local slice and its limitations.

[Authoritative roadmap and stage status](2026-09-28-ROADMAP.md) · [Current implementation](2026-09-28-APP_SPEC.md)

## Current scope

The [roadmap](2026-09-28-ROADMAP.md) now targets Mike alone on the existing localhost app. Shared data/workflow contracts below remain useful; hosted, cross-device, separate owner-bootstrap and pilot provisions are deferred, not prerequisites for local use. Preserve the working login and collection.

## Local presentation cleanup — September 28, 2026

The active authenticated Overview, Collection and Scan/Add screens retain the
existing colors, navigation and data contracts. The header now identifies the
local collection instead of a B2 rehearsal. Collection places Add beside the
heading, omits empty notes and groups purchase/grading details in a disclosure.
Overview keeps progress, confirmed coverage, guide dates and uncertainty visible;
assumed-grade estimates and the rarity table are secondary disclosures.

Scan/Add puts an existing review before the upload form, places Cancel beside the
review heading, and explains why confirmation is disabled. Provider photo transfer,
subscription limits, identity uncertainty and explicit confirmation remain visible.
Usage details, another upload, retention details and history are separately
available. The initial upload form is expanded; existing review/confirmation steps
are unchanged. No calculations, stored values or account permissions changed.

No shared Starter requirements or adoption version were found in this repository;
the existing components and local workflow guidance were used. Historical screenshots
were not used as the current baseline. Baseline UI files came from `a18baf6` (the
same UI source present at the start of this pass); prior uncommitted hardening
changes did not modify these UI files.

Validation: `scripts/verify_ui_cleanup.py` renders actual templates and JavaScript
with intercepted synthetic API responses. It never connects to the owner app or a
provider. Matched before/after captures cover Overview, populated/empty Collection,
new upload and ready/failed review at 1280×900 and 390×844. Additional after checks
cover processing/cancel, saved/undo and collection-load failure. Checks cover no
horizontal overflow, 44px buttons, keyboard disclosure toggles, confirmation
checkbox gating, focusable Cancel and doubled root text size. This is Chromium
layout evidence, not real-phone, camera, end-to-end storage or owner acceptance.

Retained captures and metrics: `evidence/ui-cleanup-20260928/` (ignored synthetic
evidence). At desktop size the Collection Add button moved from y=484 to y=151;
at narrow size from y=574 to y=366. Narrow ready-review confirmation moved from
about y=1953 to y=1404, with the same synthetic photo and fields. It still requires
scrolling; review and Cancel are now visible much earlier. The comparisons measure
layout, not user task speed. JavaScript syntax, repository lint/format checks and
43 focused parity/scan tests passed; no server was restarted.

Separate follow-ups, not implemented here:

1. Scan/Add's upload handler selects `#upload button:last-child`, which matches the
   camera button nested in its paragraph before the submit button. Confirmed in
   source: the intended submit control may remain enabled during upload. This is
   an interaction-state bug beyond the chosen presentation changes. Next: target
   the actual submit button and test an in-flight upload plus a failed response.
2. My Cards and Collection are separate destinations, and Scan/Add has a shorter
   navigation list. The inconsistency is confirmed; whether it confuses the owner
   needs verification. Changing navigation is outside this cleanup. Next: review
   the two destinations with the owner before combining or renaming them.

## Product boundary

One shared collection platform, with Pokémon first and game-specific catalog adapters. Existing Vintage 251 rules become a named, versioned goal template. They must not become global rules that reject Yu-Gi-Oh!, Digimon, sports cards or Pokémon outside species 1–251. A user may own any supported printing even when it contributes to no active goal.

The first owner account is Mike's `admin`. Preserve his existing inventory and Pokédex; create other users with empty private inventories. B1 implements isolated account provisioning and access checks; actual owner credential entry remains pending. See [B1 implementation](2026-09-28-B1_IMPLEMENTATION.md). Credentials never belong in this document or seed data.

## Shared data model

Use stable internal IDs, not names or raw card numbers as database identities. Keep external-provider IDs in mappings so changing sources does not recreate ownership. Store collector numbers as strings; prefixes, suffixes, leading zeros and fractions may be meaningful.

| Entity | Purpose and minimum fields |
| --- | --- |
| User | Stable ID, auth-subject mapping, display/login name, role and account state |
| Game | Stable game key, display name, adapter/version, supported capabilities and release state |
| Set | Game ID, internal ID, source mappings, name, aliases, language/region scope, release metadata, catalog version and coverage status |
| Printing | Set ID, collector number, language, edition, finish/variant identifiers, source provenance and typed game attributes; unresolved attributes are explicit |
| Owned copy | User ID, printing ID or provisional identity, binder, condition, purchase amount/currency/date, notes, optional grading details and creation/import provenance |
| Binder | Private user collection grouping; membership does not clone a physical copy |
| Goal | User ID, template or custom checklist, versioned membership/rules and completion policy |
| Goal item | Printing, species/entity or explicit predicate to satisfy; separate from inventory |
| Scan job | User ID, private asset IDs, state, versioned recognition output, candidate IDs, unresolved fields, timings/cost and operation ID |
| Confirmation | Scan/job or manual operation ID, chosen printing/provisional copy, user edits and resulting copy ID |
| Catalog request | Game/set hints, normalized deduplication key, state, demand count, source references and admin decision history |
| Request evidence | Submitter, private evidence references, consent scope, extracted fields and review state; separate from public catalog metadata |
| Catalog import | Source/version/rights record, preview diff, validation results, publish state and rollback reference |
| Feedback | Suggested identity versus confirmed identity, error reason, version context and optional shared-improvement consent |
| Mutation/import batch | User ID, idempotency key, created/changed copy IDs and undo information |
| Price observation (optional) | Printing/condition basis, amount/currency, source/as-of date and observed versus estimated provenance |

A physical copy has one inventory identity. Quantity is derived from copies with the same printing; fast quantity entry can create multiple copies in one batch. A copy can satisfy several goals without multiplying quantity or value. Goal completion normally counts distinct required identities, not spare copies. A card marked sold/removed no longer contributes; retain sufficient change history for intentional undo.

Do not force an unresolved edition into a standard-edition printing. A provisional copy may carry partial fields but is excluded from exact-printing completion and exact pricing until resolved. Preserve prior attribution when catalog corrections merge or retire IDs. Catalog removal must not cascade-delete owned copies; use redirects or archived printings.

Store money with exact decimal/minor-unit semantics and explicit currency. Missing purchase price is not zero. Distinguish owner-entered condition, an actual recorded graded slab and hypothetical grade-value scenarios. Do not infer grade or authenticity from identification success.

## Migration from the current local app

Current authority is `config/pokedex_251.json`; `sources/confirmed-ownership.json` is import provenance and `config/pokedex.json` is legacy history. Never rebuild current ownership from those older inputs. Read current first-edition selections and any later edits directly from the live authority at migration time.

1. Back up and hash current authority, provenance, catalogs, assets and databases. Use a consistent SQLite backup if the local app is running. Do not copy a live database in a way that loses pending journal/WAL contents.
2. Import the shared catalog with mappings from legacy card IDs. Resolve edition variants where evidence supports them; retain uncertainty elsewhere.
3. Import each owned record as one owner copy, preserve edition selection/provenance, and recompute Vintage 251 under the existing eligibility rules. Check all identities and flags, not only totals.
4. Preserve saved hunt rows, sample/live labels, request settings and raw evidence. Associate migrated personal history with the owner only. Keep original databases readable even if an optional module is not enabled in hosted beta.
5. Preserve the goal's exclusions: Dark, trainer-owned, Light/Shining and other non-normal names do not fill the existing Vintage 251 species slots. They remain collectible inventory. Do not apply these rules to full-set completion or other users' custom goals.
6. On a disposable target, repeat the import and verify no duplicates. Rehearse restore and reconcile counts against the source snapshot. Capture source hash, importer/schema version and mapping evidence.
7. Provision the first owner via a controlled bootstrap before public access. At cutover take a final snapshot with writes paused and recheck any changes since rehearsal. Switch authority once. Keep source files and a rollback/export plan for subsequent database changes.

Current documentation-only read: 207 owned printings, Kanto 133, Johto 20, total 153; one first-edition selection. These are comparison points for this snapshot, not instructions to overwrite future owner edits.

## Accounts and access

Private records always carry a user ID derived from a verified session, not trusted from a request body. Enforce the same ownership checks for API reads/writes, signed photo URLs, exports, worker jobs and deletion. Catalog data is shared; inventory and uploaded evidence are private. Keep admin catalog publication separate from ordinary collection editing.

Use an established auth implementation and a supported secure password setup/reset path. Never implement a shared hard-coded `admin` password or select privileges by comparing the username. Record only role and stable identity in application data. The supplied owner password is not a source/configuration artifact.

Implement invite-only onboarding and access recovery. Provider choice must support the owner's desired login or an explicitly agreed equivalent; no recovery email is assumed. Logging out/revocation must invalidate usable sessions under the selected auth mechanism. Test two independent accounts and a non-admin attempting admin operations.

## Photo-entry state machine

`created → uploaded → queued → analyzing → needs_confirmation → confirmed`

Other terminal/actionable states: `needs_better_photo`, `unsupported`, `failed`, `cancelled`, `expired`. A network timeout is not an unidentified card. A pending job is not an owned copy. Cancelling during processing prevents a later worker result from adding anything.

1. User captures/selects one front image and optionally a back/close-up. Explain that identification sends the selected image to the configured API provider. Validate actual file type, size and dimensions; reject invalid uploads, normalize orientation, strip unnecessary metadata and store privately.
2. Create one durable job with bounded retries and an idempotency key. Downsize within a tested recognition budget while retaining enough collector-number detail. Do not accept arbitrary user URLs as server fetch targets.
3. Recognition extracts candidate game, name, set/code, number, language, edition, finish and visible clues with unresolved fields. Treat image text as untrusted input; it cannot instruct tools, publish catalogs or alter accounts. Validate structured responses before use.
4. Adapter-specific matching searches the verified catalog, checks number/set/variant consistency, and returns a bounded candidate list. Model confidence alone cannot establish identity. Require supporting visible fields and explicitly represent uncertainty.
5. Show photo, likely printing, alternatives, missing details, duplicate warning and proposed copy details. Ask for a better photo or manual selection when necessary. Confirmation requires the user to review; choosing a match does not automatically infer condition or grade.
6. Confirmation creates the copy transactionally under one unique operation ID. Repeated clicks/retries return the same result. Adding an intentional second physical copy creates a new operation. Show the resulting goal changes and undo.
7. Record correction feedback and model/prompt/catalog versions for measurement. Photo sharing for global improvement needs separate opt-in; ordinary confirmation does not give blanket permission to publish the image.

Set retention defaults before pilot: distinguish permanent owner-chosen collection photos from temporary recognition uploads and optional evaluation evidence. Publish actual periods once selected, implement expiry and deletion, and explain any provider retention separately using current provider documentation. Remove image access when its owner account is deleted; backups need a stated expiration policy too.

OpenAI implementation should verify current model support, image limits, pricing and data handling when B3 begins. Relevant official references: [Images and vision](https://developers.openai.com/api/docs/guides/images-vision), [Model optimization](https://developers.openai.com/api/docs/guides/model-optimization). No model, unit price or automatic training capability is promised by this plan.

## Unknown scans become onboarding requests

Support three cases: known game/new set, known set/unmatched printing or variant, and unknown/unsupported game. Ask for manual game/set hints when useful; preserve the original extracted hints separately from confirmed fields.

The user can choose **Save unidentified card** and optionally **Request catalog support**. Saving creates a private provisional copy only after confirmation. A request is demand evidence, not an assertion that the suggested set exists. Never discard a user's saved card because its request is rejected or merged.

Request deduplication uses normalized game, language/region, set code and reviewed aliases, with candidate merge suggestions when uncertain. Names alone are insufficient. Preserve all requesters and attribution when merging. Rate-limit requests; distinct users count once per set for demand ranking. Do not expose their photos, names or collections in a public request list.

Admin workflow:

1. Triage request, distinguish unreadable photo from absent catalog, and correct/merge hints.
2. Find a suitable catalog source; record provenance, version, coverage and permitted use for metadata/images separately. A scan can identify a lead but does not authorize copying a source.
3. Ingest into staging and preview new/changed/conflicting printings. Keep unavailable image/price capabilities optional.
4. Validate stable IDs, counts, required fields, known variants and sampled references. Label partial catalogs as partial; never generate a full checklist from guessed numbering.
5. Publish atomically with version and rollback reference. The same process handles routine catalog updates.
6. Re-match waiting provisional copies. Present a proposed resolution to each user; do not silently change uncertain ownership. Accepting a match updates the existing copy, preserving notes/photos/provenance and avoiding a second copy.
7. Show in-app request progress and available matches. External email/push is a later option, not required for onboarding.

Rollback unpublishes faulty coverage or restores the previous catalog view, while retaining any IDs already referenced by inventory as archived records. Reconciliation is versioned and reversible; never delete owners' cards to roll back an import.

## Game adapter contract

Each adapter supplies game metadata, set/printing normalization, identity/variant rules, supported source importers, scan extraction hints, matching logic, display attributes and optional goal templates. It declares capabilities such as catalog, scanning, images, pricing and hunt support separately. A game may support inventory/manual entry without scan identification or prices.

Core code owns auth, copies, binders, goals, uploads/jobs, confirmation, requests, import review, export and admin operations. Adapters do not supply separate user tables, scanner applications or parallel inventory stores. Typed extension attributes allow game-specific fields without requiring them globally.

Examples of adapter differences to accommodate, not claims of implemented coverage:

- Pokémon: species numbers, set symbols, edition/finish variants and Pokédex goal templates.
- Yu-Gi-Oh!: set/printing codes, language, edition and rarity/finish; card name alone cannot identify a release.
- Digimon: card numbers, set releases and alternate-art variants; a printed identifier may need additional variant evidence.
- Sports: sport, season/year, manufacturer/brand, player/team, inserts/parallels and copy-specific serial numbering/autograph attributes.

Validate this boundary with a synthetic second-game fixture before declaring the foundation extensible. Publish real game support only after source review and representative identification evaluation. Easy expansion means a reusable onboarding process, not a claim that all games already work.

## Set and custom-goal behavior

- **Track set:** subscribe to a catalog checklist. Adds no ownership.
- **Add owned set:** preview an exact checklist and variant scope; show existing copies and whether to skip already-owned printings or intentionally add duplicates. Explicitly confirm the batch, then allow undo without removing older copies.
- **Request a new set:** create a catalog request; adds neither a verified checklist nor ownership.
- **Custom goal:** explicit checklist or bounded rule within supported catalog coverage, such as Vintage 251 or selected Gengar printings. Show the selected catalog scope; do not promise every printing globally.

Version goal membership. Newly published sets do not silently move a completion denominator unless the user chose a dynamic goal and is shown the change. Base-set completion, variants/master completion and species completion are separate policies. Unknown checklist coverage means completion is unavailable or qualified, never a fabricated 100%.

## Improvement and measurement

Keep a reviewed correction library separate from the published catalog. A user's confirmation is useful feedback but may be wrong. Review high-impact corrections, apply provenance checks, and test prompt/matcher/catalog changes against held-out examples. Do not use evaluation examples as tuning inputs and then report their score as independent performance.

Record accuracy by supported set/variant and image quality, unresolved frequency, wrong-confident matches, correction effort, time to confirmation, API failures, cost per attempt/success and catalog-request backlog. Retain model/prompt/matcher/catalog versions so regressions are attributable. Improvement does not require fine-tuning; API requests do not learn permanently just because a user clicked confirm.

The first beta must remain useful when scan identification fails: manual search/add and private provisional copies are permanent paths, not temporary development workarounds.

Local B3 implementation, retention and provider configuration: [B3 photo entry](2026-09-28-B3_PHOTO_ENTRY.md). Target beta recognition thresholds remain unqualified until real evaluation.

Local B4 request, consent, publication and resolution contracts: [B4 catalog expansion](2026-09-28-B4_CATALOG_EXPANSION.md). Synthetic adapter evidence does not establish real second-game coverage.
