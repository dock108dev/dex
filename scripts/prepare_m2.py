"""Prepare dated manifest and multi-set batches from pinned retained packages. Zero I/O acquisition."""

import argparse
import hashlib
import json
from pathlib import Path

from pokemon_hunter.beta.catalog_imports import fingerprint

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "config/catalog-pipeline"


def read(name):
    return json.loads((ROOT / name).read_text())


def run(check=False):
    if check:
        for name, expected in read("config/catalog-pipeline/inputs.json")["files"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    u = read("config/sealed/2026-10-04/universe.json")
    index = read("config/sealed/2026-10-04/source-index.json")
    sources = index["sets"]
    manifest = dict(
        schema_version="dex-set-universe-v1",
        version="retained-20261004-m2-v1",
        source_url=sources["url"],
        source_time=sources["retrieved_at"],
        source_sha256=sources["sha256"],
        historical_input="config/sealed/2026-10-04/universe.json",
        historical_sha256=hashlib.sha256(
            (ROOT / "config/sealed/2026-10-04/universe.json").read_bytes()
        ).hexdigest(),
        market="US",
        current=False,
        sets=[],
    )
    # Provider existence supplies neither release certainty nor product distribution.
    # Retained reviewed packages demonstrate released cards; other release states stay uncertain.
    assessed = set(u["existing_shipped_packages"]) | {"sv03.5", "det1"}
    sets = []
    for e in u["sets"]:
        code = e["id"].split(":", 2)[2]
        manifest["sets"].append(
            dict(
                id=e["id"],
                provider="tcgdex",
                provider_set_id=code,
                internal_set_key=code,
                name=e["name"],
                language=e["language"],
                era=e["series"],
                medium=e["medium"],
                release_status="released" if code in assessed else "uncertain",
                source_url=index["series-" + e["series"]]["url"],
                source_time=index["series-" + e["series"]]["retrieved_at"],
                source_sha256=index["series-" + e["series"]]["sha256"],
                source_status="retained-usable",
                expected_full_set_count=e["expected_printings"],
            )
        )
        if code not in u["existing_shipped_packages"]:
            continue
        path = u["existing_shipped_packages"][code]["package"]
        p = read(path)
        sets.append(
            dict(
                set_id=e["id"],
                language="en",
                era=e["series"],
                medium="physical",
                release_status="released",
                source_url=p["source_url"],
                source_time=None,
                source_sha256=p["source_sha256"],
                evidence_class="retained-real-source",
                enumeration_complete=p["coverage"] == "catalog-entries"
                and len(p["cards"]) == p["expected_count"],
                enumerated_ids=[c["external_id"] for c in p["cards"]],
                package=p,
            )
        )
    for code, path in [
        ("sv03.5", "config/sealed/2026-10-04-151/package.json"),
        ("det1", "config/sealed/2026-10-05-det1-e1c/package.json"),
    ]:
        p = read(path)
        exp = next(e for e in u["sets"] if e["id"] == "tcgdex:en:" + code)
        if code == "det1":
            prior = next(
                e
                for e in read("config/sealed/2026-10-04-151/package.json")["expansions"]
                if e["id"] == exp["id"]
            )
            p["expansions"][0]["sources"] = prior["sources"] + p["expansions"][0]["sources"]
            p["corrections"] = [
                dict(
                    kind="expansions",
                    id=exp["id"],
                    before_sha256=fingerprint(prior),
                    reason="Retained enumeration adds D1d provenance; preserves October 4 universe sources",
                )
            ]
            p["version"] = "2026-10-05-det1-m2-reconciled-v1"
        source = next(s for s in p["sources"] if s["id"] == ("set151" if code == "sv03.5" else "d1d:set"))
        mappings = {}
        # Explicit detail source subject identities bind every variant to its numbered record.
        for r in p["printings"]:
            if r["id"] == "tcgdex:en:sv03.5-123:normal":
                mappings[r["id"]] = "sv03.5-123"
            else:
                sid = next(s for s in r["sources"] if s.startswith("detail:") or s.startswith("d1d:det1-"))
                mappings[r["id"]] = sid.split(":", 1)[1]
        sets.append(
            dict(
                set_id=exp["id"],
                language="en",
                era=exp["series"],
                medium="physical",
                release_status="released",
                source_url=source["url"],
                source_time=source["retrieved_at"],
                source_sha256=source["sha256"],
                evidence_class="retained-real-source",
                enumeration_complete=True,
                enumerated_ids=sorted(set(mappings.values())),
                numbered_mappings=mappings,
                package=p,
            )
        )
    batch = dict(
        schema_version="dex-target-batch-v1", version="retained-20261004-m2-v1", mode="checkpoint", sets=sets
    )
    for name, value in [("universe-20261004.json", manifest), ("retained-20261004.json", batch)]:
        data = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        if check:
            assert (DEST / name).read_text() == data
        else:
            (DEST / name).write_text(data)
    if not check:
        originals = [
            "config/sealed/2026-10-04/universe.json",
            "config/sealed/2026-10-04/source-index.json",
            "config/catalog-imports/staging-ten/source-manifest.json",
            "config/sealed/2026-10-04-151/package.json",
            "config/sealed/2026-10-05-det1-e1c/package.json",
        ]
        originals += [v["package"] for v in u["existing_shipped_packages"].values()]
        originals += [
            "config/catalog-pipeline/universe-20261004.json",
            "config/catalog-pipeline/retained-20261004.json",
        ]
        lock = dict(
            evidence_class="retained normalized metadata; source hashes/time remain inherited",
            files={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in originals},
        )
        (DEST / "inputs.json").write_text(json.dumps(lock, indent=2) + "\n")
    print(f"Historical universe: {len(manifest['sets'])} sets; retained batch: {len(sets)} sets")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    run(parser.parse_args().check)
