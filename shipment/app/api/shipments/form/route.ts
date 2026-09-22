import {
  acquireOperationLock,
  getConfirmedOzonIds,
  releaseOperationLock,
  saveConfirmedOzonIds,
} from "@/lib/database";
import { NextRequest, NextResponse } from "next/server";
import { getApiCredentials } from "@/lib/api-credentials";
import { getMoySkladCustomerOrder } from "@/lib/moysklad";
import { rejectCrossSiteRequest } from "@/lib/security";
import { externalJson } from "@/lib/http";
import { collectCursorPages } from "@/lib/pagination";
import { confirmThenGetLabels } from "@/lib/ozon";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
type WbOrder = { id: number; cargoType?: number };
type OzonPosting = {
  posting_number: string;
  status?: string;
  delivery_method?: { id?: number; warehouse_id?: number };
};
type FileResult = { name: string; type: string; dataUrl: string };

const chunks = <T>(items: T[], size: number) =>
  Array.from({ length: Math.ceil(items.length / size) }, (_, index) =>
    items.slice(index * size, (index + 1) * size),
  );
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const wbHeaders = (token: string) => ({
  Authorization: token,
  "Content-Type": "application/json",
});
const ozonHeaders = (clientId: string, apiKey: string) => ({
  "Client-Id": clientId,
  "Api-Key": apiKey,
  "Content-Type": "application/json",
});
const isMoySkladReadyState = (state: string) =>
  state.includes("собран") || state.includes("доставк");
const isCanceledWbStatus = (status?: string) =>
  ["cancel", "cancelled", "canceled", "отмен"].some((value) =>
    (status ?? "").toLocaleLowerCase("ru-RU").includes(value),
  );
const binaryToBase64 = (value: string) => {
  let result = "";
  for (let index = 0; index < value.length; index += 8192) {
    result += String.fromCharCode(
      ...Array.from(
        value.slice(index, index + 8192),
        (char) => char.charCodeAt(0) & 255,
      ),
    );
  }
  return btoa(result);
};
async function jsonCall<T extends Record<string, unknown> = Record<string, unknown>>(
  url: string,
  init: RequestInit,
  label: string,
  retryable = false,
) {
  return externalJson<T>(url, init, label, { retryable });
}

async function wbNew(token: string) {
  const data = await jsonCall(
    "https://marketplace-api.wildberries.ru/api/v3/orders/new",
    { headers: { Authorization: token } },
    "WB",
    true,
  );
  return (data.orders ?? []) as WbOrder[];
}
async function wbOpenSupplyOrders(token: string) {
  const data = await jsonCall(
    "https://marketplace-api.wildberries.ru/api/v3/supplies?limit=1000&next=0",
    { headers: { Authorization: token } },
    "WB",
    true,
  );
  const supplies = (data.supplies ?? []) as Array<{ id?: string; done?: boolean }>;
  const result: Array<{ supplyId: string; orderIds: number[] }> = [];
  for (const supply of supplies.filter((item) => item.id && !item.done)) {
    let orderIds: number[] = [];
    try {
      const response = await jsonCall(
        `https://marketplace-api.wildberries.ru/api/marketplace/v3/supplies/${encodeURIComponent(String(supply.id))}/order-ids`,
        { headers: { Authorization: token } },
        "WB",
        true,
      );
      orderIds = ((response.orderIds ?? response.orders ?? []) as Array<number | string>)
        .map(Number)
        .filter(Number.isFinite);
    } catch {}
    if (!orderIds.length) try {
      const orders = await jsonCall(
        `https://marketplace-api.wildberries.ru/api/v3/supplies/${encodeURIComponent(String(supply.id))}/orders`,
        { headers: { Authorization: token } },
        "WB",
        true,
      );
      orderIds = ((orders.orders ?? []) as WbOrder[]).map((order) => order.id);
    } catch {}
    if (orderIds.length) {
      try {
        const statuses = await jsonCall<{
          orders?: Array<{
            id: number;
            supplierStatus?: string;
            wbStatus?: string;
          }>;
        }>(
          "https://marketplace-api.wildberries.ru/api/v3/orders/status",
          { method: "POST", headers: wbHeaders(token), body: JSON.stringify({ orders: orderIds }) },
          "WB",
          true,
        );
        const canceled = new Set(
          (statuses.orders ?? [])
            .filter(
              (order) =>
                isCanceledWbStatus(order.supplierStatus) ||
                isCanceledWbStatus(order.wbStatus),
            )
            .map((order) => order.id),
        );
        orderIds = orderIds.filter((orderId) => !canceled.has(orderId));
      } catch {}
      if (orderIds.length) result.push({ supplyId: String(supply.id), orderIds });
    }
  }
  return result;
}
async function isAssembledInMoySklad(orderId: number, token: string) {
  const data = await getMoySkladCustomerOrder(orderId, token);
  const order = (data.rows ?? []).find((row) => row.name === `WB${orderId}`);
  const state = order?.state?.name?.toLocaleLowerCase("ru-RU") ?? "";
  return isMoySkladReadyState(state);
}
async function wbOrderStickers(token: string, ids: number[]) {
  const files: FileResult[] = [];
  for (const part of chunks(ids, 100)) {
    const data = await jsonCall(
      "https://marketplace-api.wildberries.ru/api/v3/orders/stickers?type=png&width=58&height=40",
      {
        method: "POST",
        headers: wbHeaders(token),
        body: JSON.stringify({ orders: part }),
      },
      "WB",
      true,
    );
    for (const item of (data.stickers ?? []) as Array<{
      orderId?: number;
      file?: string;
    }>) {
      if (item.file)
        files.push({
          name: `wb-${item.orderId ?? files.length + 1}.png`,
          type: "image/png",
          dataUrl: `data:image/png;base64,${item.file}`,
        });
    }
  }
  return files;
}

