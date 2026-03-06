"""
Hatali Data Pipeline
====================
1. HTML defect loglarindan label cikarir
2. hatali_metadata.csv olusturur (69 resim + label)
3. Offline augmentation yapar → hatali_aug/ klasorune kaydeder
4. metadata.csv (hatasiz) + hatali_metadata.csv + augmented → combined_metadata.csv
5. Data leakage-siz train/val/test split ekler

Kullanim:
  python build_dataset.py
"""

import os
import re
import csv
import cv2
import random
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============================================================
# KONFIGÜRASYON
# ============================================================
HATALI_DIR = r"hatali"
RAW_DATA_DIR = r"raw_data"
HATALI_AUG_DIR = r"hatali_aug"
OK_METADATA = r"metadata.csv"
HATALI_METADATA = r"hatali_metadata.csv"
COMBINED_METADATA = r"combined_metadata.csv"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

# Augmentation: her hatali resimden kac kopya uretilecek
AUGMENTATION_FACTOR = 8

# Train/Val/Test split oranlari
TRAIN_RATIO = 0.75
VAL_RATIO = 0.15
TEST_RATIO = 0.10

# Reproducibility
RANDOM_SEED = 42

# Komponent tipi eslestirme (generate_metadata.py ile ayni)
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
    "Z": "Zener Diode",
}

# ============================================================
# Judgment → Normalize edilmis label eslestirme
# ============================================================
# HTML'deki Turkce/encoding bozuk Judgment degerlerini temiz label'a donustur
JUDGMENT_LABEL_MAP = {
    # Gercek hata tipleri
    "KISA DEVRE": "kisa_devre",
    "EGRILIK": "egrilik",
    "MEZAR TASI": "mezar_tasi",
    "LEHIM TOPU": "lehim_topu",
    "KALKIK BACAK": "kalkik_bacak",
    "KIRLI HASARLI": "kirli_hasarli",
    "EKSIK MALZEME": "eksik_malzeme",
    "EKSK MALZEME": "eksik_malzeme",  # encoding bozuk versiyon

    # Aksiyon tipleri — bunlar icin Inspection Result'a bakacagiz
    "ONARIM YAPILDI": None,  # None = Inspection Result'tan al

    # Kod bazli (00021 gibi) — Inspection Result'tan al
    "00021": None,

    # Header satiri (parse artifact)
    "Judgment": None,
}

# Inspection Result → label eslestirme (Judgment None olunca kullanilir)
INSPECTION_LABEL_MAP = {
    "LEHIM": "lehim_hatasi",
    "LEHM": "lehim_hatasi",        # encoding bozuk
    "LEH\x00M": "lehim_hatasi",    # null char
    "PRESENCE": "presence_hatasi",
    "FAZLA MALZEME": "fazla_malzeme",
    "ATIK MALZEME": "atik_malzeme",
    "SOGUK LEHIM": "soguk_lehim",
    "SOGUK LEHM": "soguk_lehim",   # encoding bozuk
    "MISSING PART": "eksik_malzeme",
    "SOLDER JOINT": "lehim_hatasi",
    "SOLDER BRIDGE": "lehim_koprusu",
    "LIFTED LEAD": "kalkik_bacak",
    "Inspection Result": None,     # header satiri
}


def normalize_text(text):
    """Encoding bozukluklarini temizle."""
    if not text:
        return ""
    # Null karakterleri kaldir
    text = text.replace("\x00", "").replace("\ufffd", "")
    # Coklu bosluklari teke indir
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_defect_label(judgment, inspection_result):
    """
    Judgment ve Inspection Result'tan defect label'i belirle.
    
    Oncelik: Judgment → eger Judgment belirsizse → Inspection Result
    """
    judgment = normalize_text(judgment)
    inspection_result = normalize_text(inspection_result)

    # Oncelik 1: Judgment'tan label al
    for key, label in JUDGMENT_LABEL_MAP.items():
        if key.upper() in judgment.upper():
            if label is not None:
                return label
            break  # None demek: Inspection Result'a bak

    # Oncelik 2: Inspection Result'tan label al
    for key, label in INSPECTION_LABEL_MAP.items():
        if key.upper() in inspection_result.upper():
            if label is not None:
                return label
            break

    # Oncelik 3: Judgment bos degilse onu kullan
    if judgment and judgment != "Judgment":
        # Bilinmeyen ama bos olmayan judgment
        clean = re.sub(r"[^a-zA-Z0-9]", "_", judgment.lower()).strip("_")
        return clean if clean else "defect_unknown"

    return "defect_unknown"


