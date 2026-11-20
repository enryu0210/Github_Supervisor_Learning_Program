-- 멤버를 나중에 추가해도 이미 로그인한 GitHub 사용자와 연결 (#109)
-- 기준: docs/db/ERD.md "로그인 ↔ members 연결"
--
-- rls_policies의 on_github_identity_created는 GitHub 첫 로그인(auth.identities insert) 때만 돈다.
-- 그래서 "로그인 → 멤버 추가" 순서면 auth_user_id가 비어 그 사람은 아무것도 읽지 못했다.
-- 이 마이그레이션은 반대 방향(members insert, github_login 변경)에서도 같은 조건으로 연결한다.
--
-- 조건은 rls_policies와 같다.
-- - GitHub identity(provider 'github')의 identity_data.user_name을 소문자로 바꿔 github_login과 비교한다.
--   email identity는 쓰지 않는다(사용자가 user_name을 임의로 넣을 수 있음).
-- - 이미 연결된 멤버(auth_user_id가 있는 행), 이미 다른 멤버와 연결된 사용자는 건드리지 않는다.
-- - 오류를 내지 않는다(멤버 등록 자체를 막지 않음).
-- 추가 조건: 후보 사용자가 정확히 1명일 때만 연결한다(같은 login의 GitHub identity가 둘 이상이면
--   누구인지 알 수 없으므로 비워 둔다. GitHub 계정 이름 변경 뒤 다른 사람이 옛 이름을 가져간 경우 등).
--
-- 되돌리기: drop trigger link_member_on_member_change on public.members;
--           drop function private.link_member_on_member_change();
--           (이미 채워진 auth_user_id는 그대로 둔다)

create function private.link_member_on_member_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  candidates uuid[];
begin
  if new.auth_user_id is not null then
    return new;
  end if;

  select array_agg(distinct i.user_id)
    into candidates
    from auth.identities i
   where i.provider = 'github'
     and lower(i.identity_data ->> 'user_name') = new.github_login
     and not exists (select 1 from public.members x where x.auth_user_id = i.user_id);

  if cardinality(candidates) = 1 then
    new.auth_user_id := candidates[1];
  end if;
  return new;
exception when others then
  raise warning 'link_member_on_member_change: %', sqlerrm;
  return new;
end;
$$;

revoke execute on function private.link_member_on_member_change() from public;

-- before 트리거: 새 행의 auth_user_id를 직접 채운다(members를 다시 update하지 않아 재귀 없음)
create trigger link_member_on_member_change
  before insert or update of github_login on public.members
  for each row
  execute function private.link_member_on_member_change();

-- rls_policies 이후 이 마이그레이션 전까지 "로그인 → 멤버 추가"로 비어 있는 멤버를 한 번 연결한다
update public.members m
   set auth_user_id = c.user_id
  from (
    select lower(i.identity_data ->> 'user_name') as login, (array_agg(distinct i.user_id))[1] as user_id
      from auth.identities i
     where i.provider = 'github'
       and not exists (select 1 from public.members x where x.auth_user_id = i.user_id)
     group by 1
    having count(distinct i.user_id) = 1
  ) c
 where m.github_login = c.login
   and m.auth_user_id is null;
