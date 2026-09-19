export function isSameOriginRequest(request: Request) {
  const fetchSite = request.headers.get("sec-fetch-site")?.toLowerCase();
  if (fetchSite === "cross-site") return false;

  const origin = request.headers.get("origin");
  const expectedOrigin = new URL(request.url).origin;
  if (origin) {
    try {
      if (new URL(origin).origin !== expectedOrigin) return false;
    } catch {
      return false;
    }
    return true;
  }

  return fetchSite === "same-origin";
}