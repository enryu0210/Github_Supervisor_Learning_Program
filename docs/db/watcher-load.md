# watcher → DB 적재 가이드

> 버전: v1 (2026-11-19) · 담당: 이남주(DB) · 받는 쪽: watcher 적재 코드(권아현)
> 기준: [`docs/architecture/data-flow.md`](../architecture/data-flow.md) 2절 공통 규칙, [`docs/guide/01_cli.md`](../guide/01_cli.md) 5절(watcher)·6절(이벤트 스키마 v1), `supabase/migrations/`의 제약, [ERD](ERD.md).
> 역할 분담은 #45(적재 코드 = watcher 담당, 테이블·적재 예시·개발 DB 시험·적재 PR 리뷰 = DB 담당), 적재 방식은 #55에서 정했다.
>
> 이 문서와 마이그레이션이 다르면 마이그레이션이 실제 상태다. CLI 이벤트 적재(`gitcoach sync` → `ingest-events`)는 [`supabase/functions/ingest-events/README.md`](../../supabase/functions/ingest-events/README.md)를 본다.

## 1. 한눈에

| 테이블 | 충돌 기준 | 방식 | supabase-py |
|---|---|---|---|
| `events` (`detected`) | `id` | 무시 (`on conflict do nothing`) | `upsert(rows, on_conflict="id", ignore_duplicates=True)` |
| `prs` | `(repo_id, number)` | 갱신 (upsert) | `upsert(rows, on_conflict="repo_id,number")` |
| `pr_reviews` | `review_id` | 갱신 (upsert) | `upsert(rows, on_conflict="review_id")` |
| `quizzes` (11/24~) | `id` | 무시 | `upsert(rows, on_conflict="id", ignore_duplicates=True)` |

- 접속: `SUPABASE_URL`·`SUPABASE_SERVICE_KEY`(watcher 컨테이너 환경변수)로 supabase-py 클라이언트를 만든다. service key는 RLS를 우회하므로 watcher 안에만 둔다.
- 순서: **`prs` → `pr_reviews`**(`pr_reviews.pr_id`가 `prs.id`를 가리킴). `events`는 다른 테이블과 FK가 없어 순서가 상관없다.
- `teams`·`repos`·`members`는 seed(`supabase/seed.sql`)로 미리 넣는다. watcher는 **읽기만** 한다.

## 2. 시작할 때 한 번: `repos.id` 찾기

```python
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

res = sb.table("repos").select("id").eq("full_name", config.repo).limit(1).execute()
if not res.data:
    raise WatcherConfigError(f"repos에 {config.repo}가 없어요. DB 담당에게 seed 등록을 요청하세요.")
repo_id = res.data[0]["id"]
```

- `config.repo`는 `GITHUB_REPO`를 `lower()`한 값이다. `repos.full_name`도 소문자만 들어간다(`repos_full_name_lower_chk`).
- 없으면 매 주기 조용히 실패하지 않도록 시작할 때 멈춘다.

## 3. `events` — `detected` 이벤트

```python
from dataclasses import asdict

rows = [asdict(e) for e in violations]          # gitcoach.models.Event 15개 필드 = events 컬럼
sb.table("events").upsert(rows, on_conflict="id", ignore_duplicates=True).execute()
```

DB가 거절하는 값 (하나라도 있으면 **그 배치 전체가 실패**한다):

| 필드 | 규칙 | 비고 |
|---|---|---|
| `id` | 반드시 보낸다 | DB가 만들지 않는다. watcher는 6절 uuid5 공식 |
| `source`·`action` | `github` + `detected` 조합만 | `events_source_action_chk` |
| `repo` | 소문자 | `events_repo_lower_chk` |
| `member` | `^[a-z0-9][a-z0-9-]*$` | 빈 값 거절. **봇 계정(`github-actions[bot]` 등)도 `[`·`]` 때문에 거절** → 배치에 넣기 전에 걸러야 한다 |
| `severity` | `high`·`medium`·`low` | |
| `related_event_id` | `null` | `detected`는 가지지 않는다 |
| `created_at` | 보내지 않는다 | DB가 채운다 (`Event`에는 이 필드가 없다) |

