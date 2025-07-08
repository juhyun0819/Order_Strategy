import sqlite3
import os
import pandas as pd
import re
from datetime import datetime

def extract_date_from_filename(filename):
    """파일명에서 날짜 추출"""
    pattern = r'(\d{2})\.(\d{2})\.(\d{2})'
    match = re.search(pattern, filename)
    if match:
        year, month, day = match.groups()
        full_year = f"20{year}"
        return f"{full_year}-{month}-{day}"
    else:
        return datetime.now().strftime('%Y-%m-%d')

def init_db():
    """데이터베이스 초기화"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_date TEXT,
            품명 TEXT,
            칼라 TEXT,
            사이즈 TEXT,
            실판매 INTEGER,
            현재고 INTEGER,
            미송잔량 INTEGER,
            판매일자 TEXT
        )
    ''')
    conn.commit()
    conn.close()

def reset_db():
    """데이터베이스 초기화 (모든 데이터 삭제)"""
    if os.path.exists('inventory.db'):
        os.remove('inventory.db')
    init_db()

def save_to_db(df, upload_date, filename):
    """데이터프레임을 데이터베이스에 저장"""
    conn = sqlite3.connect('inventory.db')
    sales_date = extract_date_from_filename(filename)
    df['upload_date'] = upload_date
    df['판매일자'] = sales_date
    # 실판매가 0인 행은 저장하지 않음
    df = df[df['실판매'] != 0]
    if not df.empty:
        df.to_sql('sales_data', conn, if_exists='append', index=False)
    conn.close()

def load_from_db():
    """데이터베이스에서 모든 데이터 로드"""
    conn = sqlite3.connect('inventory.db')
    df = pd.read_sql_query("SELECT * FROM sales_data", conn)
    conn.close()
    return df

def delete_by_date(date):
    """특정 날짜의 데이터 삭제"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales_data WHERE 판매일자 = ?", (date,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count 