# Retained catalog test metadata

These offline TCGdex metadata fixtures contain no ownership, prices or image bytes.
They are independent of runtime image mappings, so matching tests do not derive
expected identities from the implementation being checked.

`bw8.json`, `dp2.json`, `col1.json` and `dp1.json` retain package metadata for the
corresponding sets. `ivysaur-packages.json` retains source envelopes and only cards
whose `metadata.pokemon_dex` is 2. Each entry includes its original source path,
whole-file hash and source/license metadata; those fields describe provenance,
not required local files. Literal identity and variant evidence are preserved.

Tests load these tracked fixtures instead of scanning local exports or downloading
metadata. Keep source/license fields when updating them, and review expected
identities independently of image mapping changes.
