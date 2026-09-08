import { createHash, randomBytes } from "node:crypto";

export const SUPABASE_ACCESS_COOKIE = "applyai_sb_access";
export const SUPABASE_REFRESH_COOKIE = "applyai_sb_refresh";
export const SUPABASE_PKCE_VERIFIER_COOKIE = "applyai_sb_pkce_verifier";
export const SUPABASE_OAUTH_STATE_COOKIE = "applyai_sb_oauth_state";

export type SupabaseAuthUser = {
  id: string;
  email?: string | null;
  user_metadata?: Record<string, unknown>;
};

export type SupabaseTokenResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
  user: SupabaseAuthUser;
};

type SupabaseAuthError = {
  error?: string;
  error_code?: string;
  msg?: string;
  message?: string;
};

export function supabaseConfigured() {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL &&
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  );
}

function config() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, "");
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !publishableKey) {
    throw new Error("SUPABASE_AUTH_NOT_CONFIGURED");
  }
  return { url, publishableKey };
}

function authHeaders(extra: Record<string, string> = {}) {
  const { publishableKey } = config();
  return {
    apikey: publishableKey,
    "content-type": "application/json",
    ...extra,
  };
}

async function parse<T>(response: Response): Promise<T> {
  const payload = (await response.json().catch(() => ({}))) as T & SupabaseAuthError;
  if (!response.ok) {
    const reason =
      payload.error_code ??
      payload.error ??
      payload.msg ??
      payload.message ??
      `HTTP_${response.status}`;
    throw new Error(`SUPABASE_AUTH_ERROR:${reason}`);
  }
  return payload;
}

export async function signInWithPassword(email: string, password: string) {
  const { url } = config();
  return parse<SupabaseTokenResponse>(
    await fetch(`${url}/auth/v1/token?grant_type=password`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    }),
  );
}

export async function signUpWithPassword(email: string, password: string) {
  const { url } = config();
  return parse<
    | SupabaseTokenResponse
    | {
        access_token?: null;
        refresh_token?: null;
        user: SupabaseAuthUser;
      }
  >(
    await fetch(`${url}/auth/v1/signup`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    }),
  );
}

export async function getSupabaseUser(accessToken: string) {
  const { url } = config();
  const response = await fetch(`${url}/auth/v1/user`, {
    method: "GET",
    headers: authHeaders({ authorization: `Bearer ${accessToken}` }),
    cache: "no-store",
  });
  if (response.status === 401 || response.status === 403) return null;
  return parse<SupabaseAuthUser>(response);
}

export async function refreshSupabaseToken(refreshToken: string) {
  const { url } = config();
  return parse<SupabaseTokenResponse>(
    await fetch(`${url}/auth/v1/token?grant_type=refresh_token`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    }),
  );
}

export async function exchangeSupabasePkceCode(
  authCode: string,
  codeVerifier: string,
) {
  const { url } = config();
  return parse<SupabaseTokenResponse>(
    await fetch(`${url}/auth/v1/token?grant_type=pkce`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        auth_code: authCode,
        code_verifier: codeVerifier,
      }),
      cache: "no-store",
    }),
  );
}

export async function revokeSupabaseSession(accessToken: string) {
  const { url } = config();
  const response = await fetch(`${url}/auth/v1/logout`, {
    method: "POST",
    headers: authHeaders({ authorization: `Bearer ${accessToken}` }),
    cache: "no-store",
  });
  if (!response.ok && response.status !== 401) {
    await parse(response);
  }
}

export function newPkceVerifier() {
  return randomBytes(48).toString("base64url");
}

export function pkceChallenge(verifier: string) {
  return createHash("sha256").update(verifier).digest("base64url");
}

export function newOAuthState() {
  return randomBytes(32).toString("base64url");
}

export function buildGoogleAuthorizeUrl(options: {
  redirectTo: string;
  verifier: string;
  state: string;
}) {
  const { url } = config();
  const target = new URL(`${url}/auth/v1/authorize`);
  target.searchParams.set("provider", "google");
  target.searchParams.set("redirect_to", options.redirectTo);
  target.searchParams.set("code_challenge", pkceChallenge(options.verifier));
  target.searchParams.set("code_challenge_method", "s256");
  target.searchParams.set("state", options.state);
  return target.toString();
}

export function accessTokenNeedsRefresh(token: string, nowSeconds = Date.now() / 1000) {
  try {
    const payload = JSON.parse(
      Buffer.from(token.split(".")[1] ?? "", "base64url").toString("utf8"),
    ) as { exp?: number };
    return !payload.exp || payload.exp <= nowSeconds + 60;
  } catch {
    return true;
  }
}
