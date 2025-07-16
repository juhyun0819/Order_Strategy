import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from .trend_calculator import TrendCalculator

def interpolate_trend(data_indices, trend_values, total_length):
    """추세선을 전체 주차에 연속적으로 보간"""
    if not data_indices or len(trend_values) == 0:
        return [0] * total_length
    
    # 데이터가 있는 주차의 추세값을 전체 주차에 보간
    result = [0] * total_length
    
    # 데이터가 있는 주차에 추세값 설정
    for idx, value in zip(data_indices, trend_values):
        if 0 <= idx < total_length:
            result[idx] = value
    
    # 데이터가 없는 구간을 선형 보간으로 채움
    for i in range(1, len(data_indices)):
        start_idx = data_indices[i-1]
        end_idx = data_indices[i]
        start_val = result[start_idx]
        end_val = result[end_idx]
        
        # 중간 구간을 선형 보간
        for j in range(start_idx + 1, end_idx):
            if j < total_length:
                ratio = (j - start_idx) / (end_idx - start_idx)
                result[j] = start_val + (end_val - start_val) * ratio
    
    # 첫 번째 데이터 이전 구간 처리
    if data_indices and data_indices[0] > 0:
        first_val = result[data_indices[0]]
        for i in range(data_indices[0]):
            result[i] = first_val
    
    # 마지막 데이터 이후 구간 처리
    if data_indices and data_indices[-1] < total_length - 1:
        last_val = result[data_indices[-1]]
        for i in range(data_indices[-1] + 1, total_length):
            result[i] = last_val
    
    return result

def calculate_calendar_week(date):
    """실제 달력 기준으로 주차를 계산합니다."""
    # ISO 주차 계산 사용
    iso_week = date.isocalendar()
    week_number = iso_week[1]  # ISO 주차
    
    # 주차 범위 제한 (1-53)
    week_number = max(1, min(53, week_number))
    
    return week_number

