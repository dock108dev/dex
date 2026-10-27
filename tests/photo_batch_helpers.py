"""Shared synthetic photo-batch fixtures and fake recognition processes."""

import io
import json
import sys
import uuid

import pytest
from django.conf import settings
from PIL import Image
from test_b3 import image
from test_bulk_onboarding import b2, b3, b4, bulk, cx, e1, env, snapshot

from pokemon_hunter.beta import codex_recognition as cli
from pokemon_hunter.beta import photo_batches as batches
from pokemon_hunter.beta import store

__all__ = ["b2", "b3", "b4", "bulk", "cx", "e1", "env", "snapshot"]
BOX = dict(x=0.05, y=0.05, width=0.8, height=0.8, rotation=0, issues=[])
DETECTION = dict(schema_version="dex-detection-v1", status="proposed", boxes=[BOX])


@pytest.fixture
def photos(bulk):
    batches.initialize()
    batches.initialize()
    (settings.ROOT / "scan-config.json").write_text('{"mode":"codex_cli"}')
    bulk["session"] = bulk["a"].session.session_key
    return bulk


def staged(cx):
    a = cx["actor"]
    b = batches.create(a, str(uuid.uuid4()))
    return batches.admit(
        a, b["id"], b["revision"], image((400 + len(store.rows("SELECT id FROM scan_batches")), 600))
    )


def cropped(cx, b=None, n=1):
    b = b or staged(cx)
    return batches.layout(
        cx["actor"], b["id"], b["revision"], b["photos"][-1]["id"], [dict(id=None, box=BOX) for _ in range(n)]
    )


def selected(cx, b=None, n=1, retain=True):
    b = cropped(cx, b, n)
    for c in b["crops"]:
        if c["state"] == "active":
            b = batches.select_crop(
                cx["actor"],
                b["id"],
                b["revision"],
                c["id"],
                dict(printing_id=cx["by_legacy"]["c"]["id"]),
                True,
                retain,
                "different",
            )
    return b


def fake(tmp_path, monkeypatch, body):
    p = tmp_path / "fake-codex"
    p.write_text(
        f"#!{sys.executable}\nimport sys,os,json,time,stat,subprocess\nfrom pathlib import Path\nargs=sys.argv[1:]\n"
        + body
    )
    p.chmod(0o700)
    monkeypatch.setattr(cli.shutil, "which", lambda _: str(p))
    return p


def success(payload=DETECTION, usage=True):
    return f"Path(args[args.index('-o')+1]).write_text({json.dumps(json.dumps(payload))})\nprint({json.dumps(json.dumps(dict(type='turn.completed', **({'usage': {'input_tokens': 20, 'output_tokens': 3}} if usage else {}))))})\n"


def run(tmp_path, stage="detection", crop_ids=(), cancelled=lambda: False, timeout=1):
    im = io.BytesIO()
    Image.new("RGB", (400, 600), "blue").save(im, "JPEG")
    return cli.recognize_batch(
        stage, [im.getvalue()] * (len(crop_ids) or 1), tmp_path, cancelled, timeout, crop_ids
    )
