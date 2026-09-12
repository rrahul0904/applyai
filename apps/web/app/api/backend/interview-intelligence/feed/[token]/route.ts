import { NextRequest, NextResponse } from "next/server";

type RouteContext = { params: Promise<{ token: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const baseUrl = process.env.APPLYAI_API_URL;
  if (!baseUrl) {
    return NextResponse.json(
      { error: { code: "API_NOT_CONFIGURED", message: "The ApplyAI data service is not configured." } },
      { status: 503 },
    );
  }
  const params = await context.params;
  const token = params.token.endsWith(".xml") ? params.token.slice(0, -4) : params.token;
  if (!/^[A-Za-z0-9_-]{20,96}$/.test(token)) {
    return NextResponse.json(
      { error: { code: "INVALID_FEED", message: "The private feed token is invalid." } },
      { status: 400 },
    );
  }
  const target = new URL(`/api/v1/interview-intelligence/feed/${encodeURIComponent(token)}.xml`, baseUrl);
  try {
    const response = await fetch(target, { method: "GET", cache: "no-store", signal: request.signal });
    return new NextResponse(response.body, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/rss+xml",
        "cache-control": "private, no-store, max-age=0",
        "x-robots-tag": "noindex, nofollow, noarchive",
      },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "NETWORK_ERROR", message: "The private podcast feed is temporarily unavailable." } },
      { status: 503 },
    );
  }
}
