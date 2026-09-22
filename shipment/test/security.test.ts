import assert from "node:assert/strict";
import test from "node:test";
import { isSameOriginRequest } from "../lib/csrf.ts";

const makeRequest = (headers: HeadersInit = {}) =>
  new Request("http://shipment:3000/api/test", {
    method: "POST",
    headers: { host: "shipment.example", ...headers },
  });

test("CSRF accepts same-origin requests with matching Origin", () => {
  assert.equal(
    isSameOriginRequest(
      makeRequest({
        "sec-fetch-site": "same-origin",
        origin: "http://shipment.example",
      }),
    ),
    true,
  );
});

test("CSRF accepts matching Origin without Fetch Metadata", () => {
  assert.equal(
    isSameOriginRequest(makeRequest({ origin: "http://shipment.example" })),
    true,
  );
});

test("CSRF rejects cross-site, invalid Origin, and missing headers", () => {
  const cases: HeadersInit[] = [
    { "sec-fetch-site": "cross-site", origin: "http://shipment.example" },
    { origin: "http://evil.example" },
    { origin: "null" },
    { origin: "not-an-origin" },
    {},
  ];
  for (const headers of cases) {
    assert.equal(isSameOriginRequest(makeRequest(headers)), false);
  }
});