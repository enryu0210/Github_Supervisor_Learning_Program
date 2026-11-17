# ingest-events

CLI `gitcoach sync`가 이벤트를 올리는 Edge Function. 사양은 `docs/guide/01_cli.md` 3-7, 테이블은 `docs/db/ERD.md`.

| 파일 | 내용 |
|---|---|
| `index.ts` | Supabase 함수 진입점. RPC `ingest_events` 호출 |
| `handler.ts` | 요청 처리(인증 헤더·본문·배치 크기·결과 순서 맞추기). DB 호출은 주입 |
| `validate.ts` | 이벤트 스키마 v1 형식 검사(필드별 이유) |
| `handler_test.ts` | DB 없이 도는 테스트 |

## 요청·응답

```http
POST <GITCOACH_SYNC_URL>
Authorization: Bearer <팀 토큰>

{"events": [Event, ...]}        // 최대 100건
```

```json
{"results": [
  {"id": "…", "status": "inserted"},
  {"id": "…", "status": "duplicate"},
  {"id": "…", "status": "rejected", "reason": "member: …", "errors": [{"field": "member", "reason": "…"}]}
]}
```

- 결과는 보낸 순서 그대로, `id`는 받은 문자열 그대로 돌려준다.
- 배치 전체 오류는 HTTP 상태 + `{"error"}`: `401` 토큰 없음·틀림·회수 / `400` JSON 아님·`events` 배열 아님·100건 초과 / `405` POST 아님 / `500` 서버·DB 오류(다시 시도).
- `source = 'cli'`만 받는다. 이벤트의 `repo`는 토큰의 팀에 등록된 레포(`repos.full_name`)여야 한다.

## 팀 토큰 발급·회수

DB에는 sha256 해시만 넣는다. 원문 토큰은 레포·이슈·PR·톡방에 올리지 않고 받는 사람에게 개별로 전달한다.

```bash
# 1) 토큰 만들기 (원문은 받는 사람에게만 전달)
python -c "import secrets; print(secrets.token_urlsafe(32))"
# 2) 해시 계산
python -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "<토큰>"
```

```sql
-- 3) 등록 (SQL Editor, postgres 권한)
insert into public.ingest_tokens (token_hash, team_id, label)
values ('<해시>', '<teams.id>', '<누구에게·언제>');

-- 회수
update public.ingest_tokens set revoked_at = now() where label = '<label>';
```

## 배포

```bash
supabase functions deploy ingest-events --project-ref <project-ref>
```

`supabase/config.toml`에서 `verify_jwt = false`(Supabase JWT 대신 팀 토큰으로 인증). `SUPABASE_URL`·`SUPABASE_SERVICE_ROLE_KEY`는 Supabase가 함수 환경변수로 넣어 준다.

## 테스트

```bash
node --test supabase/functions/ingest-events/handler_test.ts
```

배포 뒤 확인(같은 요청을 두 번 보내면 두 번째는 전부 `duplicate`):

```bash
curl -s -X POST "$GITCOACH_SYNC_URL" -H "Authorization: Bearer $GITCOACH_SYNC_TOKEN" \
  -H "Content-Type: application/json" -d '{"events": []}'
```
