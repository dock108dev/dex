# PERF-03 isolated qualification — 2026-10-28

Beta Python source SHA-256: `6274a9db3e54e5020b0237cf8ef170e25668e211d1ce7df45a4c95440f8341b3`. This identifies the entire current beta source, including preserved pre-existing changes. No commit, hosted run, customer migration or installation is implied.

The measured tests use Python 3.14.0, SQLite 3.50.4 and macOS arm64. All state is generated in disposable pytest roots. Network access was blocked. Each of 26 scenarios has 20 reused-connection and 20 fresh-connection samples per scale: 1,040 requests per scale, 2,080 total. Fresh connections do not mean cold OS caches. SQL includes execute/fetch and transaction statements; EXPLAIN queries are excluded from the SQL count but included in first-sample API timing.

The catalogs contain 33,083 and 66,166 printings with 187 synthetic expansion sets, Unicode names, variant children, archived ownership and unresolved identity cases. The ownership load adds 5,000/10,000 copies and 10,000/20,000 historical operations to the small retained-copy fixture. Twenty successive controlled edits measure the ordinary revision-capture/refresh hooks. Preview and full confirmation planning are deliberately excluded from the 200 ms incremental preparation measurement; correctness tests exercise the full mutation path.

| Metric | Full size | 2× | Gate |
|---|---:|---:|---:|
| Largest scenario API p95 (ms) | 45.74 | 30.78 | 180 |
| Worst single API sample (ms) | 57.32 | 32.78 | reported separately |
| Largest SQL p95 (ms) | 32.73 | 27.79 | 40 |
| Maximum SQL queries | 20 | 20 | 20 |
| Maximum fetched records | 212 | 212 | reported; compact IDs included |
| Maximum decoded page records | 100 | 100 | 100 |
| Non-SQL p95 upper bound (ms) | 14.15 | 7.26 | 80 composition |
| Largest response (bytes) | 82707 | 82680 | 131,072 primary / 32,768 context/options |
| Incremental preparation p95 (ms) | 84.10 | 177.78 | 200 |
| Incremental worst sample (ms) | 90.17 | 179.24 | reported separately |
| Incremental fetched / decoded maxima | 147 / 102 | 223 / 178 | affected closure and retained species records |
| Whole-account preparation (seconds) | 8.66 | 17.65 | separate explicit preparation |

The non-SQL bound is calculated per raw sample as API elapsed minus SQL time. It conservatively includes authorization, decoding, composition, adapter work and serialization; it therefore also bounds composition. The harness separately reports timed payload decoding/composition. The maximum 212 fetched records includes two bounded 100-ID/page metadata selections plus auth/manifest records; only 100 group records are decoded. No browsing request loads the full catalog or journal.

## Scenario p95s

Every row represents 20 samples per scale. Raw per-request times, decoding counts, SQL/fetch times, payload bytes and query plans remain in ignored `reports/perf03/scale-33083.json` and `scale-66166.json`. The harness regenerates them.

