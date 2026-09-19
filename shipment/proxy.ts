import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const username = process.env.SHIPMENT_BASIC_USER;
  const password = process.env.SHIPMENT_BASIC_PASSWORD;

  if (!username || !password) {
    return new NextResponse("Basic Auth is not configured", {
      status: 500,
    });
  }

  const expected = `Basic ${Buffer.from(
    `${username}:${password}`,
    "utf8",
  ).toString("base64")}`;

  const authorization = request.headers.get("authorization");

  if (authorization !== expected) {
    return new NextResponse("Authentication required", {
      status: 401,
      headers: {
        "WWW-Authenticate": 'Basic realm="shipment", charset="UTF-8"',
        "Cache-Control": "no-store",
      },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};