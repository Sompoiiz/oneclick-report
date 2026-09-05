"""
ระบบสรุปผลการประเมินโครงการอัตโนมัติ (OneClick Report)

รันด้วยคำสั่ง: streamlit run app.py
"""
from datetime import datetime

import pandas as pd
import streamlit as st

from modules import data_loader, report_generator, stats_utils

st.set_page_config(
    page_title="ระบบสรุปผลการประเมินโครงการ",
    page_icon="📊",
    layout="wide",
)

STEP_LABELS = ["นำเข้าข้อมูล", "ตั้งค่าคอลัมน์", "ผลสถิติ", "ออกรายงาน"]
STEP_ICONS = ["📤", "⚙️", "📊", "📄"]

_LEVEL_COLORS = {
    "มากที่สุด": "background-color: #1b5e20; color: white",
    "มาก": "background-color: #10B981; color: white",
    "ปานกลาง": "background-color: #F59E0B; color: black",
    "น้อย": "background-color: #FB923C; color: white",
    "น้อยที่สุด": "background-color: #F43F5E; color: white",
}

# ---------------------------------------------------------------------------
# ธีม/สไตล์: โทนสดใสทันสมัย + ฟอนต์ Kanit (แก้ปัญหา "หน้าตาดูเรียบ" ที่ผู้ใช้แจ้ง)
# ---------------------------------------------------------------------------
_CUSTOM_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
html, body, [class*="css"] { font-family: 'Kanit', sans-serif; }
.block-container { max-width: 1100px; padding-top: 2rem; }
.stepper { display: flex; align-items: flex-start; margin: 0.5rem 0 2.5rem 0; }
.step-item { display: flex; flex-direction: column; align-items: center; flex: 0 0 auto; width: 110px; }
.step-circle { width: 42px; height: 42px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 1.2rem; background: #E2E8F0; color: #64748B; border: 2px solid #E2E8F0; transition: all .2s; }
.step-item.completed .step-circle { background: #10B981; border-color: #10B981; color: #fff; }
.step-item.active .step-circle { background: #7C3AED; border-color: #7C3AED; color: #fff; box-shadow: 0 0 0 5px rgba(124,58,237,.18); }
.step-label { margin-top: .5rem; font-size: .82rem; text-align: center; color: #64748B; font-weight: 500; line-height: 1.2; }
.step-item.active .step-label { color: #7C3AED; font-weight: 700; }
.step-item.completed .step-label { color: #10B981; }
.step-line { flex: 1 1 auto; height: 3px; background: #E2E8F0; margin-top: 20px; }
.step-line.completed { background: #10B981; }
.stButton > button { border-radius: 10px; font-weight: 600; padding: .5rem 1.4rem; transition: all .15s ease; }
[data-testid="stBaseButton-primary"] { background: linear-gradient(135deg, #7C3AED, #6366F1) !important; border: none !important; }
[data-testid="stBaseButton-primary"]:hover { box-shadow: 0 6px 16px rgba(124,58,237,.35); }
[data-testid="stMetric"] { background: #fff; border: 1px solid #E2E8F0; border-radius: 14px; padding: 1rem 1.2rem; box-shadow: 0 1px 3px rgba(0,0,0,.05); }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px !important; }
h1, h2, h3 { font-weight: 600; }
</style>
"""
st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# ค่าเริ่มต้นใน session_state
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "step": 1,
    "df": None,
    "likert_cols": [],
    "demographic_cols": [],
    "column_groups": {},
    "feedback_col": None,
    "project_name": "",
    "event_period": "",
    "event_location": "",
    "_loaded_source_id": None,
}
for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


def go_to(step: int) -> None:
    st.session_state.step = step


def reset_all() -> None:
    for key, default in _DEFAULTS.items():
        st.session_state[key] = default


def compute_flat_stats():
    df = st.session_state.df
    cols = st.session_state.likert_cols
    if df is None or not cols:
        return None, {"mean": 0.0, "sd": 0.0, "level": "-"}
    stats_df = stats_utils.calculate_statistics(df, cols)
    overall = stats_utils.overall_summary(stats_df)
    return stats_df, overall


def compute_grouped_stats():
    df = st.session_state.df
    likert_cols = st.session_state.likert_cols
    if df is None or not likert_cols:
        return []
    group_map: dict[str, list[str]] = {}
    for col in likert_cols:
        name = str(st.session_state.column_groups.get(col, "")).strip() or stats_utils.DEFAULT_GROUP_NAME
        group_map.setdefault(name, []).append(col)
    return stats_utils.calculate_grouped_statistics(df, group_map)


def compute_demographics():
    df = st.session_state.df
    cols = st.session_state.demographic_cols
    if df is None or not cols:
        return {}
    return stats_utils.calculate_demographics(df, cols)


def render_stepper(current: int) -> None:
    parts = ['<div class="stepper">']
    for i, (label, icon) in enumerate(zip(STEP_LABELS, STEP_ICONS), start=1):
        if i < current:
            cls, circle = "completed", "✓"
        elif i == current:
            cls, circle = "active", icon
        else:
            cls, circle = "", icon
        parts.append(
            f'<div class="step-item {cls}"><div class="step-circle">{circle}</div>'
            f'<div class="step-label">{label}</div></div>'
        )
        if i < len(STEP_LABELS):
            parts.append(f'<div class="step-line {"completed" if i < current else ""}"></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_stats_table(items_df: pd.DataFrame) -> None:
    styled = items_df.style.map(lambda v: _LEVEL_COLORS.get(v, ""), subset=["แปลผล"]).format({
        "ค่าเฉลี่ย (Mean)": "{:.2f}",
        "ส่วนเบี่ยงเบนมาตรฐาน (S.D.)": "{:.2f}",
    })
    st.dataframe(styled, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# Main: หัวข้อ + ปุ่มเริ่มใหม่ + Stepper + เนื้อหาตามขั้นตอน
# (ไม่มี sidebar แยกอีกต่อไป — ทุกอย่างอยู่ในหน้าเดียวตามลำดับขั้นตอน)
# ---------------------------------------------------------------------------
title_col, reset_col = st.columns([5, 1])
with title_col:
    st.title("ระบบสรุปผลการประเมินโครงการอัตโนมัติ")
with reset_col:
    if st.session_state.df is not None:
        st.write("")
        if st.button("🔄 เริ่มใหม่", width="stretch"):
            reset_all()
            st.rerun()

render_stepper(st.session_state.step)

step = st.session_state.step

# --- Step 1: นำเข้าข้อมูล ---
if step == 1:
    with st.container(border=True):
        st.subheader("📤 ขั้นตอนที่ 1: นำเข้าข้อมูล")
        st.caption("อัปโหลดไฟล์ผลการประเมิน หรือเชื่อมต่อ Google Sheets ที่เชื่อมกับ Google Form ของคุณ")

        source_type = st.radio(
            "แหล่งข้อมูล", ["อัปโหลดไฟล์ (CSV/Excel)", "Google Sheets"],
            horizontal=True, label_visibility="collapsed",
        )

        df_loaded = None
        if source_type == "อัปโหลดไฟล์ (CSV/Excel)":
            uploaded = st.file_uploader("เลือกไฟล์ข้อมูล", type=["csv", "xlsx"])
            if uploaded is not None and uploaded.file_id != st.session_state["_loaded_source_id"]:
                try:
                    if uploaded.name.lower().endswith(".csv"):
                        df_loaded = data_loader.load_csv(uploaded)
                    else:
                        df_loaded = data_loader.load_excel(uploaded)
                    st.session_state["_loaded_source_id"] = uploaded.file_id
                except Exception as e:
                    st.error(f"ไม่สามารถอ่านไฟล์ได้: {e}")
        else:
            sheet_url = st.text_input("วาง URL ของ Google Sheets")
            st.caption('⚠️ ชีตต้องตั้งค่าการแชร์เป็น "ทุกคนที่มีลิงก์ดูได้"')
            if st.button("ดึงข้อมูลจาก Google Sheets") and sheet_url:
                try:
                    df_loaded = data_loader.load_google_sheet(sheet_url)
                    st.session_state["_loaded_source_id"] = sheet_url
                except Exception as e:
                    st.error(str(e))

        if df_loaded is not None:
            st.session_state.df = df_loaded
            st.session_state.likert_cols = data_loader.detect_likert_columns(df_loaded)
            st.session_state.demographic_cols = data_loader.detect_categorical_columns(df_loaded)
            st.session_state.feedback_col = data_loader.detect_feedback_column(df_loaded)
            st.session_state.column_groups = {}
            st.rerun()  # ให้ปุ่ม "เริ่มใหม่" ที่หัวหน้าเพจ (render ก่อนหน้านี้) โผล่มาทันทีโดยไม่ต้องรอ interaction ครั้งถัดไป

        if st.session_state.df is not None:
            st.success(f"โหลดข้อมูลสำเร็จ ({len(st.session_state.df):,} แถว)")
            st.dataframe(st.session_state.df.head(5), width="stretch")

    _, col_next = st.columns([4, 1])
    with col_next:
        if st.button("ถัดไป →", type="primary", width="stretch", disabled=st.session_state.df is None):
            go_to(2)
            st.rerun()

# --- Step 2: ตั้งค่าคอลัมน์ ---
elif step == 2:
    df = st.session_state.df
    columns = list(df.columns)

    with st.container(border=True):
        st.subheader("⚙️ ขั้นตอนที่ 2: ตั้งค่าคอลัมน์")
        st.caption(
            'ติ๊ก "ข้อมูลผู้ตอบ" สำหรับคอลัมน์ข้อมูลทั่วไป (เช่น เพศ, ตำแหน่ง) และติ๊ก "Likert" '
            "สำหรับคำถามแบบมาตราส่วน 1-5 — ระบบเดาให้อัตโนมัติแล้ว ปรับแก้ไขได้ "
            'ใส่ "หมวด/ตอน" หากต้องการแยกผลค่าสถิติเป็นรายด้าน (เว้นว่างได้หากไม่ต้องการแยก)'
        )

        column_df = pd.DataFrame({
            "คอลัมน์": columns,
            "ข้อมูลผู้ตอบ": [c in st.session_state.demographic_cols for c in columns],
            "ใช้คำนวณสถิติ": [c in st.session_state.likert_cols for c in columns],
            "หมวด/ตอน": [str(st.session_state.column_groups.get(c, "")) for c in columns],
        })
        edited = st.data_editor(
            column_df,
            column_config={
                "คอลัมน์": st.column_config.TextColumn("ชื่อคำถาม/คอลัมน์", disabled=True, width="large"),
                "ข้อมูลผู้ตอบ": st.column_config.CheckboxColumn("ข้อมูลผู้ตอบ?", width="small"),
                "ใช้คำนวณสถิติ": st.column_config.CheckboxColumn("Likert (1-5)?", width="small"),
                "หมวด/ตอน": st.column_config.TextColumn("หมวด/ตอน (ถ้ามี)", width="medium"),
            },
            hide_index=True,
            width="stretch",
            height=min(38 * (len(columns) + 1), 380),
            key="column_editor",
        )
        st.session_state.demographic_cols = edited.loc[edited["ข้อมูลผู้ตอบ"], "คอลัมน์"].tolist()
        st.session_state.likert_cols = edited.loc[edited["ใช้คำนวณสถิติ"], "คอลัมน์"].tolist()
        st.session_state.column_groups = dict(zip(edited["คอลัมน์"], edited["หมวด/ตอน"]))

        st.divider()
        feedback_options = ["(ไม่มี)"] + columns
        current_fb = st.session_state.feedback_col
        default_index = feedback_options.index(current_fb) if current_fb in columns else 0
        feedback_choice = st.selectbox(
            "คอลัมน์ข้อเสนอแนะ (ข้อความอิสระ) — ถ้าเลือกจะแสดงเป็นรายการในรายงาน",
            options=feedback_options,
            index=default_index,
        )
        st.session_state.feedback_col = None if feedback_choice == "(ไม่มี)" else feedback_choice

    col_back, _, col_next = st.columns([1, 3, 1])
    with col_back:
        if st.button("← ย้อนกลับ", width="stretch"):
            go_to(1)
            st.rerun()
    with col_next:
        if st.button("ถัดไป →", type="primary", width="stretch", disabled=not st.session_state.likert_cols):
            go_to(3)
            st.rerun()
    if not st.session_state.likert_cols:
        st.warning("กรุณาเลือกอย่างน้อย 1 คอลัมน์ Likert สำหรับคำนวณสถิติ")

# --- Step 3: ผลสถิติ ---
elif step == 3:
    _, overall = compute_flat_stats()
    groups = compute_grouped_stats()
    demographics = compute_demographics()
    is_single_group = len(groups) == 1 and groups[0]["group_name"] == stats_utils.DEFAULT_GROUP_NAME

    with st.container(border=True):
        st.subheader("📊 ขั้นตอนที่ 3: ผลสถิติ")

        c1, c2, c3 = st.columns(3)
        c1.metric("จำนวนผู้ตอบแบบประเมิน", f"{len(st.session_state.df):,} คน")
        c2.metric("ค่าเฉลี่ยรวม", f"{overall['mean']:.2f}")
        c3.metric("ระดับความพึงพอใจโดยรวม", overall["level"])

        if demographics:
            st.divider()
            st.markdown("**ข้อมูลของผู้ตอบแบบประเมิน**")
            for col_name, breakdown_df in demographics.items():
                st.caption(f"จำแนกตาม{col_name}")
                st.dataframe(breakdown_df, width="stretch", hide_index=True)

        st.divider()
        if is_single_group:
            st.markdown("**ตารางค่าเฉลี่ยและส่วนเบี่ยงเบนมาตรฐานรายข้อ**")
            render_stats_table(groups[0]["items"])
        else:
            st.markdown("**ผลการประเมินรายด้าน**")
            for gi, g in enumerate(groups, start=1):
                st.markdown(f"**{gi}. {g['group_name']}**")
                render_stats_table(g["items"])
                avg = g["average"]
                st.caption(f"ค่าเฉลี่ยด้าน{g['group_name']}: {avg['mean']:.2f} (S.D. {avg['sd']:.2f}) — ระดับ{avg['level']}")

        flat_df, _ = compute_flat_stats()
        if flat_df is not None and not flat_df.empty:
            st.divider()
            st.markdown("**กราฟเปรียบเทียบค่าเฉลี่ยรายข้อ**")
            chart_df = flat_df.set_index("ข้อคำถาม")[["ค่าเฉลี่ย (Mean)"]]
            st.bar_chart(chart_df, color="#7C3AED")

        with st.expander("เกณฑ์การแปลความหมาย"):
            for low, high, label in stats_utils.INTERPRETATION_LEVELS:
                st.write(f"- {low:.2f} - {high:.2f} หมายถึง **{label}**")

    col_back, _, col_next = st.columns([1, 3, 1])
    with col_back:
        if st.button("← ย้อนกลับ", width="stretch"):
            go_to(2)
            st.rerun()
    with col_next:
        if st.button("ถัดไป →", type="primary", width="stretch"):
            go_to(4)
            st.rerun()

# --- Step 4: ออกรายงาน ---
elif step == 4:
    groups = compute_grouped_stats()
    demographics = compute_demographics()
    feedback_texts = []
    if st.session_state.feedback_col:
        raw_texts = st.session_state.df[st.session_state.feedback_col].dropna().astype(str).tolist()
        feedback_texts = [t.strip() for t in raw_texts if t.strip()]

    with st.container(border=True):
        st.subheader("📄 ขั้นตอนที่ 4: ออกรายงาน")
        st.session_state["project_name"] = st.text_input(
            "ชื่อโครงการ (สำหรับหน้าปกรายงาน)", value=st.session_state["project_name"]
        )
        col_a, col_b = st.columns(2)
        with col_a:
            st.session_state["event_period"] = st.text_input(
                "ช่วงเวลาจัดกิจกรรม (ถ้ามี)",
                value=st.session_state["event_period"],
                placeholder="เช่น 11-13 มิถุนายน 2569",
            )
        with col_b:
            st.session_state["event_location"] = st.text_input(
                "สถานที่จัดกิจกรรม (ถ้ามี)",
                value=st.session_state["event_location"],
                placeholder="เช่น วารี วัลเลย์ รีสอร์ท ขอนแก่น",
            )

        report_parts = ["ปก", "รูปแบบการประเมินผล", "เกณฑ์การประเมิน"]
        if demographics:
            report_parts.append("ข้อมูลผู้ตอบแบบประเมิน")
        report_parts.append("ผลการประเมินรายด้าน")
        if feedback_texts:
            report_parts.append(f"ข้อเสนอแนะอื่นๆ ({len(feedback_texts)} ข้อความ)")
        st.write("รายงานจะประกอบด้วย: " + " / ".join(report_parts))

        report_buffer = report_generator.generate_report(
            project_name=st.session_state.get("project_name") or "-",
            event_period=st.session_state.get("event_period") or "",
            event_location=st.session_state.get("event_location") or "",
            respondent_count=len(st.session_state.df),
            demographics=demographics,
            groups=groups,
            feedback_texts=feedback_texts,
        )

        st.download_button(
            label="📥 Export to Word (.docx)",
            data=report_buffer,
            file_name=f"รายงานผลการประเมิน_{datetime.now().strftime('%Y%m%d')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )

    col_back, _ = st.columns([1, 4])
    with col_back:
        if st.button("← ย้อนกลับ", width="stretch"):
            go_to(3)
            st.rerun()
