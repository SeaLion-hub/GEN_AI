# 파일 경로: services/data_processor/app/yfinance_processor.py

import yfinance as yf
import pandas as pd
import json
from datetime import datetime

def _get_technical_summary(hist_data: pd.DataFrame) -> dict:
    """
    (Helper) 1년치 이력 데이터(DataFrame)를 받아 
    현재 기술적 지표를 계산하고 요약합니다.
    """
    try:
        # 가장 최신 데이터
        latest_data = hist_data.iloc[-1]
        
        # 1. 이동평균 (MA)
        ma50 = hist_data['Close'].rolling(window=50).mean().iloc[-1]
        ma200 = hist_data['Close'].rolling(window=200).mean().iloc[-1]
        
        # 2. 상대강도지수 (RSI, 14일)
        delta = hist_data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        # ZeroDivisionError 방지
        if loss.iloc[-1] == 0:
            rsi_value = 100
        else:
            rs = gain.iloc[-1] / loss.iloc[-1]
            rsi_value = 100 - (100 / (1 + rs))

        # 3. LLM이 이해하기 쉬운 요약 생성
        summary = {
            "current_price": f"{latest_data['Close']:.2f}",
            "ma_50": f"{ma50:.2f}",
            "ma_200": f"{ma200:.2f}",
            "volume": f"{latest_data['Volume']:,}",
            "rsi_14": f"{rsi_value:.2f}",
            # 텍스트 요약
            "price_vs_ma50_status": "Price is ABOVE 50-day MA" if latest_data['Close'] > ma50 else "Price is BELOW 50-day MA",
            "ma_trend_status": "Golden Cross (MA50 > MA200)" if ma50 > ma200 else "Dead Cross (MA50 < MA200)",
            "rsi_status": "Overbought (RSI > 70)" if rsi_value > 70 else ("Oversold (RSI < 30)" if rsi_value < 30 else "Neutral (30 < RSI < 70)")
        }
        return summary
    
    except Exception as e:
        # 데이터가 200일 미만일 경우(신규 상장 주식 등) MA200 계산에서 오류 발생 가능
        return {"error": f"Technical data processing failed. (Maybe not enough history data): {str(e)}"}

def get_current_market_context(ticker_symbol: str, market_index: str = '^GSPC') -> dict:
    """
    함수 호출 시점을 기준으로 특정 주식의 객관적 데이터를 가져옵니다.
    (차트 지표, 재무 지표, 관련 뉴스, 시장 지표)
    
    Args:
        ticker_symbol (str): 'TSLA', '005930.KS' 등
        market_index (str): '^GSPC' (S&P 500), '^KS11' (KOSPI) 등

    Returns:
        dict: LLM이 분석하기 좋은 형태로 가공된 시장 컨텍스트
    """
    
    ticker = yf.Ticker(ticker_symbol)
    index_ticker = yf.Ticker(market_index)
    
    context = {
        "ticker": ticker_symbol,
        "market_index": market_index,
        "fetch_timestamp_kst": datetime.now().isoformat()
    }

    # --- 1. 차트 지표 (Technical Indicators) ---
    try:
        # 기술적 지표 계산을 위해 1년치 데이터 사용
        hist_data = ticker.history(period="1y")
        if not hist_data.empty:
            context['chart_indicators'] = _get_technical_summary(hist_data)
        else:
            context['chart_indicators'] = {"error": "No history data found."}
    except Exception as e:
        context['chart_indicators'] = {"error": f"Failed to get history: {str(e)}"}

    # --- 2. 재무 지표 (Financial Indicators) ---
    try:
        info = ticker.info
        q_financials = ticker.quarterly_financials
        
        financials = {
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "market_cap": info.get('marketCap'),
            "pe_ratio_ttm": info.get('trailingPE'),
            "eps_ttm": info.get('trailingEps'),
            "dividend_yield": info.get('dividendYield'),
            "52_week_high": info.get('fiftyTwoWeekHigh'),
            "52_week_low": info.get('fiftyTwoWeekLow'),
        }
        
        # 가장 최근 분기 실적 (첫 번째 컬럼)
        if not q_financials.empty:
            latest_quarter = q_financials.iloc[:, 0]
            financials['latest_quarter_report'] = {
                "report_date": latest_quarter.name.strftime('%Y-%m-%d'),
                "total_revenue": latest_quarter.get('Total Revenue'),
                "net_income": latest_quarter.get('Net Income'),
            }
        
        context['financial_indicators'] = financials
    except Exception as e:
        # .info 가 비어있거나 특정 키가 없는 경우
        context['financial_indicators'] = {"error": f"Failed to get financial info: {str(e)}"}

    # --- 3. 관련 뉴스 (News) ---
    try:
        news = ticker.news
        if news:
            context['related_news'] = [
                {
                    "title": item.get('title'),
                    "publisher": item.get('publisher'),
                    "link": item.get('link'),
                    "publish_time": datetime.fromtimestamp(item.get('providerPublishTime')).isoformat()
                } for item in news[:8] # 최대 8개
            ]
        else:
            context['related_news'] = []
    except Exception as e:
        context['related_news'] = {"error": f"Failed to get news: {str(e)}"}

    # --- 4. 시장 지표 (Market Indicators) ---
    try:
        # 5일치 데이터로 최근 추세 파악
        index_hist = index_ticker.history(period="5d")
        if not index_hist.empty:
            latest_index = index_hist.iloc[-1]
            prev_index = index_hist.iloc[-2]
            
            change = latest_index['Close'] - prev_index['Close']
            change_percent = (change / prev_index['Close']) * 100
            
            context['market_indicators'] = {
                "index_name": info.get('shortName', market_index),
                "current_price": f"{latest_index['Close']:.2f}",
                "change": f"{change:+.2f}",
                "change_percent": f"{change_percent:+.2f}%",
                "status": "RISING" if change > 0 else "FALLING"
            }
        else:
            context['market_indicators'] = {"error": "Market index data not found."}
    except Exception as e:
        context['market_indicators'] = {"error": f"Failed to get market index: {str(e)}"}

    return context

