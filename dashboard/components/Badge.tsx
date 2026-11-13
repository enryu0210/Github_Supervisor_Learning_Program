import type { LabelInfo, LabelTone } from "@/lib/labels";

/** labels.ts 의 tone → 색. 색 값은 app/globals.css(@theme) 기준 */
const TONE_CLASS: Record<LabelTone, string> = {
  danger: "bg-high-bg text-high",
  warning: "bg-medium-bg text-medium",
  info: "bg-accent-soft text-accent",
  success: "bg-ok-bg text-ok",
  neutral: "bg-low-bg text-low",
  notice: "bg-detected-bg text-detected",
};

export default function Badge({ info, text }: { info?: LabelInfo; text?: string }) {
  return (
    <span
      title={info?.description}
      className={`inline-block shrink-0 rounded-full px-2 py-px whitespace-nowrap text-[11px] font-semibold ${
        info ? TONE_CLASS[info.tone] : "bg-low-bg text-low"
      }`}
    >
      {info?.label ?? text}
    </span>
  );
}
