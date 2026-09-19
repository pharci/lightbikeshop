import assert from "node:assert/strict";
import test from "node:test";
import { collectCursorPages } from "../lib/pagination.ts";

test("cursor pagination deduplicates and stops on repeated cursor", async () => {
  const cursors: string[] = [];
  const result = await collectCursorPages(
    async (cursor) => {
      cursors.push(cursor);
      if (!cursor) return { items: [{ id: "1" }], cursor: "a" };
      if (cursor === "a") return { items: [{ id: "2" }, { id: "1" }], cursor: "b" };
      return { items: [{ id: "3" }], cursor: "b" };
    },
    (item) => item.id,
  );
  assert.deepEqual(result.map((item) => item.id), ["1", "2", "3"]);
  assert.deepEqual(cursors, ["", "a", "b"]);
});

test("cursor pagination stops at 50 pages", async () => {
  let calls = 0;
  const result = await collectCursorPages(
    async (cursor) => {
      calls += 1;
      return { items: [{ id: cursor || "0" }], cursor: String(calls) };
    },
    (item) => item.id,
  );
  assert.equal(calls, 50);
  assert.equal(result.length, 50);
});