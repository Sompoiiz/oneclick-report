"""
โมดูลคำนวณค่าสถิติพื้นฐาน (Mean, S.D.) และแปลความหมายตามเกณฑ์ 5 ระดับ
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# เกณฑ์การแปลความหมายค่าเฉลี่ย (ตามที่กำหนด)
INTERPRETATION_LEVELS = [
    (4.50, 5.00, "มากที่สุด"),
    (3.50, 4.49, "มาก"),
    (2.50, 3.49, "ปานกลาง"),
    (1.50, 2.49, "น้อย"),
    (1.00, 1.49, "น้อยที่สุด"),
]


def interpret_mean(mean: float) -> str:
    """แปลค่าเฉลี่ยเป็นระดับความหมายตามเกณฑ์ 5 ระดับ"""
    if np.isnan(mean):
        return "-"
    if mean >= 4.50:
        return "มากที่สุด"
    if mean >= 3.50:
        return "มาก"
    if mean >= 2.50:
        return "ปานกลาง"
    if mean >= 1.50:
        return "น้อย"
    return "น้อยที่สุด"


def calculate_statistics(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """คำนวณ Mean, S.D. และแปลผลของแต่ละคอลัมน์ (ข้อคำถาม) ที่ระบุ"""
    rows = []
    for col in columns:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        mean = series.mean() if len(series) > 0 else float("nan")
        sd = series.std() if len(series) > 1 else 0.0
        rows.append({
            "ข้อคำถาม": col,
            "จำนวน (n)": int(series.count()),
            "ค่าเฉลี่ย (Mean)": round(mean, 2) if not np.isnan(mean) else 0.0,
            "ส่วนเบี่ยงเบนมาตรฐาน (S.D.)": round(sd, 2) if not np.isnan(sd) else 0.0,
            "แปลผล": interpret_mean(mean),
        })
    return pd.DataFrame(rows)


def overall_summary(stats_df: pd.DataFrame) -> dict:
    """สรุปภาพรวมจากตารางค่าสถิติรายข้อ (ค่าเฉลี่ยของค่าเฉลี่ยทั้งหมด)"""
    if stats_df is None or stats_df.empty:
        return {"mean": 0.0, "sd": 0.0, "level": "-"}
    overall_mean = stats_df["ค่าเฉลี่ย (Mean)"].mean()
    overall_sd = stats_df["ส่วนเบี่ยงเบนมาตรฐาน (S.D.)"].mean()
    return {
        "mean": round(overall_mean, 2),
        "sd": round(overall_sd, 2),
        "level": interpret_mean(overall_mean),
    }


# ชื่อกลุ่มที่ใช้เมื่อผู้ใช้ไม่ได้ระบุ "หมวด/ตอน" ให้คอลัมน์ใดเลย (โหมดตารางเดี่ยวแบบเดิม)
DEFAULT_GROUP_NAME = "ผลการประเมิน"


def calculate_grouped_statistics(df: pd.DataFrame, group_map: dict[str, list[str]]) -> list[dict]:
    """
    คำนวณค่าสถิติแยกตามกลุ่ม/หมวด/ตอน (ตามที่ผู้ใช้จัดกลุ่มไว้ในขั้นตอนที่ 2)
    คืนค่าเป็นลิสต์ตามลำดับกลุ่มที่พบ แต่ละก้อนมี:
      - group_name: ชื่อกลุ่ม
      - items: ตาราง Mean/S.D./แปลผลรายข้อ (จาก calculate_statistics)
      - average: ค่าเฉลี่ยรวมของกลุ่มนั้น (จาก overall_summary)
    """
    groups = []
    for group_name, cols in group_map.items():
        if not cols:
            continue
        items_df = calculate_statistics(df, cols)
        groups.append({
            "group_name": group_name,
            "items": items_df,
            "average": overall_summary(items_df),
        })
    return groups


def calculate_demographics(df: pd.DataFrame, columns: list[str]) -> dict[str, pd.DataFrame]:
    """
    สรุปจำนวนและร้อยละของผู้ตอบแบบประเมิน แยกตามคอลัมน์ข้อมูลผู้ตอบที่ระบุ (เช่น เพศ, ตำแหน่ง)
    คืนค่าเป็น dict: {ชื่อคอลัมน์: ตาราง (รายการ, จำนวน (คน), ร้อยละ)}
    """
    result = {}
    for col in columns:
        counts = df[col].fillna("ไม่ระบุ").astype(str).value_counts()
        total = int(counts.sum())
        rows = []
        for value, count in counts.items():
            pct = round(count / total * 100, 2) if total else 0.0
            rows.append({"รายการ": value, "จำนวน (คน)": int(count), "ร้อยละ": pct})
        rows.append({"รายการ": "รวม", "จำนวน (คน)": total, "ร้อยละ": 100.0 if total else 0.0})
        result[col] = pd.DataFrame(rows)
    return result
