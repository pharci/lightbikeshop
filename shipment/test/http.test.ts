import assert from "node:assert/strict";
import test from "node:test";
import { externalFetch } from "../lib/http.ts";

const response = (status: number, headers?: Record<string, string>) =>
  new Response("{}", { status, headers });

test("HTTP retry retries 429 and 500, then succeeds", async () => {
  const originalFetch = globalThis.fetch;
  const originalSetTimeout = globalThis.setTimeout;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return calls === 3
      ? response(200)
      : response(calls === 1 ? 429 : 500, { "Retry-After": "0" });
  };
  globalThis.setTimeout = ((callback: () => void) => {
    callback();
    return 0;
  }) as unknown as typeof setTimeout;
  try {
    const result = await externalFetch("https://api.example/orders", undefined, {
      retryable: true,
    });
    assert.equal(result.status, 200);
    assert.equal(calls, 3);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.setTimeout = originalSetTimeout;
  }
});

test("HTTP does not retry ordinary 4xx or unsafe methods by default", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async (_url, init) => {
    calls += 1;
    return response(init?.method === "POST" ? 500 : calls === 1 ? 400 : 500);
  };
  try {
    const badRequest = await externalFetch("https://api.example/orders", {
      method: "GET",
    });
    assert.equal(badRequest.status, 400);
    assert.equal(calls, 1);

    calls = 0;
    const mutation = await externalFetch("https://api.example/orders", {
      method: "POST",
    });
    assert.equal(mutation.status, 500);
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("HTTP stops after four failed retryable attempts", async () => {
  const originalFetch = globalThis.fetch;
  const originalSetTimeout = globalThis.setTimeout;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return response(429);
  };
  globalThis.setTimeout = ((callback: () => void) => {
    callback();
    return 0;
  }) as unknown as typeof setTimeout;
  try {
    const result = await externalFetch("https://api.example/orders", undefined, {
      retryable: true,
    });
    assert.equal(result.status, 429);
    assert.equal(calls, 4);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.setTimeout = originalSetTimeout;
  }
});