# 🖥️ 로드밸런서와 오토스케일러 구현 및 시각화 모니터링

<br>
<img width="700" alt="pnu_proj_screen" src="https://github.com/user-attachments/assets/21224bdb-dd78-44df-a74f-4368ee8b58a2" />
<br>

## 💡 프로젝트 멤버
이상현 : Autoscaler 및 metric 수집 구현<br>
박재일 : Loadbalancer (with health check) 구현<br>
김나림 : Grafana 시각화 및 백엔드 서버 구현<br>

<br>

## 💡 프로젝트 소개

본 프로젝트는 최소한의 자원으로 안정적인 서비스 제공을 위해, 트래픽 분산을 담당하는 로드밸런서의 개발 및 서버 자원 자동 확장을 위한 오토스케일링 기능을 통합적으로 구현하고 이를 시각화하는 것을 목표로 합니다. 로드밸런서는 헬스 체크 기능을 통해 백엔드 서버의 상태를 주기적으로 확인하고, 응답이 없거나 비정상적인 서버를 자동으로 트래픽 분산 대상에서 제외함으로써 안정성을 확보합니다. 또한, 단순 라운드로빈 방식에 더해 서버 부하 정보를 반영한 분산 알고리즘을 도입하여, 요청 처리 효율을 높입니다. 오토스케일러 모듈은 프로메테우스로부터 사전 설정된 기간마다 수집된 컨테이너별 CPU 사용률을 기반으로, docker-compose.yml 파일에 설정된 임계치 이상의 사용률이 3분 이상 지속되면 scale-out 하고 임계치의 절반 미만의 사용률이 1분 이상 지속되면 scale-in 합니다. 이 모듈을 사용하여 별도의 수동적인 개입 없이 시스템의 트래픽/부하 변화에 따라 자동으로 컨테이너의 수를 조절하여 비용 효율적인 운영을 가능하게 합니다. 또한 프로메테우스를 통해 수집한 메트릭들을 Grafana를 활용해 프론트엔드로 표기합니다. 프론트엔드창에서는 CPU 사용량 및 현재 서버의 수 등을 시각적으로 확인 가능하고, 인터페이스의 버튼을 이용해 손쉽게 부하를 가할 수 있습니다.

<br>

## 💡 프로젝트의 필요성
**효율적인 리소스 사용**<br>
고정된 서버 개수로 항상 최대 트래픽을 감당하도록 구성하면, 트래픽이 적을 때에도 불필요하게 자원이 낭비됩니다.<br>
오토스케일링 기능을 통해 트래픽 변화에 따라 동적으로 인스턴스 수를 조정함으로써, 최소한의 자원으로 안정적인 서비스 제공이 가능합니다.

**안정적인 트래픽 분산**<br>
단순 Round-Robin 방식은 서버의 실시간 부하 상태를 고려하지 않기 때문에, 특정 서버에 과부하가 집중될 수 있습니다. 이에 latency 모드를 추가하여 성능이 우수한 서버가 더 많은 부하를 감당하도록 설계되었습니다.<br>
또한, 헬스체크가 구현된 로드밸런서를 사용하면, 응답 지연 또는 장애가 발생한 서버를 자동으로 회피하여 트래픽을 분산시킬 수 있어 가용성을 높입니다.

**운영 편의성 및 가시성 확보**<br>
Prometheus와 Grafana를 통한 모니터링 및 시각화 시스템을 갖추면, 운영자는 현재 서버 상태를 실시간으로 파악하고, 장애나 과부하 발생 시 즉시 대응할 수 있습니다. 또한 학습을 위해 부하 버튼을 통해서 손쉽게 로드밸런서와 오토스케일링 과정을 시각적으로 확인 가능합니다.

<br>

## 💡 관련 기술 소개
**Docker / Docker Compose**

    각 컴포넌트(백엔드, 로드밸런서, 오토스케일러, Prometheus, Grafana)를 컨테이너화하여 분리된 환경에서 독립적으로 실행합니다.
    docker-compose.yml을 통해 전체 스택을 한번에 기동/종료할 수 있도록 구성했습니다.

