// 이벤트 JSON 계약(docs/guide/01_cli.md 6절, 스키마 v1) 검사.
// 테이블 제약(supabase/migrations/*_schema_v1.sql, *_repo_lowercase.sql)과 같은 기준이며,
// 어떤 필드가 왜 틀렸는지 CLI가 보여 줄 수 있게 필드별 이유를 돌려준다.
// Deno·Node 어디서나 돌도록 런타임 API를 쓰지 않는다.

export const MAX_BATCH = 100;

export type FieldError = { field: string; reason: string };

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
// 오프셋(Z 또는 ±hh:mm)이 있는 ISO 8601. 오프셋 없는 시각은 서버 시간대로 해석돼 어긋나므로 거절한다.
const TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;
const REPO_RE = /^[^/\s]+\/[^/\s]+$/;
const MEMBER_RE = /^[a-z0-9][a-z0-9-]*$/;
const SEVERITIES = ["high", "medium", "low"];
// ingest-events는 CLI 이벤트만 받는다. detected(source = github)는 watcher가 service key로 직접 적재한다.
const CLI_ACTIONS = ["allowed", "guided", "blocked", "guide_completed", "guide_stopped"];
const INT32_MAX = 2147483647;

const isNullableString = (v: unknown) => v === null || v === undefined || typeof v === "string";

export function validateEvent(raw: unknown): FieldError[] {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return [{ field: "event", reason: "JSON 객체여야 합니다" }];
  }
  const e = raw as Record<string, unknown>;
  const errors: FieldError[] = [];
  const err = (field: string, reason: string) => errors.push({ field, reason });

  if (typeof e.id !== "string" || !UUID_RE.test(e.id)) err("id", "UUID 문자열이어야 합니다");
  if (e.schema_version !== 1) err("schema_version", "1이어야 합니다");

  if (typeof e.occurred_at !== "string" || !TIMESTAMP_RE.test(e.occurred_at) ||
      Number.isNaN(Date.parse(e.occurred_at))) {
    err("occurred_at", "시간대 오프셋이 있는 ISO 8601 시각이어야 합니다 (예: 2026-11-08T14:20:00+09:00)");
  }

  if (e.source !== "cli") err("source", "ingest-events는 'cli' 이벤트만 받습니다 (github 이벤트는 watcher가 직접 적재)");

  if (typeof e.repo !== "string" || !REPO_RE.test(e.repo)) {
    err("repo", "owner/name 형식이어야 합니다");
  } else if (e.repo !== e.repo.toLowerCase()) {
    err("repo", "소문자여야 합니다");
  }

  if (typeof e.member !== "string" || !MEMBER_RE.test(e.member)) {
    err("member", "소문자 GitHub login이어야 합니다 (빈 값 불가)");
  }

  if (typeof e.rule_id !== "string" || e.rule_id.trim() === "") err("rule_id", "빈 값이 아닌 문자열이어야 합니다");

  if (typeof e.severity !== "string" || !SEVERITIES.includes(e.severity)) {
    err("severity", `${SEVERITIES.join("·")} 중 하나여야 합니다`);
  }

  const actionOk = typeof e.action === "string" && CLI_ACTIONS.includes(e.action);
  if (!actionOk) err("action", `${CLI_ACTIONS.join("·")} 중 하나여야 합니다`);

  if (!isNullableString(e.command_summary)) err("command_summary", "문자열 또는 null이어야 합니다");
  if (!isNullableString(e.branch)) err("branch", "문자열 또는 null이어야 합니다");
  if (!isNullableString(e.explanation)) err("explanation", "문자열 또는 null이어야 합니다");

  if (e.pr_number !== null && e.pr_number !== undefined &&
      !(Number.isInteger(e.pr_number) && (e.pr_number as number) > 0 && (e.pr_number as number) <= INT32_MAX)) {
    err("pr_number", "양의 정수 또는 null이어야 합니다");
  }

  if (typeof e.llm_used !== "boolean") err("llm_used", "true 또는 false여야 합니다");

  const related = e.related_event_id;
  const hasRelated = related !== null && related !== undefined;
  if (hasRelated && (typeof related !== "string" || !UUID_RE.test(related))) {
    err("related_event_id", "UUID 문자열 또는 null이어야 합니다");
  }

  // 행 안의 교차 규칙 (테이블 check 제약과 같음)
  if (actionOk) {
    if ((e.action === "guide_completed" || e.action === "guide_stopped") && !hasRelated) {
      err("related_event_id", "가이드 결과 이벤트는 원래 guided 이벤트 id가 필요합니다");
    }
    if ((e.action === "allowed" || e.action === "blocked") && hasRelated) {
      err("related_event_id", `${e.action} 이벤트는 null이어야 합니다`);
    }
    if (e.action === "allowed") {
      const hasExplanation = e.explanation !== null && e.explanation !== undefined;
      if (hasExplanation) err("explanation", "allowed 이벤트는 null이어야 합니다");
      if (e.llm_used === true) err("llm_used", "allowed 이벤트는 false여야 합니다");
    }
  }

  return errors;
}

export function summarize(errors: FieldError[]): string {
  return errors.map((x) => `${x.field}: ${x.reason}`).join("; ");
}

// 결과 id는 받은 값을 그대로 돌려준다(CLI는 이 값으로 로컬 행을 표시한다). 문자열이 아니면 null.
export function echoId(raw: unknown): string | null {
  if (raw !== null && typeof raw === "object" && !Array.isArray(raw)) {
    const id = (raw as Record<string, unknown>).id;
    return typeof id === "string" ? id : null;
  }
  return null;
}
