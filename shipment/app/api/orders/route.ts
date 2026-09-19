import { getConfirmedOzonIds } from "@/lib/database";
import { NextResponse } from "next/server";
import { getApiCredentials } from "@/lib/api-credentials";
import { getMoySkladCustomerOrder } from "@/lib/moysklad";
import { externalJson } from "@/lib/http";
import { collectCursorPages } from "@/lib/pagination";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
type Market = "wb" | "ozon";
type ApiOrder = {
  id: string;
  market: Market;
  created: string;
  title: string;
  sku: string;
  qty: number;
  status: string;
  image?: string;
  labelNumber?: string;
  reserve: "Ожидает подключения";
};
type WbOrder = {
  id: number;
  createdAt?: string;
  supplierArticle?: string;
  nmId?: number;
  chrtId?: number;
  skus?: string[];
};
type WbProductDetail = { title?: string; image?: string };
type WbSupply = {
  id: string;
  name?: string;
  createdAt?: string;
  closedAt?: string;
  scanDt?: string;
  done?: boolean;
  cargoType?: number;
};
type SupplyCard = {
  id: string;
  name: string;
  created: string;
  ordersCount: number;
  orderIds: string[];
  items: ApiOrder[];
  status: string;
  processed: boolean;
  barcode: string;
  qrDataUrl?: string;
  boxStickers: Array<{ barcode: string; dataUrl: string }>;
};

const showDate = (value?: string) =>
  value
    ? new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Europe/Moscow",
      }).format(new Date(value))
    : "—";
const wbHeaders = (token: string) => ({ Authorization: token });
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const isMoySkladReadyState = (state: string) =>
  state.includes("собран") || state.includes("доставк");
async function wbJson<T>(
  url: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  return externalJson<T>(
    url,
    {
      ...init,
      headers: { ...wbHeaders(token), ...(init?.headers ?? {}) },
    },
    "WB",
    { retryable: true },
  );
}
function mapWbOrder(
  order: WbOrder,
  status: string,
  details?: Map<number, WbProductDetail>,
  stickerNumbers?: Map<number, string>,
): ApiOrder {
  const detail = order.nmId ? details?.get(order.nmId) : undefined;
  return {
    id: String(order.id),
    market: "wb",
    created: showDate(order.createdAt),
    title:
      detail?.title ||
      order.supplierArticle ||
      `Товар WB № ${order.nmId ?? "—"}`,
    sku: order.skus?.[0] || order.supplierArticle || "—",
    qty: 1,
    status,
    image: detail?.image,
    labelNumber: stickerNumbers?.get(order.id),
    reserve: "Ожидает подключения",
  };
}

async function getWbProductDetails(token: string, orders: WbOrder[]) {
  const wanted = new Set(
    orders.map((order) => order.nmId).filter((id): id is number => Boolean(id)),
  );
  const details = new Map<number, WbProductDetail>();
  if (!wanted.size) return details;
  try {
    let updatedAt = "";
    let nmID = 0;
    for (let page = 0; page < 20 && details.size < wanted.size; page++) {
      const response = await fetch(
        "https://content-api.wildberries.ru/content/v2/get/cards/list",
        {
          method: "POST",
          headers: { Authorization: token, "Content-Type": "application/json" },
          body: JSON.stringify({
            settings: {
              cursor: { limit: 100, ...(updatedAt ? { updatedAt, nmID } : {}) },
              filter: { withPhoto: -1 },
            },
          }),
          cache: "no-store",
        },
      );
      if (!response.ok) break;
      const data = (await response.json()) as {
        cards?: Array<{
          nmID?: number;
          title?: string;
          vendorCode?: string;
          photos?: Array<{ big?: string; c516x688?: string; c246x328?: string }>;
        }>;
        cursor?: { updatedAt?: string; nmID?: number; total?: number };
      };
      for (const card of data.cards ?? []) {
        if (!card.nmID || !wanted.has(card.nmID)) continue;
        const photo = card.photos?.[0];
        details.set(card.nmID, {
          title: card.title || card.vendorCode,
          image: photo?.c516x688 || photo?.big || photo?.c246x328,
        });
      }
      if (!(data.cards ?? []).length || !data.cursor?.updatedAt) break;
      updatedAt = data.cursor.updatedAt;
      nmID = data.cursor.nmID ?? 0;
    }
  } catch {}
  for (const nmId of wanted) {
    const current = details.get(nmId);
    if (!current?.image) {
      details.set(nmId, {
        ...current,
        image: `https://images.wbstatic.net/c516x688/new/${nmId}-1.jpg`,
      });
    }
  }
  return details;
}

