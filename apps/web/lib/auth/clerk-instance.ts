import { createHash } from "node:crypto";

export function clerkPublishableKeyInstanceFingerprint(value: string | undefined) {
  if (!value || !/^pk_(test|live)_/.test(value)) return "";
  try {
    const encoded = value.replace(/^pk_(test|live)_/, "");
    const decoded = Buffer.from(encoded, "base64").toString("utf8").replace(/\$$/, "");
    const normalized = decoded.includes("://") ? decoded : `https://${decoded}`;
    const hostname = new URL(normalized).hostname.trim().toLowerCase();
    return hostname
      ? createHash("sha256").update(hostname).digest("hex").slice(0, 16)
      : "";
  } catch {
    return "";
  }
}