- **`occurred_at`은 처음 적재된 값이 영구히 남는다.** 같은 위반을 다시 보내도 `do nothing`이라 바뀌지 않는다. 지금 `make_detected_event`는 감지한 순간의 현재 시각을 넣으므로, watcher를 늦게 켜거나 적재를 늦게 시작하면 그동안 쌓인 위반이 모두 첫 적재 날짜에 몰린다(대시보드 일별 추이가 틀어짐).
  **제안**: GitHub에 사건 시각이 있는 규칙은 그 값을 넣는다 — R01·R02 = PushEvent `created_at`, R08 = PR `created_at`, R06 = 커밋 `committer.date`. R05(브랜치명)는 사건 시각을 얻기 어려워 감지 시각 그대로 둔다. 6절에는 `occurred_at`의 의미가 정의되어 있지 않아 이 PR에서 함께 정한다.
- `member = "unknown"`(작성자를 못 찾은 R05)은 DB 제약을 통과한다. 화면의 멤버 목록·멤버별 통계에서는 DB 뷰가 제외한다.

## 4. `prs` — upsert

```python
def pr_row(pr: dict) -> dict:
    return {
        "repo_id": repo_id,
        "number": pr["number"],
        "title": pr["title"],
        "author": pr["user"]["login"].lower(),
        "state": pr["state"],                    # 'open' | 'closed' (머지된 PR도 closed)
        "opened_at": pr["created_at"],
        "merged_at": pr["merged_at"],            # 머지 전이면 None — 키는 항상 넣는다
        "reviewers": [r["login"].lower() for r in pr["requested_reviewers"]],
        "last_activity_at": pr["updated_at"],
    }

# GET /repos/{owner}/{repo}/pulls?state=all&sort=updated&direction=desc&per_page=100 (페이지를 따라간다)
res = sb.table("prs").upsert([pr_row(pr) for pr in pulls], on_conflict="repo_id,number").execute()
pr_ids = {row["number"]: row["id"] for row in res.data}      # pr_reviews에서 쓴다
```