async function getWbStickerNumbers(token: string, orders: WbOrder[]) {
  const result = new Map<number, string>();
  for (let index = 0; index < orders.length; index += 100) {
    const ids = orders.slice(index, index + 100).map((order) => order.id);
    if (!ids.length) continue;
    try {
      const data = await wbJson<{
        stickers?: Array<{
          orderId?: number;
          barcode?: string;
          partA?: number;
          partB?: number;
        }>;
      }>(
        "https://marketplace-api.wildberries.ru/api/v3/orders/stickers?type=png&width=58&height=40",
        token,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ orders: ids }),
        },
      );
      for (const sticker of data.stickers ?? []) {
        if (!sticker.orderId) continue;
        const number =
          sticker.partA != null && sticker.partB != null
            ? `${sticker.partA} · ${sticker.partB}`
            : sticker.partA != null
              ? String(sticker.partA)
              : sticker.partB != null
                ? String(sticker.partB)
                : "";
        if (number) result.set(sticker.orderId, String(number));
      }
    } catch {}
  }
  return result;
}

async function getWbNew(token: string) {
  const data = await wbJson<{ orders?: WbOrder[] }>(
    "https://marketplace-api.wildberries.ru/api/v3/orders/new",
    token,
  );
  const orders = data.orders ?? [];
  const details = await getWbProductDetails(token, orders);
  return orders.map((order) => mapWbOrder(order, "Новый", details));
}
async function filterAssembledWbOrders(orders: ApiOrder[], token: string) {
  const checks = [] as Array<{
    order: ApiOrder;
    assembled: boolean;
    registered: boolean;
    error?: string;
  }>;
  for (const order of orders) {
    try {
      const data = await getMoySkladCustomerOrder(order.id, token);
      const msOrder = (data.rows ?? []).find(
        (row) => row.name === `WB${order.id}`,
      );
      if (!msOrder) {
        checks.push({ order, assembled: false, registered: false });
        continue;
      }
      const state = msOrder.state?.name?.toLocaleLowerCase("ru-RU") ?? "";
      const ready = isMoySkladReadyState(state);
      checks.push({
        order: {
          ...order,
          status: ready
            ? "Собран в МойСклад"
            : "Ожидает сборки через МойСклад",
        },
        assembled: ready,
        registered: true,
      });
    } catch (error) {
      checks.push({
        order,
        assembled: false,
        registered: false,
        error: error instanceof Error ? error.message : "Ошибка проверки МойСклад",
      });
    }
  }
  return {
    ready: checks.filter((item) => item.registered && item.assembled).map((item) => item.order),
    waiting: checks.filter((item) => item.registered && !item.assembled).map((item) => item.order),
    errors: checks.filter((item) => item.error).map((item) => item.error),
  };
}
async function getWbSupplyOrderIds(token: string, supplyId: string) {
  try {
    const data = await wbJson<{ orderIds?: number[]; orders?: number[] }>(
      `https://marketplace-api.wildberries.ru/api/marketplace/v3/supplies/${encodeURIComponent(supplyId)}/order-ids`,
      token,
    );
    const ids = data.orderIds ?? data.orders ?? [];
    if (ids.length) return ids.map(String);
  } catch {}
  try {
    const data = await wbJson<{ orders?: WbOrder[] }>(
      `https://marketplace-api.wildberries.ru/api/v3/supplies/${encodeURIComponent(supplyId)}/orders`,
      token,
    );
    return (data.orders ?? []).map((order) => String(order.id));
  } catch {
    return [];
  }
}
async function getWbHistory(token: string) {
  const to = Math.floor(Date.now() / 1000);
  const from = to - 30 * 24 * 60 * 60;
  let next = 0;
  const all: WbOrder[] = [];
  for (let page = 0; page < 10; page++) {
    const data = await wbJson<{ orders?: WbOrder[]; next?: number }>(
      `https://marketplace-api.wildberries.ru/api/v3/orders?limit=1000&next=${next}&dateFrom=${from}&dateTo=${to}`,
      token,
    );
    all.push(...(data.orders ?? []));
    if (!data.next || data.next === next || (data.orders ?? []).length === 0)
      break;
    next = data.next;
  }
  const statusById = new Map<number, string>();
  for (let i = 0; i < all.length; i += 1000) {
    const ids = all.slice(i, i + 1000).map((order) => order.id);
    if (!ids.length) continue;
    const data = await wbJson<{
      orders?: Array<{
        id: number;
        supplierStatus?: string;
        wbStatus?: string;
      }>;
    }>("https://marketplace-api.wildberries.ru/api/v3/orders/status", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ orders: ids }),
    });
    for (const item of data.orders ?? []) {
      const label: Record<string, string> = {
        new: "Новый",
        confirm: "На сборке",
        complete: "В поставке",
        cancel: "Отменён",
        sold: "Продан",
      };
      statusById.set(
        item.id,
        label[item.supplierStatus ?? ""] ||
          label[item.wbStatus ?? ""] ||
          item.supplierStatus ||
          item.wbStatus ||
          "Неизвестно",
      );
    }
  }
  const [details, stickerNumbers] = await Promise.all([
    getWbProductDetails(token, all),
    getWbStickerNumbers(token, all),
  ]);
  return all.map((order) =>
    mapWbOrder(
      order,
      statusById.get(order.id) || "Неизвестно",
      details,
      stickerNumbers,
    ),
  );
}
async function getWbSupplies(
  token: string,
  historyById: Map<string, ApiOrder>,
): Promise<SupplyCard[]> {
  const data = await wbJson<{ supplies?: WbSupply[] }>(
    "https://marketplace-api.wildberries.ru/api/v3/supplies?limit=1000&next=0",
    token,
  );
  const monthAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
  const visible = (data.supplies ?? [])
    .filter(
      (supply) =>
        !supply.done ||
        Boolean(
          supply.closedAt && new Date(supply.closedAt).getTime() >= monthAgo,
        ),
    )
    .slice(0, 100);
  const cards: SupplyCard[] = [];
  for (const supply of visible) {
      if (cards.length) await sleep(180);
      const orderIds = await getWbSupplyOrderIds(token, supply.id);
      const orderCount = orderIds.length;
      let processed = Boolean(supply.scanDt);
      if (!processed && orderIds.length) {
        try {
          const state = await wbJson<{
            orders?: Array<{ id: number; wbStatus?: string }>;
          }>(
            "https://marketplace-api.wildberries.ru/api/v3/orders/status",
            token,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ orders: orderIds.map(Number) }),
            },
          );
          const rows = state.orders ?? [];
          processed =
            rows.length > 0 &&
            rows.every(
              (row) => !["waiting", "new"].includes(row.wbStatus ?? "waiting"),
            );
        } catch {}
      }
      const [barcodeResult, boxesResult] = await Promise.allSettled([
        supply.done && !processed
          ? wbJson<{ barcode?: string; file?: string }>(
              `https://marketplace-api.wildberries.ru/api/v3/supplies/${encodeURIComponent(supply.id)}/barcode?type=png`,
              token,
            )
          : Promise.resolve({ barcode: supply.id }),
        wbJson<{
          trbxes?: Array<{ id?: string; barcode?: string } | string>;
          trbxIds?: string[];
        }>(
          `https://marketplace-api.wildberries.ru/api/v3/supplies/${encodeURIComponent(supply.id)}/trbx`,
          token,
        ),
      ]);
      const barcode =
        barcodeResult.status === "fulfilled"
          ? barcodeResult.value.barcode || supply.id
          : supply.id;
      const file =
        barcodeResult.status === "fulfilled" && "file" in barcodeResult.value
          ? barcodeResult.value.file
          : undefined;
      const qrDataUrl = file
        ? file.startsWith("data:")
          ? file
          : `data:image/png;base64,${file}`
        : undefined;
      const trbxIds =
        boxesResult.status === "fulfilled"
          ? [
              ...(boxesResult.value.trbxIds ?? []),
              ...(boxesResult.value.trbxes ?? []).map((box) =>
                typeof box === "string" ? box : (box.id ?? box.barcode ?? ""),
              ),
            ].filter(Boolean)
          : [];
      let boxStickers: Array<{ barcode: string; dataUrl: string }> = [];
      if (trbxIds.length && !processed) {
        try {
          const stickerData = await wbJson<{
            stickers?: Array<{ barcode?: string; file?: string }>;
          }>(
            `https://marketplace-api.wildberries.ru/api/v3/supplies/${encodeURIComponent(supply.id)}/trbx/stickers?type=png`,
            token,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ trbxIds }),
            },
          );
          boxStickers = (stickerData.stickers ?? [])
            .filter((sticker) => sticker.file)
            .map((sticker, index) => ({
              barcode:
                sticker.barcode || trbxIds[index] || `Грузоместо ${index + 1}`,
              dataUrl: `data:image/png;base64,${sticker.file}`,
            }));
        } catch {
          boxStickers = [];
        }
      }
      const status = processed
        ? "Поставка обработана"
        : supply.done
          ? "Отгрузите поставку"
          : "На сборке";
      cards.push({
        id: supply.id,
        name: supply.name || `Поставка ${supply.id}`,
        created: showDate(supply.createdAt),
        ordersCount: orderCount,
        orderIds,
        items: orderIds
          .map((orderId) => historyById.get(orderId))
          .filter((order): order is ApiOrder => Boolean(order)),
        status,
        processed,
        barcode,
        qrDataUrl,
        boxStickers,
      });
  }
  return cards;
}

