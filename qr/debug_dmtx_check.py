import cv2
import sys
from pathlib import Path

from qr_fast import HAS_DMTX, HAS_PYZBAR, try_dmtx, try_pyzbar, try_cv_qr

img_path = sys.argv[1] if len(sys.argv) > 1 else "qr_test_images/test_pcb.jpg"

img = cv2.imread(img_path)
if img is None:
    print("Image could not be loaded:", img_path)
    sys.exit(1)

print("Image:", img_path)
print("Shape:", img.shape)
print("HAS_DMTX  =", HAS_DMTX)
print("HAS_PYZBAR=", HAS_PYZBAR)

print("\n--- Full image tests ---")
data, pts, typ = try_cv_qr(img)
print("try_cv_qr  :", data, typ)

data, pts, typ = try_pyzbar(img)
print("try_pyzbar :", data, typ)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
data, pts, typ = try_dmtx(gray, timeout_ms=200)
print("try_dmtx   :", data, typ)

print("\n--- Cropped ROI test ---")
# Etiketin yaklaşık bölgesi: senin görseline göre
roi = img[250:620, 80:380]
gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

data, pts, typ = try_cv_qr(roi)
print("ROI try_cv_qr  :", data, typ)

data, pts, typ = try_pyzbar(roi)
print("ROI try_pyzbar :", data, typ)

data, pts, typ = try_dmtx(gray_roi, timeout_ms=200)
print("ROI try_dmtx   :", data, typ)

cv2.imwrite("debug_roi.jpg", roi)
print("\nSaved: debug_roi.jpg")