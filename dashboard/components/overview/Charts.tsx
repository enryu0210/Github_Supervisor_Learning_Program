// 개요 차트 3개. 라이브러리 없이 HTML·CSS로 그린다 (값이 적고 서버에서 바로 그릴 수 있어서).
// 표시 규칙 (dataviz 기준)
// - 계열이 하나라 색은 accent 하나만 쓴다. 막대 두께 24px 이하, 데이터 쪽 끝만 4px 둥글게
// - 격자·축은 1px 실선, 글자는 text/muted 색 (막대 색을 글자에 쓰지 않는다)
// - 마우스를 올리면 값이 보이고(title), 같은 값은 숫자 라벨이나 표로도 볼 수 있다
import Link from "next/link";
import SegmentedBar from "@/components/SegmentedBar";
import type { DailyCount, RuleStat } from "@/lib/data";
import { RULE_NAMES } from "@/lib/labels";
import { formatKstDay } from "@/lib/time";
import type { Severity } from "@/types/event";

/* ------------------------------------------------------------------ */
/* 규칙별 위반 (가로 막대, 누르면 타임라인)                                */
/* ------------------------------------------------------------------ */

export function RuleBars({ stats, hrefFor }: { stats: RuleStat[]; hrefFor: (ruleId: string) => string }) {
  const max = Math.max(1, ...stats.map((s) => s.violation_count));
  return (
    <ul className="space-y-1">
      {stats.map((s) => (
        <li key={s.rule_id}>
          <Link
            href={hrefFor(s.rule_id)}
            title={`${s.rule_id} 위반 ${s.violation_count}건 — 눌러서 타임라인 보기`}
            className="group -mx-2 grid grid-cols-[minmax(0,10.5rem)_1fr_2rem] items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-accent-soft focus-visible:bg-accent-soft focus-visible:outline-none"
          >
            <span className="truncate text-[13px]">
              <b className="font-semibold">{s.rule_id}</b> {RULE_NAMES[s.rule_id] ?? ""}
            </span>
            <span className="h-2.5 overflow-hidden rounded-full bg-accent-light">
              <span
                className="block h-full rounded-full bg-accent"
                style={{ width: `${(s.violation_count / max) * 100}%` }}
              />
            </span>
            <span className="text-right text-[13px] font-semibold tabular-nums">{s.violation_count}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ */
/* 일별 위반 추이 (세로 막대, 월~일)                                       */
/* ------------------------------------------------------------------ */

const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];

/** 축 눈금: 0부터 깔끔한 정수 3~4개 */
function ticks(max: number): number[] {
  const step = max <= 4 ? 1 : max <= 8 ? 2 : max <= 20 ? 5 : Math.ceil(max / 4 / 5) * 5;
  const top = Math.max(step, Math.ceil(max / step) * step);
  const out: number[] = [];
  for (let v = 0; v <= top; v += step) out.push(v);
  return out;
}

export function DailyColumns({ days, today }: { days: DailyCount[]; today: string }) {
  const axis = ticks(Math.max(0, ...days.map((d) => d.violation_count)));
  const top = axis.at(-1)!;
  const PLOT = 150; // 막대 영역 높이(px). 날짜 줄은 따로 잡아 카드 안에서 잘리지 않게 한다

  return (
    <div className="flex gap-2">
      {/* y축 눈금 */}
      <div className="relative w-5 shrink-0 text-right text-[10px] text-muted tabular-nums" style={{ height: PLOT }}>
        {axis.map((v) => (
          <span key={v} className="absolute right-0 -translate-y-1/2" style={{ top: PLOT - (v / top) * PLOT }}>
            {v}
          </span>
        ))}
      </div>

      <div className="flex-1">
        <div className="relative" style={{ height: PLOT }}>
          {/* 격자 (1px 실선, 눈에 덜 띄게) */}
          {axis.map((v) => (
            <div
              key={v}
              className={`absolute inset-x-0 h-px ${v === 0 ? "bg-border" : "bg-border/60"}`}
              style={{ top: PLOT - (v / top) * PLOT }}
            />
          ))}
          <ol className="absolute inset-0 grid grid-cols-7">
            {days.map((d) => {
              const future = d.date > today;
              const h = (d.violation_count / top) * PLOT;
              return (
                <li
                  key={d.date}
                  className="group relative flex items-end justify-center"
                  title={future ? `${formatKstDay(d.date)} — 아직 오지 않은 날` : `${formatKstDay(d.date)} 위반 ${d.violation_count}건`}
                >
                  {!future && (
                    <>
                      <span
                        className="absolute text-[11px] font-semibold text-text tabular-nums"
                        style={{ bottom: h + 4 }}
                      >
                        {d.violation_count}
                      </span>
                      <span
                        className="block w-6 rounded-t-[4px] bg-accent group-hover:opacity-80"
                        style={{ height: Math.max(h, d.violation_count ? 2 : 0) }}
                      />
                    </>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
        <ol className="mt-2 grid grid-cols-7 text-center text-[11px]">
          {days.map((d, i) => (
            <li key={d.date} className={d.date === today ? "font-bold text-text" : "text-muted"}>
              {WEEKDAYS[i]}
              <span className="block text-[10px] font-normal text-muted">{formatKstDay(d.date)}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 심각도 분포 (한 덩어리를 셋으로 나눈 막대)                               */
/* 값이 셋이고 전체 대비 비율을 보는 것이라 도넛 대신 나눈 막대를 쓴다.        */
/* ------------------------------------------------------------------ */

export function SeverityBar({ counts }: { counts: Record<Severity, number> }) {
  const total = counts.high + counts.medium + counts.low;
  if (total === 0) return null;
  return (
    <div>
      <p className="mb-3 text-[28px] leading-none font-bold">
        {total}
        <span className="ml-1 text-sm font-normal text-muted">건</span>
      </p>
      <SegmentedBar
        parts={[
          { key: "high", label: "높음", value: counts.high, fill: "bg-high" },
          { key: "medium", label: "보통", value: counts.medium, fill: "bg-medium", ink: "dark" }, // 주황 위는 진한 글자
          { key: "low", label: "낮음", value: counts.low, fill: "bg-low" },
        ]}
      />
    </div>
  );
}
