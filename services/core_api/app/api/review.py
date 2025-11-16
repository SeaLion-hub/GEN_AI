"""
투자 복기 API 엔드포인트
복기 노트 생성 및 조회
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
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
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    새로운 투자 복기 노트를 생성합니다.
    
    프로세스:
    1. data_processor 호출하여 시장 데이터 수집
    2. gpt_service 호출하여 AI 분석 수행
    3. Trade 레코드 생성 (또는 기존 Trade 조회)
    4. ReviewNote 레코드 생성 및 저장
    
    Returns:
        AIAnalysisResponse: AI 분석 결과 (analysis, questions, primary_type, secondary_type)
    """
    
    # --- 1. data_processor 호출 (객관적 데이터 확보) ---
    objective_data = {}
    try:
        async with httpx.AsyncClient(timeout=settings.DATA_PROCESSOR_TIMEOUT) as client:
            params = {"ticker": request.ticker, "market_index": "^KS11"}
            response = await client.get(DATA_PROCESSOR_URL, params=params)
            response.raise_for_status()
            objective_data = response.json()
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"시장 데이터 서버(data_processor)에 연결할 수 없습니다: {e}"
        )
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="시장 데이터 서버(data_processor) 응답 시간이 초과되었습니다."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"데이터 처리 중 오류가 발생했습니다: {str(e)}"
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
    from app.services.gpt_service import get_ai_feedback
    ai_response = get_ai_feedback(ai_input_data)
    
    if ai_response.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 분석 실패: {ai_response['error']}"
        )

    # --- 4. Trade 레코드 생성 또는 조회 ---
    # trade_info에서 손익률 추출
    profit_loss_rate = extract_profit_loss_rate(request.trade_info)
    
    # 새로운 Trade 생성
    new_trade = Trade(
        user_id=current_user.id,
        ticker=request.ticker,
        profit_loss_rate=profit_loss_rate
    )
    db.add(new_trade)
    db.flush()  # trade_id를 얻기 위해 flush (아직 commit은 안 함)

    # --- 5. ReviewNote 레코드 생성 및 저장 ---
    try:
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
        db.commit()
        db.refresh(new_note)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"분석 결과를 저장하는 데 실패했습니다: {str(e)}"
        )

    # --- 6. AI 응답 반환 ---
    return AIAnalysisResponse(
        analysis=ai_response.get("analysis", ""),
        questions=ai_response.get("questions", ""),
        primary_type=ai_response.get("primary_type", ""),
        secondary_type=ai_response.get("secondary_type")
    )


@router.get("/{review_id}", response_model=ReviewNoteResponse)
def get_review(
    review_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    특정 복기 노트 조회
    본인의 복기 노트만 조회 가능합니다.
    """
    review = db.query(ReviewNote).filter(
        ReviewNote.id == review_id,
        ReviewNote.user_id == current_user.id
    ).first()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="복기 노트를 찾을 수 없습니다."
        )
    
    return review


@router.get("", response_model=list[ReviewNoteResponse])
def list_reviews(
    skip: int = 0,
    limit: int = 20,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    현재 사용자의 복기 노트 목록 조회
    """
    reviews = db.query(ReviewNote).filter(
        ReviewNote.user_id == current_user.id
    ).offset(skip).limit(limit).all()
    
    return reviews
