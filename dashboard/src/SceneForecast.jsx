import { useState } from "react";
import styles from "./OpsPages.module.css";

export const FORECAST_HORIZONS = [[30, "30 seconds"], [60, "60 seconds"], [300, "5 minutes"], [600, "10 minutes"]];

const time = seconds => [
  Math.floor(seconds / 60), String(Math.floor(seconds % 60)).padStart(2, "0"),
].join(":");

function ForecastTrend({ points }) {
  if (points.length < 2) return null;
  const start = points[0].t;
  const span = points.at(-1).t - start || 1;
  const max = Math.max(1, ...points.map(row => row.mean));
  const vertices = points.map(({ t, mean }) => ((t - start) * 240 / span) + "," + (46 - mean * 42 / max)).join(" ");
  return <svg viewBox="0 0 240 50" role="img" aria-label="Recent visible-vehicle forecasts"
    style={{ width: "100%", maxHeight: "6rem", color: "var(--sky)" }}>
    <path d="M0 47 H240" fill="none" stroke="var(--line)" />
    <polyline points={vertices} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
  </svg>;
}

export function SceneForecast({ result, sample, horizon: chosen, onHorizon }) {
  const [local, setLocal] = useState(60);
  const horizon = chosen ?? local;
  const now = sample ?? result?.samples.at(-1);
  const baseline = now?.scene_forecasts?.[horizon];
  const cutoffs = result?.traffic?.policy?.density;
  const density = baseline && cutoffs && ["Low", "Moderate", "High", "Severe"][cutoffs.filter(n => baseline.mean >= n).length];
  const points = baseline ? result.samples.filter(row => row.t <= now.t).slice(-90)
    .flatMap(row => row.scene_forecasts?.[horizon] ? [{ t: row.t, mean: row.scene_forecasts[horizon].mean }] : []) : [];
  return <section className={styles.card} aria-label="Traffic forecast">
    <h3>Visible traffic forecast</h3>
    <label>Forecast horizon{" "}
      <select value={horizon} onChange={e => (onHorizon ?? setLocal)(Number(e.target.value))}>
        {FORECAST_HORIZONS.map(([seconds, text]) => <option key={seconds} value={seconds}>{text}</option>)}
      </select>
    </label>
    {baseline ? <>
      <p><strong>{baseline.mean.toFixed(1)} vehicles in view on average</strong>
        {density && <> ? {density} estimated demand</>}</p>
      <p className={styles.muted}>Video clock {time(now.t)} to {time(now.t + horizon)}. Trailing-mean baseline.</p>
      <ForecastTrend points={points} />
      <p className={styles.muted}>{baseline.checks
        ? <>Recent error vs. detector observations ? {baseline.mae.toFixed(2)} vehicles MAE over {baseline.checks} separate windows.</>
        : "Waiting for the first comparable future observation to measure error."}</p>
      {baseline.range
        ? <p className={styles.muted}>Empirical range ? {baseline.range[0].toFixed(1)}?{baseline.range[1].toFixed(1)} vehicles, based on past errors.</p>
        : <p className={styles.muted}>An empirical range needs five completed check windows.</p>}
    </> : <p className={styles.muted}>{result && result.models?.scene !== "trailing-mean-v1"
      ? "Run a new analysis to add this forecast to an older report."
      : horizon >= 300
        ? "This horizon needs four consecutive observation windows, including three completed forecast checks."
        : "Waiting for a full observation window at this horizon."}</p>}
    <p className={styles.muted}>This forecast estimates visible traffic. Physical flow and queue forecasts need calibrated geometry and validated measurements.</p>
  </section>;
}
