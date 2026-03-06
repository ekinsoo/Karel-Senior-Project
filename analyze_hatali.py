"""
Hatali klasoru analiz scripti.
HTML defect loglarini parse eder, resimlerle eslestirir, rapor verir.
"""

import os
import re
import hashlib
from pathlib import Path
from collections import defaultdict

HATALI_DIR = r"hatali"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


def parse_html_file(html_path):
    """HTML dosyasini parse et, her satirdaki kayitlari cikar."""
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # DateTime range'i cikar
    date_range_match = re.search(r"DateTime:([^<]+)", content)
    date_range = date_range_match.group(1).strip() if date_range_match else "Bilinmiyor"

    # Her TR satirini bul ve icindeki TD/TH'leri parse et
    records = []
    # TR bloklarini bul
    tr_blocks = re.findall(r"<TR>(.*?)</TR>", content, re.DOTALL | re.IGNORECASE)

    for tr in tr_blocks:
        # Header satiri mi kontrol et (sadece TH iceriyorsa)
        cells = re.findall(r"<(?:TD|TH)[^>]*>(.*?)</(?:TD|TH)>", tr, re.DOTALL | re.IGNORECASE)
        if not cells or len(cells) < 10:
            continue

        # IMG SRC'yi ayrica cikar
        img_match = re.search(r'<IMG\s+SRC="([^"]+)"', tr, re.IGNORECASE)
        img_src = img_match.group(1).replace("\\", "/") if img_match else ""

        # Hucre iceriklerini temizle (HTML taglerini kaldir)
        clean_cells = []
        for cell in cells:
            # IMG tagli hucreleri atla, sadece text
            clean = re.sub(r"<[^>]+>", "", cell).strip()
            clean_cells.append(clean)

        # Sütun sırası: ModelName, DateTime, BoardSN, T/B, BoardNo, CompName, Type, InspResult, Judgment, ...
        if len(clean_cells) >= 9:
            record = {
                "model_name": clean_cells[0],
                "datetime": clean_cells[1],
                "board_sn": clean_cells[2],
                "top_bottom": clean_cells[3],
                "board_no": clean_cells[4],
                "comp_name": clean_cells[5],
                "comp_type": clean_cells[6],
                "inspection_result": clean_cells[7],
                "judgment": clean_cells[8],
                "img_src": img_src,
            }
            records.append(record)

    return records, date_range


def scan_image_files(hatali_dir):
    """Hatali klasorundeki tum resimleri tara."""
    images = {}  # {relative_path: absolute_path}
    base = Path(hatali_dir)

    for item in base.iterdir():
        if not item.is_dir():
            continue
        for img in item.iterdir():
            if img.suffix.lower() in IMAGE_EXTENSIONS:
                rel = f"{item.name}/{img.name}"
                images[rel] = str(img)

    return images


