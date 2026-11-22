// Readings for the operations pages (Overview extras, Signal timing, Alerts,
// System), each a pure function over the polls App already makes. Nothing here
// fetches, and nothing invents a value: a quantity the system does not report
// comes back null, and the page says "Not measured" or "Not reported".
import { APPROACHES, CLASSES, validateClass, validateCount, validateHeartbeat, validateLatestCounts } from "./validate.js";

const read = (state, validate) => (state?.status === "ok" ? validate(state.data) : null);

// ------------------------------------------------------------------ detector

// The detector's frame rate, as the edge reports it per lane (GET
// /vehicle_count/{id}/latest, `fps`). The deployed edge counts one frame every
// 2 s, so 0.5 is normal. Current lanes only; null when none is current.
export function detectorFps(latest) {
  const checked = read(latest, validateLatestCounts);
  if (!checked?.ok) return null;
  const rates = Object.values(checked.data.lanes).filter((l) => !l.stale && typeof l.fps === "number" && Number.isFinite(l.fps)).map((l) => l.fps);
  if (!rates.length) return null;
  return { fps: rates.reduce((a, b) => a + b, 0) / rates.length, lanes: rates.length, frameEvery: rates[0] > 0 ? 1 / rates[0] : null };
}

// Vehicles by class across the lanes that are current, from the edge's own
// breakdown. Classes are the wire names (car, motorcycle, auto-rickshaw, bus, truck).
export function classTotals(latest) {
  const checked = read(latest, validateLatestCounts);
  if (!checked?.ok) return null;
  const fresh = Object.values(checked.data.lanes).filter((l) => !l.stale);
  if (!fresh.length) return null;
  const totals = {};
  for (const lane of fresh) for (const [cls, n] of Object.entries(lane.types)) totals[cls] = (totals[cls] ?? 0) + n;
  const total = Object.values(totals).reduce((a, b) => a + b, 0);
  return { totals, total, lanes: fresh.length };
}

// ------------------------------------------------------------------ server and edge

// The safety limits the server enforces (server/safety.py), as GET /health
// returns them. Read defensively: a missing block is simply not shown.
const LIMIT_KEYS = ["min_green_s", "max_green_s", "all_red_s", "emergency_response_s", "mqtt_timeout_s"];
export function safetyLimits(health) {
  const limits = health?.status === "ok" ? health.data?.limits : null;
  if (!limits || typeof limits !== "object") return null;
  if (!LIMIT_KEYS.every((k) => typeof limits[k] === "number" && Number.isFinite(limits[k]) && limits[k] >= 0)) return null;
  return limits;
}

// What the edge last said about itself. `edge_status` and `mode` are passed
// through as strings when present; nothing is assumed about their values.
export function edgeState(heartbeat) {
  const checked = read(heartbeat, validateHeartbeat);
  if (!checked?.ok) return null;
  const d = checked.data;
  return { stale: d.stale, age: d.age_s, source: d.source, lanes: d.lanes,
           status: typeof d.edge_status === "string" ? d.edge_status : null,
           mode: typeof d.mode === "string" ? d.mode : null,
           directionsVerified: d.directions_verified === true };
}

// The model ids the forecasts name, so the page can say which frozen spec made them.
export function modelIds(cls, count) {
  const c = read(cls, validateClass), k = read(count, validateCount);
  return { level: c?.ok ? c.data.model : null, number: k?.ok ? k.data.model : null };
}

// ------------------------------------------------------------------ signal timing (advisory)

const PAIRS = [["N", "S"], ["E", "W"]];

// The advisory split: a share of expected vehicles per axis, from a current count
// forecast for all four approaches. The same arithmetic as Panels.timingSuggestion.
// It is an illustration of demand, never a timing plan, and reaches no signal (P97a).
export function advisorySplit(count) {
  const checked = read(count, validateCount);
  if (!checked?.ok || checked.data.stale) return null;
  const { counts } = checked.data;
  if (!APPROACHES.every((a) => a in counts)) return null;
  const demand = PAIRS.map((pair) => pair.reduce((t, a) => t + counts[a], 0));
  const total = demand[0] + demand[1];
  if (total <= 0) return null;
  return PAIRS.map((pair, i) => ({ axis: pair.join("–"), approaches: pair, demand: demand[i], share: demand[i] / total }));
}

// Why the split is what it is, in words, from the same numbers.
export function splitExplanation(split) {
  if (!split) return "No explanation: it needs a current vehicle forecast for all four approaches, with some traffic expected.";
  const [a, b] = split;
  const busier = a.share >= b.share ? a : b, quieter = busier === a ? b : a;
  if (Math.abs(a.share - b.share) < 0.05) return `Both axes expect about the same traffic (${a.approaches.join(" and ")} ${a.demand.toFixed(1)}, ${b.approaches.join(" and ")} ${b.demand.toFixed(1)} vehicles), so an even split.`;
  return `${busier.approaches.join(" and ")} expect ${busier.demand.toFixed(1)} vehicles against ${quieter.demand.toFixed(1)} on ${quieter.approaches.join(" and ")}, so ${busier.axis} would get the larger share, ${Math.round(busier.share * 100)}%.`;
}

