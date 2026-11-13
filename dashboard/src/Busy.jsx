import panel from "./Panels.module.css";
import styles from "./Busy.module.css";
import { validateCountHistory } from "./validate.js";

// D34: when each lane is busy, from the last 24 hours of measured counts. An hour
// with no samples is a gap, never zero, and a shade is always backed by a value.

const HOURS = Array.from({ length: 24 }, (_, h) => h);
const hourName = (h) => `${String(h).padStart(2, "0")}:00`;

// Per lane, per clock hour of this browser, the mean weighted by its sample count.
export function busyByHour(buckets) {
  const sums = {};
  for (const b of buckets) {
    const hour = new Date(b.t * 1000).getHours();
    for (const [lane, { mean, n }] of Object.entries(b.lanes)) {
      const row = sums[lane] ?? (sums[lane] = HOURS.map(() => ({ total: 0, n: 0 })));
      row[hour].total += mean * n;
      row[hour].n += n;
    }
  }
  return Object.fromEntries(Object.entries(sums).map(([lane, row]) => [lane, row.map((c) => (c.n ? c.total / c.n : null))]));
}

const shade = (t) => `color-mix(in srgb, var(--ink) ${Math.round(6 + t * 86)}%, var(--panel))`;

export function BusyByHour({ state, lanes }) {
  const checked = state.status === "ok" ? validateCountHistory(state.data, "24h") : null;
  const table = checked?.ok ? busyByHour(checked.data.buckets) : {};
  const names = Object.keys(table).sort();
  const name = (lane) => (lanes?.[lane] ? `${lanes[lane]}` : lane);
  if (names.length === 0) {
    return (
      <section className={`${panel.panel} ${styles.panel}`} aria-label="When each lane is busy">
        <h3>When each lane is busy</h3>
        <p className={panel.note} data-busy-empty="true">Nothing has been counted in the last 24 hours. That is not the same as no traffic.</p>
      </section>
    );
  }
  const cells = names.flatMap((lane) => table[lane].map((value, hour) => ({ lane, hour, value })).filter((c) => c.value !== null));
  const busiest = cells.reduce((m, c) => (c.value > m.value ? c : m));
  const quietest = cells.reduce((m, c) => (c.value < m.value ? c : m));
  const top = Math.max(busiest.value, 1);
  const hoursWithCounts = new Set(cells.map((c) => c.hour)).size;
  return (
    <section className={`${panel.panel} ${styles.panel}`} aria-label="When each lane is busy">
      <h3>When each lane is busy</h3>
      <div className={styles.tiles}>
        <p data-busiest="true"><span>Busiest hour</span><b>{hourName(busiest.hour)}</b>{name(busiest.lane)}, about {busiest.value.toFixed(1)} vehicles in view</p>
        <p><span>Quietest hour</span><b>{hourName(quietest.hour)}</b>{name(quietest.lane)}, about {quietest.value.toFixed(1)} vehicles in view</p>
        <p><span>Hours with counts</span><b>{hoursWithCounts} of 24</b>An hour with none is a gap, not zero traffic</p>
      </div>
      <div className={styles.grid}>
        <span />
        {HOURS.map((h) => <span key={h} className={styles.hour}>{h % 3 ? "" : String(h).padStart(2, "0")}</span>)}
        {names.map((lane) => [
          <b key={lane} data-busy-lane={lane}>{name(lane)}</b>,
          ...table[lane].map((value, hour) => (
            <i key={`${lane}-${hour}`} data-hour={hour} data-value={value === null ? "none" : value.toFixed(2)}
               className={value === null ? styles.gap : undefined}
               style={value === null ? undefined : { background: shade(Math.min(value / top, 1)) }}
               title={value === null ? `${name(lane)}, ${hourName(hour)}: no counts` : `${name(lane)}, ${hourName(hour)}: about ${value.toFixed(1)} vehicles in view`} />
          )),
        ])}
      </div>
      <p className={panel.note}>Measured, not forecast, by this computer's clock. Lighter means more vehicles in view; hover for the value. Dashed: no counts that hour. Counts leave out bicycles and are kept for 48 hours.</p>
    </section>
  );
}
