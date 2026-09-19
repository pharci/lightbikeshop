import { NextResponse } from "next/server";
import { PDFDocument } from "pdf-lib";
import { getApiCredentials } from "@/lib/api-credentials";

type Input = {
  confirmation?: string;
  supplyId?: string;
  images?: Array<{ dataUrl?: string }>;
};
type MsOrder = { id?: string; name?: string };

const msHeaders = (token: string) => ({
  Authorization: `Bearer ${token}`,
  Accept: "application/json;charset=utf-8",
  "Content-Type": "application/json",
});
const bytesFromDataUrl = (dataUrl: string) => {
  const encoded = dataUrl.split(",")[1] ?? "";
  const binary = atob(encoded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
};
const toBase64 = (bytes: Uint8Array) => {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 32768)
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
  return btoa(binary);
};

async function makePdf(images: string[]) {
  const pdf = await PDFDocument.create();
  const pageWidth = (58 / 25.4) * 72;
  const pageHeight = (40 / 25.4) * 72;
  for (const source of images) {
    const image = await pdf.embedPng(bytesFromDataUrl(source));
    const page = pdf.addPage([pageWidth, pageHeight]);
    const scale = Math.min(pageWidth / image.width, pageHeight / image.height);
    const width = image.width * scale;
    const height = image.height * scale;
    page.drawImage(image, {
      x: (pageWidth - width) / 2,
      y: (pageHeight - height) / 2,
      width,
      height,
    });
  }
  return toBase64(await pdf.save());
}

async function wbOrderIds(supplyId: string, token: string) {
  const response = await fetch(
    `https://marketplace-api.wildberries.ru/api/marketplace/v3/supplies/${encodeURIComponent(supplyId)}/order-ids`,
    { headers: { Authorization: token } },
  );
  if (!response.ok)
    throw new Error(`WB не вернул состав поставки: ${response.status}`);
  const data = (await response.json()) as { orderIds?: number[] };
  return (data.orderIds ?? []).map(String);
}

async function findMsOrder(orderId: string, token: string) {
  const response = await fetch(
    `https://api.moysklad.ru/api/remap/1.2/entity/customerorder?limit=2&filter=${encodeURIComponent(`name=WB${orderId}`)}`,
    { headers: msHeaders(token) },
  );
  if (!response.ok) throw new Error(`Поиск WB${orderId}: ${response.status}`);
  const data = (await response.json()) as { rows?: MsOrder[] };
  return (data.rows ?? []).find((row) => row.name === `WB${orderId}`);
}

async function attach(
  order: MsOrder,
  filename: string,
  content: string,
  token: string,
) {
  const url = `https://api.moysklad.ru/api/remap/1.2/entity/customerorder/${encodeURIComponent(order.id ?? "")}/files`;
  const existing = await fetch(url, { headers: msHeaders(token) });
  if (!existing.ok)
    throw new Error(
      `${order.name}: не удалось проверить файлы (${existing.status})`,
    );
  const files = (await existing.json()) as {
    rows?: Array<{ filename?: string }>;
  };
  if ((files.rows ?? []).some((file) => file.filename === filename))
    return "skipped" as const;
  const response = await fetch(url, {
    method: "POST",
    headers: msHeaders(token),
    body: JSON.stringify({ filename, content }),
  });
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 200);
    throw new Error(`${order.name}: загрузка ${response.status} ${detail}`);
  }
  return "uploaded" as const;
}

export async function POST(request: Request) {
  const { moyskladToken: msToken, wbToken } = getApiCredentials();
  if (!msToken || !wbToken)
    return NextResponse.json(
      { error: "Не настроены ключи WB или МоегоСклада" },
      { status: 503 },
    );
  try {
    const body = (await request.json()) as Input;
    if (body.confirmation !== "UPLOAD_WB_TO_MOYSKLAD")
      return NextResponse.json(
        { error: "Требуется подтверждение" },
        { status: 400 },
      );
    if (!body.supplyId?.startsWith("WB-GI-"))
      return NextResponse.json(
        { error: "Некорректная поставка" },
        { status: 400 },
      );
    const images = (body.images ?? [])
      .map((item) => item.dataUrl ?? "")
      .filter((value) => value.startsWith("data:image/png;base64,"));
    if (images.length < 2 || images.length > 10)
      return NextResponse.json(
        { error: "Нужны стикеры грузомест и QR поставки" },
        { status: 400 },
      );
    if (images.reduce((sum, value) => sum + value.length, 0) > 8_000_000)
      return NextResponse.json(
        { error: "Файлы слишком большие" },
        { status: 413 },
      );
    const ids = await wbOrderIds(body.supplyId, wbToken);
    if (!ids.length)
      return NextResponse.json(
        { error: "В поставке WB не найдены заказы" },
        { status: 404 },
      );
    const pdf = await makePdf(images);
    const filename = `WB-поставка-${body.supplyId}-58x40.pdf`;
    const results = [] as Array<{
      orderId: string;
      status: "uploaded" | "skipped" | "not_found" | "error";
      error?: string;
    }>;
    for (const id of ids) {
      try {
        const order = await findMsOrder(id, msToken);
        if (!order) {
          results.push({ orderId: id, status: "not_found" });
          continue;
        }
        results.push({
          orderId: id,
          status: await attach(order, filename, pdf, msToken),
        });
      } catch (error) {
        results.push({
          orderId: id,
          status: "error",
          error: error instanceof Error ? error.message : "Ошибка",
        });
      }
    }
    const uploaded = results.filter(
      (item) => item.status === "uploaded",
    ).length;
    const skipped = results.filter((item) => item.status === "skipped").length;
    return NextResponse.json({
      filename,
      total: ids.length,
      uploaded,
      skipped,
      failed: ids.length - uploaded - skipped,
      results,
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Ошибка передачи" },
      { status: 500 },
    );
  }
}
