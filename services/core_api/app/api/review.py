"""
투자 복기 API 엔드포인트
복기 노트 생성 및 조회
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated
import httpx
import re

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
    1. data_processor 호출하여 시장 데이터 수집
    2. gpt_service 호출하여 AI 분석 수행
    3. Trade 레코드 생성 (또는 기존 Trade 조회)
    4. ReviewNote 레코드 생성 및 저장
    
    트랜잭션 관리: AI 호출 실패 시에도 Trade가 남지 않도록 전체를 하나의 트랜잭션으로 처리
    
    Returns:
        AIAnalysisResponse: AI 분석 결과 (analysis, questions, primary_type, secondary_type)
    """
    
    # --- 1. data_processor 호출 (객관적 데이터 확보) ---
    objective_data = {}
    try:
        logger.info("시장 데이터 수집 시작", ticker=request.ticker)
        async with httpx.AsyncClient(timeout=settings.DATA_PROCESSOR_TIMEOUT) as client:
            params = {"ticker": request.ticker, "market_index": "^KS11"}
            response = await client.get(DATA_PROCESSOR_URL, params=params)
            response.raise_for_status()
            objective_data = response.json()
            logger.info("시장 데이터 수집 완료", ticker=request.ticker)
            
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
        logger.error(
            "시장 데이터 수집 중 예외 발생",
            error=str(e),
            error_type=type(e).__name__,
            ticker=request.ticker
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="시장 데이터를 가져오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )

    # --- 2. AI 입력 데이터 준비 ---
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
    # 트랜잭션 시작 전에 AI 호출하여 실패 시 DB 작업을 하지 않도록 함
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
    # AI 호출이 성공한 후에만 DB 작업 수행
    try:
        # trade_info에서 손익률 추출
        profit_loss_rate = extract_profit_loss_rate(request.trade_info)
        
        # 새로운 Trade 생성
        new_trade = Trade(
            user_id=current_user.id,
            ticker=request.ticker,
            profit_loss_rate=profit_loss_rate
        )
        db.add(new_trade)
        await db.flush()  # trade_id를 얻기 위해 flush (아직 commit은 안 함)

        # ReviewNote 레코드 생성
        new_note = ReviewNote(
            user_id=current_user.id,
            trade_id=new_trade.id,
            subjective_memo=request.memo,
            emotion_tags=request.emotion_tags,  # JSONB로 자동 변환
            objective_context=objective_data,  # JSONB로 자동 변환
            ai_analysis=ai_response.get("analysis"),
            ai_questions=ai_response.get("questions"),
            primary_type=ai_response.get("primary_type"),
            secondary_type=ai_response.get("secondary_type")
        )
        db.add(new_note)
        
        # 전체 트랜잭션 커밋 (Trade와 ReviewNote 모두 성공적으로 저장)
        await db.commit()
        await db.refresh(new_note)
        
        logger.info(
            "복기 노트 생성 완료",
            user_id=current_user.id,
            review_id=new_note.id,
            trade_id=new_trade.id
        )
        
    except Exception as e:
        # 에러 발생 시 롤백 (Trade도 함께 롤백됨)
        await db.rollback()
        logger.error(
            "복기 노트 저장 실패",
            error=str(e),
            error_type=type(e).__name__,
            user_id=current_user.id,
            ticker=request.ticker,
            traceback=str(e.__traceback__) if hasattr(e, '__traceback__') else None
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="복기 노트를 저장하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )

    # --- 5. AI 응답 반환 ---
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
    본인의 복기 노트만 조회 가능합니다.
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
    skip: int = 0,
    limit: int = 20,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
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
