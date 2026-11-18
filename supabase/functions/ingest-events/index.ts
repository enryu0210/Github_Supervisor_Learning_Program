// Supabase Edge Function `ingest-events` — CLI `gitcoach sync`가 이벤트를 올리는 곳.
// 학생 PC에는 service key를 두지 않는다: CLI는 팀 토큰만 갖고, 서버 키는 이 함수 안에서만 쓴다.
// Supabase JWT 대신 팀 토큰으로 인증하므로 verify_jwt = false (supabase/config.toml).
// SUPABASE_URL·SUPABASE_SERVICE_ROLE_KEY는 Supabase가 함수 환경변수로 넣어 준다.

import { createClient } from "npm:@supabase/supabase-js@2.118.0";
import { handle } from "./handler.ts";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false } },
);

async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

Deno.serve((req) =>
  handle(req, {
    sha256Hex,
    ingest: async (tokenHash, events) => {
      const { data, error } = await supabase.rpc("ingest_events", {
        p_token_hash: tokenHash,
        p_events: events,
      });
      return { data, error: error ? { code: error.code, message: error.message } : null };
    },
  })
);
