import { connection } from "next/server";
import { Suspense } from "react";
import EventCard from "@/components/EventCard";
import FilterRow, { type Chip } from "@/components/FilterRow";
import { EmptyState, LoadingState } from "@/components/StateViews";
import { data } from "@/lib/data";
import {
  PERIODS,
  hasAnyFilter,
  hrefToggle,
  hrefWith,
  readList,
  readPeriod,
  readQuery,
  readSort,
  toEventFilter,
  type ListKey,
  type SearchParams,
} from "@/lib/filters";
import { ACTION_LABELS, RULE_NAMES, SEVERITY_LABELS, SOURCE_LABELS, eventActionLabel } from "@/lib/labels";
import { EVENT_ACTIONS, EVENT_SOURCES, SEVERITIES, isViolation, type GitCoachEvent } from "@/types/event";

export default function EventsPage({ searchParams }: PageProps<"/events">) {
  return (
    <section>
      <h1 className="text-[22px] font-bold">위반 타임라인</h1>
      <p className="mt-1.5 mb-4 text-muted">CLI와 GitHub에서 잡힌 위반을 시간순으로 봐요.</p>
      {/* 쿼리(필터)를 읽는 부분은 요청마다 달라서 Suspense 안에서 불러온다 */}
      <Suspense fallback={<LoadingState />}>
        <EventsContent searchParams={searchParams} />
      </Suspense>
    </section>
  );
}

async function EventsContent({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  await connection(); // "오늘"·"이번 주"는 요청 시각 기준이라 미리 만들어 두지 않는다
  const [events, all] = await Promise.all([data.getEvents(toEventFilter(sp)), data.getEvents()]);
  const list = readSort(sp) === "asc" ? [...events].reverse() : events;
  const members = [...new Set(all.map((e) => e.member))].sort();
  const rules = Object.keys(RULE_NAMES).filter((r) => all.some((e) => e.rule_id === r));

  const row = (key: ListKey, label: string, options: { value: string; label: string }[]) => {
    const selected = readList(sp, key);
    const chips: Chip[] = options.map((o) => ({
      label: o.label,
      href: hrefToggle(sp, key, o.value),
      active: selected.includes(o.value),
    }));
    return <FilterRow label={label} all={{ label: "전체", href: hrefWith(sp, key, undefined), active: selected.length === 0 }} chips={chips} />;
  };

  return (
    <div className="grid grid-cols-[1fr_300px] gap-6">
      <div>
        <form action="/events" className="mb-3.5">
          {Object.entries(sp).map(([k, v]) =>
            k !== "q" && typeof v === "string" ? <input key={k} type="hidden" name={k} value={v} /> : null,
          )}
          <input
            name="q"
            defaultValue={readQuery(sp)}
            placeholder="🔍 명령어 · 브랜치 · PR 번호로 검색 (Enter)"
            className="w-full rounded-xl bg-surface px-4 py-3 shadow-card outline-none placeholder:text-muted focus:ring-2 focus:ring-accent-light"
          />
        </form>

        <div className="mb-4 rounded-card bg-surface p-4 shadow-card">
          {row("member", "멤버", members.map((m) => ({ value: m, label: m })))}
          {row("rule", "규칙", rules.map((r) => ({ value: r, label: r })))}
          {row("source", "출처", EVENT_SOURCES.map((s) => ({ value: s, label: SOURCE_LABELS[s].label })))}
          {row("severity", "심각도", SEVERITIES.map((s) => ({ value: s, label: SEVERITY_LABELS[s].label })))}
          {row("action", "결과", EVENT_ACTIONS.map((a) => ({ value: a, label: ACTION_LABELS[a].label })))}
          <FilterRow
            label="기간"
            all={{ label: "전체", href: hrefWith(sp, "period", undefined), active: readPeriod(sp) === "all" }}
            chips={PERIODS.filter((p) => p.value !== "all").map((p) => ({
              label: p.label,
              href: hrefWith(sp, "period", p.value),
              active: readPeriod(sp) === p.value,
            }))}
          />
          <p className="mt-1 flex justify-end gap-3 text-xs text-muted">
            <span>총 {events.length}건</span>
            <a href={hrefWith(sp, "sort", readSort(sp) === "asc" ? undefined : "asc")} className="font-semibold text-text">
              {readSort(sp) === "asc" ? "오래된순 ▴" : "최신순 ▾"}
            </a>
          </p>
        </div>

        {list.length === 0 ? (
          <EmptyState message="조건에 맞는 위반이 없어요" resetHref={hasAnyFilter(sp) ? "/events" : undefined} />
        ) : (
          list.map((e) => (
            <EventCard key={e.id} event={e} linked={all.filter((l) => l.related_event_id === e.id && l.action !== "guided")} />
          ))
        )}
      </div>

      <aside>
        <SeverityDonut events={events} />
        <ResultBars events={events} />
      </aside>
    </div>
  );
}

/** 심각도 분포 (필터 안 위반 기준) */
function SeverityDonut({ events }: { events: GitCoachEvent[] }) {
  const v = events.filter(isViolation);
  const n = (s: string) => v.filter((e) => e.severity === s).length;
  const [high, medium, low] = [n("high"), n("medium"), n("low")];
  const total = v.length || 1;
  const a = (high / total) * 100;
  const b = a + (medium / total) * 100;
  const gradient = v.length
    ? `conic-gradient(var(--color-high) 0 ${a}%, var(--color-medium) ${a}% ${b}%, var(--color-low) ${b}% 100%)`
    : "var(--color-accent-light)";
  return (
    <div className="mb-4 rounded-card bg-surface p-4 shadow-card">
      <h3 className="mb-3 text-sm font-bold">심각도 분포</h3>
      <div className="relative mx-auto mb-2.5 h-[140px] w-[140px] rounded-full" style={{ background: gradient }}>
        <div className="absolute inset-[30px] flex items-center justify-center rounded-full bg-surface text-xl font-bold">
          {v.length}
        </div>
      </div>
      <div className="flex justify-center gap-3 text-[11px] text-muted">
        <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-high" />높음 {high}</span>
        <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-medium" />보통 {medium}</span>
        <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-low" />낮음 {low}</span>
      </div>
    </div>
  );
}

/** 결과 분포 (필터 안 위반 기준) */
function ResultBars({ events }: { events: GitCoachEvent[] }) {
  const v = events.filter(isViolation);
  const counts = new Map<string, number>();
  for (const e of v) {
    const label = eventActionLabel(e).label;
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  const max = Math.max(1, ...counts.values());
  return (
    <div className="rounded-card bg-surface p-4 shadow-card">
      <h3 className="mb-3 text-sm font-bold">결과 분포</h3>
      {[...counts.entries()]
        .sort((a, b) => b[1] - a[1])
        .map(([label, c]) => (
          <div key={label} className="my-2 flex items-center gap-2.5 text-xs">
            <span className="w-24 shrink-0">{label}</span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-accent-light">
              <div className="h-full rounded-full bg-accent" style={{ width: `${(c / max) * 100}%` }} />
            </div>
            <em className="w-5 text-right not-italic">{c}</em>
          </div>
        ))}
      <p className="mt-2 text-[11px] text-muted">위반 수에는 가이드 완료·중단과 복구 가이드를 다시 세지 않아요.</p>
    </div>
  );
}
