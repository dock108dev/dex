import json
from pathlib import Path


def read_pokedex(path: Path) -> list[dict]:
    authoritative = path.with_name("pokedex_251.json")
    if authoritative.exists():
        from .collection import read

        return [
            {
                "dex_number": r["dex_number"],
                "pokemon_name": r["name"],
                "generation": r["generation"],
                "owned": r["dex_owned"],
            }
            for r in read(authoritative)["pokedex"].values()
        ]
    rows = json.loads(path.read_text())
    if not isinstance(rows, list) or len(rows) != 251:
        raise ValueError("Pokédex must contain all 251 entries")
    if {r["dex_number"] for r in rows} != set(range(1, 252)):
        raise ValueError("Pokédex numbers must be unique and cover 1–251")
    for row in rows:
        if type(row["owned"]) is not bool or not row["pokemon_name"]:
            raise ValueError("Every Pokédex entry needs a name and boolean owned value")
        if row["generation"] != (1 if row["dex_number"] <= 151 else 2):
            raise ValueError("Pokédex generation does not match number")
    return rows


def missing_rates(rows: list[dict]) -> tuple[float, float]:
    return tuple(
        sum(not r["owned"] for r in rows if r["generation"] == g) / size for g, size in [(1, 151), (2, 100)]
    )


def summary(rows: list[dict]) -> str:
    k, j = (sum(r["owned"] for r in rows if r["generation"] == g) for g in (1, 2))
    return f"Kanto {k}/151 · Johto {j}/100 · Total {k + j}/251 · Missing {251 - k - j}"
