import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from service.analysis import recent_7days_analysis
from statsmodels.nonparametric.smoothers_lowess import lowess

class TrendCalculator:
    """추세선 계산 (SOLID 원칙 적용, LOWESS 기반)"""
    def __init__(self, window=7, frac=0.2):
        self.window = window
        self.frac = frac

    def _lowess(self, y):
        if len(y) < 2:
            return np.array([])
        x = np.arange(len(y))
        return lowess(y, x, frac=self.frac, return_sorted=False)

    def lower_trend(self, y):
        roll_min = pd.Series(y).rolling(self.window, min_periods=1).min()
        return self._lowess(roll_min.values)

    def upper_trend(self, y):
        roll_max = pd.Series(y).rolling(self.window, min_periods=1).max()
        return self._lowess(roll_max.values)

    def mid_trend(self, y):
        lower = self.lower_trend(y)
        upper = self.upper_trend(y)
        if len(lower) == len(upper):
            return (lower + upper) / 2
        return np.array([])

def create_visualizations(df, only_product=False, all_dates=None, trend_window=7, trend_frac=0.08):
    # frac은 0.08로 설정하여 월별 흐름강조
    """ECharts용 대시보드 그래프 데이터 생성 (추세선 계산 분리)"""
    charts = {}
    trend_calculator = TrendCalculator(window=trend_window, frac=trend_frac)
    
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
        current_year = datetime.now().year
        df_current_year = df[df['판매일자'].dt.year == current_year]
        if not df_current_year.empty:
            daily_sales = df_current_year.groupby('판매일자')['실판매'].sum().reset_index()
            daily_sales['판매일자'] = pd.to_datetime(daily_sales['판매일자'])
            daily_sales = daily_sales.sort_values('판매일자')
            start_date = pd.Timestamp(f'{current_year}-01-01')
            end_date = daily_sales['판매일자'].max()
            full_date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            daily_sales = daily_sales.set_index('판매일자').reindex(full_date_range, fill_value=0).reset_index()
            daily_sales.columns = ['판매일자', '실판매']
        else:
            daily_sales = pd.DataFrame({'판매일자': [], '실판매': []})

    daily_sales_nonzero = daily_sales[daily_sales['실판매'] != 0]
    dates = daily_sales_nonzero['판매일자'].dt.strftime('%Y-%m-%d').tolist() if not daily_sales_nonzero.empty else []
    sales_data = daily_sales_nonzero['실판매'].tolist() if not daily_sales_nonzero.empty else []

    # --- 추세선 계산 (LOWESS 기반 상/하/중) ---
    if not daily_sales_nonzero.empty:
        sales_nonzero = daily_sales_nonzero['실판매'].values
        low_trend = trend_calculator.lower_trend(sales_nonzero)
        high_trend = trend_calculator.upper_trend(sales_nonzero)
        mid_trend = trend_calculator.mid_trend(sales_nonzero)
    else:
        low_trend = high_trend = mid_trend = np.array([])

    trend_data = {
        'low': low_trend.tolist() if len(low_trend) > 0 else [],
        'high': high_trend.tolist() if len(high_trend) > 0 else [],
        'mid': mid_trend.tolist() if len(mid_trend) > 0 else []
    }

    charts['sales_trend'] = {
        'type': 'line',
        'title': '판매 트렌드',
        'data': {
            'dates': dates,
            'sales': sales_data,
            'trends': trend_data
        },
        'config': {
            'xAxis': {'type': 'category', 'name': '월', 'data': dates},
            'yAxis': {'type': 'value', 'name': '판매량'},
            'series': [
                {
                    'name': '실판매',
                    'type': 'line',
                    'data': sales_data,
                    'symbol': 'circle',
                    'symbolSize': 4,
                    'lineStyle': {'width': 2}
                }
            ]
        }
    }

    if len(trend_data['low']) > 0:
        charts['sales_trend']['config']['series'].extend([
            {
                'name': '저점 추세(LOWESS)',
                'type': 'line',
                'data': trend_data['low'],
                'lineStyle': {'type': 'dashed', 'color': '#5470c6'},
                'symbol': 'none'
            },
            {
                'name': '고점 추세(LOWESS)', 
                'type': 'line',
                'data': trend_data['high'],
                'lineStyle': {'type': 'dashed', 'color': '#91cc75'},
                'symbol': 'none'
            },
            {
                'name': '중위 추세(LOWESS)',
                'type': 'line', 
                'data': trend_data['mid'],
                'lineStyle': {'type': 'dashed', 'color': '#ee6666'},
                'symbol': 'none'
            }
        ])

    # 2. 상품별 실판매 집계 (only_product=False일 때만)
    if not only_product and '품명' in df.columns and '실판매' in df.columns:
        product_sales = df.groupby('품명')['실판매'].sum().sort_values(ascending=False).head(10)
        
        charts['product_sales'] = {
            'type': 'bar',
            'title': '상품별 판매량',
            'data': {
                'categories': product_sales.index.tolist() if not product_sales.empty else [],
                'values': product_sales.values.tolist() if not product_sales.empty else []
            },
            'config': {
                'xAxis': {'type': 'category', 'name': '품명', 'data': product_sales.index.tolist() if not product_sales.empty else [], 'axisLabel': {'rotate': 30, 'interval': 0}},
                'yAxis': {'type': 'value', 'name': '실판매'},
                'series': [{
                    'name': '판매량',
                    'type': 'bar',
                    'data': product_sales.values.tolist() if not product_sales.empty else [],
                    'itemStyle': {'color': '#73c0de'}
                }]
            }
        }
        
        # 파레토 분석
        product_sales_pareto = df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
        total_sales = product_sales_pareto.sum()
        cumsum = product_sales_pareto.cumsum()
        cumsum_ratio = cumsum / total_sales
        
        # 80% 기준점 찾기
        pareto_idx = np.where(cumsum_ratio <= 0.8)[0]
        pareto_last = pareto_idx[-1] if len(pareto_idx) > 0 else 0
        top_n = pareto_last + 1
        
        products_sorted = product_sales_pareto.index[:top_n].tolist()
        sales_sorted = product_sales_pareto.values[:top_n].tolist()
        cumsum_ratio_top = (cumsum_ratio[:top_n] * 100).tolist()

        # 상위 20개만 기본 표시, dataZoom으로 전체 탐색 가능
        products_display = products_sorted[:20]
        sales_display = sales_sorted[:20]
        cumsum_display = cumsum_ratio_top[:20]

        charts['pareto_analysis'] = {
            'type': 'mixed',
            'title': '파레토 분석',
            'data': {
                'categories': products_sorted,
                'sales': sales_sorted,
                'cumulative': cumsum_ratio_top
            },
            'config': {
                'xAxis': {
                    'type': 'category',
                    'name': '품명',
                    'data': products_sorted,
                    'axisLabel': {'rotate': 45, 'interval': 0}
                },
                'yAxis': [
                    {'type': 'value', 'name': '판매량', 'position': 'left'},
                    {'type': 'value', 'name': '누적비율(%)', 'position': 'right', 'max': 100}
                ],
                'series': [
                    {
                        'name': '판매량',
                        'type': 'bar',
                        'data': sales_sorted,
                        'itemStyle': {'color': '#ffa500'},
                        'yAxisIndex': 0
                    },
                    {
                        'name': '누적비율',
                        'type': 'line',
                        'data': cumsum_ratio_top,
                        'itemStyle': {'color': '#2563eb'},
                        'yAxisIndex': 1,
                        'symbol': 'circle',
                        'symbolSize': 6
                    }
                ],
                'markLine': {
                    'data': [{'yAxis': 80, 'label': {'formatter': '80%'}}]
                },
                'dataZoom': [
                    {
                        'type': 'inside',
                        'xAxisIndex': 0,
                        'start': 0,
                        'end': 100 if len(products_sorted) <= 20 else int(20/len(products_sorted)*100)
                    },
                    {
                        'type': 'slider',
                        'xAxisIndex': 0,
                        'start': 0,
                        'end': 100 if len(products_sorted) <= 20 else int(20/len(products_sorted)*100),
                        'height': 16,
                        'handleSize': '60%',
                        'bottom': 0
                    }
                ]
            }
        }
    
    # 3. 컬러별 실판매 집계
    if '칼라' in df.columns and '실판매' in df.columns:
        color_sales = df.groupby('칼라')['실판매'].sum().sort_values(ascending=False).head(10)
        
        charts['color_sales'] = {
            'type': 'bar',
            'title': '컬러별 판매량',
            'data': {
                'categories': color_sales.index.tolist(),
                'values': color_sales.values.tolist()
            },
            'config': {
                'xAxis': {'type': 'category', 'name': '컬러', 'data': color_sales.index.tolist(), 'axisLabel': {'rotate': 30, 'interval': 0}},
                'yAxis': {'type': 'value', 'name': '실판매'},
                'series': [{
                    'name': '판매량',
                    'type': 'bar',
                    'data': color_sales.values.tolist(),
                    'itemStyle': {'color': '#fc8452'}
                }]
            }
        }
    
    # 4. 사이즈별 실판매 집계
    if '사이즈' in df.columns and '실판매' in df.columns:
        size_sales = df.groupby('사이즈')['실판매'].sum().sort_values(ascending=False)
        
        charts['size_sales'] = {
            'type': 'bar',
            'title': '사이즈별 판매량',
            'data': {
                'categories': size_sales.index.tolist(),
                'values': size_sales.values.tolist()
            },
            'config': {
                'xAxis': {'type': 'category', 'name': '사이즈', 'data': size_sales.index.tolist(), 'axisLabel': {'rotate': 30, 'interval': 0}},
                'yAxis': {'type': 'value', 'name': '실판매'},
                'series': [{
                    'name': '판매량',
                    'type': 'bar',
                    'data': size_sales.values.tolist(),
                    'itemStyle': {'color': '#91cc75'}
                }]
            }
        }
    
    # 5. 최근 7일 요일별/일별 판매 분석
    daily_sales_7, day_sales = recent_7days_analysis(df)
    
    if day_sales is not None and not day_sales.empty:
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_names = ['월', '화', '수', '목', '금', '토', '일']
        day_sales_reindexed = day_sales.groupby('요일')['실판매'].sum().reindex(day_order)
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
        
        charts['daily_sales'] = {
            'type': 'bar',
            'title': '요일별 판매량',
            'data': {
                'categories': day_names,
                'values': day_sales_reindexed.values.tolist(),
                'colors': colors
            },
            'config': {
                'xAxis': {'type': 'category', 'name': '요일', 'data': day_names},
                'yAxis': {'type': 'value', 'name': '판매량'},
                'series': [{
                    'name': '판매량',
                    'type': 'bar',
                    'data': [{'value': v, 'itemStyle': {'color': c}} 
                            for v, c in zip(day_sales_reindexed.values, colors)],
                    'label': {'show': True, 'position': 'top'}
                }]
            }
        }
    
    if daily_sales_7 is not None and not daily_sales_7.empty:
        dates_7 = daily_sales_7['판매일자'].dt.strftime('%m-%d').tolist()
        sales_7 = daily_sales_7['실판매'].tolist()
        
        charts['weekly_sales'] = {
            'type': 'line',
            'title': '최근 7일 판매량',
            'data': {
                'dates': dates_7,
                'values': sales_7
            },
            'config': {
                'xAxis': {'type': 'category', 'name': '날짜', 'data': dates_7},
                'yAxis': {'type': 'value', 'name': '판매량'},
                'series': [{
                    'name': '판매량',
                    'type': 'line',
                    'data': sales_7,
                    'symbol': 'circle',
                    'symbolSize': 6,
                    'lineStyle': {'width': 2}
                }]
            }
        }
    
    # 6. 주별 판매량 그래프 (현재 연도)
    if not df.empty:
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        
        current_year = datetime.now().year
        df_current_year = df_copy[df_copy['판매일자'].dt.year == current_year]
        
        if not df_current_year.empty:
            df_current_year['주차'] = df_current_year['판매일자'].dt.isocalendar().week
            weekly_sales = df_current_year.groupby('주차')['실판매'].sum().reset_index()
            weekly_sales = weekly_sales.sort_values('주차')
            
            last_week = weekly_sales[weekly_sales['실판매'] > 0]['주차'].max() if (weekly_sales['실판매'] > 0).any() else 1
            
            # 월별 표시를 위한 주차 변환
            month_ticks = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45]
            month_labels = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']
            
            charts['weekly_sales_chart'] = {
                'type': 'line',
                'title': '주별 판매량',
                'data': {
                    'weeks': weekly_sales['주차'][:last_week].tolist(),
                    'values': weekly_sales['실판매'][:last_week].tolist()
                },
                'config': {
                    'xAxis': {
                        'type': 'category',
                        'name': '월',
                        'data': weekly_sales['주차'][:last_week].tolist(),
                        'axisLabel': {'rotate': 30, 'interval': 0}
                    },
                    'yAxis': {'type': 'value', 'name': '판매량'},
                    'series': [{
                        'name': '판매량',
                        'type': 'line',
                        'data': weekly_sales['실판매'][:last_week].tolist(),
                        'symbol': 'circle',
                        'symbolSize': 4,
                        'lineStyle': {'width': 2, 'color': '#4ECDC4'}
                    }]
                }
            }
    
    # 7. 전년도 분석
    if not df.empty:
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        max_year = df_copy['판매일자'].dt.year.max()
        last_year = max_year - 1
        lastyear_df = df_copy[df_copy['판매일자'].dt.year == last_year]
        
        if not lastyear_df.empty:
            # 전년도 일별 판매 트렌드
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
            
            dates_ly = lastyear_daily['판매일자'].dt.strftime('%Y-%m-%d').tolist()
            
            charts['lastyear_daily_trend'] = {
                'type': 'line',
                'title': f'{last_year}년 일별 판매 트렌드',
                'data': {
                    'dates': dates_ly,
                    'sales': sales.tolist(),
                    'mid_trend': mid_trend.tolist()
                },
                'config': {
                    'xAxis': {'type': 'category', 'name': '월', 'data': dates_ly},
                    'yAxis': {'type': 'value', 'name': '판매량'},
                    'series': [
                        {
                            'name': '실판매',
                            'type': 'line',
                            'data': sales.tolist(),
                            'symbol': 'circle',
                            'symbolSize': 4,
                            'lineStyle': {'color': '#FF6B6B'}
                        },
                        {
                            'name': '중위 추세',
                            'type': 'line',
                            'data': mid_trend.tolist(),
                            'lineStyle': {'type': 'dashed', 'color': '#ee6666'},
                            'symbol': 'none'
                        }
                    ]
                }
            }
            
            # 전년도 주별 판매 트렌드
            lastyear_df['주차'] = lastyear_df['판매일자'].dt.isocalendar().week
            weekly_sales_ly = lastyear_df.groupby('주차')['실판매'].sum().reset_index()
            full_weeks = pd.DataFrame({'주차': range(1, 53)})
            weekly_sales_ly = weekly_sales_ly.merge(full_weeks, on='주차', how='right').fillna(0)
            weekly_sales_ly = weekly_sales_ly.sort_values('주차')
            
            charts['lastyear_weekly_trend'] = {
                'type': 'line',
                'title': f'{last_year}년 주별 판매 트렌드',
                'data': {
                    'weeks': weekly_sales_ly['주차'].tolist(),
                    'values': weekly_sales_ly['실판매'].tolist()
                },
                'config': {
                    'xAxis': {'type': 'category', 'name': '월', 'data': weekly_sales_ly['주차'].tolist()},
                    'yAxis': {'type': 'value', 'name': '판매량'},
                    'series': [{
                        'name': '판매량',
                        'type': 'line',
                        'data': weekly_sales_ly['실판매'].tolist(),
                        'symbol': 'circle',
                        'symbolSize': 4,
                        'lineStyle': {'color': '#4ECDC4'}
                    }]
                }
            }
            
            # 예측값 계산
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
            
            charts['lastyear_forecast_table'] = [
                {'date': d.strftime('%Y-%m-%d'), 'predicted_sales': v, 'confidence': confidence}
                for d, v in zip(forecast_dates, forecast_values)
            ]
    
    # 8. 년도별 판매량 그래프
    if not df.empty:
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        df_copy['년도'] = df_copy['판매일자'].dt.year
        yearly_sales = df_copy.groupby('년도')['실판매'].sum().reset_index()
        
        if not yearly_sales.empty:
            charts['yearly_sales_chart'] = {
                'type': 'line',
                'title': '년도별 판매량',
                'data': {
                    'years': yearly_sales['년도'].tolist(),
                    'values': yearly_sales['실판매'].tolist()
                },
                'config': {
                    'xAxis': {'type': 'category', 'name': '년도'},
                    'yAxis': {'type': 'value', 'name': '판매량'},
                    'series': [{
                        'name': '판매량',
                        'type': 'line',
                        'data': yearly_sales['실판매'].tolist(),
                        'symbol': 'circle',
                        'symbolSize': 6,
                        'lineStyle': {'width': 2, 'color': '#45B7D1'}
                    }]
                }
            }
    
    return charts

