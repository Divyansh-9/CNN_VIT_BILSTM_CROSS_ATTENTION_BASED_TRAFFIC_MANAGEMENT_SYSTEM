import panel from "./Panels.module.css";
import styles from "./Agreement.module.css";
import { APPROACHES, CHECK_SLOTS, validateChecks } from "./validate.js";

// D26, ADR-014 §2: the deferred agreement ribbon. Each cell is one checked
// minute: an earlier forecast beside what the counts then showed. Agreement is
// shape (a filled square, or a cross), never a class colour; a minute with no
// valid check is a gap cell; there is no percentage anywhere, only k of n.

export const AGREEMENT_LABEL = "Rolling agreement with auto-labels over the last 20 checked minutes. Not a "
  + "benchmark: the observed values come from the same detector counts the forecasts are made from. "
  + "Benchmark figures are in Results.";
const LIMITS = "Not accuracy: both sides come from one detector's counts, not human-verified traffic. "
  + "These are the live persistence and ridge forecasts, not MFSTNet, for this camera and these minutes "
  + "only. No forecast drives a signal (P97a).";

const CELL = 14, GAP = 4;

function cellTitle(slot, a) {
  if (slot.kind === "gap") return "No valid check this minute: the edge's window broke";
  const c = slot.classes[a], n = slot.counts[a];
  const parts = [];
  if (c) parts.push(`class forecast ${c.forecast}, then ${c.observed}`);
  if (n) parts.push(`count forecast ${n.forecast.toFixed(1)}, then ${n.observed.toFixed(1)} (off by ${Math.abs(n.forecast - n.observed).toFixed(1)})`);
  return parts.length ? parts.join("; ") : "Not checkable for this approach";
}

function Cell({ slot, a, i }) {
  const x = i * (CELL + GAP);
  const c = slot.kind === "check" ? slot.classes[a] : null;
  const kind = slot.kind === "gap" ? "gap" : !c ? "none" : c.forecast === c.observed ? "agreed" : "differed";
  return (
    <g data-cell={kind}>
      <title>{cellTitle(slot, a)}</title>
      {kind === "agreed" && <rect className={styles.agreed} x={x} y={0} width={CELL} height={CELL} rx={2} />}
      {kind === "differed" && <path className={styles.differed} d={`M${x + 2},2 L${x + CELL - 2},${CELL - 2} M${x + CELL - 2},2 L${x + 2},${CELL - 2}`} />}
      {kind === "gap" && <rect className={styles.gap} x={x + 0.5} y={0.5} width={CELL - 1} height={CELL - 1} rx={2} />}
      {kind === "none" && <rect className={styles.none} x={x + 3} y={CELL / 2 - 1} width={CELL - 6} height={2} />}
    </g>
  );
}

function summaryText(s) {
  const cls = s.class.n ? `class agreed ${s.class.agreed} of ${s.class.n}` : "no class checked";
  const cnt = s.count.n ? `count off by ${s.count.mean_abs_diff.toFixed(2)} veh on average over ${s.count.n}`
    : "no count checked yet";
  return `${cls} · ${cnt}`;
}

export function Agreement({ state, edgeLive = false }) {
  const checked = state.status === "ok" ? validateChecks(state.data) : null;
  const data = checked?.ok ? checked.data : null;
  const rows = data ? APPROACHES.filter((a) => a in data.summary) : [];
  return (
    <section className={`${panel.panel} ${styles.panel}`} aria-label="Forecast check" data-agreement={data ? "shown" : state.status}>
      <header className={panel.head}>
        <h2>Forecast check</h2>
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
      {data?.stale && (
        <p className={panel.stale} data-state="stale">
          <span className={panel.staleMark} aria-hidden="true" />
          <span><b>No new check for {data.age_s.toFixed(0)} s.</b> These are the last checks received.</span>
        </p>
      )}
      {data && (
        <ul className={styles.rows}>
          {rows.map((a) => (
            <li key={a} data-check-row={a}>
              <b className={styles.approach}>{a}</b>
              <svg className={styles.ribbon} viewBox={`0 0 ${CHECK_SLOTS * (CELL + GAP)} ${CELL}`}
                   width={CHECK_SLOTS * (CELL + GAP)} height={CELL} role="img"
                   aria-label={`${a}: ${summaryText(data.summary[a])}`}>
                {data.slots.map((slot, i) => <Cell key={i} slot={slot} a={a} i={i} />)}
              </svg>
              <span className={styles.summary} data-summary={a}>{summaryText(data.summary[a])}</span>
            </li>
          ))}
        </ul>
      )}
      <p className={panel.note}>
        Each cell is one minute, oldest left: filled, the class forecast agreed; crossed, it did not; dashed
        outline, no valid check that minute; a dash, not checkable for that approach. {LIMITS}
      </p>
    </section>
  );
}
