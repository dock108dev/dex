# Photo entry and recognition

Scan/Add accepts private card photos, shows recognition clues and catalog candidates,
and requires confirmation before adding a physical copy. Manual matching and
provisional entries work when recognition fails or catalog coverage is missing.
The model does not establish authenticity, condition, grade or value.

## Provider configuration

The private root's `scan-config.json` selects a provider:

```json
{"enabled": true, "mode": "manual", "ceiling_usd": 1.0, "user_ceiling_usd": 0.5}
```

| Mode | Requirement and behavior |
|---|---|
| `manual` | Default for ordinary new roots; choose identity yourself |
| `fixture` | Simulated results for tests and the synthetic demo |
| `openai` | `OPENAI_API_KEY` in the server/worker environment; sends image bytes to the API |
| `codex_cli` | Local only: compatible `codex` executable on PATH with its own saved ChatGPT authentication; sends images through the CLI |

`beta/scan_config.py` validates the four keys shown above. Other keys fail rather
than act as ignored provider/fallback settings. Staging stores a complete config
in `beta_operations` and supports `manual`, `fixture` and `openai`; both copied
import and runtime startup reject `codex_cli`, including disabled configurations.
Missing persistent staging configuration requires the existing staging migration
path; reading it does not invent defaults or reset reservations. Local roots keep
their supported manual defaults when a config file is absent.

Provider changes affect new work; queued jobs from a different provider fail instead
of switching silently. Running calls retain their original provider. Disabling
scans cancels CLI work, but cannot recall an API request already sent. Keep existing
ceilings and reservations when changing modes. Missing or incompatible credentials
produce a manual-entry alternative; there is no automatic provider fallback.

`beta/scans.py` pins the API model/request shape and cost calculation. Every API
attempt reserves $0.05 before transmission, with maximum lifetime ceilings of $1
per root and $0.50 per account. Failed or cancelled calls retain reservations.
Reported usage is an estimate, not an invoice. Review rates and the reservation
bound before changing model or payload size.

`beta/codex_recognition.py` pins the CLI model and required flags. Each attempt uses
a private temporary directory, an environment allowlist, disabled tools/config/rules,
a process lock and a 75-second deadline. It rejects action events and removes
payloads on ordinary exit/cancellation. Hard OS termination cannot guarantee cleanup.
The CLI manages its own authentication; Dex does not copy tokens. Private
`codex-usage.jsonl` records attempts and reported usage separately from API dollars.
Remaining subscription capacity is unavailable; usage is not represented as free
or unlimited. CLI compatibility depends on the required protocol and flags; incompatible
releases fail explicitly.

## Durable work and privacy

Uploads are validated and re-encoded without image metadata. Jobs persist in the
inventory database; provider calls occur outside database transactions. After 120
seconds, interrupted claims become failed and need explicit retry. At most two
provider attempts are allowed per job, with no automatic retry of uncertain calls.
Each account can upload 20 entries per rolling 24 hours.

Unconfirmed uploads expire after seven days. Confirmed photos remain with the copy.
Cancellation and undo delete image bytes; copy removal and account revocation block
access immediately and worker cleanup removes bytes. Existing backups may retain
old data until those backups expire or are removed. Photo sharing for catalog
requests requires explicit consent.

Confirmation is idempotent; adding an intentional duplicate is a separate action.
Undo checks for intervening changes. Edition and variant clues remain suggestions,
not automatic copy assertions. See [failure recovery](ERROR_HANDLING.md).

## Limits and evaluation

Real-card accuracy remains unmeasured. Synthetic fixtures and transport controls
are not accuracy evidence. The optional `scripts/evaluate_codex_photos.py`
requires a labeled, consented image set; inspect its help and limits before use.
It sends real images to the CLI provider and is separate from offline tests.
A broader recognition benchmark and deployment qualification remain future work.