# ECharts 설정을 JSON으로 변환하는 헬퍼 함수
def chart_to_echarts_option(chart_data):
    """차트 데이터를 ECharts 옵션으로 변환"""
    if not chart_data:
        return {}
    
    chart_type = chart_data.get('type')
    config = chart_data.get('config', {})
    data = chart_data.get('data', {})
    
    # 기본 ECharts 옵션
    option = {
        'title': {
            'text': chart_data.get('title', ''),
            'left': 'center',
            'textStyle': {'fontSize': 16}
        },
        'tooltip': {'trigger': 'axis'},
        'legend': {'top': '10%'},
        'grid': {
            'left': '3%',
            'right': '4%',
            'bottom': '3%',
            'containLabel': True
        }
    }
    
    # xAxis, yAxis 설정
    if 'xAxis' in config:
        option['xAxis'] = config['xAxis'].copy()
        if chart_type in ['bar', 'line'] and 'categories' in data:
            option['xAxis']['data'] = data['categories']
        elif 'dates' in data:
            option['xAxis']['data'] = data['dates']
        elif 'weeks' in data:
            option['xAxis']['data'] = data['weeks']
        elif 'years' in data:
            option['xAxis']['data'] = data['years']
    
    if 'yAxis' in config:
        option['yAxis'] = config['yAxis']
    
    # series 설정
    if 'series' in config:
        option['series'] = config['series']
    
    # 특별한 설정들
    if 'markLine' in config:
        if 'series' in option and len(option['series']) > 0:
            option['series'][0]['markLine'] = config['markLine']
    
    return option