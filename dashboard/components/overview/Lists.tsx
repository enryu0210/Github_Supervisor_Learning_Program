// 개요의 목록·표 부분 (방치 PR, 최근 위반, 리뷰 TOP 3, 멤버 표)
import Link from "next/link";
import Badge from "@/components/Badge";
import { CardEmpty } from "@/components/Card";
import type { MemberActivity, StalePr } from "@/lib/data";
import { eventActionLabel, severityLabel } from "@/lib/labels";
import { formatKst } from "@/lib/time";
import type { GitCoachEvent } from "@/types/event";

/* ------------------------------------------------------------------ */
/* 방치된 PR                                                            */
/* ------------------------------------------------------------------ */

export function StalePrList({ prs }: { prs: StalePr[] }) {
  if (prs.length === 0) return <CardEmpty message="3일 넘게 멈춘 PR이 없어요 👏" />;
  return (
    <ul className="space-y-2">
      {prs.map((p) => (
        <li key={`${p.repo}#${p.pr_number}`}>
          <a
            href={p.url}
            target="_blank"
            rel="noreferrer"
            className="block rounded-xl border border-border px-3.5 py-3 hover:border-accent"
          >
            <p className="truncate text-[13px] font-semibold">
              #{p.pr_number} {p.title}
            </p>
            <p className="mt-1 text-[11px] text-muted">
              {p.author} · {p.idle_days}일째 활동 없음
            </p>
          </a>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ */
/* 최근 위반                                                            */
/* ------------------------------------------------------------------ */

export function RecentViolations({ events, moreHref }: { events: GitCoachEvent[]; moreHref: string }) {
  return (
    <>
      {events.length === 0 ? (
        <CardEmpty message="이 기간에는 위반이 없어요 🎉" />
      ) : (
        <ul className="space-y-2">
          {events.map((e) => (
            <li key={e.id} className="rounded-xl border border-border px-3.5 py-3">
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge info={severityLabel(e.severity)} />
                <Badge info={eventActionLabel(e)} />
                <time dateTime={e.occurred_at} className="ml-auto text-[11px] text-muted">
                  {formatKst(e.occurred_at)}
                </time>
              </div>
              <p className="mt-1.5 truncate text-[11px] text-muted">
                {e.rule_id} · {e.member}
                {e.command_summary ? (
                  <>
                    {" · "}
                    <code className="rounded bg-low-bg px-1.5 py-px font-mono text-text">{e.command_summary}</code>
                  </>
                ) : (
                  e.branch && <> · {e.branch}</>
                )}
              </p>
            </li>
          ))}
        </ul>
      )}
      <Link href={moreHref} className="mt-3 inline-block text-[13px] font-semibold text-accent">
        전체 보기 →
      </Link>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* 리뷰 TOP 3 — 칭찬용. 위반 랭킹은 만들지 않는다 (웹 가이드)                */
/* ------------------------------------------------------------------ */

export function ReviewTop3({ members }: { members: MemberActivity[] }) {
  const ranked = members
    .filter((m) => m.reviews_given > 0)
    .sort((a, b) => b.reviews_given - a.reviews_given || a.member.localeCompare(b.member))
    .slice(0, 3)
    // 같은 수면 같은 등수
    .map((m, i, arr) => ({ ...m, rank: arr.findIndex((x) => x.reviews_given === m.reviews_given) + 1, i }));

  if (ranked.length === 0) return <CardEmpty message="아직 이 기간에 리뷰한 PR이 없어요" />;

  // 시상대처럼 2위 · 1위 · 3위 순서로 놓는다
  const order = [ranked[1], ranked[0], ranked[2]].filter(Boolean);
  return (
    <ol className="grid grid-cols-3 items-end gap-2 sm:gap-3">
      {order.map((m) => {
        const first = m.i === 0;
        return (
          <li
            key={m.member}
            className={`rounded-xl border px-3 text-center ${
              first ? "border-accent bg-accent-soft py-5" : "border-border bg-bg py-4"
            }`}
          >
            <p className="text-[13px] font-bold text-accent">{m.rank}위</p>
            <span
              aria-hidden
              className="mx-auto mt-2 flex h-11 w-11 items-center justify-center rounded-full bg-accent-light text-sm font-bold text-accent"
            >
              {m.member.slice(0, 1).toUpperCase()}
            </span>
            <p className="mt-2 truncate text-[13px]">{m.member}</p>
            <p className="mt-0.5 text-xs sm:text-sm">
              <b className="text-xl">{m.reviews_given}</b> PR
            </p>
          </li>
        );
      })}
    </ol>
  );
}

/* ------------------------------------------------------------------ */
/* 멤버별 표                                                            */
/* ------------------------------------------------------------------ */

export function MemberTable({ members, selected }: { members: MemberActivity[]; selected: string[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-left text-[13px]">
        <thead className="border-b border-border text-xs text-muted">
          <tr>
            <th className="py-2 pr-3 font-normal">멤버</th>
            <th className="py-2 pr-3 text-right font-normal">PR 연 수</th>
            <th className="py-2 pr-3 text-right font-normal">병합</th>
            <th className="py-2 pr-3 text-right font-normal" title="같은 PR 여러 번 리뷰 = 1, 자기 PR 제외">
              리뷰한 PR
            </th>
            <th className="py-2 text-right font-normal">위반</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {members.map((m) => (
            <tr
              key={m.member}
              className={`border-b border-border last:border-0 ${selected.includes(m.member) ? "bg-accent-soft" : ""}`}
            >
              <td className="py-2.5 pr-3">{m.member}</td>
              <td className="py-2.5 pr-3 text-right">{m.prs_opened}</td>
              <td className="py-2.5 pr-3 text-right">{m.prs_merged}</td>
              <td className="py-2.5 pr-3 text-right">{m.reviews_given}</td>
              <td className="py-2.5 text-right">{m.violation_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
