# -*- coding: utf-8 -*-
# 여성복 의류 도매 재고 관리 및 판매 분석 시스템

from flask import Flask, request, render_template, jsonify, flash, redirect, url_for, send_file
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import warnings
import re
import os
from rapidfuzz import process
warnings.filterwarnings('ignore')
from matplotlib.ticker import MaxNLocator

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

def extract_date_from_filename(filename):
    pattern = r'(\d{2})\.(\d{2})\.(\d{2})'
    match = re.search(pattern, filename)
    if match:
        year, month, day = match.groups()
        full_year = f"20{year}"
        return f"{full_year}-{month}-{day}"
    else:
        return datetime.now().strftime('%Y-%m-%d')

def init_db():
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
    if os.path.exists('inventory.db'):
        os.remove('inventory.db')
    init_db()

def save_to_db(df, upload_date, filename):
    conn = sqlite3.connect('inventory.db')
    sales_date = extract_date_from_filename(filename)
    df['upload_date'] = upload_date
    df['판매일자'] = sales_date
    df.to_sql('sales_data', conn, if_exists='append', index=False)
    conn.close()

def load_from_db():
    conn = sqlite3.connect('inventory.db')
    df = pd.read_sql_query("SELECT * FROM sales_data", conn)
    conn.close()
    return df

def delete_by_date(date):
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales_data WHERE 판매일자 = ?", (date,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count

def pareto_analysis(df):
    product_sales = df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
    total_sales = product_sales.sum()
    cumulative_percentage = (product_sales.cumsum() / total_sales * 100)
    top_20_products = cumulative_percentage[cumulative_percentage <= 20].index.tolist()
    return top_20_products, product_sales, cumulative_percentage

def weekly_analysis(df):
    df['판매일자'] = pd.to_datetime(df['판매일자'])
    df['주차'] = df['판매일자'].dt.isocalendar().week
    df['요일'] = df['판매일자'].dt.day_name()
    weekly_sales = df.groupby(['주차', '요일'])['실판매'].sum().reset_index()
    return weekly_sales

def recent_7days_analysis(df):
    """최근 7일간 업로드된 데이터 분석"""
    df['판매일자'] = pd.to_datetime(df['판매일자'])
    
    # 최근 7일 데이터만 필터링
    latest_date = df['판매일자'].max()
    seven_days_ago = latest_date - timedelta(days=6)
    recent_df = df[df['판매일자'] >= seven_days_ago].copy()
    
    if recent_df.empty:
        return None, None
    
    # 일별 판매량
    daily_sales = recent_df.groupby('판매일자')['실판매'].sum().reset_index()
    daily_sales = daily_sales.sort_values('판매일자')
    
    # 요일별 판매량 (최근 7일 기준)
    recent_df['요일'] = recent_df['판매일자'].dt.day_name()
    day_sales = recent_df.groupby('요일')['실판매'].sum().reset_index()
    
    return daily_sales, day_sales

def generate_inventory_alerts(df):
    alert_rows = []
    plot_products = []
    
    for prod in df['품명'].unique():
        sub = df[df['품명'] == prod].sort_values('판매일자')
        if len(sub) >= 2:
            sales = sub['실판매'].astype(float).values
            if np.ptp(sales) > 0:
                plot_products.append(prod)
    
    for prod in plot_products:
        sub = df[df['품명'] == prod].sort_values('판매일자')
        if sub.empty or '실판매' not in sub.columns or '현재고' not in sub.columns:
            continue
        sales = sub['실판매'].astype(float).values
        if len(sales) < 2:
            continue
        x = np.arange(len(sales))
        high_trend = np.poly1d(np.polyfit(x, pd.Series(sales).rolling(7, min_periods=1).max(), 1))(x)
        low_trend = np.poly1d(np.polyfit(x, pd.Series(sales).rolling(7, min_periods=1).min(), 1))(x)
        mid_trend = (high_trend + low_trend) / 2
        mid_pred = float(mid_trend[-1])
        cur_stock = sub['현재고'].iloc[-1]
        try:
            cur_stock = float(cur_stock)
        except:
            cur_stock = 0
        lack = max(0, int(round(mid_pred - cur_stock)))
        order_suggestion = f"{lack}개 발주 필요" if lack > 0 else "충분"
        if len(sales) >= 3:
            recent_trend = np.mean(sales[-3:]) - np.mean(sales[-6:-3]) if len(sales) >= 6 else sales[-1] - sales[0]
            if recent_trend > 0:
                trend = '증가'
            elif recent_trend < 0:
                trend = '감소'
            else:
                trend = '유지'
        else:
            trend = '유지'
        sub['판매일자'] = pd.to_datetime(sub['판매일자'])
        last_date = sub['판매일자'].max()
        # 최근 7일 평균 판매량 기준 소진예상일 계산
        recent7 = sub[sub['판매일자'] >= last_date - pd.Timedelta(days=6)]
        avg7 = recent7['실판매'].mean() if not recent7.empty else 0.0
        if avg7 > 0:
            days_left = cur_stock / avg7
        else:
            days_left = np.inf
        if days_left <= 3:
            alert_level = '위험'
        elif days_left <= 7:
            alert_level = '주의'
        else:
            alert_level = '안정'
        alert_rows.append({
            '날짜': str(last_date.date()),
            '상품명': prod,
            '최근 판매 경향': trend,
            '중간선': int(round(mid_pred)),
            '현재고': int(round(cur_stock)),
            '부족수량': lack,
            '발주제안': order_suggestion,
            '소진예상일': round(days_left, 1) if days_left != np.inf else '-',
            '경고등급': alert_level
        })
    return alert_rows

