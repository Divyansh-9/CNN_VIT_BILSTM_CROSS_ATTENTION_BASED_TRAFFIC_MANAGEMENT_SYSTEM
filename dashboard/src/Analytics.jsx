import styles from "./Analytics.module.css";
import { validateCountHistory } from "./validate.js";

// FR-UI03 (D21): what each lane's counting region held, as counted at the
// edge, over the last 1, 6 or 24 hours. A measurement, not a forecast, so its
// bars are solid. Lanes are named as the edge publishes them: which approach a
// lane feeds is known only at the edge.

export const WINDOWS = [["1h", "1 h"], ["6h", "6 h"], ["24h", "24 h"]];
const SPAN_LABEL = { "1h": ["−1 h", "−30 min"], "6h": ["−6 h", "−3 h"], "24h": ["−24 h", "−12 h"] };
// The drawing stretches to its box, so axis labels are HTML, not SVG text: SVG
// text would shrink with the drawing and was about 5 px tall at phone width.
const W = 600, H = 80, TOP = 2;

// One scale for every lane in the view, from zero, so lanes compare by height.
export function scaleTop(buckets) {
  let max = 0;
  for (const b of buckets) for (const v of Object.values(b.lanes)) max = Math.max(max, v.mean);
  return Math.max(1, Math.ceil(max));
}

const clock = (t) => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

function LaneChart({ lane, approach, buckets, top, window }) {
  const slot = W / buckets.length;
  const width = Math.max(slot * 0.7, 1);
  const last = buckets.length - 1;
  const latest = [...buckets].reverse().find((b) => lane in b.lanes);
  return (
    <figure className={styles.lane} data-lane={lane}>
      <figcaption className={styles.laneHead}>
        <span>
          <b className={styles.mono}>{lane}</b>
          {approach && <span className={styles.muted} data-lane-approach={approach}> · {approach} approach</span>}
        </span>
        <span className={styles.muted}>
          {latest ? `latest ${latest.lanes[lane].mean.toFixed(1)} veh at ${clock(latest.t)}` : "no samples in this window"}
        </span>
      </figcaption>
      <div className={styles.plot}>
        <div className={styles.yAxis} data-axis="y" aria-hidden="true"><span>{top}</span><span>0</span></div>
        <svg className={styles.chart} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
             aria-label={`${lane}: mean vehicles per bucket, ${buckets.filter((b) => lane in b.lanes).length} of ${buckets.length} buckets have samples`}>
          <line className={styles.grid} x1={0} y1={TOP} x2={W} y2={TOP} vectorEffect="non-scaling-stroke" />
          {buckets.map((b, i) => {
            if (!(lane in b.lanes)) return null;               // a gap stays a gap
            const v = b.lanes[lane];
            const y = H - (v.mean / top) * (H - TOP);
            return (
              <rect key={b.t} data-bucket={b.t} className={i === last ? styles.barNow : styles.bar}
                    x={i * slot + (slot - width) / 2} y={y} width={width} height={Math.max(H - y, 0.5)}>
                <title>{`${clock(b.t)}: mean ${v.mean.toFixed(2)} vehicles from ${v.n} samples`}</title>
              </rect>
            );
          })}
        </svg>
        <div className={styles.xAxis} data-axis="x" aria-hidden="true">
          <span>{SPAN_LABEL[window][0]}</span><span>{SPAN_LABEL[window][1]}</span><span>now</span>
        </div>
      </div>
    </figure>
  );
}

export function ObservedCounts({ state, window, onWindow, lanes = null }) {
  const checked = state.status === "ok" ? validateCountHistory(state.data, window) : null;
  return (
    <section className={styles.panel} aria-label="Observed vehicle counts" data-observed={window}>
      <header className={styles.head}>
        <h2>Observed vehicle counts</h2>
        <div className={styles.windows} role="group" aria-label="Window">
          {WINDOWS.map(([key, label]) => (
            <button key={key} type="button" aria-pressed={key === window} onClick={() => onWindow(key)}>{label}</button>
          ))}
        </div>
      </header>
      {state.status === "loading" && <p className={styles.muted} data-state="loading">Waiting for the server…</p>}
      {state.status === "unavailable" && <p className={styles.muted} data-state="unavailable">The server has no count history.</p>}
      {state.status === "error" && <p className={styles.problem} data-state="error">Unavailable: {state.reason}</p>}
      {checked && !checked.ok && <p className={styles.problem} data-state="invalid">Invalid response, not shown: {checked.reason}</p>}
      {checked?.ok && checked.data.lanes.length === 0 && (
        <p className={styles.muted} data-state="empty">Nothing was counted in this window.</p>
      )}
      {checked?.ok && checked.data.lanes.length > 0 && (
        <div className={styles.lanes}>
          {checked.data.lanes.map((lane) => (
            <LaneChart key={lane} lane={lane} approach={lanes?.[lane]} buckets={checked.data.buckets}
                       window={window} top={scaleTop(checked.data.buckets)} />
          ))}
        </div>
      )}
      <p className={styles.note}>
        Measured, not forecast: the mean number of vehicles in each lane's counting region per
        {" "}{checked?.ok ? checked.data.bucket_s / 60 : "one"}-minute bucket, as counted at the edge, on one scale
        from zero. An empty slot had no samples; it is a gap, not zero. Bicycles are not in these
        counts (D1).{" "}
        {lanes
          ? "Approaches come from the edge's current lane map; counts from an earlier run may have used another."
          : "Lanes are named as the edge publishes them; this edge has not reported which approach each feeds."}
      </p>
    </section>
  );
}