**Prometheus**

    오픈소스 시계열 데이터베이스 및 모니터링 시스템입니다.

    HTTP 기반의 푸시(Push) 방식이 아닌, 구성된 대상(Target)으로부터 메트릭을 폴링(Pull)하여 수집합니다.

    오토스케일러와 백엔드 서버에서 제공하는 메트릭 엔드포인트(/metrics)를 스크레이핑하여 CPU 사용률, 메모리 사용량, 응답 지연 시간 등을 수집합니다.

**Grafana**

    Prometheus에 저장된 메트릭을 시각화하는 대시보드 도구입니다.

    다양한 그래프, 차트, 알람 설정을 통해 운영자가 실시간으로 시스템 상태를 모니터링하고, 이상 징후를 감지할 수 있도록 지원합니다.

**Python 3.x**

    프로젝트의 대부분의 모듈들이 모두 Python 언어로 구현되었습니다.

    requests 라이브러리를 사용해 Prometheus HTTP API에서 메트릭을 조회하고, Docker SDK (docker 패키지)를 통해 컨테이너 제어(생성, 삭제, 상태 조회) 기능을 제공합니다.

**HTTP 서버 프레임워크 (Flask)**

    로드밸런서의 헬스체크 엔드포인트 및 요청 분배용 HTTP 서버(loadbalancer/server.py)는 Python 기반 프레임워크를 사용합니다.

    헬스체크를 위한 간단한 GET 요청 핸들러와, 클라이언트 요청을 백엔드로 전달하는 Reverse Proxy 역할을 수행합니다.

**로컬 네트워크 및 리눅스 환경**

    전체 스택은 리눅스(혹은 WSL2) 기반에서 Docker로 실행됩니다.

    로드밸런서가 백엔드 컨테이너들의 IP와 포트를 동적으로 감지하여 트래픽을 분산시키기 때문에, 네트워크 설정에 대한 기본 이해가 필요합니다.

<br>

## 💡 프로젝트 결과물 설명

### 디렉토리 구조
```bash
PNU_cloud_computing/
├── backend/
│   ├── Dockerfile
│   └── src/
│       ├── server.py
│       └──requirements.txt
│
├── autoscaler/
│   ├── __init__.py
│   ├── autoscaler.py
│   ├── metrics.py
│   └── Dockerfile
│
├── load_balancer/
│   ├── __init__.py
│   ├── health_check.py
│   ├── balancer.py
│   ├── server.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── prometheus/
│   ├── targets/
│   │   └── flask.json
│   └── prometheus.yml
│
├── grafana/
│   ├── plugins/
│   └── grafana.db
├── .grafana.ini
│
├── fe/
│   └── ...
│
└── docker-compose.yml
```

