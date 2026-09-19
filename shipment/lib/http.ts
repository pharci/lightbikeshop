const MAX_ATTEMPTS = 4;
const FALLBACK_DELAY_MS = 450;
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const retryAfterMs = (response: Response, attempt: number) => {
  const value = response.headers.get("retry-after")?.trim();
  const seconds = value ? Number(value) : NaN;
  const delay = Number.isFinite(seconds)
    ? seconds * 1000
    : value
      ? Math.max(0, Date.parse(value) - Date.now())
      : 0;
  return Math.max(delay, FALLBACK_DELAY_MS * (attempt + 1));
};

export async function externalFetch(
  url: string,
  init: RequestInit = {},
  options: { retryable?: boolean } = {},
) {
  const method = (init.method ?? "GET").toUpperCase();
  const retryable =
    options.retryable ?? ["GET", "HEAD", "OPTIONS"].includes(method);
  let response: Response | undefined;

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    response = await fetch(url, { ...init, cache: "no-store" });
    if (response.ok) return response;
    const retryStatus = response.status === 429 || response.status >= 500;
    if (!retryable || !retryStatus || attempt === MAX_ATTEMPTS - 1) break;
    await sleep(retryAfterMs(response, attempt));
  }
  return response as Response;
}

export async function externalJson<T>(
  url: string,
  init: RequestInit,
  label: string,
  options: { retryable?: boolean } = {},
) {
  const response = await externalFetch(url, init, options);
  const text = await response.text();
  let data: Record<string, unknown> = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { message: text };
  }
  if (!response.ok) {
    const message = data.message
      ? String(data.message)
      : data.error
        ? typeof data.error === "string"
          ? data.error
          : JSON.stringify(data.error)
        : `${label}: ошибка ${response.status}`;
    throw new Error(message);
  }
  return data as T;
}