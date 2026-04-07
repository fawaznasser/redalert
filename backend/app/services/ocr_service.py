from __future__ import annotations

import io
import logging
import threading
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

from app.config import settings

logger = logging.getLogger(__name__)

_reader_lock = threading.Lock()
_reader = None


@dataclass(slots=True)
class OCRResult:
    text: str | None = None
    label_color: str | None = None
    attack_side: str | None = None
    engine: str = "easyocr"


def _normalized_ocr_languages() -> list[str]:
    languages = [item.strip() for item in str(settings.ocr_languages or "").split(",") if item.strip()]
    return languages or ["en"]


def _get_reader():
    global _reader
    if _reader is not None:
        return _reader

    with _reader_lock:
        if _reader is not None:
            return _reader

        import easyocr

        _reader = easyocr.Reader(_normalized_ocr_languages(), gpu=False, verbose=False)
        return _reader


def _prepare_image_bytes(image_bytes: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(image_bytes)) as image:
        processed = ImageOps.exif_transpose(image).convert("RGB")
        # A mild upscale helps compact Telegram stickers and screenshots.
        width, height = processed.size
        if max(width, height) < 1600:
            processed = processed.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        return np.array(processed)


def _dominant_label_color(image_array: np.ndarray) -> str | None:
    if image_array.ndim != 3 or image_array.shape[2] < 3:
        return None

    height = image_array.shape[0]
    if height <= 0:
        return None

    band_height = max(24, int(height * 0.2))
    candidates = (
        image_array[:band_height, :, :3],
        image_array[-band_height:, :, :3],
    )

    best_color: str | None = None
    best_score = 0.0

    for band in candidates:
        pixels = band.reshape(-1, 3).astype(np.int16)
        if pixels.size == 0:
            continue

        r = pixels[:, 0]
        g = pixels[:, 1]
        b = pixels[:, 2]
        vivid = (np.maximum.reduce([r, g, b]) >= 90) & ((np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b])) >= 50)
        if not np.any(vivid):
            continue

        vivid_pixels = pixels[vivid]
        r = vivid_pixels[:, 0]
        g = vivid_pixels[:, 1]
        b = vivid_pixels[:, 2]

        rgb = vivid_pixels.astype(np.float32) / 255.0
        r_f = rgb[:, 0]
        g_f = rgb[:, 1]
        b_f = rgb[:, 2]
        maxc = np.maximum.reduce([r_f, g_f, b_f])
        minc = np.minimum.reduce([r_f, g_f, b_f])
        delta = maxc - minc
        sat = np.divide(delta, np.maximum(maxc, 1e-6))
        val = maxc
        hue = np.zeros_like(maxc)

        red_idx = delta > 1e-6
        r_max = red_idx & (maxc == r_f)
        g_max = red_idx & (maxc == g_f)
        b_max = red_idx & (maxc == b_f)
        hue[r_max] = (60.0 * ((g_f[r_max] - b_f[r_max]) / delta[r_max])) % 360.0
        hue[g_max] = 60.0 * (((b_f[g_max] - r_f[g_max]) / delta[g_max]) + 2.0)
        hue[b_max] = 60.0 * (((r_f[b_max] - g_f[b_max]) / delta[b_max]) + 4.0)

        red_mask = (
            (((hue <= 18.0) | (hue >= 345.0)) & (sat >= 0.38) & (val >= 0.35))
            | ((r >= 135) & (r >= g + 38) & (r >= b + 25))
        )
        purple_mask = (
            (((hue >= 255.0) & (hue <= 330.0)) & (sat >= 0.22) & (val >= 0.28))
            | ((r >= 90) & (b >= 90) & (g <= np.minimum(r, b) - 12) & (np.abs(r - b) <= 120))
        )
        orange_mask = (
            (((hue >= 18.0) & (hue <= 42.0)) & (sat >= 0.45) & (val >= 0.35))
            | ((r >= 135) & (g >= 70) & (g <= r - 18) & (b <= g - 12))
        )
        green_mask = (
            (((hue >= 58.0) & (hue <= 165.0)) & (sat >= 0.18) & (val >= 0.20) & (g_f >= r_f * 0.88) & (g_f >= b_f * 1.04))
            | ((g >= 72) & (g >= r + 6) & (g >= b + 8) & ((g - b) >= 6))
        )

        total = float(len(vivid_pixels))
        red_score = float(np.count_nonzero(red_mask)) / total
        purple_score = float(np.count_nonzero(purple_mask)) / total
        orange_score = float(np.count_nonzero(orange_mask)) / total
        green_score = float(np.count_nonzero(green_mask)) / total

        if purple_score >= 0.035 and purple_score >= red_score * 0.65 and purple_score > best_score:
            best_color = "purple"
            best_score = purple_score
            continue

        if orange_score >= 0.05 and orange_score >= red_score * 0.7 and orange_score >= green_score * 1.2 and orange_score > best_score:
            best_color = "orange"
            best_score = orange_score
            continue

        if green_score >= 0.035 and green_score > best_score and green_score >= orange_score * 0.72:
            best_color = "green"
            best_score = green_score
            continue

        for color, score in (("red", red_score), ("purple", purple_score), ("orange", orange_score), ("green", green_score)):
            if score >= 0.08 and score > best_score:
                best_color = color
                best_score = score

    return best_color


def detect_attack_side_from_image_bytes(image_bytes: bytes) -> tuple[str | None, str | None]:
    if not image_bytes:
        return None, None

    try:
        image_array = _prepare_image_bytes(image_bytes)
    except Exception:
        logger.exception("Failed to prepare Telegram media for label-color analysis")
        return None, None

    label_color = _dominant_label_color(image_array)
    if label_color == "red":
        return label_color, "enemy_attack"
    if label_color == "orange":
        return label_color, "enemy_attack"
    if label_color == "purple":
        return label_color, "resistance_attack"
    if label_color == "green":
        return label_color, None
    return None, None


def extract_ocr_text_from_bytes(image_bytes: bytes) -> OCRResult | None:
    if not settings.ocr_enabled or not image_bytes:
        return None

    label_color, attack_side = detect_attack_side_from_image_bytes(image_bytes)

    try:
        image_array = _prepare_image_bytes(image_bytes)
        reader = _get_reader()
        segments = reader.readtext(image_array, detail=0, paragraph=True)
    except Exception:
        logger.exception("OCR failed while processing Telegram media")
        return OCRResult(label_color=label_color, attack_side=attack_side) if label_color or attack_side else None

    text = "\n".join(str(segment).strip() for segment in segments if str(segment).strip()).strip()
    if not text and not label_color and not attack_side:
        return None
    return OCRResult(text=text or None, label_color=label_color, attack_side=attack_side)
