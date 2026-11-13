import styles from "./Engineering.module.css";
import { validateClass, validateCount, validateLatestCounts } from "./validate.js";

// D35: the Operator view's measurements, for an engineer or evaluator. Every column
// says where its number came from. What the system does not measure says so: a
// missing value is never drawn as zero, and vehicles in view are never called a queue.

const LARGE_BOX = 0.25;   // Share of the frame worth a look by eye (the Newport audit, D35).
const MEAN_SAMPLES = 30;  // 60 s at 2 s, the system's own window.

export function ViewToggle({ view, onChange }) {
  return (
    <div className={styles.toggle} role="group" aria-label="View" data-view-toggle="true">
      <span className={styles.toggleLabel}>View</span>
      {[["operator", "Operator"], ["engineering", "Engineering"]].map(([key, label]) => (
        <button key={key} type="button" aria-pressed={view === key} data-view={key} onClick={() => onChange(key)}>{label}</button>
      ))}
    </div>
  );
}

const Source = ({ children }) => <span className={styles.source}>{children}</span>;
const Absent = ({ children }) => <span className={styles.absent}>{children}</span>;

// The working, not only the answer. Null when any class has no weight, because a
// total that left a vehicle out would understate the road space.
export function pcuWorking(types, weights) {
  const parts = Object.entries(types).filter(([, n]) => n > 0).sort(([a], [b]) => a.localeCompare(b));
  if (parts.some(([name]) => typeof weights[name] !== "number")) return null;
  const total = parts.reduce((sum, [name, n]) => sum + n * weights[name], 0);
  return { total, text: parts.map(([name, n]) => `${n} × ${weights[name].toFixed(2)}`).join(" + ") };
}

function ByClass({ types }) {
  const parts = Object.entries(types).filter(([, n]) => n > 0).sort(([a, x], [b, y]) => y - x || a.localeCompare(b));
  if (parts.length === 0) return <Absent>none counted</Absent>;
  return <span className={styles.classes}>{parts.map(([name, n]) => <span key={name}>{n} {name}</span>)}</span>;
}

function Pcu({ types, weights }) {
  const working = pcuWorking(types, weights);
  if (!working) return <Absent>Not available: a class has no PCU value</Absent>;
  return <span className={styles.pcu}><b>{working.total.toFixed(2)}</b>{working.text && <small>{working.text}</small>}</span>;
}

function PcuNote({ pcu, tail }) {
  return (
    <p className={styles.note} data-pcu-note="true">
      <b>Provisional.</b> PCU is the sum of class count × weight: {Object.entries(pcu.weights).sort(([a], [b]) => a.localeCompare(b)).map(([n, v]) => `${n} ${v.toFixed(2)}`).join(", ")}.
      {" "}Source: {pcu.source}.{pcu.assumed.length > 0 && ` Assumed, because the source has no entry: ${pcu.assumed.join(", ")}.`}
      {" "}These are Indian road values applied to whatever this camera sees. PCU weighs vehicles; it is not a measure of saturation. {tail}
    </p>
  );
}

const QUEUE_NOTE = "Queue is not measured: vehicles in view are not a queue, and the camera gives no stop line or speed. Queues exist only in the simulator.";

