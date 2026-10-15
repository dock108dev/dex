# Retained catalog test metadata

These are offline engineering inputs from the existing retained TCGdex exports.
They contain catalog metadata only, with no ownership, prices or image bytes.
They are independent of the runtime image mappings being checked.

`bw8.json`, `dp2.json`, `col1.json` and `dp1.json` are byte-for-byte copies of
the four D8 packages used by the reviewed-image identity test. Original paths
and SHA-256 fingerprints:

- `config/catalog-pipeline/d8-20261006/bw8.json`: `68dbae0ff24c9de2c0d1c31ffdbdfffe5272996a9fd73ff1bd6827c9c3d7fb49`
- `config/catalog-pipeline/d8-20261006/dp2.json`: `cf470b946d66144cf3ad10541a77ba8b712c1b1d71cc96aa8288b5b2a9764bb1`
- `config/catalog-pipeline/d8-20261006/col1.json`: `aa588bd7355c57eacccff1f50caf6393d67893b212ceeddac3f51c62653f943c`
- `config/catalog-pipeline/d8-20261006/dp1.json`: `e3e882e02d6dc4cbd33231171df0a51f0d5d5922c5a875057495421070bb8118`

`ivysaur-packages.json` retains each package envelope and only cards whose
`metadata.pokemon_dex` is 2 from the eight D7/D8/D9 exports named in its entries.
Each entry records the original path and whole-file SHA-256. Card fields,
variant evidence and package source/license metadata are preserved. Combined
with the tracked October 4 and D6 metadata, these inputs represent the original
20 printing variants in 13 groups.

The original intermediate export directories are ignored and are not available
in clean checkouts. Tests load these explicit fixtures rather than scanning
local exports, downloading metadata or deriving expectations from image mappings.
