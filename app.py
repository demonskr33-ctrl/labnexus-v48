# app.py  ——  LabNexus V48 终极版（公网部署专用）
# 直接复制全部内容保存为 app.py 即可

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import json
import os
from datetime import datetime, date
import base64

# ================= 配置 =================
st.set_page_config(
    page_title="LabNexus V48 - 实验室大脑",
    page_icon="DNA",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 美化
st.markdown("""
<style>
    .main > div {padding-top: 2rem;}
    .stButton>button {border-radius: 8px; height: 3em; font-weight: bold;}
    .success-box {background: linear-gradient(90deg, #d4edda, #c3e6cb); padding: 1rem; border-radius: 10px; border-left: 5px solid #28a745;}
    .exp-header {background: linear-gradient(120deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.2rem; border-radius: 12px; margin: 1rem 0; text-align: center;}
    .metric-card {background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); text-align: center;}
</style>
""", unsafe_allow_html=True)

DB_NAME = "lab_nexus_data.db"
STANDARD_METRICS = ["大蒜辣素含量", "蒜氨酸含量", "水分", "耐酸力", "累计溶出度", "增重", "pH"]

@st.cache_resource
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False, timeout=20)

def run_query(sql, params=(), fetch=False):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        if fetch:
            return cur.fetchall()
        conn.commit()
        return cur.lastrowid

