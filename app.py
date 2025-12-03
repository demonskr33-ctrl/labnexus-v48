import streamlit as st
import sqlite3
import pandas as pd
import datetime
import io
import json
import os
import glob
import time
import re

# ================= 1. 全局配置 =================
st.set_page_config(page_title="LabNexus V46", page_icon="🧬", layout="wide")

STANDARD_METRICS = [
    "大蒜辣素含量", "蒜氨酸含量", "水分", 
    "耐酸力", "累计溶出度", "增重"
]

st.markdown("""
<style>
    .stApp {font-family: 'Roboto', sans-serif;}
    .metric-card {
        background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px;
        padding: 15px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-label { color: #6c757d; font-size: 0.85rem; font-weight: 500; margin-bottom: 5px; }
    .metric-value { color: #2c3e50; font-size: 1.4rem; font-weight: bold; }
    .exp-card {
        background: white; border-radius: 8px; padding: 12px; margin-bottom: 8px;
        border-left: 4px solid #0d6efd; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .slicer-box {
        border: 1px dashed #aaa; padding: 15px; border-radius: 10px; margin-top: 10px;
        background-color: #f8f9fa;
    }
    .add-btn-area {
        margin-top: 10px; padding-top: 10px; border-top: 1px dashed #eee; text-align: right;
    }
</style>
""", unsafe_allow_html=True)

# ================= 2. 数据库层 =================

@st.cache_resource
def get_db_connection_cached(db_path):
    return sqlite3.connect(db_path, check_same_thread=False)

def get_active_db_path():
    if 'active_db' in st.session_state and os.path.exists(st.session_state['active_db']):
        return st.session_state['active_db']
    priority = "lab_nexus_v25.db"
    if os.path.exists(priority): return priority
    files = glob.glob("*.db")
    if files: return max(files, key=os.path.getsize)
    return "lab_nexus.db"

def run_query(query, params=(), fetch=True):
    db_path = get_active_db_path()
    conn = get_db_connection_cached(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if fetch:
            res = cursor.fetchall()
            return res
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        st.error(f"DB Error: {e}")
        return None

def init_db():
    run_query('''CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, title TEXT, batch_no TEXT, date TEXT, status TEXT, tags TEXT, variables TEXT, conclusion TEXT, notes TEXT, searchable_metrics TEXT)''', fetch=False)
    run_query('''CREATE TABLE IF NOT EXISTS attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, exp_id INTEGER, filename TEXT, file_type TEXT, file_data BLOB, FOREIGN KEY(exp_id) REFERENCES experiments(id) ON DELETE CASCADE)''', fetch=False)
    run_query('''CREATE TABLE IF NOT EXISTS projects (name TEXT PRIMARY KEY, created_at TEXT, description TEXT)''', fetch=False)
    try:
        exps = run_query("SELECT DISTINCT project FROM experiments")
        for p in exps:
            if p[0]: run_query("INSERT OR IGNORE INTO projects (name, created_at) VALUES (?, ?)", (p[0], datetime.date.today()), fetch=False)
    except: pass

# ================= 3. 业务逻辑 =================

def get_projects():
    res = run_query("SELECT name FROM projects ORDER BY created_at DESC")
    return [r[0] for r in res] if res else []

def create_proj(name):
    run_query("INSERT INTO projects VALUES (?, ?, ?)", (name, datetime.date.today(), ""), fetch=False)

def save_experiment_atomic(data, files, metrics):
    mj = json.dumps(metrics)
    cid = data.get('id')
    
    # 🔴 V46 修复：强制转换日期格式，防止 Timestamp 报错
    raw_date = data.get('date')
    if hasattr(raw_date, 'strftime'):
        date_str = raw_date.strftime("%Y-%m-%d")
    else:
        date_str = str(raw_date)

    safe_data = {
        'project': data.get('project', ''),
        'title': data.get('title', ''),
        'batch_no': data.get('batch_no', ''),
        'date': date_str, # 使用转换后的字符串
        'status': data.get('status', 'pending'),
        'tags': data.get('tags', ''),
        'variables': data.get('variables', ''),
        'conclusion': data.get('conclusion', ''),
        'notes': data.get('notes', '')
    }
    
    if cid:
        run_query('''UPDATE experiments SET project=?, title=?, batch_no=?, date=?, status=?, tags=?, variables=?, conclusion=?, notes=?, searchable_metrics=? WHERE id=?''',
            (safe_data['project'], safe_data['title'], safe_data['batch_no'], safe_data['date'], safe_data['status'], safe_data['tags'], safe_data['variables'], safe_data['conclusion'], safe_data['notes'], mj, cid), fetch=False)
    else:
        cid = run_query('''INSERT INTO experiments (project, title, batch_no, date, status, tags, variables, conclusion, notes, searchable_metrics) VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (safe_data['project'], safe_data['title'], safe_data['batch_no'], safe_data['date'], safe_data['status'], safe_data['tags'], safe_data['variables'], safe_data['conclusion'], safe_data['notes'], mj), fetch=False)

    if files:
  
