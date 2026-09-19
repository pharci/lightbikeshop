import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";

const defaultPath = resolve(process.cwd(), "data", "shipment.sqlite");
const databasePath = process.env.SHIPMENT_DB_PATH || defaultPath;

let database: DatabaseSync | undefined;

function getConnection() {
  if (database) return database;

  mkdirSync(dirname(databasePath), { recursive: true });
  database = new DatabaseSync(databasePath);
  database.exec(`
    PRAGMA journal_mode = WAL;
    PRAGMA busy_timeout = 5000;

    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      marketplace TEXT NOT NULL,
      external_id TEXT NOT NULL,
      status TEXT NOT NULL,
      warehouse_id TEXT,
      moysklad_order_id TEXT,
      reserve_status TEXT NOT NULL DEFAULT 'pending',
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      UNIQUE (marketplace, external_id)
    );

    CREATE INDEX IF NOT EXISTS idx_orders_marketplace_status
      ON orders (marketplace, status);
  `);

  return database;
}

export function getConfirmedOzonIds() {
  const rows = getConnection()
    .prepare(
      "SELECT external_id FROM orders WHERE marketplace = ? AND status = ?",
    )
    .all("ozon", "confirmed") as Array<{ external_id: string }>;

  return new Set(rows.map((row) => row.external_id));
}

export function saveConfirmedOzonIds(orderIds: string[]) {
  const db = getConnection();
  const statement = db.prepare(`
    INSERT INTO orders
      (marketplace, external_id, status, reserve_status, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(marketplace, external_id)
    DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
  `);
  const now = Date.now();

  db.exec("BEGIN");
  try {
    for (const orderId of orderIds) {
      statement.run("ozon", orderId, "confirmed", "confirmed", now, now);
    }
    db.exec("COMMIT");
  } catch (error) {
    try {
      db.exec("ROLLBACK");
    } catch {}
    throw error;
  }
}
