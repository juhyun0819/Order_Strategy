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
    
    # 비교 상품 데이터 테이블 추가
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compare_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            compare_data TEXT NOT NULL,
            upload_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

def save_compare_product(product_name, compare_df, upload_date):
    """비교 상품 데이터를 데이터베이스에 저장"""
    import json
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # 기존 데이터가 있으면 삭제
    cursor.execute('DELETE FROM compare_products WHERE product_name = ?', (product_name,))
    
    # 새로운 데이터 저장
    compare_data_json = compare_df.to_json(orient='records')
    cursor.execute('''
        INSERT INTO compare_products (product_name, compare_data, upload_date)
        VALUES (?, ?, ?)
    ''', (product_name, compare_data_json, upload_date))
    
    conn.commit()
    conn.close()

def load_compare_product(product_name):
    """특정 상품의 비교 상품 데이터를 데이터베이스에서 불러오기"""
    import json
    import pandas as pd
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT compare_data FROM compare_products WHERE product_name = ? ORDER BY created_at DESC LIMIT 1', (product_name,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        try:
            compare_data_json = result[0]
            compare_df = pd.read_json(compare_data_json, orient='records')
            return compare_df
        except Exception as e:
            print(f"비교 상품 데이터 로드 중 오류: {e}")
            return None
    else:
        return None

def delete_compare_product(product_name):
    """특정 상품의 비교 상품 데이터를 데이터베이스에서 삭제"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM compare_products WHERE product_name = ?', (product_name,))
    
    conn.commit()
    conn.close()

def check_compare_product_exists(product_name):
    """특정 상품의 비교 상품 데이터가 존재하는지 확인"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM compare_products WHERE product_name = ?', (product_name,))
    count = cursor.fetchone()[0]
    
    conn.close()
    return count > 0

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

def init_clients_table():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS pareto_clients (
            product TEXT PRIMARY KEY,
            client_count INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def set_client_count(product, count):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('REPLACE INTO pareto_clients (product, client_count) VALUES (?, ?)', (product, count))
    conn.commit()
    conn.close()

def get_client_counts():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT product, client_count FROM pareto_clients')
    data = dict(c.fetchall())
    conn.close()
    return data

# 주차별 거래처 수 관련 함수들
def init_weekly_clients_table():
    """주차별 거래처 수 테이블 초기화"""
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS weekly_clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT,
            year INTEGER,
            week INTEGER,
            client_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product, year, week)
        )
    ''')
    conn.commit()
    conn.close()

def set_weekly_client_count(product, year, week, count):
    """주차별 거래처 수 저장/업데이트"""
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO weekly_clients (product, year, week, client_count, created_at) 
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (product, year, week, count))
    conn.commit()
    conn.close()

def get_weekly_client_counts(product, year):
    """특정 상품의 연도별 주차 거래처 수 조회"""
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        SELECT week, client_count FROM weekly_clients 
        WHERE product = ? AND year = ? 
        ORDER BY week
    ''', (product, year))
    data = dict(c.fetchall())
    conn.close()
    return data

def get_current_week_client_count(product):
    """현재 주차의 거래처 수 조회"""
    from datetime import datetime
    current_date = datetime.now()
    year = current_date.year
    week = current_date.isocalendar()[1]
    
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        SELECT client_count FROM weekly_clients 
        WHERE product = ? AND year = ? AND week = ?
    ''', (product, year, week))
    result = c.fetchone()
    conn.close()
    
    return result[0] if result else None 