| Condition / scenario | API ms full / 2× | SQL ms full / 2× | Queries max | Payload bytes max |
|---|---:|---:|---:|---:|
| warm_owned | 5.70 / 6.03 | 3.66 / 4.49 | 17 | 33414 |
| warm_max_owned | 7.96 / 8.09 | 5.62 / 5.52 | 17 | 82583 |
| warm_catalog | 7.03 / 8.62 | 5.24 / 7.00 | 18 | 33439 |
| warm_max_page | 10.55 / 11.14 | 7.53 / 8.48 | 18 | 82707 |
| warm_unicode | 7.12 / 7.30 | 4.83 / 5.48 | 18 | 33409 |
| warm_search | 11.46 / 15.98 | 9.78 / 13.96 | 18 | 33342 |
| warm_short | 10.76 / 16.31 | 8.68 / 14.49 | 18 | 33447 |
| warm_deep | 8.33 / 12.03 | 6.55 / 9.71 | 18 | 33480 |
| warm_variants | 12.61 / 20.74 | 10.85 / 18.76 | 17 | 33445 |
| warm_options | 4.17 / 4.99 | 2.99 / 4.13 | 17 | 2967 |
| warm_owned_options | 5.21 / 6.68 | 3.91 / 5.20 | 17 | 2963 |
| warm_detail | 3.11 / 4.47 | 1.87 / 3.16 | 17 | 2839 |
| warm_copies | 5.65 / 6.87 | 4.43 / 5.73 | 18 | 908 |
| warm_history | 4.04 / 7.02 | 3.07 / 5.61 | 18 | 327 |
| warm_children | 3.21 / 6.02 | 2.21 / 4.44 | 18 | 1011 |
| warm_artwork | 2.80 / 4.44 | 1.98 / 3.38 | 17 | 857 |
| warm_species | 9.33 / 9.68 | 6.70 / 7.78 | 16 | 20955 |
| warm_scoped_species | 9.71 / 13.27 | 7.27 / 9.93 | 16 | 51025 |
| warm_species_options | 3.14 / 5.34 | 2.09 / 3.87 | 17 | 2937 |
| warm_scoped_set | 19.10 / 30.78 | 15.13 / 27.79 | 16 | 51042 |
| warm_species_finish_options | 3.76 / 5.94 | 2.28 / 3.20 | 17 | 436 |
| warm_context | 3.70 / 6.49 | 2.58 / 5.10 | 16 | 962 |
| warm_duplicates | 3.11 / 4.19 | 2.06 / 3.09 | 17 | 413 |
| warm_picker | 8.72 / 14.34 | 7.12 / 12.64 | 17 | 20621 |
| warm_picker_search | 12.23 / 18.15 | 10.07 / 15.99 | 17 | 20361 |
| warm_evidence | 4.45 / 4.47 | 3.24 / 2.97 | 16 | 2983 |
| fresh_owned | 10.55 / 10.73 | 6.03 / 5.98 | 19 | 33414 |
| fresh_max_owned | 17.79 / 13.57 | 12.22 / 7.42 | 19 | 82583 |
| fresh_catalog | 17.74 / 14.88 | 12.43 / 9.37 | 20 | 33439 |
| fresh_max_page | 16.26 / 18.06 | 11.09 / 11.62 | 20 | 82707 |
| fresh_unicode | 15.91 / 16.73 | 12.04 / 7.88 | 20 | 33409 |
| fresh_search | 13.61 / 24.77 | 9.46 / 20.33 | 20 | 33342 |
| fresh_short | 14.50 / 20.97 | 10.83 / 16.36 | 20 | 33447 |
| fresh_deep | 34.62 / 15.41 | 29.61 / 11.30 | 20 | 33480 |
| fresh_variants | 45.74 / 25.73 | 32.73 / 22.12 | 19 | 33445 |
| fresh_options | 8.19 / 9.12 | 3.92 / 5.42 | 19 | 2967 |
| fresh_owned_options | 9.18 / 9.99 | 5.82 / 6.38 | 19 | 2963 |
| fresh_detail | 8.67 / 7.74 | 4.32 / 3.86 | 19 | 2839 |
| fresh_copies | 9.43 / 14.89 | 4.61 / 10.97 | 20 | 908 |
| fresh_history | 9.31 / 12.10 | 4.57 / 7.73 | 20 | 327 |
| fresh_children | 7.30 / 7.89 | 2.71 / 3.82 | 20 | 1011 |
| fresh_artwork | 7.10 / 8.34 | 2.50 / 4.08 | 19 | 857 |
| fresh_species | 11.13 / 12.81 | 6.28 / 8.87 | 18 | 20955 |
| fresh_scoped_species | 19.43 / 15.41 | 10.07 / 10.58 | 18 | 51025 |
| fresh_species_options | 8.60 / 7.50 | 3.75 / 3.83 | 19 | 2937 |
| fresh_scoped_set | 26.37 / 30.47 | 21.92 / 25.66 | 18 | 51042 |
| fresh_species_finish_options | 6.69 / 8.89 | 2.84 / 5.26 | 19 | 436 |
| fresh_context | 8.13 / 9.21 | 4.17 / 5.70 | 18 | 962 |
| fresh_duplicates | 6.03 / 6.96 | 2.65 / 3.74 | 19 | 413 |
| fresh_picker | 13.12 / 19.27 | 8.82 / 15.31 | 19 | 20621 |
| fresh_picker_search | 16.11 / 23.91 | 11.52 / 18.93 | 19 | 20361 |
| fresh_evidence | 7.71 / 7.23 | 3.51 / 3.62 | 18 | 2983 |

## Failures retained and resolved

Earlier candidates failed the fixed budgets: wide row reads, correlated search and option joins, repeated species-wide policy evaluation, unsuitable count/component indexes, a picker sort, and repeated species metadata aggregation. The slow correlated option run was interrupted after its persisted full-size failures. Later candidates narrowly missed the 40 ms species SQL gate and exposed additional set/finish-option/child-query misses when coverage expanded. These were not accepted or hidden by changing limits. Candidate-specific reports are retained under `reports/perf03/pre-*` and `initial-*`. The final two scale reports above have no failures.

The fixes use compact membership/count indexes, retained operation dependencies, differential writes, indexed literal closures, explicit child indexes, precomputed species options and exact weighted date/finish counts. Set scope prunes only definitely excluded records; unknown metadata remains eligible for an unresolved result.

## Reproduce and interpret

```sh
uv run --no-sync pytest -q tests/test_account_reads.py tests/test_account_read_photos.py --disable-socket --allow-unix-socket
uv run --no-sync pytest -q -s tests/test_account_read_performance.py --disable-socket --allow-unix-socket
uv run --no-sync pytest -q -s tests/test_catalog_read_performance.py --disable-socket --allow-unix-socket
```

Run timing tests without coverage/profilers and without overlapping heavy tests. The `no_cover` marker excludes tracing when these gates run with the repository Behavior suite. Keep all fixed thresholds. Whole-account preparation is not an ordinary GET or startup task. A large dependency/source bundle can deliberately leave the representation unavailable until explicit preparation.

PERF-02 rerun and broader regression results are recorded in `CI.md`. PostgreSQL, hosted CI, frontend adoption, readiness orchestration, customer installation and owner acceptance are separate outstanding stages. See [contracts and handoffs](perf03-account-reads.md).
