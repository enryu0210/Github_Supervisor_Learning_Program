-- ingest-events 적재 경로 (CLI `gitcoach sync` → Edge Function `ingest-events` → events)
-- 기준: docs/guide/01_cli.md 3-7(sync 사양), docs/architecture/data-flow.md ②, #60(응답 계약)
--
-- 1) ingest_tokens: 팀 토큰의 sha256 해시만 저장한다(원문 토큰은 DB·레포 어디에도 두지 않는다).
--    토큰 → 팀을 찾고, 이벤트의 repo가 그 팀 레포인지 확인하는 데 쓴다.
-- 2) ingest_events(): 배치를 한 건씩 넣고 건별 결과(inserted·duplicate·rejected)를 돌려준다.
--    한 건이 제약에 걸려도 나머지는 들어간다. 필드 형식 검사는 Edge Function이 먼저 하고,
--    여기서는 팀 레포 확인 + 테이블 제약(최종 기준)만 본다.
--
-- 되돌리기: drop function public.ingest_events(text, jsonb); drop table public.ingest_tokens;

-- ---------- 팀 토큰 (해시만) ----------
create table public.ingest_tokens (
  token_hash  text primary key check (token_hash ~ '^[0-9a-f]{64}$'),  -- sha256(토큰) 16진수 소문자
  team_id     uuid not null references public.teams (id) on delete cascade,
  label       text not null,                                           -- 누구에게·언제 준 토큰인지
  created_at  timestamptz not null default now(),
  revoked_at  timestamptz                                              -- 값이 있으면 거절(회수)
);

-- 정책 없음: anon·authenticated는 읽지도 쓰지도 못한다. ingest-events(service role)만 조회한다.
-- RLS에 더해 테이블 권한도 거둔다(Supabase는 public 새 테이블에 anon·authenticated 권한을 기본으로 준다).
alter table public.ingest_tokens enable row level security;
revoke all on table public.ingest_tokens from anon, authenticated;
grant select on table public.ingest_tokens to service_role;

-- ---------- 배치 적재 ----------
create function public.ingest_events(p_token_hash text, p_events jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_team_id     uuid;
  v_event       jsonb;
  v_id          text;
  v_rows        int;
  v_results     jsonb := '[]'::jsonb;
  v_constraint  text;
  v_message     text;
begin
  select t.team_id into v_team_id
    from public.ingest_tokens t
   where t.token_hash = p_token_hash
     and t.revoked_at is null;
  if v_team_id is null then
    raise exception 'invalid token' using errcode = '28000';  -- invalid_authorization_specification
  end if;

  if p_events is null or jsonb_typeof(p_events) <> 'array' then
    raise exception 'events must be an array' using errcode = '22023';  -- invalid_parameter_value
  end if;

  for v_event in select e.value from jsonb_array_elements(p_events) as e loop
    -- 결과 id는 받은 문자열 그대로 돌려준다(CLI는 이 값으로 로컬 행을 표시한다)
    v_id := v_event ->> 'id';

    if not exists (
      select 1 from public.repos r
       where r.team_id = v_team_id
         and r.full_name = v_event ->> 'repo'
    ) then
      v_results := v_results || jsonb_build_array(jsonb_build_object(
        'id', v_id, 'status', 'rejected',
        'reason', 'repo: 이 토큰의 팀에 등록된 레포가 아닙니다',
        'errors', jsonb_build_array(jsonb_build_object(
          'field', 'repo', 'reason', '이 토큰의 팀에 등록된 레포가 아닙니다'))));
      continue;
    end if;

    begin
      insert into public.events (
        id, schema_version, occurred_at, source, repo, member, rule_id, severity, action,
        command_summary, branch, pr_number, explanation, llm_used, related_event_id
      )
      select r.id, r.schema_version, r.occurred_at, r.source, r.repo, r.member, r.rule_id,
             r.severity, r.action, r.command_summary, r.branch, r.pr_number, r.explanation,
             r.llm_used, r.related_event_id
        from jsonb_populate_record(null::public.events, v_event) as r
      on conflict (id) do nothing;
      get diagnostics v_rows = row_count;

      v_results := v_results || jsonb_build_array(jsonb_build_object(
        'id', v_id,
        'status', case when v_rows = 1 then 'inserted' else 'duplicate' end));
    exception
      when check_violation or not_null_violation or invalid_text_representation
        or invalid_datetime_format or datetime_field_overflow or numeric_value_out_of_range then
        get stacked diagnostics v_constraint = constraint_name, v_message = message_text;
        v_results := v_results || jsonb_build_array(jsonb_build_object(
          'id', v_id, 'status', 'rejected',
          'reason', 'DB 제약 위반: ' || coalesce(nullif(v_constraint, ''), v_message),
          'errors', jsonb_build_array(jsonb_build_object(
            'field', coalesce(nullif(v_constraint, ''), 'event'), 'reason', v_message))));
    end;
  end loop;

  return jsonb_build_object('results', v_results);
end;
$$;

-- Supabase는 public 스키마 새 함수에 anon·authenticated 실행 권한을 기본으로 준다 → 막고 service role만 허용
revoke execute on function public.ingest_events(text, jsonb) from public, anon, authenticated;
grant execute on function public.ingest_events(text, jsonb) to service_role;
