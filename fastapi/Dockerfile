FROM python:3.9-slim

WORKDIR /app

COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt

COPY main.py .

# 로그 디렉토리 생성 
RUN mkdir -p /var/log/fastapi
RUN chmod 777 /var/log/fastapi

# 실행 명령 수정 (로그 설정 관련 옵션 제거)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
