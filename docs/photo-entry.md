# Photo entry and recognition

## Current capability

Photo uploads and manual review are supported. AI photo recognition is temporarily
unavailable. Executable Codex and direct OpenAI adapters, API token pricing, provider
launch code and the live evaluation script have been removed. There is no runtime
flag, credential or model setting that reactivates them. No image-generation feature
exists in this application.

`beta/scan_config.py` is the authoritative capability and effective-mode policy.
The server rejects analysis and retry requests; workers retire old queued or
processing AI jobs without deleting their images, prior results, attribution or
consumed reservations. New single-photo jobs use manual selection. Existing
account authorization, retention and confirmation rules remain in force.

## Photo workflow

Use `/scan/` to save a private photo, search the catalog, select the exact card and
explicitly confirm a physical copy. `/add-photos/` retains saved batches and their
review, correction, confirmation, report and undo controls. Its manual-photo link
opens `/scan/`; it no longer offers Identify or retry controls. Batch upload,
layout, retake and selection services remain available for manual workflows and
future recognition integration. Ordinary bulk entry remains at `/add-many/`.

Reopening photos or reviewing old suggestions never adds ownership. Unknown
identity, edition, language, finish and variant stay unknown until reviewed.
Photographs and model output do not establish condition, authenticity, grade or value.

## Provider configuration

The existing private `scan-config.json` still validates its storage contract:

```json
{"enabled": true, "mode": "manual", "ceiling_usd": 1.0, "user_ceiling_usd": 0.5}
```

`enabled` controls local photo admission. Historical `openai` and `codex_cli` values
are accepted by the local reader solely to preserve installations; they resolve to
manual admission, not provider execution. Staging retains its historical rejection
of `codex_cli` configuration and requires a complete stored configuration. Unknown
fields and invalid ceilings fail validation. Historical financial fields and usage
journals are retained unchanged, not repurposed or reset. The `fixture` spelling is
retained for engineering fixtures, but ordinary runtime capability policy makes
new photo entries manual. Tests use explicit doubles for synthetic matching.

OpenAI keys and Codex login are not application configuration. There is no automatic
paid-provider, CLI or cloud fallback. Do not erase historical provider attribution
or accounting just because the adapters are gone.

## Future Ollama recognition

Ollama is the intended future recognition backend. It is not connected yet, and
this source exposes no selectable Ollama photo mode. `photo_contracts.py` preserves
provider-neutral schemas, evidence prompts, crop geometry and image-size bounds;
`photo_matching.py` and the single-card matcher preserve catalog identity rules.
Uploads, revision checks, manual confirmation, reservations and data ownership
remain application responsibilities. A future adapter must use backend-only requests,
revalidate authority and revisions before publication, reject late results, retain
consumed attempts, and keep inference separate from collection writes. It must not
restore Codex/OpenAI fallback code.