**backend/**

    실제 서비스 로직을 실행하는 백엔드 애플리케이션 소스 코드가 위치합니다.

    현재 프로젝트에서는 단순히 백엔드의 기본적인 기능만하도록 작성되었습니다.

**autoscaler/**

    autoscaler.py: 주기적으로 Docker 컨테이너의 CPU 사용률 등을 실시간으로 조회한 뒤, 확장/축소 로직에 따라 새로운 컨테이너를 생성하거나, 제거합니다.

    metrics.py: Prometheus로부터 메트릭을 조회하는 PrometheusClient 클래스와, Docker 컨테이너를 제어하는 DockerManager 클래스를 포함합니다.

    - Scale-Out: 지정된 CPU 임계치(예: 70%)를 일정 시간(예: 3분) 초과하면 인스턴스를 추가

    - Scale-In: CPU 임계치의 절반(예: 35%) 이하로 일정 시간(예: 1분) 연속 유지되면 인스턴스를 제거

    최소/최대 인스턴스 개수를 설정하여, 무한 확장을 방지합니다.

**loadbalancer/**

    health_check.py: 각 백엔드 노드(컨테이너)의 헬스체크를 수행하는 로직을 정의합니다. 주기적으로 HTTP 요청을 보내고, 응답 코드를 기반으로 정상/비정상 상태를 판정합니다.

    balancer.py: 라운드로빈 방식과 현재 각 서버의 부하(예: CPU 사용률 또는 응답 시간)를 고려한 가중치 기반 분산 알고리즘을 모두 지원합니다.

    server.py: 클라이언트로부터 들어오는 요청을 받아, balancer.py에서 선택된 백엔드 노드로 요청을 전달(프록시)하는 라우팅 역할을 수행합니다다. 동시에, /health 엔드포인트를 제공하여 외부에서 로드밸런서 자체 상태를 체크할 수 있습니다.

**prometheus/**

    targets/flask.json: 스케일링된 백엔드 풀을 관리하는 파일입니다.
    
    prometheus.yml: Prometheus가 메트릭을 수집할 대상(autoscaler, backend, loadbalancer 등)을 정의하는 설정 파일입니다.

**grafana/**

    Grafana dashboard 출력을 위한 기본 설정 파일들입니다.

**fe/**

    localhost:3000으로 접속시 표현되는 프론트엔드 화면을 구성하는 파일들입니다.

**docker-compose.yml**

    Prometheus, Grafana, Loadbalancer, Backend, Autoscaler를 하나의 네트워크로 묶어 동시에 기동할 수 있도록 정의된 Compose 파일입니다.

    서비스별로 필요한 환경 변수, 볼륨, 포트 매핑 등을 모두 기술해 두어, 로컬 혹은 클라우드 VM에서 단번에 전체 스택을 실행할 수 있도록 합니다.

<br><br>

## 💡 프로젝트 사용법

### Prerequisites

    Docker Engine ≥ 20.x
    Docker Compose ≥ 1.29.x


### Installation
```bash
$ git clone https://github.com/JAEIL1999/PNU_cloud_computing.git
$ cd PNU_cloud_computing
```

### How to start
```bash
# 1) Docker Compose로 전체 스택 기동
$ docker-compose up -d

# (선택) 모든 컨테이너가 정상 상태인지 확인
$ docker ps

# 2) 실시간 CPU 사용량 확인
$ docker-compose logs -f
```
위 내용들이 확인 되었다면 아래 주소를 통해서 메트릭 수집 내용들을 시각적으로 확인 가능합니다.

```bash
http://localhost:3000
```

<br><br>

## 💡 프로젝트 활용방안

**학습용 데모 환경**

    오토스케일링과 로드밸런싱의 기본 개념을 이해하고 실습하기 위한 학습용 환경으로 활용할 수 있습니다.

    Prometheus와 Grafana를 함께 구성함으로써, 모니터링 대시보드를 구성하는 과정을 직접 실습해 볼 수 있습니다.

**소규모 웹 서비스 호스팅**

    VPS(가상 사설 서버)나 온프레미스 환경에서도 Docker를 지원한다면, 해당 솔루션을 그대로 배포하여 소규모 웹 애플리케이션을 안정적으로 운영할 수 있습니다.

    트래픽 패턴이 유동적인 서비스(예: 개인 블로그, 포트폴리오 사이트)에서 리소스를 효과적으로 관리할 수 있습니다.

**커스텀 확장 기능 개발**

    프로젝트의 핵심 로직(예: 오토스케일러 스케줄링 알고리즘, 헬스체크 기준)을 자유롭게 수정하여, 특정 서비스 요구사항에 맞는 특화된 확장 정책을 실험할 수 있습니다.

    예를 들어, CPU 외에도 메모리 사용량, 네트워크 대역폭, 요청 처리 대기 시간 등을 기준으로 확장 정책을 다중 지표(Multi-criteria) 기반으로 확장하도록 기능을 추가할 수 있습니다.
