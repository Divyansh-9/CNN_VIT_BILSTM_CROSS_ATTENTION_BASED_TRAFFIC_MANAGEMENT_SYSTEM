import { useState } from "react";
import { downloadText, toCsv } from "./ops.js";
import styles from "./OpsPages.module.css";
import chart from "./RecordingPages.module.css";

const clock = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const label = { green: "Green", yellow: "Yellow", "all-red": "All red" };
const intervals = row => [
  ["green", row.start, row.green_end],
  ["yellow", row.green_end, row.yellow_end],
  ["all-red", row.yellow_end, row.end],
];

function ScheduleRows({ rows, nextLocked = false }) {
  return <div className={chart.scroll}><table className={styles.table}>
    <thead><tr><th>Phase</th><th>Green / service</th><th>Yellow</th><th>All red</th><th>Simulated red wait</th><th>Reason</th></tr></thead>
    <tbody>{rows.map((row, index) => <tr key={row.start}>
      <th scope="row">{row.phase}{nextLocked && index === 0 ? " · committed" : ""}</th>
      {intervals(row).map(([state, start, end]) => <td key={state}>{clock(start)}–{clock(end)} ({end - start} s)</td>)}
      <td>{row.red_wait_s} s</td><td>{row.reason}</td>
    </tr>)}</tbody>
  </table></div>;
}

export function OfflineSignals({ schedule, result }) {
  const [cursor, select] = useState(0);
  const rows = schedule.phases;
  const length = rows.at(-1).end;
  const position = Math.min(cursor, length - 1);
  const active = rows.find(row => row.end > position);
  const [state] = intervals(active).find(([, , end]) => position < end);
  const save = () => {
    const columns = ["phase", "approaches", "start", "green_end", "yellow_end", "end", "green_s", "visible", "red_wait_s", "reason"];
    const csv = rows.map(row => ({ ...row, approaches: row.approaches.join(" / "),
      phase: /^[=+@\-]/.test(row.phase) ? "'" + row.phase : row.phase }));
    downloadText(`${result.clip}.signal-schedule.csv`, toCsv(columns, csv));
  };
  return <section className={styles.card} aria-label="Offline optimized schedule">
    <h3>Offline optimized schedule</h3>
    <p className={styles.muted}>Uses full recording windows. Times are relative to the recording.
      The final phase includes its complete clearance. Signal colors in the footage are unverified.
      {schedule.coverage_s < rows.at(-1).start && ` Planned phases after ${clock(schedule.coverage_s)} reuse the final observed demand window.`}</p>
    <label className={chart.timelineControl}>Inspect the schedule at {clock(position)}
      <input type="range" min="0" max={length - 1} value={position} onChange={e => select(Number(e.target.value))} />
    </label>
    <div className={chart.signalStrip} aria-hidden="true">{rows.flatMap(row => intervals(row).map(([color, start, end]) =>
      <span key={start} data-signal={color} style={{ flexGrow: end - start }} title={`${row.phase} · ${label[color]} · ${clock(start)}`} />))}</div>
    <p><strong>{active.phase}</strong> · {label[state]} · {active.visible} vehicles in view at the planning window</p>
    <ScheduleRows rows={rows} />
    <p className={styles.muted}>Maximum configured simulated red is {schedule.max_red_s} s.
      {result.traffic && ` Configured baseline green is ${result.traffic.policy.previous_green} s.`} Physical queue length,
      vehicle delay, existing signal durations and throughput improvement require additional measurements.</p>
    <button className={styles.button} type="button" onClick={save}>Download signal schedule CSV</button>
  </section>;
}

function positionAt(signal, elapsed) {
  let current = signal.phase;
  if (signal.next_locked && elapsed >= current.end) current = signal.upcoming[0];
  const [state, , end] = intervals(current).find(([, , until]) => elapsed < until) ?? ["all-red", 0, elapsed];
  const nextIsActive = current !== signal.phase;
  const upcoming = nextIsActive ? signal.upcoming.slice(1) : signal.upcoming;
  return { current, state, end, upcoming, nextLocked: signal.next_locked && !nextIsActive };
}

export function LiveSignalSchedule({ signal, elapsed, samples }) {
  const { upcoming, nextLocked } = positionAt(signal, elapsed);
  const history = samples.filter((row, i) => row.signal && (i === 0 || row.signal.as_of !== samples[i-1].signal?.as_of
    || row.signal.next_locked !== samples[i-1].signal?.next_locked)).slice(-6).reverse();
  return <section className={styles.card}>
    <h3>Rolling signal schedule</h3>
    <ScheduleRows rows={upcoming} nextLocked={nextLocked} />
    <details><summary>Recent predictions</summary><ul>{history.map(row =>
      <li key={row.t}>{clock(row.t)} · {row.signal.upcoming[0].phase} · {row.signal.upcoming[0].green_s} s</li>)}</ul></details>
  </section>;
}

export function LiveSignals({ signal, elapsed, samples, policy, compact = false }) {
  const { current, state, end, upcoming, nextLocked } = positionAt(signal, elapsed);
  const next = upcoming[0];
  const levels = ["Low", "Moderate", "High", "Severe"];
  return <section className={styles.card} aria-label="Live adaptive signal prediction">
    <h3>Live adaptive signal prediction</h3>
    <p className={styles.muted}>Simulated controller · Camera signal colors are unverified</p>
    <div className={compact ? chart.livePhaseStack : chart.signalGrid}>
      <div className={chart.signalTile} data-signal={state}><strong>Current · {label[state]}</strong>
        <b>{state === "all-red" ? "All approaches" : current.phase}</b><span>{Math.max(0, Math.ceil(end - elapsed))} s remaining</span></div>
      <div className={chart.signalTile}><strong>{nextLocked ? "Committed next phase" : "Recommended next phase"}</strong>
        <b>{next.phase}</b><span>Starts at {clock(next.start)} · in {Math.max(0, Math.ceil(next.start - elapsed))} s · {next.green_s} s service</span>
        <span>{next.reason}</span></div>
    </div>
    <p className={styles.muted}>Demand updated at {clock(signal.as_of)} on the feed clock.</p>
    <h4>Live lane demand</h4>
    <div className={compact ? chart.liveLaneGrid : chart.signalGrid}>{Object.entries(signal.measurements).map(([approach, row]) => {
      const color = current.approaches.includes(approach) && state !== "all-red" ? state : "all-red";
      return <div key={approach} className={chart.signalTile} data-signal={color}>
        <strong>{approach} · {color === "all-red" ? "Red" : label[color]}{next.approaches.includes(approach) ? " · Next" : ""}</strong>
        <span>{row.visible == null ? "Unobserved" :
          `${row.visible} in view · ${levels[policy.lane_demand.filter(n => row.visible >= n).length]} demand`}</span>
        {(!compact || row.inbound_per_min != null) && <span>{row.inbound_per_min == null ? "Inbound rate unavailable" : `${row.inbound_per_min} inbound/min`}</span>}
      </div>;
    })}</div>
    <p className={styles.muted}>Physical queues and vehicle wait times need calibrated measurements.</p>
    {!compact && <LiveSignalSchedule signal={signal} elapsed={elapsed} samples={samples} />}
  </section>;
}
