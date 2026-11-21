// 현재 사용자 (github_login, 소문자)
// - 합성 데이터 모드: 설정값 하나로 고정 (.env.local 의 NEXT_PUBLIC_CURRENT_USER, 기본 jiyoon-lim)
// - Supabase 모드: GitHub 로그인한 계정. members.github_login 과 같도록 GitHub user_name 을 소문자로 쓴다 (#105)
//   user_metadata 는 email 가입 때 사용자가 임의로 넣을 수 있어서, GitHub identity 의 user_name 을 읽는다.
import { redirect } from "next/navigation";
import { USE_SUPABASE } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

/** 합성 데이터 모드의 현재 사용자 */
export const MOCK_USER = process.env.NEXT_PUBLIC_CURRENT_USER ?? "jiyoon-lim";

/**
 * 요청한 사람의 github_login. 로그인하지 않았으면 null.
 * 쿠키를 읽으므로 요청 처리 중(Suspense 안, connection() 뒤)에만 부른다.
 */
export async function getCurrentUser(): Promise<string | null> {
  if (!USE_SUPABASE) return MOCK_USER;
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) return null;
  const github = data.user.identities?.find((i) => i.provider === "github");
  const login = github?.identity_data?.user_name;
  return typeof login === "string" ? login.toLowerCase() : null;
}

/** 로그인이 꼭 필요한 화면용. proxy.ts 가 먼저 막지만, 세션이 끊긴 경우를 한 번 더 막는다 */
export async function requireCurrentUser(): Promise<string> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return user;
}