async function formWb(
  token: string,
  msToken: string,
  requested: string[],
  requestedBoxCount: number,
) {
  const lock = acquireOperationLock("wb", requested);
  if (!lock) {
    throw new Error("Формирование этой поставки WB уже выполняется");
  }
  try {
    return await performWbForm(token, msToken, requested, requestedBoxCount);
  } finally {
    releaseOperationLock(lock);
  }
}

async function performWbForm(
  token: string,
  msToken: string,
  requested: string[],
  requestedBoxCount: number,
) {
  const requestedSet = new Set(requested.map(Number).filter(Number.isFinite));
  const boxCount = Math.trunc(Number(requestedBoxCount));
  if (!Number.isFinite(boxCount) || boxCount < 1 || boxCount > requestedSet.size)
    throw new Error("Укажите корректное количество грузомест WB");
  const [live, openSupplies] = await Promise.all([
    wbNew(token),
    wbOpenSupplyOrders(token),
  ]);
  const liveById = new Map(live.map((order) => [order.id, order]));
  const openOrderIds = new Set(openSupplies.flatMap((supply) => supply.orderIds));
  const selected = [...requestedSet]
    .filter((id) => liveById.has(id) || openOrderIds.has(id))
    .map((id) => liveById.get(id) ?? { id });
  const missing = [...requestedSet].filter(
    (id) => !liveById.has(id) && !openOrderIds.has(id),
  );
  if (missing.length) {
    throw new Error(
      `WB не нашёл ${missing.length} заказ(а) в новых или открытых поставках. Обновите данные и повторите.`,
    );
  }
  if (!selected.length && requestedSet.size) {
    throw new Error("WB не вернул заказы для формирования поставки");
  }
  const checks: Array<{ order: WbOrder; assembled: boolean; error?: string }> = [];
  for (const order of selected) {
    try {
      checks.push({
        order,
        assembled: await isAssembledInMoySklad(order.id, msToken),
      });
    } catch (error) {
      checks.push({
        order,
        assembled: false,
        error: error instanceof Error ? error.message : "Ошибка проверки МойСклад",
      });
    }
  }
  const failedChecks = checks.filter((item) => item.error);
  if (failedChecks.length) {
    throw new Error(
      `Не удалось проверить заказы WB в МойСклад: ${failedChecks.map((item) => item.error).join("; ")}`,
    );
  }
  const assembled = checks
    .filter((item) => item.assembled)
    .map((item) => item.order);
  const skipped = selected.length - assembled.length;
  if (!assembled.length && selected.length)
    throw new Error("Нет заказов WB со статусом «Собран» в МойСклад");
  if (skipped)
    throw new Error(
      "Часть выбранных заказов WB больше не имеет статуса «Собран» в МойСклад. Обновите список перед созданием поставки.",
    );

  const matchingSupplies = openSupplies.filter((supply) =>
    supply.orderIds.some((id) => requestedSet.has(id)),
  );
  if (matchingSupplies.length > 1)
    throw new Error(
      "Выбранные заказы уже находятся в разных поставках WB и не могут быть объединены",
    );
  const existingSupply = matchingSupplies[0];
  if (
    existingSupply &&
    (existingSupply.orderIds.length !== requestedSet.size ||
      existingSupply.orderIds.some((id) => !requestedSet.has(id)))
  ) {
    throw new Error(
      "В открытой поставке WB есть другие заказы. Обновите данные и сформируйте её отдельно",
    );
  }
  if (
    existingSupply &&
    assembled.some((order) => !existingSupply.orderIds.includes(order.id))
  ) {
    throw new Error(
      "Часть заказов уже находится в поставке WB. Их нельзя объединить с новыми заказами",
    );
  }

  const cargoType = assembled[0]?.cargoType ?? 0;
  const supplies: Array<{
    id: string;
    ordersCount: number;
    cargoType: number;
    boxIds: string[];
    cargoPlaces: Array<{ id: string; orderIds: string[] }>;
    boxStickers: FileResult[];
    orderStickers: FileResult[];
    supplyQr?: FileResult;
    error?: string;
  }> = [];
  const orders = assembled;
  let supplyId = existingSupply?.supplyId ?? "";
  try {
    if (!orders.length) throw new Error("Нет собранных заказов в поставке WB");
    if (!supplyId) {
      const created = await jsonCall(
        "https://marketplace-api.wildberries.ru/api/v3/supplies",
        {
          method: "POST",
          headers: wbHeaders(token),
          body: JSON.stringify({
            name: `Отгрузка ${new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow" }).format(new Date())}`,
          }),
        },
        "WB",
      );
      supplyId = String(created.id ?? "");
      if (!supplyId) throw new Error("WB не вернул номер поставки");
    }
    const ids = orders.map((order) => order.id);
    if (!existingSupply) {
      for (const part of chunks(ids, 100)) {
        await jsonCall(
          `https://marketplace-api.wildberries.ru/api/marketplace/v3/supplies/${encodeURIComponent(supplyId)}/orders`,
          {
            method: "PATCH",
            headers: wbHeaders(token),
            body: JSON.stringify({ orders: part }),
          },
          "WB",
        );
      }
    }
    const orderStickers = await wbOrderStickers(token, ids);
    const boxes = await jsonCall(
      `https://marketplace-api.wildberries.ru/api/v3/supplies/${encodeURIComponent(supplyId)}/trbx`,
      {
        method: "POST",
        headers: wbHeaders(token),
        body: JSON.stringify({ amount: boxCount }),
      },
      "WB",
    );
    const boxIds = ((boxes.trbxIds ?? []) as Array<string | number>).map(String);
    if (boxIds.length !== boxCount)
      throw new Error(
        `WB создал ${boxIds.length} из ${boxCount} грузомест`,
      );
    const formedCargoPlaces = boxIds.map((id) => ({
      id,
      orderIds: [],
    }));
    const stickerData = await jsonCall(
      `https://marketplace-api.wildberries.ru/api/v3/supplies/${encodeURIComponent(supplyId)}/trbx/stickers?type=png`,
      {
        method: "POST",
        headers: wbHeaders(token),
        body: JSON.stringify({ trbxIds: boxIds }),
      },
      "WB",
    );
    const stickersByBarcode = new Map(
      ((stickerData.stickers ?? []) as Array<{
        barcode?: string;
        file?: string;
      }>)
        .filter((item) => item.file)
        .map((item) => [String(item.barcode ?? ""), item]),
    );
    const rawStickers = (stickerData.stickers ?? []) as Array<{
      barcode?: string;
      file?: string;
    }>;
    const boxStickers = boxIds
      .map(
        (boxId, index) =>
          stickersByBarcode.get(boxId) ?? rawStickers[index],
      )
      .filter((item): item is { barcode?: string; file: string } =>
        Boolean(item?.file),
      )
      .map((item, index) => ({
        name: `${item.barcode ?? boxIds[index] ?? `box-${index + 1}`}.png`,
        type: "image/png",
        dataUrl: `data:image/png;base64,${item.file}`,
      }));
    await jsonCall(
      `https://marketplace-api.wildberries.ru/api/v3/supplies/${encodeURIComponent(supplyId)}/deliver`,
      { method: "PATCH", headers: wbHeaders(token) },
      "WB",
    );
    const qr = await jsonCall(
      `https://marketplace-api.wildberries.ru/api/v3/supplies/${encodeURIComponent(supplyId)}/barcode?type=png`,
      { headers: { Authorization: token } },
      "WB",
    );
    const supplyQr = qr.file
      ? {
          name: `${String(qr.barcode ?? supplyId)}.png`,
          type: "image/png",
          dataUrl: `data:image/png;base64,${String(qr.file)}`,
        }
      : undefined;
    supplies.push({
      id: supplyId,
      ordersCount: orders.length,
      cargoType,
      boxIds,
      cargoPlaces: formedCargoPlaces,
      boxStickers,
      orderStickers,
      supplyQr,
    });
  } catch (error) {
    console.error("WB supply formation failed", {
      supplyId: supplyId || null,
      orderCount: orders.length,
      message: error instanceof Error ? error.message : "Ошибка WB",
    });
    supplies.push({
      id: supplyId || "Не создана",
      ordersCount: orders.length,
      cargoType,
      boxIds: [],
      cargoPlaces: [],
      boxStickers: [],
      orderStickers: [],
      error: error instanceof Error ? error.message : "Ошибка WB",
    });
  }
  return { supplies, skipped };
}

