/** 로그인 뒤 돌아갈 주소는 같은 사이트 안의 경로만 허용한다 (외부 주소로 보내는 공격 방지) */
export function safeNext(next: unknown): string {
  return typeof next === "string" && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\")
    ? next
    : "/";
}
