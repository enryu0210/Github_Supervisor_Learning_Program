"use client";

import Link from "next/link";
import { useState } from "react";
import Badge from "@/components/Badge";
import InlineCode from "@/components/InlineCode";
import type { Quiz } from "@/lib/data";
import { RULE_NAMES, eventActionLabel, severityLabel } from "@/lib/labels";
import { formatKst } from "@/lib/time";
import type { GitCoachEvent } from "@/types/event";

export type QuizItem = { quiz: Quiz; source: GitCoachEvent | null };

/**
 * 퀴즈 한 문제씩 풀기. 상태는 이 화면 안에서만 들고 있고 어디에도 저장하지 않는다 (v0.1, D5).
 * 새로고침하면 처음부터 다시 푼다.
 */
export default function QuizRunner({ items }: { items: QuizItem[] }) {
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [results, setResults] = useState<boolean[]>([]); // 이번에 푼 문제의 정답 여부

  const done = index >= items.length;
  const correctCount = results.filter(Boolean).length;

  const next = () => {
    setIndex((i) => i + 1);
    setSelected(null);
    setSubmitted(false);
  };
  const restart = () => {
    setIndex(0);
    setSelected(null);
    setSubmitted(false);
    setResults([]);
  };

  /* ---------- 진행 표시 ---------- */
  const progress = (
    <div className="mb-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-[13px]">
        <span className="flex gap-1.5">
          <span className="rounded-full bg-accent px-3 py-1 font-semibold text-white">풀 문제 {items.length - results.length}</span>
          <span className="rounded-full border border-border bg-surface px-3 py-1">맞힌 문제 {correctCount}</span>
          <span className="rounded-full border border-border bg-surface px-3 py-1">틀린 문제 {results.length - correctCount}</span>
        </span>
        <span className="text-muted">
          문제 {Math.min(index + 1, items.length)} / {items.length}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-accent-light" role="progressbar" aria-valuemin={0} aria-valuemax={items.length} aria-valuenow={results.length}>
        <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${(results.length / items.length) * 100}%` }} />
      </div>
      <p className="mt-1.5 text-[11px] text-muted">이번 화면에서만 세는 숫자예요. 풀이 기록은 저장하지 않아요.</p>
    </div>
  );

  if (done) {
    return (
      <>
        {progress}
        <div className="rounded-card bg-surface p-8 text-center shadow-card">
          <p className="text-3xl" aria-hidden>
            {correctCount === items.length ? "🎉" : "📚"}
          </p>
          <p className="mt-2 text-lg font-bold">
            {items.length}문제 중 {correctCount}개 맞혔어요
          </p>
          <p className="mt-1 text-sm text-muted">틀린 규칙은 규칙 도감에서 다시 읽어 보세요.</p>
          <div className="mt-4 flex justify-center gap-2">
            <button type="button" onClick={restart} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white">
              다시 풀기
            </button>
            <Link href="/rules" className="rounded-lg border border-accent px-4 py-2 text-sm font-semibold text-accent">
              규칙 도감 →
            </Link>
          </div>
        </div>
      </>
    );
  }

  const { quiz, source } = items[index];
  const isCorrect = selected === quiz.answer_index;

  const submit = () => {
    if (selected === null) return;
    setSubmitted(true);
    setResults((r) => [...r, selected === quiz.answer_index]);
  };

  return (
    <>
      {progress}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-4">
          <div className="rounded-card bg-surface p-6 shadow-card">
            <div className="flex flex-wrap gap-1.5">
              {source && <Badge info={severityLabel(source.severity)} />}
              <Badge info={{ label: `${quiz.rule_id} ${RULE_NAMES[quiz.rule_id] ?? ""}`, description: "", tone: "info" }} />
            </div>
            <h2 className="mt-3 text-lg leading-snug font-bold">
              <InlineCode text={quiz.question} />
            </h2>

            <fieldset className="mt-4 space-y-2.5" disabled={submitted}>
              <legend className="sr-only">보기</legend>
              {quiz.choices.map((c, i) => {
                const picked = selected === i;
                const state = !submitted
                  ? picked
                    ? "border-accent bg-accent-soft"
                    : "border-border hover:border-accent"
                  : i === quiz.answer_index
                    ? "border-ok bg-ok-bg"
                    : picked
                      ? "border-high bg-high-bg"
                      : "border-border opacity-60";
                return (
                  <label key={i} className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm ${state}`}>
                    <input
                      type="radio"
                      name={`quiz-${quiz.id}`}
                      className="sr-only"
                      checked={picked}
                      onChange={() => setSelected(i)}
                    />
                    <span
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs ${
                        picked && !submitted ? "border-accent bg-accent text-white" : "border-border text-muted"
                      }`}
                    >
                      {i + 1}
                    </span>
                    <InlineCode text={c} />
                  </label>
                );
              })}
            </fieldset>

            {!submitted && (
              <div className="mt-4 flex gap-2">
                <button
                  type="button"
                  onClick={submit}
                  disabled={selected === null}
                  className="rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-white disabled:opacity-40"
                >
                  제출하기
                </button>
                <button type="button" onClick={next} className="rounded-lg border border-accent px-5 py-2 text-sm font-semibold text-accent">
                  건너뛰기
                </button>
              </div>
            )}
          </div>

          {submitted && (
            <div role="status" className={`rounded-card p-6 shadow-card ${isCorrect ? "bg-ok-bg" : "bg-high-bg"}`}>
              <p className={`font-bold ${isCorrect ? "text-ok" : "text-high"}`}>
                {isCorrect ? "✅ 정답이에요!" : `❌ 아쉬워요. 정답은 ${quiz.answer_index + 1}번이에요.`}
              </p>
              <p className="mt-2 text-sm leading-relaxed">
                <InlineCode text={quiz.explanation} />
              </p>
              <button type="button" onClick={next} className="mt-4 rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-white">
                {index + 1 < items.length ? "다음 문제 →" : "결과 보기 →"}
              </button>
            </div>
          )}
        </div>

        <aside className="min-w-0 space-y-5">
          <section className="rounded-card bg-surface p-5 shadow-card">
            <h2 className="mb-3 text-[15px] font-bold">이 문제가 나온 이유</h2>
            {source ? (
              <div className="rounded-xl border border-border px-3.5 py-3">
                <Badge info={eventActionLabel(source)} />
                <p className="mt-1.5 text-[11px] text-muted">
                  {formatKst(source.occurred_at)}
                  {source.command_summary && (
                    <>
                      {" · "}
                      <code className="rounded bg-low-bg px-1.5 py-px font-mono break-all text-text">{source.command_summary}</code>
                    </>
                  )}
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted">근거 기록을 찾지 못했어요.</p>
            )}
            <p className="mt-3 text-[11px] leading-relaxed text-muted">
              경고를 보고도 그냥 실행했거나 가이드를 중간에 멈춘 기록으로 문제가 만들어져요.
            </p>
          </section>
          <section className="rounded-card bg-surface p-5 shadow-card">
            <h2 className="mb-2 text-[15px] font-bold">관련 규칙</h2>
            <Link href={`/rules?rule=${quiz.rule_id}`} className="text-[13px] font-semibold text-accent">
              {quiz.rule_id} {RULE_NAMES[quiz.rule_id] ?? ""} 도감 보기 →
            </Link>
          </section>
        </aside>
      </div>
    </>
  );
}
