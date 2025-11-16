# 파일 경로: services/core_api/test_prompt.py
# (AI 프롬프트 정확도를 테스트하기 위한 일회용 스크립트)

import os
import json
import time
from dotenv import load_dotenv
import asyncio  # 1. asyncio 임포트

# .env 파일에서 OPENAI_API_KEY 로드
load_dotenv() 

# B님이 만든 gpt_service.py에서 AI 함수 임포트
from app.services.gpt_service import get_ai_feedback

# --- B님이 만든 20개 테스트 데이터셋 ---
TEST_DATASET = [
    # (유형 1: FOMO / 추격 매수)
    {"trade_info": "엔비디아 (NVDA) (-25.0%)", "subjective_data": {"emotion_tags": ["조바심(FOMO)", "질투", "탐욕"], "memo": "나 빼고 다 AI 주식으로 돈 버는 것 같아서..."}, "objective_data_at_buy": {"chart_indicators": "RSI is Overbought (82.0)...", "related_news": ["개인 투자자 '빚투' 열풍..."], "market_indicators": "NASDAQ RISING (+1.5%)"}, "ground_truth_primary": "FOMO_추격매수", "ground_truth_secondary": None},
    {"trade_info": "삼성전자 (005930.KS) (+1.2%)", "subjective_data": {"emotion_tags": ["후회", "조바심(FOMO)"], "memo": "분명히 8만 전자에 팔았는데, 3일 연속 오르는 걸 보니..."}, "objective_data_at_buy": {"chart_indicators": "RSI is Overbought (75.0)...", "related_news": ["'10만 전자 간다' 증권가 리포트 쇄도"], "market_indicators": "KOSPI RISING (+1.0%)"}, "ground_truth_primary": "FOMO_추격매수", "ground_truth_secondary": None},
    # (유형 2: Panic Sell / 공포 투매)
    {"trade_info": "애플 (AAPL) (-5.0%)", "subjective_data": {"emotion_tags": ["공포", "불안", "패닉"], "memo": "어제 미국 증시 폭락했다는 뉴스 보고 너무 무서워서..."}, "objective_data_at_sell": {"chart_indicators": "RSI is Oversold (28.0)...", "related_news": ["글로벌 경기 침체 공포 확산..."], "market_indicators": "S&P 500 FALLING (-2.8%)"}, "ground_truth_primary": "Panic_Sell_공포투매", "ground_truth_secondary": None},
    {"trade_info": "신풍제약 (019170.KS) (-15.0%)", "subjective_data": {"emotion_tags": ["공포", "후회"], "memo": "갑자기 -10% 급락하길래 커뮤니티를 봤더니 '다 망했다, 도망쳐라'..."}, "objective_data_at_sell": {"chart_indicators": "Sudden sharp decline...", "related_news": ["특별한 악재 공시 없음"], "market_indicators": "KOSDAQ Neutral"}, "ground_truth_primary": "Panic_Sell_공포투매", "ground_truth_secondary": None},
    # (유형 3: 무리한 레버리지 / 반대매매)
    {"trade_info": "삼천리 (004690.KS) (-100.0%)", "subjective_data": {"emotion_tags": ["절망", "오기", "공포"], "memo": "SG 사태 터진 종목입니다. 신용융자 써서 풀매수했는데..."}, "objective_data_at_sell": {"chart_indicators": "Continuous decline...", "related_news": ["SG 사태 이후 신용 잔고 '빨간불'..."], "market_indicators": "KOSPI FALLING (-2.1%)"}, "ground_truth_primary": "무리한_레버리지", "ground_truth_secondary": None},
    {"trade_info": "테슬라 (TSLA) (-40.0%)", "subjective_data": {"emotion_tags": ["불안", "초조"], "memo": "실수로 매도한다는 걸 미수 매수로 잘못 눌렀어요..."}, "objective_data_at_sell": {"chart_indicators": "Price declining", "related_news": ["미수거래 위험성 경고"], "market_indicators": "NASDAQ Neutral"}, "ground_truth_primary": "무리한_레버리지", "ground_truth_secondary": None},
    # (유형 4: 외부 정보 의존)
    {"trade_info": "신라젠 (215600.KQ) (-70.0%)", "subjective_data": {"emotion_tags": ["기대", "맹신", "배신감"], "memo": "구독자 50만인 주식 유튜버가 이 종목..."}, "objective_data_at_buy": {"chart_indicators": "High volatility...", "related_news": ["임상 3상 결과 발표 임박..."], "market_indicators": "KOSDAQ RISING"}, "ground_truth_primary": "외부정보_의존", "ground_truth_secondary": None},
    {"trade_info": "알 수 없는 코인 (-90.0%)", "subjective_data": {"emotion_tags": ["희망", "탐욕"], "memo": "텔레그램 리딩방에서 '원금 10배 보장'이라고 해서..."}, "objective_data_at_buy": {"chart_indicators": "N/A (Unlisted coin)", "related_news": ["유사투자자문업체 사기 급증..."], "market_indicators": "N/A"}, "ground_truth_primary": "외부정보_의존", "ground_truth_secondary": None},
    # (유형 5: 손실 회피 / 물타기)
    {"trade_info": "SOLT ETF (-45.0%)", "subjective_data": {"emotion_tags": ["오기", "불안", "자기합리화"], "memo": "물타기 대실패입니다. 떨어질 때마다 '지금이 싸다'고..."}, "objective_data_at_sell": {"chart_indicators": "Continuous decline...", "related_news": ["SOLT 커뮤니티, '시즌 종료다'..."], "market_indicators": "N/A"}, "ground_truth_primary": "손실회피_물타기", "ground_truth_secondary": None},
    {"trade_info": "카카오 (035720.KS) (-55.0%)", "subjective_data": {"emotion_tags": ["절망", "오기", "공포"], "memo": "분명히 반등할 줄 알고 마이너스 통장(마통)까지 뚫어서 물타기 했는데... 어제 증권사에서 전화 왔고, 오늘 아침 9시 동시호가에 반대매매로 다 날아갔습니다."}, "objective_data_at_sell": {"chart_indicators": "Price is BELOW 200-day MA, RSI is Oversold (18.5)", "related_news": ["신용 융자 잔고 '빨간불'...", "증권가, 목표 주가 일제히 하향"], "market_indicators": "KOSPI FALLING (-1.8%)"}, "ground_truth_primary": "무리한_레버리지", "ground_truth_secondary": "손실회피_물타기"},
    # (유형 6: 근거 없는 확신)
    {"trade_info": "게임스탑 (GME) (-75.0%)", "subjective_data": {"emotion_tags": ["도박", "근자감", "오기"], "memo": "이유는 없었어요. 그냥 이번엔 내가 사면 오를 것 같다는 '감'이 왔습니다..."}, "objective_data_at_buy": {"chart_indicators": "Extremely high volatility...", "related_news": ["'밈 주식' 열풍 재점화..."], "market_indicators": "S&P 500 Neutral"}, "ground_truth_primary": "근거없는_확신", "ground_truth_secondary": None},
    {"trade_info": "포드 (F) (-20.0%)", "subjective_data": {"emotion_tags": ["단순함", "무지"], "memo": "차트가 예뻐서 샀어요. W자 반등을 그리는 것 같길래..."}, "objective_data_at_buy": {"chart_indicators": "No clear signal...", "related_news": ["포드, 전기차 투자 계획 발표"], "market_indicators": "S&P 500 Neutral"}, "ground_truth_primary": "근거없는_확신", "ground_truth_secondary": None},
    {"trade_info": "팔란티어 (PLTR) (-30.0%)", "subjective_data": {"emotion_tags": ["기대감"], "memo": "이유는 없어요. 그냥 CEO가 마음에 들고 이름이 멋져서..."}, "objective_data_at_buy": {"chart_indicators": "Neutral", "related_news": ["팔란티어, 정부 수주 계약 체결"], "market_indicators": "NASDAQ Neutral"}, "ground_truth_primary": "근거없는_확신", "ground_truth_secondary": None},
    # (유형 7: 과도한 욕심)
    {"trade_info": "AMD (-10.0%)", "subjective_data": {"emotion_tags": ["탐욕", "후회", "욕심"], "memo": "분명 +25% 수익권이었습니다. 근데 '더블' 먹을 수 있다는 욕심에..."}, "objective_data_at_sell": {"chart_indicators": "Price declined after hitting 52-week high...", "related_news": ["차익 실현 매물 출회..."], "market_indicators": "NASDAQ FALLING"}, "ground_truth_primary": "과도한_욕심", "ground_truth_secondary": None},
    {"trade_info": "한화에어로스페이스 (012450.KS) (-5.0%)", "subjective_data": {"emotion_tags": ["탐욕", "아쉬움"], "memo": "장중에 +20%까지 급등하길래 상한가 갈 줄 알고 버텼습니다..."}, "objective_data_at_sell": {"chart_indicators": "Long upper shadow (윗꼬리) candle...", "related_news": ["방산 수주 기대감에 장중 급등"], "market_indicators": "KOSPI Neutral"}, "ground_truth_primary": "과도한_욕심", "ground_truth_secondary": None},
    {"trade_info": "코인베이스 (COIN) (-22.0%)", "subjective_data": {"emotion_tags": ["희망고문", "후회"], "memo": "비트코인 따라서 +50%까지 갔었는데, '전고점 뚫는다'는 욕심에 안 팔았어요..."}, "objective_data_at_sell": {"chart_indicators": "Price declined sharply after peak...", "related_news": ["비트코인 가격, 차익 실현 매물에 하락"], "market_indicators": "N/A (Crypto-related stock)"}, "ground_truth_primary": "과도한_욕심", "ground_truth_secondary": None},
    # (유형 8: 포트폴리오 관리 실패)
    {"trade_info": "보잉 (BA) (-50.0%)", "subjective_data": {"emotion_tags": ["절망", "무모함"], "memo": "전 재산을 보잉 한 종목에 '몰빵'했습니다..."}, "objective_data_at_sell": {"chart_indicators": "Sharp decline...", "related_news": ["보잉 737 기종, 운항 전면 중단 위기..."], "market_indicators": "S&P 500 Neutral"}, "ground_truth_primary": "포트폴리오_실패", "ground_truth_secondary": None},
    {"trade_info": "JP모건 (JPM) (-20.0%)", "subjective_data": {"emotion_tags": ["불안", "편향"], "memo": "제 포트폴리오는 90%가 은행주였습니다..."}, "objective_data_at_sell": {"chart_indicators": "Sector-wide decline...", "related_news": ["지역 은행 위기, 금융 시스템 전반으로 확산되나"], "market_indicators": "S&P 500 FALLING (-1.5%)"}, "ground_truth_primary": "포트폴리오_실패", "ground_truth_secondary": None},
    {"trade_info": "테슬라 (TSLA) (-25.0%)", "subjective_data": {"emotion_tags": ["편향", "스트레스"], "memo": "포트폴리오에 주식이 10개인데, 전부 다 나스닥 기술주였습니다..."}, "objective_data_at_sell": {"chart_indicators": "Sector-wide decline (Tech)...", "related_news": ["연준, 금리 인상 가속화 시사..."], "market_indicators": "NASDAQ FALLING (-2.0%)"}, "ground_truth_primary": "포트폴리오_실패", "ground_truth_secondary": None},
    # (유형 9: 기타)
    {"trade_info": "AT&T (T) (-15.0%)", "subjective_data": {"emotion_tags": ["실망", "무지"], "memo": "오로지 '고배당' 하나만 보고 샀습니다... 배당 삭감(컷)하네요..."}, "objective_data_at_sell": {"chart_indicators": "Long-term decline", "related_news": ["AT&T, 부채 감축 위해 배당 삭감 발표..."], "market_indicators": "S&P 500 Neutral"}, "ground_truth_primary": "기타", "ground_truth_secondary": None}
]


