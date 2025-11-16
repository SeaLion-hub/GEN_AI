"""
인증 API 엔드포인트
사용자 등록, 로그인, JWT 토큰 발급 및 검증
(비동기 CPU 블로킹 문제 해결 버전)
"""

import os
import asyncio  # 1. 비동기 스레딩을 위해 asyncio 임포트
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.db.session import get_db
from app.db.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.schemas import UserCreate, Token, UserResponse
from app.core.config import get_settings
from app.core.logging_config import get_logger

# 로거 설정
logger = get_logger(__name__)

# 설정 가져오기
settings = get_settings()

# OAuth2 스키마 정의
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

# 비밀번호 해싱 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


# ==================== 인증 유틸리티 함수 ====================

def get_password_hash(password: str) -> str:
    """비밀번호를 해시화 (CPU 집약적 동기 함수)"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증 (CPU 집약적 동기 함수)"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """JWT 액세스 토큰 생성 (빠른 동기 함수)"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """
    JWT 토큰에서 현재 사용자 정보를 추출하는 비동기 의존성 함수
    다른 API 엔드포인트에서 인증이 필요한 경우 사용합니다.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보를 확인할 수 없습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 사용자입니다.",
        )
    
    return user

# ==================== 엔드포인트 구현 ====================

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    사용자 등록 엔드포인트
    새로운 사용자를 생성하고 JWT 토큰을 반환합니다.
    """
    # 1. 사용자 존재 여부 확인
    result = await db.execute(select(User).where(User.username == user_data.username))
    db_user = result.scalar_one_or_none()
    if db_user:
        logger.warning("사용자 등록 실패: 이미 존재하는 사용자", username=user_data.username)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 존재하는 사용자 이름(ID)입니다."
        )
    
    # --- [핵심 수정 1] ---
    # 2. 비밀번호 해싱 (CPU 작업을 별도 스레드에서 실행)
    try:
        hashed_password = await asyncio.to_thread(get_password_hash, user_data.password)
    except Exception as e:
        logger.error("비밀번호 해싱 실패", error=str(e))
        raise HTTPException(status_code=500, detail="비밀번호 처리 중 오류가 발생했습니다.")
    # --- [수정 완료] ---

    new_user = User(
        username=user_data.username,
        hashed_password=hashed_password,
        is_active=True
    )
    
    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info("신규 사용자 등록 성공", username=new_user.username, user_id=new_user.id)
    except Exception as e:
        await db.rollback()
        logger.error("사용자 등록 DB 저장 실패", error=str(e), username=user_data.username)
        raise HTTPException(status_code=500, detail="사용자 등록 중 오류가 발생했습니다.")
    
    # 3. JWT 토큰 생성 및 반환
    access_token = create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    로그인 엔드포인트
    사용자 인증 후 JWT 토큰을 반환합니다.
    """
    # 1. 사용자 존재 여부 확인
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자 이름 또는 비밀번호가 잘못되었습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. 사용자 활성 상태 확인
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 사용자입니다.",
        )
    
    # --- [핵심 수정 2] ---
    # 3. 비밀번호 검증 (CPU 작업을 별도 스레드에서 실행)
    try:
        is_password_valid = await asyncio.to_thread(
            verify_password, form_data.password, user.hashed_password
        )
    except Exception as e:
        logger.error("비밀번호 검증 실패", error=str(e), username=form_data.username)
        raise HTTPException(status_code=500, detail="로그인 처리 중 오류가 발생했습니다.")

    if not is_password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자 이름 또는 비밀번호가 잘못되었습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # --- [수정 완료] ---
    
    # 4. JWT 토큰 생성 및 반환
    access_token = create_access_token(data={"sub": user.username})
    logger.info("사용자 로그인 성공", username=user.username, user_id=user.id)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    현재 로그인한 사용자 정보 조회
    """
    return current_user


