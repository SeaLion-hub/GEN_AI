"""
DB 모델 정의
User, Trade, ReviewNote 테이블 및 관계 설정
"""

import json
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB  # JSONB 타입 사용
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
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationship 정의 (User 삭제 시 관련 Trade, Review도 함께 삭제)
    trades = relationship("Trade", back_populates="owner", cascade="all, delete-orphan")
    reviews = relationship("ReviewNote", back_populates="user", cascade="all, delete-orphan")


class Trade(Base):
    """
    Trade 테이블: 사용자의 개별 거래 내역 저장
    """
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    # FK: User 테이블 참조 (User 삭제 시 이 레코드도 삭제)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    ticker = Column(String, index=True, nullable=False)  # 종목 코드
    buy_date = Column(DateTime)
    sell_date = Column(DateTime)
    profit_loss_rate = Column(Float)
    
    # Relationship 정의
    owner = relationship("User", back_populates="trades")
    # Trade 삭제 시 관련 ReviewNote도 함께 삭제
    review_note = relationship("ReviewNote", back_populates="trade", uselist=False, cascade="all, delete-orphan")


class ReviewNote(Base):
    """
    ReviewNote 테이블: AI 분석의 핵심 결과물 및 복기 메모 저장
    [B님의 제안에 따라 objective_context가 분리됨]
    """
    __tablename__ = "review_notes"

    id = Column(Integer, primary_key=True, index=True)
    # FK: User 테이블 참조 (User 삭제 시 이 레코드도 삭제)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # FK: Trade 테이블 참조 (Trade 삭제 시 이 레코드도 삭제)
    trade_id = Column(Integer, ForeignKey("trades.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    # AI 피드백을 읽고 난 후 사용자가 최종적으로 작성하는 '성찰 메모'
    final_memo = Column(String, nullable=True) 
    
    # [사용자 입력] 주관적
    subjective_memo = Column(String)
    emotion_tags = Column(JSONB) # List[str] (JSONB로 저장)
    
    # --- [B님 제안으로 변경된 부분] ---
    # [data-processor 결과] (분리된 컬럼)
    chart_context = Column(JSONB, nullable=True)     # data_processor의 'chart_indicators'
    news_context = Column(JSONB, nullable=True)      # 'related_news'
    market_context = Column(JSONB, nullable=True)    # 'market_indicators'
    financial_context = Column(JSONB, nullable=True) # 'financial_indicators'
    # --- [변경 완료] ---
    
    # [AI 분석 결과]
    ai_analysis = Column(String)
    ai_questions = Column(String)
    primary_type = Column(String, index=True)
    secondary_type = Column(String, nullable=True)
    
    # Relationship 정의
    user = relationship("User", back_populates="reviews")
    trade = relationship("Trade", back_populates="review_note")