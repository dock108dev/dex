"""Refresh a bounded snapshot of public PriceCharting guide estimates for owned cards."""

import html
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from time import sleep

import httpx

from pokemon_hunter.collection import read

ROOT = Path(__file__).resolve().parents[1]
SET_SLUGS = {
    "base_set": "pokemon-base-set",
    "base_set_2": "pokemon-base-set-2",
    "jungle": "pokemon-jungle",
    "fossil": "pokemon-fossil",
    "team_rocket": "pokemon-team-rocket",
    "wizards_black_star_promos": "pokemon-promo",
    "neo_genesis": "pokemon-neo-genesis",
    "neo_discovery": "pokemon-neo-discovery",
    "neo_revelation": "pokemon-neo-revelation",
    "neo_destiny": "pokemon-neo-destiny",
}


def name_key(name):
    return re.sub(r"[^a-z0-9]", "", name.casefold().replace("♀", "").replace("♂", ""))


def main():
    data = read(ROOT / "config/pokedex_251.json")
    owned = [c for c in data["cards"].values() if c["owned"]]
    rows, failures = [], []
    with httpx.Client(timeout=25, follow_redirects=True) as client:
        for set_id in dict.fromkeys(c["set_id"] for c in owned):
            slug = SET_SLUGS[set_id]
            url = f"https://www.pricecharting.com/console/{slug}"
            response = client.get(url)
            for page in range(6):
                if response.status_code != 200:
                    failures.append({"url": url, "status": response.status_code})
                    break
                for block in re.findall(r'<tr id="product-[\s\S]*?</tr>', response.text):
                    link = re.search(r'<a href="(/game/[^"]+)">([^<]+)</a>', block)
                    if not link:
                        continue
                    label = html.unescape(link[2]).strip()
                    match = re.fullmatch(r"(.+?)\s+#(\d+)", label)
                    if not match:
                        continue
                    name, number = match.groups()
                    edition = "first_edition" if "[1st Edition]" in name else "standard"
                    name = name.replace("[1st Edition]", "").strip()
                    card = next(
                        (
                            c
                            for c in owned
                            if c["set_id"] == set_id
                            and c["number"] == number
                            and name_key(c["name"]) == name_key(name)
                        ),
                        None,
                    )
                    if not card:
                        continue
                    values = {}
                    for grade, field in {"raw": "used_price", "9": "cib_price", "10": "new_price"}.items():
                        price = re.search(
                            r'<td class="price numeric '
                            + field
                            + r'">\s*<span class="js-price">\$([\d,]+\.\d{2})',
                            block,
                        )
                        if price:
                            values[grade] = Decimal(price[1].replace(",", ""))
                    # Rough geometric interpolation; never presented as observed grade sales.
                    if values.get("raw", 0) > 0 and values.get("9", 0) >= values["raw"]:
                        ratio = values["9"] / values["raw"]
                        values["7"] = values["raw"] * ratio ** (Decimal(1) / 3)
                        values["8"] = values["raw"] * ratio ** (Decimal(2) / 3)
                    for grade, value in values.items():
                        rows.append(
                            dict(
                                card_id=card["card_id"],
                                edition=edition,
                                grade=grade,
                                value=str(value.quantize(Decimal(".01"))),
                                grader="Guide",
                                currency="USD",
                                source_url="https://www.pricecharting.com" + link[1],
                                as_of=date.today().isoformat(),
                                variant_verified=True,
                                estimated=grade in ("7", "8"),
                                basis="Interpolated between ungraded and Grade 9"
                                if grade in ("7", "8")
                                else "PriceCharting guide estimate",
                            )
                        )
                form = re.search(r'<form method="POST"[^>]+class="next_page[\s\S]*?</form>', response.text)
                if not form:
                    break
                fields = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', form[0]))
                sleep(1)
                response = client.post(url, data=fields)
            print(f"{set_id}: {len(rows)} prices", flush=True)
            if failures:
                break
            sleep(1)
    path = ROOT / "config/market_values.json"
    previous = (
        {(r["card_id"], r["edition"], r["grade"]): r for r in json.loads(path.read_text())}
        if path.exists()
        else {}
    )
    for row in rows:
        key = (row["card_id"], row["edition"], row["grade"])
        old = previous.get(key)
        if row["estimated"] and old and not old.get("estimated") and old["as_of"] == row["as_of"]:
            continue
        previous[key] = row
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(list(previous.values()), indent=2) + "\n")
    temp.replace(path)
    report = {"checked_on": date.today().isoformat(), "records": len(rows), "failures": failures}
    (ROOT / "data/value-refresh.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
