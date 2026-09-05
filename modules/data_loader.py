"""
โมดูลสำหรับนำเข้าข้อมูล (CSV / Excel / Google Sheets)
และตรวจจับคอลัมน์ประเภทต่าง ๆ โดยอัตโนมัติ
"""
from __future__ import annotations

import re

import pandas as pd

# encoding ที่มักพบในไฟล์ CSV ของไทย เรียงตามความน่าจะเป็น
# (ไฟล์ที่ export จาก Excel บน Windows มักเป็น cp874/tis-620 ไม่ใช่ utf-8)
_CSV_ENCODINGS = ["utf-8-sig", "utf-8", "cp874", "tis-620"]


def load_csv(file) -> pd.DataFrame:
    """อ่านไฟล์ CSV โดยไล่ลอง encoding ที่พบบ่อยในไฟล์ภาษาไทย"""
    last_err: Exception | None = None
    for enc in _CSV_ENCODINGS:
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=enc)
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
            continue
    raise ValueError(
        f"ไม่สามารถอ่านไฟล์ CSV ได้ (ลองแล้วหลาย encoding: {', '.join(_CSV_ENCODINGS)}) "
        f"กรุณาบันทึกไฟล์เป็น UTF-8 แล้วลองใหม่: {last_err}"
    )


def load_excel(file) -> pd.DataFrame:
    """อ่านไฟล์ Excel (.xlsx) ด้วย openpyxl"""
    return pd.read_excel(file, engine="openpyxl")


def gsheet_url_to_csv(url: str) -> str:
    """แปลงลิงก์ Google Sheets ทั่วไป ให้เป็นลิงก์ export CSV โดยตรง"""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError("ไม่พบ Google Sheets ID ใน URL ที่ระบุ กรุณาตรวจสอบลิงก์อีกครั้ง")
    sheet_id = match.group(1)
    gid_match = re.search(r"[?&#]gid=([0-9]+)", url)
    gid = gid_match.group(1) if gid_match else "0"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def load_google_sheet(url: str) -> pd.DataFrame:
    """ดึงข้อมูลจาก Google Sheets ที่แชร์แบบ 'ทุกคนที่มีลิงก์ดูได้' มาเป็น DataFrame"""
    csv_url = gsheet_url_to_csv(url)
    try:
        return pd.read_csv(csv_url)
    except Exception as e:
        raise ValueError(
            "ไม่สามารถดึงข้อมูลจาก Google Sheets ได้ กรุณาตรวจสอบว่า:\n"
            "1) ตั้งค่าการแชร์เป็น \"ทุกคนที่มีลิงก์ดูได้ (Anyone with the link can view)\"\n"
            "2) ลิงก์ที่วางถูกต้องและชี้ไปยังชีตที่มีข้อมูล"
        ) from e


def detect_likert_columns(df: pd.DataFrame, min_val: int = 1, max_val: int = 5) -> list[str]:
    """
    ตรวจจับคอลัมน์ที่น่าจะเป็นคำถามแบบมาตราส่วนประมาณค่า (Likert scale 1-5) โดยอัตโนมัติ
    เกณฑ์: เป็นตัวเลขอย่างน้อย 50% ของแถวทั้งหมด และค่าที่แปลงได้อยู่ในช่วง 1-5 อย่างน้อย 80%
    """
    likert_cols = []
    for col in df.columns:
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().mean() < 0.5:
            continue
        valid = series.dropna()
        if len(valid) > 0 and valid.between(min_val, max_val).mean() > 0.8:
            likert_cols.append(col)
    return likert_cols


def detect_categorical_columns(df: pd.DataFrame, max_unique: int = 12) -> list[str]:
    """
    เดาคอลัมน์ข้อมูลผู้ตอบ (เช่น เพศ, ตำแหน่ง) จากคอลัมน์ข้อความที่มีค่าไม่ซ้ำน้อย
    (ข้อความอิสระอย่างข้อเสนอแนะจะมีค่าเกือบไม่ซ้ำกันเลย จึงหลุดเกณฑ์นี้ไปเองตามธรรมชาติ)
    """
    candidates = []
    for col in df.columns:
        if df[col].dtype == object:
            nunique = df[col].nunique(dropna=True)
            if 1 < nunique <= max_unique:
                candidates.append(col)
    return candidates


def detect_feedback_column(df: pd.DataFrame) -> str | None:
    """เดาคอลัมน์ข้อเสนอแนะ/ความคิดเห็นแบบข้อความอิสระ จากชื่อคอลัมน์ก่อน แล้วจึงเดาจากความยาวข้อความ"""
    keywords = [
        "ข้อเสนอแนะ", "ความคิดเห็นเพิ่มเติม", "ความคิดเห็นอื่น", "อื่นๆ",
        "comment", "feedback", "suggestion",
    ]
    candidates = [c for c in df.columns if any(k in str(c) for k in keywords)]
    if candidates:
        return candidates[-1]  # โดยทั่วไปคอลัมน์ข้อเสนอแนะแบบเปิดจะอยู่ท้ายแบบฟอร์ม

    obj_cols = df.select_dtypes(include="object").columns
    if len(obj_cols) == 0:
        return None
    avg_lens = {c: df[c].astype(str).str.len().mean() for c in obj_cols}
    return max(avg_lens, key=avg_lens.get)