def generate_a_grade_alerts(df):
    # 파레토 A급 + 소진임박(7일 이하) 상품만 추출
    top_20_products, product_sales, cumulative_percentage = pareto_analysis(df)
    total_sales = product_sales.sum()
    cum_perc = (product_sales.cumsum() / total_sales * 100)
    a_grade = cum_perc[cum_perc <= 80].index.tolist()
    alert_rows = []
    for prod in a_grade:
        sub = df[df['품명'] == prod].sort_values('판매일자')
        if sub.empty or '실판매' not in sub.columns or '현재고' not in sub.columns:
            continue
        sub['판매일자'] = pd.to_datetime(sub['판매일자'])
        last_date = sub['판매일자'].max()
        cur_stock = sub['현재고'].iloc[-1]
        try:
            cur_stock = float(cur_stock)
        except:
            cur_stock = 0
        recent7 = sub[sub['판매일자'] >= last_date - pd.Timedelta(days=6)]
        avg7 = recent7['실판매'].mean() if not recent7.empty else 0.0
        if avg7 > 0:
            days_left = cur_stock / avg7
        else:
            days_left = np.inf
        if days_left <= 7:
            alert_rows.append({
                '날짜': str(last_date.date()),
                '상품명': prod,
                '현재고': int(round(cur_stock)),
                '최근7일평균판매': round(avg7, 1),
                '소진예상일': round(days_left, 1) if days_left != np.inf else '-',
            })
    return alert_rows

def search_products(query, products):
    if not query:
        return products
    matches = process.extract(query, products, limit=10, scorer=process.fuzz.WRatio)
    return [m[0] for m in matches if m[1] >= 60]

