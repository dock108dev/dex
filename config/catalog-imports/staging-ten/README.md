# Original ten sets: explicit TCGdex reconciliation

859 English entries, source commit `309aab7060b165925fee48573e730275dfbd737c` of [TCGdex cards-database](https://github.com/tcgdex/cards-database/tree/309aab7060b165925fee48573e730275dfbd737c). [MIT permission and copyright](https://github.com/tcgdex/cards-database/blob/309aab7060b165925fee48573e730275dfbd737c/LICENSE) checked September 28, 2026. The complete copyright/permission notice is retained at `../TCGDEX_LICENSE.txt` and travels in the runtime image.

Only names, collector numbers, set identity, species, category and rarity are extracted. No artwork, artwork URLs, prices, rules text or private collection is included. This grant covers this source metadata; it does not grant Pokémon artwork/trademark rights or permissions for other providers.

`source-manifest.json` retains each source file hash, the commit, license hash and three reviewed spelling/qualifier differences. Nidoran gender-spacing and Unown bracket typography normalize only for source comparison. Every set/number/species and goal-eligibility flag is checked against the existing public reference, never inferred from an owner copy. `scripts/prepare_staging_catalog.py` reads source literals without executing the source TypeScript.

The ordinary importer accepts reconciliation only for these exact packaged mappings. Existing internal set/printing IDs, edition/finish/variant identity, copies, frozen goals and original provenance remain; publication history retains replaced attributes and supports rollback. Multiple existing variants for one source entry stop reconciliation for review. No arbitrary fuzzy match is accepted.

Fresh synthetic staging receives 859 entries here plus 132 Gym Heroes entries and two explicitly synthetic Orbits variants. Rarity follows TCGdex's classification (for example Rare rather than a legacy Rare Holo label); no finish is inferred. Known external prices and artwork remain unavailable. This restores supported catalog/Pokédex/manual matching, not the local guide or hunt experience.
