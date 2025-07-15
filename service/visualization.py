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

def get_full_year_dates(year):
    return pd.date_range(start=f'{year}-01-01', end=f'{year}-12-31', freq='D')

def safe_list(arr):
    # np.ndarray면 list로 변환, 내부 값도 float 또는 None
    if hasattr(arr, 'tolist'):
        arr = arr.tolist()
    return [float(v) if v is not None and not (isinstance(v, float) and (v != v)) else None for v in arr]

def get_yearly_trend(df, year, trend_calculator):
    full_date_range = pd.date_range(start=f'{year}-01-01', end=f'{year}-12-31', freq='D')
    df_year = df[df['판매일자'].dt.year == year]
    daily_sales = df_year.groupby('판매일자')['실판매'].sum()
    daily_sales = daily_sales.reindex(full_date_range)
    sales_data = [float(v) if v is not None and not pd.isna(v) else None for v in daily_sales.values]
    valid_indices = [i for i, v in enumerate(sales_data) if v is not None]
    valid_sales = [sales_data[i] for i in valid_indices]
    def pad_trend(trend):
        arr = [None] * len(sales_data)
        for idx, v in zip(valid_indices, trend):
            arr[idx] = float(v) if v is not None else None
        return list(arr)
    if valid_sales:
        low_trend = pad_trend(trend_calculator.lower_trend(valid_sales))
        high_trend = pad_trend(trend_calculator.upper_trend(valid_sales))
        mid_trend = pad_trend(trend_calculator.mid_trend(valid_sales))
    else:
        low_trend = high_trend = mid_trend = [None] * len(sales_data)
    return {'low': low_trend, 'high': high_trend, 'mid': mid_trend}

