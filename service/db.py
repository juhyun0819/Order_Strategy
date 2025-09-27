import sqlite3
import os
import pandas as pd
import re
from datetime import datetime

def extract_date_from_filename(filename):
    """파일명에서 날짜 추출 (괄호나 다른 문자가 있어도 날짜 부분만 추출)"""
    # YY.MM.DD 형식의 날짜 패턴을 찾되, 뒤에 괄호나 다른 문자가 있어도 매칭
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
            filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 파레토 선택 기준 일수 테이블 추가
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pareto_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            days INTEGER DEFAULT 365,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 기본값 삽입 (없는 경우에만)
    cursor.execute('''
        INSERT OR IGNORE INTO pareto_settings (id, days) VALUES (1, 365)
    ''')
    
    conn.commit()
    conn.close()

def reset_db():
    """데이터베이스 초기화 (모든 데이터 삭제)"""
    if os.path.exists('inventory.db'):
        os.remove('inventory.db')
    init_db()

def save_to_db(df, upload_date, filename):
    """데이터프레임을 데이터베이스에 저장 (동일 제목 파일 업로드 시 기존 데이터 교체)"""
    conn = sqlite3.connect('inventory.db')
    sales_date = extract_date_from_filename(filename)
    df['upload_date'] = upload_date
    df['판매일자'] = sales_date
    # 실판매가 0인 행은 저장하지 않음
    df = df[df['실판매'] != 0]
    if not df.empty:
        # 기존 데이터 삭제 (판매일자 기준)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sales_data WHERE 판매일자 = ?", (sales_date,))
        conn.commit()
        # 새 데이터 저장
        df.to_sql('sales_data', conn, if_exists='append', index=False)
    conn.close()

def save_compare_product(product_name, compare_df, upload_date, filename=None):
    """비교 상품 데이터를 데이터베이스에 저장"""
    import json
    import pandas as pd
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # 기존 데이터가 있으면 삭제
    cursor.execute('DELETE FROM compare_products WHERE product_name = ?', (product_name,))
    
    # 날짜 컬럼 찾기
    date_col = None
    for col in compare_df.columns:
        if any(keyword in str(col).lower() for keyword in ['거래일자', '판매일자', '날짜', 'date']):
            date_col = col
            break
    
    if date_col:
        print(f"저장 전 날짜 컬럼 '{date_col}' 샘플: {compare_df[date_col].head().tolist()}")
        
        # 날짜를 올바른 형태로 변환
        try:
            # 먼저 일반적인 날짜 형식으로 시도
            compare_df[date_col] = pd.to_datetime(compare_df[date_col], errors='coerce')
            
            # 변환된 날짜가 모두 NaT이거나 1970년 이전이면 Unix timestamp로 재시도
            if compare_df[date_col].isna().all() or compare_df[date_col].dt.year.min() < 2000:
                print("저장 시 Unix timestamp로 변환 시도")
                # 원본 데이터로 다시 시도
                original_dates = compare_df[date_col].copy()
                compare_df[date_col] = pd.to_datetime(original_dates, unit='ms', errors='coerce')
                
                # 여전히 문제가 있으면 다른 단위들도 시도
                if compare_df[date_col].isna().all() or compare_df[date_col].dt.year.min() < 2000:
                    print("저장 시 마이크로초 단위로 시도")
                    compare_df[date_col] = pd.to_datetime(original_dates, unit='us', errors='coerce')
                
                if compare_df[date_col].isna().all() or compare_df[date_col].dt.year.min() < 2000:
                    print("저장 시 나노초 단위로 시도")
                    compare_df[date_col] = pd.to_datetime(original_dates, unit='ns', errors='coerce')
            
            # 날짜를 ISO 형식 문자열로 변환하여 저장
            compare_df[date_col] = compare_df[date_col].dt.strftime('%Y-%m-%d')
            
            print(f"저장 시 변환된 날짜 샘플: {compare_df[date_col].head().tolist()}")
            
        except Exception as e:
            print(f"저장 시 날짜 변환 중 오류: {e}")
    
    # 새로운 데이터 저장
    compare_data_json = compare_df.to_json(orient='records')
    cursor.execute('''
        INSERT INTO compare_products (product_name, compare_data, upload_date, filename)
        VALUES (?, ?, ?, ?)
    ''', (product_name, compare_data_json, upload_date, filename))
    
    conn.commit()
    conn.close()

def load_compare_product(product_name):
    """특정 상품의 비교 상품 데이터를 데이터베이스에서 불러오기 (파일명 포함)"""
    import json
    import pandas as pd
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT compare_data, filename FROM compare_products WHERE product_name = ? ORDER BY created_at DESC LIMIT 1', (product_name,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        try:
            compare_data_json, filename = result
            from io import StringIO
            compare_df = pd.read_json(StringIO(compare_data_json), orient='records')
            
            # 날짜 컬럼 확인 (이미 올바른 형태로 저장되어 있음)
            date_cols = [col for col in compare_df.columns if any(keyword in str(col).lower() for keyword in ['거래일자', '판매일자', '날짜', 'date'])]
            if date_cols:
                print(f"로드 후 날짜 컬럼 '{date_cols[0]}' 샘플: {compare_df[date_cols[0]].head().tolist()}")
                # 이미 문자열 형태로 저장되어 있으므로 바로 datetime으로 변환
                compare_df[date_cols[0]] = pd.to_datetime(compare_df[date_cols[0]], errors='coerce')
                print(f"날짜 변환 후 샘플: {compare_df[date_cols[0]].head().tolist()}")
            
            return compare_df, filename
        except Exception as e:
            print(f"비교 상품 데이터 로드 중 오류: {e}")
            return None, None
    else:
        return None, None

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
    
    # 디버깅: 현재 데이터베이스에 있는 날짜들 확인
    cursor.execute("SELECT DISTINCT 판매일자 FROM sales_data")
    existing_dates = [row[0] for row in cursor.fetchall()]
    print(f"삭제 요청 날짜: {date}")
    print(f"데이터베이스에 있는 날짜들: {existing_dates}")
    
    cursor.execute("DELETE FROM sales_data WHERE 판매일자 = ?", (date,))
    deleted_count = cursor.rowcount
    print(f"삭제된 행 수: {deleted_count}")
    
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

def reset_compare_products():
    """비교 상품 데이터 전체 삭제"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM compare_products')
    conn.commit()
    conn.close()

def set_pareto_days(days):
    """파레토 선택 기준 일수 저장"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pareto_settings SET days = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1
    ''', (days,))
    conn.commit()
    conn.close()

def get_pareto_days():
    """파레토 선택 기준 일수 불러오기"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute('SELECT days FROM pareto_settings WHERE id = 1')
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 365 