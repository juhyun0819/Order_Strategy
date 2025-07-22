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

def interpolate_sales_data(data_list):
    """실판매 데이터의 연속된 구간들 사이만 연결 (보간된 값은 None으로 유지)"""
    if not data_list:
        return data_list
    
    result = data_list.copy()
    
    # 실제 데이터가 있는 인덱스들 찾기
    data_indices = [i for i, v in enumerate(result) if v is not None]
    
    # 연속된 구간들 사이를 연결하기 위해 보간된 값들을 임시로 계산
    # 하지만 실제로는 None으로 유지
    temp_result = result.copy()
    
    # None 값들을 선형 보간으로 채움 (연속된 구간 내에서만)
    i = 0
    while i < len(temp_result):
        if temp_result[i] is not None:
            i += 1
            continue
        
        # 왼쪽 경계 찾기
        left_idx = i - 1
        left_value = None
        while left_idx >= 0:
            if temp_result[left_idx] is not None:
                left_value = temp_result[left_idx]
                break
            left_idx -= 1
        
        # 오른쪽 경계 찾기
        right_idx = i + 1
        right_value = None
        while right_idx < len(temp_result):
            if temp_result[right_idx] is not None:
                right_value = temp_result[right_idx]
                break
            right_idx += 1
        
        # 보간 수행 (양쪽에 값이 있는 경우에만)
        if left_value is not None and right_value is not None:
            # 양쪽에 값이 있는 경우 선형 보간
            for j in range(left_idx + 1, right_idx):
                if j < len(temp_result):
                    ratio = (j - left_idx) / (right_idx - left_idx)
                    temp_result[j] = left_value + (right_value - left_value) * ratio
        
        i += 1
    
    # 실제 데이터가 있는 인덱스는 원래 값 유지, 나머지는 None으로 설정
    final_result = [None] * len(result)
    for idx in data_indices:
        final_result[idx] = result[idx]
    
    return final_result

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
    print(f"비교 데이터 처리 시작 - compare_df: {compare_df is not None}")
    if compare_df is not None and not compare_df.empty:
        print(f"비교 데이터 처리 - compare_df shape: {compare_df.shape}")
        print(f"비교 데이터 처리 - compare_df columns: {compare_df.columns.tolist()}")
        compare_data = process_compare_data(compare_df, current_year)
        print(f"비교 데이터 처리 결과 - compare_data: {compare_data is not None}")
        if compare_data:
            print(f"비교 데이터 처리 결과 - 데이터 길이: {len(compare_data)}")
            print(f"비교 데이터 처리 결과 - 유효한 값 수: {len([v for v in compare_data if v is not None])}")
    else:
        print("비교 데이터가 없습니다.")
    
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
    
    # 재고 데이터 추가 (2025년 데이터만, 파일 업로드 날짜까지 이전 값 유지)
    inventory_data = []
    pending_data = []
    
    if only_product and not df.empty:
        # 상품별 페이지에서만 재고 데이터 표시
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        
        # 2025년 데이터만 필터링
        df_2025 = df_copy[df_copy['판매일자'].dt.year == current_year]
        
        if not df_2025.empty:
            # 날짜별로 정렬
            df_2025 = df_2025.sort_values('판매일자')
            
            # 해당 상품의 가장 최근 재고 데이터 날짜 찾기
            last_inventory_date = None
            last_pending_date = None
            
            # 현재고와 미송잔량이 있는 마지막 날짜 찾기
            for _, row in df_2025.iterrows():
                if row['현재고'] is not None and not pd.isna(row['현재고']) and row['현재고'] != 0:
                    last_inventory_date = row['판매일자']
                if row['미송잔량'] is not None and not pd.isna(row['미송잔량']) and row['미송잔량'] != 0:
                    last_pending_date = row['판매일자']
            
            # 가장 최근 파일 업로드 날짜 찾기 (전체 데이터에서)
            latest_upload_date = df_copy['판매일자'].max()
            
            # 전체 날짜 범위에 대해 재고 데이터 매핑
            last_inventory = None
            last_pending = None
            
            for date in full_date_range if only_product else dates:
                if only_product:
                    # 전체 연도 표시 모드
                    date_str = date.strftime('%Y-%m-%d')
                    date_dt = pd.to_datetime(date_str)
                else:
                    # 데이터가 있는 날짜만 표시 모드
                    date_str = date
                    date_dt = pd.to_datetime(date_str)
                
                # 해당 날짜의 데이터가 있는지 확인
                date_data = df_2025[df_2025['판매일자'] == date_dt]
                
                if not date_data.empty:
                    # 해당 날짜의 미송잔량과 현재고 합계
                    pending_sum = date_data['미송잔량'].sum()
                    inventory_sum = date_data['현재고'].sum()
                    
                    # 유효한 값인 경우 업데이트
                    if inventory_sum is not None and not pd.isna(inventory_sum) and inventory_sum != 0:
                        last_inventory = float(inventory_sum)
                    if pending_sum is not None and not pd.isna(pending_sum) and pending_sum != 0:
                        last_pending = float(pending_sum)
                
                # 현재 날짜가 가장 최근 파일 업로드 날짜를 넘어서면 None으로 설정
                if date_dt > latest_upload_date:
                    last_inventory = None
                    last_pending = None
                
                # 현재 날짜의 재고 데이터 추가
                inventory_data.append(last_inventory)
                pending_data.append(last_pending)
        else:
            # 2025년 데이터가 없으면 빈 배열
            inventory_data = []
            pending_data = []
    else:
        # 메인 대시보드에서는 재고 데이터 표시 안함
        inventory_data = []
        pending_data = []
    
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
        df['판매일자'] = pd.to_datetime(df['판매일자'])
        max_my_this = df[df['판매일자'].dt.year == current_year]['실판매'].max()
        max_my_last = df[df['판매일자'].dt.year == last_year]['실판매'].max()
        max_my = max(max_my_this if not pd.isna(max_my_this) else 0,
                    max_my_last if not pd.isna(max_my_last) else 0,
                    1)
        max_compare = max([v for v in compare_data if v is not None], default=1)
        normalized_compare = [
            {'value': (v * max_my / max_compare) if (v is not None and max_compare) else None, 'original': v}
            if v is not None else None
            for v in compare_data
        ]
        series.append({
            'name': '비교상품 판매량',
            'type': 'line',
            'data': normalized_compare,
            'symbol': 'diamond',
            'symbolSize': 6,
            'lineStyle': {'width': 2, 'color': '#ff6b6b'},
            'itemStyle': {'color': '#ff6b6b'},
            'connectNulls': True,
            'yAxisIndex': 0
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
    
    # 재고 데이터 시리즈 추가 (상품별 페이지에서만)
    if only_product and inventory_data and any(v is not None for v in inventory_data):
        series.append({
            'name': '현재고',
            'type': 'line',
            'data': safe_list(inventory_data),
            'symbol': 'diamond',
            'symbolSize': 6,
            'lineStyle': {'width': 2, 'color': '#8B4513'},
            'itemStyle': {'color': '#8B4513'},
            'connectNulls': True,
            'yAxisIndex': 0  # 왼쪽 y축 사용
        })
    
    if only_product and pending_data and any(v is not None for v in pending_data):
        series.append({
            'name': '미송잔량',
            'type': 'line',
            'data': safe_list(pending_data),
            'symbol': 'triangle',
            'symbolSize': 6,
            'lineStyle': {'width': 2, 'color': '#000000'},
            'itemStyle': {'color': '#000000'},
            'connectNulls': True,
            'yAxisIndex': 0  # 왼쪽 y축 사용
        })
    
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
            'legend': {
                'show': True, 
                'top': 40,
                'selected': {
                    f'실판매({current_year})': True,
                    '비교상품 판매량': False,
                    f'실판매({last_year})': True if only_product and trend_last_year else True,
                    '현재고': False if only_product else True,
                    '미송잔량': False if only_product else True,
                    f'저점 추세({last_year})': False if only_product and trend_last_year else True,
                    f'고점 추세({last_year})': False if only_product and trend_last_year else True,
                    f'중위 추세({last_year})': True if only_product and trend_last_year else False,
                    f'저점 추세({current_year})': False,
                    f'고점 추세({current_year})': False,
                    f'중위 추세({current_year})': True
                }
            },
            'xAxis': {'type': 'category', 'name': '월', 'data': dates},
            'yAxis': {'type': 'value', 'name': '판매량/재고량'},
            'series': series,
            'dataZoom': [
                {
                    'type': 'inside',
                    'xAxisIndex': 0,
                    'start': 0,
                    'end': 100
                },
                {
                    'type': 'slider',
                    'xAxisIndex': 0,
                    'start': 0,
                    'end': 100,
                    'height': 20,
                    'handleSize': '60%',
                    'bottom': 0
                }
            ]
        }
    }

