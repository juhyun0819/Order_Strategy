# Order_Strategy

여성복 의류 도매를 위한 대시보드 애플리케이션 (SOLID 원칙 기반 구조)

## 🚀 프로젝트 구조

```
Order_Strategy/
├── app.py                      # Flask 앱 진입점 및 Blueprint 등록
├── route/                      # 라우트(컨트롤러) 모듈
│   ├── dashboard.py            # 대시보드 UI 라우트
│   ├── admin.py                # 관리 기능 라우트
│   └── api.py                  # API 라우트
├── service/                    # 비즈니스 로직/서비스 계층
│   ├── db.py                   # 데이터베이스 관련 함수
│   ├── analysis.py             # 데이터 분석 함수
│   ├── charts.py               # 차트/그래프 생성 함수
│   ├── trend_calculator.py     # 트렌드 계산 함수
│   └── visualization.py        # 시각화 함수
├── static/
│   └── style.css               # 정적 파일(CSS)
├── templates/
│   └── dashboard.html          # 템플릿(HTML)
├── requirements.txt            # Python 의존성
├── package.json                # Node.js 의존성 (Tailwind CSS)
├── package-lock.json
├── tailwind.config.js          # Tailwind CSS 설정
└── README.md
```

## 📦 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
npm install
```

### 2. CSS 빌드

```bash
npm run build:css      # 개발 모드
npm run build:css:prod # 프로덕션 모드
```

### 3. 애플리케이션 실행

```bash
python app.py
```

## 🔧 주요 기능 및 책임 분리

### route (라우트/컨트롤러)

- **dashboard.py**: 대시보드 UI, 메인 페이지, 데이터 업로드 등
- **admin.py**: 데이터 삭제, DB 초기화 등 관리 기능
- **api.py**: 재고 알림, 판매 예측, 트렌드 등 API 제공

### service (서비스/비즈니스 로직)

- **db.py**: DB 연결, 데이터 CRUD, 초기화 등 (단일 책임)
- **analysis.py**: 파레토 분석, 7일 분석, 알림 생성 등 (분석 책임)
- **charts.py**: 차트/그래프 생성 (시각화 책임)
- **trend_calculator.py**: 트렌드 계산 (예측/분석 책임)
- **visualization.py**: 시각화 함수 (그래프/차트 렌더링)

### static & templates

- **static/**: CSS 등 정적 리소스
- **templates/**: HTML 템플릿

## 🎨 UI/UX 특징

- 모던한 Tailwind 기반 디자인
- 반응형 레이아웃
- 실시간 동적 그래프/차트
- 직관적 네비게이션

## 📊 분석/비즈니스 기능

- 파레토 분석(80/20)
- 트렌드 예측(선형 회귀 등)
- 재고 관리/알림
- 시계열 분석

## 🛠️ 기술 스택

- **Backend**: Flask, SQLite
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **Data Analysis**: Pandas, NumPy, Matplotlib
- **기타**: FuzzyWuzzy 등

## �� 라이선스

MIT License
