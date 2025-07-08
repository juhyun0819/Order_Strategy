from flask import Blueprint, request, jsonify, send_file
from service.db import load_from_db
from service.analysis import pareto_analysis

from datetime import timedelta
import pandas as pd
import numpy as np
from fuzzywuzzy import process
from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as plt
import io

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/inventory-alerts')
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

@api_bp.route('/api/sales-forecast')
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

@api_bp.route('/product-trend', methods=['GET'])
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