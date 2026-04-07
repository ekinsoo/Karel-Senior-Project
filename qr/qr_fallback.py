"""
qr_fallback – Slower but more robust decoders (Tier 2 + Tier 3).

Tier 2:
    Label-like ROI candidates -> try QR + DataMatrix on multiple ROI variants

Tier 3:
    Whole image / major subregions with lightweight filters -> retry decoders

These are only invoked when the fast path (Tiers 0–1) fails.
"""

from __future__ import annotations

import cv2
import numpy as np

from qr.qr_fast import (
    HAS_DM_DECODER,
    try_dmtx,
    decode_qr,
    _gray,
)

# ── Settings ────────────────────────────────────────────────────────────────
DMTX_ROI_TIMEOUT = 80
MAX_CANDIDATES = 10


# ── Candidate search: label-like regions ───────────────────────────────────

def _find_dm_candidates(gray: np.ndarray):
    """
    Find white label-like rectangular regions that may contain a DataMatrix.
    Especially useful for PCB labels with text + code sticker.
    Returns candidate bounding boxes sorted by area.
    """
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # White labels are easier to isolate with normal binary threshold
    th = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        8,
    )

    kernel = np.ones((3, 3), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h_img, w_img = gray.shape[:2]
    candidates = []

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h

        # Small / huge regions are not useful
        if area < 80 * 80 or area > 500 * 500:
            continue

        # Sticker on your board is usually portrait-ish, not super flat
        aspect = w / float(h)
        if not (0.35 <= aspect <= 1.2):
            continue

        # Ignore border-touching junk
        if x <= 3 or y <= 3 or (x + w) >= (w_img - 3) or (y + h) >= (h_img - 3):
            continue

        perimeter = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * perimeter, True)

        score = float(area)
        if len(approx) == 4:
            score *= 1.2

        candidates.append((x, y, w, h, score))

    candidates.sort(key=lambda t: t[4], reverse=True)
    return [(x, y, w, h) for x, y, w, h, _ in candidates[:MAX_CANDIDATES]]


# ── Lightweight ROI filters ────────────────────────────────────────────────

def _clahe(img: np.ndarray) -> np.ndarray:
    gray = _gray(img)
    cl = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return cl.apply(gray)


def _otsu(img: np.ndarray) -> np.ndarray:
    gray = _gray(img)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def _sharpen(img: np.ndarray) -> np.ndarray:
    gray = _gray(img)
    kernel = np.array(
        [[0, -1, 0],
         [-1, 5, -1],
         [0, -1, 0]],
        dtype=np.float32,
    )
    return cv2.filter2D(gray, -1, kernel)


_ROI_FILTERS = [
    ("raw", lambda x: _gray(x)),
    ("clahe", _clahe),
    ("otsu", _otsu),
    ("sharpen", _sharpen),
]


# ── ROI variants inside label ──────────────────────────────────────────────

def _dm_roi_variants(roi: np.ndarray):
    """
    Generate likely subregions inside a label ROI.
    For your PCB stickers, DataMatrix is often in lower or lower-left area.
    """
    h, w = roi.shape[:2]

    variants = [("full", roi)]

    if h < 10 or w < 10:
        return variants

    variants.append(("bottom_half", roi[h // 2:h, 0:w]))
    variants.append(("bottom_left", roi[h // 2:h, 0:int(w * 0.7)]))
    variants.append(("lower_center", roi[int(h * 0.35):h, int(w * 0.15):int(w * 0.85)]))

    return variants


def _decode_roi_all(roi: np.ndarray):
    """
    Try multiple lightweight variants on one ROI.
    QR first, then DataMatrix.
    """
    for fname, ffunc in _ROI_FILTERS:
        filtered = ffunc(roi)

        h, w = filtered.shape[:2]
        if max(h, w) < 220:
            scale = max(2, int(220 / max(1, max(h, w))))
            filtered = cv2.resize(
                filtered,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )

        bgr = cv2.cvtColor(filtered, cv2.COLOR_GRAY2BGR)

        # QR
        data, pts, typ = decode_qr(bgr)
        if data:
            return data, pts, typ, f"qr_{fname}"

        # DataMatrix
        if HAS_DM_DECODER:
            data, pts, typ = try_dmtx(filtered, timeout_ms=DMTX_ROI_TIMEOUT)
            if data:
                return data, pts, typ, f"dm_{fname}"

    return None, None, None, None


# ── Tier 2: candidate label ROIs ───────────────────────────────────────────

def tier2_contour_rois(gray: np.ndarray, is_over_budget):
    """
    Detect label-like candidate ROIs and decode inside them.
    Returns (data, pts, type, method_tag) or Nones.
    """
    candidates = _find_dm_candidates(gray)
    h_img, w_img = gray.shape[:2]

    for cx, cy, cw, ch in candidates:
        if is_over_budget():
            break

        pad = int(max(cw, ch) * 0.15) + 8
        y0 = max(0, cy - pad)
        y1 = min(h_img, cy + ch + pad)
        x0 = max(0, cx - pad)
        x1 = min(w_img, cx + cw + pad)

        roi = gray[y0:y1, x0:x1]

        # Try whole ROI first
        data, pts, typ, tag = _decode_roi_all(roi)
        if data:
            pts_box = np.array([
                [x0, y0],
                [x1, y0],
                [x1, y1],
                [x0, y1],
            ], dtype=np.float32)
            return data, pts_box, typ, f"tier2_contour_{tag}_{cx}_{cy}"

        # Then try likely subregions inside label
        for vname, subroi in _dm_roi_variants(roi):
            if is_over_budget():
                break
            if subroi.size == 0:
                continue

            data, pts, typ, tag = _decode_roi_all(subroi)
            if data:
                pts_box = np.array([
                    [x0, y0],
                    [x1, y0],
                    [x1, y1],
                    [x0, y1],
                ], dtype=np.float32)
                return data, pts_box, typ, f"tier2_contour_{vname}_{tag}_{cx}_{cy}"

    return None, None, None, None


# ── Tier 3: broader filtered retries ───────────────────────────────────────

def tier3_filtered_roi(gray: np.ndarray, is_over_budget):
    """
    Last resort: try whole image and major subregions with filters.
    """
    h, w = gray.shape[:2]

    rois = [
        ("full", gray),
        ("center", gray[h // 4: 3 * h // 4, w // 4: 3 * w // 4]),
        ("tl", gray[0:h // 2, 0:w // 2]),
        ("tr", gray[0:h // 2, w // 2:w]),
        ("bl", gray[h // 2:h, 0:w // 2]),
        ("br", gray[h // 2:h, w // 2:w]),
    ]

    for rname, roi in rois:
        if is_over_budget():
            break
        if roi.size == 0:
            continue

        data, pts, typ, tag = _decode_roi_all(roi)
        if data:
            return data, pts, typ, f"tier3_{rname}_{tag}"

    return None, None, None, None
