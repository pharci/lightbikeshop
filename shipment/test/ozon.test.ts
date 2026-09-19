import assert from "node:assert/strict";
import test from "node:test";
import { confirmThenGetLabels } from "../lib/ozon.ts";

test("Ozon confirmation is persisted before labels and survives label failure", async () => {
  const events: string[] = [];
  const result = await confirmThenGetLabels(
    () => events.push("confirmed"),
    async () => {
      events.push("labels");
      throw new Error("429");
    },
  );
  assert.deepEqual(events, ["confirmed", "labels"]);
  assert.deepEqual(result, { error: "429" });
});