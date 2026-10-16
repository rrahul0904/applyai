import { NextRequest, NextResponse } from "next/server";

type RouteContext = { params: Promise<{ path: string[] }> };

const MAX_PUBLIC_BODY_BYTES = 64 * 1024;
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{20,64}$/;
const BOARD_SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function allowedResumeSharePath(path: string[]) {
  if (path.length < 3 || path[0] !== "resume-shares" || path[1] !== "public") return null;
  if (!TOKEN_PATTERN.test(path[2])) return null;
  if (path.length === 3) return path.join("/");
  if (path.length === 4 && ["events", "file", "download"].includes(path[3])) {
    return path.join("/");
  }
  return null;
}

function allowedJobBoardPath(path: string[]) {
  if (path[0] !== "job-boards") return null;
  if (path.length === 1) return "job-boards";
  if (path.length === 3 && path[1] === "outbound" && UUID_PATTERN.test(path[2])) {
    return path.join("/");
  }
  const slug = path[1];
  if (!BOARD_SLUG_PATTERN.test(slug)) return null;
  if (path.length === 2) return path.join("/");
  if (path.length === 3 && path[2] === "jobs") return path.join("/");
  if (
    path.length === 5 &&
    path[2] === "jobs" &&
    UUID_PATTERN.test(path[3]) &&
    path[4] === "structured-data"
  ) {
    return path.join("/");
  }
  return null;
}

function allowedPath(path: string[]) {
  return allowedResumeSharePath(path) ?? allowedJobBoardPath(path);
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
  if (request.method === "POST" && normalizedPath.endsWith("/events") === false) {
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
  const referer = request.headers.get("referer");
  if (referer) headers.set("referer", referer);

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
      redirect: "manual",
      signal: request.signal,
    });
    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get("location");
      if (location) return NextResponse.redirect(location, response.status);
    }
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
