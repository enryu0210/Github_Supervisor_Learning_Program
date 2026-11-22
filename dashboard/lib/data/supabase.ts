// Supabase 데이터 소스. 남주님 #105 뷰·RPC를 그대로 부른다 (대응표: #94, docs/db/ERD.md "조회 뷰 · RPC")
// - 모든 호출은 로그인 사용자 세션으로 한다 → RLS 로 "내 팀" 데이터만 온다. 로그인 없으면 401
// - 반환 컬럼은 lib/data/index.ts 타입과 같게 DB 가 맞춰 준다. 여기서는 이름만 이어 붙인다
// - 시간은 UTC(+00:00) 문자열로 온다. 화면은 Date.parse·Intl(Asia/Seoul)로만 다뤄서 그대로 써도 된다
import type { DailyCount, DataSource, EventFilter, GuideStat, MemberActivity, Quiz, QuizAttempt, RuleStat, StalePr } from "@/lib/data";
import { createClient } from "@/lib/supabase/server";
import { RULE_DEFAULT_SEVERITY, type GitCoachEvent } from "@/types/event";

/** 빈 배열·빈 문자열은 "전체" → null 로 보낸다 */
const listArg = (v?: readonly string[]) => (v && v.length ? [...v] : null);

/** EventFilter → RPC 이름 있는 인자 9개 (#94 2번) */
function filterArgs(f: EventFilter = {}) {
  return {
    p_from: f.range?.from ?? null,
    p_to: f.range?.to ?? null,
    p_members: listArg(f.members),
    p_rule_ids: listArg(f.ruleIds),
    p_sources: listArg(f.sources),
    p_severities: listArg(f.severities),
    p_actions: listArg(f.actions),
    p_repo: f.repo || null,
    p_query: f.query?.trim() || null,
  };
}

/** 오류는 화면의 error.tsx 가 받는다. 무엇이 실패했는지만 남기고 세부 내용은 서버 로그로 */
function check<T>(what: string, res: { data: T | null; error: { message: string; code?: string } | null }): T {
  if (res.error) {
    console.error(`[supabaseSource] ${what} 실패:`, res.error.code, res.error.message);
    throw new Error(`${what}을(를) 불러오지 못했어요`);
  }
  return (res.data ?? []) as T;
}

/** .in() 은 주소(URL)에 실리므로 id 가 많으면 나눠서 부른다 */
const CHUNK = 100;

export const supabaseSource: DataSource = {
  async getEvents(filter) {
    const db = await createClient();
    return check<GitCoachEvent[]>("위반 기록", await db.rpc("get_events", filterArgs(filter)));
  },

  async getRelatedEvents(ids) {
    if (ids.length === 0) return [];
    const db = await createClient();
    const out: GitCoachEvent[] = [];
    for (let i = 0; i < ids.length; i += CHUNK) {
      const res = await db
        .from("v_events")
        .select("*")
        .in("related_event_id", ids.slice(i, i + CHUNK))
        .order("occurred_at", { ascending: true });
      out.push(...check<GitCoachEvent[]>("이어진 기록", res));
    }
    return out.sort((a, b) => Date.parse(a.occurred_at) - Date.parse(b.occurred_at));
  },

  async getMembers() {
    const db = await createClient();
    const rows = check<{ member: string }[]>("멤버 목록", await db.from("v_members").select("member").order("member"));
    return rows.map((r) => r.member);
  },

  async getRuleStats(filter) {
    const db = await createClient();
    const rows = check<RuleStat[]>("규칙별 통계", await db.rpc("get_rule_stats", filterArgs(filter)));
    // DB 는 "그 규칙 이벤트 중 가장 높은 severity"를 준다. 화면은 규칙 표 기본값을 쓴다 (#94 4번, R02 = high)
    return rows.map((r) => ({ ...r, severity: RULE_DEFAULT_SEVERITY[r.rule_id] ?? r.severity }));
  },

  async getGuideStats(filter) {
    const db = await createClient();
    return check<GuideStat[]>("가이드 통계", await db.rpc("get_guide_stats", filterArgs(filter)));
  },

  async getDailyTrend(filter) {
    const db = await createClient();
    return check<DailyCount[]>("일별 추이", await db.rpc("get_daily_trend", filterArgs(filter)));
  },

  async getMemberActivity(range) {
    const db = await createClient();
    return check<MemberActivity[]>(
      "멤버별 활동",
      await db.rpc("get_member_activity", { p_from: range.from, p_to: range.to }),
    );
  },

  async getStalePrs() {
    const db = await createClient();
    return check<StalePr[]>(
      "방치된 PR",
      await db.from("v_stale_prs").select("*").order("idle_days", { ascending: false }),
    );
  },

  async getQuizzes(member) {
    const db = await createClient();
    return check<Quiz[]>(
      "복습 퀴즈",
      await db.from("v_quizzes").select("*").eq("member", member).order("created_at", { ascending: false }),
    );
  },

  async getQuizAttempts(member) {
    const db = await createClient();
    return check<QuizAttempt[]>(
      "퀴즈 풀이",
      await db.from("v_quiz_attempts").select("*").eq("member", member).order("attempted_at", { ascending: false }),
    );
  },
};
