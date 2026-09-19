import { externalFetch } from "@/lib/http";

const REQUEST_DELAY_MS = 300;
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

let requestQueue = Promise.resolve();
let lastRequestAt = 0;

const msHeaders = (token: string) => ({
  Authorization: `Bearer ${token}`,
  Accept: "application/json;charset=utf-8",
});

const queuedRequest = <T>(request: () => Promise<T>) => {
  const next = requestQueue.then(async () => {
    const wait = REQUEST_DELAY_MS - (Date.now() - lastRequestAt);
    if (wait > 0) await sleep(wait);
    lastRequestAt = Date.now();
    return request();
  });
  requestQueue = next.then(
    () => undefined,
    () => undefined,
  );
  return next;
};

export async function getMoySkladCustomerOrder(
  orderId: number | string,
  token: string,
) {
  return queuedRequest(async () => {
    const name = `WB${orderId}`;
    const url = `https://api.moysklad.ru/api/remap/1.2/entity/customerorder?limit=2&expand=state&filter=${encodeURIComponent(`name=${name}`)}`;
    const response = await externalFetch(
      url,
      { headers: msHeaders(token) },
      { retryable: true },
    );
    if (!response.ok)
      throw new Error(`МойСклад не вернул заказ ${name}: ${response.status}`);
    return (await response.json()) as {
      rows?: Array<{ name?: string; state?: { name?: string } }>;
    };
  });
}