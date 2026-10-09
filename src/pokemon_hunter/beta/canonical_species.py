"""Catalog identity authority; goal denominators and eligibility remain separate.

The packaged public registry pins official species provenance for 1,025 species.
No provider request or mutable database row supplies catalog identity authority.
"""

import hashlib
import json
from functools import cache

from pokemon_hunter.runtime_data import root

REGISTRY = root() / "config/sealed/2026-10-04/package.json"
REGISTRY_SHA256 = "ec4c1f062ec822e44793de381390c626da4b8c59d0935879a52c5e6b74e85313"


@cache
def registry():
    raw = REGISTRY.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REGISTRY_SHA256:
        raise ValueError("Retained canonical registry drift; explicit registry review required")
    rows = json.loads(raw)["species"]
    result = {r["dex"]: r for r in rows}
    if (
        len(rows) != len(result)
        or len(result) != 1025
        or any(type(n) is not int or r["id"] != f"ndex:{n:04}" for n, r in result.items())
    ):
        raise ValueError("Malformed retained canonical registry")
    return result


def require(number):
    if type(number) is not int or number not in registry():
        raise ValueError("Unsupported canonical species in retained registry")
    return registry()[number]["id"]
