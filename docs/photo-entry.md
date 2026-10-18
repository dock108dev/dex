# Photo entry and recognition

Photo entry accepts private card photos, shows identity clues and catalog matches,
and requires confirmation before adding a physical copy. Manual matching and
provisional entries work when recognition fails or catalog coverage is missing.
Model output does not establish authenticity, condition, grade or value.

Single-card entry uses `/scan/`. Multiple-card entry uses `/add-photos/` and
requires explicit capability enablement on the installation. Opening
a page never enables a feature, migrates storage or starts recognition. Real-photo
recognition accuracy remains unmeasured.

## Provider configuration

The private root's `scan-config.json` selects a provider:

```json
{"enabled": true, "mode": "manual", "ceiling_usd": 1.0, "user_ceiling_usd": 0.5}
```

| Mode | Requirement and behavior |
| --- | --- |
| `manual` | Default for ordinary new roots; choose identity yourself |
| `fixture` | Simulated results for tests and explicitly synthetic development roots |
| `openai` | `OPENAI_API_KEY` in the server/worker environment; sends image bytes to the API |
| `codex_cli` | Local only: compatible `codex` executable on PATH with its own saved authentication; sends images through the CLI |

`beta/scan_config.py` validates these four keys. Other keys fail rather than act as
ignored provider or fallback settings. Staging stores a complete configuration in
`beta_operations` and supports `manual`, `fixture` and `openai`; copied import and
startup reject `codex_cli`, including disabled configurations. Missing persistent
staging configuration requires the staging migration; reads never invent defaults
or reset reservations. Local roots retain manual defaults when the file is absent.

Provider changes affect new work. Queued jobs from a different provider fail instead
of switching silently; running calls retain their original provider. Disabling scans
cancels CLI work but cannot recall an API request already sent. Preserve ceilings
and reservations when changing modes. Missing or incompatible credentials leave
manual entry available; there is no automatic provider fallback.

`beta/scans.py` owns the `dex-photo-v1` API request shape and cost calculation. Each
API attempt reserves $0.05 before transmission, with maximum lifetime ceilings of
$1 per root and $0.50 per account. Failed or cancelled calls retain reservations.
Reported usage is an estimate, not an invoice. Review rates and the reservation
bound before changing the model or payload size.

Model names and CLI flags are pinned in the recognition adapters. Check provider
support and protocol compatibility before changing them; recognition accuracy is
not established by the model identifier alone.

`beta/codex_recognition.py` pins the CLI model and required flags. A private temporary
directory, environment allowlist, disabled tools/config/rules, shared process lock
and 75-second deadline bound each attempt. Action events reject. Payloads are removed
on ordinary exit or cancellation; hard OS termination cannot guarantee cleanup.
Private `codex-usage.jsonl` records attempts and reported usage separately from API
dollars. Remaining subscription capacity is unavailable and is never represented
as free or unlimited. Incompatible CLI protocols fail explicitly.

## Durable work and privacy

Uploads are validated and re-encoded without image metadata. Single-card jobs persist
in the inventory database; provider calls occur outside database transactions. After
120 seconds, interrupted claims become failed and need explicit retry. At most two
provider attempts are allowed per job, without automatic retry of uncertain calls.
The shared admission limit is 20 source photos per account per rolling 24 hours.

Unconfirmed uploads expire after seven days. Confirmed photos remain associated
with the copy. Cancellation and undo delete image bytes. Copy removal and account
revocation block access immediately; worker cleanup removes bytes. Backups may retain
old data until they expire or are removed. Sharing a photo for a catalog request
requires explicit consent.

Confirmation is idempotent; adding an intentional duplicate is a separate action.
Undo checks for intervening changes. Edition and variant clues remain suggestions,
not automatic assertions. See [failure recovery](ERROR_HANDLING.md).

## Accuracy and evaluation

