import pandas as pd
import numpy as np
from datetime import timedelta
from service.trend_calculator import TrendCalculator  # 추가
from service.column_validator import ColumnValidator  # 컬럼 검증 추가

def pareto_analysis(df):
    """파레토 분석 - 상위 20% 상품 추출"""
    product_sales = df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
    total_sales = product_sales.sum()
    cumulative_percentage = (product_sales.cumsum() / total_sales * 100)
    top_20_products = cumulative_percentage[cumulative_percentage <= 20].index.tolist()
    return top_20_products, product_sales, cumulative_percentage

def pareto_analysis_current_year(df):
    """올해(2025년) 데이터 기준 파레토 분석 - 상위 20% 상품 추출"""
    if df.empty:
        return [], pd.Series(), pd.Series()
    
    # 올해(2025년) 데이터만 필터링
    df['판매일자'] = pd.to_datetime(df['판매일자'])
    current_year_df = df[df['판매일자'].dt.year == 2025]
    
    if current_year_df.empty:
        return [], pd.Series(), pd.Series()
    
    product_sales = current_year_df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
    total_sales = product_sales.sum()
    cumulative_percentage = (product_sales.cumsum() / total_sales * 100)
    top_20_products = cumulative_percentage[cumulative_percentage <= 20].index.tolist()
    return top_20_products, product_sales, cumulative_percentage

def color_pareto_analysis(df):
    """컬러별 파레토 분석 - 상품-컬러 조합으로 파레토 분석"""
    if df.empty or '칼라' not in df.columns:
        return []
    
    # 상품-컬러 조합으로 판매량 집계
    color_sales = df.groupby(['품명', '칼라'])['실판매'].sum().reset_index()
    color_sales['상품_컬러'] = color_sales['품명'] + ' - ' + color_sales['칼라']
    
    # 전체 판매량 대비 비율 계산
    total_sales = color_sales['실판매'].sum()
    color_sales['비율'] = (color_sales['실판매'] / total_sales * 100).round(2)
    
    # 누적 비율 계산
    color_sales = color_sales.sort_values('실판매', ascending=False)
    color_sales['누적비율'] = color_sales['비율'].cumsum()
    
    # 80% 기준으로 파레토 상품-컬러 선택
    pareto_color_products = color_sales[color_sales['누적비율'] <= 80]['상품_컬러'].tolist()
    
    return pareto_color_products

def color_pareto_analysis_current_year(df):
    """올해(2025년) 데이터 기준 컬러별 파레토 분석 - (상품명, 컬러명) 튜플 리스트 반환"""
    if df.empty or '칼라' not in df.columns:
        return []
    df['판매일자'] = pd.to_datetime(df['판매일자'])
    current_year_df = df[df['판매일자'].dt.year == 2025]
    if current_year_df.empty:
        return []
    color_sales = current_year_df.groupby(['품명', '칼라'])['실판매'].sum().reset_index()
    total_sales = color_sales['실판매'].sum()
    color_sales['비율'] = (color_sales['실판매'] / total_sales * 100).round(2)
    color_sales = color_sales.sort_values('실판매', ascending=False)
    color_sales['누적비율'] = color_sales['비율'].cumsum()
    # 80% 기준으로 파레토 상품-컬러 선택 (상품명, 컬러명 튜플로 반환)
    pareto_color_products = color_sales[color_sales['누적비율'] <= 80][['품명', '칼라']].apply(tuple, axis=1).tolist()
    return pareto_color_products

def weekly_analysis(df):
    """주별 분석"""
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

