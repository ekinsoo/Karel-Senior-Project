"""
pcb_center_layout - Layout-aware decoder for the new 2x5 PCB panel.

The current production board contains 10 panels arranged as 2 columns x 5 rows.
We now prefer the larger DataMatrix regions on the OUTER left/right edges because
they are easier to see than the center ones.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from qr.qr_fast import decode_qr, try_dmtx


BOARD_MASK_LOWER = (35, 25, 25)
BOARD_MASK_UPPER = (95, 255, 255)
ROW_SCAN_ORDER = (2, 1, 3, 0, 4)
DEFAULT_TIME_BUDGET_MS = 700.0
DEFAULT_DMTX_TIMEOUT_MS = 40
DECODE_WORK_MAX_WIDTH = 3840
ROI_CONFIG_PATH = Path(__file__).resolve().with_name("manual_roi_config.json")
DEFAULT_MULTI_TIME_BUDGET_MS = 2200.0


@dataclass(frozen=True)
class ROICandidate:
    name: str
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return max(0, self.x1 - self.x0)

    @property
    def height(self) -> int:
        return max(0, self.y1 - self.y0)


@dataclass
class LayoutDecodeResult:
    decoded: bool = False
    data: str | None = None
    code_type: str | None = None
    method: str = ""
    elapsed_ms: float = 0.0
    points: np.ndarray | None = field(default=None, repr=False)
    board_bbox: tuple[int, int, int, int] | None = None
    candidate_name: str | None = None

    def to_dict(self) -> dict:
        return {
            "decoded": self.decoded,
            "data": self.data,
            "code_type": self.code_type,
            "method": self.method,
            "elapsed_ms": self.elapsed_ms,
            "points": None if self.points is None else self.points.tolist(),
            "board_bbox": self.board_bbox,
            "candidate_name": self.candidate_name,
        }


@dataclass
class PanelCodeResult:
    panel_index: int | None
    row: int | None
    side: str | None
    data: str
    code_type: str
    method: str
    candidate_name: str
    points: np.ndarray = field(repr=False)

    def to_dict(self) -> dict:
        return {
            "panel_index": self.panel_index,
            "row": self.row,
            "side": self.side,
            "data": self.data,
            "code_type": self.code_type,
            "method": self.method,
            "candidate_name": self.candidate_name,
            "points": self.points.tolist(),
        }


@dataclass
class LayoutMultiDecodeResult:
    codes: list[PanelCodeResult] = field(default_factory=list)
    elapsed_ms: float = 0.0
    board_bbox: tuple[int, int, int, int] | None = None
    method: str = "edge_layout_multi"

    @property
    def decoded_count(self) -> int:
        return len(self.codes)

    def to_dict(self) -> dict:
        return {
            "decoded_count": self.decoded_count,
            "elapsed_ms": self.elapsed_ms,
            "board_bbox": self.board_bbox,
            "method": self.method,
            "codes": [c.to_dict() for c in self.codes],
        }


def _elapsed_ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def _resize_to_width(img: np.ndarray, max_width: int = 1600) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    if w <= max_width:
        return img, 1.0
    scale = max_width / float(w)
    resized = cv2.resize(
        img,
        (max_width, max(1, int(round(h * scale)))),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def detect_board_bbox(img: np.ndarray) -> tuple[int, int, int, int]:
    """
    Find the green PCB panel bounding box.

    Falls back to the full image if no dominant green contour is found.
    """
    small, scale = _resize_to_width(img, max_width=1600)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, BOARD_MASK_LOWER, BOARD_MASK_UPPER)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8), iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        h, w = img.shape[:2]
        return 0, 0, w, h

    contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(contour)

    inv = 1.0 / scale
    x = int(round(x * inv))
    y = int(round(y * inv))
    w = int(round(w * inv))
    h = int(round(h * inv))

    pad_x = int(w * 0.02)
    pad_y = int(h * 0.02)
    img_h, img_w = img.shape[:2]
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(img_w, x + w + pad_x)
    y1 = min(img_h, y + h + pad_y)
    return x0, y0, x1 - x0, y1 - y0


def load_center_roi_config(config_path: str | Path = ROI_CONFIG_PATH) -> dict | None:
    path = Path(config_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None

    roi = data.get("roi")
    if not isinstance(roi, dict):
        return None

    keys = ("x0", "y0", "x1", "y1")
    if not all(k in roi for k in keys):
        return None

    try:
        roi_vals = {k: float(roi[k]) for k in keys}
    except Exception:
        return None

    if not (0.0 <= roi_vals["x0"] < roi_vals["x1"] <= 1.0):
        return None
    if not (0.0 <= roi_vals["y0"] < roi_vals["y1"] <= 1.0):
        return None

    return {
        "name": str(data.get("name", "manual_center_roi")),
        "roi": roi_vals,
        "source_image": data.get("source_image"),
        "saved_at": data.get("saved_at"),
    }


def _build_manual_candidates(
    board_bbox: tuple[int, int, int, int],
    config: dict,
) -> list[ROICandidate]:
    bx, by, bw, bh = board_bbox
    roi = config["roi"]

    x0 = roi["x0"]
    y0 = roi["y0"]
    x1 = roi["x1"]
    y1 = roi["y1"]

    candidates: list[ROICandidate] = []
    variants = (
        ("manual", x0, y0, x1, y1),
        ("manual_pad", max(0.0, x0 - 0.015), max(0.0, y0 - 0.02), min(1.0, x1 + 0.015), min(1.0, y1 + 0.02)),
        ("manual_tight", min(max(0.0, x0 + 0.01), 1.0), min(max(0.0, y0 + 0.01), 1.0), max(min(1.0, x1 - 0.01), 0.0), max(min(1.0, y1 - 0.01), 0.0)),
    )

    for label, xf0, yf0, xf1, yf1 in variants:
        if xf1 <= xf0 or yf1 <= yf0:
            continue
        candidates.append(
            ROICandidate(
                name=f"{config['name']}_{label}",
                x0=bx + int(round(xf0 * bw)),
                y0=by + int(round(yf0 * bh)),
                x1=bx + int(round(xf1 * bw)),
                y1=by + int(round(yf1 * bh)),
            )
        )
    return candidates


def build_center_roi_candidates(
    img: np.ndarray,
    board_bbox: tuple[int, int, int, int] | None = None,
) -> tuple[tuple[int, int, int, int], list[ROICandidate]]:
    """
    Build ROI windows for the outer left/right DataMatrix locations.
    """
    if board_bbox is None:
        board_bbox = detect_board_bbox(img)

    manual_config = load_center_roi_config()
    if manual_config is not None:
        return board_bbox, _build_manual_candidates(board_bbox, manual_config)

    bx, by, bw, bh = board_bbox
    candidates: list[ROICandidate] = []

    # The layout is stable: 2 columns x 5 rows. We scan the larger outer-edge
    # codes first because they are physically larger and visually clearer.
    # These windows are intentionally generous so we do not clip the code.
    for row in ROW_SCAN_ORDER:
        row_top = row / 5.0
        y_variants = (
            (row_top + 0.40 / 5.0, row_top + 0.94 / 5.0),
            (row_top + 0.45 / 5.0, row_top + 0.98 / 5.0),
            (row_top + 0.48 / 5.0, row_top + 0.90 / 5.0),
        )

        x_variants = (
            ("left_outer_wide", (0.00, 0.18)),
            ("left_outer", (0.00, 0.15)),
            ("left_outer_tight", (0.01, 0.13)),
            ("right_outer_wide", (0.82, 1.00)),
            ("right_outer", (0.85, 1.00)),
            ("right_outer_tight", (0.87, 0.99)),
        )

        for y_idx, (y0f, y1f) in enumerate(y_variants, start=1):
            y0 = by + int(round(y0f * bh))
            y1 = by + int(round(y1f * bh))

            for label, (x0f, x1f) in x_variants:
                x0 = bx + int(round(x0f * bw))
                x1 = bx + int(round(x1f * bw))
                candidates.append(
                    ROICandidate(
                        name=f"row{row + 1}_{label}_v{y_idx}",
                        x0=x0,
                        y0=y0,
                        x1=x1,
                        y1=y1,
                    )
                )

    return board_bbox, candidates


def _roi_preprocess_variants(gray: np.ndarray) -> list[tuple[str, np.ndarray]]:
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe_img = clahe.apply(gray)
    clahe_sharp = cv2.addWeighted(clahe_img, 1.6, cv2.GaussianBlur(clahe_img, (3, 3), 0), -0.6, 0)
    blackhat = cv2.morphologyEx(clahe_img, cv2.MORPH_BLACKHAT, np.ones((11, 11), np.uint8))
    adaptive = cv2.adaptiveThreshold(
        clahe_sharp,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        4,
    )
    return [
        ("gray", gray),
        ("clahe", clahe_img),
        ("clahe_sharp", clahe_sharp),
        ("blackhat", blackhat),
        ("adaptive", adaptive),
    ]


def _candidate_scales(roi_h: int, roi_w: int) -> tuple[float, ...]:
    max_dim = max(roi_h, roi_w)
    if max_dim <= 0:
        return (1.0,)
    target = 900.0 / float(max_dim)
    base = min(3.5, max(1.0, target))
    if base < 1.25:
        return (1.0, 1.35)
    if base < 2.25:
        return (round(base, 2), round(min(base * 1.35, 3.2), 2))
    return (round(base, 2), round(min(base * 1.2, 4.0), 2))


def _scale_points(pts: np.ndarray, scale: float, x0: int, y0: int) -> np.ndarray:
    pts = pts.astype(np.float32).copy()
    if scale != 1.0:
        pts /= scale
    pts[:, 0] += x0
    pts[:, 1] += y0
    return pts


def _slot_from_candidate(name: str) -> tuple[int | None, str | None]:
    m = re.match(r"row(\d+)_(left|right)_", name)
    if not m:
        return None, None
    return int(m.group(1)), m.group(2)


def _panel_index(row: int, side: str) -> int:
    # Ordering rule: row-major, left then right -> 1..10
    return (row - 1) * 2 + (1 if side == "left" else 2)


def decode_edge_panel_codes(
    img: np.ndarray,
    *,
    time_budget_ms: float = DEFAULT_MULTI_TIME_BUDGET_MS,
    dmtx_timeout_ms: int = DEFAULT_DMTX_TIMEOUT_MS,
) -> LayoutMultiDecodeResult:
    """
    Decode as many edge DataMatrix codes as possible (up to 10 slots).
    """
    t0 = time.perf_counter()
    result = LayoutMultiDecodeResult()
    work_img, work_scale = _resize_to_width(img, max_width=DECODE_WORK_MAX_WIDTH)
    board_bbox, candidates = build_center_roi_candidates(work_img)
    result.board_bbox = (
        int(round(board_bbox[0] / work_scale)),
        int(round(board_bbox[1] / work_scale)),
        int(round(board_bbox[2] / work_scale)),
        int(round(board_bbox[3] / work_scale)),
    )

    decoded_by_slot: dict[tuple[int, str], PanelCodeResult] = {}

    for candidate in candidates:
        if _elapsed_ms(t0) > time_budget_ms:
            break

        row, side = _slot_from_candidate(candidate.name)
        slot_key = (row, side) if row is not None and side is not None else None
        if slot_key is not None and slot_key in decoded_by_slot:
            continue

        roi = work_img[candidate.y0:candidate.y1, candidate.x0:candidate.x1]
        if roi.size == 0:
            continue

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        scales = _candidate_scales(candidate.height, candidate.width)

        for filter_name, filtered in _roi_preprocess_variants(gray):
            if _elapsed_ms(t0) > time_budget_ms:
                break

            for scale in scales:
                if _elapsed_ms(t0) > time_budget_ms:
                    break

                test = filtered
                if scale != 1.0:
                    test = cv2.resize(
                        filtered,
                        None,
                        fx=scale,
                        fy=scale,
                        interpolation=cv2.INTER_CUBIC,
                    )

                if filter_name in {"gray", "clahe", "clahe_sharp"}:
                    test_bgr = cv2.cvtColor(test, cv2.COLOR_GRAY2BGR)
                    data, pts, code_type = decode_qr(test_bgr)
                    if data and pts is not None:
                        full_pts = _scale_points(pts, scale, candidate.x0, candidate.y0) / work_scale
                        code = PanelCodeResult(
                            panel_index=_panel_index(row, side) if row and side else None,
                            row=row,
                            side=side,
                            data=data,
                            code_type=code_type,
                            method=f"edge_layout_{candidate.name}_{filter_name}_x{scale:g}",
                            candidate_name=candidate.name,
                            points=full_pts,
                        )
                        if slot_key is not None:
                            decoded_by_slot[slot_key] = code
                        else:
                            result.codes.append(code)
                        break

                remaining_ms = time_budget_ms - _elapsed_ms(t0)
                if remaining_ms < 15:
                    break

                timeout_ms = max(15, min(dmtx_timeout_ms, int(remaining_ms)))
                data, pts, code_type = try_dmtx(test, timeout_ms=timeout_ms)
                if data and pts is not None:
                    full_pts = _scale_points(pts, scale, candidate.x0, candidate.y0) / work_scale
                    code = PanelCodeResult(
                        panel_index=_panel_index(row, side) if row and side else None,
                        row=row,
                        side=side,
                        data=data,
                        code_type=code_type,
                        method=f"edge_layout_{candidate.name}_{filter_name}_x{scale:g}",
                        candidate_name=candidate.name,
                        points=full_pts,
                    )
                    if slot_key is not None:
                        decoded_by_slot[slot_key] = code
                    else:
                        result.codes.append(code)
                    break

            if slot_key is not None and slot_key in decoded_by_slot:
                break

        if len(decoded_by_slot) >= 10:
            break

    if decoded_by_slot:
        ordered = sorted(
            decoded_by_slot.values(),
            key=lambda c: c.panel_index if c.panel_index is not None else 999,
        )
        result.codes = ordered + result.codes

    result.elapsed_ms = round(_elapsed_ms(t0), 2)
    return result


def decode_center_panel_code(
    img: np.ndarray,
    *,
    time_budget_ms: float = DEFAULT_TIME_BUDGET_MS,
    dmtx_timeout_ms: int = DEFAULT_DMTX_TIMEOUT_MS,
) -> LayoutDecodeResult:
    """
    Backward-compatible single-code helper (returns the first decoded code).
    """
    multi = decode_edge_panel_codes(
        img,
        time_budget_ms=max(time_budget_ms, 900.0),
        dmtx_timeout_ms=dmtx_timeout_ms,
    )
    result = LayoutDecodeResult()
    result.board_bbox = multi.board_bbox
    result.elapsed_ms = multi.elapsed_ms
    if not multi.codes:
        result.method = "edge_layout_none"
        return result

    first = multi.codes[0]
    result.decoded = True
    result.data = first.data
    result.code_type = first.code_type
    result.method = first.method
    result.points = first.points
    result.candidate_name = first.candidate_name
    return result


def draw_layout_debug(
    img: np.ndarray,
    board_bbox: tuple[int, int, int, int],
    candidates: list[ROICandidate],
    decoded_points: np.ndarray | list[np.ndarray] | None = None,
    highlight_candidate: str | list[str] | set[str] | None = None,
) -> np.ndarray:
    vis = img.copy()
    bx, by, bw, bh = board_bbox
    cv2.rectangle(vis, (bx, by), (bx + bw, by + bh), (0, 0, 255), 4)

    if isinstance(highlight_candidate, str):
        highlighted = {highlight_candidate}
    elif highlight_candidate is None:
        highlighted = set()
    else:
        highlighted = set(highlight_candidate)

    for candidate in candidates:
        color = (255, 180, 0)
        thickness = 2
        if candidate.name in highlighted:
            color = (0, 255, 255)
            thickness = 3
        cv2.rectangle(vis, (candidate.x0, candidate.y0), (candidate.x1, candidate.y1), color, thickness)

    if decoded_points is not None:
        if isinstance(decoded_points, list):
            all_points = decoded_points
        else:
            all_points = [decoded_points]
        for pts in all_points:
            pts_i = pts.astype(np.int32)
            cv2.polylines(vis, [pts_i], isClosed=True, color=(0, 255, 0), thickness=4)

    return vis