type OzonPosting = {
  posting_number: string;
  in_process_at?: string;
  status?: string;
  products?: Array<{ name?: string; offer_id?: string; quantity?: number }>;
  delivery_method?: { id?: number; warehouse_id?: number };
};
async function ozonList(clientId: string, apiKey: string, statuses: string[]) {
  const now = new Date();
  const since = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  return collectCursorPages(
    async (cursor) => {
      const data = await externalJson<{ postings?: OzonPosting[]; cursor?: string }>(
      "https://api-seller.ozon.ru/v4/posting/fbs/list",
      {
        method: "POST",
        headers: {
          "Client-Id": clientId,
          "Api-Key": apiKey,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          sort_dir: "ASC",
          filter: { since: since.toISOString(), to: now.toISOString(), statuses },
          limit: 100,
          cursor,
          with: {
            analytics_data: true,
            barcodes: false,
            financial_data: false,
            legal_info: false,
            translit: true,
          },
        }),
      },
      "Ozon",
      { retryable: true },
      );
      return { items: data.postings ?? [], cursor: data.cursor };
    },
    (posting) => posting.posting_number,
  );
}
async function getOzonImages(clientId: string, apiKey: string, offerIds: string[]) {
  const result = new Map<string, string>();
  if (!offerIds.length) return result;
  try {
    const data = await externalJson<{
      items?: Array<{ offer_id?: string; primary_image?: string; images?: string[] }>;
      result?: { items?: Array<{ offer_id?: string; primary_image?: string; images?: string[] }> };
    }>("https://api-seller.ozon.ru/v3/product/info/list", {
      method: "POST",
      headers: {
        "Client-Id": clientId,
        "Api-Key": apiKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ offer_id: [...new Set(offerIds)].slice(0, 1000) }),
    }, "Ozon", { retryable: true });
    for (const item of data.items ?? data.result?.items ?? []) {
      const image = item.primary_image || item.images?.[0];
      if (item.offer_id && image) result.set(item.offer_id, image);
    }
  } catch {}
  return result;
}
function mapOzon(posting: OzonPosting, status: string, images?: Map<string, string>): ApiOrder {
  const first = posting.products?.[0];
  const extra = Math.max(0, (posting.products?.length ?? 1) - 1);
  return {
    id: posting.posting_number,
    market: "ozon",
    created: showDate(posting.in_process_at),
    title: `${first?.name || "Заказ Ozon"}${extra ? ` + ещё ${extra}` : ""}`,
    sku: first?.offer_id || "—",
    qty:
      (posting.products ?? []).reduce((sum, p) => sum + (p.quantity ?? 0), 0) ||
      1,
    status,
    image: first?.offer_id ? images?.get(first.offer_id) : undefined,
    reserve: "Ожидает подключения",
  };
}
async function getOzonOrders(clientId: string, apiKey: string) {
  const postings = await ozonList(clientId, apiKey, [
    "awaiting_packaging",
    "awaiting_deliver",
  ]);
  const images = await getOzonImages(
    clientId,
    apiKey,
    postings.flatMap((posting) => posting.products?.map((product) => product.offer_id || "") ?? []).filter(Boolean),
  );
  const confirmed = getConfirmedOzonIds();
  return postings.map((p) =>
    mapOzon(
      p,
      confirmed.has(p.posting_number)
        ? "Подтверждённая отгрузка"
        : p.status === "awaiting_deliver"
          ? "Готов к отгрузке"
          : "Новый",
      images,
    ),
  );
}
async function getOzonHistory(clientId: string, apiKey: string) {
  const statuses = [
    "awaiting_packaging",
    "awaiting_deliver",
    "delivering",
    "delivered",
    "cancelled",
  ];
  const postings = await ozonList(clientId, apiKey, statuses);
  const [confirmed, images] = await Promise.all([
    Promise.resolve(getConfirmedOzonIds()),
    getOzonImages(
      clientId,
      apiKey,
      postings
        .flatMap(
          (posting) =>
            posting.products?.map((product) => product.offer_id || "") ?? [],
        )
        .filter(Boolean),
    ),
  ]);
  const labels: Record<string, string> = {
    awaiting_packaging: "Ожидает сборки",
    awaiting_deliver: "Готов к отгрузке",
    delivering: "Доставляется",
    delivered: "Доставлен",
    cancelled: "Отменён",
  };
  return postings.map((p) =>
    mapOzon(
      p,
      confirmed.has(p.posting_number)
        ? "Подтверждённая отгрузка"
        : labels[p.status ?? ""] || p.status || "Неизвестно",
      images,
    ),
  );
}

