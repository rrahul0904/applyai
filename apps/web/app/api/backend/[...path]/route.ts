import { auth } from "@clerk/nextjs/server";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { DEV_USER_COOKIE, devAuthEnabled } from "@/lib/auth/session";

type RouteContext = { params: Promise<{ path: string[] }> };

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

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  if (devAuthEnabled()) {
    const email = (await cookies()).get(DEV_USER_COOKIE)?.value;
    const secret = process.env.DEV_AUTH_SECRET;
    if (!email || !secret) {
      return NextResponse.json(
        {
          error: {
            code: "AUTH_REQUIRED",
            message: "Sign in to continue.",
          },
        },
        { status: 401 },
      );
    }
    headers.set("x-applyai-dev-user", email);
    headers.set("x-applyai-dev-secret", secret);
  } else {
    const { userId, getToken } = await auth();
    if (!userId) {
      return NextResponse.json(
        {
          error: {
            code: "AUTH_REQUIRED",
            message: "Sign in to continue.",
          },
        },
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

  const { path } = await context.params;
  const target = new URL(`/api/v1/${path.join("/")}`, baseUrl);
  target.search = request.nextUrl.search;
  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.arrayBuffer();

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
