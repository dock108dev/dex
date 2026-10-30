# Effective current collection and reviewed editing

`beta/effective_collection.py:project` is the
shared account-authorized read model. `beta/collection_intents.py` supplies
ordinary card/source plans and effective before/after reviews through the existing
`collection.preview` → `confirm` → `undo` transaction service. Reads and previews
perform no collection writes, acquisition or artwork requests. A stored pending
operation confers no ownership.

## Independent fields and identity

| Field | Contract |
| --- | --- |
| Root `user_id`, `generation` | Verified account binding and checked collection generation for the complete read snapshot; frontend responses must agree with grouped reads before rendering |
| `cards[].present` | Current possession of a literal set/name/number card, independently of physical edition, finish, condition, scan and total |
| `species[number].present` | Current canonical #001–251 species presence; Trainer/Energy and other games do not create Pokémon progress |
| `cards[].established_total_quantity` | Positive exhaustive total explicitly attested by the collector, or null for unknown |
| `recorded_copy_count`, `recorded_copy_ids` | Matching active itemised records, including retained records omitted by a selected source; neither an exhaustive total nor an unconditional minimum |
| `current_copy_ids` | Matching active copies supported within the applicable source/removal boundary; distinct from retained records |
| `printing_ids` | Supported catalog candidate references; broad possession never qualifies every variant |
| `exact_printing_owned_ids` | Independently qualified current physical-copy identities |
| `identity_status`, `unresolved`, `conflicts` | Readable identity/order/evidence review state; no arbitrary printing/language/edition resolves a collision |
| `source_ids`, `operation_ids`, `source_boundary`, `scoped_sources` | Account-local evidence and source-selection boundaries ordered by collection generation |
| `printings[].established_total_quantity` | Null: no card total is allocated across variants |
| Parity `card_total_quantity` | A reference to the matching card's total, labelled “Total quantity for this card”; never a variant total or valuation multiplier |

Species totals remain null. Partial card quantities cannot establish a species
total. No nullable total enters legacy `pokemon_hunter.collection.derive`, which
coerces quantity into ownership. Artwork, market values, edition and grading
never establish possession or a total.

Every entry point re-resolves the principal. Reused projections bind `user_id`;
optional preloaded catalog/copy inputs must match authoritative current data.
A generation change during reading raises a reload conflict. New intent requests
use literal `set_name`, `name`, `number` and optional supported `language`.
Resolution requires authoritative catalog or retained declaration evidence.
Collisions stop that mutation with a readable conflict. Internal assertion IDs
are separate from canonical display-group IDs. Literal named/Dark/Light
identities, multi-card assertions and source bytes/hashes remain preserved.
An unidentified species/set mark is separate unresolved species evidence; it is
not silently assigned to a card or printing.

For example, an Ivysaur Base Set 2 #44 declaration without copy records is Owned,
with unknown total and zero recorded copies. Multiple candidate variants do not change that broad assertion.

## Reviewed intents and quantities

| Operation | Request and effect |
| --- | --- |
| `mark_owned` | Literal identity; establish broad card ownership with unknown total, no physical copy or advanced attributes |
| `card_quantity` | Literal identity plus required `established_total_quantity`; strict positive integer for exhaustive total, null to clear it |
| `remove` | Existing copy `id` and `revision`; “Remove this copy” removes only that record's support; other copies/declaration can keep the card Owned |
| `remove_card` | Literal identity; “Remove card from collection” means no copies remain owned; all matching active records become removed with incremented revisions, IDs/photos/attributes/history retained; old declaration/inherited records cannot revive possession |
| `declaration_correction` | Withdraw declaration support only; no physical record changes; independent explicit ownership or supported copies retain possession |
| `collection_correct` | Existing reviewed derived source correction, separately labelled; originals remain immutable, and selecting the derived source applies its reviewed replacement boundary |
| `source_select` | Retained account-local `source_id`, explicit `scope` and `replacement="replace"`; selection/reselection without creating a source row |
| `owner_declaration` | Original text/hash import and explicit selection; optional scope/replacement for regional replacement after full selection |