Local-model [listing interpretation](hunts.md#planned-ollama-listing-interpretation)
is also planned, sharing the future backend adapter while retaining separate text
and image validation. There is no active app-user text AI to migrate. The private Ollama handoff
is not consumed by the launcher or backend. No private host belongs in production
configuration. Changing source does not update an installed wheel; use the normal
compatible runtime update procedure before claiming installed-app removal.

## Durable work and privacy

Uploads are bounded, re-encoded and stripped of metadata. Single-card jobs and
photos remain in the private database. The shared admission limit is 20 source
photos/account per rolling 24 hours. Unconfirmed images expire after seven days;
retained photos remain subject to their copy associations. Cancellation, deletion,
undo, copy removal and account revocation retain their existing cleanup semantics.
The provider removal itself does not delete photo or collection data.

Single-card worker selection remains process-local for ordinary serving. Historical
provider jobs are failed before selection; batch stages are cancelled without new
transmission or reservation. Prior results remain reviewable and failed single-card
jobs can be confirmed manually. Existing provider submissions cannot be recalled.

## Accuracy and evaluation

There is no live inference evaluation command. Provider-neutral schema, matching,
image normalization, manual review, confirmation and historical-state preservation
are covered by offline tests. Those tests do not establish real-photo recognition
accuracy or future Ollama readiness.

## Copy photo references

`scans.authorized_photo_rows` owns authorized single-card and retained-crop access.
Photo descriptors and serving share that policy, including expiry and removed-copy
checks. Display is local and private, with no recognition or network fallback.

## Multiple-card photo batches

Raw batch upload and manual crop/identity services are preserved. Their existing
storage and reviewed ownership boundaries are unchanged.

### Storage and shared review

`photo_batches` owns account-scoped batches, photos, crops, reserved stages and
collection associations. `photo_batch_images` performs in-memory normalization,
bounded crop transforms and advisory similarity calculations over explicitly supplied
bytes. Image processing has no storage, admission or ownership authority.

`enable-photo-batches` explicitly adds four local tables and two indexes. Startup
and GET requests never migrate. For operation and recovery, see
[photo-batch recovery](operations.md#photo-batch-recovery).

Sources are metadata-stripped and hashed from oriented pixels. Repeated photos
recover the account's original batch, including across batches. A restored database
cannot replenish deleted or uncertain admissions. Explicit same-object retakes
preserve crop/row IDs, clear old proposals and choices, and require new layout review.
Moving or deleting photos and correcting crops perform no recognition.

Included choices become ordinary bulk rows, one copy per crop, with stable draft
and receipt identity. Generic Review/Confirm enforces the photo lease and physical
copy guards. Only explicitly retained selected crops receive copy associations in
the same confirmation transaction. Originals and unretained crops are removed at
confirmation. Undo/removal revokes and cleans associated crops. Deleting all batch
images can preserve confirmed collection records; cancelling a linked draft also
revokes and cleans its photo inputs.

The independent journal is `.dex-photo-batches/<root-path-sha256>/journal.jsonl`
beside the private root, mode 0600 in 0700 directories. It preserves admissions,
consumed or uncertain attempts, sanitized usage and deletion tombstones independently
of database restore. Recovery retains it and reapplies cleanup before serving. Unsettled reservations charge their full allowance; crashes never trigger
automatic resend. `photo_payload_cleanup.py` cleans registered stale payloads left by older
installations after 90 seconds when the legacy lock is available. That lock filename
is storage compatibility only; the cleanup module cannot launch a provider.
Unregistered paths are never swept.

### Hard limits, reservations and Stop

Batch limits remain five source-photo admissions including retakes, 15 cards/photo,
75 cards/batch, 8 MB/source and 40 MB/batch. Images must be single-frame JPEG, PNG
or WebP, at least 200px per edge and at most 24 megapixels. Crop geometry is bounded
and checked. Original normalization uses a longest edge of at most 4096px; retained
crop images remain bounded by `photo_contracts.attachment`.

Stop cancels pending historical stages without deleting reviews or refunding
reservations. Independent consumed-attempt and deletion journals survive database
restore. No new AI attempt can be admitted. Unsettled historical reservations stay
charged; the absence of a provider never creates new capacity.

### Privacy, retention and deletion

Current photo workflows do not transmit images to a model service. Historical
provider retention is independent of local deletion. Unconfirmed originals and
crops expire seven days from admission. Explicitly retained per-copy images keep
their authorization requirements. Backups may retain old bytes; recovery reapplies
current revocations, expiry, deletion and consumed attempts. Never put private
images, credentials or raw model results in source control.

## Duplicate handling and saved reports

Photo-linked bulk confirmation treats the same set, card
name and collector number as one card: an already-present card is skipped, and
repeated rows within the batch add at most one new copy. Ordinary manual bulk
entry retains its explicit copy-quantity behavior. The check uses current effective
ownership, including declarations, and is recomputed at confirmation; intervening
collection changes require a fresh preview.

A reviewed **First edition stamp visible** checkbox records edition evidence.
An exact first-edition catalog selection also carries that flag. For an already
owned card, a single current supported copy can receive the checkmark without
creating a duplicate. Existing first-edition marks are never cleared by a later
unchecked photo. If there is no current physical record or several possible ones,
the report says **Needs review**, with no copy or edition mutation. Unsupported
first-edition sets still fail validation. For a new card repeated in a batch,
a reviewed first-edition row takes priority and only one copy is created.

After confirmation the saved **Photo addition report** lists Added, Already owned /
skipped, Duplicate / skipped, First edition checked, Needs review and Excluded,
with the card identity and first-edition checkmark. It is retained in the immutable
operation plan; reopening cannot replay additions. Undo reverses the batch's new
copies and edition updates together, subject to the ordinary intervening-edit checks.
It keeps the original report visibly labeled as undone.

## Delivered verification and owner review

The October 27 simplified-photo delivery replaced mandatory separate detection and
identity screens with one original-photo analysis and reviewed confirmation. Its
source and wheel suites each passed 162 targeted tests; installed client contracts
and served assets were checked. One supplied two-card image matched Alakazam Base
Set #1 and Kangaskhan Jungle #5 as holo Unlimited in 9.43 seconds. Confirmation added
two cards and reload retained the report; that example applied no first-edition flags.
Duplicate suppression and edition updates have targeted test coverage, not proof
from that particular two-card journey. The preceding duplicate/report delivery had
181 focused source/package checks. Dependencies were unchanged in these deliveries.

The local-only `reports/photo-simple-20261027/closeout.md` records this bounded
observation. It does not establish broad recognition accuracy or owner acceptance.
Current source no longer executes that provider workflow. These observations
refer to the older installed delivery, not present source capability. A compatible
runtime update and ordinary owner review remain separate from source tests.
