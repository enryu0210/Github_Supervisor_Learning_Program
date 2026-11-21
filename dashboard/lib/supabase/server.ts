import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { connection } from "next/server";
import { supabaseEnv } from "./config";

/**
 * 서버 컴포넌트·서버 액션·라우트 핸들러용 Supabase 클라이언트.
 * 로그인 세션 쿠키를 그대로 실어 보내므로 뷰·RPC가 "로그인한 사용자 권한(RLS)"으로 실행된다.
 * (anon 키만으로 부르면 #105 정책상 401)
 */
export async function createClient() {
  const { url, anonKey } = supabaseEnv();
  // 세션 만료 확인에 현재 시각을 쓰므로, 미리 만들어 두는 화면(prerender)이 아니라 요청 때만 실행되게 한다
  await connection();
  const store = await cookies();
  return createServerClient(url, anonKey, {
    cookies: {
      getAll: () => store.getAll(),
      setAll: (toSet) => {
        try {
          toSet.forEach(({ name, value, options }) => store.set(name, value, options));
        } catch {
          // 서버 컴포넌트에서는 쿠키를 쓸 수 없다. 세션 갱신은 proxy.ts 가 맡으므로 무시해도 된다.
        }
      },
    },
  });
}