Totals reject booleans, fractional/negative/malformed values and zero. Zero
requires explicit remove-card intent; it never silently leaves an Owned card
with zero total. A positive total requires existing possession and must be
compatible with supported current matching copies. A fixed readable conflict
blocks contradictory proposals without deleting records or adjusting the total.
Resolving a retained copy that reveals a contradiction exposes a conflict and
makes the total unknown, without using resolution to establish possession.

Copy additions/removals invalidate earlier exhaustive totals. Metadata-only
edits preserve totals. Undo of a copy mutation does not resurrect its invalidated
older total; a fresh complete attestation is required. Attestation creates no
copy, condition, edition, grade, variant or financial value. Later confirmed
genuine copy addition or mark-owned can establish possession again after removal;
metadata edits and identity resolution retain their original admission.

## Source boundaries and preview agreement

Only confirmed supported operations with unique integer collection generations
provide order. Previews, creation timestamps, UUIDs and source hashes are not
clocks. Missing selected sources, duplicate/noninteger order and ambiguous
historical regional overlays remain explicit conflicts; new previews stop at
unsupported order rather than making an inferred selection.

Full selection/reselection replaces current broad presence and older quantity/
presence overrides using the pre-confirm generation, even if no source row is
created. Matching inherited records can describe a newly declared card; omitted
older copies stay retained and counted but cannot confer current presence.
Supported later copy additions and card intents apply after the boundary.

