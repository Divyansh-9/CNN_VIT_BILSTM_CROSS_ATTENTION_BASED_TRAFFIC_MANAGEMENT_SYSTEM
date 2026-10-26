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

function identity(json, roleOk, modelOk) {
  if (!json || typeof json !== "object") return fail("not an object");
  if (typeof json.role !== "string" || !roleOk(json.role))
    return fail(`wrong role for this panel: ${String(json.role)}`);
  if (typeof json.model !== "string" || !modelOk.test(json.model))
    return fail(`unrecognised model id: ${String(json.model)}`);
  return { ok: true };
}

function common(json, roleOk, modelOk, values, valueOk) {
  const who = identity(json, roleOk, modelOk);
  if (!who.ok) return who;
  if (typeof json.age_s !== "number" || typeof json.stale !== "boolean")
    return fail("age or stale flag missing");
  return approachValues(json, values, valueOk);
}

function approachValues(json, values, valueOk) {
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

const COUNT_RULES = [(r) => r === COUNT_ROLE, COUNT_MODEL, "counts",
  (v) => typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= MAX_LANE_COUNT];
const CLASS_RULES = [(r) => r.startsWith("congestion_class"), CLASS_MODEL, "predictions",
  (v) => CLASSES.includes(v)];

export function validateCount(json) {
  const [roleOk, modelOk, field, valueOk] = COUNT_RULES;
  return common(json, roleOk, modelOk, json?.[field], valueOk);
}

export function validateClass(json) {
  const [roleOk, modelOk, field, valueOk] = CLASS_RULES;
  return common(json, roleOk, modelOk, json?.[field], valueOk);
}

// A history is shown whole or not at all: one row that fails its panel's
// rules makes the response invalid, as a single forecast would be.
export function validateHistory(json, kind) {
  const [roleOk, modelOk, field, valueOk] = kind === "count" ? COUNT_RULES : CLASS_RULES;
  if (!json || !Array.isArray(json.rows)) return fail("no rows");
  for (const [i, row] of json.rows.entries()) {
    const who = identity(row, roleOk, modelOk);
    const checked = who.ok ? approachValues(row, row[field], valueOk) : who;
    if (!checked.ok) return fail(`row ${i + 1}: ${checked.reason}`);
    if (typeof row.at !== "number" || !Number.isFinite(row.at)) return fail(`row ${i + 1}: no time`);
  }
  return { ok: true, data: json };
}