- **`state=all`로 닫힌·머지된 PR까지 보내야 한다.** `state=open`(#101의 `list_open_pulls`)만 쓰면 PR이 닫혀도 DB에는 `open`으로 남는다 → 방치 PR로 잘못 잡히고 `prs_merged`가 0이 된다. 2026-11-18 기준 우리 레포 PR 60건 중 열린 것은 1건이다.
- 처음 한 번은 전체 페이지를 적재한다. 이후에는 `sort=updated&direction=desc`로 받아 마지막 적재 이후 바뀐 PR까지만 보내도 된다.
- `id`는 보내지 않는다. 처음 들어갈 때 DB가 만들고, 이후 upsert에서는 그대로 유지된다.
- **한 배치의 모든 행이 같은 키를 가져야 한다.** 행마다 키가 다르면 빠진 키가 `null`로 들어가 기존 값을 덮는다.
- `merged_at`이 있으면 `state`는 `closed`여야 한다(`prs_merged_closed_chk`). GitHub API 값 그대로면 항상 맞다.
- `reviewers`는 "요청된 리뷰어"다. 리뷰를 제출하면 GitHub 목록에서 빠지므로, 실제 리뷰 기록은 `pr_reviews`로 센다.
- `last_activity_at`은 방치 PR 판정(3일, `01_cli.md` 5절) 기준이다.

## 5. `pr_reviews` — upsert (`prs` 다음)

```python
# GET /repos/{owner}/{repo}/pulls/{number}/reviews?per_page=100
rows = [
    {
        "review_id": rv["id"],                   # GitHub id, int 범위를 넘는다 (DB bigint)
        "pr_id": pr_ids[number],
        "reviewer": rv["user"]["login"].lower(),
        "status": rv["state"],                   # APPROVED | CHANGES_REQUESTED | COMMENTED | DISMISSED
        "submitted_at": rv["submitted_at"],
        "commit_sha": rv["commit_id"],           # 40자 소문자 hex
        "html_url": rv["html_url"],
    }
    for number, rv in reviews
    if rv["state"] != "PENDING" and rv.get("user") and rv.get("commit_id")
]
sb.table("pr_reviews").upsert(rows, on_conflict="review_id").execute()
```

- `PENDING`(제출 전 리뷰)은 보내지 않는다(#44). `submitted_at`이 없어 DB가 거절한다.
- 삭제된 계정(`user`가 `null`)이나 사라진 커밋(`commit_id`가 `null`)의 리뷰는 DB 제약(not null)에 걸리므로 빼고 로그만 남긴다.
- dismiss되면 같은 `review_id`의 `status`가 `DISMISSED`로 바뀐다 → upsert라 갱신된다.
- 리뷰 `body`는 받지 않는다.
- `pr_ids`에 없는 PR(이번 배치에서 `prs`를 적재하지 않은 PR)의 리뷰는 `prs`에서 `id`를 조회해 채운다.

## 6. `quizzes` (11/24~)

- `id`는 watcher가 만들고 `on conflict (id) do nothing`으로 넣는다.
- `member_id`는 `members`에서 `github_login`으로 찾는다. `source_event_id`는 DB `events`에 이미 있는 이벤트만 가리킨다.
- `choices`는 문자열 2개 이상인 JSON 배열, `answer_index`는 0부터 시작하고 배열 범위 안이어야 한다(`quizzes_choices_chk`).
- 중복 방지 방식, 미등록 멤버 처리, 출제 근거 범위는 퀴즈 작업(11/24)에서 정한다.

## 7. 실패 처리

- 제약 위반이 한 행이라도 있으면 그 `upsert` 호출 전체가 실패한다. 위 표의 값은 **보내기 전에** 걸러 낸다.
- 실패해도 다음 폴링에서 같은 행을 다시 보내면 된다. `events`는 `do nothing`, `prs`·`pr_reviews`는 upsert라 몇 번을 보내도 결과가 같다.
- `prs` 적재가 실패하면 그 주기의 `pr_reviews`는 건너뛴다(`pr_id`를 얻을 수 없음).
- service key는 로그·예외 메시지·이벤트 필드 어디에도 남기지 않는다.

## 8. 적재 확인 쿼리

개발 DB의 SQL 편집기에서 **읽기만** 한다.

```sql
-- watcher 이벤트: 규칙별 건수와 가장 이른·늦은 발생 시각
select rule_id, count(*), min(occurred_at), max(occurred_at)
from events
where source = 'github' and repo = 'enryu0210/github_supervisor_learning_program'
group by rule_id order by rule_id;

-- PR 상태 분포: closed가 0이면 닫힌 PR을 보내지 않는 것이다
select p.state, (p.merged_at is not null) as merged, count(*)
from prs p join repos r on r.id = p.repo_id
where r.full_name = 'enryu0210/github_supervisor_learning_program'
group by 1, 2 order by 1, 2;

-- 방치 PR 후보 (3일)
select p.number, p.title, p.last_activity_at
from prs p join repos r on r.id = p.repo_id
where r.full_name = 'enryu0210/github_supervisor_learning_program'
  and p.state = 'open' and p.last_activity_at < now() - interval '3 days'
order by p.last_activity_at;

-- 리뷰 상태 분포
select rv.status, count(*)
from pr_reviews rv join prs p on p.id = rv.pr_id join repos r on r.id = p.repo_id
where r.full_name = 'enryu0210/github_supervisor_learning_program'
group by 1 order by 1;
```
