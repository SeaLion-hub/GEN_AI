"""
Pydantic 스키마 정의
API 요청/응답 데이터 유효성 검사 및 직렬화
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
import re


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
    memo: str = Field(..., min_length=10, max_length=2000, example="미국 증시 폭락하고 KOSPI -3% 찍히는 거 보고...", description="주관적 메모")
    
    @field_validator('ticker')
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """종목 코드 형식 검증"""
        if not v or not v.strip():
            raise ValueError("종목 코드는 필수입니다.")
        
        # 한국 주식: 6자리 숫자 + .KS 또는 .KQ (예: 005930.KS)
        # 미국 주식: 영문 대문자 (예: AAPL, TSLA)
        # 일반 형식: 영문/숫자 조합
        ticker_pattern = re.compile(r'^[A-Z0-9]{1,10}(\.[A-Z]{2})?$', re.IGNORECASE)
        
        if not ticker_pattern.match(v.strip()):
            raise ValueError(
                "종목 코드 형식이 올바르지 않습니다. "
                "한국 주식: 005930.KS, 미국 주식: AAPL 형식을 사용해주세요."
            )
        
        return v.strip().upper()
    
    @field_validator('trade_info')
    @classmethod
    def validate_trade_info(cls, v: str) -> str:
        """거래 정보 형식 검증"""
        if not v or not v.strip():
            raise ValueError("거래 정보는 필수입니다.")
        
        # 손익률 형식 검증: "종목명 (손익률%)" 형식
        # 예: "삼성전자 (-6.5%)", "AAPL (+12.3%)"
        profit_loss_pattern = re.compile(r'.*\([+-]?\d+\.?\d*%\)')
        
        if not profit_loss_pattern.search(v):
            raise ValueError(
                "거래 정보는 '종목명 (손익률%)' 형식이어야 합니다. "
                "예: '삼성전자 (-6.5%)' 또는 'AAPL (+12.3%)'"
            )
        
        return v.strip()
    
    @field_validator('emotion_tags')
    @classmethod
    def validate_emotion_tags(cls, v: List[str]) -> List[str]:
        """감정 태그 검증"""
        if not v:
            raise ValueError("최소 1개 이상의 감정 태그가 필요합니다.")
        
        if len(v) > 10:
            raise ValueError("감정 태그는 최대 10개까지 입력 가능합니다.")
        
        # 허용된 감정 태그 목록 (선택사항 - 필요시 확장)
        valid_emotions = [
            "공포", "패닉", "후회", "절망", "희망고문", "오기", "불안", 
            "스트레스", "편향", "무모함", "실망", "무지", "기쁨", "만족"
        ]
        
        # 각 태그 검증
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
        """메모 검증"""
        if not v or not v.strip():
            raise ValueError("주관적 메모는 필수입니다.")
        
        v = v.strip()
        
        if len(v) < 10:
            raise ValueError("주관적 메모는 최소 10자 이상이어야 합니다.")
        
        if len(v) > 2000:
            raise ValueError("주관적 메모는 최대 2000자까지 입력 가능합니다.")
        
        return v


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

