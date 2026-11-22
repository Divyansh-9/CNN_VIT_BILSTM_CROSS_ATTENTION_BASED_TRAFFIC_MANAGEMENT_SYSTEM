import { useEffect, useState } from "react";
import { get } from "./api.js";
import { wbGet } from "./workbench.js";
import { validateAnalysis } from "./validate.js";
import { LiveSignals } from "./AdaptiveSignals.jsx";
import { CountBenchmark } from "./CountBenchmark.jsx";
import { architecture, transport } from "./presentationContent.js";
import { clock, SignalLab, SignalTimeline, teachingTimeline } from "./PresentationSignals.jsx";
import { SITE } from "./site.js";
import example from "./explorer-example/bellevue.json";
import picture from "./explorer-example/bellevue.jpg";
import p105 from "../../experiments/results/bellevue_pilot/p105_results.json";
import selection from "../../experiments/results/loco_foreign/selection.json";
import trainingRun from "../../experiments/results/loco_foreign/fold3_seed13_G.csv?raw";
import ceiling from "../../experiments/results/ceiling/ceiling_stats.json";
import benchmark from "../../experiments/results/benchmark_ppo/benchmark_stats.csv?raw";
import styles from "./ExplorerTour.module.css";

const resolve = file => `${SITE.repository}/blob/main/${file}`;
const shown = number => Number.isFinite(number) ? new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(number) : "Unavailable";
const percent = value => `${value * 100}%`;
const basic = [
  ["Watch", "A camera or traffic video supplies pictures of a junction."],
  ["Understand", "STMS counts vehicles, estimates congestion, and looks one minute ahead."],
  ["Recommend", "The dashboard shows what it found and can propose the next green phase."],
];
const objectives = [
  ["Detect and count", "Recognize vehicles, keep track of them, and measure demand by approach."],
  ["Forecast demand", "Use recent counts to estimate next-minute traffic and look for congestion."],
  ["Recommend and evaluate", "Suggest a green phase and its duration. Test delay changes in simulation."],
];
const approaches = { N: "North", E: "East", S: "South", W: "West" };
const modes = [
  ["Analyze a Video", "Reads the complete recording", "Complete totals and an offline signal timeline", "Use it for an end-of-video report."],
  ["Live Monitoring", "Uses observations up to the current feed time", "Rolling counts and next-phase recommendations", "Use it to see what changed while traffic was moving."],
];
const colors = { Ridge: "primary", Observed: "secondary", Persistence: "reference" };

function Diagram({ title, steps }) {
  const [index, setIndex] = useState(0);
  const [label, text] = steps[index];
  return <section className={styles.visual} aria-label={title}>
    <h3>{title}</h3>
    <ol className={styles.steps}>
      {steps.map(([name], i) => <li key={name}>
        <button type="button" aria-pressed={i === index} onClick={() => setIndex(i)}>{name}</button>
      </li>)}
    </ol>
    <div className={styles.detail} aria-live="polite"><strong>{label}</strong><p>{text}</p></div>
  </section>;
}

function Grid({ title, items }) {
  return <section className={styles.visual}><h3>{title}</h3>
    <div className={styles.cardGrid}>
      {items.map(([label, ...text]) => <article key={label}><h4>{label}</h4>
        {text.map(line => <p key={line}>{line}</p>)}
      </article>)}
    </div>
  </section>;
}

function Bars({ title, rows, max = Math.max(1, ...rows.map(row => row[1])), suffix = "" }) {
  return <div className={styles.bars} role="group" aria-label={title}>
    {rows.map(([label, value, tone]) => <div key={label} className={styles.barRow}>
      <span>{label}</span>
      <span className={styles.barTrack} aria-hidden="true">
        <span data-tone={tone ?? "primary"} style={{ width: percent(Math.min(1, value / max)) }} />
      </span>
      <strong>{typeof value === "number" ? `${shown(value)}${suffix}` : "Unavailable"}</strong>
    </div>)}
  </div>;
}

