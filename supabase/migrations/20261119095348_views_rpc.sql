-- 대시보드 조회용 뷰·RPC
-- 기준: dashboard/lib/data/index.ts (DataSource 반환 타입), #94 (함수별 대응·필터 인자·멤버 범위·severity),
--       docs/guide/01_cli.md 6절 (위반 집계 기준)
--
-- - 웹은 테이블을 직접 읽지 않고 이 뷰·RPC만 읽는다.
-- - 뷰는 security_invoker, RPC는 security invoker → 로그인한 사용자 권한(RLS)으로 실행된다.
--   같은 팀 데이터만, 퀴즈·풀이는 본인 것만 나온다.
-- - 컬럼 이름·타입은 웹 타입과 같게 맞춘다. 건수는 integer, 비율은 double precision.
-- - 위반 수 = allowed·guided·blocked·detected, 복구 가이드(guided + related_event_id 있음)는 뺀다(웹 isViolation()과 같음).
--   방치 PR·리뷰 쏠림 rule_id는 아직 정해지지 않아 빼는 조건이 없다(정해지면 private.is_violation에 추가).
-- - 날짜는 KST(Asia/Seoul) 기준.
--
-- 되돌리기: drop function public.get_events(...), public.get_rule_stats(...), public.get_guide_stats(...),
--           public.get_daily_trend(...), public.get_member_activity(...);
--           drop view public.v_quiz_attempts, public.v_quizzes, public.v_stale_prs, public.v_members, public.v_events;
--           drop function private.filter_events(...), private.is_violation(text, uuid);

-- ---------- 공통: 위반 판정·필터 (private, API에 노출되지 않음) ----------
create function private.is_violation(p_action text, p_related_event_id uuid)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select p_action in ('allowed', 'guided', 'blocked', 'detected')
     and not (p_action = 'guided' and p_related_event_id is not null);
$$;

-- 웹 EventFilter와 같은 규칙. null·빈 배열·빈 문자열 = 전체. p_from 포함, p_to 미포함.
-- p_query: command_summary·branch·"#PR번호"에 들어 있는지(대소문자 무시, 와일드카드 없음)
create function private.filter_events(
  p_from        timestamptz,
  p_to          timestamptz,
  p_members     text[],
  p_rule_ids    text[],
  p_sources     text[],
  p_severities  text[],
  p_actions     text[],
  p_repo        text,
  p_query       text
)
returns setof public.events
language sql
stable
security invoker
set search_path = ''
as $$
  select e.*
    from public.events e
   where (p_from is null or e.occurred_at >= p_from)
     and (p_to   is null or e.occurred_at <  p_to)
     and (coalesce(cardinality(p_members), 0)    = 0 or e.member   = any (p_members))
     and (coalesce(cardinality(p_rule_ids), 0)   = 0 or e.rule_id  = any (p_rule_ids))
     and (coalesce(cardinality(p_sources), 0)    = 0 or e.source   = any (p_sources))
     and (coalesce(cardinality(p_severities), 0) = 0 or e.severity = any (p_severities))
     and (coalesce(cardinality(p_actions), 0)    = 0 or e.action   = any (p_actions))
     and (coalesce(p_repo, '') = '' or e.repo = p_repo)
     and (coalesce(btrim(p_query), '') = ''
          or strpos(lower(e.command_summary), lower(btrim(p_query))) > 0
          or strpos(lower(e.branch), lower(btrim(p_query))) > 0
          or strpos('#' || e.pr_number::text, lower(btrim(p_query))) > 0);
$$;

revoke execute on function private.is_violation(text, uuid),
  private.filter_events(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text) from public;
grant execute on function private.is_violation(text, uuid),
  private.filter_events(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text) to authenticated;

-- ---------- 뷰 ----------
-- GitCoachEvent 15개 필드 (created_at = DB 적재 시각은 뺀다). getRelatedEvents가 related_event_id로 읽는다.
create view public.v_events with (security_invoker = true) as
select e.id, e.schema_version, e.occurred_at, e.source, e.repo, e.member, e.rule_id, e.severity,
       e.action, e.command_summary, e.branch, e.pr_number, e.explanation, e.llm_used,
       e.related_event_id
  from public.events e;