// The fail-safe the edge implements (FR-A06): past the MQTT timeout without a
// heartbeat, the edge is on its own local Webster cycle. This page can only say
// what the rule is and how long the edge has been silent; it cannot observe the edge.
export function failSafe(heartbeat, limits) {
  const edge = edgeState(heartbeat);
  const timeout = limits?.mqtt_timeout_s ?? 10;
  if (!edge) return { kind: "unknown", text: "No heartbeat has been received, so the edge's state is unknown.", timeout };
  if (!edge.stale) return { kind: "normal", text: `The edge reported ${edge.age.toFixed(0)} s ago, inside the ${timeout} s link timeout.`, timeout };
  return { kind: "fallback", text: `The edge was last heard from ${edge.age.toFixed(0)} s ago, past the ${timeout} s link timeout. By FR-A06 it would now be running its own local fixed cycle (Webster), not anything from here.`, timeout };
}

// ------------------------------------------------------------------ alerts

// The conditions the page can see right now, each with a severity. Every one is
// read from a response the page already validates; none is a measurement the
// system does not make (queue length, emergency vehicles, signal errors).
export function currentAlerts({ health, cls, count, heartbeat, latestCounts }) {
  const out = [];
  if (health?.status === "error") out.push({ key: "server-down", severity: "critical", title: "Server unreachable", detail: health.reason });
  else if (health?.status === "ok" && health.data?.status !== "ok") out.push({ key: "server-problem", severity: "critical", title: "Server reports a problem", detail: "It answered, but did not report that it is working." });
  const edge = edgeState(heartbeat);
  if (edge?.stale) out.push({ key: "edge-silent", severity: "critical", title: "Camera unit silent", detail: `No heartbeat for ${edge.age.toFixed(0)} s. If this continues, the edge runs its local fallback (FR-A06).` });
  if (heartbeat?.status === "ok" && !edge) out.push({ key: "heartbeat-invalid", severity: "critical", title: "Heartbeat refused", detail: "The edge's last heartbeat failed validation." });
  for (const [name, state, validate] of [["level", cls, validateClass], ["vehicle", count, validateCount]]) {
    const checked = read(state, validate);
    if (checked && !checked.ok) out.push({ key: `${name}-invalid`, severity: "critical", title: `${name === "level" ? "Level" : "Vehicle"} forecast refused`, detail: checked.reason });
    else if (checked?.ok && checked.data.stale) out.push({ key: `${name}-stale`, severity: "warning", title: `${name === "level" ? "Level" : "Vehicle"} forecast out of date`, detail: `${checked.data.age_s.toFixed(0)} s old; it describes a minute that has passed.` });
  }
  const c = read(cls, validateClass);
  if (c?.ok && !c.data.stale) {
    const high = APPROACHES.filter((a) => c.data.predictions[a] === "HIGH");
    if (high.length) out.push({ key: "high", severity: high.length >= 3 ? "serious" : "warning", title: high.length >= 3 ? "Heavy congestion forecast" : "High congestion forecast",
      approaches: high, detail: `Approach${high.length > 1 ? "es" : ""} ${high.join(", ")} at HIGH for the next 60 s, on this camera's own scale.` });
    const missing = APPROACHES.filter((a) => !(a in c.data.predictions));
    if (missing.length) out.push({ key: "missing", severity: "warning", title: "Approach without a forecast",
      approaches: missing, detail: `No level for ${missing.join(", ")}. Shown as missing, never as LOW.` });
  }
  const countForecast = read(count, validateCount);
  if (countForecast?.ok && !countForecast.data.stale) {
    const missing = APPROACHES.filter((approach) => !(approach in countForecast.data.counts));
    if (missing.length) out.push({ key: "missing-counts", severity: "warning", title: "Approach without a count forecast",
      approaches: missing, detail: `No next-minute count for ${missing.join(", ")}.` });
  }
  const counts = read(latestCounts, validateLatestCounts);
  if (counts?.ok) {
    const stale = Object.entries(counts.data.lanes).filter(([, l]) => l.stale).map(([lane]) => lane);
    if (stale.length && stale.length === Object.keys(counts.data.lanes).length) out.push({ key: "counts-stale", severity: "warning", title: "Counting stopped", detail: `Every lane's last count is out of date.` });
  }
  return out;
}

// Events between two readings: a condition that appears is raised, one that
// disappears is cleared (a recovery). Times are this browser's clock, and say so.
export function alertEvents(previous, current, now) {
  const before = new Map(previous.map((a) => [a.key, a])), after = new Map(current.map((a) => [a.key, a]));
  const events = [];
  for (const a of current) if (!before.has(a.key)) events.push({ at: now, kind: "raised", ...a });
  for (const a of previous) if (!after.has(a.key)) events.push({ at: now, kind: "cleared", key: a.key, severity: "info", title: `Cleared: ${a.title}`, detail: "The condition is no longer present." });
  return events;
}

export const SEVERITY_ORDER = ["critical", "serious", "warning", "info"];
export const worstSeverity = (alerts) => alerts.reduce((w, a) => (SEVERITY_ORDER.indexOf(a.severity) < SEVERITY_ORDER.indexOf(w) ? a.severity : w), "info");

// ------------------------------------------------------------------ exports

// CSV with every field quoted, so a comma or quote in a value cannot break a row.
export function toCsv(columns, rows) {
  const cell = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [columns.map(cell).join(","), ...rows.map((r) => columns.map((c) => cell(r[c])).join(","))].join("\r\n");
}

export function downloadText(filename, text, type = "text/csv;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.rel = "noopener";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const CLASS_LABELS = { car: "Cars", motorcycle: "Two-wheelers", "auto-rickshaw": "Auto-rickshaws", bus: "Buses", truck: "Trucks" };
export const levelIndex = (level) => CLASSES.indexOf(level);