function Detection({ laneView = false }) {
  const [kind, setKind] = useState("");
  const [minimum, setMinimum] = useState(0);
  const [active, setActive] = useState(-1);
  const classes = [...new Set(example.boxes.map(box => box.label))];
  const boxes = example.boxes.filter(box => (!kind || box.label === kind) && box.confidence >= minimum);
  const selected = boxes[active];
  return <section className={styles.visual} aria-label="Saved Bellevue detection frame">
    <p className={styles.source}>Recorded evidence · {example.site} · {example.timestamp}</p>
    <h3>{laneView ? "Vehicles in view by approach" : "Inspect actual vehicle detections"}</h3>
    {!laneView && <div className={styles.actions}>
      <label>Vehicle type <select value={kind} onChange={e => { setKind(e.target.value); setActive(-1); }}>
        <option value="">All types</option>{classes.map(name => <option key={name} value={name}>{name}</option>)}
      </select></label>
      <label>Minimum confidence <select value={minimum} onChange={e => { setMinimum(Number(e.target.value)); setActive(-1); }}>
        <option value={0}>All saved boxes</option><option value={0.5}>50%</option><option value={0.7}>70%</option>
      </select></label>
    </div>}
    <div className={styles.frame}>
      <img src={picture} alt="A recorded traffic frame from the Bellevue intersection" />
      {boxes.map(({ label, confidence, bounds: [x1, y1, x2, y2] }, i) => {
        const props = { style: { left: percent(x1), top: percent(y1), width: percent(x2 - x1), height: percent(y2 - y1) },
          className: styles.detection };
        return laneView ? <span {...props} aria-hidden="true" key={i} />
          : <button {...props} key={i} type="button" aria-label={`Detection ${i + 1}: ${label}, ${Math.round(confidence * 100)} percent confidence`}
            aria-pressed={active === i} onClick={() => setActive(i)} />;
      })}
      {laneView && example.lanes.map(({ name, centre: [x, y], approach, count }) =>
        <span className={styles.laneMarker} key={name} style={{ left: percent(x), top: percent(y) }}>{approach} · {count}</span>)}
    </div>
    {laneView ? <Bars title="Measured occupancy by approach" rows={example.lanes.map(lane => [approaches[lane.approach], lane.count])} />
      : <p className={styles.note} aria-live="polite">{selected
        ? `${selected.label} · ${Math.round(selected.confidence * 100)}% confidence · ${selected.lane ?? "unassigned"}`
        : `${boxes.length} saved detections shown. Select a box to inspect it. Checkpoint: ${example.detector}.`}</p>}
  </section>;
}

function Tracking() {
  const [position, setPosition] = useState(0);
  return <section className={styles.visual}>
    <p className={styles.source}>Illustrative track</p>
    <h3>One track, one qualifying crossing</h3>
    <div className={styles.crossing} aria-hidden="true">
      <span className={styles.countLine} /><span className={styles.trackedCar} style={{ left: percent(0.15 + position * 0.22) }}>ID 27</span>
    </div>
    <label className={styles.rangeLabel}><span>Move the vehicle through the frames</span>
      <input type="range" min="0" max="3" value={position} onChange={e => setPosition(Number(e.target.value))} />
    </label>
    <p className={styles.note}>Frame {position + 1} · Inbound count {position < 2 ? 0 : 1} · Track ID 27</p>
  </section>;
}

function Forecast() {
  const [selected, setSelected] = useState("N");
  const lane = example.lanes.find(row => row.approach === selected);
  return <section className={styles.visual}>
    <p className={styles.source}>Saved Bellevue forecast · {example.forecastWindow}</p>
    <h3>Forecast compared with observation</h3>
    <label className={styles.selectLabel}>Approach <select value={selected} onChange={event => setSelected(event.target.value)}>
      {Object.entries(approaches).map(([direction, name]) => <option value={direction} key={direction}>{name}</option>)}
    </select></label>
    <Bars title="Average vehicles visible in the following minute" suffix=" vehicles" max={3}
      rows={[["Ridge", lane.forecast], ["Observed", lane.observed], ["Persistence", lane.baseline]]
        .map(([label, value]) => [label, value, colors[label]])} />
    <p className={styles.note}>Each bar describes average vehicles in view during the same minute. Observed values are detector measurements.</p>
  </section>;
}

