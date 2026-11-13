-- seed: 팀·레포·멤버 등록
-- watcher 직접 적재는 repo 문자열로 repos.id를, 퀴즈 저장은 github_login으로 members.id를 찾으므로
-- 적재가 시작되기 전에 이 값들이 있어야 한다.
--
-- - 실제 키·개인정보를 넣지 않는다. github_login은 GitHub에 공개된 계정명이고 display_name(실명)은 비워 둔다.
-- - auth_user_id는 비워 둔다. 첫 GitHub 로그인 때 github_login(소문자)으로 매칭해 채운다.
-- - 몇 번 실행해도 결과가 같다(고정 UUID + on conflict do nothing).
-- - 로컬 `supabase db reset`에서만 자동 실행된다. 클라우드 프로젝트에는 `supabase db push`가 seed를 넣지 않으므로
--   SQL Editor 등에서 한 번 직접 실행한다.

-- ---------- 팀 ----------
insert into public.teams (id, name) values
  ('6c0b8f3e-2d4a-4e7b-9c51-000000000001', 'gitcoach')
on conflict (id) do nothing;

-- ---------- 레포 ----------
-- 소문자 owner/name. CLI·watcher 모두 repo를 lower() 해서 기록한다(docs/guide/01_cli.md 5절, #55).
-- fork(개인 레포) 이름은 넣지 않는다. 이벤트는 upstream 이름으로 기록된다.
insert into public.repos (id, team_id, full_name) values
  ('6c0b8f3e-2d4a-4e7b-9c51-000000000101', '6c0b8f3e-2d4a-4e7b-9c51-000000000001',
   'enryu0210/github_supervisor_learning_program')
on conflict (full_name) do nothing;

-- ---------- 멤버 ----------
-- github_login은 소문자 (members.github_login 제약)
insert into public.members (id, team_id, github_login) values
  ('6c0b8f3e-2d4a-4e7b-9c51-000000000201', '6c0b8f3e-2d4a-4e7b-9c51-000000000001', 'enryu0210'),
  ('6c0b8f3e-2d4a-4e7b-9c51-000000000202', '6c0b8f3e-2d4a-4e7b-9c51-000000000001', 'kkanooww'),
  ('6c0b8f3e-2d4a-4e7b-9c51-000000000203', '6c0b8f3e-2d4a-4e7b-9c51-000000000001', 'zrrh8ngbrd-max'),
  ('6c0b8f3e-2d4a-4e7b-9c51-000000000204', '6c0b8f3e-2d4a-4e7b-9c51-000000000001', 'leafbell-sii')
  -- 배포 담당 계정은 확인되면 '...000000000205'로 추가한다
on conflict (github_login) do nothing;
