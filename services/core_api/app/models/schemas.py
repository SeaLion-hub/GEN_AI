"""
Pydantic 스키마 정의
API 요청/응답 데이터 유효성 검사 및 직렬화
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ==================== 인증 관련 스키마 ====================

class UserCreate(BaseModel):
    """사용자 생성 요청 스키마"""
    username: str = Field(..., min_length=3, max_length=50, description="사용자 이름 (이메일 또는 고유 ID)")
    password: str = Field(..., min_length=8, description="비밀번호 (최소 8자)")


class UserResponse(BaseModel):
    """사용자 정보 응답 스키마"""
    id: int
    username: str
    is_active: bool
    
    class Config:
        from_attributes = True  # SQLAlchemy 모델에서 자동 변환


class Token(BaseModel):
    """JWT 토큰 응답 스키마"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """JWT 토큰 페이로드 데이터"""
    username: Optional[str] = None


# ==================== 거래(Trade) 관련 스키마 ====================

class TradeCreate(BaseModel):
    """거래 생성 요청 스키마"""
    ticker: str = Field(..., description="종목 코드 (예: 005930.KS)")
    buy_date: Optional[datetime] = None
    sell_date: Optional[datetime] = None
    profit_loss_rate: Optional[float] = Field(None, description="손익률 (%)")


class TradeResponse(BaseModel):
    """거래 정보 응답 스키마"""
    id: int
    user_id: int
    ticker: str
    buy_date: Optional[datetime]
    sell_date: Optional[datetime]
    profit_loss_rate: Optional[float]
    
    class Config:
        from_attributes = True


# ==================== 복기 노트(ReviewNote) 관련 스키마 ====================

class ReviewCreateRequest(BaseModel):
    """복기 노트 생성 요청 스키마 (review.py와 일치)"""
    ticker: str = Field(..., example="005930.KS", description="종목 코드")
    trade_info: str = Field(..., example="삼성전자 (-6.5%)", description="거래 정보 요약")
    emotion_tags: List[str] = Field(..., example=["공포", "패닉"], description="감정 태그 리스트")
    memo: str = Field(..., example="미국 증시 폭락하고 KOSPI -3% 찍히는 거 보고...", description="주관적 메모")


class ReviewNoteResponse(BaseModel):
    """복기 노트 응답 스키마"""
    id: int
    user_id: int
    trade_id: int
    created_at: datetime
    subjective_memo: Optional[str]
    emotion_tags: Optional[List[str]]
    objective_context: Optional[dict]  # JSONB 데이터
    ai_analysis: Optional[str]
    ai_questions: Optional[str]
    primary_type: Optional[str]
    secondary_type: Optional[str]
    
    class Config:
        from_attributes = True


class AIAnalysisResponse(BaseModel):
    """AI 분석 결과 응답 스키마 (gpt_service.py 응답 형식)"""
    analysis: str = Field(..., description="Part 1: 객관적인 분석")
    questions: str = Field(..., description="Part 2: 자기 성찰을 위한 질문")
    primary_type: str = Field(..., description="Part 3: 주요 실패 원인")
    secondary_type: Optional[str] = Field(None, description="Part 3: 보조 실패 원인 (선택적)")


# ==================== 리포트 관련 스키마 (향후 구현 예정) ====================

class ReportRequest(BaseModel):
    """리포트 생성 요청 스키마"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    failure_types: Optional[List[str]] = None  # 필터링할 실패 유형


class ReportResponse(BaseModel):
    """리포트 응답 스키마"""
    user_id: int
    total_trades: int
    total_reviews: int
    failure_type_distribution: dict
    improvement_trends: dict
    generated_at: datetime