function Evaluation({ training = false }) {
  const csv = trainingRun.trim().split(/\r?\n/);
  const epochs = Number(csv[1].split(",")[csv[0].split(",").indexOf("epochs_run")]);
  const rows = benchmark.trim().split(/\r?\n/).map(line => line.split(","));
  const historical = rows.find(row => row[0] === "no-forecast_saturated_seed42" && row[1] === "webster");
  const noForecast = ceiling.arms["no-forecast"];
  const tuned = ceiling.arms.webster_s660_lost4;
  return <section className={styles.visual} aria-label={training ? "MFSTNet validation evidence" : "Verified experimental evidence"}>
    <p className={styles.source}>Saved experiment results</p>
    <h3>{training ? "Validation macro-F1" : "Forecasting and control results"}</h3>
    {training ? <>
      <Bars title="Mean validation macro-F1, 20 runs per configuration" max={1}
        rows={[["Full model G", selection.config_means.G], ["Linear probe H", selection.config_means.H, "secondary"]]} />
      <p className={styles.note}>40 runs across two configurations. The selected G checkpoint ran {epochs} epochs.
        The mean validation gap alone cannot establish an advantage on unseen cameras.</p>
      <a href={resolve("experiments/results/loco_foreign/selection.json")}>Validation selection record</a>
    </> : <>
      <h4>Held-out next-minute count error · {p105.windows} windows</h4>
      <Bars title="Pooled mean absolute error in vehicles" suffix=" vehicles"
        rows={[["Ridge", p105.pooled.ridge.mae], ["Persistence", p105.pooled.persistence.mae, "secondary"]]} />
      <h4>Forecast-control ceiling study · mean wait</h4>
      <Bars title="Mean wait in the ceiling study" suffix=" s"
        rows={[["No-forecast PPO", noForecast.mean_wait_s], ["Tuned Webster", tuned.mean_wait_s, "secondary"]]} />
      <p className={styles.note}>{ceiling.decision.reading}. The primary outcome was mean total delay. This chart shows the separate mean-wait measurement.</p>
      <details><summary>Earlier saturated benchmark and qualifications</summary>
        <p>No-forecast PPO averaged {historical[3]} s and Webster averaged {historical[6]} s across {historical[2]} paired seeds.
          This historical result used a different simulation setup, including a training-to-evaluation difference in the sublane model.</p>
        <a href={resolve("experiments/results/benchmark_ppo/benchmark_stats.csv")}>Benchmark CSV</a>
      </details>
      <a href={resolve("experiments/results/ceiling/ceiling_stats.json")}>Ceiling study data</a>
      <details><summary>Vehicle count review and CPU timing</summary><CountBenchmark /></details>
    </>}
  </section>;
}

