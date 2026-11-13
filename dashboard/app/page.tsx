import { connection } from "next/server";
import { Suspense } from "react";
import Card, { CardEmpty } from "@/components/Card";
import FilterRow from "@/components/FilterRow";
import { DailyColumns, RuleBars, SeverityBar } from "@/components/overview/Charts";
import { MemberTable, RecentViolations, ReviewTop3, StalePrList } from "@/components/overview/Lists";
import StatTile from "@/components/overview/StatTile";
import { LoadingState } from "@/components/StateViews";
import { data } from "@/lib/data";
import { hrefToggle, hrefWith, periodRange, readList, type SearchParams } from "@/lib/filters";
import { addDays, formatKstDay, kstDate, shiftRange } from "@/lib/time";
import { isViolation, type Severity } from "@/types/event";

export default function OverviewPage({ searchParams }: PageProps<"/">) {
  return (
    <section>
      <h1 className="text-[22px] font-bold">팀 협업 현황</h1>
      <Suspense fallback={<div className="mt-4"><LoadingState /></div>}>
        <OverviewContent searchParams={searchParams} />
      </Suspense>
    </section>
  );
}

/** 개요는 기간을 "이번 주"(기본)와 "지난 주" 둘만 쓴다 */
type OverviewPeriod = "week" | "lastweek";

