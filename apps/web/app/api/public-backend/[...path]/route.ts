import { NextRequest, NextResponse } from "next/server";

type RouteContext = { params: Promise<{ path: string[] }> };

const MAX_PUBLIC_BODY_BYTES = 64 * 1024;
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{20,64}$/;
const SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])?$/;

function allowedPath(path: string[]) {
  if (
    path.length === 4 &&
    path[0] === "growth" &&
    path[1] === "public" &&
    path[2] === "portfolio" &&
    SLUG_PATTERN.test(path[3])
  ) {
    return path.join("/");
  }
  if (path.length < 3 || path[0] !== "resume-shares" || path[1] !== "public") return null;
  if (!TOKEN_PATTERN.test(path[2])) return null;
  if (path.length === 3) return path.join("/");
  if (path.length === 4 && ["events", "file", "download"].includes(path[3])) {
    return path.join("/");
  }
  return null;
}

function methodAllowed(method: string, normalizedPath: string) {
  if (normalizedPath.startsWith("growth/public/portfolio/")) return method === "GET";
  if (method === "GET") return true;
  return method === "POST" && normalizedPath.endsWith("/events");
}

async function forward(request: NextRequest, context: RouteContext) {
  const baseUrl = process.env.APPLYAI_API_URL;
  if (!baseUrl) {
    return NextResponse.json(
      { error: { code: "API_NOT_CONFIGURED", message: "The ApplyAI data service is not configured." } },
      { status: 503 },
    );
  }

  const { path } = await context.params;
  const normalizedPath = allowedPath(path);
  if (!normalizedPath) {
    return NextResponse.json(
      { error: { code: "PUBLIC_PATH_NOT_ALLOWED", message: "This public API path is not available." } },
      { status: 404 },
    );
  }
  if (!methodAllowed(request.method, normalizedPath)) {
    return NextResponse.json(
      { error: { code: "METHOD_NOT_ALLOWED", message: "This public action is not available." } },
      { status: 405 },
    );
  }

  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_PUBLIC_BODY_BYTES) {
    return NextResponse.json(
      { error: { code: "REQUEST_TOO_LARGE", message: "This public request is too large." } },
      { status: 413 },
    );
  }

  const target = new URL(`/api/v1/${normalizedPath}`, baseUrl);
  target.search = request.nextUrl.search;
  const headers = new Headers();
  if (request.method === "POST") headers.set("content-type", "application/json");
  const userAgent = request.headers.get("user-agent");
  if (userAgent) headers.set("user-agent", userAgent);
  const accept = request.headers.get("accept");
  if (accept) headers.set("accept", accept);

  let body: ArrayBuffer | undefined;
  if (request.method === "POST") {
    body = await request.arrayBuffer();
    if (body.byteLength > MAX_PUBLIC_BODY_BYTES) {
      return NextResponse.json(
        { error: { code: "REQUEST_TOO_LARGE", message: "This public request is too large." } },
        { status: 413 },
      );
    }
  }

  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: request.signal,
    });
    const responseHeaders = new Headers();
    for (const headerName of ["content-type", "content-disposition", "cache-control"]) {
      const value = response.headers.get(headerName);
      if (value) responseHeaders.set(headerName, value);
    }
    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { error: { code: "NETWORK_ERROR", message: "We could not reach the public ApplyAI service." } },
      { status: 503 },
    );
  }
}

export const GET = forward;
export const POST = forward;
