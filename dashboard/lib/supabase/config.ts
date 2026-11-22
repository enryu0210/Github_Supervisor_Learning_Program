// 데이터 출처 설정 (서버·클라이언트 공용, 비밀값 없음)
//   NEXT_PUBLIC_DATA_SOURCE=supabase  → 실제 DB + GitHub 로그인 필수
//   그 밖 / 비어 있음                 → 합성 데이터(mock), 로그인 없음
// 웹은 anon(publishable) 키와 로그인 사용자 토큰만 쓴다. service_role 키는 절대 넣지 않는다.
// 값은 dashboard/.env.local 과 Vercel 환경 변수에만 둔다 (레포·채팅에 붙이지 않기).

export const USE_SUPABASE = process.env.NEXT_PUBLIC_DATA_SOURCE === "supabase";

/** Supabase 연결값. 설정이 빠졌으면 무엇이 빠졌는지 알려 준다 */
export function supabaseEnv(): { url: string; anonKey: string } {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error(
      "NEXT_PUBLIC_DATA_SOURCE=supabase 인데 NEXT_PUBLIC_SUPABASE_URL·NEXT_PUBLIC_SUPABASE_ANON_KEY 가 비어 있어요. dashboard/.env.local 을 확인하세요.",
    );
  }
  return { url, anonKey };
}
