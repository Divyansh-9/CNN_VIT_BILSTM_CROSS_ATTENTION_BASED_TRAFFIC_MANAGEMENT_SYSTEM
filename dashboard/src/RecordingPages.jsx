import { SceneForecast } from "./SceneForecast.jsx";
import { useEffect, useRef, useState } from "react";
import { PageHead } from "./OpsPages.jsx";
import { CountBenchmark } from "./CountBenchmark.jsx";
import { LiveSignals, OfflineSignals } from "./AdaptiveSignals.jsx";
import { downloadText, toCsv } from "./ops.js";
import { simulatedPhase } from "./signalSimulation.js";
import { wbGet } from "./workbench.js";
import styles from "./OpsPages.module.css";
import chart from "./RecordingPages.module.css";

const number = (n) => Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "Unavailable";
const clock = (t) => t == null ? "—" : `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const date = (t) => t ? new Date(t).toLocaleString() : "Unavailable";
const kinds = { car: "Cars", motorcycle: "Motorcycles", bus: "Buses", truck: "Trucks" };

function Card({ title, children }) {
  return <section className={styles.card}><h3>{title}</h3>{children}</section>;
}

function Fields({ entries }) {
  return <dl className={styles.fields}>{entries.map(([label, value]) => (
    <div className={styles.field} key={label}><dt>{label}</dt><dd>{value}</dd></div>
  ))}</dl>;
}

function Head({ name, result, openEvent }) {
  return <PageHead title={name} lead={result ? `Recorded video · ${result.processing?.filename ?? result.clip}` : "Real analysis mode"}>
    {result && <button type="button" className={styles.button} onClick={() => openEvent(0)}>Open replay</button>}
  </PageHead>;
}

function Summary({ result }) {
  const traffic = result.traffic;
  const peak = traffic.windows.reduce((best, row) => row.visible > best.visible ? row : best);
  const latest = traffic.windows.at(-1);
  const previous = traffic.windows.at(-2);
  const trend = latest.crossings === previous?.crossings ? "Steady"
    : latest.crossings > previous?.crossings ? "Rising" : "Falling";
  return <Card title="Traffic summary"><Fields entries={[
    [traffic.scope === "frame" ? "Distinct confirmed tracks" : "Unique inbound crossings", traffic.crossings.length],
    ["Latest observed density", latest.level],
    ["Average vehicles in view", number(traffic.average_visible)],
    ["Peak occupancy period", `${clock(peak.t)}–${clock(peak.end)} · ${number(peak.visible)} vehicles on average`],
    [traffic.scope === "frame" ? "New-track trend" : "Crossing trend", previous && latest.end - latest.t === previous.end - previous.t ? trend : "Needs two equal-length windows"],
    ["Average flow", traffic.scope === "frame" ? "Requires a counting line" : `${number(60 * traffic.crossings.length / result.duration_s)} inbound crossings/min`],
    ["Queue length and speed", "Require road and distance calibration"],
  ]} />{traffic.policy.density?.length === 3 && <p className={styles.muted}>
    Density uses the average number of vehicles in view per 30-second window.
    Moderate starts at {traffic.policy.density[0]}, High at {traffic.policy.density[1]}, and Severe at {traffic.policy.density[2]}.
  </p>}</Card>;
}

function History({ jobs, selected, select, compare, manage, managing }) {
  if (!jobs.length) return null;
  const recent = jobs.filter((job) => !compare || job.status === "Completed");
  return <Card title={compare ? "Compare recordings" : "Analysis history"}>
    <div className={chart.scroll}><table className={styles.table}><thead><tr>
      <th>Video</th><th>Date and time</th><th>Status</th><th>Analysis ID</th>
      {compare && <><th>Crossings</th><th>Average in view</th><th>Alerts</th></>}
      {manage && <><th>Vehicles counted</th><th>Traffic condition</th><th>Signal recommendation</th></>}
      <th scope="col">Actions</th>
    </tr></thead><tbody>{recent.map((job) => <tr key={job.id}>
      <td>{job.filename}{job.mode && <><br /><small>{({ demo: "Demo Live", offline: "Video analysis", camera: "Live camera", legacy: "Legacy session · source unverified" })[job.mode]}</small></>}</td>
      <td>{date(job.finished_at ?? job.started_at)}</td><td>{job.status}</td>
      <td className={styles.mono}>{job.id.slice(0, 8)}</td>
      {compare && <><td>{number(job.metrics?.crossings)}</td><td>{number(job.metrics?.average_visible)}</td><td>{number(job.metrics?.alerts)}</td></>}
      {manage && <><td>{number(job.metrics?.crossings)}</td><td>{job.metrics?.density ?? "Unavailable"}</td>
        <td>{job.metrics?.next_phase?.phase && Number.isFinite(job.metrics.next_phase.green_s)
          ? `${job.metrics.next_phase.phase} · ${job.metrics.next_phase.green_s} s green`
          : Object.entries(job.metrics?.green ?? {}).map(([lane, seconds]) => `${lane} · ${seconds} s`).join(", ") || "Unavailable"}</td></>}
      <td><div className={styles.actions}>
        {job.result_key && <button className={styles.button} type="button" disabled={managing || selected?.id === job.id}
          onClick={() => select(job)}>{selected?.id === job.id ? "Selected" : manage ? "View Results" : "View"}</button>}
        {manage && job.mode === "offline" && job.status !== "Processing" && <button className={styles.button} type="button" disabled={managing}
          aria-label={`Delete analysis for ${job.filename}`}
          onClick={() => {
            if (window.confirm(`Permanently delete this analysis of ${job.filename}?`)) manage("delete", job);
          }}>Delete</button>}
      </div></td>
    </tr>)}</tbody></table></div>
  </Card>;
}

function SavedHistory({ context, compare, manageOffline }) {
  const { browseHistory, historyOpen, historyLoaded, jobs, selected, select, offline, manage, managing } = context;
  if (!browseHistory) return null;
  if (!historyOpen) return <button className={styles.button} type="button" onClick={browseHistory}>Browse saved sessions</button>;
  const visible = manageOffline ? jobs.filter(job => ["offline", "legacy"].includes(job.mode)) : jobs;
  if (!visible.length) {
    const message = <p role="status" className={styles.muted}>
      {offline ? "Saved sessions are currently unavailable." : historyLoaded ? "No saved sessions." : "Loading saved sessions…"}
    </p>;
    return manageOffline ? <Card title="Analysis history">{message}</Card> : message;
  }
  return <History jobs={visible} selected={selected} select={select} compare={compare}
    manage={manageOffline ? manage : null} managing={managing} />;
}

function TypeChart({ result }) {
  const pairs = Object.entries(result.traffic.by_type);
  const total = result.traffic.crossings.length;
  let start = 0;
  const stops = pairs.map(([, count], index) => {
    const end = start + 100 * count / Math.max(total, 1);
    const stop = `var(--series-${index}) ${start}% ${end}%`;
    start = end;
    return stop;
  });
  return <Card title="Vehicle distribution">
    <div className={chart.distribution}>
      <div className={chart.doughnut} aria-hidden="true"
        style={{ background: total ? `conic-gradient(${stops.join(",")})` : "var(--line)" }}><b>{total}</b></div>
      <div className={chart.series}>{pairs.map(([kind, count], index) => <div key={kind}>
        <span>{kinds[kind]} <b>{result.processing?.supported_classes.includes(kind) ? count : "Unsupported"}</b></span>
        <meter aria-label={kinds[kind]} min="0" max={Math.max(total, 1)} value={count} data-series={index} />
      </div>)}</div>
    </div>
  </Card>;
}

export function Flow({ result, openEvent }) {
  const values = result.traffic.windows;
  const label = result.traffic.scope === "frame" ? "New confirmed tracks" : "Inbound crossings";
  const max = Math.max(1, ...values.map(row => row.crossings));
  const points = values.map((row, i) => `${10 + i * 580 / Math.max(1, values.length - 1)},${110 - row.crossings * 90 / max}`);
  return <Card title={`${label} over time`}>
    <svg viewBox="0 0 600 120" className={chart.plot} role="img" aria-label={`${label} per 30-second interval`}>
      <path d="M10 110H590" className={chart.axis} />
      <polyline points={points.join(" ")} className={chart.trace} />
      {points.map((xy, i) => {
        const [x, y] = xy.split(",");
        return <circle key={i} cx={x} cy={y} r="3"><title>{clock(values[i].t)} · {values[i].crossings} {label.toLowerCase()}</title></circle>;
      })}
    </svg>
    <p className={styles.muted}>Each point covers a 30-second window. The last window can be shorter.</p>
    <div className={chart.scroll}><table className={styles.table}><thead><tr><th>Time</th><th>{label}</th><th>Visible average</th><th>Density</th></tr></thead>
      <tbody>{values.map(row => <tr key={row.t}><td>{openEvent ? <button className={styles.linkButton} type="button" onClick={() => openEvent(row.t)}>{clock(row.t)}–{clock(row.end)}</button> : `${clock(row.t)}–${clock(row.end)}`}</td>
        <td>{row.crossings}</td><td>{number(row.visible)}</td><td>{row.level}</td></tr>)}</tbody></table></div>
  </Card>;
}

function Signals({ traffic, openEvent, monitoringTime }) {
  const [index, setIndex] = useState(null);
  const [phaseTime, setPhaseTime] = useState(0);
  const { windows, policy } = traffic;
  if (traffic.scope === "frame") return <Card title="Signal timing"><p className={styles.empty}>Choose or configure a matching camera profile to estimate demand by approach and simulate signal timing.</p></Card>;
  const current = windows[Math.min(index ?? windows.length - 1, windows.length - 1)];
  const value = (phase) => Math.max(...phase.map(a => current.green[a] ?? 0));
  const phases = [["N", "S"], ["E", "W"]].filter(phase => phase.some(a => a in current.green));
  const plan = phases.flatMap(phase => [
    { label: `${phase.filter(a => a in current.green).join(" + ")} green`, seconds: value(phase) },
    { label: "Yellow clearance", seconds: policy.yellow },
    { label: "All red clearance", seconds: policy.all_red },
  ]);
  const cycle = plan.reduce((sum, phase) => sum + phase.seconds, 0);
  let remaining = phaseTime % Math.max(1, cycle);
  const simulated = plan.find(phase => {
    const active = remaining < phase.seconds;
    remaining -= phase.seconds;
    return active;
  });
  const activePhase = monitoringTime == null ? simulated : simulatedPhase(traffic, monitoringTime);
  return <>
    <Card title="Advisory signal timing">
      <Fields entries={[
        ["Actual phase", "Unavailable from this recording"],
        ["Simulated phase", activePhase?.label ?? "Unavailable"],
        ...(monitoringTime == null ? [] : [["Countdown", activePhase ? `${activePhase.remaining} s · at ${clock(monitoringTime)}` : "Unavailable"]]),
        ["Configured previous green", `${policy.previous_green} s per phase`],
        ["Demo green bounds", `${policy.greens[0]}–${policy.greens.at(-1)} s`],
        ["Transition", `${policy.yellow} s yellow, then ${policy.all_red} s all red before the next phase`],
      ]} />
      <label className={styles.slider}>Demand window at {clock(current.t)}
        <input type="range" min="0" max={windows.length - 1} value={windows.indexOf(current)} onChange={e => setIndex(Number(e.target.value))} />
      </label>
      {monitoringTime == null && cycle > 0 && <label className={styles.slider}>Preview signal cycle at {phaseTime % cycle} s
        <input type="range" min="0" max={cycle - 1} value={phaseTime % cycle} onChange={e => setPhaseTime(Number(e.target.value))} />
      </label>}
      <div className={chart.scroll}><table className={styles.table}><thead><tr><th>Approach</th><th>Vehicles in view</th><th>Recommended green</th><th>Previous green</th><th>Adjustment</th></tr></thead>
        <tbody>{Object.entries(current.green).map(([a, green]) => <tr key={a}><td>{a}</td><td>{number(current.approaches[a])}</td>
          <td>{green} s <meter aria-label={`Green seconds for ${a}`} min="0" max={policy.greens.at(-1)} value={green} /></td><td>{policy.previous_green} s</td>
          <td>{green > policy.previous_green ? "+" : ""}{green - policy.previous_green} s</td></tr>)}</tbody></table></div>
      <p className={styles.muted}>The recommendation uses average vehicles in view in the selected window. Opposing phase labels follow the configured camera map. The simulated phase list sends no hardware commands.</p>
      <ol>{phases.map(phase => <li key={phase[0]}>{phase.filter(a => a in current.green).join(" + ")} · {value(phase)} s green, {policy.yellow} s yellow, {policy.all_red} s all red</li>)}</ol>
    </Card>
    <Card title="Recommendation history"><div className={chart.scroll}><table className={styles.table}>
      <thead><tr><th>Time</th><th>Green by approach</th></tr></thead><tbody>{windows.map(row => <tr key={row.t}>
        <td><button className={styles.linkButton} type="button" onClick={() => openEvent(row.t)}>{clock(row.t)}</button></td>
        <td>{Object.entries(row.green).map(([a, green]) => `${a} ${green} s`).join(" · ")}</td></tr>)}</tbody>
    </table></div></Card>
  </>;
}

function SignalReport({ result, openEvent, monitoringTime }) {
  const { traffic, samples } = result;
  const signal = samples.at(-1)?.signal;
  if (monitoringTime != null && signal) return <LiveSignals signal={signal} elapsed={monitoringTime} samples={samples} policy={traffic.policy} />;
  if (traffic.signal_schedule) return <OfflineSignals schedule={traffic.signal_schedule} result={result} />;
  if (traffic.signal_problem) return <Card title="Signal configuration"><p>{traffic.signal_problem}</p></Card>;
  return <Signals traffic={traffic} openEvent={openEvent} monitoringTime={monitoringTime} />;
}

function eventCounts(alerts) {
  return Object.entries(alerts.reduce((out, item) => ({ ...out, [item.type]: (out[item.type] ?? 0) + 1 }), {}));
}

function AlertList({ context, alerts }) {
  const { selected, entry, jobs, updateAlert, openEvent, offline } = context;
  const failures = jobs.filter(job => job.status === "Failed").map(job => ({
    id: "processing-error", type: "Video processing error", t: null, severity: "Critical",
    reason: job.error, job, source: job.filename,
  }));
  const items = [...alerts.map(event => ({ ...event, job: selected, source: entry.result.processing?.filename ?? entry.result.clip })), ...failures];
  if (offline) items.unshift({ id: "backend-offline", type: "Analysis service unavailable", severity: "Critical",
    reason: "The local job history endpoint could not be reached.", source: "Local workbench" });
  return <Card title="Alert timeline">
    {items.length === 0 && <p className={styles.empty}>No alert conditions were recorded.</p>}
    {items.map(event => <article className={chart.event} key={`${event.job?.id ?? "local"}-${event.id}`}>
      <h4>{event.type} · {event.severity}</h4>
      <p className={styles.muted}>{event.id} · {event.source} · {event.t == null ? date(event.job?.finished_at) : `${clock(event.t)} into recording · analyzed ${date(event.job?.finished_at)}`}</p>
      <p>{event.reason}</p>
      {event.t != null && <button className={styles.button} type="button" onClick={() => openEvent(event.t)}>Replay evidence at {clock(event.t)}</button>}
      {event.job && <label> Status <select value={event.job.alert_statuses?.[event.id] ?? "Active"}
        onChange={e => updateAlert(event.job.id, event.id, e.target.value)}>
        <option>Active</option><option>Acknowledged</option><option>Resolved</option>
      </select></label>}
    </article>)}
    <p className={styles.muted}>Red-light violation detection requires verified signal state and stop lines.</p>
  </Card>;
}

function exportReport(result, job) {
  const { processing, traffic } = result;
  const phases = traffic.signal_schedule?.phases;
  const first = phases?.[0];
  const rows = [];
  const add = (section, time, name, value, detail = "") => {
    const safe = (field) => typeof field === "string" && /^[=+\-@\t\r]/.test(field) ? "'" + field : field;
    rows.push({ section, seconds: time, name: safe(name), value: safe(value), detail: safe(detail) });
  };
  Object.entries({
    filename: processing.filename, analysis_id: job?.id, started_at: job?.started_at,
    completed_at: job?.finished_at, duration_s: result.duration_s, resolution: processing.resolution.join("×"),
    frames: processing.frames, processing_s: processing.seconds, processing_fps: processing.fps,
    detector: processing.model, tracker: processing.tracker,
    [traffic.scope === "frame" ? "distinct_tracks" : "tracked_crossings"]: traffic.crossings.length,
    average_visible: traffic.average_visible, configured_green: traffic.policy.previous_green,
    yellow_s: first ? first.yellow_end - first.green_end : traffic.policy.yellow,
    all_red_s: first ? first.end - first.yellow_end : traffic.policy.all_red,
  }).forEach(([name, value]) => add("summary", "", name, value));
  Object.entries(traffic.by_type).forEach(([kind, n]) => add("vehicle type", "", kind, n));
  traffic.crossings.forEach(event => add(traffic.scope === "frame" ? "track" : "crossing", event.t,
    event.type, event.track_id, traffic.scope === "frame" ? "" : event.approach));
  traffic.windows.forEach(row => {
    add("density", row.t, row.level, row.visible, `${row.crossings} inbound crossings`);
    if (!phases && !traffic.signal_problem) Object.entries(row.green).forEach(([a, green]) =>
      add("signal advice", row.t, a, green, `${row.approaches[a]} vehicles in view`));
  });
  phases?.forEach(phase => {
    add("offline green", phase.start, phase.phase, phase.green_s, phase.reason);
    add("offline yellow", phase.green_end, phase.phase, phase.yellow_end - phase.green_end);
    add("offline all red", phase.yellow_end, phase.phase, phase.end - phase.yellow_end);
  });
  result.samples.forEach(row => Object.entries(row.scene_forecasts ?? {}).forEach(([horizon, forecast]) => {
    const check = forecast.checks ? forecast.checks + " checks, MAE " + forecast.mae : "no completed checks";
    const range = forecast.range ? ", empirical range " + forecast.range.join(" to ") : "";
    add("visible traffic forecast", row.t, horizon + " s", forecast.mean, check + range);
  }));
  traffic.alerts.forEach(event => add("alert", event.t, event.type, event.severity, event.reason));
  downloadText(`${result.clip}.report.csv`, toCsv(["section", "seconds", "name", "value", "detail"], rows));
}

function WorkbenchSystem({ caps, offline, processing, fetcher }) {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    let active = true;
    let pending = false;
    const refresh = async () => {
      if (pending) return;
      pending = true;
      const routes = ["/workbench/capabilities", "/workbench/jobs/current", "/workbench/monitor/camera"];
      const [detector, job, camera] = await Promise.all(routes.map(path => wbGet(path, fetcher)));
      pending = false;
      if (active) setStatus({ detector: detector.data, job: job.data, camera: camera.data });
    };
    if (caps?.history) refresh();
    const timer = caps?.history ? setInterval(refresh, 2500) : null;
    return () => { active = false; if (timer) clearInterval(timer); };
  }, [caps?.history, fetcher]);
  const detector = status ? status.detector : caps;
  return <div className={styles.page}><Head name="System" />
    <Card title="Local analysis service"><Fields entries={[
      ["Backend", detector?.history && !offline ? "Available" : "Unavailable"],
      ["Detector", detector?.model ?? processing?.model ?? "Unavailable"],
      ["Detector configuration", detector?.analysis_ready ? "Checkpoint and dependencies found" : detector?.analysis_problem ?? "Unavailable"],
      ["Tracking", detector?.tracker ?? processing?.tracker ?? "Unavailable"],
      ["Current job", status?.job?.running ? status.job.status : status?.job ? "Idle" : "Unavailable"],
      ["Camera", status?.camera?.status ?? "Unavailable"],
      ["SQLite history", caps?.history && !offline ? "Readable" : "Unavailable"],
    ]} />
    {status?.camera?.message && <p>{status.camera.message}</p>}</Card></div>;
}

export function RecordingPage({ section, context, caps, monitoringTime, fetcher }) {
  const report = useRef(null);
  const { entry, selected, openEvent, offline } = context;
  const result = entry?.result;
  const traffic = result?.traffic;
  const alerts = traffic?.alerts ?? [];
  const processing = result?.processing;
  const inline = section === "analyze-report";
  if (inline) section = "results";
  if (section === "live") return <div className={styles.page}><Head name="Live" />
    <Card title="Live camera"><p className={styles.empty}>No live camera is connected. Select a configured camera in Live Monitoring, or open Guided Replay for a saved recording.</p>
      {result && <button type="button" className={styles.button} onClick={() => openEvent(0)}>Play recording</button>}</Card></div>;
  if (section === "system") return <WorkbenchSystem caps={caps} offline={offline} processing={processing} fetcher={fetcher} />;
  if (section === "alerts") return <div className={styles.page}><Head name="Alerts" result={result} openEvent={openEvent} />
    <AlertList context={context} alerts={alerts} /></div>;
  const title = { overview: "Overview", analytics: "Analytics", signals: "Signal timing", results: "Results" }[section];
  if (!title) return null;
  if (!traffic && inline) return null;
  if (!traffic) return <div className={styles.page}><Head name={title} result={result} openEvent={openEvent} />
    <p className={styles.empty}>{result ? "This older result has frame counts and forecasts. Run a new analysis to add tracked crossings and traffic metrics."
      : "Choose a completed recording or start a new analysis."} <a href="#analyze">Analyze a video</a></p>
    {["overview", "analytics", "results"].includes(section) &&
      <SavedHistory context={context} manageOffline={section === "results" && caps?.manage_history} />}</div>;
  const savePdf = () => {
    const element = report.current;
    element.dataset.printReport = "true";
    document.documentElement.dataset.stmsAnalysisPrint = "true";
    window.addEventListener("afterprint", () => {
      delete element.dataset.printReport;
      delete document.documentElement.dataset.stmsAnalysisPrint;
    }, { once: true });
    window.print();
  };
  return <div className={styles.page} ref={report}>
    <Head name={inline ? "Analysis results" : title} result={result} openEvent={openEvent} />
    {["analytics", "results"].includes(section) && result?.models?.scene && <SceneForecast result={result} />}
    {section === "signals" ? <SignalReport result={result} openEvent={openEvent} monitoringTime={monitoringTime} /> : <>
      <Summary result={result} />
      {(section === "overview" || section === "analytics" || section === "results") && <TypeChart result={result} />}
      {(section === "analytics" || section === "results") && <Flow result={result} openEvent={openEvent} />}
      {(section === "analytics" || section === "results") && <Card title="Alert totals">
        {alerts.length ? <Fields entries={eventCounts(alerts)} /> : <p className={styles.empty}>No alerts in this recording.</p>}
      </Card>}
      {section === "analytics" && <SignalReport result={result} openEvent={openEvent} monitoringTime={monitoringTime} />}
      {section === "results" && <>
        {!inline && <CountBenchmark />}
        <Card title="Report and processing details">
          <Fields entries={[
            ["Filename", processing.filename], ["Analysis ID", selected?.id ?? entry.id ?? "Imported JSON"],
            ["Opened for processing", date(selected?.started_at)], ["Completed", date(selected?.finished_at)],
            ["Status", selected?.status ?? "Completed"], ["Video", `${clock(result.duration_s)} · ${processing.resolution.join(" × ")}`],
            ["Model and tracker", `${processing.model}${processing.imgsz ? ` · ${processing.imgsz} px` : ""} · ${processing.tracker}`], ["Confidence threshold for occupancy", `${Math.round(result.min_confidence * 100)}%`],
            ["Processing", `${number(processing.seconds)} s · ${processing.frames} frames · ${number(processing.fps)} FPS`],
          ]} />
          <div className={styles.actions}><button className={styles.button} type="button" disabled={Boolean(caps?.uploads && entry.id && !selected)}
            onClick={() => exportReport(result, selected ?? entry)}>Download CSV report</button>
            <button className={styles.button} type="button" onClick={() =>
              downloadText(`${result.clip}.analysis.json`, JSON.stringify(result, null, 2), "application/json")}>Download JSON</button>
            <button className={styles.button} type="button" onClick={savePdf}>Save report as PDF</button></div>
        </Card>
        <SignalReport result={result} openEvent={openEvent} />
        <AlertList context={{ ...context, jobs: [], offline: false }} alerts={alerts} />
      </>}
      {!inline && ["overview", "analytics", "results"].includes(section) &&
        <SavedHistory context={context} compare={section === "analytics"} manageOffline={section === "results" && caps?.manage_history} />}
    </>}
  </div>;
}
