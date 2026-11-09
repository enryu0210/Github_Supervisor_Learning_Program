# 인프라 선작업 정리

PM 일정의 10/30~11/3 항목 중 코드로 할 수 있는 작업을 `feature/infra-repo-ci-compose` 브랜치에 정리한 문서입니다.
진행 상태는 **2026-11-02 기준**이며, 이후 달라졌을 수 있으니 아래 확인 명령으로 다시 확인하세요.

## 한눈에 보기

| 항목 | 상태 |
|---|---|
| PR 템플릿 | 완료 (병합 전) |
| Docker Compose 뼈대 | 완료 (병합 전), 로컬 기동 확인 |
| `ci-lint`, `secret-scan`, `ci-docker-build` | 작성 완료, **GitHub Actions 실행은 미확인** |
| 착수 전 결정 6가지 | 레포 문서에 미반영, 팀 합의 필요 |
| 브랜치 보호, 이슈 라벨 | 미설정 |
| `ci-lint` 웹 부분, `ci-test` | 웹 코드와 CLI 테스트가 올라오면 추가 |

## 추가된 파일

| 파일 | 역할 |
|---|---|
| `.github/pull_request_template.md` | PR에 무엇을, 왜, 어떻게 테스트했는지 적는 양식 |
| `.github/workflows/ci-lint.yml` | PR에서 `ruff`로 Python 코드 검사 |
| `.github/workflows/secret-scan.yml` | PR에서 `gitleaks`로 전체 Git 이력의 시크릿 검사 |
| `.github/workflows/ci-docker-build.yml` | PR에서 Compose 파일 검증과 이미지 빌드 |
| `docker-compose.yml` | `ollama`, `watcher`, `dashboard` 서비스와 `ollama-models` 볼륨 정의 |
| `watcher/Dockerfile`, `dashboard/Dockerfile` | 임시 빈 컨테이너. 실제 코드가 생기면 교체 |
| `.env.example` | 필요한 환경변수 목록. 실제 키 값은 적지 않음 |
| `.gitignore` | `.env`와 Python, Node 생성 파일 제외 |

## 실행 방법

```bash
cp .env.example .env                                # 실제 키 값은 .env에만 적습니다
docker compose up -d --build
docker compose ps                                   # 서비스 3개가 떠 있는지 확인
docker compose exec ollama ollama pull gemma4:e2b   # 최초 1회, 모델은 볼륨에 저장됩니다
```

`ports are not available` 오류가 나면 PC에 설치된 Ollama 등이 같은 포트를 쓰는 경우가 많습니다.
`.env`의 `OLLAMA_HOST_PORT`를 비어 있는 번호(예: `21434`)로 바꾸세요.

## 역할 문서와 다르게 한 점

| 변경 | 이유 |
|---|---|
| Ollama 포트를 `127.0.0.1`에만 공개 | Ollama에는 인증이 없어, 모든 주소에 열면 같은 네트워크의 다른 사람도 쓸 수 있음 |
| `OLLAMA_HOST_PORT`로 포트 변경 가능 | PC에 설치된 Ollama와 포트가 겹치면 컨테이너가 뜨지 못함 |
| gitleaks 액션 대신 실행 파일 사용 | 레포를 조직으로 옮겨도 라이선스 키가 필요 없고, 로컬에서 같은 명령으로 재현 가능 |
| Ollama 이미지를 `0.40.13`으로 고정 | `latest`는 발표 직전에 동작이 바뀔 수 있음 |

## 검증 결과 (2026-11-02, 로컬)

Windows 11 PC 한 대에서 워크플로와 같은 명령을 실행한 결과입니다. Ubuntu 기반의 GitHub Actions 환경에서 돌린 결과는 아닙니다.

| 항목 | 결과 |
|---|---|
| 워크플로 문법 (`actionlint`) | 통과 |
| `ruff check .` | 통과. 당시 Python 파일이 없어 실제 검사 대상은 없음 |
| `gitleaks` | 레포 이력에서 시크릿 없음. 임시 저장소에 넣은 가짜 토큰은 탐지(exit 1) |
| `docker compose config`, `build`, `up` | 통과, 서비스 3개 기동 |
| `watcher`에서 `ollama` 호출 | `Ollama is running` 응답 |
| PC의 IP로 Ollama 접속 | 거부됨 |
| 볼륨 | 컨테이너를 다시 만들어도 볼륨 안 파일은 유지, 볼륨 밖 파일은 사라짐 |
| CRLF로 저장한 `.env` | LF와 같은 값으로 읽힘 |
| `gemma4:e2b` | 레지스트리 존재만 확인. 실제 다운로드와 실행은 미검증 |

## 주의할 점

- **브랜치 보호를 켜는 순서:** 2026-11-02 기준 협업자가 레포 소유자 1명뿐입니다. 이 상태로 승인 1명 규칙을 켜면 PR을 승인할 사람이 없으므로, 팀원 초대를 먼저 끝내야 합니다.
- **CLI의 Ollama 연결 대상:** PC에 Ollama 앱이 켜져 있으면 `localhost:11434`는 컨테이너가 아니라 그 앱으로 연결될 수 있습니다. CLI 개발과 테스트 때 어느 쪽에 붙었는지 확인이 필요합니다.
- **`NEXT_PUBLIC_*` 환경변수:** Next.js는 이 값을 빌드할 때 코드에 넣습니다. 실제 대시보드를 넣을 때는 Compose의 `build.args`로도 넘겨야 합니다.

## 다음 순서

1. 팀원 4명을 협업자로 초대합니다.
2. PR을 열어 워크플로 3개가 실제로 도는지 확인합니다.
3. 권아현의 승인을 받아 병합합니다(리뷰어 순환표 기준).
4. `main`과 `develop`에 브랜치 보호를 켜고, 직접 push가 거절되는지 확인해 증거로 남깁니다.
5. 이슈 라벨을 정하고, 결정 6가지를 확정해 문서에 반영합니다.

## 현재 상태 확인 명령

```bash
gh api repos/{owner}/{repo}/collaborators --jq '.[].login'     # 협업자
gh api repos/{owner}/{repo}/invitations --jq '.[].invitee.login'  # 대기 중인 초대
gh api repos/{owner}/{repo}/branches/develop/protection        # 브랜치 보호 (404면 꺼짐)
gh label list                                                  # 이슈 라벨
gh run list --branch feature/infra-repo-ci-compose             # Actions 실행 이력
```
