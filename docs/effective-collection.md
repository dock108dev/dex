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

## Finite owner defaults

An explicit owner correction can attest a finite list of currently owned cards with
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
