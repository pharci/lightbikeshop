import { saveConfirmedOzonIds } from "@/lib/database";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      confirmation?: string;
      orderIds?: unknown[];
    };
    if (body.confirmation !== "SYNC_CONFIRMED_OZON") {
      return NextResponse.json({ error: "Подтверждение не передано" }, { status: 400 });
    }
    const orderIds = [...new Set(
      (body.orderIds ?? [])
        .filter((value): value is string => typeof value === "string")
        .map((value) => value.trim())
        .filter((value) => /^[A-Za-z0-9-]{3,80}$/.test(value)),
    )].slice(0, 100);
    if (!orderIds.length) return NextResponse.json({ saved: 0 });

    saveConfirmedOzonIds(orderIds);
    return NextResponse.json({ saved: orderIds.length });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Ошибка сохранения" },
      { status: 500 },
    );
  }
}
