-- public.rls_auto_enable() 실행 권한 회수
-- 이 함수는 Supabase 플랫폼이 프로젝트에 만든 이벤트 트리거(ensure_rls) 함수다. public에 새 테이블이 생기면 RLS를 켠다.
-- security definer인데 public 스키마에 있어 anon·authenticated가 /rest/v1/rpc/rls_auto_enable로 실행 권한을 가진다
-- (Supabase security advisor WARN). 반환형이 event_trigger라 직접 호출은 실패하지만, 필요 없는 권한이므로 거둔다.
-- 이벤트 트리거는 실행 권한과 상관없이 동작한다(함수 소유자 권한으로 실행) → 자동 RLS는 그대로다.
--
-- 플랫폼이 만든 함수라 로컬 `supabase db reset` 등 함수가 없는 환경이 있다 → 있을 때만 회수한다.
-- 되돌리기: grant execute on function public.rls_auto_enable() to public, anon, authenticated;

do $$
begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
  end if;
end;
$$;
