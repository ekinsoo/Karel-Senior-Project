"""
qr_fallback – Slower but more robust decoders (Tier 2 + Tier 3).

Tier 2: Contour-based ROI candidates → pylibdmtx   (~70 ms total).
Tier 3: Lightweight filters on pseudo-ROI → retry   (remaining budget).

These are only invoked when the fast path (Tiers 0–1) fails.
"""

from __future__ import annotations

import cv2
import numpy as np

from qr.qr_fast import (
    HAS_DMTX,
    try_dmtx,
    decode_qr,
    _gray,
)


# ── Settings ─────────────────────────────────────────────────────────────────
DMTX_ROI_TIMEOUT   = 50       # Per-ROI pylibdmtx timeout (ms)
CONTOUR_AREA_MIN   = 30 * 30
CONTOUR_AREA_MAX   = 250 * 250
CONTOUR_ASPECT_MIN = 0.4
MAX_CANDIDATES     = 8


# ── Tier 2: Contour-based DataMatrix candidate ROIs ─────────────────────────

def _find_dm_candidates(gray: np.ndarray):
    """Find small, roughly-square contours that might be DataMatrix codes."""
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    th = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 25, 10,
    )
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area = cw * ch
        if CONTOUR_AREA_MIN < area < CONTOUR_AREA_MAX:
            aspect = min(cw, ch) / max(cw, ch)
            if aspect > CONTOUR_ASPECT_MIN:
                candidates.append((x, y, cw, ch, area))

    candidates.sort(key=lambda c: c[4], reverse=True)
    return [(x, y, w, h) for x, y, w, h, _ in candidates[:MAX_CANDIDATES]]


def tier2_contour_rois(gray: np.ndarray, is_over_budget):
    """
    Detect DM candidate regions via contours, decode each small ROI.
    Returns (data, pts, type, method_tag) or Nones.
    """
    if not HAS_DMTX:
        return None, None, None, None

    candidates = _find_dm_candidates(gray)
    h_img, w_img = gray.shape[:2]

    for cx, cy, cw, ch in candidates:
        if is_over_budget():
            break
        pad = max(cw, ch)
        y0 = max(0, cy - pad)
        y1 = min(h_img, cy + ch + pad)
        x0 = max(0, cx - pad)
        x1 = min(w_img, cx + cw + pad)

        roi = gray[y0:y1, x0:x1]
        data, pts, typ = try_dmtx(roi, timeout_ms=DMTX_ROI_TIMEOUT)
        if data and pts is not None:
            pts[:, 0] += x0
            pts[:, 1] += y0
            return data, pts, typ, f"tier2_contour_{cx}_{cy}"

    return None, None, None, None


# ── Lightweight ROI filters ─────────────────────────────────────────────────

def _clahe(img: np.ndarray) -> np.ndarray:
    gray = _gray(img)
    cl = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return cl.apply(gray)


def _otsu(img: np.ndarray) -> np.ndarray:
    gray = _gray(img)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


_ROI_FILTERS = [
    ("clahe", _clahe),
    ("otsu",  _otsu),
]


# ── Tier 3: Filtered pseudo-ROI → all decoders ──────────────────────────────

def tier3_filtered_roi(gray: np.ndarray, is_over_budget):
    """
    Apply a couple of lightweight filters on the top-left quadrant (pseudo-ROI)
    and retry all decoders.  Last resort.
    Returns (data, pts, type, method_tag) or Nones.
    """
    h, w = gray.shape[:2]
    roi = gray[0 : h // 2, 0 : w // 2]

    for fname, ffunc in _ROI_FILTERS:
        if is_over_budget():
            break
        filtered = ffunc(roi)
        bgr = cv2.cvtColor(filtered, cv2.COLOR_GRAY2BGR)

        # QR decoders
        data, pts, typ = decode_qr(bgr)
        if data:
            return data, pts, typ, f"tier3_qr_{fname}"

        # DataMatrix
        if HAS_DMTX:
            data, pts, typ = try_dmtx(filtered, timeout_ms=DMTX_ROI_TIMEOUT)
            if data:
                return data, pts, typ, f"tier3_dm_{fname}"

    return None, None, None, None