def create_weekly_sales_chart(df, weekly_client_data=None, compare_df=None):
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
    
    series_list = []
    
    # 변수 초기화
    last_year_values = []
    last_high_trend = []
    last_low_trend = []
    last_mid_trend = []
    
    # 2025년 데이터가 있는지 확인
    has_current_year_data = not df_current_year.empty and df_current_year['실판매'].sum() > 0
    
    # 전년도 데이터 처리 (올해 데이터 처리 전에 먼저 처리)
    weekly_sales_last = None
    if not df_last_year.empty:
        # 전년도 주차 계산 (올해와 동일한 방식)
        df_last_year['주차'] = df_last_year['판매일자'].apply(calculate_calendar_week)
        weekly_sales_last = df_last_year.groupby('주차')['실판매'].sum().reset_index()
        weekly_sales_last = weekly_sales_last.sort_values('주차')
        last_year_values = weekly_sales_last['실판매'].tolist()
        
        # 전년도 추세선 계산
        if len(last_year_values) > 2:
            last_low_trend = safe_list(trend_calculator.lower_trend(last_year_values))
            last_high_trend = safe_list(trend_calculator.upper_trend(last_year_values))
            last_mid_trend = safe_list(trend_calculator.mid_trend(last_year_values))
        else:
            last_low_trend = last_high_trend = last_mid_trend = last_year_values
    
    # 올해 데이터 처리
    if has_current_year_data:
        # 실제 달력 기준 주차 계산
        df_current_year['주차'] = df_current_year['판매일자'].apply(calculate_calendar_week)
        weekly_sales = df_current_year.groupby('주차')['실판매'].sum().reset_index()
        weekly_sales = weekly_sales.sort_values('주차')
        current_values = weekly_sales['실판매'].tolist()
        
        # 올해 추세선 계산
        if len(current_values) > 2:
            low_trend = safe_list(trend_calculator.lower_trend(current_values))
            high_trend = safe_list(trend_calculator.upper_trend(current_values))
            mid_trend = safe_list(trend_calculator.mid_trend(current_values))
        else:
            low_trend = high_trend = mid_trend = current_values
        
        # 작년 추세선을 벗어나는 지점들을 markPoint로 표시
        # mark_points = []
        # if len(last_year_values) > 2 and len(current_values) > 0:
        #     for i, (week, current_value) in enumerate(zip(weekly_sales['주차'].tolist(), current_values)):
        #         # 해당 주차의 전년도 추세선 값 찾기
        #         if week in weekly_sales_last['주차'].values:
        #             last_year_idx = weekly_sales_last[weekly_sales_last['주차'] == week].index[0]
        #             if last_year_idx < len(last_high_trend) and last_year_idx < len(last_low_trend):
        #                 high_threshold = last_high_trend[last_year_idx]
        #                 low_threshold = last_low_trend[last_year_idx]
                        
        #                 if high_threshold is not None and low_threshold is not None:
        #                     if current_value > high_threshold:
        #                         # 고점 추세보다 높은 경우 - 빨간색 markPoint
        #                         mark_points.append({
        #                             'name': f'{current_value}',
        #                             'value': current_value,
        #                             'xAxis': week - 1,  # 주차는 1부터 시작하므로 인덱스는 0부터
        #                             'yAxis': current_value,
        #                             'itemStyle': {'color': '#ff4444'},
        #                             'symbol': 'circle',
        #                             'symbolSize': 12,
        #                             'label': {
        #                                 'show': True,
        #                                 'position': 'top',
        #                                 'formatter': f'{current_value}',
        #                                 'fontSize': 12,
        #                                 'fontWeight': 'bold',
        #                                 'color': '#ff4444'
        #                             }
        #                         })
        #                     elif current_value < low_threshold:
        #                         # 저점 추세보다 낮은 경우 - 주황색 markPoint
        #                         mark_points.append({
        #                             'name': f'{current_value}',
        #                             'value': current_value,
        #                             'xAxis': week - 1,  # 주차는 1부터 시작하므로 인덱스는 0부터
        #                             'yAxis': current_value,
        #                             'itemStyle': {'color': '#ff8800'},
        #                             'symbol': 'circle',
        #                             'symbolSize': 12,
        #                             'label': {
        #                                 'show': True,
        #                                 'position': 'bottom',
        #                                 'formatter': f'{current_value}',
        #                                 'fontSize': 12,
        #                                 'fontWeight': 'bold',
        #                                 'color': '#ff8800'
        #                             }
        #                         })
        
        # 올해 실판매 시리즈 추가 (먼저 추가)
        series_list.append({
            'name': f'실판매({current_year})',
            'type': 'line',
            'data': current_values,
            'symbol': 'circle',
            'symbolSize': 4,
            'lineStyle': {'width': 2, 'color': '#5470c6'},
            'itemStyle': {'color': '#5470c6'},
            'connectNulls': True
        })
    

    
    # 전년도 데이터 시리즈 추가 (올해 데이터 다음에)
    if not df_last_year.empty:
        # 전년도 실판매 시리즈 추가
        series_list.append({
            'name': f'실판매({last_year})',
            'type': 'line',
            'data': last_year_values,
            'symbol': 'circle',
            'symbolSize': 4,
            'lineStyle': {'width': 2, 'color': '#91cc75'},
            'itemStyle': {'color': '#91cc75'},
            'connectNulls': True,
            'tooltip': {
                'formatter': 'function(params) { if (params.value !== null && params.value !== undefined) { if (params.value === 0 || params.value === "") { return params.marker + params.seriesName + ": -"; } else { return params.marker + params.seriesName + ": " + params.value; } } return ""; }'
            }
        })
        
        # 전년도 추세선 추가
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
    
    # 올해 추세선 추가 (전년도 추세선 뒤에)
    if has_current_year_data:
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
    
    # X축 데이터 생성 (1-53주차로 고정)
    x_axis_data = list(range(1, 54))
    x_axis_labels = [str(week) for week in x_axis_data]
    
    # 데이터를 1-53주차에 매핑
    week_to_index = {week: idx for idx, week in enumerate(x_axis_data)}
    
    # 데이터 매핑 - 시리즈 순서에 따라 동적으로 처리
    if has_current_year_data:
        # 올해 데이터 매핑 - 실제 주차에 맞게 표시하고 연속성 보장
        current_mapped = [None] * 53
        current_weeks = weekly_sales['주차'].tolist()
        
        for week, value in zip(current_weeks, current_values):
            if week in week_to_index:
                current_mapped[week_to_index[week]] = value
        
        # 데이터가 있는 주차들 사이만 연결 (데이터가 없는 구간은 None으로 유지)
        current_mapped = interpolate_sales_data(current_mapped)
        
        if len(series_list) > 0:
            series_list[0]['data'] = current_mapped
        
        # 올해 추세선 매핑 - 전체 주차에 걸쳐 표시
        if len(current_values) > 2:
            # 추세선을 전체 주차에 연속적으로 보간
            current_weeks = weekly_sales['주차'].tolist()
            current_data_indices = [week_to_index[week] for week in current_weeks if week in week_to_index]
            
            low_trend_mapped = interpolate_trend(current_data_indices, low_trend, 53)
            high_trend_mapped = interpolate_trend(current_data_indices, high_trend, 53)
            mid_trend_mapped = interpolate_trend(current_data_indices, mid_trend, 53)
            
            # 올해 추세선 위치 찾기 (시리즈 이름으로)
            for i, series in enumerate(series_list):
                if series['name'] == f'저점 추세({current_year})':
                    series_list[i]['data'] = low_trend_mapped
                elif series['name'] == f'고점 추세({current_year})':
                    series_list[i]['data'] = high_trend_mapped
                elif series['name'] == f'중위 추세({current_year})':
                    series_list[i]['data'] = mid_trend_mapped
    
    # 전년도 데이터 매핑 - 실제 주차에 맞게 표시
    if weekly_sales_last is not None:
        # 1-53주차 배열에 실제 데이터만 매핑하고 연속성 보장
        last_year_mapped = [None] * 53
        last_year_weeks = weekly_sales_last['주차'].tolist()
        
        for week, value in zip(last_year_weeks, last_year_values):
            if week in week_to_index:
                last_year_mapped[week_to_index[week]] = value
        
        # 데이터가 있는 주차들 사이만 연결 (데이터가 없는 구간은 None으로 유지)
        last_year_mapped = interpolate_sales_data(last_year_mapped)
        
        # 전년도 실판매 위치 찾기
        for i, series in enumerate(series_list):
            if series['name'] == f'실판매({last_year})':
                series_list[i]['data'] = last_year_mapped
                break
        
        # 전년도 추세선 매핑 - 전체 1-53주차에 걸쳐 표시
        if len(last_year_values) > 2:
            # 추세선을 전체 주차에 연속적으로 보간
            last_data_weeks = weekly_sales_last['주차'].tolist()
            last_data_indices = [week_to_index[week] for week in last_data_weeks if week in week_to_index]
            
            last_low_trend_mapped = interpolate_trend(last_data_indices, last_low_trend, 53)
            last_high_trend_mapped = interpolate_trend(last_data_indices, last_high_trend, 53)
            last_mid_trend_mapped = interpolate_trend(last_data_indices, last_mid_trend, 53)
            
            # 전년도 추세선 위치 찾기 (시리즈 이름으로)
            for i, series in enumerate(series_list):
                if series['name'] == f'저점 추세({last_year})':
                    series_list[i]['data'] = last_low_trend_mapped
                elif series['name'] == f'고점 추세({last_year})':
                    series_list[i]['data'] = last_high_trend_mapped
                elif series['name'] == f'중위 추세({last_year})':
                    series_list[i]['data'] = last_mid_trend_mapped
    
    # 주차별 거래처 수 데이터 추가
    if weekly_client_data:
        # 거래처 수 데이터를 1-53주차에 매핑
        client_data_mapped = [None] * 53
        for week, count in weekly_client_data.items():
            if week in week_to_index:
                client_data_mapped[week_to_index[week]] = count
        
        series_list.append({
            'name': '거래처 수',
            'type': 'bar',
            'yAxisIndex': 1,  # 두 번째 y축 사용
            'data': client_data_mapped,
            'itemStyle': {'color': '#ff6b6b'},
            'barWidth': '60%'
        })
    
    # 비교 상품 데이터 추가 (주별)
    compare_series = None
    if compare_df is not None and not compare_df.empty:
        print(f"주별 그래프에 비교 상품 데이터 추가 - compare_df shape: {compare_df.shape}")
        
        # 비교 상품 데이터를 주별로 처리
        compare_df_copy = compare_df.copy()
        
        # 날짜와 판매량 컬럼 찾기
        date_col = None
        sales_col = None
        
        for col in compare_df_copy.columns:
            if any(keyword in str(col).lower() for keyword in ['거래일자', '판매일자', '날짜', 'date']):
                date_col = col
                break
        
        for col in compare_df_copy.columns:
            if any(keyword in str(col).lower() for keyword in ['판매량', '실판매', '수량', 'quantity', 'sales']):
                sales_col = col
                break
        
        if date_col is None:
            date_col = compare_df_copy.columns[0]
        if sales_col is None:
            for col in compare_df_copy.columns:
                if col != date_col and pd.api.types.is_numeric_dtype(compare_df_copy[col]):
                    sales_col = col
                    break
            if sales_col is None and len(compare_df_copy.columns) >= 2:
                sales_col = compare_df_copy.columns[1]
        
        # 날짜 컬럼을 datetime으로 변환
        compare_df_copy[date_col] = pd.to_datetime(compare_df_copy[date_col], errors='coerce')
        
        # 판매량 컬럼을 숫자로 변환
        compare_df_copy[sales_col] = pd.to_numeric(compare_df_copy[sales_col], errors='coerce')
        
        # 유효한 데이터만 필터링
        compare_df_copy = compare_df_copy.dropna(subset=[date_col, sales_col])
        
        # 현재 연도 데이터만 필터링
        compare_df_copy = compare_df_copy[compare_df_copy[date_col].dt.year == current_year]
        
        if not compare_df_copy.empty:
            # 주차 계산
            compare_df_copy['주차'] = compare_df_copy[date_col].apply(calculate_calendar_week)
            
            # 주별 판매량 집계
            weekly_compare = compare_df_copy.groupby('주차')[sales_col].sum().reset_index()
            weekly_compare = weekly_compare.sort_values('주차')
            
            # 1-53주차에 매핑
            compare_data_mapped = [None] * 53
            for week, value in zip(weekly_compare['주차'].tolist(), weekly_compare[sales_col].tolist()):
                if week in week_to_index:
                    compare_data_mapped[week_to_index[week]] = float(value)
            
            # 데이터가 있는 주차들 사이만 연결
            compare_data_mapped = interpolate_sales_data(compare_data_mapped)
            
            df['판매일자'] = pd.to_datetime(df['판매일자'])
            max_my_this = df[df['판매일자'].dt.year == current_year]['실판매'].max()
            max_my_last = df[df['판매일자'].dt.year == last_year]['실판매'].max()
            max_my = max(max_my_this if not pd.isna(max_my_this) else 0,
                        max_my_last if not pd.isna(max_my_last) else 0,
                        1)
            max_compare = max([v for v in compare_data_mapped if v is not None], default=1)
            normalized_compare = [
                {'value': (v * max_my / max_compare) if (v is not None and max_compare) else None, 'original': v}
                if v is not None else None
                for v in compare_data_mapped
            ]
            compare_series = {
                'name': '비교상품 주별 판매량',
                'type': 'line',
                'data': normalized_compare,
                'symbol': 'diamond',
                'symbolSize': 6,
                'lineStyle': {'width': 2, 'color': '#ff6b6b'},
                'itemStyle': {'color': '#ff6b6b'},
                'connectNulls': True,
                'yAxisIndex': 0
            }
    # 시리즈 순서 맞추기: 실판매(2025) 다음에 비교상품, 그 다음 실판매(2024)
    def insert_compare_series(series_list, compare_series):
        idx_2025 = next((i for i, s in enumerate(series_list) if s['name'].startswith('실판매(2025)')), None)
        idx_2024 = next((i for i, s in enumerate(series_list) if s['name'].startswith('실판매(2024)')), None)
        if compare_series and idx_2025 is not None:
            insert_idx = idx_2025 + 1
            # 만약 실판매(2024)가 바로 뒤에 있으면 그 앞에 삽입
            if idx_2024 is not None and idx_2024 == insert_idx:
                series_list.insert(insert_idx, compare_series)
            else:
                series_list.insert(insert_idx, compare_series)
        elif compare_series:
            series_list.append(compare_series)
    insert_compare_series(series_list, compare_series)
    
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
    
    # 추세선을 벗어나는 지점들을 알림용으로 수집
    trend_alerts = []
    if has_current_year_data and len(last_year_values) > 2 and len(current_values) > 0:
        for i, current_value in enumerate(current_values):
            if i < len(last_high_trend) and i < len(last_low_trend):
                high_threshold = last_high_trend[i]
                low_threshold = last_low_trend[i]
                
                if high_threshold is not None and low_threshold is not None:
                    week_num = weekly_sales.iloc[i]['주차'] if i < len(weekly_sales) else i + 1
                    if current_value > high_threshold:
                        trend_alerts.append({
                            'type': 'high',
                            'week': week_num,
                            'value': current_value,
                            'threshold': high_threshold,
                            'message': f'{week_num}주차 판매량({current_value})이 전년 고점 추세({high_threshold:.0f})를 초과'
                        })
                    elif current_value < low_threshold:
                        trend_alerts.append({
                            'type': 'low',
                            'week': week_num,
                            'value': current_value,
                            'threshold': low_threshold,
                            'message': f'{week_num}주차 판매량({current_value})이 전년 저점 추세({low_threshold:.0f}) 미달'
                        })
    
    return {
        'type': 'line',
        'title': '주별 판매량',
        'data': {
            'weeks': x_axis_labels,
            'values': current_values if has_current_year_data else [],
            'trend_alerts': trend_alerts
        },
        'config': {
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {
                    'show': False
                },
                'formatter': 'function(params) { var result = params[0].axisValue + "<br/>"; params.forEach(function(param) { if (param.value !== null && param.value !== undefined) { result += param.marker + param.seriesName + ": " + param.value + "<br/>"; } }); return result; }'
            },
            'xAxis': {
                'type': 'category',
                'name': '주차',
                'data': x_axis_labels,
                'axisLabel': {'rotate': 30, 'interval': 0}
            },
            'yAxis': y_axis_config,
            'series': series_list,
            'legend': {
                'show': True,
                'data': [series['name'] for series in series_list],
                'selected': {
                    f'실판매({current_year})': True,
                    f'실판매({last_year})': True,
                    '거래처 수': False,
                    '비교상품 판매량': False,
                    '비교상품 주별 판매량': False,
                    f'저점 추세({last_year})': False,
                    f'고점 추세({last_year})': False,
                    f'중위 추세({last_year})': True,
                    f'저점 추세({current_year})': False,
                    f'고점 추세({current_year})': False,
                    f'중위 추세({current_year})': True
                }
            },
            'dataZoom': [
                {
                    'type': 'inside',
                    'xAxisIndex': 0,
                    'start': 0,
                    'end': 100
                },
                {
                    'type': 'slider',
                    'xAxisIndex': 0,
                    'start': 0,
                    'end': 100,
                    'height': 20,
                    'handleSize': '60%',
                    'bottom': 0
                }
            ]
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
            }],
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