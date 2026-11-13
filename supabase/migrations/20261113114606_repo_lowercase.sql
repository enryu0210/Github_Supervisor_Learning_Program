-- repo 소문자 제약
-- events.repo는 repos.full_name과 FK 없이 문자열로 매칭한다. 대소문자가 다르면 팀 레포에 매칭되지 않아
-- 통계·RLS에서 조용히 빠지므로, 적재 때 거절해 바로 드러나게 한다.
-- 기준: docs/guide/01_cli.md 5절 — CLI·watcher 모두 repo를 lower() 해서 기록한다(#55).
--       member·github_login 소문자 제약과 같은 방식.
-- 되돌리기: alter table ... drop constraint <이름>;

alter table public.repos
  add constraint repos_full_name_lower_chk check (full_name = lower(full_name));

alter table public.events
  add constraint events_repo_lower_chk check (repo = lower(repo));