async function ozonReady(clientId: string, apiKey: string) {
  const now = new Date(),
    since = new Date(now.getTime() - 30 * 86400000);
  return collectCursorPages(
    async (cursor) => {
      const data = await jsonCall(
      "https://api-seller.ozon.ru/v4/posting/fbs/list",
      {
        method: "POST",
        headers: ozonHeaders(clientId, apiKey),
        body: JSON.stringify({
          sort_dir: "ASC",
          filter: {
            since: since.toISOString(),
            to: now.toISOString(),
            statuses: ["awaiting_deliver"],
          },
          limit: 100,
          cursor,
          with: {
            analytics_data: true,
            barcodes: true,
            financial_data: false,
            legal_info: false,
            translit: true,
          },
        }),
      },
      "Ozon",
      true,
      );
      return {
        items: (data.postings ?? []) as OzonPosting[],
        cursor: typeof data.cursor === "string" ? data.cursor : undefined,
      };
    },
    (posting) => posting.posting_number,
  );
}
async function ozonLabels(clientId: string, apiKey: string, ids: string[]) {
  const files: FileResult[] = [];
  for (const part of chunks(ids, 20)) {
    const data = await jsonCall(
      "https://api-seller.ozon.ru/v2/posting/fbs/package-label",
      {
        method: "POST",
        headers: ozonHeaders(clientId, apiKey),
        body: JSON.stringify({ posting_number: part }),
      },
      "Ozon",
      true,
    );
    const content = String(data.file_content ?? "");
    if (content)
      files.push({
        name: String(data.file_name ?? `ozon-labels-${files.length + 1}.pdf`),
        type: String(data.content_type ?? "application/pdf"),
        dataUrl: `data:${String(data.content_type ?? "application/pdf")};base64,${binaryToBase64(content)}`,
      });
  }
  return files;
}