@app.route('/', methods=['GET', 'POST'])
def root():
    return redirect(url_for('dashboard'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    # 파일 업로드 처리 (POST)
    if request.method == 'POST':
        files = request.files.getlist('files')
        uploaded_count = 0
        for file in files:
            if file and file.filename.endswith(('xls', 'xlsx')):
                try:
                    df = pd.read_excel(file)
                    required_cols = {'품명', '칼라', '사이즈', '실판매', '현재고', '미송잔량'}
                    if not required_cols.issubset(df.columns):
                        flash(f'파일 {file.filename}: 필수 컬럼이 누락되었습니다.', 'error')
                        continue
                    upload_date = datetime.now().strftime('%Y-%m-%d')
                    df = df.iloc[:-1]  # 마지막 행 제거
                    save_to_db(df, upload_date, file.filename)
                    sales_date = extract_date_from_filename(file.filename)
                    flash(f'파일 {file.filename} 업로드 완료! (판매일자: {sales_date})', 'success')
                    uploaded_count += 1
                except Exception as e:
                    flash(f'파일 {file.filename} 처리 중 오류: {str(e)}', 'error')
        if uploaded_count > 0:
            flash(f'{uploaded_count}개 파일이 성공적으로 업로드되었습니다!', 'success')
        elif not files or all(not file.filename for file in files):
            flash('파일을 선택해주세요.', 'error')
        # POST 처리 후 반드시 redirect
        return redirect(url_for('dashboard'))
    # 대시보드 렌더링 (GET)
    df = load_from_db()
    product_list = sorted(df['품명'].unique()) if not df.empty else []
    all_dates = sorted(pd.to_datetime(df['판매일자']).unique()) if not df.empty else []
    selected_product = request.args.get('product')
    search_query = request.args.get('search', '')
    if selected_product and selected_product in product_list:
        filtered_df = df[df['품명'] == selected_product]
        stats = {
            'total_items': len(filtered_df),
            'total_sales': filtered_df['실판매'].sum(),
            'total_inventory': filtered_df['현재고'].sum(),
            'total_pending': filtered_df['미송잔량'].sum(),
            'unique_products': filtered_df['품명'].nunique(),
            'unique_colors': filtered_df['칼라'].nunique(),
            'unique_sizes': filtered_df['사이즈'].nunique(),
            'avg_daily_sales': filtered_df.groupby('판매일자')['실판매'].sum().mean(),
            'upload_dates': filtered_df['upload_date'].nunique(),
            'sales_dates': filtered_df['판매일자'].nunique()
        }
        plots = create_visualizations(filtered_df, only_product=True, all_dates=all_dates)
        alert_df = None
        a_grade_alert_df = None
    else:
        filtered_df = df
        stats = {
            'total_items': len(filtered_df),
            'total_sales': filtered_df['실판매'].sum(),
            'total_inventory': filtered_df['현재고'].sum(),
            'total_pending': filtered_df['미송잔량'].sum(),
            'unique_products': filtered_df['품명'].nunique(),
            'unique_colors': filtered_df['칼라'].nunique(),
            'unique_sizes': filtered_df['사이즈'].nunique(),
            'avg_daily_sales': filtered_df.groupby('판매일자')['실판매'].sum().mean(),
            'upload_dates': filtered_df['upload_date'].nunique(),
            'sales_dates': filtered_df['판매일자'].nunique()
        }
        plots = create_visualizations(filtered_df)
        alert_rows = generate_inventory_alerts(df)
        alert_df = pd.DataFrame(alert_rows) if alert_rows else None
        a_grade_alert_rows = generate_a_grade_alerts(df)
        a_grade_alert_df = pd.DataFrame(a_grade_alert_rows) if a_grade_alert_rows else None
    # 작년 연도 계산
    last_year = None
    if not df.empty:
        df['판매일자'] = pd.to_datetime(df['판매일자'])
        last_year = df['판매일자'].dt.year.max() - 1
    
    # unique_dates 계산 (날짜별 데이터 삭제용)
    unique_dates = []
    if not df.empty:
        unique_dates = sorted(df['판매일자'].unique())
    
    return render_template('dashboard.html',
        plots=plots, stats=stats, product_list=product_list,
        selected_product=selected_product, alert_df=alert_df, a_grade_alert_df=a_grade_alert_df, 
        search_query=search_query, last_year=last_year, unique_dates=unique_dates)

@app.route('/delete-date', methods=['POST'])
def delete_date():
    date_to_delete = request.form.get('date')
    if date_to_delete:
        deleted = delete_by_date(date_to_delete)
        if deleted > 0:
            flash(f'{date_to_delete} 데이터 {deleted}건 삭제 완료!', 'success')
        else:
            flash('삭제할 데이터가 없습니다.', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/reset-db')
def reset_database():
    try:
        reset_db()
        flash('데이터베이스가 성공적으로 초기화되었습니다.', 'success')
    except Exception as e:
        flash(f'데이터베이스 초기화 중 오류가 발생했습니다: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

def create_visualizations(df, only_product=False, all_dates=None):
    plots = {}
    # 1. 전체 판매 트렌드
    if only_product and all_dates is not None and len(all_dates) > 0:
        df = df.copy()
        df['판매일자'] = pd.to_datetime(df['판매일자'])
        idx = pd.to_datetime(all_dates)
        daily_sales = df.groupby('판매일자')['실판매'].sum()
        daily_sales = daily_sales.reindex(idx, fill_value=0).reset_index()
        daily_sales.columns = ['판매일자', '실판매']
    else:
        df = df.copy()
        df['판매일자'] = pd.to_datetime(df['판매일자'])
        
        # 현재 연도의 데이터만 필터링
        current_year = datetime.now().year
        df_current_year = df[df['판매일자'].dt.year == current_year]
        
        if not df_current_year.empty:
            daily_sales = df_current_year.groupby('판매일자')['실판매'].sum().reset_index()
            daily_sales['판매일자'] = pd.to_datetime(daily_sales['판매일자'])
            daily_sales = daily_sales.sort_values('판매일자')
            
            # 현재 연도의 1월 1일부터 마지막 데이터까지 생성
            start_date = pd.Timestamp(f'{current_year}-01-01')
            end_date = daily_sales['판매일자'].max()
            full_date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # 전체 날짜 범위에 대해 데이터 재인덱싱
            daily_sales = daily_sales.set_index('판매일자').reindex(full_date_range, fill_value=0).reset_index()
            daily_sales.columns = ['판매일자', '실판매']
        else:
            # 현재 연도 데이터가 없으면 빈 데이터프레임 생성
            daily_sales = pd.DataFrame({'판매일자': [], '실판매': []})
    
    fig1, ax1 = plt.subplots(figsize=(8, 4.5), facecolor='#f5f7fa')
    ax1.set_facecolor('#f5f7fa')
    x = np.arange(len(daily_sales))
    sales = daily_sales['실판매'].values
    # rolling min/max
    roll_min = pd.Series(sales).rolling(7, min_periods=1).min()
    roll_max = pd.Series(sales).rolling(7, min_periods=1).max()
    # 1차 회귀선
    low_trend = np.poly1d(np.polyfit(x, roll_min, 1))(x)
    high_trend = np.poly1d(np.polyfit(x, roll_max, 1))(x)
    mid_trend = (low_trend + high_trend) / 2
    # 그래프
    ax1.plot(daily_sales['판매일자'], sales, marker='o', markersize=3, linewidth=1, label='실판매')
    ax1.plot(daily_sales['판매일자'], low_trend, '--', color='blue', linewidth=1, label='저점 추세')
    ax1.plot(daily_sales['판매일자'], high_trend, '--', color='green', linewidth=1, label='고점 추세')
    ax1.plot(daily_sales['판매일자'], mid_trend, '--', color='red', linewidth=1, label='중위 추세')
    ax1.set_xlabel('월')
    ax1.set_ylabel('판매량')
    ax1.grid(True, alpha=0.3)
    
    # x축 레이블 간소화 (월별로만 표시)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.xticks(rotation=0)
    
    # x축 범위를 1월부터 12월까지로 설정
    if not daily_sales.empty:
        ax1.set_xlim(pd.Timestamp(f'{current_year}-01-01'), pd.Timestamp(f'{current_year}-12-31'))
    ax1.legend()
    plt.tight_layout(pad=0)
    img1 = io.BytesIO()
    plt.savefig(img1, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
    img1.seek(0)
    plots['sales_trend'] = base64.b64encode(img1.getvalue()).decode()
    plt.close()
    # 상품별 실판매 집계 (only_product=False일 때만)
    if not only_product and '품명' in df.columns and '실판매' in df.columns:
        fig2, ax2 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
        prod_sales = df.groupby('품명')['실판매'].sum().sort_values(ascending=False).head(10)
        ax2.set_facecolor('#f5f7fa')
        ax2.bar(range(len(prod_sales)), prod_sales.values, color='skyblue')
        ax2.set_xlabel('품명')
        ax2.set_ylabel('실판매')
        ax2.set_xticks(range(len(prod_sales)))
        ax2.set_xticklabels(prod_sales.index, rotation=45, ha='right')
        plt.tight_layout(pad=0)
        img2 = io.BytesIO()
        plt.savefig(img2, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img2.seek(0)
        plots['product_sales'] = base64.b64encode(img2.getvalue()).decode()
        plt.close()
    # 컬러별 실판매 집계
    if '칼라' in df.columns and '실판매' in df.columns:
        fig3, ax3 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
        color_sales = df.groupby('칼라')['실판매'].sum().sort_values(ascending=False).head(10)
        ax3.set_facecolor('#f5f7fa')
        ax3.bar(range(len(color_sales)), color_sales.values, color='lightcoral')
        ax3.set_xlabel('컬러')
        ax3.set_ylabel('실판매')
        ax3.set_xticks(range(len(color_sales)))
        ax3.set_xticklabels(color_sales.index, rotation=45, ha='right')
        plt.tight_layout(pad=0)
        img3 = io.BytesIO()
        plt.savefig(img3, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img3.seek(0)
        plots['color_sales'] = base64.b64encode(img3.getvalue()).decode()
        plt.close()
    # 사이즈별 실판매 집계
    if '사이즈' in df.columns and '실판매' in df.columns:
        fig4, ax4 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
        size_sales = df.groupby('사이즈')['실판매'].sum().sort_values(ascending=False)
        ax4.set_facecolor('#f5f7fa')
        ax4.bar(range(len(size_sales)), size_sales.values, color='lightgreen')
        ax4.set_xlabel('사이즈')
        ax4.set_ylabel('실판매')
        ax4.set_xticks(range(len(size_sales)))
        ax4.set_xticklabels(size_sales.index, rotation=45, ha='right')
        plt.tight_layout(pad=0)
        img4 = io.BytesIO()
        plt.savefig(img4, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img4.seek(0)
        plots['size_sales'] = base64.b64encode(img4.getvalue()).decode()
        plt.close()
    # 파레토 분석 (only_product=False일 때만)
    if not only_product:
        top_20_products, product_sales, cumulative_percentage = pareto_analysis(df)
        fig5, (ax5a, ax5b) = plt.subplots(1, 2, figsize=(9, 4.5), facecolor='#f5f7fa')
        top_10 = product_sales.head(10)
        ax5a.set_facecolor('#f5f7fa')
        ax5a.bar(range(len(top_10)), top_10.values, color='skyblue')
        ax5a.set_xlabel('제품')
        ax5a.set_ylabel('판매량')
        ax5a.set_xticks(range(len(top_10)))
        ax5a.set_xticklabels(top_10.index, rotation=45, ha='right')
        ax5b.set_facecolor('#f5f7fa')
        ax5b.plot(range(len(cumulative_percentage)), cumulative_percentage, 'b-', linewidth=2)
        ax5b.axhline(y=20, color='r', linestyle='--', alpha=0.7, label='20% 기준선')
        ax5b.set_xlabel('제품 수')
        ax5b.set_ylabel('누적 판매 비율 (%)')
        ax5b.legend()
        ax5b.grid(True, alpha=0.3)
        plt.tight_layout(pad=0)
        img5 = io.BytesIO()
        plt.savefig(img5, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img5.seek(0)
        plots['pareto_analysis'] = base64.b64encode(img5.getvalue()).decode()
        plt.close()
    # 최근 7일 요일별/일별 판매 분석은 항상 생성
    daily_sales, day_sales = recent_7days_analysis(df)
    if day_sales is not None and not day_sales.empty:
        fig6, ax6 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_sales_reindexed = day_sales.groupby('요일')['실판매'].sum().reindex(day_order)
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
        ax6.set_facecolor('#f5f7fa')
        bars = ax6.bar(range(len(day_sales_reindexed)), day_sales_reindexed.values, color=colors)
        ax6.set_xlabel('요일')
        ax6.set_ylabel('판매량')
        ax6.set_xticks(range(len(day_sales_reindexed)))
        ax6.set_xticklabels(['월', '화', '수', '목', '금', '토', '일'])
        for bar, value in zip(bars, day_sales_reindexed.values):
            if not pd.isna(value):
                ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01*max(day_sales_reindexed.values),
                        f'{value:,}', ha='center', va='bottom', fontweight='bold')
        plt.tight_layout(pad=0)
        img6 = io.BytesIO()
        plt.savefig(img6, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img6.seek(0)
        plots['daily_sales'] = base64.b64encode(img6.getvalue()).decode()
        plt.close()
    if daily_sales is not None and not daily_sales.empty:
        fig7, ax7 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
        ax7.set_facecolor('#f5f7fa')
        ax7.plot(daily_sales['판매일자'], daily_sales['실판매'], marker='o', linewidth=2, markersize=6)
        ax7.set_xlabel('날짜')
        ax7.set_ylabel('판매량')
        ax7.grid(True, alpha=0.3)
        ax7.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        plt.xticks(rotation=45)
        plt.tight_layout(pad=0)
        img7 = io.BytesIO()
        plt.savefig(img7, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img7.seek(0)
        plots['weekly_sales'] = base64.b64encode(img7.getvalue()).decode()
        plt.close()
    
    # 주별 판매량 그래프 (2025년 데이터만)
    if not df.empty:
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        
        # 현재 연도의 데이터만 필터링
        current_year = datetime.now().year
        df_current_year = df_copy[df_copy['판매일자'].dt.year == current_year]
        
        if not df_current_year.empty:
            # 주별 판매량 계산
            df_current_year['주차'] = df_current_year['판매일자'].dt.isocalendar().week
            weekly_sales = df_current_year.groupby('주차')['실판매'].sum().reset_index()
            weekly_sales = weekly_sales.sort_values('주차')
            
            # 마지막 데이터가 있는 주차까지만 선 그래프를 그림
            last_week = weekly_sales[weekly_sales['실판매'] > 0]['주차'].max() if (weekly_sales['실판매'] > 0).any() else 1
            fig8, ax8 = plt.subplots(figsize=(8, 4.5), facecolor='#f5f7fa')
            ax8.set_facecolor('#f5f7fa')
            # 선 그래프는 마지막 데이터가 있는 주차까지만
            ax8.plot(weekly_sales['주차'][:last_week], weekly_sales['실판매'][:last_week], marker='o', linewidth=2, markersize=4, color='#4ECDC4')
            ax8.set_xlabel('월')
            ax8.set_ylabel('판매량')
            # x축을 월별로 표시 (1월부터 12월까지)
            month_ticks = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45]
            month_labels = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']
            ax8.set_xticks(month_ticks)
            ax8.set_xticklabels(month_labels, rotation=0)
            ax8.grid(True, alpha=0.3)
            plt.tight_layout(pad=0)
            img8 = io.BytesIO()
            plt.savefig(img8, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img8.seek(0)
            plots['weekly_sales_chart'] = base64.b64encode(img8.getvalue()).decode()
            plt.close()
        else:
            # 현재 연도 데이터가 없으면 빈 그래프 생성
            fig8, ax8 = plt.subplots(figsize=(8, 4.5), facecolor='#f5f7fa')
            ax8.set_facecolor('#f5f7fa')
            ax8.text(0.5, 0.5, f'{current_year}년 데이터가 없습니다', ha='center', va='center', transform=ax8.transAxes, fontsize=12)
            ax8.set_xlabel('월')
            ax8.set_ylabel('판매량')
            ax8.grid(True, alpha=0.3)
            plt.tight_layout(pad=0)
            img8 = io.BytesIO()
            plt.savefig(img8, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img8.seek(0)
            plots['weekly_sales_chart'] = base64.b64encode(img8.getvalue()).decode()
            plt.close()
    
    # 전년도 데이터만 추출
    if not df.empty:
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        max_year = df_copy['판매일자'].dt.year.max()
        last_year = max_year - 1
        lastyear_df = df_copy[df_copy['판매일자'].dt.year == last_year]
        # 1. 전년도 일별 판매 트렌드 (실판매 + 중위 추세선)
        if not lastyear_df.empty:
            # 1월 1일~12월 31일까지 전체 날짜 생성
            start_date = pd.Timestamp(f'{last_year}-01-01')
            end_date = pd.Timestamp(f'{last_year}-12-31')
            full_date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            lastyear_daily = lastyear_df.groupby('판매일자')['실판매'].sum().reset_index()
            lastyear_daily = lastyear_daily.set_index('판매일자').reindex(full_date_range, fill_value=0).reset_index()
            lastyear_daily.columns = ['판매일자', '실판매']
            x = np.arange(len(lastyear_daily))
            sales = lastyear_daily['실판매'].values
            roll_min = pd.Series(sales).rolling(7, min_periods=1).min()
            roll_max = pd.Series(sales).rolling(7, min_periods=1).max()
            low_trend = np.poly1d(np.polyfit(x, roll_min, 1))(x)
            high_trend = np.poly1d(np.polyfit(x, roll_max, 1))(x)
            mid_trend = (low_trend + high_trend) / 2
            fig9, ax9 = plt.subplots(figsize=(6, 4), facecolor='#f5f7fa')
            ax9.set_facecolor('#f5f7fa')
            ax9.plot(lastyear_daily['판매일자'], sales, marker='o', linewidth=2, markersize=4, color='#FF6B6B', label='실판매')
            ax9.plot(lastyear_daily['판매일자'], mid_trend, '--', color='red', linewidth=2, label='중위 추세')
            ax9.set_xlabel('월월')
            ax9.set_ylabel('판매량')
            ax9.legend()
            ax9.grid(True, alpha=0.3)
            # x축을 월별로만 표시
            ax9.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
            ax9.xaxis.set_major_formatter(mdates.DateFormatter('%m'))
            plt.xticks(rotation=0)
            plt.tight_layout(pad=0)
            img9 = io.BytesIO()
            plt.savefig(img9, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img9.seek(0)
            plots['lastyear_daily_trend'] = base64.b64encode(img9.getvalue()).decode()
            plt.close()
            # 2. 전년도 주별 판매 트렌드
            lastyear_df['주차'] = lastyear_df['판매일자'].dt.isocalendar().week
            weekly_sales = lastyear_df.groupby('주차')['실판매'].sum().reset_index()
            # 1~52주 전체 생성, 없는 주차는 0
            full_weeks = pd.DataFrame({'주차': range(1, 53)})
            weekly_sales = weekly_sales.merge(full_weeks, on='주차', how='right').fillna(0)
            weekly_sales = weekly_sales.sort_values('주차')
            fig10, ax10 = plt.subplots(figsize=(6, 4), facecolor='#f5f7fa')
            ax10.set_facecolor('#f5f7fa')
            ax10.plot(weekly_sales['주차'], weekly_sales['실판매'], marker='o', linewidth=2, markersize=4, color='#4ECDC4')
            ax10.set_xlabel('월')
            ax10.set_ylabel('판매량')
            # x축을 월별로 표시 (1월~12월)
            month_ticks = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45]
            month_labels = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']
            ax10.set_xticks(month_ticks)
            ax10.set_xticklabels(month_labels, rotation=0)
            ax10.grid(True, alpha=0.3)
            plt.tight_layout(pad=0)
            img10 = io.BytesIO()
            plt.savefig(img10, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img10.seek(0)
            plots['lastyear_weekly_trend'] = base64.b64encode(img10.getvalue()).decode()
            plt.close()
            # 3. 예측값 계산 (그래프X, 표로만 전달)
            slope, intercept = np.polyfit(x, mid_trend, 1)
            forecast_x = np.arange(len(lastyear_daily), len(lastyear_daily) + 7)
            forecast_dates = pd.date_range(start=lastyear_daily['판매일자'].iloc[-1] + timedelta(days=1), periods=7)
            forecast_values = [int(round(slope * xi + intercept)) for xi in forecast_x]
            # 신뢰도 계산
            recent_n = min(7, len(mid_trend))
            if recent_n > 0:
                actual = sales[-recent_n:]
                pred_mid = mid_trend[-recent_n:]
                mae = np.mean(np.abs(actual - pred_mid))
                avg_sales = np.mean(actual)
                confidence = max(0, 1 - (mae / (avg_sales + 1e-6)))
                confidence = int(round(confidence * 100))
            else:
                confidence = 70
            # 예측값, 날짜, 신뢰도 표로 전달
            plots['lastyear_forecast_table'] = [
                {'date': d.strftime('%Y-%m-%d'), 'predicted_sales': v, 'confidence': confidence}
                for d, v in zip(forecast_dates, forecast_values)
            ]
        else:
            plots['lastyear_daily_trend'] = None
            plots['lastyear_weekly_trend'] = None
            plots['lastyear_forecast_table'] = []
    
    # 년도별 판매량 그래프
    if not df.empty:
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        df_copy['년도'] = df_copy['판매일자'].dt.year
        yearly_sales = df_copy.groupby('년도')['실판매'].sum().reset_index()
        
        if not yearly_sales.empty:
            fig12, ax12 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
            ax12.set_facecolor('#f5f7fa')
            ax12.plot(range(len(yearly_sales)), yearly_sales['실판매'], marker='o', linewidth=2, markersize=6, color='#45B7D1')
            ax12.set_xlabel('년도')
            ax12.set_ylabel('판매량')
            ax12.set_xticks(range(len(yearly_sales)))
            ax12.set_xticklabels(yearly_sales['년도'], rotation=45, ha='right')
            ax12.grid(True, alpha=0.3)
            
            plt.tight_layout(pad=0)
            img12 = io.BytesIO()
            plt.savefig(img12, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img12.seek(0)
            plots['yearly_sales_chart'] = base64.b64encode(img12.getvalue()).decode()
            plt.close()
    
    return plots

@app.route('/api/inventory-alerts')
def inventory_alerts():
    try:
        df = load_from_db()
        if df.empty:
            return jsonify({'alerts': []})
        
        top_20_products, _, _ = pareto_analysis(df)
        
        alerts = []
        for product in top_20_products:
            product_data = df[df['품명'] == product]
            current_stock = product_data['현재고'].sum()
            pending_stock = product_data['미송잔량'].sum()
            avg_daily_sales = product_data['실판매'].sum() / len(product_data) if len(product_data) > 0 else 0
            
            if current_stock < avg_daily_sales * 3:
                alerts.append({
                    'product': product,
                    'current_stock': current_stock,
                    'pending_stock': pending_stock,
                    'avg_daily_sales': round(avg_daily_sales, 1),
                    'days_remaining': round(current_stock / avg_daily_sales, 1) if avg_daily_sales > 0 else 0
                })
        
        return jsonify({'alerts': alerts})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales-forecast')
def sales_forecast():
    try:
        df = load_from_db()
        product = request.args.get('product')
        if product:
            df = df[df['품명'] == product]
        if df.empty:
            return jsonify({'forecast': []})
        df = df.copy()
        df['판매일자'] = pd.to_datetime(df['판매일자'])
        daily_sales = df.groupby('판매일자')['실판매'].sum().reset_index()
        daily_sales['판매일자'] = pd.to_datetime(daily_sales['판매일자'])
        daily_sales = daily_sales.sort_values('판매일자')
        x = np.arange(len(daily_sales))
        sales = daily_sales['실판매'].values
        # 중간선 추세선 계산
        roll_min = pd.Series(sales).rolling(7, min_periods=1).min()
        roll_max = pd.Series(sales).rolling(7, min_periods=1).max()
        low_trend = np.poly1d(np.polyfit(x, roll_min, 1))(x)
        high_trend = np.poly1d(np.polyfit(x, roll_max, 1))(x)
        mid_trend = (low_trend + high_trend) / 2

        # 예측 구간 생성 (향후 7일)
        forecast_dates = pd.date_range(start=daily_sales['판매일자'].iloc[-1] + timedelta(days=1), periods=7)
        # 중간선 추세선의 방정식으로 미래 x값에 대해 예측
        mid_trend_poly = np.poly1d(np.polyfit(x, mid_trend, 1))
        forecast = []
        for i, date in enumerate(forecast_dates, 1):
            pred = int(round(mid_trend_poly(len(daily_sales) + i - 1)))
            forecast.append({
                'date': date.strftime('%Y-%m-%d'),
                'predicted_sales': max(0, pred),
                'confidence': 0.7
            })
        return jsonify({'forecast': forecast})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/product-trend', methods=['GET'])
def product_trend():
    product = request.args.get('product', '')
    query = request.args.get('query', '')
    df = load_from_db()
    if df.empty or '품명' not in df.columns or '판매일자' not in df.columns or '실판매' not in df.columns:
        return jsonify({'error': '데이터 없음'}), 404

    # 유사 상품명 검색
    all_products = sorted(df['품명'].unique())
    if query:
        matches = process.extract(query, all_products, limit=10, scorer=process.fuzz.WRatio)
        filtered_products = [m[0] for m in matches if m[1] >= 60]
    else:
        filtered_products = all_products

    # 상품 데이터 추출
    if product and product in all_products:
        sub = df[df['품명'] == product].sort_values('판매일자')
        if len(sub) < 2:
            return jsonify({'error': '데이터 부족'}), 400
        # 추세선 계산
        sales = sub['실판매'].astype(float).values
        x = np.arange(len(sales))
        high_trend = np.poly1d(np.polyfit(x, pd.Series(sales).rolling(7, min_periods=1).max(), 1))(x)
        low_trend = np.poly1d(np.polyfit(x, pd.Series(sales).rolling(7, min_periods=1).min(), 1))(x)
        mid_trend = (high_trend + low_trend) / 2
        # 그래프 생성
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(sub['판매일자'], sales, marker='o', label='실판매')
        ax.plot(sub['판매일자'], high_trend, '--', color='red', label='고점 추세선')
        ax.plot(sub['판매일자'], low_trend, '--', color='blue', label='저점 추세선')
        ax.plot(sub['판매일자'], mid_trend, '-', color='green', label='중간선')
        ax.set_title(f'{product} 판매량 및 추세선')
        ax.set_xlabel('판매일자')
        ax.set_ylabel('실판매')
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight', dpi=200)
        img.seek(0)
        plt.close()
        return send_file(img, mimetype='image/png')
    else:
        return jsonify({'products': filtered_products})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000) 