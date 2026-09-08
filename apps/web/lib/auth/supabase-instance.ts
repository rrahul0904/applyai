import { createHash } from "node:crypto";

export function supabaseProjectFingerprint(projectUrl: string | undefined) {
  if (!projectUrl) return "";
  try {
    const hostname = new URL(projectUrl).hostname.trim().toLowerCase();
    return hostname
      ? createHash("sha256").update(hostname).digest("hex").slice(0, 16)
      : "";
  } catch {
    return "";
  }
}
