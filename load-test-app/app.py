import time
import random
import threading
import psutil
import gc  # 가비지 컬렉션을 위한 모듈 추가
from flask import Flask, request, Response, jsonify
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

app = Flask(__name__)

# 메트릭 정의 - Prometheus 메트릭 타입별 용도
# Counter: 계속 증가하는 값 (요청 수 등)
# Histogram: 값의 분포 측정 (응답 시간 등)
# Gauge: 증가하거나 감소할 수 있는 값 (메모리, CPU 사용량 등)
REQUEST_COUNT = Counter('load_app_requests_total', 'Total app HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('load_app_request_latency_seconds', 'Request latency in seconds', ['method', 'endpoint'])
MEMORY_USAGE = Gauge('load_app_memory_usage_bytes', 'Memory usage in bytes')
CPU_USAGE = Gauge('load_app_cpu_usage_percent', 'CPU usage in percent')

# 스트레스 테스트 제어를 위한 글로벌 변수
stress_memory = False  # 메모리 부하 테스트 활성화 플래그
stress_cpu = False     # CPU 부하 테스트 활성화 플래그
memory_chunks = []     # 메모리 할당을 위한 리스트 (참조 유지 목적)

# 백그라운드 작업을 관리하기 위한 스레드 객체 저장
background_threads = []

def update_metrics():
    """백그라운드 스레드에서 주기적으로 시스템 메트릭 업데이트
    
    1초마다 현재 프로세스의 메모리 사용량과 CPU 사용률을 측정하여 
    Prometheus 게이지에 업데이트합니다.
    """
    while True:
        # 메모리 사용량 업데이트 - 바이트 단위
        MEMORY_USAGE.set(psutil.Process().memory_info().rss)
        
        # CPU 사용량 업데이트 - 퍼센트 단위
        CPU_USAGE.set(psutil.Process().cpu_percent(interval=0.1))
        
        time.sleep(0.9)  # 약 1초마다 업데이트 (interval 포함)

# 백그라운드 메트릭 업데이트 스레드 시작 - 앱 시작 시 실행
metrics_thread = threading.Thread(target=update_metrics, daemon=True)
metrics_thread.start()
print("메트릭 모니터링 스레드 시작됨")

def cpu_stress():
    """CPU에 부하를 주는 함수
    
    무작위 숫자 생성을 반복하여 CPU 사용률을 높입니다.
    stress_cpu 플래그가 False가 되면 스레드가 종료됩니다.
    """
    print("CPU 부하 테스트 시작")
    global stress_cpu
    
    while stress_cpu:
        # 백만 개의 랜덤 숫자 생성 - CPU 집약적 작업
        _ = [random.random() for _ in range(1000000)]
        time.sleep(0.01)  # 짧은 대기로 CPU 100% 점유 방지
    
    print("CPU 부하 테스트 종료")

def memory_stress():
    """메모리에 부하를 주는 함수
    
    10MB씩 메모리를 할당하여 memory_chunks 리스트에 저장합니다.
    최대 100MB까지 할당하거나 stress_memory 플래그가 False가 되면 종료됩니다.
    """
    print("메모리 부하 테스트 시작")
    global stress_memory, memory_chunks
    
    try:
        # 메모리 초기화 (이전 테스트에서 남은 메모리 해제)
        memory_chunks = []
        
        allocated_mb = 0
        while stress_memory and allocated_mb < 100:  # 최대 100MB 제한
            # 10MB 크기의 문자열 할당
            memory_chunks.append(' ' * 10 * 1024 * 1024)  # 10MB
            allocated_mb += 10
            print(f"메모리 할당: {allocated_mb}MB")
            time.sleep(1)  # 1초마다 10MB씩 증가
    
    except Exception as e:
        print(f"메모리 부하 테스트 중 오류 발생: {e}")
    
    print("메모리 부하 테스트 종료")

@app.route('/')
def home():
    """메인 페이지
    
    간단한 응답을 반환하며, 약간의 무작위 지연을 추가합니다.
    요청 수와 응답 시간을 Prometheus 메트릭으로 기록합니다.
    """
    start_time = time.time()  # 요청 시작 시간
    status_code = 200
    
    # 랜덤 지연 추가 (0-0.5초) - 실제 환경의 변동성 시뮬레이션
    time.sleep(random.random() * 0.5)
    
    # 요청 카운터 증가 및 응답 시간 기록
    REQUEST_COUNT.labels('get', '/', status_code).inc()
    REQUEST_LATENCY.labels('get', '/').observe(time.time() - start_time)
    
    return 'Load Testing Application\n'

@app.route('/metrics')
def metrics():
    """Prometheus 메트릭 엔드포인트
    
    Prometheus가 주기적으로 이 엔드포인트를 스크랩하여
    모든 정의된 메트릭(요청 수, 응답 시간, 메모리, CPU 등)을 수집합니다.
    """
    return Response(generate_latest(REGISTRY), mimetype='text/plain')

@app.route('/error')
def error():
    """에러 응답을 시뮬레이션하는 엔드포인트
    
    500 상태 코드를 반환하여 서버 오류 상황을 시뮬레이션합니다.
    에러 요청 수와 응답 시간을 Prometheus 메트릭으로 기록합니다.
    """
    start_time = time.time()
    status_code = 500  # 서버 오류 상태 코드
    
    # 에러 요청 카운터 증가 및 응답 시간 기록
    REQUEST_COUNT.labels('get', '/error', status_code).inc()
    REQUEST_LATENCY.labels('get', '/error').observe(time.time() - start_time)
    
    return 'Error occurred', 500

@app.route('/slow')
def slow():
    """느린 응답을 시뮬레이션하는 엔드포인트
    
    1-3초 사이의 지연을 추가하여 느린 응답을 시뮬레이션합니다.
    느린 요청 수와 응답 시간을 Prometheus 메트릭으로 기록합니다.
    """
    start_time = time.time()
    status_code = 200
    
    # 1-3초 사이 랜덤 지연 - 느린 응답 시뮬레이션
    delay = 1 + random.random() * 2
    time.sleep(delay)
    
    # 요청 카운터 증가 및 응답 시간 기록
    REQUEST_COUNT.labels('get', '/slow', status_code).inc()
    REQUEST_LATENCY.labels('get', '/slow').observe(time.time() - start_time)
    
    return f'Slow response (delay: {delay:.2f}s)\n'

@app.route('/status')
def status():
    """현재 부하 테스트 상태를 반환하는 엔드포인트
    
    현재 메모리 및 CPU 부하 테스트 상태와 실제 리소스 사용량을 JSON 형식으로 반환합니다.
    """
    global stress_memory, stress_cpu, memory_chunks
    
    # 현재 리소스 사용량 및 부하 테스트 상태 수집
    status_info = {
        "memory_stress_active": stress_memory,
        "cpu_stress_active": stress_cpu,
        "allocated_memory_mb": len(memory_chunks) * 10,  # 10MB 단위로 할당
        "memory_usage_mb": round(psutil.Process().memory_info().rss / (1024 * 1024), 2),
        "cpu_usage_percent": round(psutil.Process().cpu_percent(interval=0.1), 2)
    }
    
    return jsonify({
        "status": "running",
        "stress_tests": status_info,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/stress/memory/<action>')
def stress_memory_endpoint(action):
    """메모리 부하 테스트 엔드포인트
    
    메모리 사용량을 인위적으로 증가시키거나 해제합니다.
    'start': 메모리 사용량을 점진적으로 증가 (최대 100MB)
    'stop': 할당된 메모리를 해제하고 가비지 컬렉션 실행
    """
    global stress_memory, memory_chunks, background_threads
    
    if action == 'start':
        if not stress_memory:
            stress_memory = True
            print("메모리 부하 테스트 시작 명령 수신")
            
            # 별도 스레드에서 메모리 부하 생성
            memory_thread = threading.Thread(target=memory_stress, daemon=True)
            memory_thread.start()
            background_threads.append(memory_thread)
            
            return 'Memory stress started\n'
        else:
            return 'Memory stress already running\n'
            
    elif action == 'stop':
        stress_memory = False
        print("메모리 부하 테스트 중지 명령 수신")
        
        # 메모리 명시적 해제
        memory_chunks = []
        
        # 가비지 컬렉션 강제 실행
        gc.collect()
        print("메모리 해제 및 가비지 컬렉션 실행")
        
        return 'Memory stress stopped\n'
    else:
        return 'Invalid action\n', 400

@app.route('/stress/cpu/<action>')
def stress_cpu_endpoint(action):
    """CPU 부하 테스트 엔드포인트
    
    CPU 사용률을 인위적으로 증가시키거나 정상화합니다.
    'start': CPU 집약적인 작업을 통해 CPU 사용률 증가
    'stop': CPU 부하 생성 중단
    """
    global stress_cpu, background_threads
    
    if action == 'start':
        if not stress_cpu:
            stress_cpu = True
            print("CPU 부하 테스트 시작 명령 수신")
            
            # 별도 스레드에서 CPU 부하 생성
            cpu_thread = threading.Thread(target=cpu_stress, daemon=True)
            cpu_thread.start()
            background_threads.append(cpu_thread)
            
            return 'CPU stress started\n'
        else:
            return 'CPU stress already running\n'
            
    elif action == 'stop':
        stress_cpu = False
        print("CPU 부하 테스트 중지 명령 수신")
        return 'CPU stress stopped\n'
    else:
        return 'Invalid action\n', 400

if __name__ == '__main__':
    # 앱이 시작될 때 출력
    print("부하 테스트 애플리케이션 시작")
    print("사용 가능한 엔드포인트:")
    print("- /: 기본 페이지")
    print("- /metrics: Prometheus 메트릭")
    print("- /slow: 느린 응답 시뮬레이션")
    print("- /error: 오류 응답 시뮬레이션")
    print("- /status: 현재 부하 테스트 상태")
    print("- /stress/memory/start|stop: 메모리 부하 테스트")
    print("- /stress/cpu/start|stop: CPU 부하 테스트")
    
    # 모든 인터페이스에서 5000번 포트로 서비스 시작
    app.run(host='0.0.0.0', port=5000)