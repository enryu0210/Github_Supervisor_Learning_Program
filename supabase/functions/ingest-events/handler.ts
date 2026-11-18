// ingest-events 요청 처리. DB 호출(rpc)은 밖에서 넣어 주므로 DB 없이도 시험할 수 있다.
//
// 요청:  POST, Authorization: Bearer <팀 토큰>, 본문 {"events": [Event, ...]} (최대 100건)
// 응답:  200 {"results": [{"id", "status": "inserted"|"duplicate"|"rejected", "reason"?, "errors"?}]}
//        결과는 보낸 순서 그대로, id는 받은 문자열 그대로.
//        배치 전체 오류는 HTTP 상태 + {"error"}: 401 토큰 / 400 본문 / 405 메서드 / 500 서버·DB(다시 시도 가능)
// 기준: docs/guide/01_cli.md 3-7, #60 응답 계약

import { echoId, MAX_BATCH, summarize, validateEvent, type FieldError } from "./validate.ts";

export type Result = {
  id: string | null;
  status: "inserted" | "duplicate" | "rejected";
  reason?: string;
  errors?: FieldError[];
};

export type RpcError = { code?: string; message: string };

export type Deps = {
  // public.ingest_events(p_token_hash, p_events) 호출
  ingest: (tokenHash: string, events: unknown[]) => Promise<{ data: { results: Result[] } | null; error: RpcError | null }>;
  sha256Hex: (text: string) => Promise<string>;
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

export async function handle(req: Request, deps: Deps): Promise<Response> {
  if (req.method !== "POST") return json(405, { error: "POST만 받습니다" });

  const auth = req.headers.get("authorization") ?? "";
  const match = auth.match(/^Bearer\s+(\S+)$/i);
  if (!match) return json(401, { error: "Authorization: Bearer <팀 토큰> 헤더가 필요합니다" });
  const tokenHash = await deps.sha256Hex(match[1]);

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return json(400, { error: "본문이 JSON이 아닙니다" });
  }
  const events = (body !== null && typeof body === "object" && !Array.isArray(body))
    ? (body as Record<string, unknown>).events
    : undefined;
  if (!Array.isArray(events)) return json(400, { error: '본문은 {"events": [...]} 형식이어야 합니다' });
  if (events.length > MAX_BATCH) return json(400, { error: `한 번에 최대 ${MAX_BATCH}건까지 보낼 수 있습니다` });

  // 형식 검사를 통과한 것만 DB로 보낸다. 결과는 보낸 순서대로 다시 맞춘다.
  const results: (Result | null)[] = events.map((raw) => {
    const errors = validateEvent(raw);
    return errors.length
      ? { id: echoId(raw), status: "rejected", reason: summarize(errors), errors }
      : null;
  });
  const valid = events.filter((_, i) => results[i] === null);

  // 빈 배치여도 토큰은 확인한다(설정 확인용으로 빈 요청을 보내도 401이 드러나게).
  const { data, error } = await deps.ingest(tokenHash, valid);
  if (error) {
    if (error.code === "28000") return json(401, { error: "팀 토큰이 올바르지 않거나 회수되었습니다" });
    console.error("ingest_events failed", error.code, error.message);
    return json(500, { error: "서버에서 저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요" });
  }

  const dbResults = data?.results ?? [];
  if (dbResults.length !== valid.length) {
    console.error("ingest_events result count mismatch", dbResults.length, valid.length);
    return json(500, { error: "서버 응답이 올바르지 않습니다. 잠시 뒤 다시 시도해 주세요" });
  }
  let k = 0;
  return json(200, { results: results.map((r) => r ?? dbResults[k++]) });
}
