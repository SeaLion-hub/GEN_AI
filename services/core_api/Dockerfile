# 파일 경로: services/core_api/Dockerfile

# 1. Base Image: Python 3.10 공식 이미지를 기반으로 합니다.
FROM python:3.10-slim

# 2. Working Directory: 컨테이너 내부의 작업 폴더를 /app으로 설정합니다.
WORKDIR /app

# 3. Install Dependencies: 
# requirements.txt 파일을 먼저 복사하여 의존성을 설치합니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy Application Code: 
# 현재 폴더(.)의 모든 파일/폴더를 컨테이너의 /app 폴더로 복사합니다.
# (app/ 폴더 뿐만 아니라 모든 .py 파일을 복사합니다)
COPY . /app

# 5. Expose Port: 
# FastAPI/Uvicorn의 기본 포트인 8000번을 엽니다.
EXPOSE 8000

# 6. Run Application:
# 컨테이너가 시작되면 Uvicorn 서버를 실행합니다.
# 'app.main:app' -> app 폴더의 main.py 파일 안에 있는 app (FastAPI 객체)을 실행합니다.
# --host 0.0.0.0 -> 모든 IP에서 오는 8000번 포트 요청을 받습니다.
# --reload -> (개발용) 코드가 변경될 때마다 서버를 재시작합니다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]