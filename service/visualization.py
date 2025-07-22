from datetime import datetime
import pandas as pd
import numpy as np
from .charts import (
    create_sales_trend_chart,
    create_weekly_sales_chart,
    create_product_sales_chart,
    create_color_sales_chart,
    create_size_sales_chart,
    create_pareto_analysis_chart
)

def create_visualizations(df, only_product=False, all_dates=None, trend_window=7, trend_frac=0.08, compare_df=None, weekly_client_data=None):
    """ECharts용 대시보드 그래프 데이터 생성"""
    charts = {}
    
    # 1. 판매 추세 그래프
    sales_trend = create_sales_trend_chart(df, only_product, all_dates, trend_window, trend_frac, compare_df)
    if sales_trend:
        charts['sales_trend'] = sales_trend
    
    # 2. 주별 판매량 그래프 (상품별 상세 페이지에서만)
    if only_product:
        weekly_sales = create_weekly_sales_chart(df, weekly_client_data, compare_df)
        if weekly_sales:
            charts['weekly_sales_trend'] = weekly_sales
    
    # 3. 상품별 판매량 그래프 (메인 대시보드에서만)
    if not only_product:
        product_sales = create_product_sales_chart(df)
        if product_sales:
            charts['product_sales'] = product_sales
    
    # 4. 컬러별 판매량 그래프
    color_sales = create_color_sales_chart(df)
    if color_sales:
        charts['color_sales'] = color_sales
    
    # 5. 사이즈별 판매량 그래프
    size_sales = create_size_sales_chart(df)
    if size_sales:
        charts['size_sales'] = size_sales
    
    # 6. 파레토 분석 그래프 (메인 대시보드에서만)
    if not only_product:
        pareto_analysis = create_pareto_analysis_chart(df)
        if pareto_analysis:
            charts['pareto_analysis'] = pareto_analysis

    return charts

def chart_to_echarts_option(chart_data):
    """차트 데이터를 ECharts 옵션으로 변환"""
    if not chart_data:
        return None
    
    option = {
        'title': {'text': chart_data.get('title', ''), 'left': 'center'},
        'tooltip': {'trigger': 'axis'},
        'legend': chart_data['config'].get('legend', {'show': True}),
        'xAxis': chart_data['config']['xAxis'],
        'yAxis': chart_data['config']['yAxis'],
        'series': chart_data['config']['series']
    }
    
    # 추가 설정들
    if 'markLine' in chart_data['config']:
        option['markLine'] = chart_data['config']['markLine']
    if 'dataZoom' in chart_data['config']:
        option['dataZoom'] = chart_data['config']['dataZoom']
    
    return option