function SavedAnalysis({ view, fetcher }) {
  const [jobs, setJobs] = useState(null);
  const [id, setId] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [unavailable, setUnavailable] = useState(false);
  const selected = jobs?.find(job => job.id === id);
  useEffect(() => {
    let active = true;
    wbGet("/workbench/jobs", fetcher).then(reply => {
      if (!active) return;
      const entries = Array.isArray(reply.data) ? reply.data.filter(job => job.status === "Completed" &&
        /^[0-9a-f]{64}$/.test(job.result_key ?? "") && (view === "live" ? ["camera", "demo"].includes(job.mode) : job.mode === "offline"))
        : [];
      setJobs(entries);
      setUnavailable(reply.status !== "ok");
      const preferred = view === "timeline" ? entries.find(job => job.metrics?.next_phase) ?? entries[0] : entries[0];
      setId(preferred?.id ?? "");
    });
    return () => { active = false; };
  }, [fetcher, view]);
  useEffect(() => {
    if (!selected) return undefined;
    let active = true;
    get(`/workbench/analysis/${selected.result_key}`, fetcher).then(reply => {
      if (!active) return;
      const checked = reply.status === "ok" && validateAnalysis(reply.data);
      setAnalysis({ id: selected.id, result: checked?.ok ? checked.data : null });
    });
    return () => { active = false; };
  }, [selected, fetcher]);

  const loaded = analysis?.id === id;
  const result = loaded ? analysis.result : null;
  const traffic = result?.traffic;
  const phases = traffic?.signal_schedule?.phases ?? [];
  const samples = view === "live" && traffic ? result.samples.filter(sample => sample.signal) : [];
  const [sampleIndex, setSampleIndex] = useState(0);
  const sample = samples[Math.min(sampleIndex, samples.length - 1)];
  const reportTitle = {
    timeline: "Choose a saved signal schedule", live: "Read a recorded monitoring session",
    offline: "Open a completed analysis", reports: "Inspect a saved report",
  }[view];
  return <>
    <section className={styles.visual} aria-label={reportTitle}>
      <h3>{reportTitle}</h3>
      {!jobs && <p role="status">Checking for saved analyses…</p>}
      {jobs?.length === 0 && <p className={styles.note}>{unavailable
        ? "Sign in to an STMS server with AI analysis enabled to open saved reports."
        : view === "live" ? "No completed Live session is available to replay here." : "No completed offline analysis is available yet."}</p>}
      {jobs?.length > 0 && <label className={styles.selectLabel}>Saved recording
        <select value={id} onChange={e => { setId(e.target.value); setSampleIndex(0); }}>
          {jobs.map(job => <option key={job.id} value={job.id}>{job.filename} · {job.id.slice(0, 8)}</option>)}
        </select>
      </label>}
      {id && (!loaded ? <p role="status">Opening saved analysis…</p>
        : !result && <p role="status">This report is missing or could not be verified.</p>)}
      {result?.processing && <dl className={styles.metrics}>
        <div><dt>Checkpoint</dt><dd>{result.processing.model}</dd></div>
        <div><dt>Frames processed</dt><dd>{shown(result.processing.frames)}</dd></div>
        <div><dt>Processing rate</dt><dd>{shown(result.processing.fps)} FPS</dd></div>
        {traffic && <>
          <div><dt>{traffic.scope === "frame" ? "Confirmed tracks" : "Inbound crossings"}</dt><dd>{traffic.crossings.length}</dd></div>
          <div><dt>Last measured density</dt><dd>{traffic.windows.at(-1)?.level ?? "Unavailable"}</dd></div>
          <div><dt>Alerts</dt><dd>{traffic.alerts.length}</dd></div>
        </>}
      </dl>}
      {view === "live" && result && !sample && <p className={styles.note}>This session has no stored adaptive phase updates.</p>}
      {view === "timeline" && result && !phases.length && <p className={styles.note}>This recording has no saved approach schedule.</p>}
      {["offline", "reports"].includes(view) && traffic && <>
        <Bars title="Vehicles counted by type" rows={Object.entries(traffic.by_type)} />
        {view === "reports" && <Bars title="Counted vehicles in the first six measured windows"
          rows={traffic.windows.slice(0, 6).map(row => [`${clock(row.t)}–${clock(row.end)}`, row.crossings, "secondary"])} />}
        <details><summary>Traffic windows and alerts</summary>
          <ul>{traffic.windows.slice(0, 6).map(row => <li key={row.t}>{clock(row.t)}–{clock(row.end)} · {row.level} · {row.crossings} counted</li>)}</ul>
          {traffic.alerts.length ? <ul>{traffic.alerts.slice(0, 5).map(alert => <li key={alert.id}>{clock(alert.t)} · {alert.type}. {alert.reason}</li>)}</ul>
            : <p>No alerts were generated in this recording.</p>}
        </details>
      </>}
      <a href={view === "live" ? "#live" : view === "offline" ? "#analyze" : "#results"}>
        {view === "live" ? "Open Live Monitoring" : view === "offline" ? "Open Analyze a Video" : "Open dashboard Results"}
      </a>
    </section>
    {(view === "timeline" || (view === "offline" && phases.length > 0)) &&
      <SignalTimeline key={id} rows={phases.length ? phases.slice(0, 6) : teachingTimeline}
      caption={phases.length ? "First six phases of the saved advisory schedule" : "Illustrative schedule · saved timing unavailable"} />}
    {view === "live" && (sample ? <section className={styles.visual}>
      <label className={styles.rangeLabel}><span>Inspect a saved phase update at {clock(sample.t)}</span>
        <input type="range" min="0" max={samples.length - 1} value={sampleIndex} onChange={event => setSampleIndex(Number(event.target.value))} />
      </label>
      <LiveSignals signal={sample.signal} elapsed={sample.t} policy={traffic.policy} samples={samples} compact />
    </section> : <Detection laneView />)}
  </>;
}

