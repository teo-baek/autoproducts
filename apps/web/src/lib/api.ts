import { supabase } from "./supabase";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8444";

/**
 * FastAPI 백엔드 호출 헬퍼.
 * - body 가 FormData 면 Content-Type 자동(멀티파트), 아니면 JSON.
 * - auth=true 면 현재 Supabase 세션의 access_token 을 Bearer 로 첨부.
 */
export async function api<T = unknown>(
  path: string,
  init: RequestInit & { auth?: boolean } = {}
): Promise<T> {
  const { auth, ...rest } = init;
  const headers = new Headers(rest.headers);
  const isForm = rest.body instanceof FormData;
  if (!isForm && rest.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const { data } = await supabase.auth.getSession();
    if (data.session) headers.set("Authorization", `Bearer ${data.session.access_token}`);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...rest, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail =
      (body && (body.detail || body.message)) || `요청에 실패했습니다 (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export { API_BASE };