def parse_filename(filename):
    """Dosya adindan component bilgisi cikar (generate_metadata.py ile ayni mantik)."""
    stem = Path(filename).stem

    # {14 haneli timestamp}_{komponent}_{index}
    match = re.match(r"^(\d{14})_(.+)_(\d+)$", stem)
    if not match:
        match2 = re.match(r"^(\d{14})_(.+)$", stem)
        if match2:
            ts_raw = match2.group(1)
            component = match2.group(2)
            index = "0"
        else:
            return {"timestamp_raw": "", "timestamp": "", "component": stem,
                    "comp_prefix": "", "comp_type": "Unknown", "comp_index": "0",
                    "is_special": True, "special_note": stem}
    else:
        ts_raw = match.group(1)
        component = match.group(2)
        index = match.group(3)

    # Timestamp formatla
    try:
        dt = datetime.strptime(ts_raw, "%Y%m%d%H%M%S")
        ts_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        ts_formatted = ts_raw

    # Ozel durum kontrolu
    special_keywords = ["DIKKAT", "KAYMA", "TEST", "TEMP", "KISA DEVRE"]
    is_special = any(kw in component.upper() for kw in special_keywords)

    # Component prefix
    comp_prefix = ""
    comp_type = "Unknown"
    if not is_special:
        for key in sorted(COMP_TYPE_MAP.keys(), key=len, reverse=True):
            if component.upper().startswith(key):
                comp_prefix = key
                comp_type = COMP_TYPE_MAP[key]
                break
        if not comp_prefix:
            pfx = re.match(r"^([A-Za-z]+)", component)
            if pfx:
                comp_prefix = pfx.group(1).upper()

    return {
        "timestamp_raw": ts_raw,
        "timestamp": ts_formatted,
        "component": component,
        "comp_prefix": comp_prefix,
        "comp_type": comp_type,
        "comp_index": index,
        "is_special": is_special,
        "special_note": component if is_special else "",
    }


# ============================================================
# BOLUM 1: HTML PARSE → HATALI METADATA
# ============================================================
def parse_html_files(hatali_dir):
    """Tum HTML dosyalarini parse et, resim-label eslestirmesi yap."""
    base = Path(hatali_dir)
    html_files = sorted(f for f in base.iterdir() if f.suffix.lower() in (".html", ".htm"))

    img_label_map = {}  # {normalized_img_path: {label, judgment, inspection, ...}}

    print(f"\n[ADIM 1/5] HTML Defect Loglari Parse Ediliyor...")
    print(f"  HTML dosyalari: {len(html_files)}")

    for html_file in html_files:
        with open(str(html_file), "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        tr_blocks = re.findall(r"<TR>(.*?)</TR>", content, re.DOTALL | re.IGNORECASE)

        for tr in tr_blocks:
            cells = re.findall(
                r"<(?:TD|TH)[^>]*>(.*?)</(?:TD|TH)>", tr, re.DOTALL | re.IGNORECASE
            )
            if not cells or len(cells) < 10:
                continue

            img_match = re.search(r'<IMG\s+SRC="([^"]+)"', tr, re.IGNORECASE)
            if not img_match:
                continue

            img_src = img_match.group(1).replace("\\", "/")
            # "IMG/2025101723/file.jpg" → "2025101723/file.jpg"
            normalized = re.sub(r"^IMG/", "", img_src)

            clean_cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]

            # Sütunlar: 0=ModelName, 1=DateTime, 2=BoardSN, 3=T/B, 4=BoardNo,
            #           5=CompName, 6=Type, 7=InspResult, 8=Judgment, ...
            judgment = normalize_text(clean_cells[8]) if len(clean_cells) > 8 else ""
            inspection = normalize_text(clean_cells[7]) if len(clean_cells) > 7 else ""
            comp_name_html = normalize_text(clean_cells[5]) if len(clean_cells) > 5 else ""
            comp_type_html = normalize_text(clean_cells[6]) if len(clean_cells) > 6 else ""
            board_sn = normalize_text(clean_cells[2]) if len(clean_cells) > 2 else ""
            dt_str = normalize_text(clean_cells[1]) if len(clean_cells) > 1 else ""

            label = get_defect_label(judgment, inspection)

            # Duplicate kontrolu: ayni resim birden fazla HTML'de olabilir
            if normalized not in img_label_map:
                img_label_map[normalized] = {
                    "label": label,
                    "judgment_raw": judgment,
                    "inspection_raw": inspection,
                    "comp_name_html": comp_name_html,
                    "comp_type_html": comp_type_html,
                    "board_sn": board_sn,
                    "datetime_html": dt_str,
                    "html_source": html_file.name,
                }

    print(f"  Parse edilen kayit: {len(img_label_map)}")
    return img_label_map


