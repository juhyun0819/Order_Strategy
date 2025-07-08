# Shopping UX Dashboard v2.0

여성복 의류 도매를 위한 대시보드 애플리케이션 - 모듈화된 구조

## 🚀 새로운 구조

```
project3_shopping_ux/
├── shop.py                    # Flask 앱 생성 및 Blueprint 등록
├── route/                     # 라우트 함수들
│   ├── dashboard.py          # 대시보드 UI 관련 라우트
│   ├── admin.py              # 관리 기능 라우트
│   └── api.py                # API 관련 라우트
├── service/                   # 비즈니스 로직 함수들
│   ├── db.py                 # 데이터베이스 관련 함수
│   ├── analysis.py           # 분석 함수들
│   └── visualization.py      # 그래프 생성 함수들
├── static/
│   └── style.css
├── templates/
│   └── dashboard.html
└── requirements.txt
```

## 📦 설치 및 실행

### 1. 의존성 설치

```bash
# Python 패키지 설치
pip install -r requirements.txt

# Node.js 패키지 설치 (Tailwind CSS용)
npm install
```

### 2. CSS 빌드

```bash
# 개발 모드 (실시간 감시)
npm run build:css

# 프로덕션 모드 (압축)
npm run build:css:prod
```

### 3. 애플리케이션 실행

```bash
python shop.py
```

또는

```bash
npm start
```

## 🔧 주요 기능

### 대시보드 (`route/dashboard.py`)
- 메인 페이지 (`/`)
- 대시보드 페이지 (`/dashboard`)
- 파일 업로드 및 데이터 처리

### 관리 기능 (`route/admin.py`)
- 날짜별 데이터 삭제 (`/delete-date`)
- 데이터베이스 초기화 (`/reset-db`)

### API (`route/api.py`)
- 재고 알림 (`/api/inventory-alerts`)
- 판매 예측 (`/api/sales-forecast`)
- 상품 트렌드 (`/product-trend`)

### 서비스 레이어

#### 데이터베이스 (`service/db.py`)
- `init_db()`: 데이터베이스 초기화
- `save_to_db()`: 데이터 저장
- `load_from_db()`: 데이터 로드
- `delete_by_date()`: 날짜별 데이터 삭제
- `reset_db()`: 데이터베이스 초기화

#### 분석 (`service/analysis.py`)
- `pareto_analysis()`: 파레토 분석
- `recent_7days_analysis()`: 최근 7일 분석
- `generate_inventory_alerts()`: 재고 알림 생성
- `generate_a_grade_alerts()`: A급 상품 알림
- `get_pareto_products()`: 파레토 상품 목록

#### 시각화 (`service/visualization.py`)
- `create_visualizations()`: 대시보드 그래프 생성
- `create_product_trend_chart()`: 상품별 트렌드 차트

## 🎨 UI/UX 특징

- **모던한 디자인**: v0.dev 스타일의 깔끔한 인터페이스
- **반응형 레이아웃**: 모든 디바이스에서 최적화
- **실시간 데이터**: 동적 그래프 및 차트
- **직관적 네비게이션**: 사이드바 기반 메뉴

## 📊 분석 기능

- **파레토 분석**: 80/20 법칙 기반 상품 분석
- **트렌드 예측**: 선형 회귀 기반 판매 예측
- **재고 관리**: 자동 재고 알림 및 발주 제안
- **시계열 분석**: 일별/주별/월별 판매 트렌드

## 🛠️ 기술 스택

- **Backend**: Flask, SQLite
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **Data Analysis**: Pandas, NumPy, Matplotlib
- **Fuzzy Matching**: FuzzyWuzzy

## 🔄 버전 히스토리

### v2.0.0 (현재)
- 모듈화된 구조로 리팩토링
- Blueprint 기반 라우트 분리
- 서비스 레이어 도입
- 코드 가독성 및 유지보수성 향상

### v1.0.0
- 초기 버전
- 단일 파일 구조

## 📝 라이선스

MIT License 