export function LiveEngineering({ state, cls, count, lanes }) {
  const head = (
    <div className={styles.head}><h2>Engineering view</h2><span>Live values, with where each one came from</span></div>
  );
  const shell = (body) => <section className={styles.card} aria-label="Engineering view" data-engineering="live">{head}{body}</section>;
  if (state.status === "loading") return shell(<Absent>Checking for counts.</Absent>);
  if (state.status === "unavailable") return shell(<Absent data-state="no-counts">Not available: no counts have been received yet.</Absent>);
  if (state.status !== "ok") return shell(<p className={styles.bad} data-state="unavailable">Unavailable: {state.reason}</p>);
  const checked = validateLatestCounts(state.data);
  if (!checked.ok) return shell(<p className={styles.bad} data-state="invalid">Not shown, this response failed its check: {checked.reason}.</p>);
  const { lanes: rows, pcu } = checked.data;
  const c = cls.status === "ok" ? validateClass(cls.data) : null;
  const k = count.status === "ok" ? validateCount(count.data) : null;
  const names = [...new Set([...Object.keys(lanes ?? {}), ...Object.keys(rows)])].sort();
  return shell(
    <>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Lane</th>
              <th scope="col">Counted <Source>Detector</Source></th>
              <th scope="col">By class <Source>Detector</Source></th>
              <th scope="col">PCU <Source>Calculated, provisional</Source></th>
              <th scope="col">Forecast, next 60 s <Source>Model</Source></th>
              <th scope="col">Queue</th>
              <th scope="col">Received</th>
            </tr>
          </thead>
          <tbody>
            {names.map((name) => {
              const row = rows[name], approach = lanes?.[name];
              const level = approach && c?.ok ? c.data.predictions[approach] : undefined;
              const number = approach && k?.ok ? k.data.counts[approach] : undefined;
              return (
                <tr key={name} data-engineering-row={name}>
                  <th scope="row"><span className={styles.mono}>{name}</span>{approach && <small> label {approach}</small>}</th>
                  <td className={styles.mono}>{row ? row.count : <Absent>Not available</Absent>}</td>
                  <td>{row ? <ByClass types={row.types} /> : <Absent>Not available</Absent>}</td>
                  <td>{row ? <Pcu types={row.types} weights={pcu.weights} /> : <Absent>Not available</Absent>}</td>
                  <td className={styles.mono}>
                    {level === undefined && number === undefined ? <Absent>Not available</Absent>
                      : <>{level ?? "no level"} · {number === undefined ? "no number" : number.toFixed(1)}{(c?.ok && c.data.stale) || (k?.ok && k.data.stale) ? <b className={styles.stale} data-forecast-stale="true"> out of date</b> : null}</>}
                  </td>
                  <td><Absent>Not measured</Absent></td>
                  <td data-received={name}>{!row ? <Absent>Not available</Absent>
                    : row.stale ? <b className={styles.stale}>Stale, {row.age_s.toFixed(0)} s ago</b>
                    : <span className={styles.mono}>{row.age_s.toFixed(0)} s ago</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={styles.note}>
        Counted is one 2-second sample and leaves out bicycles. The forecast includes them, so the two are not directly
        comparable. Detection confidence is not available here: the edge sends lane totals, not single detections.
      </p>
      <p className={styles.note} data-queue-note="true">{QUEUE_NOTE}</p>
      <PcuNote pcu={pcu} tail="Bicycles are not in these totals." />
    </>,
  );
}

function trailingMean(analysis, sample, lane) {
  const end = analysis.samples.indexOf(sample);
  const window = analysis.samples.slice(Math.max(0, end - MEAN_SAMPLES + 1), end + 1);
  return window.reduce((sum, s) => sum + s.counts[lane], 0) / window.length;
}

export function VideoEngineering({ analysis, sample, className }) {
  const head = <h3>Engineering view <small className={styles.small}>Sample {analysis.samples.indexOf(sample) + 1} of {analysis.samples.length}, at {sample.t.toFixed(0)} s in the recording</small></h3>;
  if (!sample.detections) {
    return (
      <section className={className} aria-label="Engineering view" data-engineering="video">
        {head}
        <p className={styles.absent} data-state="no-class-details">Not available: this results file was made before class details were recorded. Make it again with the current analysis tool.</p>
        <p className={styles.note}>{QUEUE_NOTE}</p>
      </section>
    );
  }
  const area = ([x1, y1, x2, y2]) => (x2 - x1) * (y2 - y1);
  const byLane = Object.fromEntries(analysis.lanes.map(({ name }) => [name, {}]));
  sample.detections.forEach(([cls, , lane]) => { if (lane) byLane[lane][cls] = (byLane[lane][cls] ?? 0) + 1; });
  const outside = sample.detections.filter(([, conf, lane]) => lane === null && conf >= analysis.min_confidence).length;
  const large = sample.boxes.filter((b) => area(b) >= LARGE_BOX).length;
  return (
    <section className={className} aria-label="Engineering view" data-engineering="video">
      {head}
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Lane</th>
              <th scope="col">Counted, this sample <Source>Detector</Source></th>
              <th scope="col">Mean per 2-second sample (up to 60 s) <Source>Calculated</Source></th>
              <th scope="col">By class <Source>Detector</Source></th>
              <th scope="col">PCU <Source>Calculated, provisional</Source></th>
              <th scope="col">Forecast, next 60 s <Source>Model</Source></th>
              <th scope="col">Queue</th>
            </tr>
          </thead>
          <tbody>
            {analysis.lanes.map(({ name, approach }) => (
              <tr key={name} data-engineering-row={name}>
                <th scope="row"><span className={styles.mono}>{name}</span><small> label {approach}</small></th>
                <td className={styles.mono}>{sample.counts[name]}</td>
                <td className={styles.mono}>{trailingMean(analysis, sample, name).toFixed(2)}</td>
                <td><ByClass types={byLane[name]} /></td>
                <td><Pcu types={byLane[name]} weights={analysis.pcu.weights} /></td>
                <td className={styles.mono}>{sample.level ? sample.level[approach] : "waiting"} · {sample.number ? sample.number[approach].toFixed(1) : "waiting"}</td>
                <td><Absent>Not measured</Absent></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className={styles.details} data-detections="true">
        <summary>Detections in this sample: {sample.detections.length}, {outside} outside every lane{large > 0 ? `, ${large} flagged as large` : ""}</summary>
        <p className={styles.note} data-review-note="true">
          A large-box flag asks for a look at the footage. It does not mean the detection is wrong. Confidence is the
          detector's own score, not a check that the class is right.
        </p>
        {sample.detections.length === 0 ? <p className={styles.absent}>The detector found nothing in this sample.</p> : (
          <div className={styles.scroll}>
            <table className={styles.table}>
              <thead><tr><th scope="col">#</th><th scope="col">Class</th><th scope="col">Confidence</th><th scope="col">Counted in</th><th scope="col">Share of frame</th></tr></thead>
              <tbody>
                {sample.detections.map(([cls, conf, lane], i) => {
                  const share = area(sample.boxes[i]);
                  return (
                    <tr key={i} data-detection={i}>
                      <td className={styles.mono}>{i + 1}</td>
                      <td>{cls}</td>
                      <td className={styles.mono}>{conf.toFixed(2)}</td>
                      <td>{lane ? <span className={styles.mono}>{lane}</span> : <Absent>{conf < analysis.min_confidence ? "no lane: below the confidence threshold" : "no lane: outside every lane"}</Absent>}</td>
                      <td className={styles.mono}>{(share * 100).toFixed(1)}%{share >= LARGE_BOX && <b className={styles.stale} data-large-box="true"> large: check by eye</b>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </details>
      <p className={styles.note}>
        These counts include bicycles and everything else the detector reports, because they are the forecasters' input.
        The live page's counts leave bicycles out. Confidence threshold: {analysis.min_confidence}.
      </p>
      <p className={styles.note} data-queue-note="true">{QUEUE_NOTE}</p>
      <PcuNote pcu={analysis.pcu} tail="A class with no PCU value shows as Not available." />
    </section>
  );
}
