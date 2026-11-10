// types/event.ts
// CLI 이벤트 스키마 v1과 같은 이름·필드를 쓴다. (git-coach CLI v0.1 설계 · "이벤트 스키마 변경 제안 (v1)")
// 스키마는 팀 계약이다. 필드를 바꿀 때는 혼자 고치지 말고 권아현·이남주와 PR에서 논의한다.
// v1은 11/9에 고정된다. 그 전에 바뀌면 이 파일을 먼저 고친다.

/** 심각도. v1에서 3단계로 확정. */
export const SEVERITIES = ["high", "medium", "low"] as const;
export type Severity = (typeof SEVERITIES)[number];

/** 이벤트 출처. cli = 래퍼(shim), github = watcher */
export const EVENT_SOURCES = ["cli", "github"] as const;
export type EventSource = (typeof EVENT_SOURCES)[number];

/**
 * 위험 명령을 잡았을 때 남는 결과.
 * - allowed          : 경고를 보고도 [1] 그냥 실행함
 * - guided           : [2] 가이드를 선택함 (원래 명령은 취소됨)
 * - blocked          : R03(비밀 정보) 전용 차단. R03 화면의 [q] 취소도 blocked 로 기록
 * - guide_completed  : 가이드를 끝까지 함 (related_event_id → 원래 guided 이벤트)
 * - guide_stopped    : 가이드를 중간에 그만둠 (related_event_id → 원래 guided 이벤트)
 * - detected         : watcher가 GitHub에서 발견함 (source = "github")
 */
export const EVENT_ACTIONS = [
  "allowed",
  "guided",
  "blocked",
  "guide_completed",
  "guide_stopped",
  "detected",
] as const;
export type EventAction = (typeof EVENT_ACTIONS)[number];

/**
 * 위반이 "발생한" 시점의 이벤트. 위반 수 집계는 이 값들만 센다.
 * guide_completed·guide_stopped는 같은 위반의 후속 기록이므로 위반 수에 다시 세지 않는다.
 */
export const VIOLATION_ACTIONS = ["allowed", "guided", "blocked", "detected"] as const satisfies readonly EventAction[];
export type ViolationAction = (typeof VIOLATION_ACTIONS)[number];

/**
 * 가이드 결과 이벤트. related_event_id 로 원래 guided 이벤트를 가리킨다.
 * (복구 guided 도 related_event_id 가 채워지므로 related_event_id 만으로 결과 이벤트를 판단하지 않는다)
 */
export const GUIDE_RESULT_ACTIONS = ["guide_completed", "guide_stopped"] as const satisfies readonly EventAction[];
export type GuideResultAction = (typeof GUIDE_RESULT_ACTIONS)[number];

/** 규칙 ID. v0.1은 R01~R06, R07은 v0.2. 규칙이 늘어날 수 있어 문자열로 둔다. */
export type RuleId = string; // "R01" ...

export type GitCoachEvent = {
  id: string; // uuid
  schema_version: 1;
  occurred_at: string; // ISO 8601 (예: 2026-11-08T14:20:00+09:00)
  source: EventSource;
  repo: string; // "owner/name"
  member: string; // github_login
  rule_id: RuleId;
  severity: Severity;
  action: EventAction;
  command_summary: string | null; // 예: "git push origin main". 시크릿 값은 넣지 않는다
  branch: string | null;
  pr_number: number | null;
  explanation: string | null; // allowed 면 항상 null (ERD의 DB 제약)
  llm_used: boolean;
  /**
   * 연결된 원래 이벤트의 id.
   * - guide_completed·guide_stopped → 원래 guided 이벤트 (필수)
   * - guided(복구, `gitcoach guide undo`) → 원래 allowed 이벤트
   * - 그 외 → null
   */
  related_event_id: string | null;
};

/**
 * 타입 가드: 위반 발생 이벤트인가
 * 복구 가이드(guided + related_event_id → 원래 allowed)는 이미 센 위반의 후속 기록이므로 제외한다.
 */
export function isViolation(e: GitCoachEvent): boolean {
  if (e.action === "guided" && e.related_event_id !== null) return false;
  return (VIOLATION_ACTIONS as readonly EventAction[]).includes(e.action);
}

/** 타입 가드: 가이드 후속 결과 이벤트인가 */
export function isGuideResult(e: GitCoachEvent): boolean {
  return (GUIDE_RESULT_ACTIONS as readonly EventAction[]).includes(e.action);
}
