"""
Pydantic 스키마 정의
API 요청/응답 데이터 유효성 검사 및 직렬화
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
import re

# ==================== 인증 관련 스키마 ====================
# (UserCreate, UserResponse, Token, TokenData ... 이전과 동일)
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="사용자 이름 (이메일 또는 고유 ID)")
    password: str = Field(..., min_length=8, description="비밀번호 (최소 8자)")

class UserResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None

# ==================== 거래(Trade) 관련 스키마 ====================
# (TradeCreate, TradeResponse ... 이전과 동일)
class TradeCreate(BaseModel):
    ticker: str = Field(..., description="종목 코드 (예: 005930.KS)")
    buy_date: Optional[datetime] = None
    sell_date: Optional[datetime] = None
    profit_loss_rate: Optional[float] = Field(None, description="손익률 (%)")

class TradeResponse(BaseModel):
    id: int
    user_id: int
    ticker: str
    buy_date: Optional[datetime]
    sell_date: Optional[datetime]
    profit_loss_rate: Optional[float]
    class Config:
        from_attributes = True

# ==================== 복기 노트(ReviewNote) 관련 스키마 ====================

# (ReviewCreateRequest ... 이전과 동일)
# [B님] 프론트엔드의 '입력' 스키마는 변경할 필요가 없습니다.
class ReviewCreateRequest(BaseModel):
    ticker: str = Field(..., example="005930.KS", description="종목 코드")
    trade_info: str = Field(..., example="삼성전자 (-6.5%)", description="거래 정보 요약")
    emotion_tags: List[str] = Field(..., example=["공포", "패닉"], description="감정 태그 리스트")
    memo: str = Field(..., min_length=10, max_length=2000, example="미국 증시 폭락하고 KOSPI -3% 찍히는 거 보고...", description="주관적 메모")
    
    @field_validator('ticker')
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("종목 코드는 필수입니다.")
        ticker_pattern = re.compile(r'^[A-Z0-9]{1,10}(\.[A-Z]{2})?$', re.IGNORECASE)
        if not ticker_pattern.match(v.strip()):
            raise ValueError("종목 코드 형식이 올바르지 않습니다. 한국 주식: 005930.KS, 미국 주식: AAPL 형식을 사용해주세요.")
        return v.strip().upper()
    
    @field_validator('trade_info')
    @classmethod
    def validate_trade_info(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("거래 정보는 필수입니다.")
        profit_loss_pattern = re.compile(r'.*\([+-]?\d+\.?\d*%\)')
        if not profit_loss_pattern.search(v):
            raise ValueError("거래 정보는 '종목명 (손익률%)' 형식이어야 합니다. 예: '삼성전자 (-6.5%)' 또는 'AAPL (+12.3%)'")
        return v.strip()
    
    @field_validator('emotion_tags')
    @classmethod
    def validate_emotion_tags(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("최소 1개 이상의 감정 태그가 필요합니다.")
        if len(v) > 10:
            raise ValueError("감정 태그는 최대 10개까지 입력 가능합니다.")
        validated_tags = []
        for tag in v:
            tag = tag.strip()
            if not tag:
                continue
            if len(tag) > 20:
                raise ValueError(f"감정 태그 '{tag}'는 20자를 초과할 수 없습니다.")
            validated_tags.append(tag)
        if not validated_tags:
            raise ValueError("유효한 감정 태그가 없습니다.")
        return validated_tags
    
    @field_validator('memo')
    @classmethod
    def validate_memo(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("주관적 메모는 필수입니다.")
        v = v.strip()
        if len(v) < 10:
            raise ValueError("주관적 메모는 최소 10자 이상이어야 합니다.")
        if len(v) > 2000:
            raise ValueError("주관적 메모는 최대 2000자까지 입력 가능합니다.")
        return v

# --- [B님 제안으로 변경된 부분] ---
# ReviewNote '응답' 스키마
class ReviewNoteResponse(BaseModel):
    """복기 노트 응답 스키마 (DB 모델과 일치)"""
    id: int
    user_id: int
    trade_id: int
    created_at: datetime
    subjective_memo: Optional[str]
    emotion_tags: Optional[List[str]]
    
    # objective_context 대신 분리된 컬럼으로 응답
    chart_context: Optional[dict]
    news_context: Optional[dict]
    market_context: Optional[dict]
    financial_context: Optional[dict]
    
    ai_analysis: Optional[str]
    ai_questions: Optional[str]
    primary_type: Optional[str]
    secondary_type: Optional[str]
    
    class Config:
        from_attributes = True
# --- [변경 완료] ---

class AIAnalysisResponse(BaseModel):
    """AI 분석 결과 응답 스키마 (gpt_service.py 응답 형식)"""
    analysis: str = Field(..., description="Part 1: 객관적인 분석")
    questions: str = Field(..., description="Part 2: 자기 성찰을 위한 질문")
    primary_type: str = Field(..., description="Part 3: 주요 실패 원인")
    secondary_type: Optional[str] = Field(None, description="Part 3: 보조 실패 원인 (선택적)")

# ==================== 리포트 관련 스키마 (향후 구현 예정) ====================
# (ReportRequest, ReportResponse ... 이전과 동일)
class ReportRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    failure_types: Optional[List[str]] = None

class ReportResponse(BaseModel):
    user_id: int
    total_trades: int
    total_reviews: int
    failure_type_distribution: dict
    improvement_trends: dict
    generated_at: datetime