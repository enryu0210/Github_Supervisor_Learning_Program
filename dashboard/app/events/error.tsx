"use client";

/** /events 데이터를 못 불러왔을 때 (공통 오류 화면) */
export default function EventsError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="rounded-card bg-surface p-8 text-center text-muted shadow-card">
      <p className="text-3xl" aria-hidden>
        ⚠️
      </p>
      <p className="mt-1 font-bold text-text">데이터를 불러오지 못했어요</p>
      <button
        type="button"
        onClick={reset}
        className="mt-3 rounded-lg bg-accent px-4 py-1.5 text-sm font-semibold text-white"
      >
        다시 시도
      </button>
    </div>
  );
}
