"""
PCB Komponent Metadata Oluşturucu

Kullanım:
  python generate_metadata.py

raw_data/ klasöründeki tüm fotoğrafları tarar,
dosya adlarından metadata çıkarır ve metadata.csv oluşturur.
"""

import os
import csv
import re
from pathlib import Path
from datetime import datetime


# ============================================================
# Konfigürasyon
# ============================================================
RAW_DATA_DIR = r"raw_data"
OUTPUT_CSV = r"metadata.csv"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

# Komponent tipi eşleştirme (prefix → açıklama)
COMP_TYPE_MAP = {
    "R": "Resistor",
    "C": "Capacitor",
    "X": "Crystal/Connector",
    "U": "IC",
    "L": "Inductor",
    "D": "Diode",
    "Q": "Transistor",
    "J": "Connector",
    "F": "Fuse",
    "T": "Transformer",
    "SW": "Switch",
    "LED": "LED",
    "TP": "Test Point",
    "FB": "Ferrite Bead",
    "Y": "Crystal",
    "K": "Relay",
    "P": "Plug",
    "S": "Switch",
}

# Özel / exceptional dosya adları (flag olarak işaretlenecek)
SPECIAL_KEYWORDS = [
    "DIKKAT", "KAYMA", "TEST", "TEMP", "DELETE", "SKIP", "IGNORE", "HATA"
]


def parse_filename(filename: str) -> dict:
    """
    Dosya adını parse et.

    Örnekler:
      20260225094250_X1_2.jpg     → ts=20260225094250, comp=X1,  idx=2
      20260225094250_U12_2.jpg    → ts=20260225094250, comp=U12, idx=2
      20260225094250_R79_1.jpg    → ts=20260225094250, comp=R79, idx=1
      20260225171651_DIKKATKAYMA_1.jpg → özel durum, flag=True
    """
    stem = Path(filename).stem

    # Ana pattern: {14 haneli timestamp}_{komponent}_{index}
    # Komponent: harf(ler) + sayı(lar)  örn: X1, U12, R79, LED1, SW2
    # Index: son _'den sonraki sayı
    match = re.match(r'^(\d{14})_(.+)_(\d+)$', stem)

    if not match:
        # Index yok, sadece timestamp_isim
        match2 = re.match(r'^(\d{14})_(.+)$', stem)
        if match2:
            ts_raw = match2.group(1)
            component = match2.group(2)
            index = "0"
        else:
            # Hiçbir pattern uymadı
            return {
                "timestamp_raw": "",
                "timestamp": "",
                "component": stem,
                "comp_prefix": "",
                "comp_type": "Unknown",
                "comp_index": "0",
                "is_special": True,
                "special_note": "parse_failed"
            }
    else:
        ts_raw = match.group(1)
        component = match.group(2)
        index = match.group(3)

    # Özel durum kontrolü (DIKKATKAYMA vb.)
    is_special = False
    special_note = ""
    comp_upper = component.upper()
    for keyword in SPECIAL_KEYWORDS:
        if keyword in comp_upper:
            is_special = True
            special_note = component
            break

    # Timestamp formatla
    try:
        dt = datetime.strptime(ts_raw, "%Y%m%d%H%M%S")
        ts_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        ts_formatted = ts_raw

    # Komponent prefix'ini çıkar
    # Önce uzun prefix'leri dene: LED, SW, FB, TP
    # Sonra tek harf: R, C, U, X, D, L, Q, J, F, T
    comp_prefix = ""
    comp_type = "Unknown"

    if not is_special:
        # Uzundan kısaya prefix dene
        for key in sorted(COMP_TYPE_MAP.keys(), key=len, reverse=True):
            if component.upper().startswith(key):
                comp_prefix = key
                comp_type = COMP_TYPE_MAP[key]
                break

        # Eğer hala bulamadıysak, ilk harfi al
        if not comp_prefix:
            prefix_match = re.match(r'^([A-Za-z]+)', component)
            if prefix_match:
                comp_prefix = prefix_match.group(1).upper()
                comp_type = COMP_TYPE_MAP.get(comp_prefix, "Unknown")

    return {
        "timestamp_raw": ts_raw,
        "timestamp": ts_formatted,
        "component": component,
        "comp_prefix": comp_prefix,
        "comp_type": comp_type,
        "comp_index": index,
        "is_special": is_special,
        "special_note": special_note,
    }


