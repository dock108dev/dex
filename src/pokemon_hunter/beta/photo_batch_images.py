"""In-memory photo normalization, bounded crops and advisory duplicate hints.

Callers supply image bytes and already authorized crop records. This module never
reads account storage, records admission, selects a printing or merges objects.
"""

import hashlib
import io
import warnings

from PIL import Image, ImageOps

from . import photo_contracts as protocol


def source(upload):
    if upload.size > 8_000_000:
        raise ValueError("Use a photo at most 8 MB")
    data = upload.read(8_000_001)
    if len(data) > 8_000_000:
        raise ValueError("Use a photo at most 8 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                if im.format not in {"JPEG", "PNG", "WEBP"} or getattr(im, "n_frames", 1) != 1:
                    raise ValueError
                w, h = im.size
                if min(w, h) < 200 or w * h > 24_000_000 or max(w, h) > 10000:
                    raise ValueError
                im.load()
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((4096, 4096))
                clean = Image.new("RGB", im.size)
                clean.paste(im)
                out = io.BytesIO()
                clean.save(out, "JPEG", quality=90)
                normalized = out.getvalue()
                # Canonical pixels prevent metadata/format changes from resubmitting one photo.
                digest = hashlib.sha256(str(clean.size).encode() + clean.tobytes()).hexdigest()
                return normalized, digest, len(data)
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Use one JPEG/PNG/WebP frame, minimum 200px edge, maximum 24 MP") from None


def crop_bytes(content, box):
    box = protocol.Box.model_validate(box)
    with Image.open(io.BytesIO(content)) as im:
        w, h = im.size
        coords = (
            round(box.x * w),
            round(box.y * h),
            round((box.x + box.width) * w),
            round((box.y + box.height) * h),
        )
        if coords[2] - coords[0] < 20 or coords[3] - coords[1] < 20:
            raise ValueError("Crop must be at least 20 pixels per edge")
        cropped = im.crop(coords).rotate(-box.rotation, expand=True)
        out = io.BytesIO()
        cropped.save(out, "JPEG", quality=90)
        return protocol.attachment(out.getvalue(), 1024, 500_000)


def perceptual_hash(content):
    with Image.open(io.BytesIO(content)) as im:
        pixels = list(im.convert("L").resize((8, 8)).tobytes())
        avg = sum(pixels) / 64
        return sum((1 << i) for i, p in enumerate(pixels) if p >= avg)


def duplicate_pairs(crops, hashes):
    # Same printing or similar pixels never establishes the same physical object.
    pairs = []
    active = [c for c in crops if c["state"] == "active"]
    for i, c in enumerate(active):
        for other in active[i + 1 :]:
            a, b = c["row_json"], other["row_json"]
            same_printing = bool(a.get("printing_id") and a.get("printing_id") == b.get("printing_id"))
            similar = (
                c["id"] in hashes
                and other["id"] in hashes
                and (hashes[c["id"]] ^ hashes[other["id"]]).bit_count() <= 5
            )
            if same_printing or (similar and c["photo_id"] != other["photo_id"]):
                pairs.append(
                    dict(
                        first=c["id"], second=other["id"], same_printing=same_printing, similar_pixels=similar
                    )
                )
    return pairs
