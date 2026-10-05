# E3a qualification — October 4, 2026

**E3a is qualified for local synthetic engineering.** Synchronized-runtime checks,
ordinary browser walkthrough and protected-state preservation passed. No implementation
repairs, acquisition, owner-installation changes, commit or release occurred.
Full E3 and beta remain open; this is not owner acceptance.

## Candidate and runtime checks

Baseline HEAD: `fba1be13135b0b3bbb6cb674de5586e0f3c80740`.
Original E3a manifest SHA-256:
`c3e0d9a21354a8eda21fea57b940317882eab6496be4d6b220bb58391798c6de`.
All 244 listed files matched except the documented Desktop handoff replacement,
SHA-256 `4554e4abc2a0f2efe2aca4b91e48e9bb7eba28486c8db4bacc0e5436a17b3507`.
All other files and implementation remained unchanged through qualification.
Earlier manifests and failed-attempt evidence remain retained.

Checks used `UV_CACHE_DIR=/private/tmp/dex-e3a-uv` in the local Python 3.14 environment:

- `uv sync --locked --extra dev`: pass; resolved 33, audited 31 packages.
- Cleanup cancel/timeout/shutdown: 3 passed in 0.82 seconds; actual ps assertions ran.
- Full final-source suite: **464 passed, 1 warning, 141.62 seconds**.
- Compilation and all beta/static and web JavaScript syntax: pass.
- Ruff lint: pass. Ruff formatting: 164 files already formatted.
- Diff whitespace: pass.

The existing Starlette/httpx deprecation warning remains. Required checks were not
skipped or weakened. Logs/results are local in `evidence/e3a-qualification-20261004/`.
Final candidate manifest and SHA-256 companion are under its `validation-final/`.
They are frozen after documentation closeout; tests qualify unchanged code.

## Ordinary synthetic browser walkthrough

Used `/private/tmp/dex-e3a-20261005-copy` with its synthetic marker and retained
baseline. Supported port 8011 was free. `scripts/serve_e3a.py` started the disposable
loopback server with eBay/HTTP-client acquisition prohibited and counted. The user's
standing authorization for local beta testing applied. Generated synthetic credentials
were used privately and do not appear in captures or logs.

A fresh in-app browser session verified:

1. Version 2's ordinary goal-card entry opened Packs to open with whole-goal 151
   possible missing-species coverage, preserving its exact selected goal ID.
2. Scyther opened with one possible species and one confirmed standard printing;
   expanded details showed uncommon, nonfoil/normal and the unresolved reverse variant.
3. Product details showed exact UPC/version, unknown official quantities and guaranteed
   inclusions, unknown confirmed product coverage and no unsupported Buy now claim.
4. Both historical offers retained their original times. USD 27.99 remained observed
   out-of-stock; seller/direct-versus-marketplace and shipping stayed unknown. The
   approximate original-time limitation and unverified current availability were visible.
5. Local species/expansion filtering and reset preserved the goal scope.
6. Explicit version 1 navigation showed the empty reviewed-booster join, without
   substituting version 2; navigation back restored version 2.
7. Scyther's missing-species checklist link opened the correct frozen species view.
8. An absent-expansion filter showed the coverage-gap state; the legacy Vintage 251
   goal displayed its unsupported-goal limitation without claiming no packs exist.

Screenshots and DOM observations are retained under `browser/`. Browser warning/error
logs were empty. Expansion aggregates retain the source/service evidence of 185
confirmed Pokémon printing relationships and 161 unresolved Pokémon variants; the
package-wide 207/177 figures include non-Pokémon records. Current synthetic completion
is 0/151, independent of the owner's missing-18 research seed.

The test browser tab was closed and only the disposable server was stopped. No owner
server was started, stopped or replaced; no security policy was changed.

## Preservation and remaining scope

`rehearse_e3a.py --verify` passed against the retained pre-browser snapshot. All protected
copies, goals, saved hunts, scan jobs/reservations, scan photos, binders and observations
were unchanged; photo bytes matched. Login/session bookkeeping is separate. The
provider counter was **zero**. Browsing/filtering did not refresh offer timestamps.

Next: separate D3/D4a exact Bundle data collection, using the seven-attempt budget
and identities in [E3A](../E3A.md). Official product contents/current seller-specific
offers, 177 membership gaps, independent Scyther review, all-era coverage, live eBay,
E4/E5 and owner acceptance remain open. Synthetic qualification does not establish
current stock, worldwide coverage or full E3/beta completion.
