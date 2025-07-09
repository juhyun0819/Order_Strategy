import pandas as pd
import numpy as np
from datetime import timedelta

def pareto_analysis(df):
    """파레토 분석 - 상위 20% 상품 추출"""
    product_sales = df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
    total_sales = product_sales.sum()
    cumulative_percentage = (product_sales.cumsum() / total_sales * 100)
    top_20_products = cumulative_percentage[cumulative_percentage <= 20].index.tolist()
    return top_20_products, product_sales, cumulative_percentage

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

def generate_inventory_alerts(df):
    """재고 알림 생성"""
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
    """A급 상품 알림 생성 (파레토 A급 + 소진임박)"""
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
    """파레토 상품 목록 반환"""
    if df.empty:
        return []
    
    product_sales = df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
    total_sales = product_sales.sum()
    cumulative_percentage = (product_sales.cumsum() / total_sales * 100)
    
    # 80% 기준으로 파레토 상품 선택
    pareto_products = cumulative_percentage[cumulative_percentage <= 80].index.tolist()
    return pareto_products 

def get_product_stats(df, product_name):
    """
    선택된 상품의 누적 판매량, 현재고(가장 최근 날짜), 최근 7일 판매량을 반환
    """
    if df.empty or product_name not in df['품명'].unique():
        return {
            'product_total_sales': 0,
            'product_current_stock': 0,
            'product_7days_sales': 0
        }
    product_df = df[df['품명'] == product_name].copy()
    # 누적 판매량
    total_sales = product_df['실판매'].sum()
    # 날짜 컬럼 변환
    product_df['판매일자'] = pd.to_datetime(product_df['판매일자'])
    # 현재고: 가장 최근 날짜의 재고
    latest_date = product_df['판매일자'].max()
    latest_row = product_df[product_df['판매일자'] == latest_date]
    current_stock = latest_row['현재고'].iloc[0] if not latest_row.empty else 0
    # 최근 7일 판매량
    last_7_days = latest_date - pd.Timedelta(days=6)
    sales_7days = product_df[product_df['판매일자'] >= last_7_days]['실판매'].sum()
    return {
        'product_total_sales': int(total_sales),
        'product_current_stock': int(current_stock),
        'product_7days_sales': int(sales_7days)
    } 