async function OverviewContent({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  await connection(); // "이번 주"는 요청 시각 기준
  const now = new Date();

  const period: OverviewPeriod = sp.period === "lastweek" ? "lastweek" : "week";
  const range = periodRange(period, now)!;
  // 비교 기간: 이번 주면 "지난주 같은 시점까지", 지난 주면 "그 전 주 전체"
  const prevFull = shiftRange(range, -7);
  const compare =
    period === "week" ? { from: prevFull.from, to: new Date(now.getTime() - 7 * 86400000).toISOString() } : prevFull;
  const selected = readList(sp, "member");
  const filter = { range, members: selected };

  const [events, prevEvents, ruleStats, guideStats, trend, activity, stalePrs, members] = await Promise.all([
    data.getEvents(filter),
    data.getEvents({ range: compare, members: selected }),
    data.getRuleStats(filter),
    data.getGuideStats(filter),
    data.getDailyTrend(filter),
    data.getMemberActivity(range),
    data.getStalePrs(),
    data.getMembers(),
  ]);

  /* ---------- 숫자 카드 ---------- */
  const violations = events.filter(isViolation);
  const fromCli = violations.filter((e) => e.source === "cli");
  const fromGithub = violations.length - fromCli.length;
  const diff = violations.length - prevEvents.filter(isViolation).length;
  const compareName = period === "week" ? "지난주 같은 때" : "그 전 주";

  const guided = guideStats.reduce((s, g) => s + g.guided_count, 0);
  const completed = guideStats.reduce((s, g) => s + g.completed_count, 0);
  const allowed = fromCli.filter((e) => e.action === "allowed").length;
  const stale = selected.length ? stalePrs.filter((p) => selected.includes(p.author)) : stalePrs;

  const severity: Record<Severity, number> = { high: 0, medium: 0, low: 0 };
  for (const e of violations) severity[e.severity] += 1;

  /* ---------- 링크 (같은 조건으로 타임라인 열기) ---------- */
  const eventsHref = (extra: Record<string, string> = {}) => {
    const q = new URLSearchParams({ period, ...(selected.length ? { member: selected.join(",") } : {}), ...extra });
    return `/events?${q}`;
  };
  const lastDay = addDays(kstDate(range.from), 6);
  const repo = events[0]?.repo;

  return (
    <>
      <p className="mt-1.5 text-muted">
        {repo && <>{repo} · </>}
        {formatKstDay(range.from)} ~ {formatKstDay(`${lastDay}T00:00:00+09:00`)}
      </p>

      {/* 필터는 한 줄에 모아 화면 전체에 적용한다 */}
      <div className="mt-4 mb-5 rounded-card bg-surface px-4 pt-3 pb-1.5 shadow-card">
        <FilterRow
          label="기간"
          all={{ label: "이번 주", href: hrefWith(sp, "period", undefined, "/"), active: period === "week" }}
          chips={[{ label: "지난 주", href: hrefWith(sp, "period", "lastweek", "/"), active: period === "lastweek" }]}
        />
        <FilterRow
          label="멤버"
          all={{ label: "전체", href: hrefWith(sp, "member", undefined, "/"), active: selected.length === 0 }}
          chips={members.map((m) => ({ label: m, href: hrefToggle(sp, "member", m, "/"), active: selected.includes(m) }))}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        {/* ---------------- 왼쪽 ---------------- */}
        <div className="min-w-0 space-y-5">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <StatTile
              hero
              label={period === "week" ? "이번 주 위반" : "지난 주 위반"}
              value={String(violations.length)}
              unit="건"
              note={
                <>
                  CLI {fromCli.length} · GitHub {fromGithub}
                  <br />
                  {diff === 0 ? (
                    <>{compareName}와 같아요</>
                  ) : (
                    <>
                      {compareName}보다 <b>{Math.abs(diff)}건 {diff < 0 ? "줄었어요" : "늘었어요"}</b>
                    </>
                  )}
                </>
              }
            />
            <StatTile
              label="가이드 완료율"
              value={guided ? String(Math.round((completed / guided) * 100)) : "–"}
              unit={guided ? "%" : undefined}
              note={guided ? `가이드 ${guided}번 중 ${completed}번 완료` : "아직 시작한 가이드가 없어요"}
            />
            <StatTile
              label="그냥 실행 비율"
              value={fromCli.length ? String(Math.round((allowed / fromCli.length) * 100)) : "–"}
              unit={fromCli.length ? "%" : undefined}
              note={`경고를 보고도 실행 ${allowed}번 (CLI 위반 ${fromCli.length}건 중)`}
            />
            <StatTile label="방치된 PR" value={String(stale.length)} unit="개" note="3일 이상 활동 없음 · 지금 기준" />
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Card title="규칙별 위반" hint="막대를 누르면 타임라인으로">
              {ruleStats.length ? (
                <RuleBars stats={ruleStats} hrefFor={(rule) => eventsHref({ rule })} />
              ) : (
                <CardEmpty message="이 기간에는 위반이 없어요 🎉" />
              )}
            </Card>
            <Card title="일별 위반 추이">
              <DailyColumns days={trend} today={kstDate(now.toISOString())} />
            </Card>
          </div>

          <Card
            title={period === "week" ? "이번 주 리뷰 TOP 3" : "지난 주 리뷰 TOP 3"}
            hint="서로 리뷰를 많이 해 준 팀원 · 위반 랭킹은 만들지 않아요"
          >
            <ReviewTop3 members={activity} />
            <div className="mt-6">
              <MemberTable members={activity} selected={selected} />
            </div>
            <p className="mt-3 text-[11px] text-muted">
              리뷰한 PR은 같은 PR에 여러 번 리뷰해도 1로 세고, 자기 PR에 단 리뷰는 빼요. 표는 멤버 필터와 상관없이 팀 전체를 보여 줘요.
            </p>
          </Card>
        </div>

        {/* ---------------- 오른쪽 ---------------- */}
        <aside className="min-w-0 space-y-5">
          <Card title="방치된 PR">
            <StalePrList prs={stale} />
          </Card>
          <Card title="심각도 분포">
            {violations.length ? <SeverityBar counts={severity} /> : <CardEmpty message="위반이 없어요" />}
          </Card>
          <Card title="최근 위반">
            <RecentViolations events={violations.slice(0, 3)} moreHref={eventsHref()} />
          </Card>
        </aside>
      </div>
    </>
  );
}
