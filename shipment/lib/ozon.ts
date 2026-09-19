export async function confirmThenGetLabels<T>(
  confirm: () => void,
  getLabels: () => Promise<T>,
) {
  confirm();
  try {
    return { labels: await getLabels() };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "Не удалось получить labels",
    };
  }
}