import logging
import time
from fastapi import FastAPI, Request
from datetime import datetime

# 로깅 설정 
logging.basicConfig(
    level=logging.INFO, # info 레벨 이상의 로그만 출력 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", # 로그 출력 형식 설정 
    handlers=[ # 로그가 저장될 위치 지정 
        logging.FileHandler("/var/log/fastapi/app.log"), # 해당 파일로 로그 기록 
        logging.StreamHandler() # 터미널/콘솔에도 로그 출력 
    ]
)

logger = logging.getLogger("fastapi-app") # 해당 이름의 로거 생성 

app = FastAPI() # fastapi로 서버 인스턴스 생성 

@app.middleware("http") # 모든 http 요청을 받는 미들웨어 
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # 요청 로깅 
    logger.info(f"Request started: {request.method} {request.url.path}")

    response = await call_next(request)

    # 응답 시간 계산 
    process_time = time.time() - start_time
    logger.info(f"Request complete: {request.method} {request.url.path} - Took: {process_time:.4f}s")

    return response


@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Hello world"}

@app.get("/health")
async def health():
    logger.info("Health check endpoint called")
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/error")
async def trigger_error():
    logger.error("Error endpoint called - Generating sample error")

    return {"error": "This is a sample error log message"}

@app.get("/calc")
async def calculate(op: str, a: float, b: float):
    logger.info(f"Calc endpoint called: {a} {op} {b}")

    if op == "add":
        result = a + b
    elif op == "sub":
        result = a - b
    elif op == "mul":
        result = a * b
    elif op == "div":
        if b == 0:
            logger.warning("Division by zero attempted")
            return {"error": "Cannot divide by zero"}
        result = a / b
    else:
        logger.warning(f"Invalid operation: {op}")
        return {"error": "Invalid operation. Use add, sub, mul, or div."}

    logger.info(f"Calculation result: {result}")
    return {"operation": op, "a": a, "b": b, "result": result}