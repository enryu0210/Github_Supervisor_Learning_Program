// DB 없이 요청 처리·형식 검사를 시험한다. 실행: node --test supabase/functions/ingest-events/handler_test.ts
// (Node 22.18+/24는 .ts 타입을 지우고 바로 실행한다. DB 쪽 시험은 개발 DB에서 curl로 — README 참고)

import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { handle, type Deps, type Result } from "./handler.ts";
import { validateEvent } from "./validate.ts";

const SAMPLES_DIR = join(import.meta.dirname, "..", "..", "..", "samples");
const samples = readdirSync(SAMPLES_DIR)
  .filter((f) => f.endsWith(".json"))
  .sort()
  .map((f) => JSON.parse(readFileSync(join(SAMPLES_DIR, f), "utf8")));
const cliSamples = samples.filter((e) => e.source === "cli");

const base = () => structuredClone(cliSamples[0]); // allowed 이벤트

// DB 흉내: 토큰 "good"만 통과, 처음 보는 id는 inserted, 본 id는 duplicate
function fakeDeps() {
  const seen = new Set<string>();
  const calls: unknown[][] = [];
  const deps: Deps = {
    sha256Hex: async (t) => `hash:${t}`,
    ingest: async (hash, events) => {
      calls.push(events);
      if (hash !== "hash:good") return { data: null, error: { code: "28000", message: "invalid token" } };
      const results: Result[] = events.map((e) => {
        const id = (e as { id: string }).id;
        const status = seen.has(id) ? "duplicate" : "inserted";
        seen.add(id);
        return { id, status };
      });
      return { data: { results }, error: null };
    },
  };
  return { deps, calls };
}

const post = (body: unknown, token: string | null = "good") =>
  new Request("http://localhost/ingest-events", {
    method: "POST",
    headers: token ? { authorization: `Bearer ${token}` } : {},
    body: typeof body === "string" ? body : JSON.stringify(body),
  });

test("samples의 CLI 이벤트는 모두 형식 검사를 통과한다", () => {
  assert.ok(cliSamples.length >= 18);
  for (const e of cliSamples) assert.deepEqual(validateEvent(e), [], e.id);
});

test("samples의 watcher detected 이벤트는 source로 거절한다", () => {
  for (const e of samples.filter((x) => x.source === "github")) {
    assert.deepEqual(validateEvent(e).map((x) => x.field), ["source", "action"]);
  }
});

test("처음 보내면 inserted, 다시 보내면 duplicate (보낸 순서·id 그대로)", async () => {
  const { deps } = fakeDeps();
  const first = await (await handle(post({ events: cliSamples }), deps)).json();
  assert.deepEqual(first.results.map((r: Result) => r.id), cliSamples.map((e) => e.id));
  assert.ok(first.results.every((r: Result) => r.status === "inserted"));
  const again = await (await handle(post({ events: cliSamples }), deps)).json();
  assert.ok(again.results.every((r: Result) => r.status === "duplicate"));
});

test("틀린 건만 rejected(필드·이유 포함), 나머지는 DB로 간다", async () => {
  const { deps, calls } = fakeDeps();
  const bad = { ...base(), id: "BAD-ID", member: "LeafBell-SII", explanation: "설명" };
  const res = await handle(post({ events: [bad, cliSamples[1]] }), deps);
  assert.equal(res.status, 200);
  const { results } = await res.json();
  assert.equal(results[0].status, "rejected");
  assert.equal(results[0].id, "BAD-ID"); // 받은 값 그대로
  assert.deepEqual(results[0].errors.map((x: { field: string }) => x.field), ["id", "member", "explanation"]);
  assert.match(results[0].reason, /^id: .*; member: .*; explanation: /);
  assert.equal(results[1].status, "inserted");
  assert.deepEqual(calls[0], [cliSamples[1]]);
});

test("대문자 UUID도 받은 문자열 그대로 돌려준다", async () => {
  const { deps } = fakeDeps();
  const e = { ...base(), id: base().id.toUpperCase() };
  const { results } = await (await handle(post({ events: [e] }), deps)).json();
  assert.equal(results[0].id, e.id);
});

test("교차 규칙: 가이드 결과는 related 필요, allowed는 설명·LLM 없음, 오프셋 없는 시각 거절", () => {
  const fields = (patch: Record<string, unknown>) => validateEvent({ ...base(), ...patch }).map((x) => x.field);
  assert.deepEqual(fields({ action: "guide_completed", related_event_id: null }), ["related_event_id"]);
  assert.deepEqual(fields({ action: "blocked", related_event_id: base().id }), ["related_event_id"]);
  assert.deepEqual(fields({ llm_used: true }), ["llm_used"]);
  assert.deepEqual(fields({ occurred_at: "2026-11-06T09:12:03" }), ["occurred_at"]);
  assert.deepEqual(fields({ repo: "Owner/Name" }), ["repo"]);
  assert.deepEqual(fields({ member: "" }), ["member"]);
  assert.deepEqual(fields({ pr_number: 1.5 }), ["pr_number"]);
  assert.deepEqual(fields({ severity: "critical", schema_version: 2 }), ["schema_version", "severity"]);
  assert.deepEqual(validateEvent([]).map((x) => x.field), ["event"]);
});

test("배치 전체 오류는 HTTP 상태로", async () => {
  const { deps } = fakeDeps();
  assert.equal((await handle(post({ events: [] }, null), deps)).status, 401);
  assert.equal((await handle(post({ events: [] }, "wrong"), deps)).status, 401);
  assert.equal((await handle(post("not json"), deps)).status, 400);
  assert.equal((await handle(post({ events: {} }), deps)).status, 400);
  assert.equal((await handle(post({ events: Array(101).fill(base()) }), deps)).status, 400);
  assert.equal((await handle(new Request("http://localhost/", { method: "GET" }), deps)).status, 405);
  const ok = await handle(post({ events: [] }), deps);
  assert.equal(ok.status, 200);
  assert.deepEqual(await ok.json(), { results: [] });
});

test("DB 오류는 500 (CLI는 SyncError → 다음에 다시 시도)", async () => {
  const deps: Deps = {
    sha256Hex: async () => "h",
    ingest: async () => ({ data: null, error: { code: "57014", message: "timeout" } }),
  };
  assert.equal((await handle(post({ events: [base()] }), deps)).status, 500);
});
