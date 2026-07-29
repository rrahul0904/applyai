import { auth } from "@clerk/nextjs/server";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { DEV_USER_COOKIE, devAuthEnabled } from "@/lib/auth/session";

type RouteContext = { params: Promise<{ path: string[] }> };

const MAX_PROXY_BODY_BYTES = 1024 * 1024;
const SAFE_SEGMENT = /^[A-Za-z0-9_-]+$/;

function safeBackendPath(path: string[]): string | null {
  if (!path.length || path.some((segment) => !SAFE_SEGMENT.test(segment))) return null;
  return path.join("/");
}

async function forward(request: NextRequest, context: RouteContext) {
  const baseUrl = process.env.APPLYAI_API_URL;
  if (!baseUrl) {
    return NextResponse.json(
      {
        error: {
          code: "API_NOT_CONFIGURED",
          message: "The ApplyAI data service is not configured.",
        },
      },
      { status: 503 },
    );
  }

  const { path } = await context.params;
  const normalizedPath = safeBackendPath(path);
  if (!normalizedPath) {
    return NextResponse.json(
      { error: { code: "INVALID_BACKEND_PATH", message: "The requested API path is invalid." } },
      { status: 400 },
    );
  }

  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_PROXY_BODY_BYTES) {
    return NextResponse.json(
      {
        error: {
          code: "REQUEST_TOO_LARGE",
          message: "This request is too large for the application proxy.",
        },
      },
      { status: 413 },
    );
  }

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  if (devAuthEnabled()) {
    const email = (await cookies()).get(DEV_USER_COOKIE)?.value;
    const secret = process.env.DEV_AUTH_SECRET;
    if (!email || !secret) {
      return NextResponse.json(
        { error: { code: "AUTH_REQUIRED", message: "Sign in to continue." } },
        { status: 401 },
      );
    }
    headers.set("x-applyai-dev-user", email);
    headers.set("x-applyai-dev-secret", secret);
  } else {
    const { userId, getToken } = await auth();
    if (!userId) {
      return NextResponse.json(
        { error: { code: "AUTH_REQUIRED", message: "Sign in to continue." } },
        { status: 401 },
      );
    }
    const token = await getToken();
    if (!token) {
      return NextResponse.json(
        {
          error: {
            code: "SESSION_EXPIRED",
            message: "Your session has expired. Please sign in again.",
          },
        },
        { status: 401 },
      );
    }
    headers.set("authorization", `Bearer ${token}`);
  }

  const target = new URL(`/api/v1/${normalizedPath}`, baseUrl);
  target.search = request.nextUrl.search;
  let body: ArrayBuffer | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.arrayBuffer();
    if (body.byteLength > MAX_PROXY_BODY_BYTES) {
      return NextResponse.json(
        {
          error: {
            code: "REQUEST_TOO_LARGE",
            message: "This request is too large for the application proxy.",
          },
        },
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
    const responseType = response.headers.get("content-type");
    if (responseType) responseHeaders.set("content-type", responseType);
    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "NETWORK_ERROR",
          message: "We could not reach the ApplyAI data service. Please try again.",
        },
      },
      { status: 503 },
    );
  }
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
