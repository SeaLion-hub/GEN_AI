"""
설정 관리 모듈
환경 변수를 중앙에서 관리하고 Pydantic Settings로 검증
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스
    환경 변수에서 값을 로드하며, .env 파일도 자동으로 읽습니다.
    """
    
    # 앱 기본 설정
    APP_NAME: str = "GEN_AI Core API"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    
    # 데이터베이스 설정
    DATABASE_URL: str
    
    # JWT 인증 설정
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OpenAI 설정
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    
    # 외부 서비스 URL
    DATA_PROCESSOR_URL: str = "http://data_processor:5001"
    EMBEDDING_API_URL: Optional[str] = None  # 향후 구현 예정
    
    # Redis 설정 (캐싱용, 향후 구현 예정)
    REDIS_URL: Optional[str] = None
    
    # 서비스 타임아웃 설정 (초)
    DATA_PROCESSOR_TIMEOUT: int = 10
    EMBEDDING_API_TIMEOUT: int = 5
    
    # 재시도 설정
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    설정 인스턴스를 싱글톤으로 반환
    lru_cache를 사용하여 한 번만 로드하고 재사용
    """
    return Settings()