function findCarriageId(value: unknown, deliveryMethodId: number) {
  const candidates: Array<{ id: number; deliveryMethodId?: number; status?: string }> = [];
  const visit = (node: unknown, inheritedDeliveryMethodId?: number) => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      node.forEach((item) => visit(item, inheritedDeliveryMethodId));
      return;
    }
    const item = node as Record<string, unknown>;
    const delivery = item.delivery_method as Record<string, unknown> | undefined;
    const currentDeliveryMethodId = Number(
      delivery?.id ?? item.delivery_method_id ?? inheritedDeliveryMethodId ?? 0,
    );
    const looksLikeCarriage =
      "status" in item &&
      ("delivery_method" in item ||
        "delivery_method_id" in item ||
        "posting_count" in item ||
        "postings_count" in item);
    const id = Number(item.carriage_id ?? (looksLikeCarriage ? item.id : 0) ?? 0);
    if (id) {
      candidates.push({
        id,
        deliveryMethodId: currentDeliveryMethodId || undefined,
        status: String(item.status ?? "").toLocaleLowerCase("ru-RU"),
      });
    }
    Object.values(item).forEach((child) => visit(child, currentDeliveryMethodId || inheritedDeliveryMethodId));
  };
  visit(value);
  const usable = candidates.filter(
    (item) => !item.deliveryMethodId || item.deliveryMethodId === deliveryMethodId,
  );
  return usable.find((item) =>
    ["new", "unformed", "not_formed", "draft"].includes(item.status ?? ""),
  )?.id;
}

