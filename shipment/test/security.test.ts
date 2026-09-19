import assert from "node:assert/strict";
import test from "node:test";
import { isSameOriginRequest } from "../lib/csrf.ts";

const makeRequest = (headers: HeadersInit = {}) =>
  new Request("https://shipment.example/api/test", {
    method: "POST",
    headers,
  });

test("CSRF accepts same-origin requests with matching Origin", () => {
  assert.equal(
    isSameOriginRequest(
      makeRequest({
        "sec-fetch-site": "same-origin",
        origin: "https://shipment.example",
      }),
    ),
    true,
  );
});

test("CSRF accepts matching Origin without Fetch Metadata", () => {
  assert.equal(
    isSameOriginRequest(makeRequest({ origin: "https://shipment.example" })),
    true,
  );
});

test("CSRF rejects cross-site, invalid Origin, and missing headers", () => {
  const cases: HeadersInit[] = [
    { "sec-fetch-site": "cross-site", origin: "https://shipment.example" },
    { origin: "https://evil.example" },
    { origin: "null" },
    { origin: "not-an-origin" },
    {},
  ];
  for (const headers of cases) {
    assert.equal(isSameOriginRequest(makeRequest(headers)), false);
  }
});