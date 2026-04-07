import argparse
from pathlib import Path
import os
import sys

import cv2
import numpy as np

try:
    from qr.pcb_center_layout import (
        build_center_roi_candidates,
        decode_edge_panel_codes,
        draw_layout_debug,
    )
except ModuleNotFoundError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from qr.pcb_center_layout import (
        build_center_roi_candidates,
        decode_edge_panel_codes,
        draw_layout_debug,
    )


def _resize_keep_width(img, width: int):
    h, w = img.shape[:2]
    if width <= 0 or w <= width:
        return img
    scale = width / float(w)
    return cv2.resize(
        img,
        (width, max(1, int(round(h * scale)))),
        interpolation=cv2.INTER_AREA,
    )


def _save_filter_debug_set(img, candidate, base_path: Path):
    roi = img[candidate.y0:candidate.y1, candidate.x0:candidate.x1]
    if roi.size == 0:
        return

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    clahe_sharp = cv2.addWeighted(clahe, 1.6, cv2.GaussianBlur(clahe, (3, 3), 0), -0.6, 0)
    blackhat = cv2.morphologyEx(clahe, cv2.MORPH_BLACKHAT, np.ones((11, 11), np.uint8))
    adaptive = cv2.adaptiveThreshold(
        clahe_sharp,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        4,
    )

    cv2.imwrite(str(base_path.with_name(base_path.stem + "_roi.jpg")), roi)
    cv2.imwrite(str(base_path.with_name(base_path.stem + "_gray.jpg")), gray)
    cv2.imwrite(str(base_path.with_name(base_path.stem + "_clahe.jpg")), clahe)
    cv2.imwrite(str(base_path.with_name(base_path.stem + "_clahe_sharp.jpg")), clahe_sharp)
    cv2.imwrite(str(base_path.with_name(base_path.stem + "_blackhat.jpg")), blackhat)
    cv2.imwrite(str(base_path.with_name(base_path.stem + "_adaptive.jpg")), adaptive)


def main():
    parser = argparse.ArgumentParser(description="Test the new edge-layout DataMatrix decoder.")
    parser.add_argument("images", nargs="+", help="Path(s) to image(s)")
    parser.add_argument(
        "--simulate-width",
        type=int,
        action="append",
        default=[],
        help="Optionally test a resized copy (example: --simulate-width 3840)",
    )
    parser.add_argument(
        "--debug-dir",
        default="qr_debug_runs",
        help="Directory for debug overlays",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=5000.0,
        help="Decode time budget in milliseconds",
    )
    args = parser.parse_args()

    debug_dir = Path(args.debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)

    widths = [None] + args.simulate_width
    for image_path in args.images:
        src = cv2.imread(image_path)
        if src is None:
            print(f"❌ Image could not be loaded: {image_path}")
            continue

        for width in widths:
            img = src if width is None else _resize_keep_width(src, width)
            label = "orig" if width is None else f"w{width}"

            result = decode_edge_panel_codes(img, time_budget_ms=args.budget)
            board_bbox, candidates = build_center_roi_candidates(img, result.board_bbox)
            overlay = draw_layout_debug(
                img,
                board_bbox,
                candidates,
                decoded_points=[c.points for c in result.codes] if result.codes else None,
                highlight_candidate=[c.candidate_name for c in result.codes] if result.codes else None,
            )
            overlay_path = debug_dir / f"{Path(image_path).stem}_{label}_layout_debug.jpg"
            cv2.imwrite(str(overlay_path), overlay)

            chosen_name = result.codes[0].candidate_name if result.codes else None
            chosen = next((c for c in candidates if c.name == chosen_name), candidates[0] if candidates else None)
            if chosen is not None:
                _save_filter_debug_set(img, chosen, overlay_path)

            print(f"\n[{Path(image_path).name}] [{label}] shape={img.shape}")
            if result.codes:
                print(f"✅ DATAMATRIX / QR DETECTED ({result.decoded_count} code)")
                for c in result.codes:
                    idx = f"#{c.panel_index}" if c.panel_index is not None else "#?"
                    rs = f"row={c.row} side={c.side}" if c.row is not None and c.side is not None else "row=? side=?"
                    print(f"  {idx} {rs} data={c.data} type={c.code_type}")
            else:
                print("❌ No code decoded in edge layout ROIs")
                print(f"Method : {result.method}")
            print(f"Time   : {result.elapsed_ms} ms")
            print(f"Debug  : {overlay_path}")


if __name__ == "__main__":
    main()