def build_hatali_metadata(hatali_dir, img_label_map):
    """Hatali klasorunun metadata'sini olustur."""
    print(f"\n[ADIM 2/5] Hatali Metadata Olusturuluyor...")

    base = Path(hatali_dir)
    rows = []

    for folder in sorted(base.iterdir()):
        if not folder.is_dir():
            continue
        for img_file in sorted(folder.iterdir()):
            if img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            rel_path = f"{folder.name}/{img_file.name}"
            parsed = parse_filename(img_file.name)

            # HTML'den label al
            html_info = img_label_map.get(rel_path, {})
            label = html_info.get("label", "defect_unknown")
            judgment_raw = html_info.get("judgment_raw", "")
            inspection_raw = html_info.get("inspection_raw", "")

            rows.append({
                "filepath": f"hatali/{rel_path}",
                "filename": img_file.name,
                "component": parsed["component"],
                "comp_prefix": parsed["comp_prefix"],
                "comp_type": parsed["comp_type"],
                "comp_index": parsed["comp_index"],
                "timestamp": parsed["timestamp"],
                "batch": folder.name,
                "is_special": parsed["is_special"],
                "special_note": parsed["special_note"],
                "label": label,
                "source": "html",
                "augmented": False,
                "aug_parent": "",
                "judgment_raw": judgment_raw,
                "inspection_raw": inspection_raw,
            })

    # CSV yaz
    fieldnames = [
        "filepath", "filename", "component", "comp_prefix", "comp_type",
        "comp_index", "timestamp", "batch", "is_special", "special_note",
        "label", "source", "augmented", "aug_parent",
        "judgment_raw", "inspection_raw",
    ]

    with open(HATALI_METADATA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Rapor
    label_counts = defaultdict(int)
    for r in rows:
        label_counts[r["label"]] += 1

    print(f"  Toplam hatali resim: {len(rows)}")
    print(f"  Label dagilimi:")
    for lbl, cnt in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"    {lbl:<25} {cnt:>4}")
    print(f"  Kaydedildi: {HATALI_METADATA}")

    return rows


