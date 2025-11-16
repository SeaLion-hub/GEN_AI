"""
DB 세션 설정 및 관리 (비동기)
FastAPI 의존성 주입을 위한 get_db() 함수 제공
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator

from ..core.config import get_settings

# 설정에서 DB 연결 URL 가져오기
settings = get_settings()
DATABASE_URL = settings.DATABASE_URL

# PostgreSQL URL을 비동기 형식으로 변환
# postgresql:// -> postgresql+asyncpg://
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# SQLAlchemy 비동기 Engine 생성
# pool_pre_ping=True: 연결을 사용하기 전에 유효성을 검사하여 끊어진 연결 재사용 방지
# echo=False: SQL 쿼리 로깅 비활성화 (개발 중에는 True로 설정 가능)
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,  # 개발 중 SQL 로깅이 필요하면 True로 변경
    future=True
)

# 비동기 DB 세션 생성기 정의
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 의존성 주입(Dependency Injection)을 위한 비동기 DB 세션 생성기.
    요청이 끝날 때 세션을 자동으로 닫습니다.
    
    주의: commit은 각 엔드포인트에서 명시적으로 수행해야 합니다.
    
    Usage:
        @router.post("/items")
        async def create_item(db: AsyncSession = Depends(get_db)):
            item = Item(...)
            db.add(item)
            await db.commit()  # 명시적 commit
            return item
    """
    async with AsyncSessionLocal() as session:
        try:
            # DB 세션을 API 엔드포인트에 제공
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# 참고: Base 클래스 임포트 및 테이블 생성 (main.py 또는 별도의 스크립트에서 호출)
# from .models import Base
# Base.metadata.create_all(bind=engine)