Explicit scopes are `full251`, `kanto` (#001–151), and `johto` (#152–251). A full
source may replace all cards or one region; a regional source may replace only
its own region. Regional replacement after a full source requires explicit
`replacement="replace"`. It replaces declarations, copy admission and card/
quantity overrides only in that scope. Outside-scope presence, quantities,
copy evidence and later edits remain identical. Full reselection supersedes older
regional boundaries and overrides. Legacy regional overlays lacking replacement
intent remain conflicts; their historical meaning is never inferred.

Plans contain `reviewed_effects`: added/removed literal cards and species,
quantity before/after, affected copy IDs, evidence conflicts and replacement scope.
Source-summary deltas use the effective current before/after state, including
supported later edits. The review shows copy disposition and preserved history.
Current dashboard, card/species adapters and no-goal missing lookup use this same
projection. Confirmation recomputes and compares the complete stored plan;
it never silently refreshes a stale preview.

## Transactions, dependencies and undo

The existing journal stores new intent in its plan JSON; no schema or database
migration is needed. Account-scoped operation IDs, strict request allowlists,
atomic application, collection generation, raw-row revisions and after-images
remain authoritative. Repeated confirmation returns the saved result; changing
input under an operation ID conflicts. A stale preview requires explicit preview
again before confirmation. Failure rolls back rows, operation state and generation.

Row after-image checks protect physical records. Journal-only card intents also
check newer same-card intents/record edits and source boundaries in their scope.
Source undo checks newer overlapping source/card/copy dependencies; undo never
erases newer intent. Existing source-creator dependency, retained goal/source and
successor guards remain. An older raw copy-removal undo may restore the record
without overriding a newer source boundary; the copy's original admission still
controls current possession. Exact row edits after an operation block its undo.
No undo creates a successor, refreshes a goal or assigns broad presence as an
exact-variant achievement.

## Callers, saved policies and preservation

| View or contract | Policy |
| --- | --- |
| Shared projection, collection dashboard, current card/species, no-goal missing/hunt | Effective current presence; card total, copy counts and variants independent |
| Saved declaration goals | Frozen source/species snapshot and membership |
| Other saved goals, goal-backed Shopping/lookup/Packs | Existing frozen membership and current qualified-copy rules |
| Legacy totals, valuation, original-app state | Existing qualified-copy/original contracts; no inferred broad totals |
| Historical JSON/CSV export/import | Existing copy/binder/goal/source-history contract; import does not restore the operation journal or attest current totals |

The export is labelled “copy and goal JSON export,” not a complete current-state
backup. Current intent survives restart in `collection_operations`; protected
database backups preserve it. No export/import schema, source text/hash, exact
copy/printing ID, goal membership/lineage or financial evidence is rewritten.
Fresh initialization, existing engineering roots and repeated legacy migrations
use their existing paths. The intent service uses existing journal records and transaction boundaries;
it requires no additional tables or backend-specific writes.

Group APIs consume these fields through the [canonical group contract](card-groups.md).
Private totals reference one mapped literal assertion; current ownership, archived
records and catalog projections remain distinct. UI editing delegates to the same
reviewed transaction helpers. For runtime updates and protected backups, follow
[operations](operations.md).

## Finite card defaults

An owner-role attestation can set defaults for a finite list of currently owned cards with
`card_defaults` through the existing preview/confirm/undo journal. The request lists
current effective card IDs, quantity `1` and variant `normal`; it does not apply to
future additions or to another account. Existing positive totals, qualified variants,
first-edition selections and copy notes are preserved. Multiple current copies without
an exhaustive total require an explicit total rather than silently becoming one.

The attestation supplies the displayed card total and a private normal-variant ownership
label. Known normal catalog children can show declared ownership; unknown catalog
edition/finish fields do not become exact printing qualification. No physical copies,
catalog records, prices or frozen goal policies are created or rewritten. Later explicit
quantity changes override the total; copy additions/removals invalidate the exhaustive
total under the existing policy. Later variant notes override the normal label. Removing
and re-adding a card, or selecting a newer source, clears the prior default. Undo checks
all affected card identities and rejects newer dependent edits or source replacements.

## Manual bulk entry

Use **Add Card → Add many cards** (`/add-many/`) to prepare one account-local
batch from the published catalog. The flow supports checklist selection, pasted
numbers and CSV without recognition or provider requests. Cards are added only
by confirming the reviewed operation. Installation and recovery use the explicit
[manual bulk operations](operations.md#manual-bulk-entry-and-recovery) commands.

### One ordinary flow, three entry paths

| Screen | Interaction and next state |
| --- | --- |
| 1. Add many cards | Choose **Add physical copies** (recommended first-use path), **Record known totals**, or **Mark cards owned**. The meaning remains visible in the header. Resume an account-local draft or start one; no card is added. Choose Checklist, Paste numbers or Upload CSV. |
| 2A. Set checklist | Choose a supported game, language and set. Show numbered card groups in numeric-aware order with literal number/name, existing possession, total or Unknown, and recorded/current copies separately. Search, select a range and select visible results; **Select all matching N** explicitly includes other pages. No selection is prefilled. Choosing a card never selects every variant. The batch summary shows hidden selections and their sets. Switch sets to append to the same draft. |
| 2B. Paste numbers | Select a set/language first. Parse explicit numbers/ranges and optional quantities using the grammar below. Display the expanded numbered rows and ambiguous matches. No fuzzy match is silently accepted. Multiple set blocks use separate set selectors; CSV handles mixed-set text. |
| 2C. Upload CSV | Download the current set-aware template or mixed-set template, then upload UTF-8 CSV. Show source row numbers, exact matches, errors, duplicate warnings and template/catalog version. Existing copy/goal JSON imports remain separately labelled **Restore copy/goal export**; they are not bulk-onboarding CSV. |
| 3. Defaults and exceptions | One visible defaults bar; one compact table with quantity, proposed identity and exception badges. Apply a default to selected rows, with a count and before/after warning. Open one row drawer only for exceptions, or multi-edit selected rows. Invalid defaults stay flagged on the affected rows; they are never silently dropped. |
| 4. Review changes | One generation-bound review combines current holdings, included changes, exclusions and warnings across all sets. Columns: identity/candidates, action, existing presence, established card total, current/recorded copy counts, proposed added copies or total, resulting presence/total and unresolved fields. Show supported exact-child qualification separately. Expand row provenance/advanced fields on demand. **Confirm batch** is the sole collection mutation; its review lists copy additions, ownership declarations and totals separately. |
| 5. Receipt | Show saved operation ID, actual applied/skipped counts, unknown totals, link to affected cards and **Undo this batch**. An interrupted response offers **Check saved result** using the same operation, never a new addition. |

Back, reload, choosing a set, changing defaults, previewing, reopening, deleting a
draft and cancelling all leave collection/goals unchanged. Preserve return/filter/
scroll/focus through the existing navigation service. Selection and review display 50 rows per page. The batch summary sits beside the
desktop checklist and before it on narrow screens. Keyboard checkboxes, named row
errors and a focused row editor keep the complete batch usable without rendering
2,000 forms or introducing nested scrolling.
Defaults and proposed changes remain readable at 320px and doubled text.

### Defaults and truthful applicability

The initial defaults are quantity **1** for Add copies only; language is the chosen
catalog scope (currently only `en`), with condition, edition, finish, variant,
grading and purchases **Unknown**. No default means normal/unlimited/NM. Quantity
is not silently defaulted for totals or ownership declarations. Common defaults
are visible before Review; row exceptions remain pinned when defaults change.
A default records a user assertion for selected rows, never catalog publication.

Edition/finish/stamp controls are selectors with **Unknown**, supported child choices
and explicit **Not applicable** where a catalog rule proves exclusion. They are not
unchecked binary flags. First edition, shadowless, unlimited, holo/reverse and stamps
are offered only for actual compatible children; use the exact combination, not a
cross-product of set-wide values. Keep raw catalog codes/IDs unchanged. Friendly
labels may group `first_edition`/`1st-edition` or `reverse`/`reverse-holo` visually,
but may not collapse separate printings. A provider-generated variant identifier
is a literal indexed choice, not proof of a physical distinction. Missing stamp
metadata never attests that the physical card is unstamped. Show its source
label or “catalog variant; details unavailable”; never invent a stamp name.

Unknown and a missing catalog option are coverage gaps. A collector can leave a
broad identity or retain an explicitly provisional copy with candidate IDs and the
unresolved fields. That does not select an arbitrary child. Unsupported physical
claims can be kept in user notes with a coverage warning, never converted to
catalog-qualified flags. Merely being in a set never records the pack a card came
from. Bulk onboarding has no pack-origin default.

Advanced multi-edit includes condition (`Mint`, `NM`, `LP`, `MP`, `HP`, `DMG`, or
Unknown), literal grading company/grade/certificate, existing account-owned binder,
location text, notes and optional purchase date/amount/currency. An unreadable
certificate stays unknown. A grade/certificate is the collector's supplied text,
not a verification. A certificate with quantity >1 requires separate copy rows;
one nonblank certificate cannot be cloned across copies. Repeated certificate text
across rows requires explicit “different copies” review or correction.

There is no separate copy-location field. Location is stored as a
visible `Location: ...` line in copy notes, with the composed notes previewed and
subject to the existing 2,000-character limit. Binder uses the existing binder ID;
foreign/removed binders fail. Do not auto-create binders from misspelled names.
Non-copy actions disable copy-only fields with “Not applicable to this
action”; supplied values must be removed or the action changed before Review.

Purchase values use the existing exact decimal/currency/date validators. An amount
is **per physical copy**, requiring explicit `purchase_basis=per_copy`; quantity >1
shows the repeated amount and extended count for acknowledgement. A batch/lot price
may be recorded once as draft/receipt context (`lot_amount`, `lot_currency`,
`lot_date`), never divided or copied to the individual purchase fields. No currency
conversion, valuation, fees, taxes or missing costs are inferred. Financial context
stays user-authored and is excluded from catalog/AI requests.

### Quantity and ownership actions

| Action | Required input | Proposed effect |
| --- | --- | --- |
| `add_copies` | Supported exact child or explicitly unresolved/provisional physical identity; positive `quantity` | Create that many new itemised records using the existing copy planner. Default 1 is visible. Existing presence never implies an exhaustive total. Copy creation invalidates an earlier total to Unknown under current policy; review shows that change. |
| `set_total` | Authoritative broad card identity already currently owned; `total` positive integer or literal `unknown` | Attest the exhaustive **card** total through `card_quantity`, or clear it to null. Create no copies; allocate nothing across variants. A total below supported current-copy count conflicts. An unowned card must first be marked owned in a separate reviewed batch; never silently turn the total into an addition. |
| `mark_owned` | Authoritative broad card identity; no quantity/total/copy fields | Establish broad possession with unknown total and no exact-copy assertion using `mark_owned`. If already owned, show **No change** and omit that intent, preserving its existing total/variant evidence. Do not reapply mark-owned just to force a total unknown. |

Zero is invalid in onboarding. Removing a card uses the existing explicitly named
Remove card action, outside this addition flow. Unknown total never becomes one
because one copy is recorded. Adding two copies to a card with declared total five
results in total Unknown, not seven. Setting total five with two recorded copies
creates no three extra objects. Duplicate physical copies do not enlarge a species
or printing checklist. Frozen goal membership/source/version/policy never changes;
only eligible current-copy progress may change under that goal's stored policy.

One card may have multiple `add_copies` rows for different copies/attributes. In a
single batch, reject overlapping `set_total`/`mark_owned`/`add_copies` actions for
the same broad identity, and repeated total attestations. This avoids order-dependent
implicit arithmetic. Mixed actions for different identities are allowed.

### Paste grammar and matching

Grammar: `items := item (comma | semicolon | newline) item ...`;
`item := literal-number ["x" positive-integer] | integer "-" integer ["x" positive-integer]`.
Whitespace surrounds delimiters; `x` is lowercase ASCII. Quotes around a number
force a literal token (`"RC1-RC3"` is one number, not a range). No free-form names,
prices or set names in this grammar. `1-3 x2, 8, 10 x3` expands 1/2/3 twice,
8 once and 10 three times. Range quantity applies to **each** number. Paste in
Mark owned disallows `x`; Record totals requires `xN` for every token, or
`number xunknown` to clear a total. A range never means total-for-the-range.

Only ascending ASCII integer ranges are expanded. `RC1-RC3`, `3-1`, negative or
fractional quantities fail with an example of separate literal tokens. Leading
zeros are preserved first. Try exact collector-number matching, then a unique
numeric-padding alias; never normalize alphanumeric/suffixed identities. A unique
prefix-before-slash alias is allowed only inside the selected set (`001` may match
`001/165`); an explicit denominator must match the catalog's denominator. Aliases
are resolved to the retained literal number and shown before confirmation. If more
than one card group or denominator fits, require a selection. Missing numbers in
ranges are row errors, not silently skipped; the paged preview includes every expansion.
Repeated/overlapping tokens are flagged rather than summed automatically.

Resolution order: authoritative printing ID (if supplied); exact game/set ID and
language plus literal number; exact set name or unique retained catalog alias plus
number; only then the bounded padding/slash aliases. Names may disambiguate only
when they exactly match; conflicting name/ID/flags fails. Never choose the first
candidate, guess a set by release year, translate card names or search a provider.
Multiple supported children require explicit child choice or **Keep variant unknown**.
A catalog row with unresolved fields remains unresolved even when it is the only
match. For multiple child candidates sharing one resolved card group, **Keep
variant unknown** creates a group-bound provisional copy (`printing_id=null`), with
server-validated group ID/literal identity, current candidate IDs/version and explicit
unresolved fields in `provisional_identity`. It never chooses a representative child.
Shared copy read/projection helpers count that admitted group-bound object as a
current/recorded copy and broad possession, while
exact-printing ownership remains empty. Apply the same source boundaries, total
invalidation, account checks and removal/undo dependencies as printing-bound copies.
Do not synthesize a separate mark-owned intent to make that object appear owned.
Fully unidentified provisional objects remain outside identified-card progress.
This group binding is journal-validated; arbitrary imported JSON alone
must not grant it. Resolving later changes that same copy, preserves its original
creation admission and confers no new presence after a removal/source boundary.
Ambiguous catalog-name/species groups block mutation until corrected;
missing coverage may instead become an explicit provisional copy, or be excluded.
Broad ownership/totals cannot target an unidentified provisional object.

### CSV/template contract (`dex-onboarding-v1`)

UTF-8, optional BOM, RFC-style quoting, unique headers, no macros/Excel formulas or
URL/photo/credential fields. This is an **adapter format**, not a replacement
for `dex-collection-v2`. Limits: 1.5 MB text; 2,000 source rows, 2,000 normalized
rows and 2,000 expanded copies/intents per draft; quantity 1–2,000 with aggregate
cap; 100 open drafts/account; 1,000-character location bounded by composed notes.
Reject oversized input before expansion. A larger collection uses explicit separate
batches/receipts, never hidden chunks or partial confirmation.

| Columns | Meaning / validation |
| --- | --- |
| `schema`, `row_id`, `action` | Required `dex-onboarding-v1`, stable unique source row ID (1–200 characters), and action. File rows may override the visible default action, shown as an exception. |
| `game`, `set_id` or `set`, `language`, `number`, `name`, `printing_id` | Catalog selectors. `game` is the registered key (`pokemon` now). Supply printing ID or set/number; a set-name alias must resolve uniquely. If redundant selectors are supplied they must agree. Optional exact name, not a fuzzy query. |
| `quantity`, `total` | Quantity only for add; total only for set-total. Positive integer, no booleans/fractions/signs/exponents. `unknown` means null only in total. Mark-owned accepts neither. Blank add quantity inherits visible default 1. Blank total is an error. |
| `edition`, `finish`, `variant` | Blank inherits an explicitly selected visible default; `unknown` overrides a default to unresolved. A nonblank value must identify a permitted exact child combination. `variant` is the exported literal token/JSON string, properly CSV-quoted. No ad hoc `stamp=true` or `first_edition=false` columns. |
| `condition`, `grading_company`, `grade`, `certificate`, `binder_id`, `location`, `notes` | Copy-only. Empty inherits the visible default; `unknown` clears inheritance to null for nullable attributes. Literal text `unknown` can be entered through the row drawer when it is intended as actual notes. Existing 200-character text / 2,000-character composed-notes checks apply. Grader+grade must be paired for a graded claim; no catalog price implication. |
| `purchase_amount`, `purchase_currency`, `purchase_date`, `purchase_basis` | Copy-only. Exact nonnegative decimal, max 12 integer/6 fractional digits, uppercase three-letter currency, ISO date; basis `per_copy` when amount supplied. Unknown remains null. No inferred USD/date. |

Draft envelope (outside CSV): defaults with explicit inheritance/clear states,
set/language context, duplicate decisions, optional whole-lot context, input hashes,
parser/schema version and catalog versions, stable draft/revision IDs. Persist the
normalized literal matches and exceptions; edits keep their source row IDs.
Never accept foreign `user_id`, copy IDs, operation state, revisions or goal fields
from this template. Re-exporting a template escapes spreadsheet-leading formula
characters in user text and includes an import-safe encoding indicator so escaping
is reversible, rather than executing or silently changing the value.

Examples below illustrate the schema, not any account's holdings or proposed writes.
IDs refer to catalog metadata; quantities and actions are examples.

```csv
schema,row_id,action,game,set,language,number,quantity,total,printing_id
dex-onboarding-v1,r1,add_copies,pokemon,Base Set,en,2,2,,52341b3a-8171-5d8b-a2f6-aa8817e809ed
dex-onboarding-v1,r2,mark_owned,pokemon,Jungle,en,17,,,
dex-onboarding-v1,r3,set_total,pokemon,Base Set 2,en,2,,5,
```

Row r1 is a valid **unresolved-edition/finish/variant** copy
selection, not an exact variant. Row r2 declares broad ownership only; if already
owned it is no change. Row r3 is valid only if currently owned and copy count
permits five; the UI checks the real current state. The template does not assert
that either fact holds for this account.

Ambiguous example: `pokemon / Prismatic Evolutions / en / 001`, action add, quantity
1, finish reverse and no variant matches ordinary reverse, Poké Ball reverse and
Master Ball reverse. Require a child choice or keep variant unknown with all
candidates retained. `Gym Challenge / 2 / holo` likewise does not establish first
edition or the error variant. Valid exact example: printing
`bd6a97c6-6760-5cc4-94b5-fc2ce0e7b1f0` is the catalog's first-edition holo child of
Blaine's Charizard #2, while its other unresolved fields retain their actual state.

Invalid examples: Base Set 2 with edition first-edition (existing explicit guard),
Base Set #2 with shadowless (not indexed), `151 / 001/999` against the actual
`001/165`, quantity 0 or `1.5`, an unknown extra header, a repeated `row_id`, a
foreign binder, nonblank copy attributes on mark-owned, an unowned set-total row,
or `$25` without a currency/basis. Show row + column + safe reason + correction;
keep the original input. Do not echo secrets, render pasted HTML, or drop invalid
rows behind a duplicate policy. **Confirm** is disabled while any included row has
an error. **Exclude errored rows** requires an explicit reviewed exclusion count;
excluded rows remain in the draft, outside the confirmed operation.

### Duplicates, durable drafts and interruption

Existing holdings are informative, never proof that another physical object is a
duplicate. Three separate questions are shown: repeated source row, same printing
already recorded, and same physical card seen again. Stable row/copy identity is
a hard replay constraint; printing equivalence is only a warning. Default for a
possible accidental repeated input is **Needs review**. Choose **Same copy / skip**,
**Different copies / add these N**, or correct the row. Existing copy service
`skip`/`allow`/`reject` policies remain available, but bulk entry resolves each row first;
“skip existing printings” must not erase an intended second copy. All skipped rows
are validated and shown. Broad already-owned marks become no-ops; totals are
attestations, never additive duplicate merging.

Account-scoped durable draft record: `(id, user_id, schema, revision,
state, input_json, input_hashes, created_at, updated_at, expires_at,
confirmed_operation_id)`. Use a small dedicated `collection_drafts` table through
the existing database/transactions, not collection rows or an unvalidated browser
blob. CAS revision guards multiple tabs; a stale tab reloads explicitly before editing.
The draft contains user inputs/candidates, never provider price data or credentials.
Explicit Save and Review POSTs write draft state only; navigation never autosaves or confirms. Unsaved edits are visibly labelled and guarded on page exit. Reads and Resume do not renew expiry or confirm.
Save/resume for seven days since explicit edit; show expiry. Delete/cancel tombstones
prevent stale tabs from reviving a draft. Logout clears browser buffers and denies
access; the same account may resume after normal sign-in. Revocation blocks reads/
writes immediately; the existing revoke service clears mutable draft inputs while retaining replay history. Operator `bulk-cleanup` clears expired/revoked mutable input without deleting operation history. Unrelated accounts never see it.

States: `editing → ready → previewed → confirmed`; an edit from ready/previewed
increments revision and invalidates the old preview. `cancelled` and `expired` are
terminal. Validation errors retain editing state. Confirm atomically binds the exact
draft revision/input hash to one existing collection operation and its receipt.
A stale collection generation or changed catalog/child/binder requires an explicit
new review, never silent refresh at confirmation. Remove invalid catalog choices
only by user correction/exclusion; preserve original row evidence.

A file's byte hash + parser version + defaults revision identifies an upload in
that account; identical reupload resumes its draft or receipt, not another batch.
Canonical row-ID/content fingerprints also flag reordered/whitespace-only reuploads
within the draft. Reusing a row ID with changed content conflicts rather than
skipping it. A same-content new batch is possible only via **Add another physical
batch**, with a new batch identity and visible duplicate review; content alone cannot
prove physical duplication. Keep a minimal confirmation fingerprint/operation mapping
with retained collection history even after draft expiry, so an old exact file
reupload returns the receipt. Editing defaults after confirmation is a new explicit
batch, never a way to mutate the saved operation.

Before dispatch, cancel discards only draft inputs. During collection confirmation,
show **Checking saved result**: a committed database transaction cannot be recalled
by closing a tab. Reauthorize and query the saved operation ID. If confirmed, offer
Undo; if still previewed, cancellation invalidates it atomically against confirmation.
The cancel/confirm race uses the same lock: exactly one result wins. No successful
cancellation may subsequently commit from a late tab. Network failure never retries
with a fresh operation ID. Undo checks every row after-image and journal-only intent/
source dependency first, then reverses the entire batch atomically or refuses with
a readable conflict. No partial best-effort undo. Existing copy-total invalidation
rules remain: undo of added copies does not resurrect an older exhaustive total.
Deleted photo bytes cannot be reconstructed by undo. Frozen goals stay frozen.

### Shared-service implementation boundary

The bounded `bulk` kind uses the existing collection request/plan/confirm/undo
machinery, deterministic per-row copy identities and one generation increment.
Reviewed copy creations and `card_intents` belong to one operation, rather than a
loop of independently committed confirmations. Inputs are normalized before the
immutable preview. `augment_plan` supplies complete effective changes, including
total invalidation and source-boundary consequences.

The shared effective projection consumes `card_intents` and now includes
bulk admission in `ADDITION_KINDS`, complete pending/group-bound provisional-copy simulation and bulk-aware
post-attestation invalidation/dependency checks. Resolve totals/ownership from the
authoritative literal group, including catalog cards absent from current holdings.
Do not fabricate a source declaration to get around an unsupported identity.
One batch rejects mixed actions on the same broad identity, so no within-generation
operation ordering is invented. Preserve all existing export/import and goal policies.


### Service ownership and migration

`bulk_formats` owns CSV/paste parsing, templates, envelopes and input fingerprints.
`bulk_input` resolves current groups/aliases and validates all rows, including skipped rows. The single supported-child selector shows actual
combinations; **Keep variants unknown** and **Different copies** can be applied to
all explicitly checked draft rows. Both selection and Review page 50 rows at a time.
The review includes server-simulated resulting presence, total and current/recorded
counts for each broad identity across the complete batch.

`collection_drafts` owns seven-day edit leases, revision checks, cancellation,
source/row fingerprint aliases and immutable receipt linkage. An explicit new physical
batch has a stable client UUID so an uncertain creation response is recoverable too.
`collection_replays` retains minimal input/row fingerprint mappings after expiry.
An edited draft retains original upload aliases; reupload recovers the actual reviewed
receipt. Changed input reusing a source-row identity requires correction in its draft
or a separately explicit new batch. Matching printings alone never prove duplication.

`collection_plans.build(bulk)` uses its existing copy constructor and one
`card_intents` list; `collection.confirm` binds the receipt inside its transaction.
`copy_identity.binding` admits a null-printing group binding only from that copy's
original confirmed bulk creation image. Arbitrary imported/provisional JSON confers
no such authority. Shared card-group reads include these records and expose ordinary
edit/remove/explicit supported-child resolution. Resolution retains original admission.
Exact-printing and frozen goal policies still exclude unresolved copies where required.

`enable-bulk` creates only two tables and an account/state index through existing
transactions; it neither rewrites existing tables nor alters schema versions for legacy
copy/goal export. Startup and page reads never migrate. Do not rerun migration for
ordinary use; an uninitialized development root requires explicit enablement.
See [manual bulk operations](operations.md#manual-bulk-entry-and-recovery).
`bulk-cleanup` is explicit maintenance, not a new scheduler.
The receipt/replay journal and complete protected database belong in a backup; the
ordinary copy/goal export still cannot restore all current state. Managed price
snapshots remain excluded from backups. A runtime without bulk/group-bound support
cannot interpret that confirmed history. Recovery requires a compatible runtime or
forward repair against the latest database.


The two manual JSON adapters (`/api/bulk/save/`, `/api/bulk/parse/`) have a dedicated
32 MB transport bound to accommodate JSON expansion of independently validated rows.
This does not raise the 1.5 MB CSV, 2,000-row/copy, ordinary-request or single-card/photo
limits. Other paths retain their existing ingress rules. The draft stream reader
checks the same bound before decoding; it never disables global request limits.


### Photo rows in the shared review

Photo batches use the same `dex-onboarding-v1` input and
atomic bulk planner/confirmation/replay/Undo. Each crop has a stable source-row
ID and quantity one. Identity proposals never select a catalog child; the person
chooses the supported printing or explicitly keeps the catalog variant unknown.
Unreadable/unsupported crops can remain excluded. Retakes of the same physical
objects preserve row IDs and invalidate prior choices. Cross-photo or manual-row
physical duplicates need explicit review; matching printing IDs never merge cards.

The linked photo lease and distinct-copy guards apply to generic bulk endpoints
as well. Shared review can correct supported identities/attributes or exclude a
row; it cannot multiply a crop into several copies or reinclude an excluded crop
without photo review. The receipt names excluded crops. Explicit crop retention
is bound to deterministic created copy IDs in the same confirmation transaction;
no original group photo is attached to every copy. Image deletion can preserve
confirmed copies. Cancellation/Undo/removal and account revocation remove access
immediately and clean authorized bytes; tombstones prevent resurrection on recovery.

Photo batches require separate local activation. See the
[photo contract](photo-entry.md#multiple-card-photo-batches) for image admission,
recognition, retention and recovery limits.

## Durable account-read representation

The private evaluator is shared with explicit account preparation and bounded
identity updates. The public `project` entry point retains its full validation
and account/generation checks. Derived records never define a second ownership
policy or authorize mutation. See [account reads](account-reads.md)
for source-boundary, unknown-quantity, species, frozen-goal and recovery contracts.
