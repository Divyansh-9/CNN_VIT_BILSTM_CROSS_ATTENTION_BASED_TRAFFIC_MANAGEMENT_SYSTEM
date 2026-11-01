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
  if ("directions_verified" in json && typeof json.directions_verified !== "boolean")
    return fail("directions_verified must be true or false");
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

// D26, ADR-014 §2: earlier forecasts beside what the counts then showed, a
// minute apart. Shown whole or not at all, and the summary is recomputed here
// from the slots: a server summary that disagrees with its own slots is
// refused, as missing_approaches is. Never a percentage.
export const CHECK_SLOTS = 20;
const PAIR = ["forecast", "observed"];

function pairsProblem(pairs, valueOk) {
  if (!pairs || typeof pairs !== "object" || Array.isArray(pairs)) return "malformed pairs";
  for (const [a, pair] of Object.entries(pairs)) {
    if (!APPROACHES.includes(a)) return "unknown approach";
    if (!pair || typeof pair !== "object" || Object.keys(pair).sort().join() !== PAIR.join()
        || !PAIR.every((k) => valueOk(pair[k]))) return `invalid pair for ${a}`;
  }
  return null;
}

export function agreement(slots) {
  const out = {};
  for (const a of APPROACHES) {
    const cls = slots.filter((s) => s.kind === "check" && a in s.classes).map((s) => s.classes[a]);
    const cnt = slots.filter((s) => s.kind === "check" && a in s.counts).map((s) => s.counts[a]);
    if (!cls.length && !cnt.length) continue;
    const mad = cnt.length ? cnt.reduce((t, p) => t + Math.abs(p.forecast - p.observed), 0) / cnt.length : null;
    out[a] = { class: { agreed: cls.filter((p) => p.forecast === p.observed).length, n: cls.length },
               count: { mean_abs_diff: mad === null ? null : Math.round(mad * 100) / 100, n: cnt.length } };
  }
  return out;
}

export function validateChecks(json) {
  if (!json || typeof json !== "object") return fail("not an object");
  if (!SESSION.test(json.session)) return fail("invalid session");
  if (typeof json.age_s !== "number" || typeof json.stale !== "boolean") return fail("age or stale flag missing");
  if (json.spacing_s !== 60) return fail("checks are not a minute apart");
  if (!Array.isArray(json.slots) || json.slots.length > CHECK_SLOTS) return fail("no slots, or too many");
  for (const [i, s] of json.slots.entries()) {
    if (s?.kind === "gap" && Object.keys(s).length === 1) continue;
    if (s?.kind !== "check" || !seconds(s.made_ts) || !seconds(s.checked_ts) || s.checked_ts <= s.made_ts)
      return fail(`slot ${i + 1}: malformed`);
    const problem = pairsProblem(s.classes, (v) => CLASSES.includes(v))
      ?? pairsProblem(s.counts, (v) => typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= MAX_LANE_COUNT);
    if (problem) return fail(`slot ${i + 1}: ${problem}`);
    if (!Object.keys(s.classes).length && !Object.keys(s.counts).length) return fail(`slot ${i + 1}: compares nothing`);
  }
  if (!sameSummary(agreement(json.slots), json.summary))
    return fail("summary disagrees with the checks it summarises");
  return { ok: true, data: json };
}

// Field by field, not by serialised text: key order is not a fact, and
// Python's round and Math.round can differ by 0.01 on a halfway value.
function sameSummary(mine, theirs) {
  if (!theirs || typeof theirs !== "object") return false;
  const keys = Object.keys(mine);
  if (keys.sort().join() !== Object.keys(theirs).sort().join()) return false;
  return keys.every((a) => {
    const [m, t] = [mine[a], theirs[a]];
    if (t?.class?.agreed !== m.class.agreed || t?.class?.n !== m.class.n || t?.count?.n !== m.count.n) return false;
    if (m.count.mean_abs_diff === null) return t.count.mean_abs_diff === null;
    return typeof t.count.mean_abs_diff === "number" && Math.abs(t.count.mean_abs_diff - m.count.mean_abs_diff) <= 0.011;
  });
}

