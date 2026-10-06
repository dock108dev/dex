"""Parse pinned TypeScript literals as data, never execute upstream code."""

import ast
import hashlib
import json
import re
import tarfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d7-20261005"
DEST = ROOT / "config/catalog-pipeline/d7-20261005"
PIN = "99c994747cf7519a3e51166cc932de79a88bd4b3"
TOKEN = re.compile(
    r"""\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|-?\d+(?:\.\d+)?|[A-Za-z_$][\w$]*|[^\s]"""
)


def parse(text):
    text = re.split(r"\bconst\s+\w+\s*:\s*\w+\s*=", text, maxsplit=1)[1]
    ts = [t for t in TOKEN.findall(text) if not t.isspace() and not t.startswith(("//", "/*"))]
    i = 0

    def val():
        nonlocal i
        t = ts[i]
        i += 1
        if t == "{":
            d = {}
            while ts[i] != "}":
                if ts[i] == ",":
                    i += 1
                    continue
                k = ts[i]
                i += 1
                if k[0] in "\"'":
                    k = ast.literal_eval(k)
                if ts[i] == ":":
                    i += 1
                    d[k] = val()
                else:
                    d[k] = {"reference": k}
                if ts[i] not in [",", "}"]:
                    raise ValueError("Unsupported expression: " + str(ts[i : i + 5]))
            i += 1
            return d
        if t == "[":
            a = []
            while ts[i] != "]":
                if ts[i] == ",":
                    i += 1
                    continue
                a.append(val())
                if ts[i] not in [",", "]"]:
                    raise ValueError("Unsupported array expression")
            i += 1
            return a
        if t[0] in "\"'":
            value = ast.literal_eval(t)
            while ts[i] == "+":
                i += 1
                other = val()
                if not isinstance(other, str):
                    raise ValueError("Only literal string concatenation supported")
                value += other
            return value
        if re.fullmatch(r"-?\d+(?:\.\d+)?", t):
            return float(t) if "." in t else int(t)
        if t in ["true", "false", "null", "undefined"]:
            return {"true": True, "false": False, "null": None, "undefined": None}[t]
        return {"reference": t}

    result = val()
    if not isinstance(result, dict):
        raise ValueError("Object expected")
    return result


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def english_variants(value):
    """Only explicit variant objects applicable to English; legacy shapes stay raw."""
    if not isinstance(value, list):
        return [], [{"reason": "unresolved-variant-shape", "value": value}]
    accepted, excluded = [], []
    for variant in value:
        if not isinstance(variant, dict):
            excluded.append({"reason": "unresolved-variant-shape", "value": variant})
            continue
        languages = variant.get("languages")
        if languages is not None and (not isinstance(languages, list) or "en" not in languages):
            excluded.append({"reason": "non-English-or-unresolved-variant-language", "value": variant})
        else:
            accepted.append(variant)
    return accepted, excluded


def variant_count(record):
    return len(record["english_variants"])


