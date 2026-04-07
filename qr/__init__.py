"""
qr – Fast QR / DataMatrix decoding module for PCB images.

Usage:
    from qr import decode_image
    result = decode_image("path/to/image.jpg")
"""

from qr.qr_pipeline import decode_image, decode_frame  # noqa: F401
from qr.pcb_center_layout import decode_center_panel_code, decode_edge_panel_codes  # noqa: F401
