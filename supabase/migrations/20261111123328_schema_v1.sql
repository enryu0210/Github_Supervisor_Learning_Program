-- schema v1 (ERD v1, 이벤트 스키마 v1)
-- 범위: 테이블·제약·인덱스 + 모든 테이블 RLS enable.
--       RLS 정책·뷰·RPC는 별도 마이그레이션에서 추가한다. 정책이 없는 동안 anon·authenticated는 아무것도 읽지 못한다.
-- 기준: docs/db/ERD.md, docs/guide/01_cli.md 5절(watcher 수집 필드)·6절(이벤트 JSON 계약)
-- 이 버전(20261111123328)은 개발 DB에 먼저 적용해 시험했다. 이후 변경은 이 파일을 고치지 않고 새 마이그레이션으로 추가한다.

-- ---------- 팀·멤버·레포 (seed로 등록) ----------
create table public.teams (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  created_at  timestamptz not null default now()
);

create table public.members (
  id            uuid primary key default gen_random_uuid(),
  team_id       uuid not null references public.teams (id) on delete cascade,
  -- GitHub login, 소문자. 빈 값 금지 (events.member와 같은 규칙)
  github_login  text not null unique check (github_login ~ '^[a-z0-9][a-z0-9-]*$'),
  display_name  text,
  -- 첫 GitHub 로그인 때 github_login으로 매칭해 채운다 (RLS 판정용)
  auth_user_id  uuid unique references auth.users (id) on delete set null,
  created_at    timestamptz not null default now()
);

create table public.repos (
  id          uuid primary key default gen_random_uuid(),
  team_id     uuid not null references public.teams (id) on delete cascade,
  full_name   text not null unique check (full_name ~ '^[^/\s]+/[^/\s]+$'),  -- owner/name
  created_at  timestamptz not null default now()
);

-- ---------- PR (watcher가 (repo_id, number) 기준 upsert) ----------
create table public.prs (
  id                uuid primary key default gen_random_uuid(),
  repo_id           uuid not null references public.repos (id) on delete cascade,
  number            int  not null,
  title             text not null,
  author            text not null check (author = lower(author)),             -- github_login, 소문자
  state             text not null check (state in ('open', 'closed')),       -- GitHub API 값. 머지 여부는 merged_at으로 판별
  opened_at         timestamptz not null,
  merged_at         timestamptz,
  reviewers         text[] not null default '{}'                              -- 요청된 리뷰어 github_login, 소문자
                    check (reviewers::text = lower(reviewers::text)),
  last_activity_at  timestamptz not null,
  unique (repo_id, number),
  -- 머지된 PR은 GitHub API에서 항상 state = 'closed'
  constraint prs_merged_closed_chk check (merged_at is null or state = 'closed')
);