def create_sales_trend_chart(df, only_product=False, all_dates=None, trend_window=7, trend_frac=0.08, compare_df=None):
    """판매 추세 그래프 생성 (일별)"""
    current_year = datetime.now().year
    last_year = current_year - 1
    trend_calculator = TrendCalculator(window=trend_window, frac=trend_frac)
    
    # 비교 데이터 처리
    compare_data = None
    if compare_df is not None and not compare_df.empty:
        compare_data = process_compare_data(compare_df, current_year)
    
    if only_product:
        # 상품별 상세 페이지용 - 전체 연도 표시
        full_date_range = pd.date_range(start=f'{current_year}-01-01', end=f'{current_year}-12-31', freq='D')
        df = df.copy()
        df['판매일자'] = pd.to_datetime(df['판매일자'])
        daily_sales = df.groupby('판매일자')['실판매'].sum()
        daily_sales = daily_sales.reindex(full_date_range)
        dates = full_date_range.strftime('%Y-%m-%d').tolist()
        sales_data = [float(v) if v is not None and not pd.isna(v) else None for v in daily_sales.values]
        
        # 추세선 계산
        valid_indices = [i for i, v in enumerate(sales_data) if v is not None]
        valid_sales = [sales_data[i] for i in valid_indices]
        
        if valid_sales:
            # 추세선을 전체 날짜에 연속적으로 보간
            low_trend = interpolate_trend(valid_indices, trend_calculator.lower_trend(valid_sales), len(sales_data))
            high_trend = interpolate_trend(valid_indices, trend_calculator.upper_trend(valid_sales), len(sales_data))
            mid_trend = interpolate_trend(valid_indices, trend_calculator.mid_trend(valid_sales), len(sales_data))
        else:
            low_trend = high_trend = mid_trend = [0] * len(sales_data)
        
        trend_data = {
            'low': low_trend,
            'high': high_trend,
            'mid': mid_trend
        }
        
        # 전년도 데이터 추가
        trend_last_year = get_yearly_trend(df, last_year, trend_calculator)
        
    else:
        # 메인 대시보드용 - 데이터가 있는 날짜만 표시
        df = df.copy()
        df['판매일자'] = pd.to_datetime(df['판매일자'])
        df = df[df['판매일자'].dt.year == current_year]
        daily_sales = df.groupby('판매일자')['실판매'].sum().reset_index()
        daily_sales = daily_sales[daily_sales['실판매'] != 0]
        dates = daily_sales['판매일자'].dt.strftime('%Y-%m-%d').tolist() if not daily_sales.empty else []
        sales_data = [float(v) if v is not None and not pd.isna(v) else None for v in (daily_sales['실판매'].tolist() if not daily_sales.empty else [])]
        
        if sales_data:
            low_trend = [float(v) if v is not None else 0 for v in trend_calculator.lower_trend(sales_data)]
            high_trend = [float(v) if v is not None else 0 for v in trend_calculator.upper_trend(sales_data)]
            mid_trend = [float(v) if v is not None else 0 for v in trend_calculator.mid_trend(sales_data)]
        else:
            low_trend = high_trend = mid_trend = []
        
        trend_data = {
            'low': low_trend if len(low_trend) > 0 else [],
            'high': high_trend if len(high_trend) > 0 else [],
            'mid': mid_trend if len(mid_trend) > 0 else []
        }
        trend_last_year = None
    
    # 차트 설정
    series = [
        {
            'name': f'실판매({current_year})',
            'type': 'line',
            'data': safe_list(sales_data),
            'symbol': 'circle',
            'symbolSize': 4,
            'lineStyle': {'width': 2, 'color': '#5470c6'},
            'itemStyle': {'color': '#5470c6'},
            'connectNulls': True
        }
    ]
    
    # 비교 데이터 추가
    if compare_data:
        print(f"비교 데이터를 그래프에 추가합니다. 데이터 길이: {len(compare_data)}")
        series.append({
            'name': '비교상품 판매량',
            'type': 'line',
            'data': safe_list(compare_data),
            'symbol': 'diamond',
            'symbolSize': 6,
            'lineStyle': {'width': 2, 'color': '#ff6b6b'},
            'itemStyle': {'color': '#ff6b6b'},
            'connectNulls': True
        })
    else:
        print("비교 데이터가 없습니다.")
    
    # 전년도 데이터 추가 (only_product=True일 때만)
    if only_product and trend_last_year:
        full_date_range_last = pd.date_range(start=f'{last_year}-01-01', end=f'{last_year}-12-31', freq='D')
        daily_sales_last = df[df['판매일자'].dt.year == last_year].groupby('판매일자')['실판매'].sum()
        daily_sales_last = daily_sales_last.reindex(full_date_range_last)
        sales_data_last = [float(v) if v is not None and not pd.isna(v) else None for v in daily_sales_last.values]
        
        series.append({
            'name': f'실판매({last_year})',
            'type': 'line',
            'data': safe_list(sales_data_last),
            'symbol': 'circle',
            'symbolSize': 4,
            'lineStyle': {'width': 2, 'color': '#91cc75'},
            'itemStyle': {'color': '#91cc75'},
            'connectNulls': True
        })
        
        # 전년도 추세선 추가
        series.extend([
            {
                'name': f'저점 추세({last_year})',
                'type': 'line',
                'data': safe_list(trend_last_year['low']),
                'lineStyle': {'color': '#fac858'},
                'itemStyle': {'color': '#fac858'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': f'고점 추세({last_year})',
                'type': 'line',
                'data': safe_list(trend_last_year['high']),
                'lineStyle': {'color': '#ee6666'},
                'itemStyle': {'color': '#ee6666'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': f'중위 추세({last_year})',
                'type': 'line',
                'data': safe_list(trend_last_year['mid']),
                'lineStyle': {'color': '#73c0de'},
                'itemStyle': {'color': '#73c0de'},
                'symbol': 'none',
                'connectNulls': True
            }
        ])
    
    # 올해 추세선 추가
    if (only_product and any(v is not None for v in trend_data['low'])) or (not only_product and len(trend_data['low']) > 0):
        series.extend([
            {
                'name': f'저점 추세({current_year})',
                'type': 'line',
                'data': safe_list(trend_data['low']),
                'lineStyle': {'type': 'dashed', 'color': '#3ba272'},
                'itemStyle': {'color': '#3ba272'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': f'고점 추세({current_year})', 
                'type': 'line',
                'data': safe_list(trend_data['high']),
                'lineStyle': {'type': 'dashed', 'color': '#fc8452'},
                'itemStyle': {'color': '#fc8452'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': f'중위 추세({current_year})',
                'type': 'line', 
                'data': safe_list(trend_data['mid']),
                'lineStyle': {'type': 'dashed', 'color': '#9a60b4'},
                'itemStyle': {'color': '#9a60b4'},
                'symbol': 'none',
                'connectNulls': True
            }
        ])
    
    return {
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
            'series': series
        }
    }

def create_weekly_sales_chart(df, weekly_client_data=None):
    """주별 판매량 그래프 생성"""
    current_year = datetime.now().year
    last_year = current_year - 1
    trend_calculator = TrendCalculator(window=5, frac=0.3)  # 주별 데이터용 설정
    
    if df.empty:
        return None
    
    df_copy = df.copy()
    df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
    
    # 올해와 전년도 데이터
    df_current_year = df_copy[df_copy['판매일자'].dt.year == current_year]
    df_last_year = df_copy[df_copy['판매일자'].dt.year == last_year]
    
    legend_data = []
    series_list = []
    
    # 모든 주차 데이터 수집
    all_weeks = set()
    
    # 추세선 변수 초기화
    low_trend = high_trend = mid_trend = []
    
    # 2025년 데이터가 있는지 확인
    has_current_year_data = not df_current_year.empty and df_current_year['실판매'].sum() > 0
    
    # 올해 데이터 처리
    if has_current_year_data:
        # 실제 달력 기준 주차 계산
        df_current_year['주차'] = df_current_year['판매일자'].apply(calculate_calendar_week)
        weekly_sales = df_current_year.groupby('주차')['실판매'].sum().reset_index()
        weekly_sales = weekly_sales.sort_values('주차')
        current_weeks = [f"{week}주차" for week in weekly_sales['주차'].tolist()]
        current_values = weekly_sales['실판매'].tolist()
        all_weeks.update(weekly_sales['주차'].tolist())
        
        # 올해 추세선 계산
        if len(current_values) > 2:
            low_trend = safe_list(trend_calculator.lower_trend(current_values))
            high_trend = safe_list(trend_calculator.upper_trend(current_values))
            mid_trend = safe_list(trend_calculator.mid_trend(current_values))
        else:
            low_trend = high_trend = mid_trend = current_values
        
        legend_data.extend([
            f'실판매({current_year})',
            f'실판매({last_year})',
            f'저점 추세({current_year})',
            f'고점 추세({current_year})',
            f'중위 추세({current_year})',
            f'저점 추세({last_year})',
            f'고점 추세({last_year})',
            f'중위 추세({last_year})'
        ])
        
        series_list.extend([
            {
                'name': f'실판매({current_year})',
                'type': 'line',
                'data': current_values,
                'symbol': 'circle',
                'symbolSize': 4,
                'lineStyle': {'width': 2, 'color': '#5470c6'},
                'itemStyle': {'color': '#5470c6'},
                'connectNulls': False
            }
        ])
        last_week = weekly_sales[weekly_sales['실판매'] > 0]['주차'].max() if (weekly_sales['실판매'] > 0).any() else 1
    else:
        current_weeks = []
        current_values = []
        last_week = 1
    
    # 전년도 데이터 처리
    if not df_last_year.empty:
        # 2025년 데이터가 있으면 2025년 기준으로, 없으면 2024년 기준으로 주차 계산
        if has_current_year_data:
            # 2025년 데이터가 있는 경우: 2025년 기준으로 주차 계산
            df_last_year['주차'] = df_last_year['판매일자'].apply(calculate_calendar_week)
        else:
            # 2025년 데이터가 없는 경우: 2024년 기준으로 주차 계산
            df_last_year['주차'] = df_last_year['판매일자'].apply(lambda x: x.isocalendar()[1])
        
        weekly_sales_last = df_last_year.groupby('주차')['실판매'].sum().reset_index()
        weekly_sales_last = weekly_sales_last.sort_values('주차')
        last_year_weeks = [f"{week}주차" for week in weekly_sales_last['주차'].tolist()]
        last_year_values = weekly_sales_last['실판매'].tolist()
        all_weeks.update(weekly_sales_last['주차'].tolist())
        
        # 전년도 추세선 계산
        if len(last_year_values) > 2:
            last_low_trend = safe_list(trend_calculator.lower_trend(last_year_values))
            last_high_trend = safe_list(trend_calculator.upper_trend(last_year_values))
            last_mid_trend = safe_list(trend_calculator.mid_trend(last_year_values))
        else:
            last_low_trend = last_high_trend = last_mid_trend = last_year_values
        
        # 전년도 실판매를 두 번째 위치에 추가
        series_list.append({
            'name': f'실판매({last_year})',
            'type': 'line',
            'data': last_year_values,
            'symbol': 'circle',
            'symbolSize': 4,
            'lineStyle': {'width': 2, 'color': '#91cc75'},
            'itemStyle': {'color': '#91cc75'},
            'connectNulls': False
        })
        
        # 올해 추세선을 전년도 실판매 뒤에 추가
        series_list.extend([
            {
                'name': f'저점 추세({current_year})',
                'type': 'line',
                'data': low_trend,
                'lineStyle': {'type': 'dashed', 'color': '#3ba272'},
                'itemStyle': {'color': '#3ba272'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': f'고점 추세({current_year})',
                'type': 'line',
                'data': high_trend,
                'lineStyle': {'type': 'dashed', 'color': '#fc8452'},
                'itemStyle': {'color': '#fc8452'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': f'중위 추세({current_year})',
                'type': 'line',
                'data': mid_trend,
                'lineStyle': {'type': 'dashed', 'color': '#9a60b4'},
                'itemStyle': {'color': '#9a60b4'},
                'symbol': 'none',
                'connectNulls': True
            }
        ])
        
        # 전년도 추세선을 마지막에 추가
        series_list.extend([
            {
                'name': f'저점 추세({last_year})',
                'type': 'line',
                'data': last_low_trend,
                'lineStyle': {'color': '#fac858'},
                'itemStyle': {'color': '#fac858'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': f'고점 추세({last_year})',
                'type': 'line',
                'data': last_high_trend,
                'lineStyle': {'color': '#ee6666'},
                'itemStyle': {'color': '#ee6666'},
                'symbol': 'none',
                'connectNulls': True
            },
            {
                'name': f'중위 추세({last_year})',
                'type': 'line',
                'data': last_mid_trend,
                'lineStyle': {'color': '#73c0de'},
                'itemStyle': {'color': '#73c0de'},
                'symbol': 'none',
                'connectNulls': True
            }
        ])
    
    # 주차별 거래처 수 데이터 추가
    if weekly_client_data:
        legend_data.append('거래처 수')
        series_list.append({
            'name': '거래처 수',
            'type': 'bar',
            'yAxisIndex': 1,  # 두 번째 y축 사용
            'data': weekly_client_data,
            'itemStyle': {'color': '#ff6b6b'},
            'barWidth': '60%'
        })
    
    # 항상 1-53주차로 고정
    x_axis_data = [str(week) for week in range(1, 54)]
    week_to_index = {week: idx for idx, week in enumerate(range(1, 54))}
    
    # 올해 데이터를 전체 주차에 매핑
    if has_current_year_data:
        # 실제 판매량은 데이터가 있는 주차만 표시 (None으로 설정)
        current_mapped_values = [None] * len(x_axis_data)
        for week, value in zip(weekly_sales['주차'].tolist(), current_values):
            if week in week_to_index:
                current_mapped_values[week_to_index[week]] = value
        
        # 올해 추세선 계산 및 매핑
        if len(current_values) > 2:
            low_trend = safe_list(trend_calculator.lower_trend(current_values))
            high_trend = safe_list(trend_calculator.upper_trend(current_values))
            mid_trend = safe_list(trend_calculator.mid_trend(current_values))
        else:
            low_trend = high_trend = mid_trend = current_values
        
        # 추세선을 전체 주차에 연속적으로 매핑
        # 데이터가 있는 주차의 인덱스를 찾아서 추세선을 보간
        data_weeks = weekly_sales['주차'].tolist()
        data_indices = [week_to_index[week] for week in data_weeks if week in week_to_index]
        
        # 추세선을 전체 주차에 보간
        low_trend_mapped = interpolate_trend(data_indices, low_trend, len(x_axis_data))
        high_trend_mapped = interpolate_trend(data_indices, high_trend, len(x_axis_data))
        mid_trend_mapped = interpolate_trend(data_indices, mid_trend, len(x_axis_data))
        
        # 시리즈 업데이트
        series_list[0]['data'] = current_mapped_values  # 실판매(2025)
        series_list[2]['data'] = low_trend_mapped      # 저점 추세
        series_list[3]['data'] = high_trend_mapped     # 고점 추세
        series_list[4]['data'] = mid_trend_mapped      # 중위 추세
    
    # 전년도 데이터를 전체 주차에 매핑
    last_year_mapped_values = [None] * len(x_axis_data)  # 기본값으로 None 배열 초기화
    
    if not df_last_year.empty:
        # 실제 판매량은 데이터가 있는 주차만 표시 (None으로 설정)
        last_year_mapped_values = [None] * len(x_axis_data)
        for week, value in zip(weekly_sales_last['주차'].tolist(), last_year_values):
            if week in week_to_index:
                last_year_mapped_values[week_to_index[week]] = value
        
        # 전년도 추세선 계산 및 매핑
        if len(last_year_values) > 2:
            last_low_trend = safe_list(trend_calculator.lower_trend(last_year_values))
            last_high_trend = safe_list(trend_calculator.upper_trend(last_year_values))
            last_mid_trend = safe_list(trend_calculator.mid_trend(last_year_values))
        else:
            last_low_trend = last_high_trend = last_mid_trend = last_year_values
        
        # 전년도 추세선을 전체 주차에 연속적으로 매핑
        last_data_weeks = weekly_sales_last['주차'].tolist()
        last_data_indices = [week_to_index[week] for week in last_data_weeks if week in week_to_index]
        
        # 전년도 추세선을 전체 주차에 보간
        last_low_trend_mapped = interpolate_trend(last_data_indices, last_low_trend, len(x_axis_data))
        last_high_trend_mapped = interpolate_trend(last_data_indices, last_high_trend, len(x_axis_data))
        last_mid_trend_mapped = interpolate_trend(last_data_indices, last_mid_trend, len(x_axis_data))
        
        # 전년도 시리즈 업데이트 (전년도 데이터가 있을 때만)
        if len(series_list) >= 8:  # 전년도 시리즈가 추가되었을 때만
            series_list[1]['data'] = last_year_mapped_values  # 실판매(2024)
            series_list[5]['data'] = last_low_trend_mapped    # 저점 추세(2024)
            series_list[6]['data'] = last_high_trend_mapped   # 고점 추세(2024)
            series_list[7]['data'] = last_mid_trend_mapped    # 중위 추세(2024)
        elif not has_current_year_data:
            # 2025년 데이터가 없고 2024년 데이터만 있는 경우: 시리즈를 직접 업데이트
            if len(series_list) >= 4:
                series_list[0]['data'] = last_year_mapped_values  # 실판매
                series_list[1]['data'] = last_low_trend_mapped    # 저점 추세
                series_list[2]['data'] = last_high_trend_mapped   # 고점 추세
                series_list[3]['data'] = last_mid_trend_mapped    # 중위 추세
                
                # 시리즈 이름도 2024년으로 수정
                series_list[0]['name'] = f'실판매({last_year})'
                series_list[1]['name'] = f'저점 추세({last_year})'
                series_list[2]['name'] = f'고점 추세({last_year})'
                series_list[3]['name'] = f'중위 추세({last_year})'
    
    # 전년도 데이터가 없어도 series_list[1]에 None 배열 할당
    if len(series_list) >= 2 and not df_last_year.empty:
        series_list[1]['data'] = last_year_mapped_values  # 실판매(2024) - None 배열
    
    # 주차별 거래처 수 데이터 매핑
    if weekly_client_data:
        client_data_mapped = [None] * len(x_axis_data)
        for week, count in weekly_client_data.items():
            if week in week_to_index:
                client_data_mapped[week_to_index[week]] = count
        
        # 거래처 수 시리즈 업데이트 (마지막 시리즈)
        series_list[-1]['data'] = client_data_mapped
    
    # y축 설정 (거래처 수가 있으면 이중 y축 사용)
    y_axis_config = [
        {'type': 'value', 'name': '판매량', 'position': 'left'},
    ]
    
    if weekly_client_data:
        y_axis_config.append({
            'type': 'value', 
            'name': '거래처 수', 
            'position': 'right',
            'axisLine': {'show': True, 'lineStyle': {'color': '#ff6b6b'}},
            'axisLabel': {'color': '#ff6b6b'}
        })
    
    return {
        'type': 'line',
        'title': '주별 판매량',
        'data': {
            'weeks': current_weeks,
            'values': current_values
        },
        'config': {
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {
                    'show': False
                },
                'formatter': 'function(params) { var result = params[0].axisValue + "주차<br/>"; params.forEach(function(param) { if (param.value !== null && param.value !== undefined) { result += param.marker + param.seriesName + ": " + param.value + "<br/>"; } }); return result; }'
            },
            'xAxis': {
                'type': 'category',
                'name': '주차',
                'data': x_axis_data,
                'axisLabel': {'rotate': 30, 'interval': 0}
            },
            'yAxis': y_axis_config,
            'series': series_list,
            'legend': {'data': legend_data}
        }
    }

def create_product_sales_chart(df):
    """상품별 판매량 그래프 생성"""
    if '품명' not in df.columns or '실판매' not in df.columns:
        return None
    
    product_sales = df.groupby('품명')['실판매'].sum().sort_values(ascending=False).head(10)
    
    return {
        'type': 'bar',
        'title': '상품별 판매량',
        'data': {
            'categories': product_sales.index.tolist() if not product_sales.empty else [],
            'values': product_sales.values.tolist() if not product_sales.empty else []
        },
        'config': {
            'xAxis': {
                'type': 'category', 
                'name': '품명', 
                'data': product_sales.index.tolist() if not product_sales.empty else [], 
                'axisLabel': {'rotate': 30, 'interval': 0}
            },
            'yAxis': {'type': 'value', 'name': '실판매'},
            'series': [{
                'name': '판매량',
                'type': 'bar',
                'data': product_sales.values.tolist() if not product_sales.empty else [],
                'itemStyle': {'color': '#73c0de'}
            }]
        }
    }

def create_color_sales_chart(df):
    """컬러별 판매량 그래프 생성"""
    if '칼라' not in df.columns or '실판매' not in df.columns:
        return None
    
    color_sales = df.groupby('칼라')['실판매'].sum().sort_values(ascending=False).head(10)
    
    return {
        'type': 'bar',
        'title': '컬러별 판매량',
        'data': {
            'categories': color_sales.index.tolist(),
            'values': color_sales.values.tolist()
        },
        'config': {
            'xAxis': {
                'type': 'category', 
                'name': '컬러', 
                'data': color_sales.index.tolist(), 
                'axisLabel': {'rotate': 30, 'interval': 0}
            },
            'yAxis': {'type': 'value', 'name': '실판매'},
            'series': [{
                'name': '판매량',
                'type': 'bar',
                'data': color_sales.values.tolist(),
                'itemStyle': {'color': '#fc8452'}
            }]
        }
    }

def create_size_sales_chart(df):
    """사이즈별 판매량 그래프 생성"""
    if '사이즈' not in df.columns or '실판매' not in df.columns:
        return None
    
    size_sales = df.groupby('사이즈')['실판매'].sum().sort_values(ascending=False).head(10)
    
    return {
        'type': 'bar',
        'title': '사이즈별 판매량',
        'data': {
            'categories': size_sales.index.tolist(),
            'values': size_sales.values.tolist()
        },
        'config': {
            'xAxis': {
                'type': 'category', 
                'name': '사이즈', 
                'data': size_sales.index.tolist(), 
                'axisLabel': {'rotate': 30, 'interval': 0}
            },
            'yAxis': {'type': 'value', 'name': '실판매'},
            'series': [{
                'name': '판매량',
                'type': 'bar',
                'data': size_sales.values.tolist(),
                'itemStyle': {'color': '#9a60b4'}
            }]
        }
    }

def create_pareto_analysis_chart(df):
    """파레토 분석 그래프 생성"""
    if '품명' not in df.columns or '실판매' not in df.columns:
        return None
    
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
    
    return {
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

def safe_list(arr):
    """np.ndarray를 list로 변환, 내부 값도 float 또는 None"""
    if hasattr(arr, 'tolist'):
        arr = arr.tolist()
    return [float(v) if v is not None and not (isinstance(v, float) and (v != v)) else None for v in arr]

def process_compare_data(compare_df, current_year):
    """비교 엑셀 파일 데이터 처리"""
    try:
        # 비교 엑셀 파일의 컬럼명을 표준화
        compare_df = compare_df.copy()
        
        print(f"비교 데이터 처리 시작: 컬럼명 = {compare_df.columns.tolist()}")
        print(f"비교 데이터 샘플:\n{compare_df.head()}")
        
        # 날짜와 판매량 컬럼 찾기
        if len(compare_df.columns) >= 2:
            # 날짜 컬럼 찾기 (거래일자, 판매일자, 날짜 등)
            date_col = None
            for col in compare_df.columns:
                if any(keyword in str(col).lower() for keyword in ['거래일자', '판매일자', '날짜', 'date']):
                    date_col = col
                    break
            
            # 판매량 컬럼 찾기 (판매량, 실판매, 수량 등)
            sales_col = None
            for col in compare_df.columns:
                if any(keyword in str(col).lower() for keyword in ['판매량', '실판매', '수량', 'quantity', 'sales']):
                    sales_col = col
                    break
            
            # 컬럼을 찾지 못한 경우 기본값 사용
            if date_col is None:
                date_col = compare_df.columns[0]
            if sales_col is None:
                # 판매량 컬럼이 없으면 숫자 데이터가 있는 컬럼 찾기
                for col in compare_df.columns:
                    if col != date_col and pd.api.types.is_numeric_dtype(compare_df[col]):
                        sales_col = col
                        break
                if sales_col is None and len(compare_df.columns) >= 2:
                    sales_col = compare_df.columns[1]  # 두 번째 컬럼 사용
            
            print(f"날짜 컬럼: {date_col}, 판매량 컬럼: {sales_col}")
            
            # 날짜 컬럼을 datetime으로 변환
            compare_df[date_col] = pd.to_datetime(compare_df[date_col], errors='coerce')
            
            # 판매량 컬럼을 숫자로 변환
            compare_df[sales_col] = pd.to_numeric(compare_df[sales_col], errors='coerce')
            
            print(f"날짜 변환 후 샘플:\n{compare_df.head()}")
            
            # 유효한 데이터만 필터링
            compare_df = compare_df.dropna(subset=[date_col, sales_col])
            
            print(f"유효 데이터 필터링 후 행 수: {len(compare_df)}")
            
            # 현재 연도 데이터만 필터링
            compare_df = compare_df[compare_df[date_col].dt.year == current_year]
            
            print(f"현재 연도 필터링 후 행 수: {len(compare_df)}")
            
            if not compare_df.empty:
                # 전체 연도 날짜 범위 생성
                full_date_range = pd.date_range(start=f'{current_year}-01-01', end=f'{current_year}-12-31', freq='D')
                
                # 날짜별 판매량 집계
                daily_compare = compare_df.groupby(date_col)[sales_col].sum()
                daily_compare = daily_compare.reindex(full_date_range)
                
                print(f"날짜별 집계 후 데이터 수: {len(daily_compare)}")
                print(f"판매량이 있는 날짜 수: {daily_compare.notna().sum()}")
                
                # 판매량 데이터 생성
                compare_data = [float(v) if v is not None and not pd.isna(v) else None for v in daily_compare.values]
                
                # None이 아닌 값이 있는지 확인
                valid_values = [v for v in compare_data if v is not None]
                print(f"유효한 판매량 값 수: {len(valid_values)}")
                if valid_values:
                    print(f"판매량 범위: {min(valid_values)} ~ {max(valid_values)}")
                
                return compare_data
            else:
                print("현재 연도에 유효한 데이터가 없습니다.")
        
        return None
    except Exception as e:
        print(f"비교 데이터 처리 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_yearly_trend(df, year, trend_calculator):
    """연도별 추세 계산"""
    full_date_range = pd.date_range(start=f'{year}-01-01', end=f'{year}-12-31', freq='D')
    df_year = df[df['판매일자'].dt.year == year]
    daily_sales = df_year.groupby('판매일자')['실판매'].sum()
    daily_sales = daily_sales.reindex(full_date_range)
    sales_data = [float(v) if v is not None and not pd.isna(v) else None for v in daily_sales.values]
    valid_indices = [i for i, v in enumerate(sales_data) if v is not None]
    valid_sales = [sales_data[i] for i in valid_indices]
    
    if valid_sales:
        # 추세선을 전체 날짜에 연속적으로 보간
        low_trend = interpolate_trend(valid_indices, trend_calculator.lower_trend(valid_sales), len(sales_data))
        high_trend = interpolate_trend(valid_indices, trend_calculator.upper_trend(valid_sales), len(sales_data))
        mid_trend = interpolate_trend(valid_indices, trend_calculator.mid_trend(valid_sales), len(sales_data))
    else:
        low_trend = high_trend = mid_trend = [0] * len(sales_data)
    
    return {'low': low_trend, 'high': high_trend, 'mid': mid_trend} 