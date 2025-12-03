import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import os
from datetime import date

st.set_page_config(
    page_title="LabNexus V48 - 实验室大脑",
    page_icon="DNA",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main > div {padding-top: 2rem;}
    .stButton>button {border-radius: 12px; height: 3em; font-weight: bold; width: 100%;}
    .exp-header {background: linear-gradient(120deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 15px; margin: 2rem 0; text-align: center; font-size: 2rem;}
</style>
""", unsafe_allow_html=True)

DB_NAME = "data/lab_nexus_data.db"
if not os.path.exists("data"):
    os.makedirs("data")

@st.cache_resource
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False, timeout=30)

def run_query(sql, params=(), fetch=False):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        if fetch:
            return cur.fetchall()
        conn.commit()
        return cur.lastrowid

def init_db():
    if st.session_state.get("db_ready"):
        return
    conn = get_conn()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project TEXT, title TEXT, batch_no TEXT, date TEXT,
        status TEXT DEFAULT '进行中', created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exp_id INTEGER, sample_name TEXT, sort_order INTEGER,
        FOREIGN KEY(exp_id) REFERENCES experiments(id) ON DELETE CASCADE
    );
    ''')
    conn.commit()
    st.session_state.db_ready = True
    st.success("LabNexus V48 启动成功！数据库已准备就绪")

init_db()

with st.sidebar:
    st.markdown("<h1 style='color:#667eea;text-align:center;'>DNA LabNexus V48</h1>", unsafe_allow_html=True)
    if st.button("新建实验", type="primary", use_container_width=True):
        st.session_state.mode = "new"
    total = len(run_query("SELECT id FROM experiments", fetch=True) or [])
    st.caption(f"实验总数：{total}")

st.markdown("<div class='exp-header'>实验列表</div>", unsafe_allow_html=True)

if st.session_state.get("mode") == "new":
    with st.form("new_exp"):
        c1, c2 = st.columns(2)
        with c1:
            project = st.text_input("项目名称", "大蒜深加工")
            title = st.text_input("实验标题", "酶解条件优化")
        with c2:
            batch = st.text_input("批号", "2025-003")
            d = st.date_input("日期", date.today())
        tmp = st.selectbox("模板", ["6个平行样", "3组×3重复", "时间序列", "空白"])
        if st.form_submit_button("创建实验"):
            eid = run_query("INSERT INTO experiments (project,title,batch_no,date) VALUES (?,?,?,?)",
                           (project, title, batch, str(d)))
            samples = {
                "6个平行样": [f"样品{i}" for i in range(1,7)],
                "3组×3重复": [f"{g}{r}" for g in ["A","B","C"] for r in range(1,4)],
                "时间序列": ["0h","2h","4h","8h","12h","24h"],
                "空白": ["样品1"]
            }[tmp]
            for i, s in enumerate(samples):
                run_query("INSERT INTO samples (exp_id, sample_name, sort_order) VALUES (?,?,?)", (eid, s, i+1))
            st.success(f"创建成功！ID: {eid}")
            st.session_state.current_exp = eid
            st.session_state.mode = None
            st.rerun()

exps = run_query("SELECT id, title, batch_no, date FROM experiments ORDER BY id DESC", fetch=True) or []
for e in exps:
    eid, title, batch, d = e
    with st.container():
        c1, c2 = st.columns([5,1])
        with c1:
            st.write(f"**{title}** | {batch} | {d}")
        with c2:
            if st.button("进入", key=eid):
                st.session_state.current_exp = eid
                st.rerun()

if st.session_state.get("current_exp"):
    eid = st.session_state.current_exp
    info = run_query("SELECT title FROM experiments WHERE id=?", (eid,), fetch=True)[0][0]
    st.markdown(f"# {info}")
    if st.button("返回列表"):
        st.session_state.pop("current_exp", None)
        st.rerun()