Synthetic fixtures and transport controls do not measure real-card accuracy. The
optional `scripts/evaluate_codex_photos.py` requires a labeled, consented image set;
inspect its help and limits before use. It sends real images to the CLI provider
and is separate from offline tests. Accuracy claims require an explicit evaluation
with reported denominators, uncertainty, unreadable cases and manual corrections.

## Copy photo references

Descriptors use the actual authorized scan-job/copy/photo association shared with
photo serving. Imported or provisional JSON, arbitrary paths and URLs cannot grant
access. Removed copies, expired unconfirmed jobs, missing bytes and revoked or
foreign accounts have no available photo. Undo cannot reconstruct deleted bytes.
Display is read-only local serving with private no-store headers and no recognition
attempt. See [image roles](artwork.md).

## Multiple-card photo batches

Batches stage source photos and reviewed crops, then pass user-selected identities
to the [shared bulk review](effective-collection.md#photo-rows-in-the-shared-review).
Manual crop editing and catalog matching remain available without CLI capacity.
Recognition proposes identities; only confirmed collection operations create copies.

### Storage and shared review

`photo_batches` owns account-scoped batches, photos, crops, reserved stages and
collection associations. `photo_batch_images` performs in-memory normalization,
bounded crop transforms and advisory similarity calculations over explicitly supplied
bytes. Image processing has no storage, admission or ownership authority.

`enable-photo-batches` explicitly adds four local tables and two indexes. Startup
and GET requests never migrate. For operation and recovery, see
[local development](operations.md#photo-batch-recovery) and
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
of database restore. Recovery retains it and reapplies cleanup before serving or
dispatch. Unsettled reservations charge their full allowance; crashes never trigger
automatic resend. Registered payload directories are removed on normal exit; stale
owned payloads are cleaned after 90 seconds when the shared CLI lock is available.
Unregistered paths are never swept.

### Photo workflow

| Step | Behavior |
| --- | --- |
| Prepare | Use a plain contrasting surface, visible card edges, diffuse light and sharp text. Keep cards parallel and avoid glare, fingers and overlapping sleeves. Use fewer cards or a close-up when text is unreadable. |
| Stage | Explicitly upload at most five photos. Ordering, removal and local preview make no provider request. JPEG/PNG/WebP validation rejects unsupported HEIC or animated files. |
| Review transmission | Show the provider/model, selected photos or crops, finite invocation/time allowance, unknown remaining capacity and privacy notice. Recognition requires a separate explicit action. Manual entry remains available. |
| Detect and correct | A detection request proposes at most 15 rectangles and readability flags. Review crop count, geometry, rotation and glare/overlap/cut-off issues before identity recognition. Manual corrections make no provider call. |
| Match identities | Send only the reviewed crops, each labeled by opaque crop ID. Local catalog matching interprets visible name/set/number/language/edition/finish clues. Model-generated printing IDs have no authority. |
| Correct duplicates | Choose supported identity, keep variants unknown, match manually, exclude or explicitly retake. Corrections invalidate old proposals. Retakes identified as the same physical objects retain row IDs. |
| Review collection changes | Inspect actual holdings, additions, totals, exclusions and physical duplicate decisions in the shared preview. Confirmation applies one operation with receipt and whole-batch undo. Reopening never retries recognition or adds copies. |

Similar pixels, overlapping photos or matching printing IDs produce **Possible same
physical card** hints. They never merge objects or create copies automatically.
Review **Same card / keep one**, **Different copies / keep both**, or **Not sure /
exclude for now**, including any manually entered row representing a crop. No quantity
is inferred from an approximate model count. Excluded or unreadable crops stay in the
draft and are identified by the receipt. A 16th card requires layout correction or a
retake; it is never silently discarded.

Model output establishes no authenticity, condition, grade, certificate verification,
value, pack origin or possession. Clear photographs do not manufacture an unsupported
catalog variant. A confirmed unresolved copy can remain outside exact-printing completion.

### CLI isolation

The batch adapter preserves the single-card profile and uses separate versioned
`dex-detection-v1` and `dex-identities-v1` schemas under `dex-photo-batch-v1`.
`beta/batch_recognition.py` shares CLI serialization and restrictions with
`beta/codex_recognition.py`. The pinned compatibility model is `gpt-5.6-sol`;
model or flag changes require explicit compatibility review.

Temporary selected files, strict schemas/events, an environment allowlist and
restricted tools/config keep inventory, the private root, repository and unrelated
files outside model access. Reject tool/action events, unexpected crop IDs and late
or malformed output. An incompatible isolation profile leaves manual entry available
rather than relaxing permissions. Deadlines are supervised independently of slow
authorization reads. Account, session and crop revisions must match before dispatch
and publication. Human-reviewed glare, overlap, cut-off and unreadable flags force
abstention.

Dex uses CLI-managed authentication without reading or copying the authentication
cache, extracting tokens, changing accounts or treating subscription login as a
Platform API credential. Missing CLI, expired login or usage limits preserve safe
staged inputs. There is no automatic retry, provider/model fallback or paid capacity
purchase. Local executable placement does not imply offline inference: selected
images are transmitted through the CLI service.

### Hard limits, reservations and Stop

| Dimension | Contract |
| --- | --- |
| Photos/cards | Five source-photo admissions including retakes, 15 cards/photo and 75/batch. Smaller manual batches remain supported. |
| Local source/decode | JPEG/PNG/WebP, single frame, 8 MB/photo, 40 MB/batch, 24 MP/photo and minimum 200px edge. Metadata stripped, orientation normalized, decode-bomb checks, staged longest edge at most 4096px. |
| CLI attachments | One overview at most 1600px/2 MB, or at most 15 reviewed crops at most 1024px/500 KB each and 7.5 MB aggregate. No additional original is attached. These bounds do not describe the CLI's internal wire serialization. |
| Output | Closed schema and semantic checks. Result file, stdout and stderr each at most 256 KB, independently supervised. Reported tokens are accounting, not a hard CLI token cap. |
| Attempts | Ordinarily one detection and one identity/photo; at most ten invocations/batch and two explicit attempts/logical stage. One in flight/account, with serialization shared across single-card work. |
| Time | At most 75 active seconds/invocation and/photo, 180 active seconds/batch. Launch uses the lesser remaining deadline. Human review never replenishes time or attempts. |
| Frequency | Shared maximum of 20 source photos/account/24h, including retakes and single-card admissions. |
| Accounting | Reserve before launch; retain outcomes, uncertainty and reported tokens. Remaining subscription capacity and monetary cost remain Unknown/null. API dollar reservations remain separate and are never converted or reset. |

Stop guards dispatch and publication independently. Cancellation or deadline
terminates only owned subprocesses and descendants. A crash after reservation
remains consumed or uncertain; recovery never automatically resends. Stop cannot
recall transmitted images or promise provider erasure. The independent journal
contains no image content, raw model output or authentication data. Drafts and
proposals remain non-owning until collection confirmation.

### Privacy, retention and deletion

Before recognition, explain that selected images/crops leave the machine through
Codex CLI, consume account capacity and may produce incorrect results. Show the
finite invocation/time allowance, unknown remaining capacity and manual alternative.
Record consent version and selected image/crop IDs separately from local staging.

CLI ephemeral mode and local cleanup do not establish provider deletion, zero
retention, training policy or entitlement. Data handling depends on the actual
authentication/account context; Platform API guarantees cannot be inherited.

Unconfirmed originals, crops and thumbnails expire seven days from admission,
regardless of edits. Retain only explicitly selected per-copy crops with authorized
associations; never attach the whole group original to every copy. Confirmation
without retaining images is supported. Cancellation, deletion, undo and removal
revoke access and clean authorized bytes. Cleanup retains sanitized receipt/attempt
identifiers, not image or model bodies. Deleted bytes cannot be reconstructed by
undo. Backups may retain old bytes; recovery reapplies current revocations, expiry,
deletion and consumed attempts before serving or dispatch. Keep private image pixels
out of source control and public output.
