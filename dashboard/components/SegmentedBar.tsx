/**
 * 한 덩어리를 몇 칸으로 나눈 막대 (전체 대비 비율, 칸 6개 이하).
 * 도넛보다 비율을 정확히 읽을 수 있어 개요의 심각도 분포, /me 의 선택 습관에 쓴다.
 * - 칸 사이 2px 틈, 모서리 4px, 높이 28px
 * - 칸이 넓을 때만 숫자를 안에 쓰고, 좁으면 범례에서 본다
 * - 마우스를 올리면 이름·개수·비율(title), 화면 읽기 프로그램은 aria-label 로 읽는다
 */
export type Segment = {
  key: string;
  label: string;
  value: number;
  /** Tailwind 배경 클래스. 예: "bg-high" */
  fill: string;
  /** 칸 안 글자색. 밝은 칸은 진한 글자 */
  ink?: "light" | "dark";
};

export default function SegmentedBar({ parts, unit = "건" }: { parts: Segment[]; unit?: string }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  if (total === 0) return null;
  return (
    <div>
      <div
        role="img"
        aria-label={parts.map((p) => `${p.label} ${p.value}${unit}`).join(", ")}
        className="flex h-7 gap-[2px]"
      >
        {parts
          .filter((p) => p.value > 0)
          .map((p) => {
            const share = p.value / total;
            return (
              <div
                key={p.key}
                title={`${p.label} ${p.value}${unit} (${Math.round(share * 100)}%)`}
                className={`flex items-center rounded-[4px] px-2 text-[11px] font-semibold ${p.fill} ${
                  p.ink === "dark" ? "text-text" : "text-white"
                }`}
                style={{ width: `${share * 100}%` }}
              >
                {share >= 0.12 && p.value}
              </div>
            );
          })}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-1">
            <i className={`inline-block h-2 w-2 rounded-sm ${p.fill}`} aria-hidden />
            {p.label} <span className="text-text tabular-nums">{p.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
