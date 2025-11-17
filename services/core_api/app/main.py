"""
FastAPI 애플리케이션 진입점
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import setup_logging, get_logger
from app.db.models import Base
from app.db.session import engine
from app.api import auth, review, report

# 로깅 초기화
setup_logging()
logger = get_logger(__name__)

# 설정 가져오기
settings = get_settings()

# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    debug=settings.DEBUG,
)

# CORS 설정 (프론트엔드와 통신을 위해 필요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(review.router, prefix=settings.API_V1_PREFIX)
app.include_router(report.router, prefix=settings.API_V1_PREFIX)

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행"""
    logger.info("애플리케이션 시작", app_name=settings.APP_NAME, version="1.0.0")
    # 데이터베이스 테이블 생성 (개발 환경용)
    # 프로덕션에서는 Alembic 마이그레이션 사용 권장
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("데이터베이스 테이블 생성 완료")


@app.get("/")
def root():
    """루트 엔드포인트"""
    return {
        "message": "GEN_AI Core API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy"}

