"""
DB 세션 설정 및 관리
FastAPI 의존성 주입을 위한 get_db() 함수 제공
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from ..core.config import get_settings

# 설정에서 DB 연결 URL 가져오기
settings = get_settings()
DATABASE_URL = settings.DATABASE_URL

# SQLAlchemy Engine 생성
# pool_pre_ping=True: 연결을 사용하기 전에 유효성을 검사하여 끊어진 연결 재사용 방지
# echo=False: SQL 쿼리 로깅 비활성화 (개발 중에는 True로 설정 가능)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False  # 개발 중 SQL 로깅이 필요하면 True로 변경
)

# DB 세션 생성기 정의
# autocommit=False: 명시적인 commit 필요
# autoflush=False: 명시적인 flush 필요
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 의존성 주입(Dependency Injection)을 위한 DB 세션 생성기.
    요청이 끝날 때 세션을 자동으로 닫습니다.
    
    Usage:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        # DB 세션을 API 엔드포인트에 제공
        yield db
    finally:
        # 요청 완료 후 세션 닫기
        db.close()


# 참고: Base 클래스 임포트 및 테이블 생성 (main.py 또는 별도의 스크립트에서 호출)
# from .models import Base
# Base.metadata.create_all(bind=engine)

