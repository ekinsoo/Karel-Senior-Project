"""
qr_fast – Fastest-path decoders (Tier 0 + Tier 1).

Tier 0: OpenCV QRCodeDetector + pyzbar on a downscaled image (~5 ms).
Tier 1: Overlapping 2×2 quadrant tiles → pylibdmtx        (~15 ms per tile).
"""

from __future__ import annotations

import cv2
import numpy as np

# ── Optional decoder imports (graceful degradation) ──────────────────────────
try:
    from pyzbar import pyzbar
    HAS_PYZBAR = True
except ImportError:
    HAS_PYZBAR = False

try:
    from pylibdmtx import pylibdmtx
    HAS_DMTX = True
except ImportError:
    HAS_DMTX = False


# ── Settings ─────────────────────────────────────────────────────────────────
DETECT_MAX_WIDTH = 640       # Downscale ceiling for Tier 0
TILE_OVERLAP     = 0.15      # Fractional overlap between quadrant tiles
DMTX_TILE_TIMEOUT = 80       # Per-tile pylibdmtx timeout (ms)


# ── Low-level decoders ───────────────────────────────────────────────────────

_cv_qr = cv2.QRCodeDetector()


def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def try_cv_qr(img: np.ndarray):
    """OpenCV QRCodeDetector — fastest, C++ backend, QR only."""
    try:
        data, pts, _ = _cv_qr.detectAndDecode(img)
        if data and pts is not None:
            return data, pts[0].astype(np.float32), "QRCODE"
    except cv2.error:
        pass
    return None, None, None


def try_pyzbar(img: np.ndarray):
    """pyzbar/zbar — robust for QR + 1-D barcodes."""
    if not HAS_PYZBAR:
        return None, None, None
    gray = _gray(img)
    try:
        results = pyzbar.decode(gray)
        if results:
            obj = results[0]
            data = obj.data.decode("utf-8", errors="replace")
            pts = np.array(obj.polygon, dtype=np.float32)
            return data, pts, str(obj.type)
    except Exception:
        pass
    return None, None, None


def try_dmtx(img: np.ndarray, timeout_ms: int = DMTX_TILE_TIMEOUT):
    """pylibdmtx — the only option for DataMatrix.  SLOW on large images."""
    if not HAS_DMTX:
        return None, None, None
    gray = _gray(img)
    try:
        results = pylibdmtx.decode(gray, timeout=timeout_ms, max_count=1)
        if results:
            obj = results[0]
            data = obj.data.decode("utf-8", errors="replace")
            x, y_bot, w, h = obj.rect
            img_h = gray.shape[0]
            y_top = img_h - y_bot           # bottom-left → top-left origin
            pts = np.array([
                [x,     y_top],
                [x + w, y_top],
                [x + w, y_top + abs(h)],
                [x,     y_top + abs(h)],
            ], dtype=np.float32)
            return data, pts, "DATAMATRIX"
    except Exception:
        pass
    return None, None, None


def decode_qr(img: np.ndarray):
    """Try QR-only decoders (fast).  Returns (data, pts, type)."""
    data, pts, typ = try_cv_qr(img)
    if data:
        return data, pts, typ
    return try_pyzbar(img)


# ── Tier 0: QR on downscaled image ──────────────────────────────────────────

def _downscale(img: np.ndarray, max_w: int = DETECT_MAX_WIDTH):
    h, w = img.shape[:2]
    if w <= max_w:
        return img, 1.0
    scale = max_w / w
    return cv2.resize(img, (max_w, int(h * scale)), interpolation=cv2.INTER_AREA), scale


def tier0_qr_downscaled(img: np.ndarray):
    """
    Downscale → OpenCV QR + pyzbar.  ~5 ms.
    Returns (data, pts_in_original_coords, type, method_tag) or Nones.
    """
    small, scale = _downscale(img)
    data, pts, typ = decode_qr(small)
    if data and pts is not None:
        pts_orig = pts / scale if scale != 1.0 else pts
        return data, pts_orig, typ, "tier0_qr_downscaled"
    return None, None, None, None


# ── Tier 1: Overlapping quadrant tiles → pylibdmtx ──────────────────────────

def _make_tiles(h: int, w: int, overlap: float = TILE_OVERLAP):
    mid_y, mid_x = h // 2, w // 2
    ov_y, ov_x = int(mid_y * overlap), int(mid_x * overlap)
    yield (0,            mid_y + ov_y, 0,            mid_x + ov_x)
    yield (0,            mid_y + ov_y, mid_x - ov_x, w)
    yield (mid_y - ov_y, h,           0,            mid_x + ov_x)
    yield (mid_y - ov_y, h,           mid_x - ov_x, w)


def tier1_tiled_dmtx(gray: np.ndarray, is_over_budget):
    """
    Decode DataMatrix by splitting the image into 4 overlapping quadrants.
    Each tile is small enough for pylibdmtx to run in ~15 ms.

    Parameters
    ----------
    gray : np.ndarray   – grayscale full-res image
    is_over_budget : callable  – returns True when time budget is exhausted

    Returns (data, pts, type, method_tag) or Nones.
    """
    if not HAS_DMTX:
        return None, None, None, None

    h, w = gray.shape[:2]
    for y0, y1, x0, x1 in _make_tiles(h, w):
        if is_over_budget():
            break
        tile = gray[y0:y1, x0:x1]
        data, pts, typ = try_dmtx(tile, timeout_ms=DMTX_TILE_TIMEOUT)
        if data and pts is not None:
            pts[:, 0] += x0
            pts[:, 1] += y0
            return data, pts, typ, f"tier1_tile_{x0}_{y0}"
    return None, None, None, None
