# D7 validation — October 6, 2026

[D7 closeout](../D7_DATA_COLLECTION.md) is authoritative for final counts and limitations.

Attempt 1 published the real D7 packages, refused broken exact references and a stale competing correction, and preserved protected tables. Rollback correctly refused D7 M2 while the later shopping delta was active. This was a rehearsal sequencing error; application code was untouched. The fresh replacement rolled back shopping before M2 before sealed catalog.

Attempt 2 passed the corrected publication/conflict/rollback sequence, then refused a rehearsal lookup request that incorrectly placed offer filters in the scope fields. The script was corrected to use the existing lookup contract. Failed attempts 1/2 reports are retained in `evidence/d7-20261005/validation-attempt1.tar.gz` and `validation-attempt2.tar.gz`, with adjacent logs.

Fresh attempt 3 passed publication, repeated confirmation/idempotency, exact-reference refusal, stale correction refusal with unchanged records, all active sealed data restoration, source timestamp preservation, account isolation and copied-backup comparison. It republished uniquely versioned disposable records for browser qualification. Browser save/restart/reopen passed with unchanged frozen snapshot and original/new observations, historical goals/research/declarations and protected tables/photos/credentials. Zero provider calls; two server starts; server stopped. Occupied port 8011 was left untouched and D7 used 8013.

87 focused tests passed; all seven new D7 scripts passed lint. Deterministic regeneration reproduced package bytes. No new full suite, PostgreSQL, hosted, independent review or owner acceptance. Shopping current eligibility remains zero; collection progress remains 137/151 Kanto, 161/251 total and 14/90 missing.

Final candidate and adjacent hash are under `evidence/d7-20261005/`. Entry verification covered all 1,736 inherited handoff files. Final preservation diff binds deliberate documentation/hand-off updates and rejects unexpected inherited changes.

Budget deviation: two uncompressed failed-attempt reports temporarily raised estimated retained logical bytes to 108,404,237 (103.4 MiB), above the 100 MiB cap. Compression preserved their contents and brought final evidence below the cap; acquisition had already closed. This limitation is recorded in the closeout and budget report.
