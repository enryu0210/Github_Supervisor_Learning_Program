import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import Card, { CardEmpty } from "@/components/Card";
import EventCard from "@/components/EventCard";
import SegmentedBar from "@/components/SegmentedBar";
import { LoadingState } from "@/components/StateViews";
import { data } from "@/lib/data";
import { RULE_NAMES, actionLabel } from "@/lib/labels";
import { thisWeekRange } from "@/lib/time";
import { CURRENT_USER } from "@/lib/user";
import { isViolation, type EventAction, type GitCoachEvent } from "@/types/event";

// /me 내 기록 (와이어프레임 03-me)
// - 로그인 전이라 현재 사용자는 lib/user.ts 의 CURRENT_USER 로 고정한다
// - 퀴즈 정답률 카드는 넣지 않는다: v0.1은 풀이 기록을 저장하지 않는다 (D5)
// - 자주 틀린 규칙·선택 습관은 전체 기간, 머리말의 칭찬 문장은 이번 주 기준

export default function MePage() {
  return (
    <section>
      <h1 className="text-[22px] font-bold">{CURRENT_USER} 님의 Git 학습 기록</h1>
      <Suspense fallback={<div className="mt-4"><LoadingState /></div>}>
        <MeContent />
      </Suspense>
    </section>
  );
}

/** 위반 칸에 쓰는 action 별 짧은 문구 */
const BREAKDOWN: { action: EventAction; key: "allowed_count" | "guided_count" | "blocked_count" | "detected_count" }[] = [
  { action: "allowed", key: "allowed_count" },
  { action: "guided", key: "guided_count" },
  { action: "blocked", key: "blocked_count" },
  { action: "detected", key: "detected_count" },
];