# ================= 自动建表 + 智能升级 =================
def init_db():
    if st.session_state.get("db_ready"): return
    with get_conn() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOIN8INCREMENT,
            project TEXT, title TEXT, batch_no TEXT, date TEXT,
            status TEXT DEFAULT '进行中', tags TEXT, conclusion TEXT, notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id INTEGER, sample_name TEXT, group_name TEXT, replicate INTEGER, sort_order INTEGER,
            FOREIGN KEY(exp_id) REFERENCES experiments(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS sample_metrics (
            sample_id INTEGER, metric_name TEXT, value REAL,
            PRIMARY KEY (sample_id, metric_name)
        );
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id INTEGER, filename TEXT, file_data BLOB
        );
        ''')
    st.session_state.db_ready = True
    st.success("LabNexus V48 已启动！后Excel时代来临！")

init_db()

# ================= 侧边栏 =================
with st.sidebar:
    st.markdown("<h1 style='color:#667eea'>DNA LabNexus V48</h1>", unsafe_allow_html=True)
    st.markdown("**你的实验室，终于有了大脑**")
    st.markdown("---")
    if st.button("新建实验", type="primary", use_container_width=True):
        st.session_state.mode = "new"
    st.markdown("---")
    st.caption(f"数据库：{DB_NAME} | 实验总数：{len(run_query('SELECT id FROM experiments', fetch=True) or [])}")

# ================= 主界面 =================
st.markdown("<div class='exp-header'><h1>实验列表</h1></div>", unsafe_allow_html=True)

if st.session_state.get("mode") == "new":
    with st.form("新建实验"):
        c1, c2 =  st.columns(2)
        with c1:
            project = st.text_input("项目名称", "大蒜深加工")
            title = st.text_input("实验标题", "酶解条件优化实验")
        with c2:
            batch_no = st.text_input("批号", "2025-003")
            exp_date = st.date_input("日期", date.today())
        template = st.selectbox("模板", ["6个平行样", "3组×3重复", "时间序列", "空白模板"])
        if st.form_submit_button("创建实验"):
            exp_id = run_query("INSERT INTO experiments (project, title, batch_no, date) VALUES (?,?,?,?)",
                               (project, title, batch_no, str(exp_date)))
            samples = {
                "6个平行样": [f"平行样{i}" for i in range(1,7)],
                "3组×3重复": [f"{g}-重复{r}" for g in ["对照","加酶","高温"] for r in range(1,4)],
                "时间序列": ["0h","2h","4h","8h","12h","24h"],
                "空白模板": ["样品1"]
            }[template]
            for i, s in enumerate(samples):
                run_query("INSERT INTO samples (exp_id, sample_name, sort_order) VALUES (?,?,?)", (exp_id, s, i+1))
            st.success(f"实验创建成功！ID: {exp_id}")
            st.session_state.current_exp = exp_id
            st.rerun()

# 列出实验
exps = run_query("SELECT id, title, batch_no, date, status FROM experiments ORDER BY id DESC", fetch=True) or []
for exp in exps[:100]:
    eid, title, batch, date, status = exp
    with st.container():
        col1, col2, col3 = st.columns([4,2,1.5])
        with col1:
            st.markdown(f"**{title}**  |  {batch or '无批号'}  |  {date}")
        with col2:
            st.write(f"状态：`{status}`")
        with col3:
            if st.button("进入", key=f"go_{eid}"):
                st.session_state.current_exp = eid
                st.rerun()

# ================= 实验详情页 =================
if "current_exp" in st.session_state:
    eid = st.session_state.current_exp
    data = run_query("SELECT * FROM experiments WHERE id=?", (eid,), fetch=True)[0]
    st.markdown(f"<div class='exp-header'><h2>实验 #{eid}: {data[2]}</h2></div>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["多样品数据", "统计图表", "附件"])
    
    with tab1:
        samples = run_query("SELECT id, sample_name, group_name, replicate FROM samples WHERE exp_id=? ORDER BY sort_order", (eid,))
        rows = []
        for sid, name, group, rep in samples:
            row = {"_id": sid, "样品名称": name, "处理组": group or "", "重复": rep or ""}
            metrics = run_query("SELECT metric_name, value FROM sample_metrics WHERE sample_id=?", (sid,))
            for m, v in metrics:
                row[m] = v
            rows.append(row)
        
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["样品名称"] + STANDARD_METRICS)
        edited = st.data_editor(
            df, num_rows="dynamic",
            column_config={m: st.column_config.NumberColumn(m, format="%.4f") for m in STANDARD_METRICS}
        )
        
        if st.button("保存所有数据", type="primary"):
            for _, row in edited.iterrows():
                sid = row.get("_id")
                if pd.isna(sid):
                    sid = run_query("INSERT INTO samples (exp_id, sample_name) VALUES (?,?)", (eid, row["样品名称"]))
                else:
                    run_query("UPDATE samples SET sample_name=? WHERE id=?", (row["样品名称"], int(sid)))
                for m in STANDARD_METRICS:
                    val = row.get(m)
                    if pd.notna(val):
                        run_query("INSERT OR REPLACE INTO sample_metrics VALUES (?,?,?)", (sid, m, float(val)))
            st.success("保存成功！")
            st.balloons()
    
    with tab2:
        df_raw = pd.read_sql(f"""
            SELECT s.sample_name, s.group_name, sm.metric_name, sm.value 
            FROM samples s 
            LEFT JOIN sample_metrics sm ON s.id = sm.sample_id 
            WHERE s.exp_id = {eid}
        """, get_conn())
        if not df_raw.empty:
            pivot = df_raw.pivot_table(index=["group_name", "sample_name"], columns="metric_name", values="value")
            st.dataframe(pivot)
            metric = st.selectbox("选择指标绘图", STANDARD_METRICS)
            fig = px.bar(df_raw[df_raw.metric_name==metric], x="group_name", y="value", error_y=df_raw[df_raw.metric_name==metric]["value"].std())
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        uploaded = st.file_uploader("上传附件", accept_multiple_files=True)
        if uploaded:
            for f in uploaded:
                run_query("INSERT INTO attachments (exp_id, filename, file_data) VALUES (?,?,?)",
                          (eid, f.name, f.getvalue()))
        atts = run_query("SELECT filename, file_data FROM attachments WHERE exp_id=?", (eid,))
        for name, data in atts:
            st.write(f"附件: {name}")
            if name.lower().endswith(('.png','.jpg','.jpeg')):
                st.image(data)
            st.download_button("下载", data, file_name=name)

st.markdown("---")
st.caption("LabNexus V48 • 你的实验室终于有了灵魂 • 再见，Excel！")
