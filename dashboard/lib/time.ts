// 시간 계산은 모두 KST(Asia/Seoul) 기준이다. ("이번 주"·일별 집계, data-flow 공통 규칙)
import type { Range } from "@/lib/data";

const TZ = "Asia/Seoul";
const KST_OFFSET_MS = 9 * 60 * 60 * 1000; // 한국은 서머타임이 없어 +09:00 고정

/** ISO 시각 → KST 날짜 "YYYY-MM-DD" */
export function kstDate(iso: string): string {
  return new Date(Date.parse(iso) + KST_OFFSET_MS).toISOString().slice(0, 10);
}

/** KST 날짜 "YYYY-MM-DD"의 00:00(KST)을 ISO 문자열로 */
function kstMidnightIso(date: string): string {
  return `${date}T00:00:00+09:00`;
}

/** 날짜에 n일 더하기 ("YYYY-MM-DD") */
export function addDays(date: string, n: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** 오늘(KST) 하루 */
export function todayRange(now = new Date()): Range {
  const today = kstDate(now.toISOString());
  return { from: kstMidnightIso(today), to: kstMidnightIso(addDays(today, 1)) };
}

/** 이번 주(KST 월요일 00:00 ~ 다음 주 월요일 00:00) */
export function thisWeekRange(now = new Date()): Range {
  const today = kstDate(now.toISOString());
  const dow = new Date(`${today}T00:00:00Z`).getUTCDay(); // 0=일 … 6=토
  const monday = addDays(today, dow === 0 ? -6 : 1 - dow);
  return { from: kstMidnightIso(monday), to: kstMidnightIso(addDays(monday, 7)) };
}

/** 지난주(KST 월~일). 이번 주 범위를 7일 앞으로 옮긴 것 */
export function lastWeekRange(now = new Date()): Range {
  return shiftRange(thisWeekRange(now), -7);
}

/** 범위를 n일 옮기기 */
export function shiftRange(r: Range, days: number): Range {
  const ms = days * 24 * 60 * 60 * 1000;
  const move = (iso: string) => new Date(Date.parse(iso) + ms + KST_OFFSET_MS).toISOString().replace(/\.\d{3}Z$/, "+09:00");
  return { from: move(r.from), to: move(r.to) };
}

/** 화면 표시용 "11/9" (KST 날짜만) */
export function formatKstDay(iso: string): string {
  const [, m, d] = kstDate(iso).split("-");
  return `${Number(m)}/${Number(d)}`;
}

/** 화면 표시용 "11/10 14:20" (KST) */
export function formatKst(iso: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: TZ,
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .format(new Date(iso))
    .replace(/\.\s?/g, "/")
    .replace(/\/\s*(\d{2}:\d{2})/, " $1");
}
