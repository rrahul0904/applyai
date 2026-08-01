const SAFE_SEGMENT = /^[A-Za-z0-9_-]+$/;

export const MAX_PROXY_BODY_BYTES = 1024 * 1024;

export function safeBackendPath(path: string[]): string | null {
  if (!path.length) return null;
  if (path.some((segment) => !SAFE_SEGMENT.test(segment))) return null;
  return path.join("/");
}