-- ---------- PR 리뷰 (watcher가 review_id 기준 upsert, #44) ----------
-- 출처: GET /repos/{owner}/{repo}/pulls/{number}/reviews (body 제외)
-- watcher는 JSON의 repo·pr_number로 prs.id를 찾아 pr_id에 넣는다 → prs를 먼저 적재한다.
-- PENDING(제출 전 리뷰)은 watcher가 보내지 않는다 → submitted_at은 항상 값이 있다.
create table public.pr_reviews (
  review_id     bigint primary key,                                    -- GitHub 리뷰 id (int 범위를 넘는다)
  pr_id         uuid not null references public.prs (id) on delete cascade,
  reviewer      text not null check (reviewer = lower(reviewer)),      -- github_login, 소문자
  status        text not null
                check (status in ('APPROVED', 'CHANGES_REQUESTED', 'COMMENTED', 'DISMISSED')),  -- API 값 그대로
  submitted_at  timestamptz not null,
  commit_sha    text not null check (commit_sha ~ '^[0-9a-f]{40}$'),
  html_url      text not null
);
create index pr_reviews_pr_idx            on public.pr_reviews (pr_id);
create index pr_reviews_reviewer_time_idx on public.pr_reviews (reviewer, submitted_at desc);

-- ---------- 이벤트 (모든 통계의 원천, insert ... on conflict (id) do nothing) ----------
-- repo·member는 repos.full_name·members.github_login과 FK 없이 문자열로 매칭한다.
create table public.events (
  id                uuid primary key,              -- 보내는 쪽이 만든 UUID (CLI uuid4, watcher detected uuid5). DB에서 생성하지 않는다
  schema_version    int  not null default 1 check (schema_version = 1),
  occurred_at       timestamptz not null,
  source            text not null check (source in ('cli', 'github')),
  repo              text not null,                 -- owner/name
  member            text not null check (member ~ '^[a-z0-9][a-z0-9-]*$'),  -- github_login, 소문자, 빈 값 금지
  rule_id           text not null,
  severity          text not null check (severity in ('high', 'medium', 'low')),
  action            text not null check (action in (
                      'allowed', 'guided', 'blocked',
                      'guide_completed', 'guide_stopped', 'detected')),
  command_summary   text,
  branch            text,
  pr_number         int,
  explanation       text,
  llm_used          boolean not null default false,
  -- FK 없음: sync 순서가 바뀌어도 적재되게 한다
  --   guide_completed·guide_stopped → 원래 guided (필수), guided(복구 가이드) → 원래 allowed (선택)
  related_event_id  uuid,
  created_at        timestamptz not null default now(),

  -- detected는 watcher(github)만, 나머지는 CLI만
  constraint events_source_action_chk check (
    (source = 'github' and action = 'detected')
    or (source = 'cli' and action <> 'detected')
  ),
  -- 가이드 결과는 반드시, guided는 복구 가이드일 때만, 나머지는 related_event_id를 갖지 않는다
  constraint events_related_chk check (
    case
      when action in ('guide_completed', 'guide_stopped') then related_event_id is not null
      when action = 'guided' then true
      else related_event_id is null
    end
  ),
  -- allowed(그냥 실행)는 LLM 설명을 만들지 않는다
  constraint events_allowed_no_llm_chk check (
    action <> 'allowed' or (explanation is null and llm_used = false)
  )
);
create index events_repo_time_idx    on public.events (repo, occurred_at desc);
create index events_member_time_idx  on public.events (member, occurred_at desc);
create index events_rule_action_idx  on public.events (rule_id, action);
create index events_related_idx      on public.events (related_event_id) where related_event_id is not null;

-- ---------- 퀴즈 (watcher가 Ollama로 생성해 직접 저장, 웹은 표시만) ----------
create table public.quizzes (
  id               uuid primary key,              -- watcher가 만든 UUID (중복 방지 방식은 퀴즈 작업 때 확정)
  member_id        uuid not null references public.members (id) on delete cascade,
  rule_id          text not null,
  source_event_id  uuid references public.events (id) on delete set null,
  question         text not null,
  choices          jsonb not null,                -- 문자열 배열
  answer_index     int  not null,                 -- 0부터 시작
  explanation      text,
  created_at       timestamptz not null default now(),
  constraint quizzes_choices_chk check (
    jsonb_typeof(choices) = 'array'
    and jsonb_array_length(choices) >= 2
    and answer_index >= 0
    and answer_index < jsonb_array_length(choices)
  )
);
create index quizzes_member_idx on public.quizzes (member_id, created_at desc);

-- v0.1에서는 웹이 풀이를 저장하지 않는다(테이블만 둔다)
create table public.quiz_attempts (
  id              uuid primary key default gen_random_uuid(),
  quiz_id         uuid not null references public.quizzes (id) on delete cascade,
  member_id       uuid not null references public.members (id) on delete cascade,
  selected_index  int  not null check (selected_index >= 0),
  is_correct      boolean not null,
  attempted_at    timestamptz not null default now()
);
create index quiz_attempts_member_idx on public.quiz_attempts (member_id, attempted_at desc);

-- ---------- RLS: 모든 테이블에서 켠다 (정책은 별도 마이그레이션) ----------
alter table public.teams          enable row level security;
alter table public.members        enable row level security;
alter table public.repos          enable row level security;
alter table public.prs            enable row level security;
alter table public.pr_reviews     enable row level security;
alter table public.events         enable row level security;
alter table public.quizzes        enable row level security;
alter table public.quiz_attempts  enable row level security;