# 2. 함수를 'async def'로 변경
async def run_prompt_test():
    """
    20개 데이터셋으로 AI 프롬프트의 'Primary/Secondary' 분류 정확도를 테스트합니다.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        print("🛑 Error: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("services/core_api/.env 파일을 확인하거나 환경 변수를 직접 설정해주세요.")
        return

    print("--- [AI 프롬프트 분류 정확도 테스트 (Primary/Secondary)] ---")
    
    primary_correct_count = 0
    secondary_correct_count = 0
    total_count = len(TEST_DATASET)
    
    for i, test_case in enumerate(TEST_DATASET):
        print(f"\n[Test Case {i+1}/{total_count}] - '{test_case['trade_info']}'")
        
        expected_primary = test_case.pop("ground_truth_primary")
        expected_secondary = test_case.pop("ground_truth_secondary", None)
        
        # API 호출 속도 제어 (API Rate Limit 방지)
        # (비동기 환경에서는 time.sleep 대신 asyncio.sleep 사용)
        await asyncio.sleep(20) 
        
        # 3. 'await' 키워드 추가
        ai_response = await get_ai_feedback(test_case)
        
        if ai_response.get("error"):
            print(f"    ❌ FAILED (API Error): {ai_response['error']}")
            continue
            
        # --- Primary Type 검증 ---
        actual_primary = ai_response.get("primary_type")
        is_primary_correct = (actual_primary == expected_primary)
        if is_primary_correct:
            primary_correct_count += 1
            print(f"    ✅ Primary: '{actual_primary}' (일치)")
        else:
            print(f"    ❌ FAILED (Primary): AI '{actual_primary}' (예상: '{expected_primary}')")

        # --- Secondary Type 검증 ---
        actual_secondary = ai_response.get("secondary_type", None)
        if isinstance(actual_secondary, str) and actual_secondary.lower() in ["null", "none", ""]:
            actual_secondary = None
            
        is_secondary_correct = (actual_secondary == expected_secondary)
        if is_secondary_correct:
            secondary_correct_count += 1
            print(f"    ✅ Secondary: '{actual_secondary}' (일치)")
        else:
            print(f"    ❌ FAILED (Secondary): AI '{actual_secondary}' (예상: '{expected_secondary}')")

    print("\n--- [테스트 결과 요약] ---")
    primary_accuracy = (primary_correct_count / total_count) * 100
    secondary_accuracy = (secondary_correct_count / total_count) * 100
    
    print(f"✅ Primary Type 정확도: {primary_accuracy:.1f}% ({primary_correct_count}/{total_count}개 성공)")
    print(f"✅ Secondary Type 정확도: {secondary_accuracy:.1f}% ({secondary_correct_count}/{total_count}개 성공)")

    if primary_accuracy < 90.0:
        print("\n[B님 Action Item]")
        print("❗️Primary Type 정확도가 90% 미만입니다.")
        print("  AI가 헷갈려하는 케이스(예: FOMO vs 근거없는 확신)를 분석하여 `gpt_service.py`의 `CLASSIFICATION_GUIDE` (분류 가이드라인)을 튜닝하세요.")

# --- 스크립트 실행 ---
if __name__ == "__main__":
    # 4. 'asyncio.run()'으로 비동기 함수 실행
    asyncio.run(run_prompt_test())