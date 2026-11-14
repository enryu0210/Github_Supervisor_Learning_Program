// mock 데이터 소스. 다음 두 가지를 합쳐서 쓴다.
//   1) samples/*.json   — CLI 계약용 더미 20건 (npm run samples:sync 로 복사, 날짜 그대로)
//   2) synthetic.json   — 대시보드 화면용 합성 데이터 3주치 (npm run synthetic:gen 으로 생성)
// 화면은 이 파일을 직접 부르지 않고 `data`(lib/data/index.ts)만 부른다.
// 11/19~20 supabaseSource 로 바꿔도 반환 형태는 같아야 한다.
import type {
  DailyCount,
  DataSource,
  EventFilter,
  GuideStat,
  MemberActivity,
  Quiz,
  RuleStat,
  StalePr,
} from "@/lib/data";
import { addDays, kstDate, thisWeekRange } from "@/lib/time";
import {
  EVENT_ACTIONS,
  EVENT_SOURCES,
  RULE_DEFAULT_SEVERITY,
  SEVERITIES,
  isViolation,
  type GitCoachEvent,
} from "@/types/event";
import samples from "./mock/sample-events.json";
import synthetic from "./mock/synthetic.json";

/** PR (samples/watcher/prs_sample.json 형식) */
type MockPr = {
  repo: string;
  number: number;
  title: string;
  author: string;
  state: string; // "open" | "closed"
  opened_at: string;
  merged_at: string | null;
  reviewers: string[];
  last_activity_at: string;
};

/** PR 리뷰 (samples/watcher/pr_reviews_sample.json 형식) */
type MockReview = {
  review_id: number;
  repo: string;
  pr_number: number;
  reviewer: string;
  status: string;
  submitted_at: string;
};

const DAY_MS = 24 * 60 * 60 * 1000;
const STALE_DAYS = 3; // D3: 방치 PR 기준 3일

/** JSON 값이 스키마 v1 값 목록 안에 있는지 확인하고 타입을 붙인다 (잘못된 데이터를 빨리 찾기 위함) */
function toEvents(raw: unknown[], file: string): GitCoachEvent[] {
  return raw.map((r, i) => {
    const e = r as GitCoachEvent;
    const ok =
      e.schema_version === 1 &&
      (EVENT_ACTIONS as readonly string[]).includes(e.action) &&
      (EVENT_SOURCES as readonly string[]).includes(e.source) &&
      (SEVERITIES as readonly string[]).includes(e.severity);
    if (!ok) throw new Error(`${file} ${i}번째 이벤트가 스키마 v1과 맞지 않아요: ${e.id}`);
    return e;
  });
}

const SAMPLE_EVENTS = toEvents(samples, "sample-events.json");
const SYN_EVENTS = toEvents(synthetic.events, "synthetic.json");
const SYN_PRS: MockPr[] = synthetic.prs;
const SYN_REVIEWS: MockReview[] = synthetic.pr_reviews;
const SYN_QUIZZES: Quiz[] = synthetic.quizzes;

/* ------------------------------------------------------------------ */
/* 합성 데이터 날짜 옮기기                                               */
/* 합성 데이터는 anchor_monday 주를 "이번 주"로 만들어 두었다.            */
/* 화면을 여는 날이 속한 주로 통째로(주 단위) 옮기고, 아직 오지 않은 시각은 뺀다. */
/* 시각을 쓰므로 반드시 요청 처리 중(connection() 뒤)에 불러야 한다.       */
/* ------------------------------------------------------------------ */

type Dataset = { events: GitCoachEvent[]; prs: MockPr[]; reviews: MockReview[]; quizzes: Quiz[]; now: number };

/** ISO 시각에 ms 를 더해 다시 "+09:00" 형식으로 */
function shiftIso(iso: string, ms: number): string {
  if (ms === 0) return iso;
  return new Date(Date.parse(iso) + ms + 9 * 3600000).toISOString().replace(/\.\d{3}Z$/, "+09:00");
}

let cache: { key: string; value: Dataset } | null = null;

function dataset(): Dataset {
  const now = Date.now();
  const week = thisWeekRange(new Date(now));
  const shift = Date.parse(week.from) - Date.parse(`${synthetic.anchor_monday}T00:00:00+09:00`);
  const key = `${shift}:${Math.floor(now / 60000)}`; // 1분마다 "지금" 기준을 새로 잡는다
  if (cache?.key === key) return cache.value;

  const past = (iso: string | null) => iso !== null && Date.parse(iso) <= now;

  const events = [
    ...SAMPLE_EVENTS,
    ...SYN_EVENTS.map((e) => ({ ...e, occurred_at: shiftIso(e.occurred_at, shift) })),
  ].filter((e) => past(e.occurred_at));

  const reviews = SYN_REVIEWS.map((r) => ({ ...r, submitted_at: shiftIso(r.submitted_at, shift) })).filter((r) =>
    past(r.submitted_at),
  );

  const prs = SYN_PRS.map((p) => ({
    ...p,
    opened_at: shiftIso(p.opened_at, shift),
    merged_at: p.merged_at && shiftIso(p.merged_at, shift),
    last_activity_at: shiftIso(p.last_activity_at, shift),
  }))
    .filter((p) => past(p.opened_at))
    .map((p) => {
      if (past(p.merged_at)) return p;
      // 아직 머지 전: 열린 PR 로 보고, 마지막 활동은 지금까지 있었던 리뷰 기준
      const seen = reviews.filter((r) => r.pr_number === p.number).map((r) => r.submitted_at);
      const last = [p.opened_at, ...seen, ...(past(p.last_activity_at) ? [p.last_activity_at] : [])].sort().at(-1)!;
      return { ...p, state: "open", merged_at: null, last_activity_at: last };
    });

  const quizzes = SYN_QUIZZES.map((q) => ({ ...q, created_at: shiftIso(q.created_at, shift) })).filter((q) =>
    past(q.created_at),
  );

  const value = { events, prs, reviews, quizzes, now };
  cache = { key, value };
  return value;
}

