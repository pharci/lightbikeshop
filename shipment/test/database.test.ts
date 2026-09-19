import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

process.env.SHIPMENT_DB_PATH = join(mkdtempSync(join(tmpdir(), "shipment-test-")), "shipment.sqlite");
const {
  acquireOperationLock,
  releaseOperationLock,
} = await import("../lib/database.ts");

test("operation lock is atomic, sorted, owner-bound, and releasable", () => {
  const [first, second] = [
    acquireOperationLock("wb", [3, 1, 2, 1]),
    acquireOperationLock("wb", [2, 3, 1]),
  ];
  assert.ok(first);
  assert.equal(first.operationKey, "wb:1,2,3");
  assert.equal(second, null);

  releaseOperationLock({ ...first, owner: "another-owner" });
  assert.equal(acquireOperationLock("wb", [1, 2, 3]), null);

  releaseOperationLock(first);
  assert.ok(acquireOperationLock("wb", [1, 2, 3]));
});

test("expired operation lock can be recovered", async () => {
  const first = acquireOperationLock("ozon", ["A"], 1);
  assert.ok(first);
  await new Promise((resolve) => setTimeout(resolve, 5));
  const recovered = acquireOperationLock("ozon", ["A"], 1000);
  assert.ok(recovered);
  releaseOperationLock(recovered);
});