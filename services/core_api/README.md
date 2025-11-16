# GEN_AI Core API

투자 복기 AI 분석 플랫폼의 메인 API 서버입니다.

## 주요 기능

- 사용자 인증/인가 (JWT)
- 투자 복기 노트 생성 및 조회
- AI 기반 투자 행동 분석
- 실패 유형 분류 (9가지 카테고리)

## 기술 스택

- **Framework**: FastAPI
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Authentication**: JWT (python-jose, passlib)
- **AI**: OpenAI GPT-4o
- **Migration**: Alembic

## 설치 및 실행

### 1. 환경 변수 설정

`.env.example` 파일을 참고하여 `.env` 파일을 생성하세요:

```bash
cp .env.example .env
```

필수 환경 변수:
- `DATABASE_URL`: PostgreSQL 연결 URL
- `SECRET_KEY`: JWT 토큰 서명용 시크릿 키
- `OPENAI_API_KEY`: OpenAI API 키

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 데이터베이스 마이그레이션

```bash
# 초기 마이그레이션 생성
alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 적용
alembic upgrade head
```

### 4. 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 다음 URL에서 API 문서를 확인할 수 있습니다:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 엔드포인트

### 인증 (`/api/v1/auth`)

- `POST /api/v1/auth/register` - 사용자 등록
- `POST /api/v1/auth/login` - 로그인 (JWT 토큰 발급)
- `GET /api/v1/auth/me` - 현재 사용자 정보 조회

### 복기 노트 (`/api/v1/review`)

- `POST /api/v1/review` - 새로운 복기 노트 생성
- `GET /api/v1/review/{review_id}` - 특정 복기 노트 조회
- `GET /api/v1/review` - 복기 노트 목록 조회

## 프로젝트 구조

```
app/
├── api/              # API 엔드포인트 라우터
│   ├── auth.py       # 인증 API
│   └── review.py     # 복기 노트 API
├── core/             # 핵심 설정 및 유틸리티
│   └── config.py     # 설정 관리
├── db/               # 데이터베이스 관련
│   ├── models.py     # SQLAlchemy 모델
│   └── session.py    # DB 세션 관리
├── models/           # Pydantic 스키마
│   └── schemas.py    # API 요청/응답 스키마
├── services/         # 비즈니스 로직
│   └── gpt_service.py  # OpenAI GPT 서비스
└── main.py           # FastAPI 앱 진입점
```

## 개발 가이드

### 데이터베이스 모델

- `User`: 사용자 정보 및 인증
- `Trade`: 거래 내역
- `ReviewNote`: 복기 노트 및 AI 분석 결과

### 환경 변수 관리

모든 설정은 `app/core/config.py`의 `Settings` 클래스에서 관리됩니다.
환경 변수는 `.env` 파일 또는 시스템 환경 변수로 설정할 수 있습니다.

### 마이그레이션 사용법

```bash
# 새 마이그레이션 생성
alembic revision --autogenerate -m "설명"

# 마이그레이션 적용
alembic upgrade head

# 마이그레이션 롤백
alembic downgrade -1

# 현재 버전 확인
alembic current
```

## Docker 실행

```bash
docker build -t gen-ai-core-api .
docker run -p 8000:8000 --env-file .env gen-ai-core-api
```

## 라이선스

MIT