/* ------------------------------------------------------------------ */
/* 필터                                                                 */
/* ------------------------------------------------------------------ */

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

const inRange = (iso: string | null, from: number, to: number) => {
  if (iso === null) return false;
  const t = Date.parse(iso);
  return t >= from && t < to;
};

/* ------------------------------------------------------------------ */
/* DataSource 구현                                                      */
/* ------------------------------------------------------------------ */

export const mockSource: DataSource = {
  async getEvents(filter) {
    return applyFilter(dataset().events, filter).sort(newestFirst);
  },

  async getRelatedEvents(ids) {
    const want = new Set(ids);
    return dataset()
      .events.filter((e) => e.related_event_id !== null && want.has(e.related_event_id))
      .sort((a, b) => -newestFirst(a, b));
  },

  async getMembers() {
    const { events, prs, reviews } = dataset();
    const all = [...events.map((e) => e.member), ...prs.map((p) => p.author), ...reviews.map((r) => r.reviewer)];
    return [...new Set(all)].sort();
  },

  async getRuleStats(filter) {
    const violations = applyFilter(dataset().events, filter).filter(isViolation);
    const byRule = new Map<string, RuleStat>();
    for (const e of violations) {
      const s =
        byRule.get(e.rule_id) ??
        ({
          rule_id: e.rule_id,
          severity: RULE_DEFAULT_SEVERITY[e.rule_id] ?? e.severity, // 규칙 기본값 (R02 = high)
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
    const { events } = dataset();
    const guided = applyFilter(events, filter).filter((e) => e.action === "guided");
    const results = events.filter((e) => e.action === "guide_completed" || e.action === "guide_stopped");
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
    return [...byRule.values()]
      .map((s) => ({ ...s, completion_rate: s.guided_count ? s.completed_count / s.guided_count : 0 }))
      .sort((a, b) => a.rule_id.localeCompare(b.rule_id));
  },

  async getDailyTrend(filter) {
    const counts = new Map<string, number>();
    for (const e of applyFilter(dataset().events, filter).filter(isViolation)) {
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
    const { events, prs, reviews } = dataset();
    const from = Date.parse(range.from);
    const to = Date.parse(range.to);
    const members = await mockSource.getMembers();
    const authorOf = new Map(prs.map((p) => [`${p.repo}#${p.number}`, p.author]));

    return members.map((member) => {
      // 리뷰한 PR 수: 같은 PR 여러 번 = 1, 작성자 본인 리뷰 제외
      const reviewed = new Set(
        reviews
          .filter(
            (r) =>
              r.reviewer === member &&
              inRange(r.submitted_at, from, to) &&
              authorOf.get(`${r.repo}#${r.pr_number}`) !== member,
          )
          .map((r) => `${r.repo}#${r.pr_number}`),
      );
      return {
        member,
        prs_opened: prs.filter((p) => p.author === member && inRange(p.opened_at, from, to)).length,
        prs_merged: prs.filter((p) => p.author === member && inRange(p.merged_at, from, to)).length,
        reviews_given: reviewed.size,
        violation_count: applyFilter(events, { range, members: [member] }).filter(isViolation).length,
      } satisfies MemberActivity;
    });
  },

  async getStalePrs() {
    const { prs, now } = dataset();
    return prs
      .filter((p) => p.state === "open")
      .map(
        (p) =>
          ({
            repo: p.repo,
            pr_number: p.number,
            title: p.title,
            author: p.author,
            opened_at: p.opened_at,
            last_activity_at: p.last_activity_at,
            idle_days: Math.floor((now - Date.parse(p.last_activity_at)) / DAY_MS),
            url: `https://github.com/${p.repo}/pull/${p.number}`,
          }) satisfies StalePr,
      )
      .filter((p) => p.idle_days >= STALE_DAYS)
      .sort((a, b) => b.idle_days - a.idle_days);
  },

  async getQuizzes(member) {
    return dataset()
      .quizzes.filter((q) => q.member === member)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  },

  async getQuizAttempts() {
    return []; // v0.1은 풀이를 저장하지 않는다 (D5)
  },
};