# --- [신규 추가] 차트용 이력 데이터 함수 ---

def get_chart_data(ticker_symbol: str, period: str = "1y") -> dict:
    """
    프론트엔드 차트(Recharts)에 사용할 이력 데이터를 가져옵니다.
    
    Args:
        ticker_symbol (str): 'TSLA', '005930.KS' 등
        period (str): '1d', '5d', '1mo', '6mo', '1y', 'ytd', 'max'

    Returns:
        dict: 차트 데이터 리스트 또는 오류 메시지
    """
    
    ticker = yf.Ticker(ticker_symbol)
    
    # 기간(period)에 따라 데이터 간격(interval)을 자동으로 조절합니다.
    # (예: 1일은 30분, 1년은 1일)
    interval_map = {
        '1d': '30m',
        '5d': '30m',
        '1mo': '1d',
        '6mo': '1d',
        '1y': '1d',
        'ytd': '1d',
        'max': '1wk'
    }
    
    # period가 맵에 없으면 '1d' 간격을 기본으로 사용
    interval = interval_map.get(period, '1d')

    try:
        hist = ticker.history(period=period, interval=interval)
        
        if hist.empty:
            return {"error": f"No history data found for {ticker_symbol} with period {period}"}
        
        # DataFrame의 Index (날짜/시간)를 리셋하여 'Datetime' 또는 'Date' 컬럼으로 만듭니다.
        hist = hist.reset_index()
        
        # 'Datetime' 또는 'Date' 컬럼명을 'date'로 표준화합니다.
        # ( intraday는 'Datetime', daily는 'Date'로 컬럼명이 다를 수 있음 )
        timestamp_col_name = None
        if 'Datetime' in hist.columns:
            timestamp_col_name = 'Datetime'
        elif 'Date' in hist.columns:
            timestamp_col_name = 'Date'
        else:
            return {"error": "Could not find timestamp column in history data."}

        # 프론트엔드가 사용하기 좋은 포맷: [{"date": "...", "price": ...}]
        chart_data = hist[[timestamp_col_name, 'Close']]
        chart_data.columns = ['date', 'price'] # 컬럼명 변경
        
        # 'date' 컬럼을 ISO 포맷 문자열로 변환 (JSON 호환성)
        chart_data['date'] = chart_data['date'].apply(lambda x: x.isoformat())
        
        # .to_dict('records')가 [{"date": ..., "price": ...}, ...] 리스트를 만듭니다.
        return {"data": chart_data.to_dict('records')}

    except Exception as e:
        return {"error": f"Failed to get chart data: {str(e)}"}

# --- 실행 예시 ---
if __name__ == "__main__":
    
    # 1. 현재 스냅샷 (이전 함수 테스트)
    print("--- [1] Fetching snapshot data for TSLA ---")
    tsla_snapshot = get_current_market_context('TSLA', market_index='^GSPC')
    # print(json.dumps(tsla_snapshot, indent=2, default=str)) # (출력이 기니 주석 처리)

    # 2. 차트용 이력 데이터 (새 함수 테스트)
    print("\n--- [2] Fetching 1-Year chart data for TSLA ---")
    tsla_chart_1y = get_chart_data('TSLA', period='1y')
    print(json.dumps(tsla_chart_1y, indent=2, default=str))
    
    print("\n--- [3] Fetching 1-Day chart data for TSLA (Intraday) ---")
    tsla_chart_1d = get_chart_data('TSLA', period='1d')
    print(json.dumps(tsla_chart_1d, indent=2, default=str))