def run():
    ledger = json.loads((ROOT / "evidence/d6-20261005/source-ledger.json").read_text())
    bulk = next(a for a in ledger["attempts"] if a.get("key") == "tcgdex-archive")
    assert hashlib.sha256((ROOT / bulk["response_path"]).read_bytes()).hexdigest() == bulk["sha256"]
    files = {}
    parsed = {}
    exceptions = []
    with tarfile.open(ROOT / bulk["response_path"]) as tar:
        for m in tar.getmembers():
            path = m.name.split("/", 1)[-1]
            if not m.isfile() or not path.startswith("data/") or not path.endswith(".ts"):
                continue
            raw = tar.extractfile(m).read()
            files[path] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            try:
                parsed[path] = parse(raw.decode())
            except (ValueError, IndexError, SyntaxError) as e:
                exceptions.append(dict(path=path, reason="literal-parser-unresolved", detail=str(e)))
        lic = next(m for m in tar.getmembers() if m.name.endswith("/LICENSE"))
        (OUT / "TCGDEX_LICENSE.txt").write_bytes(tar.extractfile(lic).read())
    sets = []
    printings = []
    assessments = []
    counts = Counter()
    mapping = []
    variant_exclusions = []
    for path, s in parsed.items():
        if len(Path(path).parts) != 3 or not s.get("id") or not s.get("name", {}).get("en"):
            continue
        code = s["id"]
        era_path = str(Path(path).parent) + ".ts"
        era = parsed.get(era_path, {}).get("id", "unknown")
        medium = "digital" if era == "tcgp" or "Pocket" in path else "physical"
        prefix = path[:-3] + "/"
        cardpaths = sorted(p for p in files if p.startswith(prefix) and len(Path(p).parts) == 4)
        english = []
        gaps = []
        rows = []
        for cp in cardpaths:
            c = parsed.get(cp)
            if c is None:
                gaps.append(dict(path=cp, reason="parser-failure"))
                continue
            if not c.get("name", {}).get("en"):
                gaps.append(dict(path=cp, reason="no-english-name"))
                continue
            english.append(cp)
            category = c.get("category")
            dex = c.get("dexId", [])
            target = [n for n in dex if isinstance(n, int) and 1 <= n <= 251]
            if category == "Pokemon" and len(dex) != 1:
                gaps.append(dict(path=cp, reason="unresolved-or-multiple-canonical-mapping", dex=dex))
            if category not in ["Pokemon", "Trainer", "Energy"]:
                gaps.append(dict(path=cp, reason="unknown-category", category=category))
            if category == "Pokemon" and len(dex) == 1 and target:
                number = Path(cp).stem
                external = code + "-" + number
                rec = dict(
                    provider="tcgdex",
                    provider_set_id=code,
                    external_id=external,
                    species=target[0],
                    name=c["name"]["en"],
                    number=number,
                    rarity=c.get("rarity"),
                    category=category,
                    era=era,
                    medium=medium,
                    file=cp,
                    file_sha256=files[cp]["sha256"],
                    commit=PIN,
                    source_url=f"https://github.com/tcgdex/cards-database/blob/{PIN}/{cp}",
                    variants=c.get("variants", []),
                    distribution="unknown",
                    language="en",
                )
                rec["english_variants"], excluded = english_variants(rec["variants"])
                rec["variant_language_exclusions"] = excluded
                rec["market_applicability"] = (
                    "English-language source; US release applicability not independently established"
                )
                variant_exclusions.extend(dict(external_id=external, file=cp, **e) for e in excluded)
                printings.append(rec)
                rows.append(rec)
        release = s.get("releaseDate")
        status = "released" if isinstance(release, str) and release <= "2026-10-05" else "uncertain"
        complete = not gaps and bool(cardpaths)
        se = dict(
            id="tcgdex:en:" + code,
            provider="tcgdex",
            provider_set_id=code,
            internal_set_key=code,
            name=s["name"]["en"],
            language="en",
            era=era,
            medium=medium,
            release_status=status,
            release_date=release,
            source_url=f"https://github.com/tcgdex/cards-database/blob/{PIN}/{path}",
            source_time=bulk["retrieved_at"],
            source_sha256=files[path]["sha256"],
            source_status="retained-usable",
            expected_full_set_count=len(cardpaths),
            official_numbered_count=s.get("cardCount", {}).get("official"),
            english_source_records=len(english),
            target_numbered_count=len(rows),
            supplied_variant_records=sum(variant_count(r) for r in rows),
            enumeration_complete=complete,
            enumeration_basis="All card-file members in complete pinned git tree and archive, not printed official count",
            gaps=gaps,
        )
        sets.append(se)
        exceptions.extend(dict(set_id=se["id"], **g) for g in gaps)
        counts[medium] += 1
        # Import priority plus coherent modern sets. Numbered packages retain all English source categories;
        # above-251 records remain raw and count reconciliation uses a target-only partial package.
        if (
            code not in ["ecard1", "ecard2", "sv02", "sv06", "swsh10", "swsh11", "swsh12"]
            or medium != "physical"
        ):
            continue
        cards = []
        numbered = {}
        for r in rows:
            variants = r["english_variants"]
            if not variants and not r["variant_language_exclusions"]:
                variants = [None]
            seen = set()
            for v in variants:
                variant = (
                    json.dumps(
                        {k: value for k, value in v.items() if k != "thirdParty"},
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if v
                    else None
                )
                # Full variant identity is retained in sidecar; compact digest prevents unstable positional IDs.
                suffix = hashlib.sha256(variant.encode()).hexdigest()[:16] if variant else "unspecified"
                eid = r["external_id"] + ":" + suffix
                if eid in seen:
                    exceptions.append(
                        dict(set_id=se["id"], identity=eid, reason="identical-variant-coalesced")
                    )
                    continue
                seen.add(eid)
                finish = v.get("type") if v else None
                edition = "1st-edition" if v and "1st-edition" in v.get("stamp", []) else None
                cards.append(
                    dict(
                        external_id=eid,
                        number=r["number"],
                        name=r["name"],
                        finish=finish,
                        variant=variant,
                        edition=edition,
                        metadata=dict(
                            pokemon_dex=r["species"],
                            dex_eligible=True,
                            supertype="Pokémon",
                            rarity=r["rarity"] or "Unknown",
                        ),
                    )
                )
                numbered[eid] = r["external_id"]
                mapping.append(
                    dict(
                        provider="tcgdex",
                        external_id=eid,
                        numbered_id=r["external_id"],
                        species=r["species"],
                        set_id=se["id"],
                        file=r["file"],
                        file_sha256=r["file_sha256"],
                    )
                )
        p = dict(
            schema_version="dex-catalog-v1",
            game="pokemon",
            provider="tcgdex",
            version="d7-" + PIN[:12] + "-v1",
            set_key=code.replace(".", "-"),
            set_name=se["name"],
            language="en",
            aliases=[],
            source_url=bulk["url"],
            source_sha256=bulk["sha256"],
            metadata_permission="MIT; Copyright (c) 2021 TCGdex; see evidence/d7-20261005/TCGDEX_LICENSE.txt",
            image_permission="not-included",
            coverage="partial",
            expected_count=max(len(cardpaths), len(cards)),
            cards=cards,
        )
        # M2 complete reconciliation currently requires every numbered source identity represented.
        # Do not invent above-251 imports to force target-only packages complete.
        assessments.append(
            dict(
                set_id="tcgdex:en:" + p["set_key"],
                language="en",
                era=era,
                medium=medium,
                release_status=status,
                source_url=bulk["url"],
                source_time=bulk["retrieved_at"],
                source_sha256=bulk["sha256"],
                evidence_class="retained-real-source",
                enumeration_complete=False,
                enumerated_ids=sorted({r["external_id"] for r in rows}),
                numbered_mappings=numbered,
                expected_target_count=len(rows),
                package=p,
            )
        )
        if code == "gym1":
            prior = json.loads((ROOT / "config/catalog-pipeline/retained-20261004.json").read_text())
            prior = next(a["package"] for a in prior["sets"] if a["set_id"] == "tcgdex:en:gym1")
            originals = []
            for old in prior["cards"]:
                cp = prefix + old["number"] + ".ts"
                c = parsed.get(cp, {})
                cat = c.get("category")
                dex = c.get("dexId", [])
                meta = dict(
                    pokemon_dex=dex[0] if cat == "Pokemon" and len(dex) == 1 else None,
                    dex_eligible=cat == "Pokemon" and len(dex) == 1,
                    supertype={"Pokemon": "Pokémon", "Trainer": "Trainer", "Energy": "Energy"}[cat],
                    rarity=c.get("rarity") or "Unknown",
                )
                originals.append(dict(**old, edition=None, finish=None, variant=None, metadata=meta))
            p["cards"] = originals + p["cards"]
            p["aliases"] = prior["aliases"]
            p["expected_count"] = len(p["cards"])
            write(
                OUT / "gym-heroes-correction-before.json",
                dict(
                    before_sha256=hashlib.sha256(json.dumps(prior, sort_keys=True).encode()).hexdigest(),
                    prior_package_path="config/catalog-pipeline/retained-20261004.json",
                    note="Original IDs retain unknown physical attributes; source canonical/category corrections are reviewed through catalog journal. Variants stay separate.",
                ),
            )
        write(DEST / (code.replace(".", "-") + ".json"), p)
    sets.sort(key=lambda s: (s["era"], s["id"]))
    write(
        DEST / "batch.json",
        dict(
            schema_version="dex-target-batch-v1",
            version="d7-" + PIN[:12] + "-v1",
            mode="checkpoint",
            sets=[a for a in assessments if a["set_id"] != "tcgdex:en:gym1"],
        ),
    )
    write(OUT / "archive-file-manifest.json", dict(commit=PIN, archive_sha256=bulk["sha256"], files=files))
    write(
        OUT / "universe.json",
        dict(
            schema_version="dex-set-universe-v1",
            version="d7-" + PIN[:12],
            market="English; US applicability unresolved",
            current=True,
            source_url=bulk["url"],
            source_time=bulk["retrieved_at"],
            source_sha256=bulk["sha256"],
            sets=sets,
        ),
    )
    write(OUT / "target-printings.json", printings)
    write(OUT / "provider-mappings.json", mapping)
    write(OUT / "exceptions.json", exceptions)
    write(OUT / "variant-exclusions.json", variant_exclusions)
    species = []
    for n in range(1, 252):
        rs = [r for r in printings if r["species"] == n and r["medium"] == "physical"]
        species.append(
            dict(
                pokemon_dex=n,
                printing_count=len(rs),
                supplied_variant_records=sum(variant_count(r) for r in rs),
                sets=sorted({r["provider_set_id"] for r in rs}),
                distribution="unresearched",
                documented_products=0,
                eligible_offers=0,
            )
        )
    write(OUT / "species-coverage.json", species)
    write(
        OUT / "era-coverage.json",
        [
            dict(
                era=e,
                sets=sum(s["era"] == e for s in sets),
                physical_sets=sum(s["era"] == e and s["medium"] == "physical" for s in sets),
                target_printings=sum(r["era"] == e and r["medium"] == "physical" for r in printings),
            )
            for e in sorted({s["era"] for s in sets})
        ],
    )
    summary = dict(
        commit=PIN,
        archive_card_files=sum(len(Path(p).parts) == 4 for p in files),
        parsed_files=len(parsed),
        set_count=len(sets),
        medium=dict(counts),
        physical_target_printings=sum(r["medium"] == "physical" for r in printings),
        import_sets=len(assessments),
        import_catalog_rows=sum(len(a["package"]["cards"]) for a in assessments),
        import_target_records=sum(
            sum(
                c.get("metadata", {}).get("pokemon_dex") is not None and c["metadata"]["pokemon_dex"] <= 251
                for c in a["package"]["cards"]
            )
            for a in assessments
        ),
        new_supplied_variant_records=len(mapping),
        preserved_gym_numbered_rows=0,
        import_target_numbered=sum(a["expected_target_count"] for a in assessments),
        exceptions=len(exceptions),
        variant_exclusions=len(variant_exclusions),
        assessed_sets=[{k: a[k] for k in ["set_id", "expected_target_count"]} for a in assessments],
    )
    write(OUT / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run()