def create_visualizations(df, only_product=False, all_dates=None, trend_window=7, trend_frac=0.08, compare_df=None):
    current_year = datetime.now().year
    last_year = current_year - 1
    # frac은 0.08로 설정하여 월별 흐름강조
    charts = {}
    trend_calculator = TrendCalculator(window=trend_window, frac=trend_frac)
    
    # 1. 전체 판매 트렌드 or 상품별 판매 트렌드
    if only_product:
        full_date_range = pd.date_range(start=f'{current_year}-01-01', end=f'{current_year}-12-31', freq='D')
        df = df.copy()
        df['판매일자'] = pd.to_datetime(df['판매일자'])
        daily_sales = df.groupby('판매일자')['실판매'].sum()
        daily_sales = daily_sales.reindex(full_date_range)
        dates = full_date_range.strftime('%Y-%m-%d').tolist()
        # 데이터가 없는 날은 None으로 채움, 값이 있으면 float으로 변환
        sales_data = [float(v) if v is not None and not pd.isna(v) else None for v in daily_sales.values]

        # --- 추세선 계산 (LOWESS 기반 상/하/중) ---
        valid_indices = [i for i, v in enumerate(sales_data) if v is not None]
        valid_sales = [sales_data[i] for i in valid_indices]
        def pad_trend(trend):
            arr = [None] * len(sales_data)
            for idx, v in zip(valid_indices, trend):
                arr[idx] = float(v) if v is not None else None
            return list(arr)
        if valid_sales:
            low_trend = pad_trend(trend_calculator.lower_trend(valid_sales))
            high_trend = pad_trend(trend_calculator.upper_trend(valid_sales))
            mid_trend = pad_trend(trend_calculator.mid_trend(valid_sales))
        else:
            low_trend = high_trend = mid_trend = [None] * len(sales_data)

        trend_data = {
            'low': low_trend,
            'high': high_trend,
            'mid': mid_trend
        }
        # 전년도 추세선 계산 및 시리즈 추가
        trend_last_year = get_yearly_trend(df, last_year, trend_calculator)
    else:
        # 전체 판매 트렌드는 기존 방식 유지 (데이터가 있는 날짜만 x축)
        df = df.copy()
        df['판매일자'] = pd.to_datetime(df['판매일자'])
        # 올해 데이터만 필터링
        df = df[df['판매일자'].dt.year == current_year]
        daily_sales = df.groupby('판매일자')['실판매'].sum().reset_index()
        daily_sales = daily_sales[daily_sales['실판매'] != 0]
        dates = daily_sales['판매일자'].dt.strftime('%Y-%m-%d').tolist() if not daily_sales.empty else []
        sales_data = [float(v) if v is not None and not pd.isna(v) else None for v in (daily_sales['실판매'].tolist() if not daily_sales.empty else [])]
        if sales_data:
            low_trend = [float(v) if v is not None else None for v in trend_calculator.lower_trend(sales_data)]
            high_trend = [float(v) if v is not None else None for v in trend_calculator.upper_trend(sales_data)]
            mid_trend = [float(v) if v is not None else None for v in trend_calculator.mid_trend(sales_data)]
        else:
            low_trend = high_trend = mid_trend = []
        trend_data = {
            'low': low_trend if len(low_trend) > 0 else [],
            'high': high_trend if len(high_trend) > 0 else [],
            'mid': mid_trend if len(mid_trend) > 0 else []
        }

    # 올해 실판매 시계열 (기존)
    charts['sales_trend'] = {
        'type': 'line',
        'title': '판매 트렌드',
        'data': {
            'dates': dates,
            'sales': safe_list(sales_data),
            'trends': {
                'low': safe_list(trend_data['low']),
                'high': safe_list(trend_data['high']),
                'mid': safe_list(trend_data['mid'])
            }
        },
        'config': {
            'legend': {'show': True},
            'xAxis': {'type': 'category', 'name': '월', 'data': dates},
            'yAxis': {'type': 'value', 'name': '판매량'},
            'series': [
                {
                    'name': f'실판매({current_year})',
                    'type': 'line',
                    'data': safe_list(sales_data),
                    'symbol': 'circle',
                    'symbolSize': 4,
                    'lineStyle': {'width': 2, 'color': '#5470c6'},
                    'connectNulls': True
                }
            ]
        }
    }
    # 전년도 실판매 시계열 추가 (only_product=True일 때만)
    if only_product:
        full_date_range_last = pd.date_range(start=f'{last_year}-01-01', end=f'{last_year}-12-31', freq='D')
        daily_sales_last = df[df['판매일자'].dt.year == last_year].groupby('판매일자')['실판매'].sum()
        daily_sales_last = daily_sales_last.reindex(full_date_range_last)
        sales_data_last = [float(v) if v is not None and not pd.isna(v) else None for v in daily_sales_last.values]
        charts['sales_trend']['config']['series'].append({
            'name': f'실판매({last_year})',
            'type': 'line',
            'data': safe_list(sales_data_last),
            'symbol': 'circle',
            'symbolSize': 4,
            'lineStyle': {'width': 2, 'color': '#91cc75'},
            'connectNulls': True
        })
    if only_product:
        # 전년도 추세선 시리즈 추가
        charts['sales_trend']['config']['series'].extend([
            {
                'name': '저점 추세(LOWESS, 전년도)',
                'type': 'line',
                'data': safe_list(trend_last_year['low']),
                'lineStyle': {'color': '#fac858'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': '고점 추세(LOWESS, 전년도)',
                'type': 'line',
                'data': safe_list(trend_last_year['high']),
                'lineStyle': {'color': '#ee6666'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': '중위 추세(LOWESS, 전년도)',
                'type': 'line',
                'data': safe_list(trend_last_year['mid']),
                'lineStyle': {'color': '#73c0de'},
                'symbol': 'none',
                'connectNulls': True
            }
        ])
    if (only_product and any(v is not None for v in trend_data['low'])) or (not only_product and len(trend_data['low']) > 0):
        charts['sales_trend']['config']['series'].extend([
            {
                'name': '저점 추세(LOWESS)',
                'type': 'line',
                'data': safe_list(trend_data['low']),
                'lineStyle': {'type': 'dashed', 'color': '#3ba272'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': '고점 추세(LOWESS)', 
                'type': 'line',
                'data': safe_list(trend_data['high']),
                'lineStyle': {'type': 'dashed', 'color': '#fc8452'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': '중위 추세(LOWESS)',
                'type': 'line', 
                'data': safe_list(trend_data['mid']),
                'lineStyle': {'type': 'dashed', 'color': '#9a60b4'},
                'symbol': 'none',
                'connectNulls': True
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

        # 올해(예: 2025)와 전년도(예: 2024)만 plot
        df_current_year = df_copy[df_copy['판매일자'].dt.year == current_year]
        df_last_year = df_copy[df_copy['판매일자'].dt.year == last_year]

        # legend와 series 순서 명확히 지정
        legend_data = []
        series_list = []

        if not df_current_year.empty and df_current_year['실판매'].sum() > 0:
            df_current_year['주차'] = df_current_year['판매일자'].dt.isocalendar().week
            weekly_sales = df_current_year.groupby('주차')['실판매'].sum().reset_index()
            weekly_sales = weekly_sales.sort_values('주차')
            legend_data.append(f'실판매({current_year})')
            series_list.append({
                'name': f'실판매({current_year})',
                'type': 'line',
                'data': weekly_sales['실판매'].tolist(),
                'symbol': 'circle',
                'symbolSize': 4,
                'lineStyle': {'width': 2, 'color': '#5470c6'},
                'connectNulls': True
            })
            last_week = weekly_sales[weekly_sales['실판매'] > 0]['주차'].max() if (weekly_sales['실판매'] > 0).any() else 1
        else:
            weekly_sales = None
            last_week = 1

        if not df_last_year.empty and df_last_year['실판매'].sum() > 0:
            df_last_year['주차'] = df_last_year['판매일자'].dt.isocalendar().week
            weekly_sales_last = df_last_year.groupby('주차')['실판매'].sum().reset_index()
            weekly_sales_last = weekly_sales_last.sort_values('주차')
            legend_data.append(f'실판매({last_year})')
            series_list.append({
                'name': f'실판매({last_year})',
                'type': 'line',
                'data': weekly_sales_last['실판매'].tolist(),
                'symbol': 'circle',
                'symbolSize': 4,
                'lineStyle': {'width': 2, 'color': '#91cc75'},
                'connectNulls': True
            })
        else:
            weekly_sales_last = None

        # 월별 표시를 위한 주차 변환
        month_ticks = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45]
        month_labels = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']
        
        charts['weekly_sales_chart'] = {
            'type': 'line',
            'title': '주별 판매량',
            'data': {
                'weeks': weekly_sales['주차'][:last_week].tolist() if weekly_sales is not None else [],
                'values': weekly_sales['실판매'][:last_week].tolist() if weekly_sales is not None else []
            },
            'config': {
                'xAxis': {
                    'type': 'category',
                    'name': '월',
                    'data': weekly_sales['주차'][:last_week].tolist() if weekly_sales is not None else [],
                    'axisLabel': {'rotate': 30, 'interval': 0}
                },
                'yAxis': {'type': 'value', 'name': '판매량'},
                'series': series_list,
                'legend': {'data': legend_data}
            }
        }

        # 전년도 plot
        if not df_last_year.empty and df_last_year['실판매'].sum() > 0:
            df_last_year['주차'] = df_last_year['판매일자'].dt.isocalendar().week
            weekly_sales_last = df_last_year.groupby('주차')['실판매'].sum().reset_index()
            weekly_sales_last = weekly_sales_last.sort_values('주차')
            
            charts['lastyear_weekly_trend'] = {
                'type': 'line',
                'title': f'{last_year}년 주별 판매 트렌드',
                'data': {
                    'weeks': weekly_sales_last['주차'].tolist(),
                    'values': weekly_sales_last['실판매'].tolist()
                },
                'config': {
                    'xAxis': {'type': 'category', 'name': '월', 'data': weekly_sales_last['주차'].tolist()},
                    'yAxis': {'type': 'value', 'name': '판매량'},
                    'series': [{
                        'name': '판매량',
                        'type': 'line',
                        'data': weekly_sales_last['실판매'].tolist(),
                        'symbol': 'circle',
                        'symbolSize': 4,
                        'lineStyle': {'color': '#4ECDC4'}
                    }]
                }
            }
            
            # 예측값 계산
            # (전년도 분석 코드가 삭제되었으므로, x, lastyear_daily, mid_trend, sales 등 관련 예측 및 신뢰도 계산 코드도 함께 삭제)
            pass # 예측값 계산 코드 제거
    
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
    
    # --- 주별 실판매 및 추세선 (올해/전년도, 비교 상품 포함) ---
    if only_product:
        week_range = range(1, 54)
        # 기존 상품 데이터
        df['주차'] = df['판매일자'].dt.isocalendar().week
        weekly_this = df[df['판매일자'].dt.year == current_year].groupby('주차')['실판매'].sum().reindex(week_range, fill_value=0)
        weekly_last = df[df['판매일자'].dt.year == last_year].groupby('주차')['실판매'].sum().reindex(week_range, fill_value=0)
        # LOWESS 기반 추세선 계산 (일별과 동일)
        def pad_trend_week(trend, valid_indices, length):
            arr = [None] * length
            for idx, v in zip(valid_indices, trend):
                arr[idx] = float(v) if v is not None else None
            return list(arr)
        # 올해
        sales_this = weekly_this.values.tolist()
        valid_idx_this = [i for i, v in enumerate(sales_this) if v is not None and v != 0]
        valid_sales_this = [sales_this[i] for i in valid_idx_this]
        if valid_sales_this:
            low_this = pad_trend_week(trend_calculator.lower_trend(valid_sales_this), valid_idx_this, len(sales_this))
            high_this = pad_trend_week(trend_calculator.upper_trend(valid_sales_this), valid_idx_this, len(sales_this))
            mid_this = pad_trend_week(trend_calculator.mid_trend(valid_sales_this), valid_idx_this, len(sales_this))
        else:
            low_this = high_this = mid_this = [None] * len(sales_this)
        # 전년도
        sales_last = weekly_last.values.tolist()
        valid_idx_last = [i for i, v in enumerate(sales_last) if v is not None and v != 0]
        valid_sales_last = [sales_last[i] for i in valid_idx_last]
        if valid_sales_last:
            low_last = pad_trend_week(trend_calculator.lower_trend(valid_sales_last), valid_idx_last, len(sales_last))
            high_last = pad_trend_week(trend_calculator.upper_trend(valid_sales_last), valid_idx_last, len(sales_last))
            mid_last = pad_trend_week(trend_calculator.mid_trend(valid_sales_last), valid_idx_last, len(sales_last))
        else:
            low_last = high_last = mid_last = [None] * len(sales_last)
        charts['weekly_sales_trend'] = {
            'type': 'line',
            'title': '주별 판매 추세',
            'data': {
                'weeks': list(week_range),
                'sales_this': sales_this,
                'sales_last': sales_last,
                'low_this': low_this,
                'high_this': high_this,
                'mid_this': mid_this,
                'low_last': low_last,
                'high_last': high_last,
                'mid_last': mid_last
            },
            'config': {
                'legend': {
                    'show': True,
                    'top': 0,
                    'left': 'center',
                    'orient': 'horizontal',
                    'data': [
                        f'실판매({current_year})',
                        f'실판매({last_year})',
                        '저점 추세(LOWESS, 전년도)',
                        '고점 추세(LOWESS, 전년도)',
                        '중위 추세(LOWESS, 전년도)',
                        '저점 추세(LOWESS)',
                        '고점 추세(LOWESS)',
                        '중위 추세(LOWESS)'
                    ]
                },
                'xAxis': {'type': 'category', 'name': '주', 'data': list(week_range)},
                'yAxis': {'type': 'value', 'name': '판매량'},
                'series': [
                    {
                        'name': f'실판매({current_year})',
                        'type': 'line',
                        'data': sales_this,
                        'symbol': 'circle',
                        'symbolSize': 4,
                        'lineStyle': {'width': 2, 'color': '#5470c6'},
                        'connectNulls': True
                    },
                    {
                        'name': f'실판매({last_year})',
                        'type': 'line',
                        'data': sales_last,
                        'symbol': 'circle',
                        'symbolSize': 4,
                        'lineStyle': {'width': 2, 'color': '#91cc75'},
                        'connectNulls': True
                    },
                    {
                        'name': '저점 추세(LOWESS, 전년도)',
                        'type': 'line',
                        'data': low_last,
                        'lineStyle': {'color': '#fac858'},
                        'symbol': 'none',
                        'connectNulls': True
                    },
                    {
                        'name': '고점 추세(LOWESS, 전년도)',
                        'type': 'line',
                        'data': high_last,
                        'lineStyle': {'color': '#ee6666'},
                        'symbol': 'none',
                        'connectNulls': True
                    },
                    {
                        'name': '중위 추세(LOWESS, 전년도)',
                        'type': 'line',
                        'data': mid_last,
                        'lineStyle': {'color': '#73c0de'},
                        'symbol': 'none',
                        'connectNulls': True
                    },
                    {
                        'name': '저점 추세(LOWESS)',
                        'type': 'line',
                        'data': low_this,
                        'lineStyle': {'type': 'dashed', 'color': '#3ba272'},
                        'symbol': 'none',
                        'connectNulls': True
                    },
                    {
                        'name': '고점 추세(LOWESS)',
                        'type': 'line',
                        'data': high_this,
                        'lineStyle': {'type': 'dashed', 'color': '#fc8452'},
                        'symbol': 'none',
                        'connectNulls': True
                    },
                    {
                        'name': '중위 추세(LOWESS)',
                        'type': 'line',
                        'data': mid_this,
                        'lineStyle': {'type': 'dashed', 'color': '#9a60b4'},
                        'symbol': 'none',
                        'connectNulls': True
                    }
                ]
            }
        }
        # 비교 상품 데이터 처리
        compare_series = []
        compare_legend = []
        if compare_df is not None:
            compare_df = compare_df.copy()
            compare_df['판매일자'] = pd.to_datetime(compare_df['판매일자'])
            compare_df['주차'] = compare_df['판매일자'].dt.isocalendar().week
            # 올해
            weekly_this_cmp = compare_df[compare_df['판매일자'].dt.year == current_year].groupby('주차')['실판매'].sum().reindex(week_range, fill_value=0)
            sales_this_cmp = weekly_this_cmp.values.tolist()
            valid_idx_this_cmp = [i for i, v in enumerate(sales_this_cmp) if v is not None and v != 0]
            valid_sales_this_cmp = [sales_this_cmp[i] for i in valid_idx_this_cmp]
            if valid_sales_this_cmp:
                low_this_cmp = pad_trend_week(trend_calculator.lower_trend(valid_sales_this_cmp), valid_idx_this_cmp, len(sales_this_cmp))
                high_this_cmp = pad_trend_week(trend_calculator.upper_trend(valid_sales_this_cmp), valid_idx_this_cmp, len(sales_this_cmp))
                mid_this_cmp = pad_trend_week(trend_calculator.mid_trend(valid_sales_this_cmp), valid_idx_this_cmp, len(sales_this_cmp))
            else:
                low_this_cmp = high_this_cmp = mid_this_cmp = [None] * len(sales_this_cmp)
            # 작년
            weekly_last_cmp = compare_df[compare_df['판매일자'].dt.year == last_year].groupby('주차')['실판매'].sum().reindex(week_range, fill_value=0)
            sales_last_cmp = weekly_last_cmp.values.tolist()
            valid_idx_last_cmp = [i for i, v in enumerate(sales_last_cmp) if v is not None and v != 0]
            valid_sales_last_cmp = [sales_last_cmp[i] for i in valid_idx_last_cmp]
            if valid_sales_last_cmp:
                low_last_cmp = pad_trend_week(trend_calculator.lower_trend(valid_sales_last_cmp), valid_idx_last_cmp, len(sales_last_cmp))
                high_last_cmp = pad_trend_week(trend_calculator.upper_trend(valid_sales_last_cmp), valid_idx_last_cmp, len(sales_last_cmp))
                mid_last_cmp = pad_trend_week(trend_calculator.mid_trend(valid_sales_last_cmp), valid_idx_last_cmp, len(sales_last_cmp))
            else:
                low_last_cmp = high_last_cmp = mid_last_cmp = [None] * len(sales_last_cmp)
            # 시리즈/범례 추가 (순서 반드시 일치)
            compare_series += [
                {
                    'name': f'비교-실판매({current_year})',
                    'type': 'line',
                    'data': sales_this_cmp,
                    'symbol': 'circle',
                    'symbolSize': 4,
                    'lineStyle': {'width': 2, 'color': '#e573b7'},
                    'connectNulls': True
                },
                {
                    'name': f'비교-실판매({last_year})',
                    'type': 'line',
                    'data': sales_last_cmp,
                    'symbol': 'circle',
                    'symbolSize': 4,
                    'lineStyle': {'width': 2, 'color': '#64b5f6'},
                    'connectNulls': True
                },
                {
                    'name': '비교-저점 추세(LOWESS, 전년도)',
                    'type': 'line',
                    'data': low_last_cmp,
                    'lineStyle': {'color': '#aed581'},
                    'symbol': 'none',
                    'connectNulls': True
                },
                {
                    'name': '비교-고점 추세(LOWESS, 전년도)',
                    'type': 'line',
                    'data': high_last_cmp,
                    'lineStyle': {'color': '#ffb74d'},
                    'symbol': 'none',
                    'connectNulls': True
                },
                {
                    'name': '비교-중위 추세(LOWESS, 전년도)',
                    'type': 'line',
                    'data': mid_last_cmp,
                    'lineStyle': {'color': '#ff8a65'},
                    'symbol': 'none',
                    'connectNulls': True
                },
                {
                    'name': '비교-저점 추세(LOWESS)',
                    'type': 'line',
                    'data': low_this_cmp,
                    'lineStyle': {'type': 'dashed', 'color': '#ba68c8'},
                    'symbol': 'none',
                    'connectNulls': True
                },
                {
                    'name': '비교-고점 추세(LOWESS)',
                    'type': 'line',
                    'data': high_this_cmp,
                    'lineStyle': {'type': 'dashed', 'color': '#4fc3f7'},
                    'symbol': 'none',
                    'connectNulls': True
                },
                {
                    'name': '비교-중위 추세(LOWESS)',
                    'type': 'line',
                    'data': mid_this_cmp,
                    'lineStyle': {'type': 'dashed', 'color': '#00bcd4'},
                    'symbol': 'none',
                    'connectNulls': True
                }
            ]
            compare_legend += [
                f'비교-실판매({current_year})',
                f'비교-실판매({last_year})',
                '비교-저점 추세(LOWESS, 전년도)',
                '비교-고점 추세(LOWESS, 전년도)',
                '비교-중위 추세(LOWESS, 전년도)',
                '비교-저점 추세(LOWESS)',
                '비교-고점 추세(LOWESS)',
                '비교-중위 추세(LOWESS)'
            ]
        # 기존 시리즈/범례와 합침 (순서 반드시 일치)
        charts['weekly_sales_trend']['config']['series'].extend(compare_series)
        charts['weekly_sales_trend']['config']['legend']['data'].extend(compare_legend)

    # charts['sales_trend'] 생성 후, 반환 직전 안전하게 변환
    charts['sales_trend']['data']['sales'] = safe_list(charts['sales_trend']['data']['sales'])
    charts['sales_trend']['data']['trends']['low'] = safe_list(charts['sales_trend']['data']['trends']['low'])
    charts['sales_trend']['data']['trends']['high'] = safe_list(charts['sales_trend']['data']['trends']['high'])
    charts['sales_trend']['data']['trends']['mid'] = safe_list(charts['sales_trend']['data']['trends']['mid'])
    for s in charts['sales_trend']['config']['series']:
        if 'data' in s:
            s['data'] = safe_list(s['data'])

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