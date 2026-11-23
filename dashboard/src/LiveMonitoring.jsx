import { useEffect, useState } from "react";
import { AnalyzeVideo } from "./Analyze.jsx";
import { LiveRecordingSession } from "./LiveRecordingSession.jsx";
import { PageHead } from "./OpsPages.jsx";
import { BrowserCamera } from "./BrowserCamera.jsx";
import { uploadVideo, wbGet, wbPost } from "./workbench.js";
import { SceneForecast } from "./SceneForecast.jsx";
import { NewCamera } from "./Workbench.jsx";
import { Flow } from "./RecordingPages.jsx";
import { LiveSignals, LiveSignalSchedule } from "./AdaptiveSignals.jsx";
import { simulatedPhase } from "./signalSimulation.js";
export { simulatedPhase } from "./signalSimulation.js";
import styles from "./OpsPages.module.css";
import player from "./Analyze.module.css";
import chart from "./RecordingPages.module.css";

const levels = ["Low", "Moderate", "High", "Severe"];
const rank = (value, cutoffs) => cutoffs.filter(c => value >= c).length;

// Every displayed measurement is limited to the playback clock, including
// the current partial window and the distinction between counts and crossings.
export function monitoringPrefix(result, time) {
  if (!result?.traffic) return null;
  const samples = result.samples.filter(s => s.t <= time).map(s => ({ ...s, then: null }));
  if (!samples.length) return null;
  const { signal_schedule: offlineSchedule, ...traffic } = result.traffic;
  const crossings = traffic.crossings.filter(e => e.t <= time);
  const byType = Object.fromEntries(Object.keys(traffic.by_type).map(k => [k, 0]));
  crossings.forEach(e => { byType[e.type] += 1; });
  const windows = [];
  for (let offset = 0; offset < samples.length; offset += 15) {
    const batch = samples.slice(offset, offset + 15);
    const t = batch[0].t;
    const end = Math.min(time, t + 30);
    const approaches = Object.fromEntries(result.lanes.map(({ name, approach }) =>
      [approach, batch.reduce((sum, row) => sum + row.counts[name], 0) / batch.length]));
    const visible = Object.values(approaches).reduce((sum, n) => sum + n, 0);
    windows.push({ t, end, approaches, visible, level: levels[rank(visible, traffic.policy.density)],
      green: traffic.scope === "frame" ? {} : Object.fromEntries(Object.entries(approaches).map(([a, n]) => [a, traffic.policy.greens[rank(n, traffic.policy.lane_demand)]])),
      crossings: crossings.filter(e => e.t >= t && e.t < t + 30).length });
  }
  const average = samples.reduce((sum, s) => sum + Object.values(s.counts).reduce((a, b) => a + b, 0), 0) / samples.length;
  return { ...result, duration_s: time, samples, traffic: { ...traffic, crossings, windows, by_type: byType,
    average_visible: average, alerts: traffic.alerts.filter(e => e.t <= time) } };
}