export async function GET(request: Request) {
  const {
    wbToken,
    ozonClientId,
    ozonApiKey,
    moyskladToken: msToken,
  } = getApiCredentials();
  const result: {
    orders: ApiOrder[];
    history: ApiOrder[];
    supplies: SupplyCard[];
    connections: { wb: boolean; ozon: boolean };
    errors: Partial<Record<Market | string, string>>;
    syncedAt: string;
    waitingWbAssembly: number;
  } = {
    orders: [],
    history: [],
    supplies: [],
    connections: {
      wb: Boolean(wbToken),
      ozon: Boolean(ozonClientId && ozonApiKey),
    },
    errors: {},
    syncedAt: new Date().toISOString(),
    waitingWbAssembly: 0,
  };
  const tasks: Promise<void>[] = [];
  if (wbToken) {
    const wbHistoryPromise = getWbHistory(wbToken);
    tasks.push(
      Promise.all([getWbNew(wbToken), wbHistoryPromise])
        .then(async ([newOrders, history]) => {
          if (!msToken)
            throw new Error("МойСклад не подключён — заказы WB заблокированы");
          const active = new Map<string, ApiOrder>();
          for (const order of newOrders) active.set(order.id, order);
          for (const order of history) {
            if (["Новый", "На сборке"].includes(order.status)) {
              active.set(order.id, order);
            }
          }
          const filtered = await filterAssembledWbOrders(
            [...active.values()],
            msToken,
          );
          result.orders.push(...filtered.ready, ...filtered.waiting);
          result.waitingWbAssembly = filtered.waiting.length;
          if (filtered.errors.length) {
            result.errors.moysklad = `Не удалось проверить заказы WB: ${filtered.errors.join("; ")}`;
          }
        })
        .catch((error) => {
          result.errors.wb =
            error instanceof Error ? error.message : "Ошибка WB";
        }),
    );
    tasks.push(
      wbHistoryPromise
        .then((history) => {
          result.history.push(...history);
        })
        .catch((error) => {
          result.errors.wbHistory =
            error instanceof Error ? error.message : "Ошибка истории WB";
        }),
    );
    tasks.push(
      wbHistoryPromise
        .then(
          (history) =>
            new Map(
              history.map((order) => [order.id, order] as const),
            ),
        )
        .then((historyById) => getWbSupplies(wbToken, historyById))
        .then((supplies) => {
          result.supplies = supplies;
        })
        .catch((error) => {
          result.errors.wbSupplies =
            error instanceof Error ? error.message : "Ошибка поставок WB";
        }),
    );
  }
  if (ozonClientId && ozonApiKey) {
    tasks.push(
      getOzonOrders(ozonClientId, ozonApiKey)
        .then((orders) => {
          result.orders.push(...orders);
        })
        .catch((error) => {
          result.errors.ozon =
            error instanceof Error ? error.message : "Ошибка Ozon";
        }),
    );
    tasks.push(
      getOzonHistory(ozonClientId, ozonApiKey)
        .then((history) => {
          result.history.push(...history);
        })
        .catch((error) => {
          result.errors.ozonHistory =
            error instanceof Error ? error.message : "Ошибка истории Ozon";
        }),
    );
  }
  await Promise.all(tasks);
  return NextResponse.json(result, {
    headers: { "Cache-Control": "no-store" },
  });
}
