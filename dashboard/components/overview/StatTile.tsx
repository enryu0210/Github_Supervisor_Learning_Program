/**
 * 개요 상단 숫자 카드. hero = 보라색 강조 카드 (한 화면에 하나만)
 * 큰 숫자는 비례 숫자(tabular-nums 쓰지 않음), 글꼴은 본문과 같은 산세리프
 */
export default function StatTile({
  label,
  value,
  unit,
  note,
  hero = false,
}: {
  label: string;
  value: string;
  unit?: string;
  note: React.ReactNode;
  hero?: boolean;
}) {
  return (
    <div
      className={`rounded-card p-5 shadow-card ${hero ? "bg-accent text-white" : "bg-surface"}`}
    >
      <p className={`text-[13px] ${hero ? "text-white/85" : "text-muted"}`}>{label}</p>
      <p className="mt-2 text-[34px] leading-none font-bold">
        {value}
        {unit && <span className="ml-0.5 text-[26px]">{unit}</span>}
      </p>
      <p className={`mt-3 text-xs ${hero ? "text-white/90" : "text-muted"}`}>{note}</p>
    </div>
  );
}
