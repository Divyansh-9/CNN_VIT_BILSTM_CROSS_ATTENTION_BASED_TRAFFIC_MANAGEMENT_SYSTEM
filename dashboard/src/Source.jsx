import panel from "./Panels.module.css";
import styles from "./Source.module.css";
import { Icon } from "./icons.jsx";
import { validateHeartbeat } from "./validate.js";

// D22: what the edge is counting from, as its heartbeat last said. Recorded
// footage is never presented as live: a replay says REPLAY and where in the
// clip it is, and anything short of a fresh, valid heartbeat that names its
// source reads as unknown or stale, never as a live camera.

export const clip = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" });

export function sourceStatus(state, { sample = false } = {}) {
  const at = state.status === "ok" ? state.data?.at : null;
  const date = Number.isFinite(at) ? new Date(at * 1000) : null;
  const updated = date && Number.isFinite(date.getTime()) ? date.toISOString() : null;
  if (sample) return { kind: "sample", title: "Sample", detail: "Bundled traffic data", updated };
  if (state.status === "loading") return { kind: "unknown", title: "Source unknown", detail: "checking" };
  if (state.status === "unavailable") return { kind: "unknown", title: "Source unknown", detail: "nothing reported yet" };
  if (state.status === "error") return { kind: "unknown", title: "Source unknown", detail: "server not reachable" };
  const checked = validateHeartbeat(state.data);
  if (!checked.ok) return { kind: "bad", title: "Source unknown", detail: `invalid heartbeat: ${checked.reason}` };
  const { stale, age_s: age, source } = checked.data;
  if (stale) return { kind: "stale", title: "Source out of date", detail: `last heard from ${age.toFixed(0)} s ago`, updated };
  if (source === null) return { kind: "unknown", title: "Source unknown", detail: "this edge unit does not report its source" };
  if (source.kind === "camera") return { kind: "camera", title: "Live camera", detail: source.label, updated };
  const length = source.duration_s === null ? "length unknown" : clip(source.duration_s);
  return { kind: "replay", title: "Replay", detail: `${source.label} · ${clip(source.position_s)} / ${length}`,
           position: clip(source.position_s), updated };
}

const SHAPE = { camera: "fresh", replay: "fresh", sample: "none", stale: "stale", bad: "bad", unknown: "none" };
const ICON = { camera: "live", replay: "history", sample: "film-strip" };

export function SourceBadge({ state, sample }) {
  const s = sourceStatus(state, { sample });
  return (
    <p className={styles.badge} data-source={s.kind} title="What the edge unit is counting from, as it last reported">
      <span className={`${panel.dot} ${panel[`k_${SHAPE[s.kind]}`]}`} aria-hidden="true" />
      {ICON[s.kind] && <Icon name={ICON[s.kind]} size={14} />}
      <b className={styles.title}>{s.title}</b>
      <span className={styles.detail}>{s.detail}</span>
      {s.updated && <time className={styles.detail} dateTime={s.updated}>{timeFormat.format(Date.parse(s.updated))}</time>}
    </p>
  );
}

// Shown only while a replay is current: the one case where the clock on this
// page and the footage being counted are at different times.
export function ReplayNote({ state }) {
  const s = sourceStatus(state);
  if (s.kind !== "replay") return null;
  return (
    <p className={styles.note} data-replay-note="true">
      Recorded footage, replayed. It is not a live camera. Clock times on this page are when the server received each
      message, not when the footage was recorded; the clip is at <span className={styles.mono}>{s.position}</span>.
    </p>
  );
}
