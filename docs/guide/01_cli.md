# 권아현 · 개발 팀장 · CLI 메인 프로그램 가이드

작업 규칙은 루트의 `CLAUDE.md`가 우선한다.

## 1. 내 임무
- **CLI v0.1을 11/9(월)까지 완성**한다. 위험한 git 명령을 실행 전에 가로채 규칙 엔진이 판정하고, 학생에게 **[1] 그냥 실행 / [2] 어떻게 해야 하나요?** 두 선택지를 준다. [2]를 고르면 올바른 방법을 학생이 **직접 입력**하도록 단계별로 안내하고, 결과를 로그로 남긴다.
- **이벤트 스키마 v1을 11/9에 고정**한다. 웹(임지윤)과 DB(이남주)가 이 스키마를 보고 일하므로 내가 계약의 주인이다. (v1 변경은 11/5 확정, 두 담당자에게 통보)
- CLI 이후 **11/10부터 watcher(핵심 기능 2)**를 만든다. CLI의 규칙 엔진을 그대로 재사용한다.
- 개발 팀장으로서 PR 리뷰가 한 사람에게 몰리지 않게 순환시키고, 기능 단위로 PR이 쪼개지는지 확인한다.

### CLI v0.1 설계 확정 사항 (11/5)
1. R01·R04는 **main만 검사**한다(develop 제외). fork 동기화용 `git push origin develop`은 경고 없이 통과시킨다(회의 안건 종결). develop 보호는 GitHub 브랜치 보호(장일호 담당)로 맡긴다.
2. 모든 규칙은 **2선택지**([1] 그냥 실행 / [2] 어떻게 해야 하나요?) 화면 하나로 통일한다. R03(비밀 정보)만 "그냥 실행"을 제공하지 않는다. 기본값은 Enter = [2].
3. 복구 안내는 명령어 목록만 보여주고 끝내지 않는다. **학생이 단계를 직접 입력**하게 하고, 래퍼가 입력을 확인한 뒤 다음 단계로 넘기는 학습 가이드 형태로 진행한다.
4. **"그냥 실행" 시 영향 안내**를 추가한다. 선택 화면에 결과 한 줄, 실행 직후 되돌리는 방법을 보여 준다.
5. **여러 규칙에 걸리면 심각한 순서대로 모두 보여 준다.** [2]면 가장 심각한 규칙부터 차례로 가이드한다.
6. **터미널에서만 검사한다.** 파이프·스크립트 등 터미널이 아니면 검사 없이 그대로 실행한다.
7. 이벤트 `action` 값은 6장의 6개 값(`allowed`·`guided`·`blocked`·`guide_completed`·`guide_stopped`·`detected`)으로 정하고, 가이드 완료/중단 이벤트가 원본 이벤트를 가리키도록 `related_event_id` 필드를 둔다.
8. **R07은 v0.2로 연기한다.**

## 2. 일정
| 기간 | 할 일 | 완료 기준 |
|---|---|---|
| 11/5~11/6 | 골격 PR, shim·parser·context, R01·R02·R03, 2선택지 화면(템플릿 설명) | `git push --force origin main`에서 선택지가 뜨고 ci-lint·ci-test 통과 |
| 11/7 | guide 엔진(상태·매칭·hint/done/stop, 다중 위반 순차 진행), R01·R02·R03 시나리오, 이벤트 저장 | R01 가이드를 끝까지 진행하면 `guide_completed`가 남는다 |
| 11/8 | Ollama 설명·캐시, R04·R05·R06, init·doctor·config·log, "그냥 실행" 영향 문구 | Ollama를 꺼도 동작한다 |
| 11/9 | Windows(PowerShell·Git Bash) 확인, 스키마 v1 고정, `samples/` 20건+, v0.1.0 태그 / 인계 | 팀원 PC 2대 이상 설치 |
| 11/10~11/19 | watcher 개발 (5장) | 우리 레포의 위반이 이벤트로 출력된다 |
| 11/20~11/23 | Compose 컨테이너 통합 (장일호·임호일과 함께). DB 쓰기 자체는 11/17~ 이미 시작(5장). **추후 결정**: DB 쓰기 코드 담당 구분(권아현·이남주 vs 장일호·임호일) — 장일호 확인 예정 | `docker compose up`으로 watcher가 돈다 |
| 11/24~11/26 | 퀴즈 생성 주도. **watcher가 DB 이벤트 기준으로 생성·전송**(오답·허용 이벤트 → Ollama → `quizzes`), CLI `sync`는 관여 안 함(11/9 확정, 남주 전달) | 대시보드에 퀴즈가 나온다 |
| 11/27~12/4 | 테스트·보완, 도그푸딩 결과 정리, 발표 준비 | 발표 데모가 재현된다 |

> 11/5 착수라 Sprint 1이 이틀 밀렸다. 11/9 v0.1.0은 지킨다. R07은 v0.2로 미루고, P2(되돌릴 수 없는 명령 추가 확인, 상황별 심각도 조절)는 시간이 남으면 한다.

## 3. CLI 개발 가이드 (11/5~11/9)

### 3-1. v0.1 범위
| ID | 감지 대상 | 감지 명령 | 우선 | 심각도 | 그냥 실행 |
|---|---|---|---|---|---|
| R01 | **main**에 직접 push (develop 제외) | `git push` | P0 | high | 가능 |
| R02 | force push(`-f`, `--force`, `+ref`). `--force-with-lease`만이면 medium | `git push` | P0 | high | 가능 |
| R03 | 비밀 정보 staged(.env, 개인키, 토큰 패턴) | `add`·`commit`·`push` | P0 | high | **불가** |
| R04 | **main**에서 직접 커밋 (develop 제외) | `git commit` | P1 | medium | 가능 |
| R05 | 브랜치명 규칙 위반 | `checkout -b`, `switch -c`, `branch` | P1 | low | 가능 |
| R06 | 커밋 메시지 규칙 위반 | `commit -m` | P1 | low | 가능 |
| R07 | 되돌리기 어려운 명령(`reset --hard`, `clean -fd`, `branch -D`) | 해당 명령 | **v0.2** | medium | 가능 |
| R08 | PR 대상 브랜치 오류(feature → main, develop이어야 함) | N/A(watcher, GitHub PR API) | P1 | low | N/A(watcher 전용, 선택지 없음) |