async function findOzonCarriage(
  clientId: string,
  apiKey: string,
  deliveryMethodId: number,
) {
  const headers = ozonHeaders(clientId, apiKey);
  const requestBodies = [
    { status: "new", limit: 100 },
    { filter: { status: "new" }, limit: 100 },
    { status: "unformed", limit: 100 },
    { filter: { status: "unformed" }, limit: 100 },
    { limit: 100 },
  ];
  let lastError: unknown;
  for (const body of requestBodies) {
    try {
      const data = await jsonCall(
        "https://api-seller.ozon.ru/v2/carriage/delivery/list",
        { method: "POST", headers, body: JSON.stringify(body) },
        "Ozon",
        true,
      );
      const id = findCarriageId(data, deliveryMethodId);
      if (id) return id;
    } catch (error) {
      lastError = error;
    }
  }
  if (lastError) throw lastError;
  return undefined;
}

async function createOzonCarriage(
  clientId: string,
  apiKey: string,
  deliveryMethodId: number,
) {
  const created = await jsonCall(
    "https://api-seller.ozon.ru/v1/carriage/create",
    {
      method: "POST",
      headers: ozonHeaders(clientId, apiKey),
      body: JSON.stringify({
        delivery_method_id: deliveryMethodId,
        first_mile_from_time: "00:00",
        first_mile_to_time: "23:59",
      }),
    },
    "Ozon",
  );
  const result = created.result as
    | { id?: number; carriage_id?: number }
    | undefined;
  let id = Number(result?.carriage_id ?? result?.id ?? 0);
  if (!id) {
    await sleep(700);
    id = Number(
      await findOzonCarriage(clientId, apiKey, deliveryMethodId),
    );
  }
  return id;
}

async function formOzon(clientId: string, apiKey: string, requested: string[]) {
  const lock = acquireOperationLock("ozon", requested);
  if (!lock) {
    throw new Error("Формирование этой поставки Ozon уже выполняется");
  }
  try {
    return await performOzonForm(clientId, apiKey, requested);
  } finally {
    releaseOperationLock(lock);
  }
}