// D34: GET /sites. A bad row refuses the whole list, as every response does.
export function validateSites(json) {
  if (!json || !Array.isArray(json.sites)) return fail("no sites");
  for (const s of json.sites) {
    if (typeof s?.id !== "string" || !LANE.test(s.id)) return fail("invalid site id");
    if (!seconds(s.age_s) || typeof s.stale !== "boolean") return fail("age or stale flag missing");
    if (s.kind !== null && !["camera", "replay"].includes(s.kind)) return fail("unknown source kind");
    if (s.label !== null && (typeof s.label !== "string" || !LANE.test(s.label))) return fail("invalid source label");
  }
  return { ok: true, data: json };
}

// D34: a results file from scripts/analyze_video.py, opened by hand, so it is
// checked like any response: shown whole or refused with the reason.
const unit = (v) => typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1;
const number = (v) => typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= MAX_LANE_COUNT;

function sampleProblem(s, laneNames, approaches) {
  if (!s || !seconds(s.t)) return "no time";
  const sameKeys = (o, keys) => o && typeof o === "object" && Object.keys(o).sort().join() === [...keys].sort().join();
  if (!sameKeys(s.counts, laneNames)) return "counts do not cover its lanes";
  if (!Object.values(s.counts).every((n) => Number.isInteger(n) && n >= 0 && n <= MAX_LANE_COUNT)) return "invalid count";
  if (!Array.isArray(s.boxes) || !s.boxes.every((b) => Array.isArray(b) && b.length === 4 && b.every(unit))) return "invalid box";
  if (s.level !== null && (!sameKeys(s.level, approaches) || !Object.values(s.level).every((c) => CLASSES.includes(c)))) return "invalid level";
  if (s.number !== null && (!sameKeys(s.number, approaches) || !Object.values(s.number).every(number))) return "invalid number";
  if (s.then !== null && (!sameKeys(s.then, approaches)
      || !Object.values(s.then).every((p) => CLASSES.includes(p?.level) && number(p?.number)))) return "invalid outcome";
  return null;
}

export function validateAnalysis(json) {
  if (!json || json.kind !== "stms-video-analysis") return fail("it is not an analysis results file");
  if (json.schema !== 1) return fail(`unknown schema ${String(json.schema)}`);
  if (json.step_s !== 2 || !seconds(json.duration_s) || json.duration_s <= 0) return fail("invalid timing");
  if (typeof json.clip !== "string" || typeof json.camera !== "string") return fail("no clip or camera");
  if (typeof json.directions_verified !== "boolean") return fail("directions_verified must be true or false");
  if (!Array.isArray(json.known_limits) || !json.known_limits.every((l) => typeof l === "string")) return fail("invalid known limits");
  if (!(number(json.limits?.low) && number(json.limits?.med) && json.limits.low < json.limits.med)) return fail("invalid level limits");
  if (!Array.isArray(json.lanes) || json.lanes.length === 0) return fail("no lanes");
  for (const lane of json.lanes) {
    if (!LANE.test(lane?.name ?? "") || !APPROACHES.includes(lane?.approach)
        || !Array.isArray(lane?.centre) || lane.centre.length !== 2 || !lane.centre.every(unit)) return fail("invalid lane");
  }
  const laneNames = json.lanes.map((l) => l.name), approaches = json.lanes.map((l) => l.approach);
  if (new Set(approaches).size !== approaches.length) return fail("two lanes map to one approach");
  if (!Array.isArray(json.samples) || json.samples.length === 0) return fail("no samples");
  for (const [i, s] of json.samples.entries()) {
    const problem = sampleProblem(s, laneNames, approaches);
    if (problem) return fail(`sample ${i + 1}: ${problem}`);
    if (i > 0 && s.t <= json.samples[i - 1].t) return fail(`sample ${i + 1}: out of order`);
  }
  return { ok: true, data: json };
}
