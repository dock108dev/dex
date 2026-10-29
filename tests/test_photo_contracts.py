"""Provider-neutral photo contracts and cleanup of historical temporary payloads."""

import io
import json
import time
import uuid

import pytest
from photo_batch_helpers import BOX, DETECTION
from PIL import Image

from pokemon_hunter.beta import photo_contracts as protocol
from pokemon_hunter.beta import photo_payload_cleanup as cleanup


def test_schema_crop_ids_and_abstention():
    cid = str(uuid.uuid4())
    clue = dict(
        crop_id=cid,
        status="unreadable",
        name=None,
        set_name=None,
        number=None,
        language=None,
        edition=None,
        finish=None,
        variant=None,
        reason="glare",
    )
    payload = dict(schema_version="dex-identities-v1", crops=[clue])
    assert protocol.validate("identity", json.dumps(payload), [cid]) == payload
    for bad in [
        {**payload, "crops": [clue, clue]},
        {**payload, "crops": [{**clue, "name": "guess"}]},
        {**payload, "catalog_id": "made-up"},
    ]:
        with pytest.raises(ValueError):
            protocol.validate("identity", json.dumps(bad), [cid])
    with pytest.raises(ValueError):
        protocol.validate("identity", json.dumps(payload), [str(uuid.uuid4())])
    assert (
        protocol.validate(
            "detection", json.dumps(dict(schema_version="dex-detection-v1", status="refused", boxes=[]))
        )["status"]
        == "refused"
    )
    with pytest.raises(ValueError):
        protocol.validate("detection", json.dumps({**DETECTION, "boxes": [BOX] * 16}))


def test_attachment_dimensions_and_limits():
    out = io.BytesIO()
    Image.new("RGB", (4096, 3000), "green").save(out, "JPEG")
    for edge, ceiling in [(1600, 2_000_000), (1024, 500_000)]:
        content = protocol.attachment(out.getvalue(), edge, ceiling)
        assert len(content) <= ceiling
        with Image.open(io.BytesIO(content)) as im:
            assert max(im.size) <= edge


def test_registered_crash_payload_cleanup_never_sweeps_unowned(tmp_path):
    home = cleanup.payload_home(tmp_path, create=True)
    owned = home / "dex-batch-owned"
    owned.mkdir(mode=0o700)
    unrelated = home / "dex-batch-unregistered"
    unrelated.mkdir(mode=0o700)
    (owned / "selected.jpg").write_bytes(b"engineering pixels")
    registry = home / "owned.jsonl"
    registry.write_text(json.dumps(dict(name=owned.name, created=time.time() - 100)) + "\n")
    cleanup.cleanup_payloads(tmp_path)
    assert not owned.exists() and unrelated.exists()