-- 등록 멤버 ∪ 이벤트·PR·리뷰에 나온 login (#94 3번). 활동이 없는 등록 멤버도 나온다.
-- 'unknown'(작성자를 못 찾은 watcher 이벤트)과 봇 계정은 사람이 아니므로 뺀다.
create view public.v_members with (security_invoker = true) as
select s.login as member
  from (
    select m.github_login from public.members m
    union select e.member from public.events e
    union select p.author from public.prs p
    union select r.reviewer from public.pr_reviews r
  ) as s (login)
 where s.login <> 'unknown'
   and s.login not like '%[bot]'
 order by s.login;

-- 방치 PR: 열려 있고 마지막 활동 후 3일 이상 (data-flow D2·D3). 기준을 바꾸면 watcher·대시보드도 같이 고친다.
create view public.v_stale_prs with (security_invoker = true) as
select r.full_name as repo,
       p.number    as pr_number,
       p.title,
       p.author,
       p.opened_at,
       p.last_activity_at,
       floor(extract(epoch from (now() - p.last_activity_at)) / 86400)::int as idle_days,
       'https://github.com/' || r.full_name || '/pull/' || p.number as url
  from public.prs p
  join public.repos r on r.id = p.repo_id
 where p.state = 'open'
   and p.last_activity_at <= now() - interval '3 days'
 order by idle_days desc, p.number;

-- member_id → github_login. explanation은 null 그대로(#94 5번, 웹 타입 string | null)
create view public.v_quizzes with (security_invoker = true) as
select q.id, m.github_login as member, q.rule_id, q.source_event_id, q.question, q.choices,
       q.answer_index, q.explanation, q.created_at
  from public.quizzes q
  join public.members m on m.id = q.member_id;

-- v0.1은 저장하는 쪽이 없어 비어 있다
create view public.v_quiz_attempts with (security_invoker = true) as
select a.id, a.quiz_id, m.github_login as member, a.selected_index, a.is_correct, a.attempted_at
  from public.quiz_attempts a
  join public.members m on m.id = a.member_id;

-- ---------- RPC ----------
-- 필터 인자는 모두 기본값 null → 웹은 쓰는 것만 넘기면 된다.

-- 위반 타임라인 (/events). 최신순.
create function public.get_events(
  p_from timestamptz default null, p_to timestamptz default null,
  p_members text[] default null, p_rule_ids text[] default null, p_sources text[] default null,
  p_severities text[] default null, p_actions text[] default null,
  p_repo text default null, p_query text default null
)
returns setof public.v_events
language sql
stable
security invoker
set search_path = ''
as $$
  select e.id, e.schema_version, e.occurred_at, e.source, e.repo, e.member, e.rule_id, e.severity,
         e.action, e.command_summary, e.branch, e.pr_number, e.explanation, e.llm_used,
         e.related_event_id
    from private.filter_events(p_from, p_to, p_members, p_rule_ids, p_sources, p_severities,
                               p_actions, p_repo, p_query) e
   order by e.occurred_at desc, e.id desc;
$$;

-- 규칙별 위반 집계. severity = 그 규칙 위반 중 가장 높은 값(웹이 규칙 기본값으로 덮어씀, #94 4번)
create function public.get_rule_stats(
  p_from timestamptz default null, p_to timestamptz default null,
  p_members text[] default null, p_rule_ids text[] default null, p_sources text[] default null,
  p_severities text[] default null, p_actions text[] default null,
  p_repo text default null, p_query text default null
)
returns table (
  rule_id text, severity text, violation_count int, allowed_count int, guided_count int,
  blocked_count int, detected_count int, ratio double precision
)
language sql
stable
security invoker
set search_path = ''
as $$
  with v as (
    select e.*
      from private.filter_events(p_from, p_to, p_members, p_rule_ids, p_sources, p_severities,
                                 p_actions, p_repo, p_query) e
     where private.is_violation(e.action, e.related_event_id)
  ), s as (
    select v.rule_id,
           case max(case v.severity when 'high' then 3 when 'medium' then 2 else 1 end)
             when 3 then 'high' when 2 then 'medium' else 'low' end            as severity,
           count(*)::int                                                       as violation_count,
           (count(*) filter (where v.action = 'allowed'))::int                 as allowed_count,
           (count(*) filter (where v.action = 'guided'))::int                  as guided_count,
           (count(*) filter (where v.action = 'blocked'))::int                 as blocked_count,
           (count(*) filter (where v.action = 'detected'))::int                as detected_count
      from v
     group by v.rule_id
  )
  select s.rule_id, s.severity, s.violation_count, s.allowed_count, s.guided_count,
         s.blocked_count, s.detected_count,
         s.violation_count::double precision / sum(s.violation_count) over ()
    from s
   order by s.violation_count desc, s.rule_id;
$$;

-- 가이드 완료율. 분모 = 필터에 맞는 guided(복구 가이드 포함).
-- 결과(guide_completed·guide_stopped)는 필터·기간과 상관없이 찾는다. completed가 하나라도 있으면 완료.
create function public.get_guide_stats(
  p_from timestamptz default null, p_to timestamptz default null,
  p_members text[] default null, p_rule_ids text[] default null, p_sources text[] default null,
  p_severities text[] default null, p_actions text[] default null,
  p_repo text default null, p_query text default null
)
returns table (
  rule_id text, guided_count int, completed_count int, stopped_count int,
  in_progress_count int, completion_rate double precision
)
language sql
stable
security invoker
set search_path = ''
as $$
  with g as (
    select e.rule_id,
           exists (select 1 from public.events x
                    where x.related_event_id = e.id and x.action = 'guide_completed') as completed,
           exists (select 1 from public.events x
                    where x.related_event_id = e.id and x.action = 'guide_stopped')   as stopped
      from private.filter_events(p_from, p_to, p_members, p_rule_ids, p_sources, p_severities,
                                 p_actions, p_repo, p_query) e
     where e.action = 'guided'
  )
  select g.rule_id,
         count(*)::int,
         (count(*) filter (where g.completed))::int,
         (count(*) filter (where not g.completed and g.stopped))::int,
         (count(*) filter (where not g.completed and not g.stopped))::int,
         (count(*) filter (where g.completed))::double precision / count(*)
    from g
   group by g.rule_id
   order by g.rule_id;
$$;

-- 일별 위반 수 (KST 날짜 "YYYY-MM-DD"). p_from·p_to가 둘 다 있으면 빈 날도 0으로 채운다.
create function public.get_daily_trend(
  p_from timestamptz default null, p_to timestamptz default null,
  p_members text[] default null, p_rule_ids text[] default null, p_sources text[] default null,
  p_severities text[] default null, p_actions text[] default null,
  p_repo text default null, p_query text default null
)
returns table ("date" text, violation_count int)
language sql
stable
security invoker
set search_path = ''
as $$
  with v as (
    select (e.occurred_at at time zone 'Asia/Seoul')::date as d
      from private.filter_events(p_from, p_to, p_members, p_rule_ids, p_sources, p_severities,
                                 p_actions, p_repo, p_query) e
     where private.is_violation(e.action, e.related_event_id)
  ), days as (
    select g::date as d
      from generate_series((p_from at time zone 'Asia/Seoul')::date,
                           ((p_to - interval '1 microsecond') at time zone 'Asia/Seoul')::date,
                           interval '1 day') as g
     where p_from is not null and p_to is not null
  ), all_days as (
    select v.d from v union select days.d from days
  )
  select to_char(a.d, 'YYYY-MM-DD'), (select count(*) from v where v.d = a.d)::int
    from all_days a
   order by a.d;
$$;

-- 멤버별 PR·리뷰·위반 (멤버 목록 = v_members)
-- reviews_given = 기간 안에 리뷰한 PR 수: 같은 PR 여러 번 = 1, PR 작성자 본인 리뷰 제외
create function public.get_member_activity(
  p_from timestamptz default null, p_to timestamptz default null
)
returns table (
  member text, prs_opened int, prs_merged int, reviews_given int, violation_count int
)
language sql
stable
security invoker
set search_path = ''
as $$
  select m.member,
         (select count(*) from public.prs p
           where p.author = m.member
             and (p_from is null or p.opened_at >= p_from)
             and (p_to   is null or p.opened_at <  p_to))::int,
         (select count(*) from public.prs p
           where p.author = m.member
             and p.merged_at is not null
             and (p_from is null or p.merged_at >= p_from)
             and (p_to   is null or p.merged_at <  p_to))::int,
         (select count(distinct r.pr_id) from public.pr_reviews r
            join public.prs p on p.id = r.pr_id
           where r.reviewer = m.member
             and p.author <> m.member
             and (p_from is null or r.submitted_at >= p_from)
             and (p_to   is null or r.submitted_at <  p_to))::int,
         (select count(*) from public.events e
           where e.member = m.member
             and private.is_violation(e.action, e.related_event_id)
             and (p_from is null or e.occurred_at >= p_from)
             and (p_to   is null or e.occurred_at <  p_to))::int
    from public.v_members m
   order by m.member;
$$;

-- ---------- 권한: 로그인한 사용자만 ----------
-- Supabase는 public 새 뷰·함수에 anon·authenticated 권한을 기본으로 준다 → anon은 거둔다.
revoke all on public.v_events, public.v_members, public.v_stale_prs, public.v_quizzes,
  public.v_quiz_attempts from anon, authenticated;
grant select on public.v_events, public.v_members, public.v_stale_prs, public.v_quizzes,
  public.v_quiz_attempts to authenticated;

revoke execute on function
  public.get_events(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text),
  public.get_rule_stats(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text),
  public.get_guide_stats(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text),
  public.get_daily_trend(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text),
  public.get_member_activity(timestamptz, timestamptz)
  from public, anon;
grant execute on function
  public.get_events(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text),
  public.get_rule_stats(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text),
  public.get_guide_stats(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text),
  public.get_daily_trend(timestamptz, timestamptz, text[], text[], text[], text[], text[], text, text),
  public.get_member_activity(timestamptz, timestamptz)
  to authenticated;