async function MeContent() {
  await connection(); // "이번 주"·"오늘"은 요청 시각 기준
  const me = CURRENT_USER;
  const mine = { members: [me] };
  const week = thisWeekRange();

  const [events, ruleStats, guideStats, weekGuides, quizzes] = await Promise.all([
    data.getEvents(mine),
    data.getRuleStats(mine),
    data.getGuideStats(mine),
    data.getGuideStats({ ...mine, range: week }),
    data.getQuizzes(me),
  ]);

  const violations = events.filter(isViolation);
  const recent = violations.slice(0, 4);
  const related = await data.getRelatedEvents(recent.map((e) => e.id));

  /* ---------- 머리말 칭찬 문장 (이번 주) ---------- */
  const weekCompleted = weekGuides.reduce((s, g) => s + g.completed_count, 0);
  const cheer =
    weekCompleted > 0
      ? `조금씩 나아지고 있어요. 이번 주 가이드를 ${weekCompleted}번 끝까지 했어요.`
      : "이번 주는 아직 끝까지 마친 가이드가 없어요. 다음 경고 때 [2] 가이드를 골라 보세요.";

  /* ---------- 선택 습관 (CLI 에서 경고를 받았을 때 고른 것) ---------- */
  // detected 는 CLI 경고를 거치지 않았으니 빼고, 복구 가이드도 다시 세지 않는다 (isViolation)
  const cli = violations.filter((e) => e.source === "cli");
  const count = (a: EventAction) => cli.filter((e) => e.action === a).length;
  const habit = { guided: count("guided"), allowed: count("allowed"), blocked: count("blocked") };
  const guidedShare = cli.length ? Math.round((habit.guided / cli.length) * 100) : 0;

  return (
    <>
      <p className="mt-1.5 mb-5 text-muted">{cheer}</p>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        {/* ---------------- 왼쪽 ---------------- */}
        <div className="min-w-0 space-y-5">
          <ReviewBanner quizzes={quizzes} events={events} />

          <section>
            <h2 className="mb-3 text-[15px] font-bold">내가 자주 틀린 규칙 TOP 3</h2>
            {ruleStats.length === 0 ? (
              <div className="rounded-card bg-surface shadow-card">
                <CardEmpty message="아직 위반 기록이 없어요 🎉" />
              </div>
            ) : (
              <ol className="grid gap-4 sm:grid-cols-3">
                {ruleStats.slice(0, 3).map((s, i) => (
                  <li key={s.rule_id} className="rounded-card bg-surface p-5 shadow-card">
                    <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-bold text-accent">
                      {i + 1}위
                    </span>
                    <p className="mt-2.5 truncate text-sm font-bold">
                      {s.rule_id} {RULE_NAMES[s.rule_id] ?? ""}
                    </p>
                    <p className="mt-2 text-[30px] leading-none font-bold">
                      {s.violation_count}
                      <span className="ml-0.5 text-lg">회</span>
                    </p>
                    <p className="mt-2.5 text-xs text-muted">
                      {BREAKDOWN.filter((b) => s[b.key] > 0)
                        .map((b) => `${actionLabel(b.action).label} ${s[b.key]}`)
                        .join(" · ")}
                    </p>
                    <Link
                      href={`/rules?rule=${s.rule_id}`}
                      className="mt-3 inline-block text-[13px] font-semibold text-accent"
                    >
                      규칙 도감 보기 →
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <Card
            title="내 최근 기록"
            hint={
              <Link href={`/events?member=${me}`} className="text-[13px] font-semibold text-accent">
                전체 보기 →
              </Link>
            }
          >
            {recent.length === 0 ? (
              <CardEmpty message="아직 기록이 없어요" />
            ) : (
              recent.map((e) => (
                <EventCard
                  key={e.id}
                  event={e}
                  linked={related.filter((l) => l.related_event_id === e.id && l.action !== "guided")}
                />
              ))
            )}
          </Card>
        </div>

        {/* ---------------- 오른쪽 ---------------- */}
        <aside className="min-w-0 space-y-5">
          <Card title="규칙별 가이드 완료">
            {guideStats.length === 0 ? (
              <CardEmpty message="아직 시작한 가이드가 없어요" />
            ) : (
              <ul className="space-y-3.5">
                {guideStats.map((g) => {
                  const done = g.guided_count > 0 && g.completed_count === g.guided_count;
                  return (
                    <li key={g.rule_id} title={`완료 ${g.completed_count} · 중단 ${g.stopped_count} · 진행 중 ${g.in_progress_count}`}>
                      <div className="mb-1.5 flex justify-between text-[13px]">
                        <span className="truncate">
                          {g.rule_id} {RULE_NAMES[g.rule_id] ?? ""}
                        </span>
                        <span className="tabular-nums">
                          {g.completed_count}/{g.guided_count}
                          {done && <span className="ml-1 text-ok">✓</span>}
                        </span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-accent-light">
                        <div
                          className={`h-full rounded-full ${done ? "bg-ok" : "bg-accent"}`}
                          style={{ width: `${g.completion_rate * 100}%` }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="mt-4 text-[11px] text-muted">가이드를 시작한 횟수 중 끝까지 마친 횟수예요. 복구 가이드도 포함해요.</p>
          </Card>

          <Card title="나의 선택 습관">
            {cli.length === 0 ? (
              <CardEmpty message="CLI 경고 기록이 없어요" />
            ) : (
              <>
                <p className="mb-3 text-sm text-muted">
                  경고를 받았을 때 가이드를 고른 비율
                  <b className="mt-1 block text-[28px] leading-none text-text">{guidedShare}%</b>
                </p>
                <SegmentedBar
                  unit="번"
                  parts={[
                    { key: "guided", label: "가이드 시작", value: habit.guided, fill: "bg-accent" },
                    { key: "allowed", label: "그냥 실행", value: habit.allowed, fill: "bg-medium", ink: "dark" },
                    { key: "blocked", label: "실행 막힘", value: habit.blocked, fill: "bg-high" },
                  ]}
                />
                <p className="mt-3 text-[11px] text-muted">GitHub에서 발견된 위반은 CLI 경고를 거치지 않아 빼고 셌어요.</p>
              </>
            )}
          </Card>
        </aside>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* 오늘의 복습 — 퀴즈가 있으면 /quiz 로 안내                              */
/* ------------------------------------------------------------------ */

function ReviewBanner({ quizzes, events }: { quizzes: Awaited<ReturnType<typeof data.getQuizzes>>; events: GitCoachEvent[] }) {
  if (quizzes.length === 0) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card bg-accent-soft px-6 py-5">
        <div>
          <p className="font-bold">📚 오늘의 복습</p>
          <p className="mt-1 text-sm text-muted">아직 준비된 복습 문제가 없어요. 규칙 도감에서 규칙을 미리 읽어 볼 수 있어요.</p>
        </div>
        <Link href="/rules" className="rounded-lg bg-surface px-4 py-2 text-sm font-semibold text-accent shadow-card">
          규칙 도감 →
        </Link>
      </div>
    );
  }

  // 가장 최근 문제의 근거 이벤트로 안내 문장을 만든다
  const latest = quizzes[0];
  const source = events.find((e) => e.id === latest.source_event_id);
  const why = source?.action === "allowed" ? "그냥 실행한" : source?.action === "guide_stopped" ? "가이드를 중단한" : "최근";
  const sameRule = quizzes.filter((q) => q.rule_id === latest.rule_id).length;
  const name = RULE_NAMES[latest.rule_id];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-card bg-accent px-6 py-5 text-white shadow-card">
      <div>
        <p className="font-bold">📚 오늘의 복습</p>
        <p className="mt-1 text-sm text-white/90">
          {why} {latest.rule_id}
          {name && `(${name})`} 관련 문제 {sameRule}개를 포함해 모두 {quizzes.length}개가 준비됐어요.
        </p>
      </div>
      <Link href="/quiz" className="rounded-lg bg-surface px-4 py-2 text-sm font-semibold text-accent">
        퀴즈 풀기 →
      </Link>
    </div>
  );
}
