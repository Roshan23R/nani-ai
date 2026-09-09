"""Convert camera formats Bedrock will not accept.

iPhones shoot HEIC by default. A patient photographing a prescription with the
phone in their hand produces exactly the file Bedrock rejects, so refusing it
would fail the most likely upload in the product.

Two encoder settings were measured against a real handwritten prescription,
because handwriting legibility is the whole game here:

    3000px long edge, baseline      -> CBC: "Hb/TC/DC/ESR"   correct
    3000px long edge, progressive   -> CBC: "Hb% RBC ESR"    misread
    2000px long edge, either        -> CBC: "Hb% RBC ESR"    misread

So: baseline JPEG, never progressive, and do not shrink below ~3000px. A full
4284px encode also exceeds Bedrock's 5 MB image cap, which is what pushed the
first version into progressive compression and quietly cost accuracy.
"""

from __future__ import annotations

import io
import logging
import os

log = logging.getLogger(__name__)

#: Formats we can convert into something Bedrock accepts.
CONVERTIBLE = {"heic", "heif", "bmp", "tiff", "tif"}

#: Bedrock rejects images over 5 MB. Leave headroom for base64 overhead.
MAX_BYTES = 4_500_000
#: Measured sweet spot: enough detail for handwriting, small enough to encode
#: baseline under the size cap. Larger is not better once Bedrock resamples.
MAX_EDGE = 3000
#: Below this, panel names start being misread. Do not trade past it.
MIN_EDGE = 2600

_JPEG_QUALITY = 92
_registered = False


def _ensure_heif() -> None:
    global _registered
    if _registered:
        return
    import pillow_heif

    pillow_heif.register_heif_opener()
    _registered = True


def needs_conversion(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower().lstrip(".") in CONVERTIBLE


def to_jpeg(data: bytes, filename: str = "") -> bytes:
    """Return JPEG bytes Bedrock will accept. Raises ValueError if it cannot."""
    _ensure_heif()
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"could not decode {filename or 'the image'}: {exc}") from exc

    # EXIF orientation: phone photos are routinely stored rotated, and a
    # sideways prescription extracts badly.
    try:
        from PIL import ImageOps

        image = ImageOps.exif_transpose(image)
    except Exception:  # noqa: BLE001
        pass

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    if max(image.size) > MAX_EDGE:
        image.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        log.info("%s resized to %s for extraction", filename, image.size)

    out = _encode(image, _JPEG_QUALITY)

    # Only now trade away detail, and only as much as it takes to fit.
    quality = _JPEG_QUALITY
    while len(out) > MAX_BYTES and quality > 55:
        quality -= 10
        out = _encode(image, quality)
    while len(out) > MAX_BYTES and max(image.size) > MIN_EDGE:
        image.thumbnail((int(image.width * 0.9), int(image.height * 0.9)), Image.LANCZOS)
        out = _encode(image, quality)
    if len(out) > MAX_BYTES:
        raise ValueError(f"{filename or 'image'} is too large to send even after resizing")

    log.info("converted %s -> jpeg %s q%d, %.1f MB", filename, image.size, quality, len(out) / 1e6)
    return out


def _encode(image, quality: int) -> bytes:
    # progressive=True measurably degrades handwriting extraction. Never set it.
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True, progressive=False)
    return buf.getvalue()