export function PresentationVisual({ kind, fetcher }) {
  switch (kind) {
    case "foundation": return <Diagram title="The project in three parts" steps={basic} />;
    case "demand": return <section className={styles.visual}><p className={styles.source}>Illustrative demand</p><h3>Two approaches, unequal demand</h3>
      <Bars title="Illustrative vehicles waiting" rows={[["Quiet road", 2, "secondary"], ["Busy road", 10]]} suffix=" vehicles" /></section>;
    case "objectives": return <Diagram title="How the objectives connect" steps={objectives} />;
    case "comparison": return <Grid title="Conventional timing and the STMS workbench" items={[
      ["Fixed-time signal", "Follows a schedule configured in advance.", "Demand, forecasts, and analytics require separate sensors or systems."],
      ["STMS advisory workflow", "Measures vehicles with a camera and estimates upcoming congestion.", "Shows adaptive timing suggestions, monitoring, and reports. Timing is simulated."],
    ]} />;
    case "architecture": return <Diagram title="Select a stage of the system" steps={architecture} />;
    case "stack": return <Grid title="What runs each part" items={[
      ["Interface", "React · JavaScript · Vite", "Native SVG and CSS charts"],
      ["Video and AI", "Python · OpenCV · YOLO · ByteTrack · PyTorch"],
      ["Transport and storage", "FastAPI · SQLite · MQTT · Mosquitto"],
      ["Research", "Ridge and persistence forecasting · MFSTNet · SUMO"],
    ]} />;
    case "transport": return <Diagram title="Follow the request and the data" steps={transport} />;
    case "input": return <Grid title="Three ways into STMS" items={[
      ["Upload for analysis", "Process the complete video and keep the finished report."],
      ["Demo Live", "Stream measurements from a recording against its playback clock."],
      ["Real Live", "Read a connected camera or server. Timing depends on available frames and processing resources."],
    ]} />;
    case "detection": return <Detection />;
    case "tracking": return <Tracking />;
    case "lanes": return <Detection laneView />;
    case "forecast": return <Forecast />;
    case "training": return <Evaluation training />;
    case "simulation": return <SignalLab />;
    case "formula": return <section className={styles.visual}>
      <h3>How a phase is ranked and timed</h3>
      <dl className={styles.formula}>
        <div><dt>Priority score</dt><dd>visible vehicles + inbound per minute ÷ 12 + time red ÷ 20</dd></div>
        <div><dt>Green duration</dt><dd>smaller of the effective maximum and minimum green + ⌈2 × visible vehicles + inbound per minute ÷ 6⌉</dd></div>
        <div><dt>Transition</dt><dd>green ends → yellow → all red → next eligible phase</dd></div>
      </dl>
      <p className={styles.note}>For 6 visible vehicles and no measured inbound rate, a 15 s minimum gives 27 s before the maximum is applied.</p>
    </section>;
    case "modes": return <Grid title="Choose the right workflow" items={modes} />;
    case "timeline": case "live": case "offline": case "reports": return <SavedAnalysis view={kind} fetcher={fetcher} />;
    case "evidence": return <Evaluation />;
    case "scope": return <Grid title="Deployment readiness" items={[
      ["Working", "Monitoring, analysis, forecast, simulated advice, and saved reports."],
      ["Needs setup", "A good camera view, mapped approaches, hardware checks, and field measurements."],
      ["Future work", "Multi-junction coordination, controller integration, and emergency signal priority."],
    ]} />;
    case "launch": return null;
    default: return null;
  }
}
