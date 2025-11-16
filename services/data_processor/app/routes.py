# 파일 경로: services/data_processor/app/routes.py

from flask import Blueprint, request, jsonify
# .yfinance_processor (같은 app 폴더 내의) 모듈에서 함수 임포트
from .yfinance_processor import get_current_market_context, get_chart_data

# 'market'이라는 이름으로 Blueprint 객체 생성
# /api/market/* 형태의 모든 요청을 이 블루프린트가 처리합니다.
market_bp = Blueprint('market', __name__, url_prefix='/api/market')


@market_bp.route('/context', methods=['GET'])
def context_endpoint():
    """
    호출 시점의 시장/종목 스냅샷 데이터를 반환합니다.
    (차트 지표, 재무 지표, 뉴스, 시장 지표)
    
    Query Params:
        ?ticker=TSLA
        ?market_index=^GSPC (KOSPI는 ^KS11)
    """
    ticker = request.args.get('ticker')
    market_index = request.args.get('market_index', '^GSPC') # 기본값 S&P 500

    if not ticker:
        return jsonify({"error": "Missing required query parameter: ticker"}), 400

    try:
        data = get_current_market_context(ticker, market_index)
        if data.get("error"):
            return jsonify(data), 500
        return jsonify(data), 200
        
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@market_bp.route('/chart', methods=['GET'])
def chart_endpoint():
    """
    프론트엔드 차트용 이력 데이터를 반환합니다.
    
    Query Params:
        ?ticker=TSLA
        ?period=1y (예: 1d, 5d, 1mo, 6mo, 1y, ytd, max)
    """
    ticker = request.args.get('ticker')
    period = request.args.get('period', '1y') # 기본값 1년

    if not ticker:
        return jsonify({"error": "Missing required query parameter: ticker"}), 400

    try:
        data = get_chart_data(ticker, period)
        if data.get("error"):
            return jsonify(data), 500
        return jsonify(data), 200
        
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500