# ============================================================
# BOLUM 2: OFFLINE AUGMENTATION
# ============================================================
def augment_image(image):
    """Tek bir augmented kopya uret. Her cagirildigida farkli sonuc."""
    img = image.copy()
    h, w = img.shape[:2]

    # 1. Dondurme (0, 90, 180, 270)
    if random.random() > 0.3:
        angle = random.choice([90, 180, 270])
        if angle == 90:
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            img = cv2.rotate(img, cv2.ROTATE_180)
        else:
            img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

    # 2. Yatay / dikey flip
    if random.random() > 0.5:
        img = cv2.flip(img, 1)
    if random.random() > 0.5:
        img = cv2.flip(img, 0)

    # 3. Parlaklik / kontrast
    if random.random() > 0.3:
        alpha = random.uniform(0.75, 1.25)
        beta = random.randint(-30, 30)
        img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    # 4. Gaussian blur
    if random.random() > 0.7:
        ksize = random.choice([3, 5])
        img = cv2.GaussianBlur(img, (ksize, ksize), 0)

    # 5. Gaussian noise
    if random.random() > 0.7:
        noise = np.random.normal(0, 8, img.shape).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # 6. Random crop + resize (orijinal boyuta geri)
    if random.random() > 0.4:
        curr_h, curr_w = img.shape[:2]
        crop_pct = random.uniform(0.85, 0.95)
        new_h = int(curr_h * crop_pct)
        new_w = int(curr_w * crop_pct)
        y_off = random.randint(0, curr_h - new_h)
        x_off = random.randint(0, curr_w - new_w)
        img = img[y_off:y_off + new_h, x_off:x_off + new_w]
        img = cv2.resize(img, (curr_w, curr_h))

    # 7. Hafif renk shift (Hue)
    if random.random() > 0.6:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.int16)
        hsv[:, :, 0] = (hsv[:, :, 0] + random.randint(-5, 5)) % 180
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] + random.randint(-15, 15), 0, 255)
        img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    return img


def run_augmentation(hatali_rows):
    """Hatali resimlerin augmented kopyalarini olustur."""
    print(f"\n[ADIM 3/5] Offline Augmentation Yapiliyor...")
    print(f"  Faktor: {AUGMENTATION_FACTOR}x")
    print(f"  Beklenen cikti: {len(hatali_rows)} x {AUGMENTATION_FACTOR} = {len(hatali_rows) * AUGMENTATION_FACTOR}")

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    os.makedirs(HATALI_AUG_DIR, exist_ok=True)
    aug_rows = []
    fail_count = 0

    for row in hatali_rows:
        # Orijinal resmi oku
        img_path = row["filepath"]
        img = cv2.imread(img_path)
        if img is None:
            print(f"  [UYARI] Okunamiyor: {img_path}")
            fail_count += 1
            continue

        stem = Path(row["filename"]).stem

        for i in range(AUGMENTATION_FACTOR):
            aug_img = augment_image(img)

            aug_filename = f"{stem}_aug{i:02d}.jpg"
            aug_path = os.path.join(HATALI_AUG_DIR, aug_filename)
            cv2.imwrite(aug_path, aug_img)

            aug_row = row.copy()
            aug_row["filepath"] = aug_path
            aug_row["filename"] = aug_filename
            aug_row["source"] = "augmentation"
            aug_row["augmented"] = True
            aug_row["aug_parent"] = row["filepath"]
            aug_rows.append(aug_row)

    print(f"  Uretilen augmented resim: {len(aug_rows)}")
    if fail_count:
        print(f"  Okunamayan resim: {fail_count}")
    print(f"  Kaydedildi: {HATALI_AUG_DIR}/")

    return aug_rows


# ============================================================
# BOLUM 3: METADATA BIRLESTIRME + SPLIT
# ============================================================
def assign_splits(combined_rows):
    """
    Data leakage-siz train/val/test split.
    
    Kurallar:
    1. Ayni orijinal resmin augmented kopyalari AYNI split'te olmali
    2. Ayni fiziksel komponent (ayni comp_name + ayni batch grubu) mumkunse ayni split'te
    3. Hatasiz ve hatali verilerin orani her split'te benzer olmali
    """
    random.seed(RANDOM_SEED)

    # Gruplama: "component_group" bazinda split yap
    # Her orijinal hatali resim bir grup. Augmented'lar parent'in grubunda.
    # Her ok resim kendi grubu.

    # Hatali gruplari: parent filepath bazli
    defect_groups = defaultdict(list)  # {parent_path: [row_indices]}
    ok_indices = []

    for i, row in enumerate(combined_rows):
        if row["label"] == "ok":
            ok_indices.append(i)
        elif row["augmented"]:
            parent = row["aug_parent"]
            defect_groups[parent].append(i)
        else:
            # Orijinal hatali resim
            defect_groups[row["filepath"]].append(i)

    # Hatali gruplari shuffle et ve split
    defect_group_keys = list(defect_groups.keys())
    random.shuffle(defect_group_keys)

    n_defect = len(defect_group_keys)
    n_train_d = int(n_defect * TRAIN_RATIO)
    n_val_d = int(n_defect * VAL_RATIO)

    defect_train_keys = defect_group_keys[:n_train_d]
    defect_val_keys = defect_group_keys[n_train_d:n_train_d + n_val_d]
    defect_test_keys = defect_group_keys[n_train_d + n_val_d:]

    # OK resimleri shuffle et ve split
    random.shuffle(ok_indices)
    n_ok = len(ok_indices)
    n_train_ok = int(n_ok * TRAIN_RATIO)
    n_val_ok = int(n_ok * VAL_RATIO)

    ok_train = ok_indices[:n_train_ok]
    ok_val = ok_indices[n_train_ok:n_train_ok + n_val_ok]
    ok_test = ok_indices[n_train_ok + n_val_ok:]

    # Split ata
    for i in ok_train:
        combined_rows[i]["split"] = "train"
    for i in ok_val:
        combined_rows[i]["split"] = "val"
    for i in ok_test:
        combined_rows[i]["split"] = "test"

    for key in defect_train_keys:
        for i in defect_groups[key]:
            combined_rows[i]["split"] = "train"
    for key in defect_val_keys:
        for i in defect_groups[key]:
            combined_rows[i]["split"] = "val"
    for key in defect_test_keys:
        for i in defect_groups[key]:
            combined_rows[i]["split"] = "test"

    return combined_rows


