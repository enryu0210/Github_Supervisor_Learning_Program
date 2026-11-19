-- RLS 정책 + 첫 GitHub 로그인 때 members 연결
-- 기준: docs/db/ERD.md (RLS 판정: auth.uid() → members.auth_user_id → team_id / member_id),
--       docs/architecture/data-flow.md (웹은 anon 키 + 로그인 토큰, 읽기만)
--
-- - 로그인한 멤버는 같은 팀 데이터만 읽는다. 퀴즈·풀이 기록은 본인 것만 읽는다.
-- - 웹용 쓰기 정책은 없다(v0.1 웹은 읽기만, 풀이도 저장하지 않음). 적재는 service role(RLS 우회)만 한다.
-- - anon(로그인 전)용 정책은 없다 → 로그인하지 않으면 아무것도 읽지 못한다.
-- - members에 연결되지 않은 로그인 사용자(팀 밖 GitHub 계정, email 가입)도 아무것도 읽지 못한다.
--
-- 되돌리기: drop trigger on_github_identity_created on auth.identities;
--           drop policy ... (아래 정책 이름); drop schema private cascade;

-- ---------- 판정용 함수 (API에 노출되지 않는 private 스키마) ----------
-- security definer: 정책 안에서 members를 다시 읽을 때 members 정책이 재귀로 걸리지 않게 한다.
-- 로그인 사용자 본인의 team_id·member_id만 돌려주므로 권한이 넓어지지 않는다.
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;

create function private.my_team_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select m.team_id from public.members m where m.auth_user_id = auth.uid();
$$;

create function private.my_member_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select m.id from public.members m where m.auth_user_id = auth.uid();
$$;

revoke execute on function private.my_team_id(), private.my_member_id() from public;
grant execute on function private.my_team_id(), private.my_member_id() to authenticated;

-- ---------- 정책 (select만, authenticated만) ----------
-- (select private.my_team_id())로 감싸 행마다가 아니라 쿼리당 한 번만 계산되게 한다.

create policy teams_select_own_team on public.teams
  for select to authenticated
  using (id = (select private.my_team_id()));

create policy members_select_own_team on public.members
  for select to authenticated
  using (team_id = (select private.my_team_id()));

create policy repos_select_own_team on public.repos
  for select to authenticated
  using (team_id = (select private.my_team_id()));

create policy prs_select_own_team on public.prs
  for select to authenticated
  using (exists (
    select 1 from public.repos r
     where r.id = prs.repo_id
       and r.team_id = (select private.my_team_id())));

create policy pr_reviews_select_own_team on public.pr_reviews
  for select to authenticated
  using (exists (
    select 1 from public.prs p
      join public.repos r on r.id = p.repo_id
     where p.id = pr_reviews.pr_id
       and r.team_id = (select private.my_team_id())));

-- events는 repos와 FK 없이 문자열로 매칭한다(repo = repos.full_name)
create policy events_select_own_team on public.events
  for select to authenticated
  using (exists (
    select 1 from public.repos r
     where r.full_name = events.repo
       and r.team_id = (select private.my_team_id())));

create policy quizzes_select_own on public.quizzes
  for select to authenticated
  using (member_id = (select private.my_member_id()));

create policy quiz_attempts_select_own on public.quiz_attempts
  for select to authenticated
  using (member_id = (select private.my_member_id()));

-- ---------- 첫 GitHub 로그인 때 members.auth_user_id 채우기 ----------
-- GitHub login은 auth.identities.identity_data의 user_name(GitHub가 준 값)으로 읽는다.
-- auth.users.raw_user_meta_data는 email 가입 때 사용자가 임의로 넣을 수 있어 쓰지 않는다.
-- - 이미 다른 사용자와 연결된 멤버, 이미 다른 멤버와 연결된 사용자는 건드리지 않는다.
-- - 등록되지 않은 login이면 아무것도 하지 않는다(그 사용자는 아무것도 읽지 못한다).
-- - 어떤 경우에도 오류를 내지 않는다(트리거 오류는 로그인 자체를 실패시킨다).
create function private.link_member_on_github_identity()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.members m
     set auth_user_id = new.user_id
   where m.github_login = lower(new.identity_data ->> 'user_name')
     and m.auth_user_id is null
     and not exists (select 1 from public.members x where x.auth_user_id = new.user_id);
  return new;
exception when others then
  raise warning 'link_member_on_github_identity: %', sqlerrm;
  return new;
end;
$$;

revoke execute on function private.link_member_on_github_identity() from public;

create trigger on_github_identity_created
  after insert on auth.identities
  for each row
  when (new.provider = 'github')
  execute function private.link_member_on_github_identity();

-- 이 마이그레이션 전에 이미 로그인한 사용자도 한 번 연결한다
update public.members m
   set auth_user_id = i.user_id
  from auth.identities i
 where i.provider = 'github'
   and m.github_login = lower(i.identity_data ->> 'user_name')
   and m.auth_user_id is null
   and not exists (select 1 from public.members x where x.auth_user_id = i.user_id);
