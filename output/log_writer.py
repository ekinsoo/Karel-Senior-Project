"""
log_writer – Append QR decode results to a plain-text log.

Format (pipe-delimited, one line per decode):
    timestamp | decoded_text | method | latency_ms | status

Example:
    2026-02-15 14:30:01 | 96110221104… | tier1_tile_0_0 | 78.2 | OK
    2026-02-15 14:30:03 | - | none | 200.0 | FAIL
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qr.qr_pipeline import QRResult


_LOG_DIR = "qr_test_images/results"
_LOG_FILE = os.path.join(_LOG_DIR, "qr_results.txt")
_lock = threading.Lock()


def append_result(result: "QRResult", log_path: str = _LOG_FILE) -> None:
    """Thread-safe append of a single QR result line."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = result.data if result.data else "-"
    method = result.method or "-"
    latency = f"{result.elapsed_ms:.1f}"
    status = "OK" if result.decoded else "FAIL"

    line = f"{ts} | {text} | {method} | {latency} | {status}\n"

    with _lock:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
