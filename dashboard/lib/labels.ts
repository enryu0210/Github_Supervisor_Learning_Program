// lib/labels.ts
// 이벤트 값 → 화면 표시 문구. 화면에서 문구를 직접 쓰지 말고 여기서 가져온다.
// Record<EventAction, ...> 형태라서 types/event.ts에 값이 추가되면 여기서 컴파일 오류가 나 빠뜨릴 수 없다.

import type { EventAction, EventSource, GitCoachEvent, RuleId, Severity } from "@/types/event";

/**
 * 배지 색 의미. 실제 색(Tailwind 클래스)은 components/Badge.tsx 에서 매핑한다.
 * notice 는 "GitHub에서 발견" 전용 색 (docs/wireframes/README.md)
 */
export type LabelTone = "danger" | "warning" | "info" | "success" | "neutral" | "notice";

export type LabelInfo = {
  label: string; // 배지·표에 쓰는 짧은 문구
  description: string; // 툴팁·범례에 쓰는 한 줄 설명
  tone: LabelTone;
};

/* ------------------------------------------------------------------ */
/* action                                                              */
/* ------------------------------------------------------------------ */

export const ACTION_LABELS: Record<EventAction, LabelInfo> = {
  allowed: {
    label: "그냥 실행함",
    description: "경고를 보고도 [1] 그냥 실행을 골랐어요.",
    tone: "warning",
  },
  guided: {
    label: "가이드 시작",
    description: "[2] 가이드를 골라 원래 명령을 취소했어요.",
    tone: "info",
  },
  blocked: {
    label: "실행 막힘",
    description: "비밀 정보가 들어 있어 실행을 막았어요.",
    tone: "danger",
  },
  guide_completed: {
    label: "가이드 완료",
    description: "가이드를 끝까지 진행했어요.",
    tone: "success",
  },
  guide_stopped: {
    label: "가이드 중단",
    description: "가이드를 중간에 그만뒀어요.",
    tone: "neutral",
  },
  detected: {
    label: "GitHub에서 발견",
    description: "watcher가 GitHub 활동에서 규칙 위반을 찾았어요.",
    tone: "notice",
  },
};

/** `gitcoach guide undo` 로 시작한 복구 가이드 (guided + related_event_id → 원래 allowed) */
const RECOVERY_GUIDE_LABEL: LabelInfo = {
  label: "복구 가이드 시작",
  description: "그냥 실행한 명령을 되돌리는 복구 가이드를 시작했어요.",
  tone: "info",
};

/* ------------------------------------------------------------------ */
/* severity                                                            */
/* ------------------------------------------------------------------ */

export const SEVERITY_LABELS: Record<Severity, LabelInfo> = {
  high: { label: "높음", description: "되돌리기 어렵거나 팀 전체에 영향을 줘요.", tone: "danger" },
  medium: { label: "보통", description: "주의가 필요하지만 대체로 되돌릴 수 있어요.", tone: "warning" },
  low: { label: "낮음", description: "규칙 위반이지만 동작에는 문제가 없어요.", tone: "neutral" },
};

/** 정렬용 순서 (심각한 것 먼저) */
export const SEVERITY_ORDER: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

/* ------------------------------------------------------------------ */
/* source                                                              */
/* ------------------------------------------------------------------ */

export const SOURCE_LABELS: Record<EventSource, LabelInfo> = {
  cli: { label: "CLI", description: "터미널의 git 명령에서 잡았어요.", tone: "neutral" },
  github: { label: "GitHub", description: "GitHub의 브랜치·PR·커밋에서 찾았어요.", tone: "neutral" },
};

/* ------------------------------------------------------------------ */
/* rule (짧은 이름만)                                                   */
/* ------------------------------------------------------------------ */

/**
 * 규칙 짧은 이름. CLI v0.1 설계의 규칙 표 기준 임시 문구다.
 * /rules 도감의 "왜 위험한지"·복구 방법 문장은 CLI 템플릿과 같아야 하므로
 * 권아현에게 받은 텍스트로 별도 관리한다. 여기에 길게 쓰지 않는다.
 */
export const RULE_NAMES: Record<string, string> = {
  R01: "main에 직접 push",
  R02: "force push",
  R03: "비밀 정보 커밋",
  R04: "main에서 직접 커밋",
  R05: "브랜치명 규칙 위반",
  R06: "커밋 메시지 규칙 위반",
  R07: "되돌리기 어려운 명령", // v0.2
  R08: "PR 대상 브랜치 오류", // watcher 전용 (feature → main, develop 이어야 함)
};

/* ------------------------------------------------------------------ */
/* 조회 함수 — DB에서 예상 밖의 값이 와도 화면이 깨지지 않게 한다          */
/* ------------------------------------------------------------------ */

function fallback(raw: string): LabelInfo {
  return { label: raw, description: "알 수 없는 값", tone: "neutral" };
}

export function actionLabel(action: EventAction | string): LabelInfo {
  return (ACTION_LABELS as Record<string, LabelInfo>)[action] ?? fallback(action);
}

/** 이벤트 하나의 action 문구. 복구 가이드는 일반 guided 와 다르게 보여 준다. */
export function eventActionLabel(e: Pick<GitCoachEvent, "action" | "related_event_id">): LabelInfo {
  if (e.action === "guided" && e.related_event_id !== null) return RECOVERY_GUIDE_LABEL;
  return actionLabel(e.action);
}

export function severityLabel(severity: Severity | string): LabelInfo {
  return (SEVERITY_LABELS as Record<string, LabelInfo>)[severity] ?? fallback(severity);
}

export function sourceLabel(source: EventSource | string): LabelInfo {
  return (SOURCE_LABELS as Record<string, LabelInfo>)[source] ?? fallback(source);
}

/** 예: "R01 · main에 직접 push". 모르는 규칙이면 ID만 보여 준다. */
export function ruleLabel(ruleId: RuleId): string {
  const name = RULE_NAMES[ruleId];
  return name ? `${ruleId} · ${name}` : ruleId;
}
