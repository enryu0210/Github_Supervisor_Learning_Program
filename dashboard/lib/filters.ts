// URL 쿼리 ↔ EventFilter 변환. 필터 상태는 URL 한 곳에만 둔다 (웹 가이드 3-5).
// 같은 쿼리를 개요 차트에서도 쓰면 타임라인과 함께 바뀐다.
//   /events?member=a,b&rule=R01&source=cli&severity=high&action=allowed&period=week&q=main&sort=asc
//   개요(/)는 period(week·lastweek)와 member 만 쓴다. 차트를 누르면 같은 쿼리로 /events 에 간다.
import type { EventFilter } from "@/lib/data";
import { lastWeekRange, thisWeekRange, todayRange } from "@/lib/time";
import { EVENT_ACTIONS, EVENT_SOURCES, SEVERITIES } from "@/types/event";
import type { EventAction, EventSource, Severity } from "@/types/event";

export type SearchParams = Record<string, string | string[] | undefined>;

export const PERIODS = [
  { value: "today", label: "오늘" },
  { value: "week", label: "이번 주" },
  { value: "lastweek", label: "지난 주" },
  { value: "all", label: "전체" },
] as const;
export type Period = (typeof PERIODS)[number]["value"];

/** 여러 값 쿼리 키 (쉼표로 구분) */
export const LIST_KEYS = ["member", "rule", "source", "severity", "action"] as const;
export type ListKey = (typeof LIST_KEYS)[number];

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export function readList(sp: SearchParams, key: ListKey): string[] {
  return (first(sp[key]) ?? "").split(",").filter(Boolean);
}

function only<T extends string>(values: string[], allowed: readonly T[]): T[] {
  return values.filter((v): v is T => (allowed as readonly string[]).includes(v));
}

export function readPeriod(sp: SearchParams): Period {
  const p = first(sp.period);
  return p === "today" || p === "week" || p === "lastweek" ? p : "all";
}

export function readSort(sp: SearchParams): "asc" | "desc" {
  return first(sp.sort) === "asc" ? "asc" : "desc";
}

export function readQuery(sp: SearchParams): string {
  return first(sp.q)?.trim() ?? "";
}

/** 기간 값 → 범위 ("all" 이면 undefined) */
export function periodRange(period: Period, now = new Date()) {
  if (period === "today") return todayRange(now);
  if (period === "week") return thisWeekRange(now);
  if (period === "lastweek") return lastWeekRange(now);
  return undefined;
}

/** URL 쿼리 → 데이터 계층에 넘길 필터 */
export function toEventFilter(sp: SearchParams, now = new Date()): EventFilter {
  const period = readPeriod(sp);
  return {
    range: periodRange(period, now),
    members: readList(sp, "member"),
    ruleIds: readList(sp, "rule"),
    sources: only<EventSource>(readList(sp, "source"), EVENT_SOURCES),
    severities: only<Severity>(readList(sp, "severity"), SEVERITIES),
    actions: only<EventAction>(readList(sp, "action"), EVENT_ACTIONS),
    query: readQuery(sp) || undefined,
  };
}

/** 현재 쿼리에서 key 하나만 바꾼 주소. value 가 undefined 면 그 키를 지운다. path 기본값은 /events */
export function hrefWith(sp: SearchParams, key: string, value: string | undefined, path = "/events"): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    const s = first(v);
    if (s && k !== key) params.set(k, s);
  }
  if (value) params.set(key, value);
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

/** 여러 값 키에서 value 하나를 켜고 끈 주소 */
export function hrefToggle(sp: SearchParams, key: ListKey, value: string, path = "/events"): string {
  const current = readList(sp, key);
  const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
  return hrefWith(sp, key, next.length ? next.join(",") : undefined, path);
}

/** 필터가 하나라도 걸려 있는지 (빈 상태에서 "필터 초기화"를 보여 줄지) */
export function hasAnyFilter(sp: SearchParams): boolean {
  return LIST_KEYS.some((k) => readList(sp, k).length > 0) || readPeriod(sp) !== "all" || !!readQuery(sp);
}
