"""Create empty local state without ever overwriting an existing collection."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
for name in ("pokedex_251.json", "settings.yaml"):
    target = root / "config" / name
    source = target.with_name(target.stem + ".example" + target.suffix)
    if not target.exists():
        with target.open("xb") as output:
            output.write(source.read_bytes())

values = root / "config/market_values.json"
if not values.exists():
    with values.open("x") as output:
        output.write("[]\n")
