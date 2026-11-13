import { useMemo, useRef, useState } from "react";
import { forecastCheck, laneSeries, perMinute } from "./check.js";
import styles from "./VideoCheck.module.css";

// D43: how this video's forecasts compared with what the next minute then showed,
// beside P105's question: does the ridge count forecast beat repeating the last
// minute? Every value is from the opened results file. Agreement, not accuracy.

const fmt = (t) => `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const veh = (v) => (v === null || v === undefined ? "–" : v.toFixed(2));
const W = 760, H = 228, PAD = { l: 40, r: 132, t: 24, b: 26 };

// Each series keeps its line style everywhere, so identity is never colour alone.
export const SERIES = [
  { key: "then", label: "What then happened", className: "then" },
  { key: "ridge", label: "Ridge forecast", className: "ridge" },
  { key: "repeat", label: "Repeat the last minute", className: "repeat" },
];

function path(points, x, y, key) {
  let d = "", open = false;
  for (const p of points) {
    if (p[key] === null) { open = false; continue; }
    d += `${open ? "L" : "M"}${x(p.t).toFixed(1)},${y(p[key]).toFixed(1)}`;
    open = true;
  }
  return d;
}

function Swatch({ className }) {
  return <svg width="26" height="8" aria-hidden="true"><line className={styles[className]} x1="1" y1="4" x2="25" y2="4" /></svg>;
}

function Chart({ analysis, lane, t, onSeek }) {
  const points = useMemo(() => perMinute(laneSeries(analysis, lane), undefined, analysis.step_s), [analysis, lane]);
  const [hover, setHover] = useState(null);
  const box = useRef(null);
  const end = analysis.duration_s;
  const top = Math.max(1, ...points.flatMap((p) => [p.then, p.ridge, p.repeat].filter((v) => v !== null)));
  const yMax = Math.ceil(top);
  const x = (v) => PAD.l + (v / end) * (W - PAD.l - PAD.r);
  const y = (v) => H - PAD.b - (v / yMax) * (H - PAD.t - PAD.b);
  const ticks = [0, yMax / 2, yMax];
  const xticks = [0, end / 4, end / 2, (3 * end) / 4, end];
  const last = (key) => [...points].reverse().find((p) => p[key] !== null);
  const at = (event) => {
    const r = box.current.getBoundingClientRect();
    const px = ((event.clientX - r.left) / r.width) * W;
    const time = Math.min(Math.max(((px - PAD.l) / (W - PAD.l - PAD.r)) * end, 0), end);
    return points.reduce((best, p) => (Math.abs(p.t - time) < Math.abs(best.t - time) ? p : best), points[0]);
  };
  // Direct labels at the right end, nudged apart so they never overlap.
  const ends = SERIES.map((s) => ({ ...s, p: last(s.key) })).filter((s) => s.p)
    .map((s) => ({ ...s, y: y(s.p[s.key]) })).sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i += 1) if (ends[i].y - ends[i - 1].y < 13) ends[i].y = ends[i - 1].y + 13;
  const overflow = ends.length ? ends[ends.length - 1].y - (H - PAD.b - 2) : 0;
  if (overflow > 0) ends.forEach((s) => { s.y -= overflow; });
  ends.forEach((s) => { s.y = Math.max(s.y, PAD.t + 8); });
  return (
    <div className={styles.chartWrap}>
      <svg ref={box} className={styles.chart} viewBox={`0 0 ${W} ${H}`} role="img" data-check-chart={lane}
           aria-label={`${lane}: what then happened, the ridge forecast and the last minute repeated, in vehicles in view, across the video`}
           onMouseMove={(e) => setHover(at(e))} onMouseLeave={() => setHover(null)} onClick={(e) => onSeek(at(e).from)}>
        {ticks.map((v) => (
          <g key={v}>
            <line className={styles.grid} x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} />
            <text className={styles.axis} x={PAD.l - 6} y={y(v) + 4} textAnchor="end">{Number.isInteger(v) ? v : v.toFixed(1)}</text>
          </g>
        ))}
        {xticks.map((v) => <text key={v} className={styles.axis} x={x(v)} y={H - 8} textAnchor="middle">{fmt(v)}</text>)}
        {SERIES.slice().reverse().map((s) => <path key={s.key} className={styles[s.className]} d={path(points, x, y, s.key)} data-series={s.key} />)}
        <line className={styles.now} x1={x(Math.min(t, end))} x2={x(Math.min(t, end))} y1={PAD.t} y2={H - PAD.b} />
        {ends.map((s) => <text key={s.key} className={styles.endLabel} x={W - PAD.r + 6} y={s.y + 4}>{s.label}</text>)}
        {hover && (
          <g>
            <line className={styles.cross} x1={x(hover.t)} x2={x(hover.t)} y1={PAD.t} y2={H - PAD.b} />
            {SERIES.filter((s) => hover[s.key] !== null).map((s) => (
              <circle key={s.key} className={styles.dot} cx={x(hover.t)} cy={y(hover[s.key])} r="4" />
            ))}
          </g>
        )}
        <text className={styles.axis} x={PAD.l} y={PAD.t - 2}>vehicles in view</text>
      </svg>
      {hover && (
        <div className={styles.tip} style={{ left: `${(x(hover.t) / W) * 100}%` }} data-check-tip="true">
          <b>{fmt(hover.from)}–{fmt(Math.min(hover.from + 60, end))}</b> · forecasts made in this minute, mean
          {SERIES.map((s) => <span key={s.key}><Swatch className={s.className} /> {s.label} <b>{veh(hover[s.key])}</b></span>)}
          <span className={styles.hint}>Click to jump the video here</span>
        </div>
      )}
    </div>
  );
}

export function VideoCheck({ analysis, t, onSeek }) {
  const result = useMemo(() => forecastCheck(analysis), [analysis]);
  const [lane, setLane] = useState(analysis.lanes[0].name);
  const shown = analysis.lanes.some((l) => l.name === lane) ? lane : analysis.lanes[0].name;
  const p = result.pooled;
  return (
    <section className={styles.card} aria-label="Forecast check for this video" data-video-check="true">
      <div className={styles.head}>
        <h3>Forecast check for this video</h3>
        <button type="button" className={styles.print} onClick={() => window.print()} data-print="true">Print or save as PDF</button>
      </div>
      <p className={styles.lead} data-check-verdict="true">
        {p.count
          ? <>Over {p.count.n.toLocaleString()} paired forecasts, the ridge count forecast was off by <b>{veh(p.count.ridge)}</b> vehicles on
            average, against <b>{veh(p.count.repeat)}</b> for repeating the last minute; it was closer in {p.count.ridgeCloser.toLocaleString()} of {p.count.n.toLocaleString()}.
            The class forecast agreed with what then happened in {p.level.agreed.toLocaleString()} of {p.level.n.toLocaleString()}.</>
          : "Too short to compare: the count forecast starts at 02:00 and needs the minute after it."}
      </p>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead>
            <tr><th scope="col">Lane</th><th scope="col">Class forecast agreed</th><th scope="col">Ridge forecast off by</th>
              <th scope="col">Repeat the last minute off by</th><th scope="col">Closer: ridge · repeat · tied</th></tr>
          </thead>
          <tbody>
            {result.rows.map((r, i) => (
              <tr key={r.lane} data-check-row={r.lane}>
                <th scope="row"><b>L{i}</b> label {r.approach}</th>
                <td>{r.level.n ? `${r.level.agreed} of ${r.level.n}` : "–"}</td>
                <td>{r.count ? `${veh(r.count.ridge)} veh` : "–"}</td>
                <td>{r.count ? `${veh(r.count.repeat)} veh` : "–"}</td>
                <td>{r.count ? `${r.count.ridgeCloser} · ${r.count.repeatCloser} · ${r.count.tied} of ${r.count.n}` : "–"}</td>
              </tr>
            ))}
            {p.count && (
              <tr className={styles.total} data-check-row="all">
                <th scope="row">All lanes</th>
                <td>{`${p.level.agreed} of ${p.level.n}`}</td>
                <td>{`${veh(p.count.ridge)} veh`}</td>
                <td>{`${veh(p.count.repeat)} veh`}</td>
                <td>{`${p.count.ridgeCloser} · ${p.count.repeatCloser} · ${p.count.tied} of ${p.count.n}`}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className={styles.chartHead}>
        <span className={styles.segment} role="radiogroup" aria-label="Lane shown in the chart">
          {analysis.lanes.map((l, i) => (
            <button key={l.name} type="button" role="radio" aria-checked={shown === l.name} onClick={() => setLane(l.name)}>L{i} {l.approach}</button>
          ))}
        </span>
        <span className={styles.legend} aria-label="Legend">
          {SERIES.map((s) => <span key={s.key}><Swatch className={s.className} />{s.label}</span>)}
        </span>
      </div>
      <Chart analysis={analysis} lane={shown} t={t} onSeek={onSeek} />
      <p className={styles.note}>
        Each point is the mean of one minute of forecasts, each made for the 60 s after it, beside the mean of what those 60 s then showed.
        The table uses every forecast. Both sides come from the same
        detector's counts, so this is agreement, not accuracy: human-verified quality (S67) has not been measured. A class depends on this camera's
        limits, LOW up to {analysis.limits.low.toFixed(2)} and MEDIUM up to {analysis.limits.med.toFixed(2)} vehicles. The ridge forecaster and repeating the
        last minute are the comparison P105 made across held-out cameras; one video is one example, not that result.
      </p>
    </section>
  );
}
