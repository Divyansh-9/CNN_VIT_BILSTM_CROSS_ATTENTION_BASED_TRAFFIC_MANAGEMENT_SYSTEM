import panel from "./Panels.module.css";
import styles from "./Agreement.module.css";
import { APPROACHES, CHECK_SLOTS, validateChecks } from "./validate.js";

// D26, ADR-014 §2: the deferred agreement ribbon. Each cell is one checked
// minute: an earlier forecast beside what the counts then showed. Since D33 a
// cell's colour and letter are the level the counts showed, so the row also
// shows the recent pattern. Agreement is still shape, a cut corner, never
// colour; a minute with no valid check is a gap cell; there is no percentage
// anywhere, only k of n.

export const AGREEMENT_LABEL = "Rolling agreement with auto-labels over the last 20 checked minutes. Not a "
  + "benchmark: the observed values come from the same detector counts the forecasts are made from. "
  + "Benchmark figures are in Results.";
const LIMITS = "Not accuracy: both sides come from one detector's counts, not human-verified traffic. "
  + "These are the live persistence and ridge forecasts, not MFSTNet, for this camera and these minutes "
  + "only. No forecast drives a signal (P97a).";

const CELL = 26, HEIGHT = 18, GAP = 3, CUT = 8;
// Below this the row is too short to carry both ends of the axis; the note still says oldest left.
const AXIS_MIN_SLOTS = 10;

function cellTitle(slot, a) {
  if (slot.kind === "gap") return "No valid check this minute: the edge's window broke";
  const c = slot.classes[a], n = slot.counts[a];
  const parts = [];
  if (c) parts.push(`level forecast ${c.forecast}, then ${c.observed}`);
  if (n) parts.push(`vehicle forecast ${n.forecast.toFixed(1)}, then ${n.observed.toFixed(1)} (off by ${Math.abs(n.forecast - n.observed).toFixed(1)})`);
  return parts.length ? parts.join("; ") : "Not checkable for this approach";
}

function Cell({ slot, a, i }) {
  const x = i * (CELL + GAP);
  const c = slot.kind === "check" ? slot.classes[a] : null;
  const kind = slot.kind === "gap" ? "gap" : !c ? "none" : c.forecast === c.observed ? "agreed" : "differed";
  return (
    <g data-cell={kind}>
      <title>{cellTitle(slot, a)}</title>
      {c && <rect className={styles[c.observed]} x={x} y={0} width={CELL} height={HEIGHT} rx={2} />}
      {c && <text className={styles.letter} x={x + CELL / 2} y={HEIGHT / 2 + 4} textAnchor="middle">{c.observed[0]}</text>}
      {kind === "differed" && <path className={styles.cut} data-cut="true" d={`M${x + CELL - CUT},0 H${x + CELL} V${CUT} Z`} />}
      {kind === "gap" && <rect className={styles.gap} x={x + 0.5} y={0.5} width={CELL - 1} height={HEIGHT - 1} rx={2} />}
      {kind === "none" && <rect className={styles.none} x={x + 8} y={HEIGHT / 2 - 1} width={CELL - 16} height={2} />}
    </g>
  );
}

function summaryText(s) {
  const cls = s.class.n ? `level matched ${s.class.agreed} of ${s.class.n}` : "no level checked";
  const cnt = s.count.n ? `vehicle number off by ${s.count.mean_abs_diff.toFixed(2)} on average over ${s.count.n}`
    : "no vehicle number checked yet";
  return `${cls} · ${cnt}`;
}

// D27: `runSession` is the session of a valid heartbeat, else null. The checks
// are called the previous run's only when both ids are known and differ; with
// no heartbeat, or none naming a source, nothing is claimed about whose they are.
export function Agreement({ state, edgeLive = false, runSession = null }) {
  const checked = state.status === "ok" ? validateChecks(state.data) : null;
  const data = checked?.ok ? checked.data : null;
  const rows = data ? APPROACHES.filter((a) => a in data.summary) : [];
  const previousRun = Boolean(data && runSession && data.session !== runSession);
  return (
    <section className={`${panel.panel} ${styles.panel}`} aria-label="Level over the last 20 minutes" data-agreement={data ? "shown" : state.status}>
      <header className={panel.head}>
        <h2>Level over the last 20 minutes</h2>
        <span className={panel.badge}>not a benchmark</span>
      </header>
      <p className={styles.label}>{AGREEMENT_LABEL}</p>
      {state.status === "loading" && <p className={panel.note} data-state="loading">Waiting for the server…</p>}
      {state.status === "unavailable" && (edgeLive
        ? <p className={panel.note} data-state="warming">Warming up: a forecast is checked 60 s after it is made,
            once the edge has 30 samples for the class and 60 for the count.</p>
        : <p className={panel.note} data-state="unreported">Not reported: no forecast check has reached the server.</p>)}
      {state.status === "error" && <p className={panel.problem} data-state="error">Unavailable: {state.reason}</p>}
      {checked && !checked.ok && <p className={panel.problem} data-state="invalid">Invalid response, not shown: {checked.reason}</p>}
      {(data?.stale || previousRun) && (
        <p className={panel.stale} data-state={data.stale ? "stale" : "previous-run"} data-previous-run={previousRun}>
          <span className={panel.staleMark} aria-hidden="true" />
          <span>
            <b>{data.stale ? `No new check for ${data.age_s.toFixed(0)} s.` : "Not this run's checks."}</b>
            {" "}These are the last checks received{previousRun ? ", from the previous run" : ""}.
          </span>
        </p>
      )}
      {data && data.slots.length === 0 && !data.stale && !previousRun && (
        <p className={panel.note} data-state="first-minute">
          The first check for this run has been received. Cells are anchored to minute boundaries, so the
          first cell will appear when the next minute begins.
        </p>
      )}
      {data && (
        <ul className={styles.rows}>
          {rows.map((a) => (
            <li key={a} data-check-row={a}>
              <b className={styles.approach}>{a}</b>
              <svg className={styles.ribbon} viewBox={`0 0 ${CHECK_SLOTS * (CELL + GAP) - GAP} ${HEIGHT}`} role="img"
                   aria-label={`${a}: ${summaryText(data.summary[a])}`}>
                {data.slots.map((slot, i) => <Cell key={i} slot={slot} a={a} i={i} />)}
              </svg>
              <span className={styles.summary} data-summary={a}>{summaryText(data.summary[a])}</span>
            </li>
          ))}
        </ul>
      )}
      {/* The span the row really covers. Its right end is the latest check, not
          now: a check exists only 60 s after its forecast, and may be stale. */}
      {data && rows.length > 0 && data.slots.length >= AXIS_MIN_SLOTS && (
        <div className={styles.axisRow}>
          <p className={styles.axis} data-axis="time" style={{ width: `${(data.slots.length / CHECK_SLOTS) * 100}%` }}>
            <span>{data.slots.length - 1} min earlier</span><i aria-hidden="true" /><span>Latest check</span>
          </p>
        </div>
      )}
      <p className={panel.note}>
        Each cell is one minute, oldest left. Colour and letter: the level the counts showed. A cut corner:
        the forecast said otherwise. Dashed outline: no valid check that minute. A dash: not checkable for that
        approach. {LIMITS}
      </p>
    </section>
  );
}
