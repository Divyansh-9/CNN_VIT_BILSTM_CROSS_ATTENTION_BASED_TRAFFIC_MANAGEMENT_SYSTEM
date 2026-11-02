// The dashboard's only way to reach the server. Read-only by construction:
// GET, and only the endpoints below. Nothing here can reach /observation or
// any signal-control path, and the tests pin that.

// The id part is the server's INTERSECTION_ID, length included (P142).
export const ALLOWED = [
  /^\/count_forecast\/[A-Za-z0-9_-]{1,32}\/(latest|history)$/,
  /^\/prediction\/[A-Za-z0-9_-]{1,32}\/(latest|history)$/,
  // FR-UI03: observed counts, one of the three windows and nothing else (D21).
  /^\/vehicle_count\/[A-Za-z0-9_-]{1,32}\/history\?window=(1h|6h|24h)$/,
  // D35: each lane's latest count by class, for the Engineering view.
  /^\/vehicle_count\/[A-Za-z0-9_-]{1,32}\/latest$/,
  // D22: the edge's latest heartbeat, for the source badge and the lane map.
  /^\/heartbeat\/[A-Za-z0-9_-]{1,32}\/latest$/,
  // D26: forecast checks, a minute apart (ADR-014 §2).
  /^\/forecast_check\/[A-Za-z0-9_-]{1,32}\/recent$/,
  // D34: the intersections the server has heard from.
  /^\/sites$/,
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
