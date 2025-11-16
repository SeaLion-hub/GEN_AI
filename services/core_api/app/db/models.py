"""
DB 모델 정의
User, Trade, ReviewNote 테이블 및 관계 설정
"""

import json
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime


# SQLAlchemy 모델의 기본 클래스
class Base(DeclarativeBase):
    pass


class User(Base):
    """
    User 테이블: 사용자 인증 및 기본 정보 저장
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # username을 이메일로 사용할 경우를 고려해 index 추가
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationship 정의
    trades = relationship("Trade", back_populates="owner", cascade="all, delete-orphan")
    reviews = relationship("ReviewNote", back_populates="user", cascade="all, delete-orphan")


class Trade(Base):
    """
    Trade 테이블: 사용자의 개별 거래 내역 저장
    """
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    # FK: User 테이블 참조
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    ticker = Column(String, index=True, nullable=False)  # 종목 코드
    buy_date = Column(DateTime)
    sell_date = Column(DateTime)
    # 실제 손익률 또는 절대 손익 금액 등을 저장할 수 있음
    profit_loss_rate = Column(Float)
    
    # Relationship 정의
    owner = relationship("User", back_populates="trades")
    review_note = relationship("ReviewNote", back_populates="trade", uselist=False, cascade="all, delete-orphan")


class ReviewNote(Base):
    """
    ReviewNote 테이블: AI 분석의 핵심 결과물 및 복기 메모 저장
    """
    __tablename__ = "review_notes"

    id = Column(Integer, primary_key=True, index=True)
    # FK: User 테이블 참조
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # FK: Trade 테이블 참조 (하나의 거래에 하나의 복기 노트)
    trade_id = Column(Integer, ForeignKey("trades.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # [사용자 입력] 주관적 메모
    subjective_memo = Column(String)
    # [사용자 입력] 감정 태그 (review.py와 일치)
    emotion_tags = Column(JSONB)
    
    # [data-processor 결과] 시장 데이터 (JSONB 사용)
    objective_context = Column(JSONB)
    
    # [AI 분석 결과 Part 1] 분석 결과
    ai_analysis = Column(String)
    # [AI 분석 결과 Part 2] 성찰 유도 질문
    ai_questions = Column(String)
    # [AI 분석 결과 Part 3] 실패 유형 분류 (review.py와 일치)
    primary_type = Column(String, index=True)  # 주요 원인
    secondary_type = Column(String, nullable=True)  # 보조 원인 (선택적)
    
    # Relationship 정의
    user = relationship("User", back_populates="reviews")
    trade = relationship("Trade", back_populates="review_note")