def build_combined_metadata(hatali_rows, aug_rows):
    """Hatasiz + hatali + augmented → combined_metadata.csv"""
    print(f"\n[ADIM 4/5] Combined Metadata Olusturuluyor...")

    # Hatasiz metadata'yi oku
    ok_rows = []
    with open(OK_METADATA, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ok_rows.append({
                "filepath": f"raw_data/{row['filepath']}",
                "filename": row["filename"],
                "component": row["component"],
                "comp_prefix": row["comp_prefix"],
                "comp_type": row["comp_type"],
                "comp_index": row["comp_index"],
                "timestamp": row["timestamp"],
                "batch": row["batch"],
                "is_special": row["is_special"],
                "special_note": row["special_note"],
                "label": "ok",
                "source": "scan",
                "augmented": False,
                "aug_parent": "",
                "judgment_raw": "",
                "inspection_raw": "",
                "split": "",
            })

    # Hatali + augmented satirlara split alani ekle
    for row in hatali_rows:
        row["split"] = ""
    for row in aug_rows:
        row["split"] = ""

    # Hepsini birlestir
    combined = ok_rows + hatali_rows + aug_rows

    # Split ata
    combined = assign_splits(combined)

    # CSV yaz
    fieldnames = [
        "filepath", "filename", "component", "comp_prefix", "comp_type",
        "comp_index", "timestamp", "batch", "is_special", "special_note",
        "label", "source", "augmented", "aug_parent",
        "judgment_raw", "inspection_raw", "split",
    ]

    with open(COMBINED_METADATA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(combined)

    print(f"  Kaydedildi: {COMBINED_METADATA}")

    return combined


# ============================================================
# BOLUM 4: RAPOR
# ============================================================
def print_report(combined):
    """Detayli final rapor."""
    print(f"\n[ADIM 5/5] Final Rapor")
    print("=" * 70)
    print("  COMBINED DATASET RAPORU")
    print("=" * 70)

    # Genel sayilar
    total = len(combined)
    ok_count = sum(1 for r in combined if r["label"] == "ok")
    defect_orig = sum(1 for r in combined if r["label"] != "ok" and not r["augmented"])
    defect_aug = sum(1 for r in combined if r["label"] != "ok" and r["augmented"])

    print(f"\n  Toplam kayit:             {total}")
    print(f"    Hatasiz (ok):           {ok_count}")
    print(f"    Hatali (orijinal):      {defect_orig}")
    print(f"    Hatali (augmented):     {defect_aug}")
    print(f"    Hatali toplam:          {defect_orig + defect_aug}")
    print(f"    ok:defect orani:        {ok_count}:{defect_orig + defect_aug} "
          f"(~{ok_count / max(1, defect_orig + defect_aug):.1f}:1)")

    # Label dagilimi
    label_counts = defaultdict(int)
    for r in combined:
        label_counts[r["label"]] += 1

    print(f"\n  --- Label Dagilimi ---")
    for lbl, cnt in sorted(label_counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(40, cnt // max(1, total // 40))
        print(f"    {lbl:<25} {cnt:>6}  {bar}")

    # Split dagilimi
    split_label_counts = defaultdict(lambda: defaultdict(int))
    for r in combined:
        split_label_counts[r["split"]][r["label"]] += 1

    print(f"\n  --- Split Dagilimi ---")
    for split_name in ["train", "val", "test"]:
        split_data = split_label_counts.get(split_name, {})
        total_split = sum(split_data.values())
        ok_split = split_data.get("ok", 0)
        defect_split = total_split - ok_split
        print(f"\n    {split_name.upper()} ({total_split} kayit)")
        print(f"      ok:     {ok_split:>6}")
        print(f"      defect: {defect_split:>6}")
        for lbl, cnt in sorted(split_data.items(), key=lambda x: -x[1]):
            if lbl != "ok":
                print(f"        {lbl:<23} {cnt:>4}")

    # Augmentation detayi
    print(f"\n  --- Augmentation Bilgisi ---")
    print(f"    Orijinal hatali:    {defect_orig}")
    print(f"    Augmentation faktor: {AUGMENTATION_FACTOR}x")
    print(f"    Uretilen:           {defect_aug}")
    print(f"    Toplam hatali:      {defect_orig + defect_aug}")

    # Data leakage kontrolu
    print(f"\n  --- Data Leakage Kontrolu ---")
    parent_splits = {}
    leakage_found = False
    for r in combined:
        if r["augmented"] and r["aug_parent"]:
            parent = r["aug_parent"]
            child_split = r["split"]
            if parent in parent_splits:
                if parent_splits[parent] != child_split:
                    leakage_found = True
                    print(f"    !! LEAKAGE: {parent} → {parent_splits[parent]} vs {child_split}")
            else:
                parent_splits[parent] = child_split

    # Orijinallerin split'ini de kontrol et
    for r in combined:
        if not r["augmented"] and r["label"] != "ok" and r["filepath"] in parent_splits:
            if r["split"] != parent_splits[r["filepath"]]:
                leakage_found = True
                print(f"    !! LEAKAGE: Orijinal {r['filepath']} split={r['split']}, "
                      f"augmented={parent_splits[r['filepath']]}")

    if not leakage_found:
        print(f"    [OK] Data leakage tespit edilmedi!")
        print(f"    [OK] Augmented veriler parent'lariyla ayni split'te.")

    print(f"\n{'=' * 70}")
    print(f"  CIKTI DOSYALARI")
    print(f"{'=' * 70}")
    print(f"  {HATALI_METADATA:<30} Hatali metadata ({defect_orig} kayit)")
    print(f"  {HATALI_AUG_DIR + '/':<30} Augmented resimler ({defect_aug} resim)")
    print(f"  {COMBINED_METADATA:<30} Birlesik metadata ({total} kayit)")
    print(f"\n{'=' * 70}\n")


# ============================================================
# MAIN
# ============================================================
def main():
    print()
    print("=" * 70)
    print("  PCB DEFECT DATASET BUILDER")
    print("=" * 70)

    # Kontroller
    if not os.path.exists(HATALI_DIR):
        print(f"[HATA] {HATALI_DIR} klasoru bulunamadi!")
        return
    if not os.path.exists(OK_METADATA):
        print(f"[HATA] {OK_METADATA} bulunamadi! Once generate_metadata.py calistirin.")
        return

    # 1. HTML parse
    img_label_map = parse_html_files(HATALI_DIR)

    # 2. Hatali metadata
    hatali_rows = build_hatali_metadata(HATALI_DIR, img_label_map)

    # 3. Augmentation
    aug_rows = run_augmentation(hatali_rows)

    # 4. Birlestirme + split
    combined = build_combined_metadata(hatali_rows, aug_rows)

    # 5. Rapor
    print_report(combined)


if __name__ == "__main__":
    main()
