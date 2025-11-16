"""
투자 복기 API 엔드포인트
복기 노트 생성, 조회, 'Final Memo' 수정
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated, List
import httpx
import re
from pydantic import BaseModel, Field # B님의 'Final Memo' 스키마를 위해 임포트

from app.db.session import get_db
from app.db.models import User, Trade, ReviewNote
from app.api.auth import get_current_user
from app.models.schemas import (
    ReviewCreateRequest,
    ReviewNoteResponse,
    AIAnalysisResponse
)
from app.core.config import get_settings
from app.core.logging_config import get_logger

# 로거 설정
logger = get_logger(__name__)

router = APIRouter(prefix="/review", tags=["Review"])

# 설정 가져오기
settings = get_settings()
DATA_PROCESSOR_URL = f"{settings.DATA_PROCESSOR_URL}/api/market/context"


# --- Pydantic 스키마 추가 (B님의 'Final Memo' 기능용) ---
class FinalMemoUpdate(BaseModel):
    final_memo: str = Field(..., max_length=5000, description="사용자의 최종 성찰 메모")


def extract_profit_loss_rate(trade_info: str) -> float | None:
    """
    trade_info 문자열에서 손익률 추출
    예: "삼성전자 (-6.5%)" -> -6.5
    """
    match = re.search(r'\(([+-]?\d+\.?\d*)%\)', trade_info)
    if match:
        return float(match.group(1))
    return None


@router.post("", response_model=AIAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    request: ReviewCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    새로운 투자 복기 노트를 생성합니다.
    
    프로세스:
    1. data_processor 호출 (객관적 데이터 수집)
    2. gpt_service 호출 (AI 분석 수행)
    3. Trade 및 ReviewNote 레코드 생성 (DB 저장)
    """
    
    # --- 1. data_processor 호출 (객관적 데이터 확보) ---
    objective_data = {}
    try:
        logger.info("시장 데이터 수집 시작", ticker=request.ticker, user_id=current_user.id)
        async with httpx.AsyncClient(timeout=settings.DATA_PROCESSOR_TIMEOUT) as client:
            params = {"ticker": request.ticker, "market_index": "^KS11"} # (KOSPI 기본값)
            response = await client.get(DATA_PROCESSOR_URL, params=params)
            response.raise_for_status()
            objective_data = response.json()
            logger.info("시장 데이터 수집 완료", ticker=request.ticker, user_id=current_user.id)
            
    except httpx.HTTPStatusError as e:
        logger.error(
            "시장 데이터 서버 연결 실패",
            error=str(e),
            status_code=e.response.status_code,
            ticker=request.ticker
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="시장 데이터 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
        )
    except httpx.ReadTimeout:
        logger.error("시장 데이터 서버 타임아웃", timeout=settings.DATA_PROCESSOR_TIMEOUT)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="시장 데이터 서버(data_processor) 응답 시간이 초과되었습니다."
        )
    except Exception as e:
        logger.error("시장 데이터 수집 중 예외 발생", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="시장 데이터를 가져오는 중 오류가 발생했습니다."
        )

    # --- 2. AI 입력 데이터 준비 ---
    # (B님의 gpt_service로 보내는 입력 데이터)
    ai_input_data = {
        "trade_info": request.trade_info,
        "subjective_data": {
            "emotion_tags": request.emotion_tags,
            "memo": request.memo
        },
        "objective_data_at_sell_or_buy": {
            "chart_indicators": objective_data.get("chart_indicators", {}).get("rsi_status", "N/A"),
            "related_news": [
                news.get("title", "N/A") 
                for news in objective_data.get("related_news", [])[:3]
            ],
            "market_indicators": objective_data.get("market_indicators", {}).get("status", "N/A")
        }
    }

    # --- 3. gpt_service 호출 (AI 분석 및 분류) ---
    from app.services.gpt_service import get_ai_feedback
    logger.info("AI 분석 시작", user_id=current_user.id, ticker=request.ticker)
    ai_response = await get_ai_feedback(ai_input_data)
    
    if ai_response.get("error"):
        logger.error("AI 분석 실패", error=ai_response.get("error"), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 분석 실패: {ai_response['error']}"
        )
    
    logger.info("AI 분석 완료", user_id=current_user.id, primary_type=ai_response.get("primary_type"))

    # --- 4. Trade 및 ReviewNote 레코드 생성 및 저장 (트랜잭션) ---
    try:
        profit_loss_rate = extract_profit_loss_rate(request.trade_info)
        
        # 새로운 Trade 생성
        new_trade = Trade(
            user_id=current_user.id,
            ticker=request.ticker,
            profit_loss_rate=profit_loss_rate
        )
        db.add(new_trade)
        await db.flush()  # trade_id를 얻기 위해 flush

        # [B님 제안 적용] ReviewNote 레코드 생성 (컬럼 분리)
        new_note = ReviewNote(
            user_id=current_user.id,
            trade_id=new_trade.id,
            
            subjective_memo=request.memo,
            emotion_tags=request.emotion_tags,
            
            # (B님이 제안한 분리된 컬럼으로 저장)
            chart_context=objective_data.get("chart_indicators"),
            news_context=objective_data.get("related_news"),
            market_context=objective_data.get("market_indicators"),
            financial_context=objective_data.get("financial_indicators"),

            # (AI 결과)
            ai_analysis=ai_response.get("analysis"),
            ai_questions=ai_response.get("questions"),
            primary_type=ai_response.get("primary_type"),
            secondary_type=ai_response.get("secondary_type"),
            
            # (final_memo는 이 단계에서는 null)
        )
        db.add(new_note)
        
        await db.commit()
        await db.refresh(new_note)
        
        logger.info(
            "복기 노트 생성 완료",
            user_id=current_user.id,
            review_id=new_note.id,
            trade_id=new_trade.id
        )
        
    except Exception as e:
        await db.rollback()
        logger.error(
            "복기 노트 저장 실패",
            error=str(e),
            error_type=type(e).__name__,
            user_id=current_user.id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="복기 노트를 저장하는 중 오류가 발생했습니다."
        )

    # --- 5. AI 응답 반환 ---
    # (프론트엔드는 이 응답을 받아 사용자에게 '즉시' AI 피드백을 보여줌)
    return AIAnalysisResponse(
        analysis=ai_response.get("analysis", ""),
        questions=ai_response.get("questions", ""),
        primary_type=ai_response.get("primary_type", ""),
        secondary_type=ai_response.get("secondary_type")
    )