def generate_inventory_alerts(df, pareto_color_products=None):
    """재고 알림 생성 (파레토 상품-컬러만)"""
    # 컬럼 검증 추가
    is_valid, missing_columns = ColumnValidator.validate_analysis_columns(df)
    if not is_valid:
        print(f"경고: 분석에 필요한 컬럼이 누락되었습니다. 누락된 컬럼: {missing_columns}")
        return []  # 빈 리스트 반환하여 오류 방지
    
    alert_rows = []
    plot_products = []
    trend_calculator = TrendCalculator(window=7, frac=0.2)  # LOWESS 기반 중간선 계산기

    # 파레토 상품-컬러 튜플만 필터링
    if pareto_color_products is not None:
        filter_mask = df.apply(lambda row: (row['품명'], row['칼라']) in pareto_color_products, axis=1)
        df = df[filter_mask]

    for (prod, color) in df[['품명', '칼라']].drop_duplicates().itertuples(index=False):
        sub = df[(df['품명'] == prod) & (df['칼라'] == color)].sort_values('판매일자')
        if len(sub) >= 2:
            sales = sub['실판매'].astype(float).values
            if np.ptp(sales) > 0:
                plot_products.append((prod, color))

    for (prod, color) in plot_products:
        sub = df[(df['품명'] == prod) & (df['칼라'] == color)].sort_values('판매일자')
        if sub.empty or '실판매' not in sub.columns or '현재고' not in sub.columns:
            continue
        sales = sub['실판매'].astype(float).values
        if len(sales) < 2:
            continue
        x = np.arange(len(sales))
        # LOWESS 기반 중간선 계산
        mid_trend_arr = trend_calculator.mid_trend(sales)
        mid_pred = float(mid_trend_arr[-1]) if len(mid_trend_arr) > 0 else 0
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
            '상품명': f"{prod} - {color}",
            '품명': prod,
            '칼라': color,
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
    """A급 상품 알림 생성 (파레토 A급 + 소진임박)"""
    # 컬럼 검증 추가
    is_valid, missing_columns = ColumnValidator.validate_analysis_columns(df)
    if not is_valid:
        print(f"경고: A급 상품 분석에 필요한 컬럼이 누락되었습니다. 누락된 컬럼: {missing_columns}")
        return []  # 빈 리스트 반환하여 오류 방지
    
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
    """상품명 검색"""
    if not query:
        return products
    return [p for p in products if query.lower() in p.lower()]

def get_pareto_products(df):
    """파레토 상품 목록 반환 (상품별)"""
    if df.empty:
        return []
    
    product_sales = df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
    total_sales = product_sales.sum()
    cumulative_percentage = (product_sales.cumsum() / total_sales * 100)
    
    # 80% 기준으로 파레토 상품 선택
    pareto_products = cumulative_percentage[cumulative_percentage <= 80].index.tolist()
    return pareto_products

def get_pareto_products_current_year(df):
    """올해(2025년) 데이터 기준 파레토 상품 목록 반환 (상품별)"""
    if df.empty:
        return []
    
    # 올해(2025년) 데이터만 필터링
    df['판매일자'] = pd.to_datetime(df['판매일자'])
    current_year_df = df[df['판매일자'].dt.year == 2025]
    
    if current_year_df.empty:
        return []
    
    product_sales = current_year_df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
    total_sales = product_sales.sum()
    cumulative_percentage = (product_sales.cumsum() / total_sales * 100)
    
    # 80% 기준으로 파레토 상품 선택
    pareto_products = cumulative_percentage[cumulative_percentage <= 80].index.tolist()
    return pareto_products

def get_pareto_products_by_category(df):
    """상품별/컬러별 파레토 상품 목록 반환"""
    if df.empty:
        return {'products': [], 'colors': []}
    
    # 상품별 파레토
    product_pareto = get_pareto_products(df)
    
    # 컬러별 파레토
    color_pareto = color_pareto_analysis(df)
    
    return {
        'products': product_pareto,
        'colors': color_pareto
    }

def get_pareto_products_by_category_current_year(df):
    """올해(2025년) 데이터 기준 상품별/컬러별 파레토 상품 목록 반환"""
    if df.empty:
        return {'products': [], 'colors': []}
    
    # 상품별 파레토 (올해 기준)
    product_pareto = get_pareto_products_current_year(df)
    
    # 컬러별 파레토 (올해 기준)
    color_pareto = color_pareto_analysis_current_year(df)
    
    return {
        'products': product_pareto,
        'colors': color_pareto
    }

