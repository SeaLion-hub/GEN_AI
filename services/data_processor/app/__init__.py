# 파일 경로: services/data_processor/app/__init__.py

from flask import Flask
from flask_cors import CORS # CORS 처리를 위한 임포트

def create_app():
    """
    Flask 애플리케이션 팩토리 함수
    """
    app = Flask(__name__)
    
    # CORS(Cross-Origin Resource Sharing) 설정
    # 프론트엔드(React)가 다른 도메인(e.g., localhost:3000)에서
    # 이 API(e.g., localhost:5000)를 호출할 수 있게 허용합니다.
    CORS(app) 

    # --- 블루프린트 등록 ---
    # routes.py에서 정의한 market_bp를 앱에 등록합니다.
    from .routes import market_bp
    app.register_blueprint(market_bp)
    
    # --- 기본 라우트 (서버 건강 체크용) ---
    @app.route('/health')
    def health_check():
        return "Data Processor Service is ALIVE!"

    return app