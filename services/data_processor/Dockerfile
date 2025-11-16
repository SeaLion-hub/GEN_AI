# 파일 경로: services/data_processor/Dockerfile

# 1. Base Image: Python 3.10 공식 이미지를 기반으로 합니다.
FROM python:3.10-slim

# 2. Working Directory: 컨테이너 내부의 작업 폴더를 /app으로 설정합니다.
WORKDIR /app

# 3. Install Dependencies: 
# requirements.txt 파일을 먼저 복사하여 의존성을 설치합니다.
# (코드가 바뀌어도 매번 설치하지 않도록 레이어 캐싱 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy Application Code: 
# 'app' 폴더 전체를 컨테이너의 /app/app 폴더로 복사합니다.
COPY ./app /app/app

# 5. Expose Port: 
# Gunicorn이 5001번 포트에서 실행될 것이므로 컨테이너의 5001번 포트를 엽니다.
# (로컬 실행 테스트 시 5001번을 사용하기로 했었음)
EXPOSE 5001

# 6. Run Application:
# 컨테이너가 시작되면 Gunicorn 서버를 실행합니다.
# 'app:create_app()' -> app 폴더의 __init__.py 안에 있는 create_app() 함수를 찾아 실행합니다.
# 0.0.0.0:5001 -> 모든 IP에서 오는 5001번 포트 요청을 받습니다.
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app:create_app()"]