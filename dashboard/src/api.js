// The dashboard's only way to reach the server. Read-only by construction:
// GET, and only the endpoints below. Nothing here can reach /observation or
// any signal-control path, and the tests pin that.

// The id part is the server's INTERSECTION_ID, length included (P142).
export const ALLOWED = [
  /^\/count_forecast\/[A-Za-z0-9_-]{1,32}\/(latest|history)$/,
  /^\/prediction\/[A-Za-z0-9_-]{1,32}\/(latest|history)$/,
  /^\/evidence$/,
  /^\/health$/,
];

export function isAllowed(path) {
  return ALLOWED.some((pattern) => pattern.test(path));
}

// Resolves to one of:
//   { status: "ok", data }      a 2xx with a JSON body
//   { status: "unavailable" }   404: nothing has been published yet
//   { status: "error", reason } network failure, non-2xx, or a body that is not JSON
export async function get(path, fetcher = globalThis.fetch) {
  if (!isAllowed(path)) {
    throw new Error(`read-only dashboard: ${path} is not an allowed endpoint`);
  }
  let response;
  try {
    response = await fetcher(path, { method: "GET", headers: { accept: "application/json" } });
  } catch (error) {
    return { status: "error", reason: `server unreachable (${error.message})` };
  }
  if (response.status === 404) return { status: "unavailable" };
  if (!response.ok) return { status: "error", reason: `server answered ${response.status}` };
  try {
    return { status: "ok", data: await response.json() };
  } catch {
    return { status: "error", reason: "response was not JSON" };
  }
}
