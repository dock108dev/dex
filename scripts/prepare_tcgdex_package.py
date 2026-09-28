"""Convert a saved TCGdex set response into the ordinary B4 importer format.

Metadata only: no artwork, card rules text, prices or private information are copied.
Usage: uv run python scripts/prepare_tcgdex_package.py --source SET.json --output PACKAGE.json --version DATE
Download/source review is an explicit operator task, never a background network import.
"""

import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--version", required=True)
args = parser.parse_args()
raw = args.source.read_bytes()
source = json.loads(raw)
package = {
    "schema_version": "dex-catalog-v1",
    "game": "pokemon",
    "set_key": source["id"],
    "set_name": source["name"],
    "language": "en",
    "aliases": [source["name"], source.get("tcgOnline", source["id"])],
    "provider": "tcgdex",
    "version": args.version + "-" + hashlib.sha256(raw).hexdigest()[:12],
    "source_url": "https://api.tcgdex.net/v2/en/sets/" + source["id"],
    "source_sha256": hashlib.sha256(raw).hexdigest(),
    "metadata_permission": "TCGdex cards-database: MIT, copyright (c) 2021 TCGdex; license retained in TCGDEX_LICENSE.txt. Local catalog metadata only.",
    "image_permission": "not-included",
    "coverage": "catalog-entries",
    "expected_count": source["cardCount"]["total"],
    "cards": [{"external_id": c["id"], "number": c["localId"], "name": c["name"]} for c in source["cards"]],
}
args.output.write_text(json.dumps(package, indent=2) + "\n")
print("Prepared metadata-only package. Review, verify and publish through Catalog review.")
