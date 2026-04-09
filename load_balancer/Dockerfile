FROM python:3.9-slim

WORKDIR /app

# 필요한 패키지 설치 (docker sdk 등)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# FastAPI 실행 (uvicorn 사용)
# --workers 설정을 통해 동시 처리 성능을 조절할 수 있습니다.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
