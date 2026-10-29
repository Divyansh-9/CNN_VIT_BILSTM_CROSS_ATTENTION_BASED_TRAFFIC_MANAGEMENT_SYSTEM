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

// FR-UI03 (D21): observed counts per lane, bucketed by the server. Like every
// response, shown whole or not at all. A lane with no samples in a bucket is
// absent from it, so a gap is never read as zero.
export const COUNT_WINDOWS = { "1h": 60, "6h": 300, "24h": 900 };
const LANE = /^[A-Za-z0-9_-]{1,32}$/;

export function validateCountHistory(json, window) {
  if (!json || typeof json !== "object") return fail("not an object");
  if (json.window !== window) return fail(`not the ${window} window`);
  if (json.bucket_s !== COUNT_WINDOWS[window]) return fail("bucket size does not match the window");
  if (!Array.isArray(json.buckets)) return fail("no buckets");
  const lanes = new Set();
  for (const [i, bucket] of json.buckets.entries()) {
    if (!bucket || typeof bucket.t !== "number" || !Number.isFinite(bucket.t)
        || !bucket.lanes || typeof bucket.lanes !== "object" || Array.isArray(bucket.lanes))
      return fail(`bucket ${i + 1}: malformed`);
    for (const [lane, value] of Object.entries(bucket.lanes)) {
      if (!LANE.test(lane)) return fail(`bucket ${i + 1}: invalid lane name`);
      if (!value || typeof value.mean !== "number" || !Number.isFinite(value.mean)
          || value.mean < 0 || value.mean > MAX_LANE_COUNT)
        return fail(`bucket ${i + 1}: invalid mean for ${lane}`);
      if (!Number.isInteger(value.n) || value.n < 1) return fail(`bucket ${i + 1}: invalid sample count for ${lane}`);
      lanes.add(lane);
    }
  }
  return { ok: true, data: { ...json, lanes: [...lanes].sort() } };
}

// D22: the edge's heartbeat, which names its source and lane map. The same
// rules as contracts/mqtt.py, so nothing the server would refuse is shown. A
// heartbeat with no source is valid, and is shown as unknown, never as live.
const SESSION = /^[0-9a-f]{12}$/;
const seconds = (v) => typeof v === "number" && Number.isFinite(v) && v >= 0;

function sourceProblem(source) {
  const keys = ["duration_s", "kind", "label", "position_s", "session"];
  if (!source || typeof source !== "object" || Object.keys(source).sort().join() !== keys.join())
    return "source fields are not kind, session, label, position_s and duration_s";
  if (!["camera", "replay"].includes(source.kind)) return "unknown source kind";
  if (!SESSION.test(source.session)) return "invalid source session";
  if (typeof source.label !== "string" || !LANE.test(source.label)) return "invalid source label";
  if (source.kind === "camera")
    return source.position_s === null && source.duration_s === null ? null : "a camera has no clip position";
  if (!seconds(source.position_s)) return "invalid replay position";
  if (source.duration_s !== null && !(seconds(source.duration_s) && source.duration_s > 0
                                      && source.position_s <= source.duration_s))
    return "invalid replay duration";
  return null;
}

export function validateHeartbeat(json) {
  if (!json || typeof json !== "object") return fail("not an object");
  if (typeof json.age_s !== "number" || typeof json.stale !== "boolean") return fail("age or stale flag missing");
  if (json.source !== null) {
    const problem = sourceProblem(json.source);
    if (problem) return fail(problem);
  }
  if (json.lanes !== null) {
    const map = json.lanes;
    if (!map || typeof map !== "object" || Array.isArray(map)) return fail("invalid lane map");
    const entries = Object.entries(map);
    if (entries.length === 0 || entries.length > APPROACHES.length) return fail("invalid lane map");
    for (const [lane, approach] of entries)
      if (!LANE.test(lane) || !APPROACHES.includes(approach)) return fail("invalid lane map");
    if (new Set(Object.values(map)).size !== entries.length) return fail("two lanes map to one approach");
  }
  return { ok: true, data: json };
}
