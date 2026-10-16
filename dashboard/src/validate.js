// Every live response is checked before it is shown. A response that fails is
// displayed as invalid, with the reason, and never partly shown. In particular,
// a count is never shown in the class panel or a class in the count panel
// (ADR-027), and a missing approach is never shown as zero or LOW.

export const APPROACHES = ["N", "S", "E", "W"];
export const CLASSES = ["LOW", "MEDIUM", "HIGH"];
export const COUNT_ROLE = "next_minute_count (ridge)";
const COUNT_MODEL = /^ridge@[0-9a-f]{12}$/;
const CLASS_MODEL = /^(?:[A-H]|persistence)@[0-9a-f]{12}$/;
const MAX_LANE_COUNT = 200;

const fail = (reason) => ({ ok: false, reason });

function common(json, roleOk, modelOk, values, valueOk) {
  if (!json || typeof json !== "object") return fail("not an object");
  if (typeof json.role !== "string" || !roleOk(json.role))
    return fail(`wrong role for this panel: ${String(json.role)}`);
  if (typeof json.model !== "string" || !modelOk.test(json.model))
    return fail(`unrecognised model id: ${String(json.model)}`);
  if (typeof json.age_s !== "number" || typeof json.stale !== "boolean")
    return fail("age or stale flag missing");
  if (!values || typeof values !== "object") return fail("no per-approach values");
  const keys = Object.keys(values);
  if (keys.length === 0) return fail("no approach forecast");
  for (const key of keys) {
    if (!APPROACHES.includes(key)) return fail(`unknown approach ${key}`);
    if (!valueOk(values[key])) return fail(`approach ${key}: invalid value ${String(values[key])}`);
  }
  const expected = APPROACHES.filter((a) => !keys.includes(a));
  const listed = Array.isArray(json.missing_approaches) ? [...json.missing_approaches].sort() : null;
  if (!listed || listed.join() !== [...expected].sort().join())
    return fail("missing_approaches disagrees with the values present");
  return { ok: true, data: json };
}

export function validateCount(json) {
  return common(json, (r) => r === COUNT_ROLE, COUNT_MODEL, json?.counts,
    (v) => typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= MAX_LANE_COUNT);
}

export function validateClass(json) {
  return common(json, (r) => r.startsWith("congestion_class"), CLASS_MODEL, json?.predictions,
    (v) => CLASSES.includes(v));
}
