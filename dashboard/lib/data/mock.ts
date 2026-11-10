// mock 데이터 소스. 레포 맨 위 samples/*.json(스키마 v1 더미 20건)을 그대로 쓴다.
// 화면은 이 파일을 직접 부르지 않고 `data`(lib/data/index.ts)만 부른다.
// 11/19~20 supabaseSource 로 바꿔도 반환 형태는 같아야 한다.
import type {
  DailyCount,
  DataSource,
  EventFilter,
  GuideStat,
  MemberActivity,
  RuleStat,
} from "@/lib/data";
import { addDays, kstDate } from "@/lib/time";
import {
  EVENT_ACTIONS,
  EVENT_SOURCES,
  SEVERITIES,
  isViolation,
  type GitCoachEvent,
} from "@/types/event";
import samples from "./mock/sample-events.json";

/** JSON 값이 스키마 v1 값 목록 안에 있는지 확인하고 타입을 붙인다 (잘못된 샘플을 빨리 찾기 위함) */
function toEvents(raw: unknown[]): GitCoachEvent[] {
  return raw.map((r, i) => {
    const e = r as GitCoachEvent;
    const ok =
      e.schema_version === 1 &&
      (EVENT_ACTIONS as readonly string[]).includes(e.action) &&
      (EVENT_SOURCES as readonly string[]).includes(e.source) &&
      (SEVERITIES as readonly string[]).includes(e.severity);
    if (!ok) throw new Error(`sample-events.json ${i}번째 이벤트가 스키마 v1과 맞지 않아요: ${e.id}`);
    return e;
  });
}

const EVENTS = toEvents(samples);

/** 필터 적용. 배열이 비었거나 없으면 그 조건은 "전체" */
function applyFilter(events: GitCoachEvent[], f: EventFilter = {}): GitCoachEvent[] {
  const has = <T>(list: T[] | undefined, v: T) => !list || list.length === 0 || list.includes(v);
  const from = f.range ? Date.parse(f.range.from) : -Infinity;
  const to = f.range ? Date.parse(f.range.to) : Infinity;
  const q = f.query?.trim().toLowerCase();
  const matches = (e: GitCoachEvent) =>
    !q ||
    [e.command_summary, e.branch, e.pr_number === null ? null : `#${e.pr_number}`].some((v) =>
      v?.toLowerCase().includes(q),
    );
  return events.filter((e) => {
    const t = Date.parse(e.occurred_at);
    return (
      matches(e) &&
      t >= from &&
      t < to &&
      has(f.members, e.member) &&
      has(f.ruleIds, e.rule_id) &&
      has(f.sources, e.source) &&
      has(f.severities, e.severity) &&
      has(f.actions, e.action) &&
      (!f.repo || e.repo === f.repo)
    );
  });
}

const newestFirst = (a: GitCoachEvent, b: GitCoachEvent) =>
  Date.parse(b.occurred_at) - Date.parse(a.occurred_at);

export const mockSource: DataSource = {
  async getEvents(filter) {
    return applyFilter(EVENTS, filter).sort(newestFirst);
  },

  async getRuleStats(filter) {
    const violations = applyFilter(EVENTS, filter).filter(isViolation);
    const byRule = new Map<string, RuleStat>();
    for (const e of violations) {
      const s =
        byRule.get(e.rule_id) ??
        ({
          rule_id: e.rule_id,
          severity: e.severity,
          violation_count: 0,
          allowed_count: 0,
          guided_count: 0,
          blocked_count: 0,
          detected_count: 0,
          ratio: 0,
        } satisfies RuleStat);
      s.violation_count += 1;
      if (e.action === "allowed") s.allowed_count += 1;
      if (e.action === "guided") s.guided_count += 1;
      if (e.action === "blocked") s.blocked_count += 1;
      if (e.action === "detected") s.detected_count += 1;
      byRule.set(e.rule_id, s);
    }
    const total = violations.length;
    return [...byRule.values()]
      .map((s) => ({ ...s, ratio: total ? s.violation_count / total : 0 }))
      .sort((a, b) => b.violation_count - a.violation_count);
  },

  async getGuideStats(filter) {
    // 분모: 필터에 맞는 guided (복구 가이드 포함). 결과는 기간 밖에 끝났어도 찾는다.
    const guided = applyFilter(EVENTS, filter).filter((e) => e.action === "guided");
    const results = EVENTS.filter((e) => e.action === "guide_completed" || e.action === "guide_stopped");
    const byRule = new Map<string, GuideStat>();
    for (const g of guided) {
      const s =
        byRule.get(g.rule_id) ??
        ({
          rule_id: g.rule_id,
          guided_count: 0,
          completed_count: 0,
          stopped_count: 0,
          in_progress_count: 0,
          completion_rate: 0,
        } satisfies GuideStat);
      const mine = results.filter((r) => r.related_event_id === g.id);
      s.guided_count += 1;
      if (mine.some((r) => r.action === "guide_completed")) s.completed_count += 1;
      else if (mine.some((r) => r.action === "guide_stopped")) s.stopped_count += 1;
      else s.in_progress_count += 1;
      byRule.set(g.rule_id, s);
    }
    return [...byRule.values()].map((s) => ({
      ...s,
      completion_rate: s.guided_count ? s.completed_count / s.guided_count : 0,
    }));
  },

  async getDailyTrend(filter) {
    const counts = new Map<string, number>();
    for (const e of applyFilter(EVENTS, filter).filter(isViolation)) {
      const d = kstDate(e.occurred_at);
      counts.set(d, (counts.get(d) ?? 0) + 1);
    }
    if (filter?.range) {
      // 빈 날도 0으로 채운다 (to 는 미포함)
      const last = kstDate(new Date(Date.parse(filter.range.to) - 1).toISOString());
      for (let d = kstDate(filter.range.from); d <= last; d = addDays(d, 1)) {
        if (!counts.has(d)) counts.set(d, 0);
      }
    }
    return [...counts.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, violation_count]) => ({ date, violation_count }) satisfies DailyCount);
  },

  async getMemberActivity(range) {
    // mock에는 PR·리뷰 데이터가 없다. watcher JSON(prs·pr_reviews)이 나오면 채운다.
    const byMember = new Map<string, MemberActivity>();
    for (const e of applyFilter(EVENTS, { range }).filter(isViolation)) {
      const m =
        byMember.get(e.member) ??
        { member: e.member, prs_opened: 0, prs_merged: 0, reviews_given: 0, violation_count: 0 };
      m.violation_count += 1;
      byMember.set(e.member, m);
    }
    return [...byMember.values()].sort((a, b) => a.member.localeCompare(b.member));
  },

  async getStalePrs() {
    return []; // mock에는 PR 데이터가 없다
  },

  async getQuizzes() {
    return []; // 퀴즈는 watcher가 11/24~26에 만든다
  },

  async getQuizAttempts() {
    return []; // v0.1은 풀이를 저장하지 않는다 (D5)
  },
};