async function performOzonForm(
  clientId: string,
  apiKey: string,
  requested: string[],
) {
  const confirmedIds = getConfirmedOzonIds();
  const live = await ozonReady(clientId, apiKey),
    requestedSet = new Set(requested),
    selected = live.filter(
      (item) =>
        requestedSet.has(item.posting_number) &&
        !confirmedIds.has(item.posting_number),
    );
  const groups = new Map<number, OzonPosting[]>();
  for (const posting of selected) {
    const key = posting.delivery_method?.id ?? 0;
    if (key) groups.set(key, [...(groups.get(key) ?? []), posting]);
  }
  const shipments: Array<{
    id: string;
    deliveryMethodId: number;
    ordersCount: number;
    labels: FileResult[];
    barcode?: FileResult;
    documents?: FileResult;
    status: string;
    orderIds: string[];
    error?: string;
  }> = [];
  for (const [deliveryMethodId, postings] of groups) {
    try {
      const ids = postings.map((item) => item.posting_number);
      let id = await findOzonCarriage(clientId, apiKey, deliveryMethodId);
      if (!id)
        id = await createOzonCarriage(clientId, apiKey, deliveryMethodId);
      if (!id) throw new Error("Ozon не вернул номер отгрузки");

      let confirmed = false;
      for (let attempt = 0; attempt < 2 && !confirmed; attempt++) {
        try {
          await jsonCall(
            "https://api-seller.ozon.ru/v1/carriage/set-postings",
            {
              method: "POST",
              headers: ozonHeaders(clientId, apiKey),
              body: JSON.stringify({ carriage_id: id, posting_numbers: ids }),
            },
            "Ozon",
          );
          await jsonCall(
            "https://api-seller.ozon.ru/v1/carriage/approve",
            {
              method: "POST",
              headers: ozonHeaders(clientId, apiKey),
              body: JSON.stringify({ carriage_id: id }),
            },
            "Ozon",
          );
          confirmed = true;
        } catch (error) {
          const message = error instanceof Error ? error.message : "";
          if (
            attempt === 0 &&
            message.includes("INCORRECT_CARRIAGE_STATUS")
          ) {
            id = await createOzonCarriage(
              clientId,
              apiKey,
              deliveryMethodId,
            );
            if (!id) throw new Error("Ozon не создал новую отгрузку");
            continue;
          }
          throw error;
        }
      }
      if (!confirmed) throw new Error("Ozon не подтвердил отгрузку");

      const labelResult = await confirmThenGetLabels(
        () => saveConfirmedOzonIds(ids),
        () => ozonLabels(clientId, apiKey, ids),
      );
      const labels = labelResult.labels ?? [];
      const labelsError = labelResult.error
        ? `Отгрузка подтверждена, но labels получить не удалось: ${labelResult.error}`
        : undefined;
      shipments.push({
        id: String(id),
        deliveryMethodId,
        ordersCount: ids.length,
        labels,
        status: "confirmed",
        orderIds: ids,
        error: labelsError,
      });
    } catch (error) {
      shipments.push({
        id: "Не создана",
        deliveryMethodId,
        ordersCount: postings.length,
        labels: [],
        status: "error",
        orderIds: postings.map((item) => item.posting_number),
        error: error instanceof Error ? error.message : "Ошибка Ozon",
      });
    }
  }
  return shipments;
}

export async function POST(request: NextRequest) {
  const csrfResponse = rejectCrossSiteRequest(request);
  if (csrfResponse) return csrfResponse;
  try {
    const body = (await request.json()) as {
      confirmation?: string;
      wbOrderIds?: string[];
      wbBoxCount?: number;
      wbCargoPlaces?: string[][];
      ozonOrderIds?: string[];
    };
    if (body.confirmation !== "FORM_SHIPMENTS")
      return NextResponse.json(
        { error: "Требуется подтверждение операции" },
        { status: 400 },
      );
    const {
      wbToken,
      moyskladToken: msToken,
      ozonClientId,
      ozonApiKey,
    } = getApiCredentials();
    const wbOrderIds = [...new Set(body.wbOrderIds ?? [])],
      ozonOrderIds = [...new Set(body.ozonOrderIds ?? [])];
    const [wbResult, ozon] = await Promise.all([
      wbToken && msToken && wbOrderIds.length
        ? formWb(
            wbToken,
            msToken,
            wbOrderIds,
            body.wbBoxCount ?? body.wbCargoPlaces?.length ?? 1,
          )
        : Promise.resolve({ supplies: [], skipped: 0 }),
      ozonClientId && ozonApiKey && ozonOrderIds.length
        ? formOzon(ozonClientId, ozonApiKey, ozonOrderIds)
        : Promise.resolve([]),
    ]);
    return NextResponse.json({
      wb: wbResult.supplies,
      ozon,
      warnings: [
        !wbToken && wbOrderIds.length ? "WB не подключён" : "",
        !msToken && wbOrderIds.length ? "МойСклад не подключён" : "",
        wbResult.skipped
          ? `Пропущено заказов WB без статуса «Собран» в МойСклад: ${wbResult.skipped}`
          : "",
        (!ozonClientId || !ozonApiKey) && ozonOrderIds.length
          ? "Ozon не подключён"
          : "",
      ].filter(Boolean),
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Не удалось сформировать отгрузки",
      },
      { status: 500 },
    );
  }
}
