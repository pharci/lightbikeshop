export function isSameOriginRequest(request: Request) {
  const fetchSite = request.headers.get("sec-fetch-site")?.toLowerCase();
  if (fetchSite === "cross-site") return false;

  const origin = request.headers.get("origin");
  const requestUrl = new URL(request.url);
  const host = request.headers.get("host")?.trim();
  const forwardedProto = request.headers.get("x-forwarded-proto")?.toLowerCase();
  const protocol = forwardedProto === "https" || forwardedProto === "http"
    ? forwardedProto
    : requestUrl.protocol.replace(":", "");
  const expectedOrigin = host
    ? `${protocol}://${host}`
    : requestUrl.origin;
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