import { useAuth } from "@clerk/expo";
import { useCallback } from "react";

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

export function useApplyAIApi() {
  const { getToken } = useAuth();

  const request = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    if (!API_BASE_URL) throw new Error("EXPO_PUBLIC_API_BASE_URL is required");
    const token = await getToken();
    const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null) as { error?: { message?: string } } | null;
      throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }, [getToken]);

  return { request };
}

export type MobileMatch = { job_id: string; semantic_score: number; title: string; company: string; explanation: string };
export type MobileJob = { id: string; title: string; company_name: string; location: string | null; work_mode: string | null; saved: boolean };
export type MobileApplication = { id: string; job_id: string; current_status: string; updated_at: string };
export type MobileNotification = { id: string; title: string; body: string; read_at: string | null; action_url: string | null };
