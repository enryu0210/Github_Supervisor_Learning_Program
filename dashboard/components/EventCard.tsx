import Badge from "@/components/Badge";
import { eventActionLabel, ruleLabel, severityLabel, sourceLabel } from "@/lib/labels";
import { formatKst } from "@/lib/time";
import type { GitCoachEvent } from "@/types/event";

/** 위반 타임라인의 이벤트 한 건. linked = 이 이벤트를 related_event_id 로 가리키는 이벤트들 */
export default function EventCard({ event: e, linked }: { event: GitCoachEvent; linked: GitCoachEvent[] }) {
  return (
    <article className="mb-2.5 rounded-xl bg-surface px-4 py-3.5 shadow-card">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge info={severityLabel(e.severity)} />
        <b className="text-sm">{ruleLabel(e.rule_id)}</b>
        <Badge info={eventActionLabel(e)} />
        <Badge info={sourceLabel(e.source)} />
        <time dateTime={e.occurred_at} className="ml-auto text-xs text-muted">
          {formatKst(e.occurred_at)}
        </time>
      </div>

      <p className="mt-1.5 text-[11px] text-muted">
        {e.member}
        {e.branch && <> · {e.branch}</>}
        {e.pr_number !== null && <> · PR #{e.pr_number}</>}
        {e.command_summary && (
          <>
            {" · "}
            <code className="rounded bg-low-bg px-1.5 py-px font-mono text-text">{e.command_summary}</code>
          </>
        )}
      </p>

      {/* allowed 는 설명이 항상 null (LLM 미호출) */}
      {e.explanation && (
        <details className="mt-2 rounded-lg bg-accent-soft px-2.5 py-2 text-xs text-[#3d3580]">
          <summary className="cursor-pointer select-none">
            💡 {e.explanation.length > 40 ? `${e.explanation.slice(0, 40)}…` : e.explanation}
          </summary>
          <p className="mt-1 leading-relaxed">{e.explanation}</p>
        </details>
      )}

      {linked.length > 0 && (
        <p className="mt-1.5 flex flex-wrap items-center gap-1 text-[11px] text-muted">
          ↳ 이어진 기록
          {linked.map((l) => (
            <span key={l.id} className="flex items-center gap-1">
              <Badge info={eventActionLabel(l)} />
              {formatKst(l.occurred_at)}
            </span>
          ))}
        </p>
      )}
    </article>
  );
}