def main():
    base_path = Path(HATALI_DIR)

    if not base_path.exists():
        print(f"[HATA] Klasor bulunamadi: {HATALI_DIR}")
        return

    # ============================================================
    # 1. HTML dosyalarini bul ve parse et
    # ============================================================
    html_files = sorted([f for f in base_path.iterdir() if f.suffix.lower() in (".html", ".htm")])
    print("=" * 70)
    print("  HATALI KLASORU ANALIZ RAPORU")
    print("=" * 70)

    print(f"\n  HTML dosyalari: {len(html_files)}")

    all_html_records = {}  # {html_name: [records]}
    all_img_srcs = {}  # {html_name: set(img_src)}

    for html_file in html_files:
        records, date_range = parse_html_file(str(html_file))
        name = html_file.name
        all_html_records[name] = records
        all_img_srcs[name] = set(r["img_src"] for r in records if r["img_src"])
        print(f"    {name}")
        print(f"      Tarih araligi: {date_range}")
        print(f"      Kayit sayisi:  {len(records)}")

    # ============================================================
    # 2. HTML duplicate kontrolu
    # ============================================================
    print(f"\n{'=' * 70}")
    print("  KONTROL 1: HTML DUPLICATE KONTROLU")
    print("=" * 70)

    # MD5 hash kontrolu
    html_hashes = {}
    for html_file in html_files:
        with open(str(html_file), "rb") as f:
            h = hashlib.md5(f.read()).hexdigest()
        html_hashes[html_file.name] = h

    hash_groups = defaultdict(list)
    for name, h in html_hashes.items():
        hash_groups[h].append(name)

    has_exact_dup = False
    for h, names in hash_groups.items():
        if len(names) > 1:
            has_exact_dup = True
            print(f"\n  !! BIREBIR AYNI ICERIK:")
            for n in names:
                print(f"       - {n}")

    if not has_exact_dup:
        print(f"\n  [OK] Birebir ayni icerikli HTML dosyasi YOK.")

    # IMG referans cakismasi kontrolu
    print(f"\n  --- IMG Referans Karsilastirma ---")
    html_names = list(all_img_srcs.keys())
    for i in range(len(html_names)):
        for j in range(i + 1, len(html_names)):
            n1 = html_names[i]
            n2 = html_names[j]
            s1 = all_img_srcs[n1]
            s2 = all_img_srcs[n2]

            common = s1 & s2
            total_unique = len(s1 | s2)
            overlap_pct = (len(common) / total_unique * 100) if total_unique > 0 else 0

            status = ""
            if overlap_pct == 100:
                status = " !! TAMAMEN AYNI"
            elif overlap_pct > 50:
                status = " !! YUKSEK ORTUSME"

            print(f"\n  {n1[:40]}...")
            print(f"  vs")
            print(f"  {n2[:40]}...")
            print(f"    Ortak: {len(common)}/{total_unique} ({overlap_pct:.1f}%){status}")

    # ============================================================
    # 3. Resimleri tara
    # ============================================================
    print(f"\n{'=' * 70}")
    print("  KONTROL 2: RESIM - HTML ESLESTIRME")
    print("=" * 70)

    actual_images = scan_image_files(HATALI_DIR)
    print(f"\n  Klasorlerdeki toplam resim: {len(actual_images)}")

    # HTML'deki tum img referanslarini topla (IMG\ prefix'ini kaldir)
    all_html_img_paths = {}  # {normalized_path: record}
    for html_name, records in all_html_records.items():
        for rec in records:
            src = rec["img_src"]
            if not src:
                continue
            # "IMG/2025101723/20251017231856_U7_2.jpg" → "2025101723/20251017231856_U7_2.jpg"
            normalized = src.replace("IMG/", "").replace("IMG\\", "")
            all_html_img_paths[normalized] = {
                "html_file": html_name,
                "record": rec,
            }

    print(f"  HTML'lerdeki toplam IMG referansi: {len(all_html_img_paths)}")

    # Eslestirme
    matched = []
    orphan_images = []  # Klasorde var ama HTML'de yok
    missing_images = []  # HTML'de var ama klasorde yok

    for img_path in actual_images:
        if img_path in all_html_img_paths:
            matched.append((img_path, all_html_img_paths[img_path]))
        else:
            orphan_images.append(img_path)

    for html_path in all_html_img_paths:
        if html_path not in actual_images:
            missing_images.append((html_path, all_html_img_paths[html_path]))

    print(f"\n  [OK] Eslesen (klasorde + HTML'de): {len(matched)}")
    print(f"  [??] Orphan (klasorde var, HTML'de yok): {len(orphan_images)}")
    print(f"  [!!] Missing (HTML'de var, klasorde yok): {len(missing_images)}")

    if orphan_images:
        print(f"\n  --- ORPHAN RESIMLER (HTML'de yok) ---")
        for img in sorted(orphan_images):
            print(f"    - {img}")

    if missing_images:
        print(f"\n  --- MISSING RESIMLER (klasorde yok) ---")
        for img_path, info in sorted(missing_images, key=lambda x: x[0]):
            rec = info["record"]
            print(f"    - {img_path}")
            print(f"      HTML: {info['html_file']}")
            print(f"      Judgment: {rec['judgment']}")

    # ============================================================
    # 4. Hata tipi dagılımı
    # ============================================================
    print(f"\n{'=' * 70}")
    print("  HATA TIPI DAGILIMI (HTML Kayitlarindan)")
    print("=" * 70)

    judgment_counts = defaultdict(int)
    inspection_counts = defaultdict(int)
    comp_type_counts = defaultdict(int)

    for html_name, records in all_html_records.items():
        for rec in records:
            judgment_counts[rec["judgment"]] += 1
            inspection_counts[rec["inspection_result"]] += 1
            comp_type_counts[rec["comp_type"]] += 1

    print(f"\n  --- Judgment (Karar) ---")
    for jud, count in sorted(judgment_counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(40, count)
        print(f"    {jud:25s} {count:>4}  {bar}")

    print(f"\n  --- Inspection Result ---")
    for ir, count in sorted(inspection_counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(40, count)
        print(f"    {ir:25s} {count:>4}  {bar}")

    print(f"\n  --- Komponent Tipi ---")
    for ct, count in sorted(comp_type_counts.items(), key=lambda x: -x[1]):
        print(f"    {ct:25s} {count:>4}")

    # ============================================================
    # 5. Eslesen kayitlarin detayli listesi
    # ============================================================
    print(f"\n{'=' * 70}")
    print("  ESLESEN KAYITLARIN DETAYI")
    print("=" * 70)
    print(f"\n  {'Dosya Adi':<45} {'Comp':>8} {'Judgment':>20} {'Inspection':>20}")
    print(f"  {'-'*95}")

    for img_path, info in sorted(matched, key=lambda x: x[0]):
        rec = info["record"]
        fname = img_path.split("/")[-1] if "/" in img_path else img_path
        print(f"  {fname:<45} {rec['comp_name']:>8} {rec['judgment']:>20} {rec['inspection_result']:>20}")

    # ============================================================
    # OZET
    # ============================================================
    total_all = len(all_html_records)
    total_records = sum(len(v) for v in all_html_records.values())

    print(f"\n{'=' * 70}")
    print("  GENEL OZET")
    print("=" * 70)
    print(f"  HTML dosyalari:           {len(html_files)}")
    print(f"  HTML'deki toplam kayit:   {total_records}")
    print(f"  Unique IMG referansi:     {len(all_html_img_paths)}")
    print(f"  Klasordeki resim sayisi:  {len(actual_images)}")
    print(f"  Eslesen:                  {len(matched)}")
    print(f"  Orphan (HTML'de yok):     {len(orphan_images)}")
    print(f"  Missing (klasorde yok):   {len(missing_images)}")
    print(f"  Benzersiz hata tipi:      {len(judgment_counts)}")

    if has_exact_dup:
        print(f"\n  !! Duplicate HTML dosyasi VAR — birisini silebilirsiniz")
    else:
        print(f"\n  [OK] Duplicate HTML yok")

    if not orphan_images and not missing_images:
        print(f"  [OK] Tum resimler HTML kayitlariyla eslesiyor!")
    elif orphan_images:
        print(f"\n  !! {len(orphan_images)} resim HTML'de referans edilmiyor.")
        print(f"     Bu resimlerin labeli HTML'den alinaMAZ.")
        print(f"     Secenekler:")
        print(f"       a) Bu resimleri elle labellayabilirsiniz")
        print(f"       b) Resim uzerindeki kirmizi kareden OCR ile label okunabilir")
        print(f"       c) Bu resimleri dataset'ten cikarabilirsiniz")

    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