def scan_and_generate(raw_dir: str, output_csv: str):
    """Tüm fotoğrafları tara ve metadata CSV oluştur."""

    raw_path = Path(raw_dir)

    if not raw_path.exists():
        print(f"\n[HATA] Klasor bulunamadi: {raw_dir}")
        print(f"\nYapmaniz gereken:")
        print(f"  1. '{raw_dir}' klasorunu olusturun")
        print(f"  2. Fotograf klasorlerinizi (2026022509/ vb.) icine koyun")
        print(f"  3. Bu scripti tekrar calistirin")
        return

    # Tüm fotoğrafları bul
    all_images = []
    for img_path in sorted(raw_path.rglob("*")):
        if img_path.suffix.lower() in IMAGE_EXTENSIONS:
            rel_path = img_path.relative_to(raw_path)
            batch = str(rel_path.parent) if str(rel_path.parent) != "." else "root"
            all_images.append((str(rel_path), img_path.name, batch))

    if not all_images:
        print(f"\n[HATA] Hic fotograf bulunamadi: {raw_dir}/")
        print(f"Desteklenen formatlar: {IMAGE_EXTENSIONS}")
        return

    # Parse et
    rows = []
    comp_counter = {}
    type_counter = {}
    batch_counter = {}
    special_count = 0

    for rel_path, filename, batch_folder in all_images:
        parsed = parse_filename(filename)

        comp_name = parsed["component"]
        comp_type = parsed["comp_type"]

        if parsed["is_special"]:
            special_count += 1

        comp_counter[comp_name] = comp_counter.get(comp_name, 0) + 1
        type_counter[comp_type] = type_counter.get(comp_type, 0) + 1
        batch_counter[batch_folder] = batch_counter.get(batch_folder, 0) + 1

        rows.append({
            "filepath": rel_path.replace("\\", "/"),
            "filename": filename,
            "component": comp_name,
            "comp_prefix": parsed["comp_prefix"],
            "comp_type": comp_type,
            "comp_index": parsed["comp_index"],
            "timestamp": parsed["timestamp"],
            "batch": batch_folder,
            "is_special": parsed["is_special"],
            "special_note": parsed["special_note"],
            "label": "ok",
        })

    # CSV yaz
    fieldnames = [
        "filepath", "filename", "component", "comp_prefix",
        "comp_type", "comp_index", "timestamp", "batch",
        "is_special", "special_note", "label"
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # ============================================================
    # Rapor
    # ============================================================
    print()
    print("=" * 60)
    print("  METADATA RAPORU")
    print("=" * 60)

    print(f"""
  Toplam fotograf:     {len(rows)}
  Ozel durumlar:       {special_count} (DIKKAT, KAYMA vb.)
  Normal fotograf:     {len(rows) - special_count}
  CSV dosyasi:         {output_csv}
""")

    # Batch bazlı
    print(f"  --- Batch / Klasor ({len(batch_counter)} adet) ---")
    for batch, count in sorted(batch_counter.items()):
        print(f"    {batch:<30} {count:>6} foto")

    # Komponent tipi bazlı
    print(f"\n  --- Komponent Tipi ({len(type_counter)} tip) ---")
    for comp_type, count in sorted(type_counter.items(), key=lambda x: -x[1]):
        bar = "█" * min(50, count // max(1, len(rows) // 50))
        print(f"    {comp_type:<20} {count:>6}  {bar}")

    # Benzersiz komponentler
    print(f"\n  --- Benzersiz Komponentler ({len(comp_counter)} adet) ---")
    for comp, count in sorted(comp_counter.items(), key=lambda x: -x[1])[:25]:
        print(f"    {comp:<15} {count:>6} foto")
    if len(comp_counter) > 25:
        print(f"    ... ve {len(comp_counter) - 25} komponent daha")

    # Özel durumlar
    if special_count > 0:
        print(f"\n  --- Ozel Durumlar ({special_count} adet) ---")
        specials = [r for r in rows if r["is_special"]]
        for s in specials[:10]:
            print(f"    {s['filename']:<45} note: {s['special_note']}")
        if special_count > 10:
            print(f"    ... ve {special_count - 10} tane daha")

    print(f"""
{"=" * 60}
  SONRAKI ADIMLAR
{"=" * 60}

  1. {output_csv} dosyasini EXCEL ile acin
  
  2. Hatali fotograflarin 'label' sutununu degistirin:
     ok  →  solder_bridge
     ok  →  missing_component
     ok  →  crack
     ok  →  tombstone
     ok  →  vb.
  
  3. 'is_special' = True olanlara karar verin:
     Kullanilacaksa label verin, kullanilmayacaksa satin silin
  
  4. CSV'yi kaydedin

  NOT: Sadece hatali olanlari degistirin.
       Hatasizlari 'ok' olarak birakin.
       Emin olmadiklarinizi 'unknown' yapin.
""")

    return rows
    


if __name__ == "__main__":
    scan_and_generate(RAW_DATA_DIR, OUTPUT_CSV)