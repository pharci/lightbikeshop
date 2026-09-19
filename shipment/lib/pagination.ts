export async function collectCursorPages<T>(
  fetchPage: (cursor: string) => Promise<{ items: T[]; cursor?: string }>,
  getKey: (item: T) => string,
  maxPages = 50,
) {
  const items = new Map<string, T>();
  const seenCursors = new Set<string>();
  let cursor = "";

  for (let page = 0; page < maxPages; page++) {
    const result = await fetchPage(cursor);
    for (const item of result.items) items.set(getKey(item), item);
    const nextCursor = String(result.cursor ?? "").trim();
    if (!nextCursor || seenCursors.has(nextCursor)) break;
    seenCursors.add(nextCursor);
    cursor = nextCursor;
  }
  return [...items.values()];
}