- P0은 반드시, P1은 되도록, P2는 시간이 남으면 한다. R07은 v0.2로 미룬다.
- 검사 기준: 브랜치 `feature|fix/<영역>-<설명>`(영역: cli·watcher·web·db·infra·docs, 대문자·`#` 금지), 커밋 `type(scope): 설명`.
- 보호 브랜치 목록은 `.gitcoach.toml`의 `protected = ["main"]`. 다른 팀이 develop을 다시 넣을 수 있게 config로 둔다.
- 검사 대상은 **터미널에서 직접 입력한 명령**뿐이다.
- **v0.1에서 하지 않는 것**: R07, GitHub API 감지(watcher), DB 전송(`sync`는 stub), 퀴즈. 이벤트는 로컬에만 저장.

### 3-2. 동작 흐름
위반이 없으면 지연 없이 실행하고, 위반일 때만 멈춰 두 선택지를 보여 준다. LLM은 [2]를 고른 뒤에만 부르므로 선택 화면은 즉시 뜬다.

1. 학생이 `git ...`을 입력하면 쉘 함수 `git`이 `gitcoach run -- <인자>`로 넘긴다.
2. 터미널이 아니면(파이프·스크립트) 검사하지 않고 진짜 git을 그대로 실행한다. 기록도 남기지 않는다.
3. 가이드가 진행 중이면 먼저 기대 단계와 비교한다(3-3).
4. `parser`가 인자를 해석하고 `context`가 브랜치·remote·staged 파일을 모은 뒤, 규칙 엔진이 판정한다.
5. 위반이 없으면 진짜 git을 바로 실행한다. 기록도 남기지 않는다.
6. 위반이 있으면 **심각한 순서대로 모두** 보여 준다(규칙명 + 한 줄 경고 + "그냥 실행하면:" 한 줄, 모두 템플릿). 선택은 명령 하나에 한 번 받는다. Enter는 [2].
7. [1]이면 git을 실행하고 위반마다 `allowed` 기록 → "되돌리려면" 안내. [2]면 원래 명령을 취소하고 위반마다 `guided` 기록 → 설명(Ollama, 실패 시 템플릿) → **가장 심각한 규칙부터 차례로** 가이드(하나가 끝나면 다음 가이드 시작).
8. 위반 중에 R03이 있으면 [1] 대신 [q] 취소만 있다. 취소하면 **R03의 `blocked` 1건만** 기록하고, 함께 걸린 다른 위반(예: R01)은 기록하지 않는다(#12 확정, #15 머지 때 문서에 빠졌던 부분 11/10 보강).

"터미널"의 판단: 사용자가 키보드로 답할 수 있는가(stdin이 tty인가)로 본다. `git log | grep`처럼 출력만 파이프로 넘기는 경우는 키보드 입력이 살아 있으므로 터미널로 본다. IDE·GitHub Desktop의 Git 버튼은 애초에 쉘 함수를 거치지 않으므로 검사 대상이 아니며, watcher가 GitHub 쪽에서 보완한다.

화면 예시:
```text
$ git push origin main
⚠  [R01] main 브랜치에 직접 push하려고 해요.
   그냥 실행하면: 리뷰·CI 없이 main에 들어가 배포까지 이어질 수 있어요.
   [1] 그냥 실행할래요
   [2] 어떻게 해야 하나요?   (기본값)
> 2

💡 왜 문제일까요?  (Ollama 설명, 실패 시 템플릿)
   main은 팀 전체가 공유하는 배포 브랜치예요. ...

📘 가이드 시작: feature 브랜치로 옮겨 PR 올리기 (총 3단계)
   원래 명령(git push origin main)은 취소했어요.
   1/3  지금 커밋을 가진 새 브랜치를 만드세요.
        힌트: git switch -c feature/<영역>-<설명>

$ git switch -c feature/cli-login-fix
✅ 1/3 완료!  2/3  새 브랜치를 내 fork(origin)에 올리세요.
```

다중 위반 예시 (`git push --force origin main`):
```text
⚠  위반 2개 (심각한 순서)
   1. [R01] main 브랜치에 직접 push하려고 해요.
      그냥 실행하면: 리뷰·CI 없이 main에 들어가 배포까지 이어질 수 있어요.
   2. [R02] 원격 기록을 덮어쓰는 force push를 하려고 해요.
      그냥 실행하면: 다른 사람이 올린 커밋이 사라질 수 있어요.
   [1] 그냥 실행할래요
   [2] 어떻게 해야 하나요?   (기본값) → R01 가이드부터 차례로
```

### 3-3. 학습 가이드 ("어떻게 해야 하나요?")
도구가 대신 실행하지 않고 학생이 **직접 입력**하게 한다. 모든 git 명령은 어차피 래퍼를 거치므로, 래퍼가 "지금 기대하는 단계"와 입력을 비교해 진행을 판단한다.

1. 가이드는 규칙별 고정 시나리오다. 단계마다 `설명 · 기대 명령(패턴) · 힌트 · 정답 예시`를 가진다. LLM이 명령어를 만들지 않는다.
2. 진행 상태는 레포별 `.git/gitcoach/guide.json`에 저장한다. 터미널을 닫아도 이어진다. 다중 위반이면 남은 가이드 목록(큐)도 함께 저장한다.
3. 기대 명령과 맞으면 실행하고 ✅ 후 다음 단계를 안내한다.
4. `git status`·`log`·`diff`·`branch` 같은 확인용 명령은 그냥 실행하고 현재 단계를 한 줄 상기시킨다.
5. 그 외 명령은 평소처럼 규칙 검사를 거치고 "가이드 진행 중: 다음은 …" 힌트를 붙인다.
6. git 밖의 단계(`gh pr create`, `.gitignore` 편집)는 래퍼가 볼 수 없으므로 `gitcoach guide done`으로 직접 완료 표시한다.
7. 가이드 하나가 끝나면 요약(배운 점 1줄)을 보여 주고 `guide_completed`를 남긴다. 큐에 다음 가이드가 있으면 이어서 시작한다. 퀴즈(핵심 기능 3)의 출제 근거가 된다.
8. `guide skip`은 **현재 가이드만** 중단한다 — `guide_completed` 대신 `guide_stopped`를 남기고, 큐에 남은 가이드가 있으면 바로 이어서 시작한다(7번과 동일하게 자동 진행). `guide stop`은 **큐 전체**를 중단한다 — 현재 가이드에 `guide_stopped`를 남기고 남은 큐는 비운 채 종료한다(11/9 확정). 둘 다 별도 action 값 없이 `guide_stopped`로 기록한다(스키마 값은 6개로 유지).
9. 가이드 진행 중 **무관한 명령**에서 새 위반이 뜨고 학생이 다시 [2]를 고르면, 진행 중이던 가이드·큐는 버리고 새 위반의 가이드로 **덮어쓴다**(11/9 확정, 최소 구현 — 기존 가이드를 보존·재개하는 것은 범위 밖).

명령어: `gitcoach guide`(현재 단계 다시 보기) · `guide hint`(1회: 힌트, 2회: 정답 명령) · `guide done` · `guide skip` · `guide stop`

| 규칙 | 가이드 제목 | 단계 |
|---|---|---|
| R01 | feature 브랜치로 옮겨 PR 올리기 | `git switch -c feature/<영역>-<설명>` → `git push -u origin <브랜치>` → `gh pr create --base develop` (done) |
| R02 | 원격 변경을 가져와 안전하게 push | `git pull --rebase` → (충돌 시) 해결 후 `git rebase --continue` → `git push` |
| R03 | 비밀 파일 빼고 .gitignore에 등록 | `git restore --staged <파일>` → `.gitignore`에 추가 (done) → `git add .gitignore` |
| R04 | 커밋을 feature 브랜치에서 하기 | `git switch -c feature/<영역>-<설명>` → `git commit -m "type(scope): 설명"` |
| R05 | 규칙에 맞는 브랜치명 쓰기 | 제안 이름으로 `git switch -c <제안>` |
| R06 | 커밋 메시지 형식 맞추기 | `git commit -m "type(scope): 설명"` (type 목록 힌트) |
| R07 (v0.2) | 지우기 전에 확인하기 | reset: `git stash` → 재시도 / clean: `git clean -n` → 재시도 / branch: `git branch -d` |

### 3-4. "그냥 실행" 시 영향
[1]을 골랐을 때의 결과는 규칙마다 다르고, 특히 **되돌릴 수 있는가**가 크게 갈린다. 이 표를 선택 화면 한 줄(`consequence`)과 실행 직후 "되돌리려면" 안내에 쓴다. 정확해야 하므로 LLM이 아니라 템플릿이다.

| 규칙 | 그냥 실행하면 | 되돌리기 | 사후 복구 |
|---|---|---|---|
| R01 | 보호가 있으면 서버가 거절. 없으면 리뷰·CI 없이 main에 들어가 Vercel 배포까지 이어질 수 있음 | 가능 | `git revert <커밋>` 후 push (force push로 지우면 R02 문제) |
| R02 | 다른 사람 커밋이 원격에서 사라지고 그 사람의 로컬 기록이 갈라짐. PR 리뷰 댓글도 어긋남 | 대체로 가능 | 커밋이 남은 팀원 PC에서 다시 push, 또는 `git reflog` |
| R03 | 허용 불가 | — | — |
| R04 | 로컬이라 당장 피해 없음. 다음 push에서 R01, 로컬 main이 원격과 갈라져 동기화 실패 | 가능 | `git branch feature/...`로 옮긴 뒤 main을 원격 상태로 |
| R05 | 동작은 정상. watcher 재경고, `pr-convention` 실패, 대시보드 통계 누락 | 쉬움 | `git branch -m <새 이름>` |
| R06 | 기록 가독성 저하, `pr-convention` 실패 | push 전 쉬움 | push 전 `git commit --amend` (push 후 amend는 force push 필요 → R02) |
| R07 reset --hard (v0.2) | 커밋 안 한 변경 **영구 삭제** | 일부 불가 | `git reflog` → 이전 위치 |
| R07 clean -fd (v0.2) | 추적 안 하는 새 파일 **영구 삭제** (.gitignore 파일은 `-x` 없으면 남음) | **불가** | 없음 |
| R07 branch -D (v0.2) | 병합 안 된 커밋이 사라진 것처럼 보임 | 기간 내 가능 | reflog에서 찾아 `git branch <이름> <커밋>` (보통 30일 안팎) |

반영 계획:
1. 선택 화면에 "그냥 실행하면:" 한 줄 — v0.1
2. [1] 실행 직후 "되돌리려면" 안내, `gitcoach guide undo`로 복구 가이드 — v0.1 (`guide undo`는 원래 `allowed` 이벤트를 참조해야 해서 `cli-event-log`(3-8의 7번) 이후 별도 PR로 진행, 11/9 확정)
3. 되돌릴 수 없는 명령(`clean -fd`, 미커밋 변경이 있는 `reset --hard`)은 [1]이어도 y/N 한 번 더 — **P2** (R07과 함께 v0.2가 될 가능성 높음)
4. 상황별 심각도 조절(혼자 쓰는 feature 브랜치의 force push는 낮춤) — **P2** (시간이 남으면)
5. 반복 허용한 규칙을 퀴즈에 우선 출제 — v0.1에서는 이벤트만 남기고 11/24~ 퀴즈 때 사용

### 3-5. 레포 구조
```
git-coach/
├─ pyproject.toml          # Python 3.11+, Typer·Rich·httpx, dev: pytest·ruff
├─ .gitcoach.toml          # 레포별 설정 예시 (protected = ["main"])
├─ .github/workflows/      # ci-lint.yml, ci-test.yml
├─ src/gitcoach/
│  ├─ cli.py               # Typer: run, init, doctor, config, log, explain, guide, sync, uninstall
│  ├─ shim.py              # 전체 흐름 조립 (터미널 확인 → 가이드 확인 → 판정 → 선택 → 실행 → 기록)
│  ├─ ui.py                # Rich 출력, 2선택지 프롬프트, 가이드 화면
│  ├─ parser.py            # git 인자 → Command
│  ├─ context.py           # 브랜치·remote·staged 파일·tty 수집 (git 실행은 여기서만)
│  ├─ models.py            # Command, Context, Violation, Choice 등 공용 데이터클래스
│  ├─ rules/               # r01_protected_push.py … r06_commit_message.py (r07은 v0.2), 규칙 1개 = 파일 1개
│  ├─ guide/               # scenarios.py(규칙별 단계), matcher.py(입력↔기대 단계), state.py(진행·큐 저장)
│  ├─ explain/             # ollama.py, prompts.py, templates.py(폴백), cache.py
│  ├─ events.py            # 이벤트 스키마 v1, 로컬 SQLite 저장
│  └─ config.py            # ~/.gitcoach/config.toml(member=github_login 등) + .gitcoach.toml 병합
├─ tests/                  # 규칙별 단위 테스트, tmp_path 임시 레포 통합 테스트
└─ samples/                # 샘플 이벤트 JSON (11/9 20건+)
```
`rules/`·`guide/`·`explain/`·`events.py`·`models.py`는 watcher가 재사용하는 공용 부분이라 CLI 전용 코드(`cli.py`·`shim.py`·`ui.py`)를 import하지 않는다.

`context.py`의 보호 브랜치 값은 `config.py`(3-8의 10번 PR)가 생기기 전까지는 `["main"]`을 하드코딩해서 돌려주고, `cli-config` PR에서 실제 설정 파일을 읽도록 교체한다(앞 PR이 뒤 PR을 기다리지 않게 하기 위함).

**모듈 간 약속 (인터페이스)** — 각 모듈이 다른 모듈에 제공하는 함수와 입출력. 이것만 지키면 따로 만들어도 맞물린다. 바꾸려면 PR에서 논의한다.

| 모듈 | 핵심 함수 | 돌려주는 것 |
|---|---|---|
| parser | `parse(argv) -> Command` | 하위 명령, 플래그, remote, refspec, 메시지 |
| context | `collect(cmd) -> Context` | 현재 브랜치, push 대상 브랜치, staged 파일, 보호 브랜치, tty 여부 |
| rules | `check_xxx(cmd, ctx) -> Violation \| None` | 순수 함수, I/O 금지 |
| rules | `evaluate(cmd, ctx) -> list[Violation]` | 심각도 순 정렬(R03 우선). **화면에는 전부** 표시 |
| guide | `start(violations) / on_command(argv) / advance() / hint() / done() / stop()` | 시나리오 진행 상태, 다중 위반 큐 |
| explain | `explain(v) -> Explanation` | 한국어 설명 + `llm_used`. 8초 초과·오류 시 템플릿 |
| events | `record(event)` | 로컬 SQLite에 저장 |

### 3-6. 핵심 설계 결정
1. **가로채기는 쉘 래퍼로 한다.** `gitcoach init`이 `git`이라는 이름의 쉘 함수(bash, zsh, PowerShell)를 설치하고, 이 함수가 `gitcoach run -- <인자>`를 거쳐 진짜 git을 부른다. 해제는 `gitcoach uninstall`. `command git`으로 우회할 수 있지만 이 도구는 강제가 아니라 코치이므로 괜찮다. Windows 비율이 높으니 PowerShell과 Git Bash를 먼저 확인한다.
2. **터미널에서만 검사한다.** stdin이 tty가 아니면(스크립트, 입력 파이프) 판정 없이 진짜 git을 그대로 실행한다. IDE·GitHub Desktop의 Git 버튼은 쉘 함수를 거치지 않으므로 애초에 대상이 아니다. 이런 행동은 watcher가 GitHub 쪽에서 보완한다.
3. **판정은 코드, 설명은 LLM.** 규칙은 `Violation`만 돌려준다. LLM에는 facts만 주고 "왜 위험한지"만 설명하게 한다. 가이드 명령어·경고·"그냥 실행하면" 문구는 모두 코드에 고정한다.
4. **`Violation` 필드**: `rule_id, title, severity, facts, guide_id, allow_run, warning, consequence`. R03만 `allow_run=False`. 기존 `fix_steps`는 가이드 시나리오로 옮겨서 없앴다.
5. **LLM 호출은 [2]를 고른 뒤에만, 짧게, 실패해도 동작하게.** Ollama `/api/chat`, 응답 상한 약 200토큰, 타임아웃 8초 안팎(측정 후 조정). 실패하면 템플릿. 같은 규칙·사실의 설명은 캐시. e2b는 작은 모델이라 "왜 문제 · 생기는 일 · 아래 가이드를 따르라" 3문장 형식으로 고정한다. 다중 위반이면 각 가이드를 시작할 때 그 규칙의 설명을 부른다.
6. **위반이 없으면 LLM도 기록도 없이 바로 통과.** 체감 지연이 없어야 한다.
7. **모든 선택을 이벤트로 남긴다.** 다중 위반이면 위반마다 이벤트 1건. 스키마는 6장.
8. **시크릿 값은 어디에도 남기지 않는다.** 로그와 프롬프트에는 파일명, 패턴 종류, 줄 번호만.
9. **여러 규칙에 걸리면** 심각한 순서대로 모두 보여 주고, 선택은 한 번만 받는다. 하나라도 `allow_run=False`면 [1]이 없다. [2]면 가장 심각한 규칙부터 가이드를 차례로 진행한다.

설명 프롬프트:
```
[system] 너는 Git을 처음 배우는 학생 팀을 돕는 코치다.
아래 '사실'만 근거로 설명한다. 사실에 없는 내용과 명령어는 절대 만들지 않는다.
[user] 규칙: {rule_title}
사실: {facts}
형식: 한국어 3문장, 존댓말. (1) 왜 문제인지 (2) 그대로 하면 생기는 일
(3) 아래 가이드를 따라 해 보자고만 말한다.
```

### 3-7. 명령어
| 명령 | 하는 일 |
|---|---|
| `gitcoach init` | 쉘 래퍼 설치, Ollama 연결과 모델 확인, 설정 파일 생성(`gh api user`로 member=github_login 자동 감지 후 소문자로 저장, 실패 시 수동 입력) |
| `gitcoach doctor` | Ollama·모델·git·래퍼 상태 점검, 문제 시 해결 방법 안내 |
| `gitcoach config` | 보호 브랜치, 규칙 끄기, Ollama 주소·모델 변경 |
| `gitcoach log [--today]` | 내 위반·선택 기록 보기 |
| `gitcoach explain <R01>` | 규칙 설명 미리 보기(학습용) |
| `gitcoach guide [hint\|done\|skip\|stop]` | 학습 가이드 진행 (`cli-guide-engine`, R01~R03 시나리오) |
| `gitcoach guide undo` | 되돌리기 복구 가이드. 원래 `allowed` 이벤트 참조가 필요해 `cli-event-log`(7번) 이후 별도 PR로 추가(11/9 확정) |
| `gitcoach sync` | 팀 토큰으로 Supabase Edge Function `ingest-events`를 호출해 로그를 올린다(CLI는 DB에 직접 쓰지 않음). **v0.1에서는 stub만**. 퀴즈는 포함하지 않음(퀴즈는 watcher 담당, 11/9 확정) |
| `gitcoach uninstall` | 래퍼 제거 |

**`gitcoach sync` 사양 (11/9 확정, 이남주 확인 완료)**
- 배치: 미전송 이벤트를 최대 100건씩 묶어 전송
- 응답 형식: 건별로 원본 이벤트 `id`와 함께 `inserted`(새로 저장)·`duplicate`(이미 저장됨 → CLI는 전송 성공으로 처리)·`rejected`(저장 안 됨, 틀린 필드·이유 포함) 중 하나
- 인증: `Authorization: Bearer <토큰>` 헤더. 토큰은 환경변수 `GITCOACH_SYNC_TOKEN`
- 엔드포인트 주소도 환경변수 `GITCOACH_SYNC_URL`로 받는다(`SUPABASE_URL`과 같은 방식 — config.toml은 개인 설정용이라 팀 공용 인프라 주소·토큰은 안 둔다)
- 실제 주소·토큰 발급은 11/17~18(이남주), `.env`에만 저장, 레포에는 `.env.example`만

### 3-8. PR 쪼개기 (1 PR = 1 목적, ~300줄, base는 upstream develop)
1. `feature/cli-project-skeleton` — 골격, pyproject, ci-lint·ci-test
2. `feature/cli-git-shim` — 가로채기, 터미널 판단, 통과 로직
3. `feature/cli-git-parser` — 인자 파서 + context (보호 브랜치는 `["main"]` 하드코딩, 10번에서 config로 교체)
4. `feature/cli-choice-prompt` — 2선택지 화면(다중 위반 목록), "그냥 실행하면" 문구
5. `feature/cli-rule-protected-push`(R01), `feature/cli-rule-force-push`(R02), `feature/cli-rule-secret-commit`(R03)
6. `feature/cli-guide-engine` — 가이드 상태·매칭·명령어(`hint`·`done`·`skip`·`stop`)·다중 위반 큐. **R01~R03 시나리오만** 포함(R04~06은 9번에서 해당 규칙과 함께 추가), `guide undo`는 7번 이후로 미룸(11/9 확정)
7. `feature/cli-event-log` — 스키마 v1 + SQLite + `gitcoach log [--today]` 조회 커맨드 (임지윤·이남주 리뷰)
8. `feature/cli-explain-ollama` — LLM 설명, 템플릿 폴백, 캐시
9. `feature/cli-rule-direct-commit`(R04), `feature/cli-rule-naming`(R05·R06) — 규칙 로직과 함께 각 가이드 시나리오(3-3 표)도 이 PR에서 추가(11/9 확정)
10. `feature/cli-config` — `config.py`(설정 병합, 보호 브랜치) + `gitcoach config` 커맨드. `context.py`가 하드코딩 대신 이 모듈을 읽도록 교체
11. `feature/cli-sync` — Edge Function `ingest-events` 호출로 `gitcoach sync` 실구현(stub 교체). 팀 토큰·엔드포인트는 `config.py`가 아니라 환경변수 `GITCOACH_SYNC_TOKEN`·`GITCOACH_SYNC_URL`로 받는다(3-7 사양 기준, 11/10 정정 — 이전의 "config.toml 평문 저장" 문구는 3-7의 "config.toml엔 팀 공용 인프라 값을 안 둔다"는 원칙과 충돌해서 폐기)
12. `feature/cli-init-doctor` — `gitcoach init`(쉘 래퍼 설치·Ollama 연결 확인·설정 파일 생성, member 자동 감지) + `gitcoach uninstall`(래퍼 제거) + `gitcoach doctor`(상태 점검)
13. (P2) `feature/cli-irreversible-confirm`(추가 확인), `feature/cli-severity-context`(상황별 심각도)
14. (v0.2) `feature/cli-rule-destructive`(R07)

## 4. 결정 사항 (11/5)
- [x] 스키마 v1의 `action` 값 → 6장의 6개 값으로 확정. 임지윤·이남주에게 변경 통보
- [x] 선택 화면 기본값 → Enter = [2] 가이드
- [x] 터미널이 아닌 곳에서 실행될 때 → 터미널에서만 검사. 파이프·스크립트 등 터미널이 아니면 검사 없이 그대로 실행. IDE의 Git 버튼은 래퍼를 거치지 않아 watcher가 보완
- [x] 한 명령에 위반이 여러 개일 때 → 심각한 순서대로 모두 보여 주고, [2]면 가장 심각한 규칙부터 차례로 가이드
- [x] 발표 자료 문구 → 바꾸지 않음
- [x] R07 → v0.2로 연기
- [x] 되돌릴 수 없는 명령의 추가 확인(y/N)과 상황별 심각도 조절 → P2

## 5. watcher 개발 가이드 (11/10~11/19)
GitHub API를 주기적으로 조회해 PR 밖의 행동까지 감지하고, CLI와 같은 규칙 엔진·이벤트 스키마로 결과를 낸다. watcher는 학생과 대화하지 않으므로 선택지·가이드 없이 `action: "detected"` 이벤트만 낸다. IDE 버튼·스크립트처럼 CLI가 검사하지 않은 행동도 여기서 잡힌다.

| 감지 대상 | 방법(제안) | 비고 |
|---|---|---|
| 브랜치명 규칙 위반 | 브랜치 목록 조회 후 R05 재사용 | 공용 규칙 엔진 |
| PR 대상 브랜치 오류(feature → main, R08) | 열린 PR의 base 확인 | feature는 develop으로. R08은 watcher 전용(11/9 확정, 심각도 low — R05·R06 선례 따름) |
| 커밋 메시지 규칙 위반 | PR 커밋 목록 조회 후 R06 재사용 | 공용 규칙 엔진 |
| 방치된 PR | 마지막 활동 후 **3일**(11/9 임시 결정, N 확정 전까지 watcher·대시보드·DB 뷰 공통 사용) 이상 열린 PR | `prs.last_activity_at`. R08과 무관(성격이 다른 신호라 규칙 위반 통계에서 제외, 11/9 결정). 이 감지를 `detected` 이벤트로도 남길지·rule_id는 **추후 결정**(D2, 뷰 판정만으로 대체 가능, 11/17 전) |
| 리뷰 쏠림 | 멤버별 리뷰 수 집계, 한 사람 비중이 기준 초과 시 알림 | 기준값은 팀이 정함. 방치 PR과 동일하게 규칙 위반 통계에서 제외(11/9 결정). rule_id·이벤트화 여부도 **추후 결정**(D2, 위와 동일 건) |
| PR 리뷰 원본 기록(`pr_reviews`) | `GET /repos/{owner}/{repo}/pulls/{number}/reviews` | 이남주 DB 요청(11/9, 동의 완료). 리뷰 쏠림과 같은 호출 재사용. 필드: `review_id`(네이티브 id)·`repo`·`pr_number`·`reviewer`·`status`·`submitted_at`·`commit_sha`·`html_url`(`body` 제외). CLI·DB는 합의됐으나 웹(임지윤) 확인 전이라 3인 승인 기준으로는 **미정**(D4) |
| main 직접 push, force push | Events API와 웹훅 payload 중 필요한 정보를 주는 쪽 확인 | 착수 때 먼저 검증 |

- PR 데이터 수집 시 `author`·`reviewers`는 GitHub API 값을 그대로 쓰지 않고 `lower()` 처리 후 저장한다(DB `members.github_login` 소문자 제약과 매칭, 11/9 결정).
- PR `state`는 GitHub API 값 `open`·`closed`만 받는다. "merged" 여부는 `merged_at` 존재로 판별한다(GitHub API에 `state=merged`는 없음, 11/9 확인).
- PR `title`은 항상 존재하는 값으로 보고 필수로 수집한다(방치 PR 목록 표시용, `prs.title` not null).
- 인증 토큰을 쓰고, 조회 주기는 수 분 단위로 잡아 API 한도를 피한다.
- DB 준비 전(11/17 전)에는 같은 스키마의 JSON 파일로 출력한다. `source`는 `"github"`. `pr_reviews`도 동일 — 11/14 마이그레이션 전까지는 JSON으로 제공하고, 실제 DB 적재는 11/17~ 일정에 맞춘다(11/9 확정).
- 11/17~부터 DB 적재는 **service key**로 하며, 이 키는 watcher 컨테이너에만 두고 CLI에는 전달하지 않는다. 적재 순서는 `events` 먼저 → `quizzes` 나중(퀴즈가 근거 이벤트를 가리키므로), `insert ... on conflict (id) do nothing`으로 중복 적재를 막는다(`docs/architecture/data-flow.md` 공통 규칙).
- 환경변수: `OLLAMA_URL`, `GITHUB_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GITCOACH_SYNC_URL`, `GITCOACH_SYNC_TOKEN`(3-7 `gitcoach sync` 사양). 실제 값은 `.env`에만, 레포에는 `.env.example`만.
- 일정: 11/10~12 GitHub API 조회 PoC와 push 감지 방법 검증 → 11/13~16 브랜치명·PR 대상·커밋 메시지 규칙 적용 → 11/17~19 방치 PR·리뷰 쏠림, JSON/DB 출력, Dockerfile.
- **퀴즈 생성·전송(11/24~26)은 watcher가 맡는다(11/9 확정, 남주 전달·동의).** DB에 쌓인 전체 이벤트(`source`: cli+github 모두)를 기준으로 오답·허용 이벤트를 모아 Ollama로 퀴즈를 만들고 `quizzes`에 직접 쓴다. CLI `gitcoach sync`는 이벤트 업로드만 하고 퀴즈 생성에는 관여하지 않는다. 이유: (1) 대시보드 퀴즈는 cli·github 전체 소스를 봐야 완전해짐, (2) watcher는 이미 DB·Ollama에 상시 연결되어 트리거가 안정적, (3) `sync` 스펙(3-7)은 이벤트 업로드로 고정되어 있어 퀴즈 페이로드를 얹으면 계약이 커짐.

## 6. 이벤트 스키마 v1 (내가 지키는 계약)
```json
{
  "id": "9b1f...-uuid",
  "schema_version": 1,
  "occurred_at": "2026-11-08T14:20:00+09:00",
  "source": "cli",            // "cli" | "github"
  "repo": "owner/name",
  "member": "github_login",
  "rule_id": "R01",
  "severity": "high",         // "high" | "medium" | "low"
  "action": "guided",         // 아래 표
  "command_summary": "git push origin main",
  "branch": "main",
  "pr_number": null,
  "explanation": "main은 팀 전체가 공유하는 ...",
  "llm_used": true,
  "related_event_id": null    // v1 신규
}
```

| `action` | 뜻 |
|---|---|
| `allowed` | 경고를 보고도 [1] 그냥 실행 |
| `guided` | [2] 가이드 선택, 원래 명령 취소 |
| `blocked` | 실행 불가 규칙(R03)에서 취소 |
| `guide_completed` | 가이드를 끝까지 진행 |
| `guide_stopped` | 가이드를 중간에 그만둠 |
| `detected` | watcher가 GitHub에서 발견 |

- `id`: **CLI(`source=cli`)와 watcher(`source=github`, `detected`만)가 서로 다른 방식을 쓴다(11/10 확정, 임지윤·이남주 동의).**
  - **CLI**: 이벤트를 기록하는 시점에 `uuid4()`로 1회 생성해 로컬 SQLite에 그대로 저장한다. CLI는 "명령 한 번 = 이벤트 한 번"이 원칙이라 같은 위반을 다시 저질러도 별개 사건으로 센다 — entity·action 기반 멱등 id(`uuid5`)를 쓰면 같은 커밋으로 재시도하는 경우처럼 실제로는 다른 사건인데도 같은 id가 나와 `on conflict (id) do nothing`에 조용히 사라지는 문제가 있어서 제외했다. `sync` 재전송 시에도 로컬에 저장해 둔 같은 id를 그대로 보내므로 서버 쪽 중복 방지는 그대로 유지된다. (샘플 이벤트 JSON, PR #19도 이 방식으로 교체 필요 — 임지윤 확인)
  - **watcher**: `uuid5(namespace=events.py에 고정한 UUID 리터럴, name=f"{rule_id}\x1f{repo.lower()}\x1f{entity}")`(`\x1f`는 브랜치명에 못 들어가는 구분자). watcher는 같은 사건을 주기적 조회로 반복 감지할 수 있어 이 멱등 id가 필요하다(D1 해결 — 이남주 확인 완료). 규칙별 `entity`:

    | 규칙 | entity |
    |---|---|
    | R01 (main 직접 push) | push 후 해당 브랜치의 head SHA (커밋이 여러 개인 push도 1건으로 묶기 위함, 이남주 확인) |
    | R02 (force push) | `f"{branch}:{new_head_sha}"` |
    | R05 (브랜치명 규칙 위반) | 브랜치명 |
    | R06 (커밋 메시지 규칙 위반) | 커밋 SHA |
    | R08 (PR 대상 브랜치 오류) | `f"pr:{번호}"` (이남주 확인, 포맷 통일) |

    방치 PR·리뷰 쏠림은 rule_id 자체가 D2 확정 전까지 없으므로 `entity`도 D2 확정 후 추가한다.
- `related_event_id`: `guide_completed`·`guide_stopped`가 원래 `guided` 이벤트의 id를 가리킨다. `guide undo`로 시작한 복구 가이드의 `guided` 이벤트는 원래 `allowed` 이벤트의 id를 가리킨다. 나머지는 null. **구현 메모**: CLI의 `id`는 사후에 다시 계산할 수 없으므로(uuid4라 entity로 재현 불가), 가이드를 시작할 때 원래 `guided` 이벤트의 id를 `.git/gitcoach/guide.json`(`ViolationSnapshot`)에 함께 저장해 둬야 한다(11/10 확인, 이남주 요청).
- `guide_completed`·`guide_stopped`의 `rule_id`·`severity`·`repo`·`member`·`branch`·`command_summary`는 가리키는 `guided` 이벤트와 동일한 값을 쓴다(`command_summary`도 복사 — 11/10 확정, 임지윤 확인: #19 샘플과 일치하고 타임라인에서 "가이드 완료 · git push origin main"처럼 어떤 명령에서 시작했는지 바로 보임. 가이드 연결은 `related_event_id`로 충분하므로 별도 식별 문자열은 쓰지 않음). **구현 시 주의**: 이 값들은 현재 context를 다시 읽어서 채우면 안 되고, 가이드 시작 시 저장해 둔 원래 `guided` 이벤트 값을 그대로 복사한다(예: R01 가이드 중 `git switch -c feature/...`로 브랜치가 실제로 바뀌므로, 그때 context를 다시 읽으면 `branch`가 달라져 점검 쿼리에 걸린다. `guide/state.py`에 원래 값을 들고 있어야 함, 11/9 확인).
- `guide skip`은 별도 action을 만들지 않고 `guide_stopped`로 기록한다.
- `blocked`는 R03(실행 불가 규칙) 취소에만 쓴다. 다른 규칙에서 Ctrl+C 등으로 중단하는 경우는 이벤트를 남기지 않는다.
- 다중 위반이면 위반마다 이벤트 1건씩 남긴다(같은 `command_summary`). **단, R03이 포함된 다중 위반에서 [q]로 취소한 경우는 예외** — R03의 `blocked` 1건만 남기고 나머지 위반은 기록하지 않는다(3-2 8번 참고, #12 확정).
- 위반 수 집계 시 `guided`에 `related_event_id`가 있는 것(= `guide undo` 복구 가이드)은 위반으로 세지 않는다. 대시보드·DB RPC도 같은 기준을 쓴다(11/9 확인).
- `source`는 `cli` 또는 `github`. 두 경우 모두 같은 스키마.
- v1은 11/5 확정 후 임지윤·이남주에게 통보했다. 이후 필드 추가·변경은 PR을 올리고 CLI·웹·DB 담당 3명이 모두 승인한다. ERD의 `events.action` 설명도 함께 바꾼다.
- 시크릿 값은 어떤 필드에도 넣지 않는다.
- 활용: 대시보드는 "위반 후 가이드를 끝까지 한 비율"을 학습 지표로, 퀴즈는 `allowed`·`guide_stopped`를 우선 출제 근거로 쓴다.
- 이벤트 로컬 저장 위치는 레포별이 아니라 **사용자 전역** `~/.gitcoach/events.db`(`config.toml`과 동일한 위치, 11/10 확정, 이남주 확인 — DB 쪽 영향 없음). 학생이 git 사고로 레포를 지우고 다시 clone해도 이벤트 기록이 남도록 하기 위함.
- **[참고, 11/17~19 임지윤과 정리]** R01·R05·R06은 CLI(`guided`/`allowed`)와 watcher(`detected`)가 같은 사건을 각자 따로 잡을 수 있어 위반 통계에 중복 집계될 수 있다. `source` 필터로 구분할지는 watcher 착수 때 정한다(이남주 지적).
- 11/9 v1 고정, 11/10 id 공식(CLI=uuid4/watcher=uuid5 분리)·`command_summary` 복사·저장 위치·R03 다중위반 예외 보강(임지윤·이남주 확인 완료).

## 7. 주고받는 것
| 상대 | 내가 받는 것 | 내가 주는 것 | 기한 |
|---|---|---|---|
| 장일호 | upstream develop 브랜치 보호(승인 1명+), 골격 PR 리뷰, fork PR CI 승인 | 첫 테스트가 올라오면 ci-test 추가, v0.1 이후 pr-convention에 쓸 규칙 엔진 | 11/6 |
| 임호일 | Windows PC 설치 확인(`pip install -e .` + `gitcoach init`), 패키징 결과 | 11/9 v0.1.0 인계, 설치 절차, `gitcoach doctor` 사양 | 11/9 |
| 임지윤 | 스키마 v1 변경 확인, 화면에서 필요한 필드 요청 | 스키마 v1(통보), 샘플 이벤트 JSON 20건+(더미, PR #19. 실 코드 완성 후 교체) | 11/9 |
| 이남주 | 스키마 v1 변경 반영, `ingest-events` 엔드포인트 주소와 팀 토큰(11/17~18) | 스키마 v1(통보), `gitcoach sync` 사양, `pr_reviews` 소스 필드 정의(11/9, 동의 완료). **추후 결정**: data-flow ④⑤ "이남주 공동 담당"의 실제 범위(DB 적재 코드 공동작성 vs 스키마/리뷰 지원) — 이남주 확인 예정 | 11/9 |
| 모두 | 가이드 문구·단계가 입문자에게 이해되는지 짧은 피드백 | — | 11/9 |

## 8. 완료 기준
**CLI v0.1 (11/9)**
- [ ] `git push origin main`에서 두 선택지가 뜨고, [2]를 고르면 PR로 올리는 3단계 가이드가 진행된다
- [ ] `git push origin develop`(fork 동기화)은 경고 없이 통과한다
- [ ] `git push --force`에서 선택지가 뜨고, [1]을 고르면 실행 후 "되돌리려면" 안내가 나온다
- [ ] `git push --force origin main`처럼 여러 규칙에 걸리면 심각한 순서대로 모두 나오고, [2]면 차례로 가이드된다
- [ ] 스테이징된 `.env`는 [1]이 없고, 비밀 값은 화면과 로그에 나오지 않는다
- [ ] `git checkout -b MyBranch` 같은 위반 브랜치명에 경고와 제안 이름이 나온다
- [ ] `git commit -m "fix"`에 경고가 나온다
- [ ] 스크립트에서 실행한 git 명령은 검사 없이 그대로 실행된다
- [ ] 가이드 진행 중 터미널을 닫았다 열어도 이어지고, `guide hint/done/stop`이 동작한다
- [ ] Ollama를 꺼도 템플릿 설명으로 동작한다
- [ ] 모든 선택(allowed·guided·blocked·guide_completed·guide_stopped)이 로컬 이벤트 로그에 남는다
- [ ] 규칙별 단위 테스트가 있고 CI가 통과한다
- [ ] 팀원 PC 2대 이상(Windows 포함)에서 설치·동작 확인

**watcher (11/19)**
- [ ] 우리 레포의 위반(브랜치명, PR 대상, 커밋 메시지, 방치 PR)이 `detected` 이벤트로 출력된다
- [ ] main 직접 push·force push 감지 방법이 검증되어 문서에 적혀 있다
- [ ] Dockerfile이 있고 `docker compose up`에서 ollama와 통신한다
- [ ] 토큰·키가 레포에 없고 `.env.example`만 있다

## 부록. 팀 공통 (요약)
- 도구: Ollama(gemma4:e2b), Supabase, Vercel, Docker Compose(컨테이너 3종+), GitHub Actions(워크플로 5개+)
- 브랜치: `main`(배포, `release`에서만 병합, 병합 시 태그) / `develop`(통합, 승인 1명+) / `feature/<영역>-<설명>` / `fix/<영역>-<설명>` / `docs/<설명>`(문서 전용 작업, 11/9 피드백 반영) / `release/vX.Y`(마일스톤 완료 시 팀장이 `develop`에서 분기 → 버전 문서화·테스트 → `main` 병합). hotfix는 사용하지 않음(11/5 결정 — 실제 배포 없이 개발 과정만 다루는 프로젝트라 긴급 운영 수정 시나리오가 없음)
- 커밋·PR 세부 규칙은 `CLAUDE.md`를 따른다.
- 오픈소스 표기: Ollama·Supabase는 오픈소스, Vercel은 호스팅 서비스로 별도 표기

**전체 마일스톤**
| 날짜 | 목표 |
|---|---|
| 11/9 | CLI v0.1.0, 스키마 v1, 샘플 JSON 전달 |
| 11/13 | 중간 발표 (2선택지·가이드 데모) |
| 11/16 | 웹이 mock 데이터로 전 화면 동작, Vercel 프리뷰 |
| 11/20 | DB 연동 완료, 웹이 실제 데이터 표시 |
| 11/26 | Compose 통합, Actions 5개, 퀴즈 생성, main 첫 병합 |
| 12/4 | 테스트·발표 완료 |
