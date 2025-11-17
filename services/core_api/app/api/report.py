"""
투자 리포트 API 엔드포인트
사용자의 복기 데이터를 집계하여 통계 리포트 생성
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Annotated, Dict, List, Any
from datetime import datetime, timedelta

from app.db.session import get_db
from app.db.models import User, Trade, ReviewNote
from app.api.auth import get_current_user
from app.models.schemas import ReportResponse
from app.core.logging_config import get_logger

# 로거 설정
logger = get_logger(__name__)

router = APIRouter(prefix="/report", tags=["Report"])


@router.get("", response_model=ReportResponse)
async def generate_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    days: int = 30  # 기본적으로 최근 30일 데이터 분석
):
    """
    투자 분석 리포트 생성
    - 실패 유형별 분포 (Pie Chart용)
    - 감정 태그별 통계 (Bar Chart용)
    - 주요 개선 필요 사항 도출
    """
    logger.info("리포트 생성 요청", user_id=current_user.id, period_days=days)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # --- 1. 기본 통계 데이터 조회 (SQL Aggregation) ---
    
    # 1-1. 전체 거래 및 복기 수
    # (ReviewNote와 Trade를 조인하여 기간 내 데이터 조회)
    query_base = select(ReviewNote).join(Trade).where(
        ReviewNote.user_id == current_user.id,
        ReviewNote.created_at >= start_date
    )
    
    result_notes = await db.execute(query_base)
    notes = result_notes.scalars().all()
    
    total_reviews = len(notes)
    if total_reviews == 0:
        # 데이터가 없으면 빈 리포트 반환
        return ReportResponse(
            user_id=current_user.id,
            total_trades=0,
            total_reviews=0,
            failure_type_distribution={},
            improvement_trends={},
            generated_at=datetime.utcnow()
        )

    # --- 2. 실패 유형별 분석 (Primary Type Distribution) ---
    # "B님은 'FOMO_추격매수'를 가장 많이 했습니다"
    
    failure_dist = {}
    for note in notes:
        p_type = note.primary_type
        if p_type:
            failure_dist[p_type] = failure_dist.get(p_type, 0) + 1
            
    # (빈도순 정렬)
    sorted_failure_dist = dict(sorted(
        failure_dist.items(), 
        key=lambda item: item[1], 
        reverse=True
    ))

    # --- 3. 감정 태그별 손실률 분석 (Emotion Analysis) ---
    # "B님은 '공포'를 느꼈을 때 평균 -15% 손실을 봅니다"
    # (JSONB 컬럼인 emotion_tags를 파이썬 레벨에서 집계)
    
    emotion_stats = {}  # { "공포": {"count": 5, "total_loss": -50.0} }
    
    for note in notes:
        # 감정 태그 리스트 가져오기
        tags = note.emotion_tags if note.emotion_tags else []
        # 해당 거래의 손익률 가져오기
        pl_rate = note.trade.profit_loss_rate if note.trade.profit_loss_rate else 0.0
        
        for tag in tags:
            if tag not in emotion_stats:
                emotion_stats[tag] = {"count": 0, "total_loss": 0.0}
            
            emotion_stats[tag]["count"] += 1
            emotion_stats[tag]["total_loss"] += pl_rate

    # 평균 손실률 계산 및 포맷팅
    formatted_emotion_stats = {}
    for tag, data in emotion_stats.items():
        avg_loss = data["total_loss"] / data["count"]
        formatted_emotion_stats[tag] = {
            "count": data["count"],
            "avg_profit_loss": round(avg_loss, 2)
        }

    # --- 4. 최종 응답 구성 ---
    return ReportResponse(
        user_id=current_user.id,
        total_trades=total_reviews, # (현재는 1:1 관계이므로 동일 취급)
        total_reviews=total_reviews,
        failure_type_distribution=sorted_failure_dist,
        improvement_trends=formatted_emotion_stats, # (프론트엔드에서 감정별 차트로 표시)
        generated_at=datetime.utcnow()
    )