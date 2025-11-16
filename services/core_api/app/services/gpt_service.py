# 파일 경로: services/core_api/app/services/gpt_service.py

import openai
from openai import AsyncOpenAI
import os
import json
import asyncio
from typing import Dict, Optional
from ..core.config import get_settings
from ..core.logging_config import get_logger

# 로거 설정
logger = get_logger(__name__)

# 설정 가져오기
settings = get_settings()

# --- 1. AI의 역할 및 응답 형식 정의 (System) ---

SYSTEM_PROMPT = """
당신은 투자자의 심리와 행동을 분석하여 성장을 돕는 전문 '투자 행동 코치'입니다.

당신의 임무는 [입력 데이터]를 바탕으로 3단계에 걸쳐 피드백을 제공하는 것입니다.
당신의 응답은 반드시 아래 [응답 JSON 형식]을 따라야 하며, 그 외의 설명이나 대답은 절대 추가하지 마세요.

[응답 JSON 형식]
{
  "analysis": " (Part 1 내용을 여기에 작성) ",
  "questions": " (Part 2 내용을 여기에 작성) ",
  "primary_type": " (Part 3의 '주요 원인' 1개) ",
  "secondary_type": " (Part 3의 '보조 원인' 1개 또는 null) "
}
"""

# --- 2. 9개 카테고리 분류 가이드 (AI의 의사결정 로직) ---

CLASSIFICATION_GUIDE = """
**[분류 가이드라인 (Part 3)]**
AI는 아래의 우선순위와 기준을 '반드시' 따라서 9개 키워드 중 1개를 선택합니다.

1.  **'주요 원인' (primary_type) 선택 (필수):**
    * 거래 실패에 가장 치명적이고 직접적인 '행동' 또는 '심리' 1개를 선택합니다.
    * **(최우선 1) `무리한_레버리지`**: '신용', '미수', '반대매매', '마통', '빚투' 등 '빚'이 언급되면, 다른 원인이 결합되었더라도 이것이 '주요 원인'입니다.
    * ** (최우선 2) `포트폴리오_실패`**: '몰빵', '전 재산', '한 섹터 편중' 등 '자산 배분'의 문제가 언급되면 이것이 '주요 원인'입니다.
    * ** (기타 진입/청산 원인)**:
        * `FOMO_추격매수`: '나만 못 벌까 봐', '조바심', '수익 인증', '과매수(RSI 80+)' 상태에서의 매수.
        * `외부정보_의존`: '유튜버', '리딩방', '지인', '뉴스'를 맹신하여 매수.
        * `근거없는_확신`: '그냥 감이', '이유 없음', '차트 모양만 보고' 매수.
        * `Panic_Sell_공포투매`: '시장 급락', '공포', '패닉'으로 '과매도(RSI 20-)' 상태에서 매도.
        * `과도한_욕심`: '수익권(+%)'이었으나 '더 먹으려는 욕심'에 익절을 못하고 손실로 전환.
        * `손실회피_물타기`: '손절 못함', '본전 생각', '기도 매매', '분석 없는 물타기'.
        * `기타`: 위 8가지에 속하지 않는 명확한 실패 (예: 배당주 함정).

2.  **'보조 원인' (secondary_type) 선택 (선택적):**
    * 만약 '주요 원인' 외에 명백하게 결합된 '보조 원인'이 있다면 1개 선택합니다.
    * (예: '무리한_레버리지'(Primary)를 사용해 '물타기'(Secondary)를 한 경우)
    * 명확한 보조 원인이 없다면, `null`을 반환합니다.
"""

# --- 3. OpenAI API 호출 함수 (비동기 버전) ---

