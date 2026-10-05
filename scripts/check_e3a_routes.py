"""Framework route rehearsal on prepared synthetic state; not browser evidence."""

import argparse
import json
from pathlib import Path
from unittest.mock import patch


def run(root, output):
    if not (root / "SYNTHETIC_ONLY").is_file():
        raise ValueError("Synthetic roots only")
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model
    from django.test import Client

    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import store

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    client = Client(HTTP_HOST="127.0.0.1:8011")
    client.force_login(get_user_model().objects.get(username="admin"))
    goals = sorted(
        [g for g in inv.goals(actor) if g["kind"] == "original151"],
        key=lambda g: g["definition"]["lineage"]["number"],
    )
    assertions = []
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No network")),
        patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No provider")),
    ):
        for g in goals:
            for label, filters in [
                ("whole-goal", {}),
                ("Scyther", {"species": "123"}),
                ("gap-filter", {"expansion": "unindexed"}),
            ]:
                response = client.get("/packs/", dict(goal=g["id"], **filters))
                assert response.status_code == 200
                text = response.content.decode()
                assert g["version"] in text
                if label == "gap-filter" or g == goals[0]:
                    assert "No compatible reviewed booster membership" in text
                elif label == "Scyther":
                    assert "#123 Scyther" in text and "1 possible missing species" in text
                    assert "Official contents and quantities remain unverified" in text
                    assert "Shipping: Unknown" in text and "Approximate original tool-read time" in text
                else:
                    assert "151 possible missing species" in text
                name = f"route-v{g['definition']['lineage']['number']}-{label}.html"
                (output / name).write_text(text)
                assertions.append(
                    dict(version=g["version"], label=label, status=200, assertions_passed=True, html=name)
                )
    (output / "route-assertions.json").write_text(
        json.dumps(
            dict(
                evidence_class="Django framework route checks, not browser displayed-state evidence",
                provider_calls=0,
                assertions=assertions,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.root, a.output)
