import { NextResponse } from "next/server";
import { isSameOriginRequest } from "@/lib/csrf";

export function rejectCrossSiteRequest(request: Request) {
  if (isSameOriginRequest(request)) return null;
  return NextResponse.json({ error: "Запрос отклонён" }, { status: 403 });
}