def get_product_stats(df, product_name, color_name=None):
    """
    선택된 상품(및 선택된 컬러)의 누적 판매량, 현재고(가장 최근 날짜), 최근 7일 판매량을 반환
    """
    if df.empty or product_name not in df['품명'].unique():
        return {
            'product_total_sales': 0,
            'product_current_stock': 0,
            'product_7days_sales': 0
        }
    if color_name:
        product_df = df[(df['품명'] == product_name) & (df['칼라'] == color_name)].copy()
    else:
        product_df = df[df['품명'] == product_name].copy()
    # 누적 판매량
    total_sales = product_df['실판매'].sum()
    # 날짜 컬럼 변환
    product_df['판매일자'] = pd.to_datetime(product_df['판매일자'])
    # 현재고: 가장 최근 날짜의 모든 행의 현재고 합산
    latest_date = product_df['판매일자'].max()
    latest_rows = product_df[product_df['판매일자'] == latest_date]
    current_stock = latest_rows['현재고'].sum() if not latest_rows.empty else 0
    # 최근 7일 판매량
    last_7_days = latest_date - pd.Timedelta(days=6)
    sales_7days = product_df[product_df['판매일자'] >= last_7_days]['실판매'].sum()
    return {
        'product_total_sales': int(total_sales),
        'product_current_stock': int(current_stock),
        'product_7days_sales': int(sales_7days)
    } 

def get_pareto_products_date_specified(df, days):
    """지정된 일수 기준 파레토 상품 목록 반환 (상품별)"""
    if df.empty:
        return []
    
    # 날짜 컬럼 변환
    df['판매일자'] = pd.to_datetime(df['판매일자'])
    
    # 최신 날짜부터 지정된 일수만큼의 데이터만 필터링
    latest_date = df['판매일자'].max()
    start_date = latest_date - pd.Timedelta(days=days)
    filtered_df = df[df['판매일자'] >= start_date]
    
    if filtered_df.empty:
        return []
    
    # 상품별 판매량 집계 및 정렬
    product_sales = filtered_df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
    total_sales = product_sales.sum()
    
    if total_sales == 0:
        return []
    
    # 누적 비율 계산
    cumulative_percentage = (product_sales.cumsum() / total_sales * 100)
    
    # 80% 기준으로 파레토 상품 선택
    pareto_products = cumulative_percentage[cumulative_percentage <= 80].index.tolist()
    return pareto_products

def color_pareto_analysis_date_specified(df, days):
    """지정된 일수 기준 컬러별 파레토 분석 - (상품명, 컬러명) 튜플 리스트 반환"""
    if df.empty or '칼라' not in df.columns:
        return []
    
    # 날짜 컬럼 변환
    df['판매일자'] = pd.to_datetime(df['판매일자'])
    
    # 최신 날짜부터 지정된 일수만큼의 데이터만 필터링
    latest_date = df['판매일자'].max()
    start_date = latest_date - pd.Timedelta(days=days)
    filtered_df = df[df['판매일자'] >= start_date]
    
    if filtered_df.empty:
        return []
    
    # 상품-컬러 조합으로 판매량 집계
    color_sales = filtered_df.groupby(['품명', '칼라'])['실판매'].sum().reset_index()
    total_sales = color_sales['실판매'].sum()
    
    if total_sales == 0:
        return []
    
    # 비율 계산
    color_sales['비율'] = (color_sales['실판매'] / total_sales * 100).round(2)
    
    # 누적 비율 계산
    color_sales = color_sales.sort_values('실판매', ascending=False)
    color_sales['누적비율'] = color_sales['비율'].cumsum()
    
    # 80% 기준으로 파레토 상품-컬러 선택 (상품명, 컬러명 튜플로 반환)
    pareto_color_products = color_sales[color_sales['누적비율'] <= 80][['품명', '칼라']].apply(tuple, axis=1).tolist()
    return pareto_color_products

def get_pareto_products_by_category_date_specified(df, days):
    """지정된 일수 기준 상품별/컬러별 파레토 상품 목록 반환"""
    if df.empty:
        return {'products': [], 'colors': []}
    
    # 상품별 파레토 (지정된 일수 기준)
    product_pareto = get_pareto_products_date_specified(df, days)
    
    # 컬러별 파레토 (지정된 일수 기준)
    color_pareto = color_pareto_analysis_date_specified(df, days)
    
    return {
        'products': product_pareto,
        'colors': color_pareto
    } 