import argparse
import json
from datetime import datetime
from pathlib import Path

import cv2

try:
    from qr.pcb_center_layout import detect_board_bbox, ROI_CONFIG_PATH
except ModuleNotFoundError:
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from qr.pcb_center_layout import detect_board_bbox, ROI_CONFIG_PATH


def _clamp(val: float) -> float:
    return max(0.0, min(1.0, val))


def main():
    parser = argparse.ArgumentParser(description="Calibrate a manual QR/DataMatrix ROI.")
    parser.add_argument("image", help="Image path to calibrate from")
    parser.add_argument(
        "--output",
        default=str(ROI_CONFIG_PATH),
        help="Where to save the ROI config JSON",
    )
    args = parser.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        print(f"❌ Image could not be loaded: {args.image}")
        return 1

    bx, by, bw, bh = detect_board_bbox(img)
    board = img[by:by + bh, bx:bx + bw].copy()
    preview = board.copy()

    hint = (
        "Select ONE QR/DataMatrix ROI and press ENTER/SPACE. "
        "ESC cancels."
    )
    cv2.putText(
        preview,
        hint,
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    rect = cv2.selectROI("Select Center QR ROI", preview, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    x, y, w, h = [int(v) for v in rect]
    if w <= 0 or h <= 0:
        print("⚠️ Selection cancelled.")
        return 1

    roi = {
        "x0": _clamp(x / float(bw)),
        "y0": _clamp(y / float(bh)),
        "x1": _clamp((x + w) / float(bw)),
        "y1": _clamp((y + h) / float(bh)),
    }
    payload = {
        "name": "manual_center_roi",
        "source_image": str(Path(args.image).resolve()),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "board_bbox": {
            "x": bx,
            "y": by,
            "w": bw,
            "h": bh,
        },
        "roi": roi,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(payload, indent=2))

    vis = img.copy()
    cv2.rectangle(vis, (bx, by), (bx + bw, by + bh), (0, 0, 255), 4)
    ax0 = bx + x
    ay0 = by + y
    ax1 = ax0 + w
    ay1 = ay0 + h
    cv2.rectangle(vis, (ax0, ay0), (ax1, ay1), (0, 255, 255), 4)

    debug_path = output_path.with_suffix(".preview.jpg")
    cv2.imwrite(str(debug_path), vis)

    print("✅ Manual ROI saved")
    print(f"Config : {output_path}")
    print(f"Preview: {debug_path}")
    print(f"ROI    : {roi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
