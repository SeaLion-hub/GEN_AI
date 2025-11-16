"""
로깅 설정 모듈
구조화된 로깅을 위한 설정
"""

import logging
import sys
import structlog
from typing import Any

def setup_logging() -> None:
    """
    애플리케이션 로깅 설정
    structlog를 사용한 구조화된 로깅
    """
    # 표준 라이브러리 logging 설정
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    
    # structlog 설정
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    로거 인스턴스 반환
    
    Args:
        name: 로거 이름 (보통 __name__ 사용)
    
    Returns:
        structlog.BoundLogger 인스턴스
    """
    return structlog.get_logger(name)