@router.get("/{review_id}", response_model=ReviewNoteResponse)
async def get_review(
    review_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    특정 복기 노트 조회
    (B님의 'final_memo'가 포함된 전체 노트를 반환합니다)
    """
    result = await db.execute(
        select(ReviewNote).where(
            ReviewNote.id == review_id,
            ReviewNote.user_id == current_user.id
        )
    )
    review = result.scalar_one_or_none()
    
    if not review:
        logger.warning("복기 노트 조회 실패", review_id=review_id, user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="복기 노트를 찾을 수 없습니다."
        )
    
    return review


@router.get("", response_model=list[ReviewNoteResponse])
async def list_reviews(
    # [Pylance 오류 수정] 기본값이 없는 파라미터(db, current_user)를
    # 기본값이 있는 파라미터(skip, limit) 앞으로 이동
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 20
):
    """
    현재 사용자의 복기 노트 목록 조회
    """
    result = await db.execute(
        select(ReviewNote)
        .where(ReviewNote.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .order_by(ReviewNote.created_at.desc())
    )
    reviews = result.scalars().all()
    
    return list(reviews)


@router.patch("/{review_id}/final_memo", response_model=ReviewNoteResponse)
async def update_final_memo(
    review_id: int,
    memo_data: FinalMemoUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    [B님 신규 기능] AI 피드백 확인 후, 'Final Memo'를 저장/수정합니다.
    """
    logger.info(
        "Final Memo 업데이트 시작", 
        review_id=review_id, 
        user_id=current_user.id
    )
    
    # 1. 본인의 복기 노트가 맞는지 확인
    result = await db.execute(
        select(ReviewNote).where(
            ReviewNote.id == review_id,
            ReviewNote.user_id == current_user.id
        )
    )
    review = result.scalar_one_or_none()
    
    if not review:
        logger.warning(
            "Final Memo 업데이트 실패: 노트 없음", 
            review_id=review_id, 
            user_id=current_user.id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="복기 노트를 찾을 수 없습니다."
        )
        
    # 2. 'final_memo' 컬럼에 메모 업데이트
    try:
        review.final_memo = memo_data.final_memo
        db.add(review)
        await db.commit()
        await db.refresh(review)
        
        logger.info(
            "Final Memo 업데이트 완료", 
            review_id=review.id, 
            user_id=current_user.id
        )
        
        # 3. 업데이트된 전체 노트 반환
        return review
        
    except Exception as e:
        await db.rollback()
        logger.error(
            "Final Memo 저장 실패", 
            error=str(e), 
            review_id=review_id, 
            user_id=current_user.id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="메모 저장 중 오류가 발생했습니다."
        )