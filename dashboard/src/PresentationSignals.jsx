import { useEffect, useState } from "react";
import styles from "./ExplorerTour.module.css";

const directions = ["N", "E", "S", "W"];
const names = { N: "North", E: "East", S: "South", W: "West" };
const exampleDemand = { N: 8, E: 4, S: 2, W: 1 };
const minGreen = 15, yellow = 4, allRed = 2, maxRed = 240;
const maxGreen = Math.min(60, Math.floor(maxRed / (2 * directions.length - 1)) - yellow - allRed);

// Four exclusive phases with the workbench's default timing policy. The example has
// no measured inbound rate, so the rate term from adaptive_signal.py contributes zero.
export function teachingSchedule(demand) {
  const lastEnd = Object.fromEntries(directions.map(a => [a, 0]));
  const rows = [];
  let start = 0;
  for (let round = 0; round < 2; round += 1) {
    const eligible = new Set(directions);
    while (eligible.size) {
      const ranked = [...eligible].map(phase => {
        const wait = start - lastEnd[phase];
        return { phase, wait, score: demand[phase] + wait / 20 };
      }).sort((a, b) => Number(b.wait >= maxRed / 2) - Number(a.wait >= maxRed / 2)
        || b.score - a.score || b.wait - a.wait);
      const { phase, wait } = ranked[0];
      const green = Math.min(maxGreen, minGreen + Math.ceil(2 * demand[phase]));
      const greenEnd = start + green;
      rows.push({ phase, start, green_s: green, green_end: greenEnd, yellow_end: greenEnd + yellow,
        end: greenEnd + yellow + allRed, visible: demand[phase], red_wait_s: wait,
        reason: `${demand[phase]} visible vehicles and ${wait} s spent red${wait >= maxRed / 2 ? ". Long-red priority applied." : "."}` });
      eligible.delete(phase);
      lastEnd[phase] = greenEnd;
      start = greenEnd + yellow + allRed;
    }
  }
  return rows;
}

export const clock = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

function SignalsRoad({ active, signal, demand }) {
  return <div className={styles.intersection} aria-label="Simulated four-approach intersection">
    {directions.map(phase => {
      const state = active === phase ? signal : "red";
      return <div className={styles.roadArm} key={phase} data-arm={phase}>
        <span className={styles.lamp} data-signal={state} />
        <strong>{names[phase]}</strong>
        <span>{state} · {demand[phase]} waiting</span>
      </div>;
    })}
  </div>;
}

export function SignalLab() {
  const [demand, setDemand] = useState(exampleDemand);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const rows = teachingSchedule(demand);
  const end = rows.at(-1).end - 1;
  useEffect(() => {
    if (!playing) return undefined;
    const timer = setInterval(() => setTime(value => (value + 1) % (end + 1)), 1000);
    return () => clearInterval(timer);
  }, [end, playing]);
  const index = rows.findIndex(row => row.end > time);
  const current = rows[index];
  const next = rows[index + 1];
  const state = time < current.green_end ? "green" : time < current.yellow_end ? "yellow" : "red";
  const remaining = (state === "green" ? current.green_end : state === "yellow" ? current.yellow_end : current.end) - time;
  return <section className={styles.visual} aria-label="Traffic signal simulation">
    <p className={styles.source}>Interactive simulation</p>
    <h3>Change demand at the intersection</h3>
    <p className={styles.muted}>Illustrative queues equal the demand you enter. Adjusting demand restarts the simulated plan.</p>
    <div className={styles.lab}>
      <SignalsRoad active={current.phase} signal={state} demand={demand} />
      <div className={styles.visualRows}>
        {directions.map(phase => <label key={phase} className={styles.rangeLabel}>
          <span>{names[phase]} demand <strong>{demand[phase]} vehicles</strong></span>
          <input type="range" min="0" max="18" value={demand[phase]} aria-label={`${names[phase]} demand`}
            onChange={event => { setDemand({ ...demand, [phase]: Number(event.target.value) }); setTime(0); setPlaying(false); }} />
        </label>)}
      </div>
    </div>
    <label className={styles.rangeLabel}><span>Simulation clock <strong>{clock(time)}</strong></span>
      <input type="range" min="0" max={end} value={time} onChange={event => setTime(Number(event.target.value))} />
    </label>
    <div className={styles.actions}>
      <button type="button" className={styles.secondary} onClick={() => setPlaying(value => !value)}>{playing ? "Pause" : "Play"}</button>
      <button type="button" className={styles.secondary} onClick={() => setTime(Math.min(end, time + remaining))}>Advance to next signal</button>
    </div>
    <dl className={styles.metrics}>
      <div><dt>Current state</dt><dd>{state === "red" ? "All red" : `${names[current.phase]} ${state}`} · {remaining} s left</dd></div>
      <div><dt>Next phase</dt><dd>{next ? `${names[next.phase]} at ${clock(next.start)} · ${next.green_s} s green` : "End of example"}</dd></div>
      <div><dt>Fixed plan comparison</dt><dd>30 s green per approach</dd></div>
    </dl>
    {next && <p className={styles.note}>{next.reason}</p>}
  </section>;
}

export function SignalTimeline({ rows, caption }) {
  const [index, setIndex] = useState(0);
  const row = rows[Math.min(index, rows.length - 1)];
  const start = rows[0].start;
  const duration = rows.at(-1).end - start;
  return <section className={styles.visual} aria-label="Signal timing timeline">
    <p className={styles.source}>{caption}</p>
    <h3>Signal timing timeline</h3>
    <div className={styles.timelineLegend} aria-label="Signal colors">
      <span data-signal="green">Green</span><span data-signal="yellow">Yellow</span><span data-signal="red">All red</span>
    </div>
    <div className={styles.timeline}>
      {rows.map((item, i) => <button type="button" key={item.start} aria-pressed={row === item}
        aria-label={`Inspect phase ${item.phase} at ${clock(item.start)}`} onClick={() => setIndex(i)}>
        <span>{item.phase}</span>
        <span className={styles.track} aria-hidden="true">
          <span style={{ flexBasis: `${100 * (item.start - start) / duration}%` }} />
          {[["green", item.start, item.green_end], ["yellow", item.green_end, item.yellow_end],
            ["red", item.yellow_end, item.end]].map(([type, from, to]) =>
            <span key={type} data-signal={type} style={{ flexBasis: `${100 * (to - from) / duration}%` }} />)}
        </span>
      </button>)}
    </div>
    <dl className={styles.metrics}>
      <div><dt>Green</dt><dd>{clock(row.start)} to {clock(row.green_end)} · {row.green_s} s</dd></div>
      <div><dt>Yellow / all red</dt><dd>{row.yellow_end - row.green_end} s / {row.end - row.yellow_end} s</dd></div>
      <div><dt>Demand</dt><dd>{row.visible} vehicles in view</dd></div>
    </dl>
    <p className={styles.note}>{row.reason}</p>
  </section>;
}

export const teachingTimeline = teachingSchedule(exampleDemand).slice(0, 6);
