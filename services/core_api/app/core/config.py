"""
설정 관리 모듈
환경 변수를 중앙에서 관리하고 Pydantic Settings로 검증
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache
from typing import Optional
import re


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
    DATABASE_URL: str = Field(..., description="PostgreSQL 데이터베이스 연결 URL")
    
    # JWT 인증 설정
    SECRET_KEY: str = Field(..., min_length=32, description="JWT 토큰 서명용 시크릿 키 (최소 32자)")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OpenAI 설정
    OPENAI_API_KEY: str = Field(..., description="OpenAI API 키")
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
    
    @field_validator('DATABASE_URL')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """데이터베이스 URL 형식 검증"""
        if not v:
            raise ValueError("DATABASE_URL이 설정되지 않았습니다.")
        # postgresql:// 또는 postgres://로 시작하는지 확인
        if not (v.startswith("postgresql://") or v.startswith("postgres://")):
            raise ValueError("DATABASE_URL은 postgresql:// 또는 postgres://로 시작해야 합니다.")
        return v
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """시크릿 키 강도 검증"""
        if not v:
            raise ValueError("SECRET_KEY가 설정되지 않았습니다.")
        if len(v) < 32:
            raise ValueError("SECRET_KEY는 최소 32자 이상이어야 합니다. (보안 강화)")
        return v
    
    @field_validator('OPENAI_API_KEY')
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        """OpenAI API 키 형식 검증"""
        if not v:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        if not v.startswith("sk-"):
            raise ValueError("OpenAI API 키는 'sk-'로 시작해야 합니다.")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    설정 인스턴스를 싱글톤으로 반환
    lru_cache를 사용하여 한 번만 로드하고 재사용
    
    시작 시 필수 환경 변수를 검증합니다.
    """
    try:
        settings = Settings()
        return settings
    except Exception as e:
        # 환경 변수 검증 실패 시 명확한 에러 메시지
        error_msg = str(e)
        if "DATABASE_URL" in error_msg:
            print("❌ 오류: DATABASE_URL 환경 변수가 설정되지 않았거나 형식이 잘못되었습니다.")
            print("   예시: postgresql://user:password@localhost:5432/dbname")
        elif "SECRET_KEY" in error_msg:
            print("❌ 오류: SECRET_KEY 환경 변수가 설정되지 않았거나 너무 짧습니다.")
            print("   최소 32자 이상의 랜덤 문자열이 필요합니다.")
        elif "OPENAI_API_KEY" in error_msg:
            print("❌ 오류: OPENAI_API_KEY 환경 변수가 설정되지 않았거나 형식이 잘못되었습니다.")
            print("   OpenAI API 키는 'sk-'로 시작해야 합니다.")
        else:
            print(f"❌ 환경 변수 설정 오류: {error_msg}")
        print("\n.env 파일을 확인하거나 환경 변수를 설정해주세요.")
        raise

