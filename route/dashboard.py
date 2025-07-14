from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from service.db import load_from_db, save_to_db, delete_by_date, reset_db, init_clients_table, set_client_count, get_client_counts
from service.analysis import generate_inventory_alerts, generate_a_grade_alerts, get_pareto_products, get_product_stats
from service.visualization import create_visualizations
from datetime import datetime
import pandas as pd
import json

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/', methods=['GET', 'POST'])
def root():
    return redirect(url_for('dashboard.dashboard'))

@dashboard_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    # 파레토 거래처 테이블 초기화 (최초 1회)
    init_clients_table()

    selected_product = request.args.get('product')

    # 거래처 수 저장 처리 (POST, 상품 세부 페이지)
    if request.method == 'POST' and selected_product and 'client_count_form' in request.form:
        value = request.form.get('client_count', '').strip()
        if value == '':
            # 빈 값이면 삭제(0으로 저장하거나, 삭제 로직 추가 가능)
            set_client_count(selected_product, None)
        else:
            try:
                count = int(value)
                set_client_count(selected_product, count)
            except ValueError:
                pass
        flash('거래처 수가 저장되었습니다.', 'success')
        return redirect(url_for('dashboard.dashboard', product=selected_product))
    
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
                    # '실판매'와 '금액'이 모두 포함된 컬럼은 모두 제거
                    drop_cols = [col for col in df.columns if '실판매' in col and '금액' in col]
                    if drop_cols:
                        df = df.drop(columns=drop_cols)
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
        return redirect(url_for('dashboard.dashboard'))
    
    # 대시보드 렌더링 (GET)
    df = load_from_db()
    # '일반상품' 제외
    if not df.empty:
        df = df[df['품명'] != '(일반상품)']
    product_list = sorted(df['품명'].unique()) if not df.empty else []
    all_dates = sorted(pd.to_datetime(df['판매일자']).unique()) if not df.empty else []
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
        # 상품별 통계 추가
        stats.update(get_product_stats(df, selected_product))
        plots = create_visualizations(filtered_df, only_product=True, all_dates=all_dates)
        charts = create_visualizations(df)  # 전체 데이터용
        
        alert_df = None
        a_grade_alert_df = None
    else:
        filtered_df = df
        # 최근 7일 판매량 계산
        recent_7days_sales = 0
        if not filtered_df.empty:
            filtered_df['판매일자'] = pd.to_datetime(filtered_df['판매일자'])
            latest_date = filtered_df['판매일자'].max()
            last_7_days = latest_date - pd.Timedelta(days=6)
            recent_7days_sales = filtered_df[filtered_df['판매일자'] >= last_7_days]['실판매'].sum()
        stats = {
            'total_items': len(filtered_df),
            'total_sales': filtered_df['실판매'].sum(),
            'recent_7days_sales': int(recent_7days_sales),
            'total_pending': filtered_df['미송잔량'].sum(),
            'unique_products': filtered_df['품명'].nunique(),
            'unique_colors': filtered_df['칼라'].nunique(),
            'unique_sizes': filtered_df['사이즈'].nunique(),
            'avg_daily_sales': filtered_df.groupby('판매일자')['실판매'].sum().mean(),
            'upload_dates': filtered_df['upload_date'].nunique(),
            'sales_dates': filtered_df['판매일자'].nunique()
        }
        charts = create_visualizations(filtered_df)
        plots = None
        
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
    
    sidebar_products = get_pareto_products(df) if not df.empty else []
    # 파레토 상품별 거래처 수 불러오기
    client_counts = get_client_counts()
    # 현재 상품의 거래처 수
    current_client_count = client_counts.get(selected_product) if selected_product else None
    
    return render_template('dashboard.html',
        charts=charts, plots=plots, stats=stats, product_list=product_list,
        selected_product=selected_product, alert_df=alert_df, a_grade_alert_df=a_grade_alert_df, 
        search_query=search_query, last_year=last_year, unique_dates=unique_dates,
        sidebar_products=sidebar_products,
        sidebar_products_json=json.dumps(sidebar_products),
        client_counts=client_counts,
        current_client_count=current_client_count
    )

@dashboard_bp.route('/dashboard/plot')
def dashboard_plot():
    df = load_from_db()
    all_dates = sorted(pd.to_datetime(df['판매일자']).unique()) if not df.empty else []
    product = request.args.get('product')
    product_list = sorted(df['품명'].unique()) if not df.empty else []
    if product and product in product_list:
        filtered_df = df[df['품명'] == product]
        stats = {
            'product_total_sales': int(filtered_df['실판매'].sum()),
            'product_current_stock': int(filtered_df['현재고'].sum()),
            'product_7days_sales': int(filtered_df.tail(7)['실판매'].sum()),
        }
        plots = create_visualizations(filtered_df, only_product=True, all_dates=all_dates)
        return jsonify({
            'plot': plots['sales_trend'],
            'stats': stats,
            'product': product
        })
    return jsonify({'error': 'Invalid product'}), 400

def extract_date_from_filename(filename):
    """파일명에서 날짜 추출"""
    import re
    # 파일명에서 날짜 패턴 찾기 (YYYY-MM-DD 또는 YYYYMMDD)
    date_pattern = r'(\d{4}[-_]\d{2}[-_]\d{2}|\d{8})'
    match = re.search(date_pattern, filename)
    if match:
        date_str = match.group(1)
        if '-' in date_str or '_' in date_str:
            return date_str.replace('_', '-')
        else:
            # YYYYMMDD 형식을 YYYY-MM-DD로 변환
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return "날짜 없음" 