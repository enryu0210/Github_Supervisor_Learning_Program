# 데이터 흐름 (Data Flow) v0

- 작성: 장일호(PM) · 2026-11-09 · 상태: **초안 (팀 확인 전)**
- 원본: `data-flow.pdf` (이 파일은 Claude Code가 읽을 수 있게 옮긴 텍스트판)
- 기준 문서: `docs/guide/01_cli.md` 6절(이벤트 스키마 v1) · `docs/db/ERD.md`(#12) · `dashboard/lib/data`(#11)
- 범위: 데이터가 **어디서 생겨서 → 어디에 저장되고 → 누가 읽는지**만 다룬다. 컬럼 정의는 ERD, 필드 정의는 스키마 v1이 기준이며 여기서 다시 정의하지 않는다.

## 1. 한 장 요약

### 구성 요소
| 위치 | 구성 요소 | 설명 |
|---|---|---|
| 학생 PC | `gitcoach` CLI | git 래퍼 |
| 학생 PC | 로컬 SQLite | `~/.gitcoach` |
| 외부 | GitHub API | 우리 팀 레포 |
| Docker Compose | `ollama` | `gemma4:e2b` · 포트 `11434` |
| Docker Compose | `watcher` | 감지 · 퀴즈 생성 |
| Docker Compose | `dashboard` | Next.js · `lib/data` |
| Supabase (클라우드) | Edge Function `ingest-events` | CLI 업로드 수신 |
| Supabase (클라우드) | DB 테이블 | `events` · `prs` · `quizzes` … |
| Supabase (클라우드) | 조회 뷰 / RPC | `v_rule_stats` … |

### 흐름도
실선(`-->`) = 데이터 저장·전달 · 점선(`-.->`) = 설명 요청(저장 없음) · 번호는 2절 표의 흐름 번호

```mermaid
flowchart LR
  subgraph PC[학생 PC]
    CLI[gitcoach CLI<br/>git 래퍼]
    SQLITE[(로컬 SQLite<br/>~/.gitcoach)]
  end
  GH[GitHub API<br/>우리 팀 레포]
  subgraph COMPOSE[Docker Compose]
    OLLAMA[ollama<br/>gemma4:e2b :11434]
    WATCHER[watcher<br/>감지·퀴즈 생성]
    DASH[dashboard<br/>Next.js lib/data]
  end
  subgraph SB[Supabase 클라우드]
    EDGE[Edge Function<br/>ingest-events]
    DB[(DB 테이블<br/>events·prs·quizzes…)]
    VIEW[조회 뷰 / RPC<br/>v_rule_stats…]
  end

  CLI -->|① 위반 기록| SQLITE
  CLI -.->|설명 요청 [2] 선택 시| OLLAMA
  CLI -->|② gitcoach sync · 팀 토큰| EDGE
  EDGE --> DB
  GH -->|③ 주기 조회| WATCHER
  WATCHER -->|④ detected·prs · service key| DB
  WATCHER -->|⑤ 퀴즈 생성| OLLAMA
  WATCHER -->|⑤ quizzes · service key| DB
  DB --> VIEW
  VIEW -->|⑥ anon key + 로그인·RLS| DASH
```

## 2. 흐름별 계약

| # | 흐름 | 보내는 쪽 → 받는 쪽 | 데이터 | 인증 | 담당 | 시작 |
|---|---|---|---|---|---|---|
| ① | 위반 기록 | CLI → 로컬 SQLite | `events` (스키마 v1, `source=cli`) | 없음 (로컬) | 권아현 | 완료 (v0.1) |
| ② | 업로드 | CLI `sync` → `ingest-events` → `events` | ①과 같은 이벤트 묶음 | 팀 토큰 (학생 PC에 서버 키 없음) | 권아현 · 이남주 | 11/17~18 |
| ③ | 감지 | GitHub API → watcher | 브랜치 · PR · 커밋 · 리뷰 | `GITHUB_TOKEN` | 권아현 | 11/10 |
| ④ | 감지 결과 적재 | watcher → `events`, `prs` | `detected` 이벤트, PR 상태 | service key | 권아현 · 이남주 | 11/17 (전까지 JSON 파일) |
| ⑤ | 퀴즈 | watcher → ollama → `quizzes` | `allowed` · `guide_stopped` 기반 문제 | service key | 권아현 · 이남주 | 11/24 |
| ⑥ | 화면 | 뷰/RPC → dashboard `lib/data` | 집계 · 타임라인 · 방치 PR · 퀴즈 | anon key + 로그인 토큰, RLS | 임지윤 · 이남주 | 11/19~20 (전까지 mock) |

### 공통 규칙
- 모든 적재는 `insert … on conflict (id) do nothing` → 같은 것을 다시 보내도 한 번만 저장된다.
- 적재 순서: **`events` 먼저, `quizzes` 나중** (퀴즈가 출제 근거 이벤트를 가리키기 때문).
- 키 위치: service key = **watcher 컨테이너만** · 팀 토큰 = **CLI 설정** · anon key = **dashboard**.
- 시크릿 값은 어떤 흐름에도 싣지 않는다.
- 시간은 오프셋 포함 ISO 8601로 저장. 화면의 "이번 주"·일별 집계는 KST(`Asia/Seoul`) 기준.

## 3. 단계별 전환 (DB 준비 전 → 후)

| 기간 | CLI | watcher | dashboard |
|---|---|---|---|
| ~11/16 | 로컬 SQLite, `samples/*.json` 20건+ 전달 | JSON 파일 출력 (같은 스키마) | `mockSource` (samples 읽음) |
| 11/17~20 | `gitcoach sync` → Edge Function | Supabase 직접 적재 | `supabaseSource`로 교체 |
| 11/24~ | — | 퀴즈 생성 추가 | `/quiz` 표시 |

화면은 `lib/data`의 `DataSource`만 호출하므로 11/17 전환 때 화면 코드는 바뀌지 않는다. 환경변수 하나(`NEXT_PUBLIC_DATA_SOURCE`)로 바꾼다.

## 4. 결정이 필요한 것

> **긴급: D1은 watcher 착수(11/10) 전에 정해야 재작업이 없다.**

| # | 쟁점 | 제안 | 결정할 사람 |
|---|---|---|---|
| D1 | **watcher 이벤트 중복** — watcher는 몇 분마다 같은 위반을 다시 본다. id를 매번 새 랜덤 UUID로 만들면 같은 위반이 조회할 때마다 쌓여 통계가 틀어진다. | `detected`의 id를 항상 같은 값이 나오는 UUID로 생성: `uuid5(repo + rule_id + 대상)` (대상 = 브랜치명·PR 번호·커밋 SHA). `on conflict`가 중복을 막는다. | 권아현 · 이남주 |
| D2 | **방치 PR을 두 군데서 계산** — watcher의 `detected` 이벤트와 DB 뷰 `v_stale_prs` | 방치 여부는 뷰 하나(`prs.last_activity_at`)로 판정. 이벤트로도 남길지는 위반 통계에 넣을지로 결정 | 팀 |
| D3 | **방치 기준 N일** | 임시 3일. `01_cli.md` 5절 한 곳에 적고 watcher·뷰가 따름 | 팀 |
| D4 | **리뷰 기록** — `prs.reviewers`(요청 목록)로는 "누가 언제 리뷰했는지" 셀 수 없음 | `pr_reviews` 테이블 추가 (11/14 마이그레이션 전) | CLI · 웹 · DB 3명 |
| D5 | **`/quiz` 답 제출을 DB에 저장하나** (#14) | v0.1은 저장 안 함(읽기 전용). 저장하면 웹 → DB 쓰기 흐름과 RLS 정책이 새로 생김 | 임지윤 · 이남주 |
| D6 | **로그인 사용자 ↔ `members` 연결** | 멤버를 미리 등록해 두고, 첫 로그인 때 `github_login`(소문자)으로 매칭해 `auth_user_id`를 채움 | 이남주 |
| D7 | **CLI가 쓰는 ollama 위치** — 학생 PC마다 Compose를 띄우나, 각자 Ollama를 설치하나 | 설치 가이드에 하나로 고정. 없어도 템플릿 설명으로 동작(기능 영향 없음) | 권아현 · 임호일 |

## 5. 하지 않는 것
- dashboard는 Supabase 테이블을 직접 읽지 않는다 (**뷰/RPC만**).
- CLI는 DB에 직접 쓰지 않는다 (**Edge Function 경유**).
- `pr-convention` 워크플로는 PR 검사만 하고 이벤트를 적재하지 않는다 (같은 위반은 watcher가 `detected`로 남김).

## 부록. Claude Code 참고 메모 (원본에 없음, 변환 시 추가)
- 이 문서는 **초안**이다. 여기 적힌 결정(D1~D7)을 구현하기 전에 확정 여부를 먼저 확인한다.
- ERD v0의 `events.action`은 아직 `blocked, ran, warned`로 되어 있고 `related_event_id`가 없다. 스키마 v1(`allowed|guided|blocked|guide_completed|guide_stopped|detected`, `related_event_id` 추가)이 기준이며, ERD 쪽 갱신이 필요하다.
