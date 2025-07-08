import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for web applications

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
from datetime import datetime, timedelta
from service.analysis import recent_7days_analysis

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

def create_visualizations(df, only_product=False, all_dates=None):
    """대시보드용 그래프 생성"""
    plots = {}
    
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
        
        # 현재 연도의 데이터만 필터링
        current_year = datetime.now().year
        df_current_year = df[df['판매일자'].dt.year == current_year]
        
        if not df_current_year.empty:
            daily_sales = df_current_year.groupby('판매일자')['실판매'].sum().reset_index()
            daily_sales['판매일자'] = pd.to_datetime(daily_sales['판매일자'])
            daily_sales = daily_sales.sort_values('판매일자')
            
            # 현재 연도의 1월 1일부터 마지막 데이터까지 생성
            start_date = pd.Timestamp(f'{current_year}-01-01')
            end_date = daily_sales['판매일자'].max()
            full_date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # 전체 날짜 범위에 대해 데이터 재인덱싱
            daily_sales = daily_sales.set_index('판매일자').reindex(full_date_range, fill_value=0).reset_index()
            daily_sales.columns = ['판매일자', '실판매']
        else:
            # 현재 연도 데이터가 없으면 빈 데이터프레임 생성
            daily_sales = pd.DataFrame({'판매일자': [], '실판매': []})
    
    fig1, ax1 = plt.subplots(figsize=(8, 4.5), facecolor='#f5f7fa')
    ax1.set_facecolor('#f5f7fa')
    x = np.arange(len(daily_sales))
    sales = daily_sales['실판매'].values
    
    # 실판매가 0인 데이터는 plot에서 제외
    nonzero_mask = sales != 0
    daily_sales_nonzero = daily_sales[nonzero_mask]
    sales_nonzero = sales[nonzero_mask]
    x_nonzero = np.arange(len(sales_nonzero))

    # 추세선 계산도 0이 아닌 데이터만 사용
    if len(sales_nonzero) > 1:
        roll_min = pd.Series(sales_nonzero).rolling(7, min_periods=1).min()
        roll_max = pd.Series(sales_nonzero).rolling(7, min_periods=1).max()
        # x, y 길이 체크
        if len(x_nonzero) == len(roll_min) and len(x_nonzero) > 1:
            low_trend = np.poly1d(np.polyfit(x_nonzero, roll_min, 1))(x_nonzero)
            high_trend = np.poly1d(np.polyfit(x_nonzero, roll_max, 1))(x_nonzero)
            mid_trend = (low_trend + high_trend) / 2
        else:
            low_trend = roll_min
            high_trend = roll_max
            mid_trend = (roll_min + roll_max) / 2
    else:
        low_trend = np.array([])
        high_trend = np.array([])
        mid_trend = np.array([])
    
    # 그래프
    ax1.plot(daily_sales_nonzero['판매일자'], sales_nonzero, marker='o', markersize=3, linewidth=1, label='실판매')
    # 추세선이 있을 때만 그리기
    if len(low_trend) > 0:
        ax1.plot(daily_sales_nonzero['판매일자'], low_trend, '--', color='blue', linewidth=1, label='저점 추세')
    if len(high_trend) > 0:
        ax1.plot(daily_sales_nonzero['판매일자'], high_trend, '--', color='green', linewidth=1, label='고점 추세')
    if len(mid_trend) > 0:
        ax1.plot(daily_sales_nonzero['판매일자'], mid_trend, '--', color='red', linewidth=1, label='중위 추세')
    ax1.set_xlabel('월')
    ax1.set_ylabel('판매량')
    ax1.grid(True, alpha=0.3)
    
    # x축 레이블 간소화 (월별로만 표시)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.xticks(rotation=0)
    
    # x축 범위를 1월부터 12월까지로 설정
    if not daily_sales_nonzero.empty and not only_product:
        ax1.set_xlim(pd.Timestamp(f'{current_year}-01-01'), pd.Timestamp(f'{current_year}-12-31'))
    ax1.legend()
    plt.tight_layout(pad=0)
    img1 = io.BytesIO()
    plt.savefig(img1, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
    img1.seek(0)
    plots['sales_trend'] = base64.b64encode(img1.getvalue()).decode()
    plt.close()
    
    # 상품별 실판매 집계 (only_product=False일 때만)
    if not only_product and '품명' in df.columns and '실판매' in df.columns:
        # 원래 상품별 판매 그래프로 되돌리기
        product_sales = df.groupby('품명')['실판매'].sum().sort_values(ascending=False).head(10)
        fig2, ax2 = plt.subplots(figsize=(8, 5), facecolor='#f5f7fa')
        ax2.set_facecolor('#f5f7fa')
        ax2.bar(range(len(product_sales)), product_sales.values, color='lightblue')
        ax2.set_xlabel('품명')
        ax2.set_ylabel('실판매')
        ax2.set_xticks(range(len(product_sales)))
        ax2.set_xticklabels(product_sales.index, rotation=45, ha='right')
        plt.tight_layout(pad=0)
        img2 = io.BytesIO()
        plt.savefig(img2, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img2.seek(0)
        plots['product_sales'] = base64.b64encode(img2.getvalue()).decode()
        plt.close()
        
        # 파레토 분석 그래프 (새로 만든 막대/선 그래프)
        product_sales_pareto = df.groupby('품명')['실판매'].sum().sort_values(ascending=False)
        total_sales = product_sales_pareto.sum()
        cumsum = product_sales_pareto.cumsum()
        cumsum_ratio = cumsum / total_sales
        # 파레토 구간 인덱스 (80% 기준)
        pareto_idx = np.where(cumsum_ratio <= 0.8)[0]
        pareto_last = pareto_idx[-1] if len(pareto_idx) > 0 else 0
        # 80% 기준을 채우는 모든 상품만 표시
        top_n = pareto_last + 1
        products_sorted = product_sales_pareto.index[:top_n]
        sales_sorted = product_sales_pareto.values[:top_n]
        cumsum_ratio_top = cumsum_ratio[:top_n]
        # 그래프
        fig_pareto, ax1 = plt.subplots(figsize=(max(8, 0.35*len(products_sorted)), 5), facecolor='#f5f7fa')
        ax1.set_facecolor('#f5f7fa')
        # 막대그래프(판매량)
        bar_colors = ['#FFA500' if i <= pareto_last else '#FFE5B4' for i in range(top_n)]
        bars = ax1.bar(products_sorted, sales_sorted, color=bar_colors, label='판매량')
        ax1.set_xlabel('품명')
        ax1.set_ylabel('판매량')
        ax1.set_xticklabels(products_sorted, rotation=60, ha='right', fontsize=8)
        plt.subplots_adjust(bottom=0.32)  # 하단 여백 늘리기
        # 누적비율 선그래프
        ax2 = ax1.twinx()
        ax2.plot(products_sorted, cumsum_ratio_top, color='#2563eb', marker='o', label='누적비율')
        ax2.axhline(0.8, color='gray', linestyle='--', linewidth=1)
        ax2.text(top_n-1, 0.82, '80%', color='gray', va='bottom', ha='right', fontsize=10)
        ax2.set_ylabel('누적비율')
        ax2.set_ylim(0, 1.05)
        ax2.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        ax2.set_yticklabels(['0%', '20%', '40%', '60%', '80%', '100%'])
        # 스타일
        fig_pareto.tight_layout()
        img_pareto = io.BytesIO()
        plt.savefig(img_pareto, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img_pareto.seek(0)
        plots['pareto_analysis'] = base64.b64encode(img_pareto.getvalue()).decode()
        plt.close()
    
    # 컬러별 실판매 집계
    if '칼라' in df.columns and '실판매' in df.columns:
        fig3, ax3 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
        color_sales = df.groupby('칼라')['실판매'].sum().sort_values(ascending=False).head(10)
        ax3.set_facecolor('#f5f7fa')
        ax3.bar(range(len(color_sales)), color_sales.values, color='lightcoral')
        ax3.set_xlabel('컬러')
        ax3.set_ylabel('실판매')
        ax3.set_xticks(range(len(color_sales)))
        ax3.set_xticklabels(color_sales.index, rotation=45, ha='right')
        plt.tight_layout(pad=0)
        img3 = io.BytesIO()
        plt.savefig(img3, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img3.seek(0)
        plots['color_sales'] = base64.b64encode(img3.getvalue()).decode()
        plt.close()
    
    # 사이즈별 실판매 집계
    if '사이즈' in df.columns and '실판매' in df.columns:
        fig4, ax4 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
        size_sales = df.groupby('사이즈')['실판매'].sum().sort_values(ascending=False)
        ax4.set_facecolor('#f5f7fa')
        ax4.bar(range(len(size_sales)), size_sales.values, color='lightgreen')
        ax4.set_xlabel('사이즈')
        ax4.set_ylabel('실판매')
        ax4.set_xticks(range(len(size_sales)))
        ax4.set_xticklabels(size_sales.index, rotation=45, ha='right')
        plt.tight_layout(pad=0)
        img4 = io.BytesIO()
        plt.savefig(img4, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img4.seek(0)
        plots['size_sales'] = base64.b64encode(img4.getvalue()).decode()
        plt.close()
    
    # 최근 7일 요일별/일별 판매 분석은 항상 생성
    daily_sales, day_sales = recent_7days_analysis(df)
    if day_sales is not None and not day_sales.empty:
        fig6, ax6 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_sales_reindexed = day_sales.groupby('요일')['실판매'].sum().reindex(day_order)
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
        ax6.set_facecolor('#f5f7fa')
        bars = ax6.bar(range(len(day_sales_reindexed)), day_sales_reindexed.values, color=colors)
        ax6.set_xlabel('요일')
        ax6.set_ylabel('판매량')
        ax6.set_xticks(range(len(day_sales_reindexed)))
        ax6.set_xticklabels(['월', '화', '수', '목', '금', '토', '일'])
        for bar, value in zip(bars, day_sales_reindexed.values):
            if not pd.isna(value):
                ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01*max(day_sales_reindexed.values),
                        f'{value:,}', ha='center', va='bottom', fontweight='bold')
        plt.tight_layout(pad=0)
        img6 = io.BytesIO()
        plt.savefig(img6, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img6.seek(0)
        plots['daily_sales'] = base64.b64encode(img6.getvalue()).decode()
        plt.close()
    
    if daily_sales is not None and not daily_sales.empty:
        fig7, ax7 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
        ax7.set_facecolor('#f5f7fa')
        ax7.plot(daily_sales['판매일자'], daily_sales['실판매'], marker='o', linewidth=2, markersize=6)
        ax7.set_xlabel('날짜')
        ax7.set_ylabel('판매량')
        ax7.grid(True, alpha=0.3)
        ax7.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        plt.xticks(rotation=45)
        plt.tight_layout(pad=0)
        img7 = io.BytesIO()
        plt.savefig(img7, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
        img7.seek(0)
        plots['weekly_sales'] = base64.b64encode(img7.getvalue()).decode()
        plt.close()
    
    # 주별 판매량 그래프 (2025년 데이터만)
    if not df.empty:
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        
        # 현재 연도의 데이터만 필터링
        current_year = datetime.now().year
        df_current_year = df_copy[df_copy['판매일자'].dt.year == current_year]
        
        if not df_current_year.empty:
            # 주별 판매량 계산
            df_current_year['주차'] = df_current_year['판매일자'].dt.isocalendar().week
            weekly_sales = df_current_year.groupby('주차')['실판매'].sum().reset_index()
            weekly_sales = weekly_sales.sort_values('주차')
            
            # 마지막 데이터가 있는 주차까지만 선 그래프를 그림
            last_week = weekly_sales[weekly_sales['실판매'] > 0]['주차'].max() if (weekly_sales['실판매'] > 0).any() else 1
            fig8, ax8 = plt.subplots(figsize=(8, 4.5), facecolor='#f5f7fa')
            ax8.set_facecolor('#f5f7fa')
            # 선 그래프는 마지막 데이터가 있는 주차까지만
            ax8.plot(weekly_sales['주차'][:last_week], weekly_sales['실판매'][:last_week], marker='o', linewidth=2, markersize=4, color='#4ECDC4')
            ax8.set_xlabel('월')
            ax8.set_ylabel('판매량')
            # x축을 월별로 표시 (1월부터 12월까지)
            month_ticks = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45]
            month_labels = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']
            ax8.set_xticks(month_ticks)
            ax8.set_xticklabels(month_labels, rotation=0)
            ax8.grid(True, alpha=0.3)
            plt.tight_layout(pad=0)
            img8 = io.BytesIO()
            plt.savefig(img8, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img8.seek(0)
            plots['weekly_sales_chart'] = base64.b64encode(img8.getvalue()).decode()
            plt.close()
        else:
            # 현재 연도 데이터가 없으면 빈 그래프 생성
            fig8, ax8 = plt.subplots(figsize=(8, 4.5), facecolor='#f5f7fa')
            ax8.set_facecolor('#f5f7fa')
            ax8.text(0.5, 0.5, f'{current_year}년 데이터가 없습니다', ha='center', va='center', transform=ax8.transAxes, fontsize=12)
            ax8.set_xlabel('월')
            ax8.set_ylabel('판매량')
            ax8.grid(True, alpha=0.3)
            plt.tight_layout(pad=0)
            img8 = io.BytesIO()
            plt.savefig(img8, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img8.seek(0)
            plots['weekly_sales_chart'] = base64.b64encode(img8.getvalue()).decode()
            plt.close()
    
    # 전년도 데이터만 추출
    if not df.empty:
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        max_year = df_copy['판매일자'].dt.year.max()
        last_year = max_year - 1
        lastyear_df = df_copy[df_copy['판매일자'].dt.year == last_year]
        # 1. 전년도 일별 판매 트렌드 (실판매 + 중위 추세선)
        if not lastyear_df.empty:
            # 1월 1일~12월 31일까지 전체 날짜 생성
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
            fig9, ax9 = plt.subplots(figsize=(6, 4), facecolor='#f5f7fa')
            ax9.set_facecolor('#f5f7fa')
            ax9.plot(lastyear_daily['판매일자'], sales, marker='o', linewidth=2, markersize=4, color='#FF6B6B', label='실판매')
            ax9.plot(lastyear_daily['판매일자'], mid_trend, '--', color='red', linewidth=2, label='중위 추세')
            ax9.set_xlabel('월월')
            ax9.set_ylabel('판매량')
            ax9.legend()
            ax9.grid(True, alpha=0.3)
            # x축을 월별로만 표시
            ax9.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
            ax9.xaxis.set_major_formatter(mdates.DateFormatter('%m'))
            plt.xticks(rotation=0)
            plt.tight_layout(pad=0)
            img9 = io.BytesIO()
            plt.savefig(img9, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img9.seek(0)
            plots['lastyear_daily_trend'] = base64.b64encode(img9.getvalue()).decode()
            plt.close()
            # 2. 전년도 주별 판매 트렌드
            lastyear_df['주차'] = lastyear_df['판매일자'].dt.isocalendar().week
            weekly_sales = lastyear_df.groupby('주차')['실판매'].sum().reset_index()
            # 1~52주 전체 생성, 없는 주차는 0
            full_weeks = pd.DataFrame({'주차': range(1, 53)})
            weekly_sales = weekly_sales.merge(full_weeks, on='주차', how='right').fillna(0)
            weekly_sales = weekly_sales.sort_values('주차')
            fig10, ax10 = plt.subplots(figsize=(6, 4), facecolor='#f5f7fa')
            ax10.set_facecolor('#f5f7fa')
            ax10.plot(weekly_sales['주차'], weekly_sales['실판매'], marker='o', linewidth=2, markersize=4, color='#4ECDC4')
            ax10.set_xlabel('월')
            ax10.set_ylabel('판매량')
            # x축을 월별로 표시 (1월~12월)
            month_ticks = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45]
            month_labels = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']
            ax10.set_xticks(month_ticks)
            ax10.set_xticklabels(month_labels, rotation=0)
            ax10.grid(True, alpha=0.3)
            plt.tight_layout(pad=0)
            img10 = io.BytesIO()
            plt.savefig(img10, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img10.seek(0)
            plots['lastyear_weekly_trend'] = base64.b64encode(img10.getvalue()).decode()
            plt.close()
            # 3. 예측값 계산 (그래프X, 표로만 전달)
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
            # 예측값, 날짜, 신뢰도 표로 전달
            plots['lastyear_forecast_table'] = [
                {'date': d.strftime('%Y-%m-%d'), 'predicted_sales': v, 'confidence': confidence}
                for d, v in zip(forecast_dates, forecast_values)
            ]
        else:
            plots['lastyear_daily_trend'] = None
            plots['lastyear_weekly_trend'] = None
            plots['lastyear_forecast_table'] = []
    
    # 년도별 판매량 그래프
    if not df.empty:
        df_copy = df.copy()
        df_copy['판매일자'] = pd.to_datetime(df_copy['판매일자'])
        df_copy['년도'] = df_copy['판매일자'].dt.year
        yearly_sales = df_copy.groupby('년도')['실판매'].sum().reset_index()
        
        if not yearly_sales.empty:
            fig12, ax12 = plt.subplots(figsize=(6, 4.5), facecolor='#f5f7fa')
            ax12.set_facecolor('#f5f7fa')
            ax12.plot(range(len(yearly_sales)), yearly_sales['실판매'], marker='o', linewidth=2, markersize=6, color='#45B7D1')
            ax12.set_xlabel('년도')
            ax12.set_ylabel('판매량')
            ax12.set_xticks(range(len(yearly_sales)))
            ax12.set_xticklabels(yearly_sales['년도'], rotation=45, ha='right')
            ax12.grid(True, alpha=0.3)
            
            plt.tight_layout(pad=0)
            img12 = io.BytesIO()
            plt.savefig(img12, format='png', bbox_inches='tight', dpi=300, facecolor='#f5f7fa')
            img12.seek(0)
            plots['yearly_sales_chart'] = base64.b64encode(img12.getvalue()).decode()
            plt.close()
    
    return plots

def create_product_trend_chart(df, product):
    """상품별 트렌드 차트 생성"""
    sub = df[df['품명'] == product].sort_values('판매일자')
    if len(sub) < 2:
        return None
    
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
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight', dpi=200)
    img.seek(0)
    plt.close()
    
    return img 