function TrafficNow({ result, elapsed, onInspect }) {
  if (!result) return null;
  const { traffic } = result;
  const sample = result.samples.at(-1);
  const window = traffic.windows.at(-1);
  const phase = sample.signal || traffic.signal_problem ? null : simulatedPhase(traffic, elapsed);
  const fields = [
    [traffic.scope === "frame" ? "Distinct confirmed tracks" : "Unique inbound crossings", traffic.crossings.length],
    ...Object.entries(traffic.by_type).map(([kind, n]) => [kind, result.processing.supported_classes.includes(kind) ? n : "Unsupported"]),
    ["Current density", `${window.level} · ${window.visible.toFixed(1)} vehicles in view`],
    ["Flow", traffic.scope === "frame" ? "Needs a counting line" : elapsed >= 1 ? `${(60 * traffic.crossings.length / elapsed).toFixed(1)} crossings/min since start` : "Insufficient data"],
    ["Approach density forecast (60 s)", sample.level ? Object.entries(sample.level).map(([a, level]) => `${a} ${level}`).join(" / ")
      : traffic.scope === "frame" ? "Whole-scene forecast shown above" : "Warming up"],
    ["Approach volume forecast (60 s)", sample.number ? Object.entries(sample.number).map(([a, n]) => `${a} ${n.toFixed(1)} vehicles`).join(" / ")
      : traffic.scope === "frame" ? "Whole-scene forecast shown above" : "Warming up"],
    ...(phase ? [["Legacy simulated phase", `${phase.label} · ${phase.remaining} s remaining`]] : []),
    ["Active alerts", traffic.alerts.length],
  ];
  return <><section className={styles.card}>
    <h3>Monitoring statistics</h3>
    <dl className={styles.fields}>{fields.map(([label, value]) => <div key={label} className={styles.field}>
      <dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {traffic.scope !== "frame" && <p className={styles.muted}>Forecasts use recent approach counts and give point estimates. The simulated green plan uses measured demand and configured clearance intervals.</p>}
    {phase && <div className={player.monitorSignal} role="img" aria-label={`${phase.label}, ${phase.remaining} seconds remaining`}>
      {["red", "yellow", "green"].map(color => <span key={color} data-color={color} data-active={phase.label.toLowerCase().includes(color)} />)}
      <b>{phase.remaining} s</b>
    </div>}
    <h3>Session alerts</h3>
    {traffic.alerts.length ? <ul>{traffic.alerts.map(a => <li key={a.id}>{a.t.toFixed(1)} s · {a.type} · {a.severity} · {a.reason}
      {onInspect && <button type="button" className={styles.button} onClick={() => onInspect(a.t)}>Inspect event</button>}</li>)}</ul>
      : <p className={styles.muted}>No alert conditions have been reached.</p>}
  </section><Flow result={result} />
    {sample.signal && <LiveSignalSchedule signal={sample.signal} elapsed={elapsed} samples={result.samples} />}
  </>;
}

function LiveSignalPanel({ result, elapsed, horizon, setHorizon }) {
  const signal = result?.samples.at(-1)?.signal;
  return <div>
    <SceneForecast result={result} horizon={horizon} onHorizon={setHorizon} />
    {signal ? <LiveSignals signal={signal} elapsed={elapsed} samples={result.samples} policy={result.traffic.policy} compact />
      : <section className={styles.card}><h3>Live adaptive signal prediction</h3>
        <p className={styles.muted}>{result?.traffic.signal_problem ?? (result?.traffic.scope === "frame"
          ? "Select a saved intersection configuration for lane-specific predictions and simulated signal timing."
          : "Waiting for demand from a configured intersection.")}</p></section>}
  </div>;
}

function LiveCalibration({ file, lanes, fetcher, onSaved }) {
  const [upload, stage] = useState(null);
  const [pending, busy] = useState(false);
  const [problem, fail] = useState("");
  const begin = async () => {
    fail("");
    busy(true);
    const response = await uploadVideo(file, fetcher);
    busy(false);
    if (response.status === "ok") stage(response.data.recording);
    else fail(response.reason);
  };
  return <details className={player.how}>
    <summary>Advanced intersection calibration</summary>
    {upload == null ? <button type="button" className={styles.button} disabled={pending} onClick={begin}>
      {pending ? "Preparing calibration?" : "Place and save lane markers"}</button>
      : <NewCamera lanes={lanes} recording={upload} fetcher={fetcher} onCancel={() => stage(null)}
        onSaved={id => { stage(null); onSaved(id); }} />}
    {problem && <p role="alert">{problem}</p>}
  </details>;
}

export function LiveMonitoring({ workbench, fetcher, onProgress, onSaved, active }) {
  const [source, setSource] = useState("demo");
  const [url, setUrl] = useState("");
  const [cameraId, setCameraId] = useState("whole-frame");
  const [cameras, setCameras] = useState(null);
  const [demoProfile, setDemoProfile] = useState("whole-frame");
  const [horizon, setHorizon] = useState(60);
  const [camera, setCamera] = useState({ status: "Disconnected" });
  const [frame, setFrame] = useState(null);
  const [message, setMessage] = useState("");
  const [inspect, setInspect] = useState(null);
  const capable = workbench?.monitoring;
  const hosted = workbench?.hosted;
  const cameraSource = hosted ? (workbench.server_camera ? "registered-camera" : "") : url.trim();
  useEffect(() => {
    if (!capable) return undefined;
    let alive = true;
    wbGet("/workbench/cameras", fetcher).then(r => { if (alive) setCameras(r.status === "ok" ? r.data : []); });
    return () => { alive = false; };
  }, [capable, fetcher, source]);
  useEffect(() => {
    if (!capable || source !== "camera") return undefined;
    let alive = true;
    let pending = false;
    const poll = async () => {
      if (pending) return;
      pending = true;
      const response = await wbGet("/workbench/monitor/camera", fetcher);
      pending = false;
      if (!alive) return;
      if (response.status !== "ok") {
        setCamera({ status: "Error", message: "The camera service is unavailable." });
        onProgress(null);
        return;
      }
      const data = response.data;
      setCamera(data);
      const live = data.status === "Connected" ? data.result : null;
      onProgress(live ? { result: live, time: data.elapsed, source: "camera" } : null);
      if (data.saved_job && data.result && !live) setMessage("Camera measurements saved to analysis history.");
    };
    poll();
    const timer = setInterval(poll, 1100);
    return () => { alive = false; clearInterval(timer); };
  }, [capable, source, fetcher, onProgress]);

  const demoFrame = (data, time) => {
    const result = monitoringPrefix(data, time);
    const next = result ? { result, time, source: "demo" } : null;
    setFrame(next);
    onProgress(next);
  };
  // The upload's clock effects use a stable callback.
  const [onDemo] = useState(() => demoFrame);
  const finish = async (result, id) => {
    const saved = id && await wbPost("/workbench/monitor/finish", { job_id: id }, fetcher);
    if (saved?.status === "ok") {
      setMessage("Monitoring complete. Saved to Results.");
      onSaved(result, id);
    } else setMessage(saved?.reason ?? "The recording could not be saved.");
  };
  const command = async (connect) => {
    setMessage("");
    const reply = await wbPost(`/workbench/monitor/${connect ? "connect" : "disconnect"}`,
      connect ? { source: cameraSource, camera: cameraId } : {}, fetcher);
    if (reply.status !== "ok") setMessage(reply.reason);
    else {
      setCamera({ status: connect ? "Connecting" : "Disconnected" });
      if (!connect) onProgress(null);
    }
  };
  const clearDemo = () => { setMessage(""); setInspect(null); };
  const switchSource = next => {
    if (next === source) return;
    setSource(next); clearDemo(); setFrame(null); onProgress(null);
  };
  const connected = ["Connecting", "Connected"].includes(camera.status);
  const cameraSample = camera.result?.samples.at(-1);
  return <section className={styles.page} aria-label="Dual-mode live monitoring" hidden={!active}>
    <PageHead title="Live monitoring" lead="Choose Traffic Monitoring Source" />
    <div className={`${styles.actions} ${styles.sourceSelector}`} role="group" aria-label="Monitoring source">
      <button type="button" className={styles.button} aria-pressed={source === "camera"} onClick={() => switchSource("camera")}>Real Live Camera / Server</button>
      <button type="button" className={styles.button} aria-pressed={source === "demo"} disabled={connected} onClick={() => switchSource("demo")}>Demo Live – Upload Video</button>
    </div>
    {message && <p role="status" className={styles.banner}>{message}</p>}
    {workbench === null && <p role="status" className={styles.empty}>Checking the live monitoring service…</p>}
    {workbench !== null && !capable && (source === "demo" ? <>
      <AnalyzeVideo browserPreview />
      <div className={styles.banner}>
        <p className={styles.text}>The AI monitoring service is unavailable on this site. You can still preview a recording.</p>
      </div>
    </> : <BrowserCamera />)}
    {capable && source === "demo" && <>
      <AnalyzeVideo caps={workbench} onFile={clearDemo}
        monitor={{ onProgress: onDemo, onFinish: finish, onReset: clearDemo,
          panel: <LiveSignalPanel result={frame?.result} elapsed={frame?.time ?? 0} horizon={horizon} setHorizon={setHorizon} />,
          tools: <div className={styles.card}>
            <h3>Smart AI Traffic Configuration</h3>
            <label className={chart.liveSourceProfile}>Analysis configuration
            <select value={demoProfile} onChange={e => { clearDemo(); setDemoProfile(e.target.value); }}>
              <option value="whole-frame">Automatic AI Analysis</option>
              <option value="">Match a saved configuration by filename</option>
              {(cameras ?? []).map(profile => <option key={profile.id} value={profile.id}>{profile.id}</option>)}
            </select>
          </label>
          <p className={styles.muted}>Automatic mode estimates whole-scene traffic. Saved configurations enable lane selection and approach forecasts.</p>
          </div>,
          calibration: ({ file, lanes }) => workbench.uploads && file && <LiveCalibration key={file.name} file={file}
            lanes={lanes} fetcher={fetcher} onSaved={async id => {
              const response = await wbGet("/workbench/cameras", fetcher);
              if (response.status === "ok") setCameras(response.data);
              clearDemo();
              setDemoProfile(id);
            }} /> }}
        seekTo={inspect} assistant={props => <LiveRecordingSession {...props} profiles={cameras} selected={demoProfile}
          fetcher={fetcher} caps={workbench} />} />
      <TrafficNow result={frame?.result} elapsed={frame?.time ?? 0} onInspect={time => setInspect({ time })} />
    </>}
    {capable && source === "camera" && <>
      <div className={chart.liveSignalLayout}>
      <section className={styles.card}>
        <h3>{camera.status === "Disconnected" ? "No Live Camera Connected" : camera.status}</h3>
        <form onSubmit={e => { e.preventDefault(); command(true); }}>
          {hosted ? <p>{cameraSource ? "STMS server camera" : "No camera has been configured on the STMS server."}</p>
            : <label>Camera URL <input type="password" autoComplete="off" placeholder="rtsp://… or webcam:0" maxLength="300" value={url} disabled={connected} onChange={e => setUrl(e.target.value)} /></label>}
          <label> Camera profile <select value={cameraId} disabled={connected} onChange={e => setCameraId(e.target.value)}>
            <option value="whole-frame">Automatic AI Analysis</option>{(cameras ?? []).map(profile => <option key={profile.id}>{profile.id}</option>)}</select></label>
          <button className={styles.button} type="submit" disabled={connected || !cameraSource || !cameraId || workbench.analysis_ready === false}>Connect Camera</button>
          <button className={styles.button} type="button" disabled={!connected} onClick={() => command(false)}>Disconnect</button>
        </form>
        {workbench.analysis_ready === false && <p role="alert">{workbench.analysis_problem}</p>}
        {camera.message && <p role="status">{camera.message}</p>}
        {camera.status === "Connected" && camera.frame && <div className={player.stage} style={{ "--video-aspect": camera.result.processing.resolution[0] / camera.result.processing.resolution[1] }}>
          <img src={`data:image/jpeg;base64,${camera.frame}`} alt="Current traffic camera frame" style={{ width: "100%" }} />
          <span className={player.tag}>Latest analyzed camera frame</span>
          <svg viewBox="0 0 1 1" preserveAspectRatio="none" className={player.boxes} aria-hidden="true">
            {cameraSample.boxes.map(([x1, y1, x2, y2], i) => <rect key={i} x={x1} y={y1} width={x2-x1} height={y2-y1} vectorEffect="non-scaling-stroke" />)}
          </svg>
          {cameraSample.detections.map(([kind, confidence], i) => <span key={i} className={player.classLabel}
            style={{ left: `${cameraSample.boxes[i][0] * 100}%`, top: `${cameraSample.boxes[i][1] * 100}%` }}>
            {kind}{cameraSample.track_ids?.[i] != null && ` #${cameraSample.track_ids[i]}`} · {Math.round(confidence * 100)}%
          </span>)}
        </div>}
      </section>
      <LiveSignalPanel result={camera.status === "Connected" ? camera.result : null} elapsed={camera.elapsed ?? 0} horizon={horizon} setHorizon={setHorizon} />
      </div>
      <TrafficNow result={camera.status === "Connected" ? camera.result : null} elapsed={camera.elapsed ?? 0} />
    </>}
  </section>;
}
