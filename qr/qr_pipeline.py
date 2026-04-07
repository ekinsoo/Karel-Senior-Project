"""
qr_pipeline – Orchestrates fast → fallback decoding with a time budget.

Public API:
    decode_image(path)   – load from disk, decode, optionally save debug image.
    decode_frame(img)    – decode an already-loaded BGR numpy array.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Optional

import cv2
import numpy as np

try:
    from qr.qr_fast import (
        tier0_qr_downscaled,
        tier1_tiled_dmtx,
        _gray,
    )
    from qr.qr_fallback import (
        tier2_contour_rois,
        tier3_filtered_roi,
    )
except ModuleNotFoundError:
    # Running as a direct script (python qr/qr_pipeline.py) –
    # the parent dir isn't on sys.path, so use relative imports.
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from qr.qr_fast import (
        tier0_qr_downscaled,
        tier1_tiled_dmtx,
        _gray,
    )
    from qr.qr_fallback import (
        tier2_contour_rois,
        tier3_filtered_roi,
    )


# ── Configuration ────────────────────────────────────────────────────────────
DEFAULT_TIME_BUDGET_MS = 200


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class QRResult:
    decoded: bool = False
    data: Optional[str] = None
    code_type: Optional[str] = None
    method: str = ""
    elapsed_ms: float = 0.0
    points: Optional[np.ndarray] = field(default=None, repr=False)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["points"] is not None:
            d["points"] = d["points"].tolist()
        return d


# ── Helpers ──────────────────────────────────────────────────────────────────

def _elapsed_ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def _make_budget_checker(t0: float, budget_ms: float):
    """Return a zero-arg callable that returns True when the budget is spent."""
    def _check() -> bool:
        return _elapsed_ms(t0) > budget_ms
    return _check


# ── Core pipeline ────────────────────────────────────────────────────────────

def decode_frame(
    img: np.ndarray,
    *,
    time_budget_ms: float = DEFAULT_TIME_BUDGET_MS,
) -> QRResult:
    """
    Decode a QR / DataMatrix code from a BGR frame.

    Tiers (executed in order, first success wins):
        0  QR on downscaled image               ~5 ms
        1  Quadrant tiles → pylibdmtx           ~15 ms/tile
        2  Contour-based ROI → pylibdmtx        ~70 ms
        3  Filtered pseudo-ROI → all decoders   remaining budget
    """
    t0 = time.perf_counter()
    over = _make_budget_checker(t0, time_budget_ms)
    result = QRResult()

    gray = _gray(img)

    # ── Tier 0 ────────────────────────────────────────────────────────────
    data, pts, typ, method = tier0_qr_downscaled(img)
    if data:
        return _finish(result, data, pts, typ, method, t0)

    # ── Tier 1 ────────────────────────────────────────────────────────────
    if not over():
        data, pts, typ, method = tier1_tiled_dmtx(gray, over)
        if data:
            return _finish(result, data, pts, typ, method, t0)

    # ── Tier 2 ────────────────────────────────────────────────────────────
    if not over():
        data, pts, typ, method = tier2_contour_rois(gray, over)
        if data:
            return _finish(result, data, pts, typ, method, t0)

    # ── Tier 3 ────────────────────────────────────────────────────────────
    if not over():
        data, pts, typ, method = tier3_filtered_roi(gray, over)
        if data:
            return _finish(result, data, pts, typ, method, t0)

    # ── Nothing worked ────────────────────────────────────────────────────
    result.method = "none"
    result.elapsed_ms = round(_elapsed_ms(t0), 2)
    return result


def decode_image(
    image_path: str,
    *,
    time_budget_ms: float = DEFAULT_TIME_BUDGET_MS,
    debug_path: str | None = None,
) -> QRResult:
    """Load an image from disk, decode, optionally write a debug overlay."""
    img = cv2.imread(image_path)
    if img is None:
        return QRResult(error=f"Cannot read {image_path}")

    result = decode_frame(img, time_budget_ms=time_budget_ms)

    if debug_path and result.points is not None:
        _save_debug(img, result, debug_path)

    return result


# ── Internals ────────────────────────────────────────────────────────────────

def _finish(result: QRResult, data, pts, typ, method, t0) -> QRResult:
    result.decoded = True
    result.data = data
    result.code_type = typ
    result.method = method
    result.points = pts
    result.elapsed_ms = round(_elapsed_ms(t0), 2)
    return result


def _save_debug(img: np.ndarray, result: QRResult, path: str):
    vis = img.copy()
    pts = result.points.astype(np.int32)
    cv2.polylines(vis, [pts], isClosed=True, color=(0, 0, 255), thickness=3)
    if result.data:
        org = (int(pts[:, 0].min()), int(pts[:, 1].min()) - 10)
        cv2.putText(vis, result.data, org,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imwrite(path, vis)


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    INPUT = "qr_test_images/test_pcb.jpg"
    DEBUG = "debug_qr.png"

    res = decode_image(INPUT, debug_path=DEBUG)

    if res.decoded:
        print(f"  DECODED in {res.elapsed_ms} ms")
        print(f"  Type  : {res.code_type}")
        print(f"  Method: {res.method}")
        print(f"  Data  : {res.data}")
        print(f"  Debug : {DEBUG}")
    else:
        print(f"  NOT decoded after {res.elapsed_ms} ms")
    if res.error:
        print(f"  Error : {res.error}")