async def get_ai_feedback(input_data: dict) -> dict:
    """
    입력 데이터를 받아 OpenAI API를 비동기로 호출하고,
    분석, 질문, 분류가 포함된 JSON 응답을 반환합니다.
    
    재시도 로직 및 타임아웃 포함.
    
    Args:
        input_data: AI 분석에 필요한 입력 데이터 딕셔너리
    
    Returns:
        dict: AI 분석 결과 또는 에러 메시지가 포함된 딕셔너리
    """
    
    # OpenAI 클라이언트 초기화
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY가 설정되지 않았습니다")
        return {"error": "API 키가 설정되지 않았습니다."}
    
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    # 1. 입력 데이터를 JSON 문자열로 변환
    try:
        input_data_json = json.dumps(input_data, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("입력 데이터 JSON 변환 실패", error=str(e))
        return {"error": f"입력 데이터 JSON 변환 실패: {e}"}

    # 2. AI에게 전달할 최종 User 프롬프트 구성
    USER_PROMPT = f"""
[입력 데이터]
{input_data_json}

[지시 사항]
위 [입력 데이터]를 바탕으로, 아래 3단계 지시 사항을 수행하여 [응답 JSON 형식]을 완성하세요.

**Part 1: 객관적인 분석 (analysis)**
* '주관적 데이터'(감정, 메모)와 '객관적 데이터'(시장, 뉴스, 차트)를 연결하여 투자 편향을 진단합니다.
* 이 결정이 합리적이었는지, 충동적이었는지 평가합니다.

**Part 2: 자기 성찰을 위한 질문 (questions)**
* 위 분석을 바탕으로, 사용자가 스스로 깨달을 수 있도록 날카로운 질문을 2-3개 제공합니다.
* 주의: 절대 직접적인 조언이나 정답을 제시하지 말고, 오직 질문만 합니다.

**Part 3: 실패 유형 분류 (primary_type, secondary_type)**
* 위에 제시된 [분류 가이드라인]을 '반드시' 준수하여 '주요 원인'과 '보조 원인'을 추출합니다.
{CLASSIFICATION_GUIDE}
"""

    # 3. 재시도 로직을 포함한 OpenAI API 호출
    max_retries = settings.MAX_RETRIES
    retry_delay = settings.RETRY_DELAY
    timeout = 30  # 30초 타임아웃
    
    for attempt in range(max_retries):
        try:
            logger.info(
                "OpenAI API 호출 시도",
                attempt=attempt + 1,
                max_retries=max_retries
            )
            
            completion = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": USER_PROMPT}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2
                ),
                timeout=timeout
            )
            
            response_content = completion.choices[0].message.content
            
            # 4. AI의 JSON 응답을 파싱하여 딕셔너리로 반환
            result = json.loads(response_content)
            logger.info("OpenAI API 호출 성공", attempt=attempt + 1)
            return result

        except asyncio.TimeoutError:
            logger.warning(
                "OpenAI API 호출 타임아웃",
                attempt=attempt + 1,
                timeout=timeout
            )
            if attempt == max_retries - 1:
                return {"error": f"AI 응답 시간이 {timeout}초를 초과했습니다."}
            await asyncio.sleep(retry_delay * (attempt + 1))  # 지수 백오프
            
        except openai.BadRequestError as e:
            error_msg = str(e) if hasattr(e, '__str__') else "API 요청 오류"
            logger.error(
                "OpenAI API BadRequest 오류",
                error=error_msg,
                attempt=attempt + 1
            )
            return {"error": f"API 요청 오류: {error_msg}"}
            
        except openai.RateLimitError as e:
            logger.warning(
                "OpenAI API RateLimit 오류",
                attempt=attempt + 1,
                retry_after=retry_delay * (attempt + 1)
            )
            if attempt == max_retries - 1:
                return {"error": "API 요청 한도 초과. 잠시 후 다시 시도해주세요."}
            await asyncio.sleep(retry_delay * (attempt + 1))
            
        except Exception as e:
            logger.error(
                "OpenAI API 호출 중 예외 발생",
                error=str(e),
                error_type=type(e).__name__,
                attempt=attempt + 1
            )
            if attempt == max_retries - 1:
                return {"error": f"AI 응답 처리 중 오류가 발생했습니다: {str(e)}"}
            await asyncio.sleep(retry_delay * (attempt + 1))
    
    return {"error": "AI 분석을 완료할 수 없습니다. 재시도 횟수를 초과했습니다."}


# --- 4. B님을 위한 로컬 테스트 구문 ---
# (이 파일을 직접 실행하여 프롬프트를 테스트할 수 있습니다.)
# (PowerShell/터미널에서: python services/core_api/app/services/gpt_service.py)

if __name__ == "__main__":
    
    print("--- [gpt_service.py] 로컬 테스트 시작 ---")
    
    # B님의 API 키를 여기에 임시로 설정하거나, 환경 변수에 등록해야 합니다.
    # os.environ["OPENAI_API_KEY"] = "sk-..." 
    
    if not os.environ.get("OPENAI_API_KEY"):
        print("경고: OPENAI_API_KEY 환경 변수가 없습니다. 테스트를 건너뜁니다.")
        print("테스트를 실행하려면 파일 상단에 키를 설정하거나 환경 변수에 등록하세요.")
    else:
        # 우리가 만든 20개 테스트셋 중 가장 복잡한 [4번 사례]
        test_input = {
          "trade_info": "카카오 (-55.0%)",
          "subjective_data": {
            "emotion_tags": ["절망", "오기", "공포"],
            "memo": "분명히 반등할 줄 알고 마이너스 통장(마통)까지 뚫어서 물타기 했는데... 어제 증권사에서 전화 왔고, 오늘 아침 9시 동시호가에 반대매매로 다 날아갔습니다."
          },
          "objective_data_at_sell": {
            "chart_indicators": "Price is BELOW 200-day MA, RSI is Oversold (18.5)",
            "related_news": ["신용 융자 잔고 '빨간불'", "증권가, 목표 주가 일제히 하향"],
            "market_indicators": "KOSPI FALLING (-1.8%)"
          }
        }
        
        print(f"\n[테스트 입력 데이터]\n{json.dumps(test_input, indent=2, ensure_ascii=False)}")
        
        # AI 피드백 함수 호출
        ai_response = get_ai_feedback(test_input)
        
        print("\n[AI 응답 (JSON)]")
        print(json.dumps(ai_response, indent=2, ensure_ascii=False))

        # 분류 정확도 확인 (예상: '무리한_레버리지' / '손실회피_물타기')
        print("\n[분류 결과]")
        print(f"Primary: {ai_response.get('primary_type')}")
        print(f"Secondary: {ai_response.get('secondary_type')}")