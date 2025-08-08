from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from service.db import load_from_db, save_to_db, delete_by_date, reset_db, init_clients_table, set_client_count, get_client_counts, init_weekly_clients_table, set_weekly_client_count, get_weekly_client_counts, get_current_week_client_count, set_pareto_days, get_pareto_days
from service.analysis import generate_inventory_alerts, generate_a_grade_alerts, get_pareto_products, get_pareto_products_by_category, get_pareto_products_by_category_current_year, get_product_stats, get_pareto_products_by_category_date_specified, get_pareto_products_date_specified
from service.visualization import create_visualizations
from service.charts import create_weekly_sales_chart
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
    # 주차별 거래처 수 테이블 초기화 (최초 1회)
    init_weekly_clients_table()

    selected_product = request.args.get('product')
    selected_color = request.args.get('color')  # 컬러 파라미터 추가

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
        return redirect(url_for('dashboard.dashboard', product=selected_product, color=selected_color))
    
    # 주차별 거래처 수 저장 처리
    if request.method == 'POST' and selected_product and 'weekly_client_count_form' in request.form:
        value = request.form.get('weekly_client_count', '').strip()
        if value == '':
            flash('거래처 수를 입력해주세요.', 'error')
        else:
            try:
                count = int(value)
                current_date = datetime.now()
                year = current_date.year
                week = current_date.isocalendar()[1]
                set_weekly_client_count(selected_product, year, week, count)
                flash(f'{year}년 {week}주차 거래처 수가 저장되었습니다.', 'success')
            except ValueError:
                flash('올바른 숫자를 입력해주세요.', 'error')
        return redirect(url_for('dashboard.dashboard', product=selected_product, color=selected_color))
    
    # 비교 상품 데이터 처리
    compare_df = None
    compare_filename = None
    
    if request.method == 'POST' and 'compare_upload' in request.form and selected_product:
        compare_file = request.files.get('compare_file')
        if compare_file and compare_file.filename.endswith(('xls', 'xlsx')):
            try:
                compare_df = pd.read_excel(compare_file)
                from service.db import save_compare_product
                upload_date = datetime.now().strftime('%Y-%m-%d')
                save_compare_product(selected_product, compare_df, upload_date, filename=compare_file.filename)
                flash(f'비교 상품 파일 {compare_file.filename} 업로드 완료! (상품: {selected_product})', 'success')
                compare_filename = compare_file.filename
            except Exception as e:
                flash(f'비교 상품 파일 처리 중 오류: {str(e)}', 'error')
    elif request.method == 'POST' and 'delete_compare' in request.form and selected_product:
        from service.db import delete_compare_product
        delete_compare_product(selected_product)
        flash(f'비교 상품 데이터가 삭제되었습니다.', 'success')
        return redirect(url_for('dashboard.dashboard', product=selected_product, color=selected_color))
    elif selected_product:
        from service.db import load_compare_product
        result = load_compare_product(selected_product)
        if result is not None:
            compare_df, compare_filename = result
            print(f"비교상품 데이터 로드 성공 - compare_df: {compare_df is not None}, compare_filename: {compare_filename}")
            if compare_df is not None:
                print(f"비교상품 데이터 shape: {compare_df.shape}, columns: {compare_df.columns.tolist()}")
        else:
            compare_df, compare_filename = None, None
            print("비교상품 데이터 로드 실패 - result is None")
    # 파레토 설정 저장 처리
    if request.method == 'POST' and 'pareto_settings_form' in request.form:
        try:
            pareto_days = int(request.form.get('pareto_days', 365))
            if pareto_days <= 0:
                flash('파레토 선택 기준 일수는 1일 이상이어야 합니다.', 'error')
            else:
                set_pareto_days(pareto_days)
                flash(f'파레토 선택 기준이 {pareto_days}일로 설정되었습니다.', 'success')
        except ValueError:
            flash('올바른 숫자를 입력해주세요.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    
    elif request.method == 'POST':
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
                    drop_cols = [col for col in df.columns if '실판매' in col and '금액' in col]
                    if drop_cols:
                        df = df.drop(columns=drop_cols)
                    df = df.iloc[:-1]
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
        return redirect(url_for('dashboard.dashboard'))
    
    # 대시보드 렌더링 (GET)
    df = load_from_db()
    # '일반상품' 제외
    if not df.empty:
        df = df[df['품명'] != '(일반상품)']
    product_list = sorted(df['품명'].unique()) if not df.empty else []
    all_dates = sorted(pd.to_datetime(df['판매일자']).unique()) if not df.empty else []
    search_query = request.args.get('search', '')
    
    # 저장된 파레토 설정 일수 가져오기 (먼저 정의)
    pareto_days = get_pareto_days()
    
    if selected_product and selected_product in product_list:
        # 컬러 필터링 적용
        if selected_color:
            # 특정 컬러가 선택된 경우: 해당 상품의 특정 컬러만 필터링
            filtered_df = df[(df['품명'] == selected_product) & (df['칼라'] == selected_color)]
            display_name = f"{selected_product} - {selected_color}"
        else:
            # 컬러가 선택되지 않은 경우: 해당 상품 전체
            filtered_df = df[df['품명'] == selected_product]
            display_name = selected_product
        
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
        if selected_color:
            stats.update(get_product_stats(df, selected_product, selected_color))
        else:
            stats.update(get_product_stats(df, selected_product))
        
        # 주차별 거래처 수 데이터 가져오기
        current_year = datetime.now().year
        weekly_client_data = get_weekly_client_counts(selected_product, current_year)
        
        plots = create_visualizations(filtered_df, only_product=True, all_dates=all_dates, compare_df=compare_df, weekly_client_data=weekly_client_data)
        charts = create_visualizations(df)  # 전체 데이터용
        
        # 추세선 알림 데이터 추출
        trend_alerts = []
        if plots and 'weekly_sales_trend' in plots and plots['weekly_sales_trend']:
            weekly_data = plots['weekly_sales_trend']
            if isinstance(weekly_data, dict) and 'data' in weekly_data:
                trend_alerts = weekly_data.get('data', {}).get('trend_alerts', [])
        
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
        
        # 파레토 상품들에 대한 추세 알림 생성 (메인 대시보드용)
        trend_alerts = []
        if not filtered_df.empty:
            # 파레토 상품들 가져오기 (저장된 일수 기준)
            pareto_products = get_pareto_products_date_specified(filtered_df, pareto_days)
            
            for product in pareto_products[:10]:  # 상위 10개 파레토 상품만 분석
                product_df = filtered_df[filtered_df['품명'] == product]
                if not product_df.empty:
                    weekly_sales_product = create_weekly_sales_chart(product_df, compare_df=compare_df)
                    if weekly_sales_product and 'data' in weekly_sales_product:
                        product_alerts = weekly_sales_product.get('data', {}).get('trend_alerts', [])
                        # 상품명을 알림 메시지에 추가
                        for alert in product_alerts:
                            alert['product'] = product
                            alert['message'] = f"[{product}] {alert['message']}"
                        trend_alerts.extend(product_alerts)
        
        # 파레토 컬러 상품-컬러 리스트 추출 (저장된 일수 기준)
        pareto_color_products = []
        if not filtered_df.empty:
            from service.analysis import color_pareto_analysis_date_specified
            pareto_color_products = color_pareto_analysis_date_specified(filtered_df, pareto_days)
        alert_rows = generate_inventory_alerts(filtered_df, pareto_color_products=pareto_color_products)
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
        # datetime 객체를 문자열로 변환
        unique_dates = sorted(df['판매일자'].dt.strftime('%Y-%m-%d').unique())
    
    # 상품별/컬러별 파레토 상품 가져오기 (저장된 일수 기준)
    pareto_data = get_pareto_products_by_category_date_specified(df, pareto_days) if not df.empty else {'products': [], 'colors': []}
    sidebar_products = pareto_data['products']
    sidebar_colors = pareto_data['colors']
    
    # 파레토 상품별 거래처 수 불러오기
    client_counts = get_client_counts()
    # 현재 상품의 거래처 수
    current_client_count = client_counts.get(selected_product) if selected_product else None
    
    # 현재 주차 거래처 수
    current_week_client_count = None
    if selected_product:
        current_week_client_count = get_current_week_client_count(selected_product)
    
    return render_template('dashboard.html',
        charts=charts, plots=plots, stats=stats, product_list=product_list,
        selected_product=selected_product, selected_color=selected_color, display_name=display_name if 'display_name' in locals() else selected_product,
        alert_df=alert_df, a_grade_alert_df=a_grade_alert_df, trend_alerts=trend_alerts if 'trend_alerts' in locals() else [],
        search_query=search_query, last_year=last_year, unique_dates=unique_dates,
        sidebar_products=sidebar_products,
        sidebar_colors=sidebar_colors,
        sidebar_products_json=json.dumps(sidebar_products),
        sidebar_colors_json=json.dumps(sidebar_colors),
        client_counts=client_counts,
        current_client_count=current_client_count,
        current_week_client_count=current_week_client_count,
        compare_df=compare_df,
        compare_filename=compare_filename,
        pareto_days=pareto_days
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