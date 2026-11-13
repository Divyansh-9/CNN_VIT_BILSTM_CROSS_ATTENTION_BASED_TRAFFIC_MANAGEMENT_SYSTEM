import { useEffect, useRef, useState } from "react";
import { get } from "./api.js";
import styles from "./Workbench.module.css";
import { validateAnalysis } from "./validate.js";
import { fingerprint, wbGet, wbPost } from "./workbench.js";

// D41: what only the local workbench can do, inside the dashboard itself. Shown only
// when the page is served by scripts/demo_launcher.py; on the server none of this
// renders, and the dashboard is the read-only page it always was.

const MARK = { waiting: "", running: "…", done: "✓", failed: "✕" };
const APPROACHES = ["N", "S", "E", "W"];
const clock = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

// A themed single choice: a list of buttons with radio semantics, never the
// browser's own drop-down, which ignores the page's colours. Long lists get a filter.
export function Choice({ label, options, value, onChange, disabled = false, filterAt = 8 }) {
  const [filter, setFilter] = useState("");
  const shown = filter ? options.filter((o) => `${o.label} ${o.detail ?? ""}`.toLowerCase().includes(filter.toLowerCase())) : options;
  return (
    <div className={styles.choice}>
      {options.length > filterAt && (
        <input className={styles.filter} type="search" placeholder={`Filter ${options.length} ${label.toLowerCase()}`} aria-label={`Filter ${label}`}
               value={filter} onChange={(e) => setFilter(e.target.value)} disabled={disabled} />
      )}
      <div role="radiogroup" aria-label={label} className={styles.options}>
        {shown.map((o) => (
          <button key={o.value} type="button" role="radio" aria-checked={o.value === value} disabled={disabled}
                  className={styles.option} data-choice={o.value} onClick={() => onChange(o.value)}>
            <span className={styles.dot} aria-hidden="true" />
            <span className={styles.optionText}><b>{o.label}</b>{o.detail && <span>{o.detail}</span>}</span>
            {o.tag && <span className={styles.tag}>{o.tag}</span>}
          </button>
        ))}
        {shown.length === 0 && <p className={styles.small}>Nothing matches.</p>}
      </div>
    </div>
  );
}

function Stages({ job }) {
  const p = job.progress;
  const left = !p || p.eta_s === null ? "measuring the speed" : p.eta_s < 60 ? "under a minute left" : `about ${Math.round(p.eta_s / 60)} min left`;
  return (
    <div className={styles.job} aria-live="polite">
      <p className={styles.status} data-job-status="true">{job.status}</p>
      <ol className={styles.stages}>
        {job.stages.map((st, i) => (
          <li key={st.id} data-state={st.state} data-stage={st.id}>
            <span className={styles.mark} aria-hidden="true">{st.state === "waiting" ? i + 1 : MARK[st.state]}</span>
            <span className={styles.stageName}>{st.name}{st.detail && <span className={styles.stageDetail}>{st.detail}</span>}</span>
            <span className={styles.stageWord}>{st.state}</span>
          </li>
        ))}
      </ol>
      {p && (
        <div data-progress="true">
          <div className={styles.bar} role="progressbar" aria-valuemin={0} aria-valuemax={p.total} aria-valuenow={p.done}
               aria-label="Frames analysed"><div style={{ width: `${Math.min(100, (100 * p.done) / p.total)}%` }} /></div>
          <p className={styles.count}>{p.done >= p.total
            ? `All ${p.total.toLocaleString()} frames analysed (one every 2 s of video)`
            : `${p.done.toLocaleString()} of ${p.total.toLocaleString()} frames analysed (one every 2 s of video) · ${left}`}</p>
        </div>
      )}
      {job.checks.length > 0 && (
        <ul className={styles.checks}>
          {job.checks.map((c) => (
            <li key={c.name} data-ok={String(c.ok)}><span>{c.ok === true ? "✓" : c.ok === false ? "✕" : "!"} {c.name}</span><span>{c.detail}</span></li>
          ))}
        </ul>
      )}
      {job.problem && job.problem !== "stopped" && <p className={styles.problem} data-job-problem="true">{job.problem}</p>}
    </div>
  );
}

// Lane placement for a new camera: the picture is the page's own video, and each
// click there adds a lane centre (Analyze.jsx owns the picture and passes `lanes`).
function NewCamera({ lanes, recording, fetcher, onSaved, onCancel }) {
  const [name, setName] = useState("");
  const [reach, setReach] = useState(0.25);
  const [problem, setProblem] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { lanes.begin(); return () => lanes.end(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { lanes.setReach(reach); }, [reach]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = async () => {
    setProblem("");
    if (!/^[A-Za-z0-9_-]{1,32}$/.test(name)) { setProblem("Name the camera with 1 to 32 letters, digits, - or _."); return; }
    if (lanes.points.length === 0) { setProblem("Click the picture to place at least one lane."); return; }
    setSaving(true);
    const r = await wbPost("/workbench/cameras", { id: name, recording, max_radius: reach,
      lanes: lanes.points.map((p) => ({ centre: [Number(p.x.toFixed(4)), Number(p.y.toFixed(4))], approach: p.approach })) }, fetcher);
    setSaving(false);
    if (r.status !== "ok") { setProblem(r.reason); return; }
    onSaved(r.data.id);
  };
  return (
    <div className={styles.newCamera} data-new-camera="true">
      <p className={styles.small}><b>Click the picture</b> on the centre of each lane you want counted, up to four. Pause on a busy moment first.</p>
      <ol className={styles.lanes}>
        {lanes.points.map((p, i) => (
          <li key={i} data-lane={i}>
            <span className={styles.mono}>L{i}</span>
            <span className={styles.segment} role="radiogroup" aria-label={`Approach of lane ${i}`}>
              {APPROACHES.map((a) => (
                <button key={a} type="button" role="radio" aria-checked={p.approach === a} disabled={lanes.points.some((q, j) => j !== i && q.approach === a)}
                        onClick={() => lanes.setApproach(i, a)}>{a}</button>
              ))}
            </span>
            <button type="button" className={styles.linkButton} onClick={() => lanes.remove(i)} aria-label={`Remove lane ${i}`}>Remove</button>
          </li>
        ))}
      </ol>
      <label className={styles.field}><span>Reach of each lane: <span className={styles.mono}>{reach.toFixed(2)}</span> of the picture</span>
        <input type="range" min="0.05" max="0.5" step="0.01" value={reach} onChange={(e) => setReach(Number(e.target.value))} />
      </label>
      <label className={styles.field}><span>Camera name</span>
        <input className={styles.text} value={name} maxLength={32} placeholder="for example Gate_2_North" onChange={(e) => setName(e.target.value)} />
      </label>
      <p className={styles.small}>N, S, E and W are labels you choose, not verified directions. This camera stays on this computer, is marked
        provisional, and its LOW, MEDIUM and HIGH levels are set from the first recording you analyse with it, so they flatter that
        recording and are not evidence.</p>
      {problem && <p className={styles.problem}>{problem}</p>}
      <div className={styles.row}>
        <button type="button" className={styles.primary} onClick={save} disabled={saving}>Save camera</button>
        <button type="button" className={styles.button} onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

// The whole analysis, beside the picture: find the file, choose its camera, analyse,
// and the results appear on this page. `file` is the File the viewer opened here.
export function AnalyzeAssistant({ file, lanes, onResults, fetcher }) {
  const [where, setWhere] = useState({ state: "idle" });   // idle | finding | found | missing | error
  const [cameras, setCameras] = useState([]);
  const [camera, setCamera] = useState(null);
  const [making, setMaking] = useState(false);
  const [job, setJob] = useState(null);
  const [problem, setProblem] = useState("");
  const [asking, setAsking] = useState(false);
  const delivered = useRef(null);

  const loadCameras = async () => {
    const r = await wbGet("/workbench/cameras", fetcher);
    if (r.status === "ok") setCameras(r.data);
  };
  useEffect(() => { loadCameras(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const find = async () => {
    if (!file) return;
    setWhere({ state: "finding" });
    let print;
    try { print = await fingerprint(file); } catch (error) { setWhere({ state: "error", reason: error.message }); return; }
    const r = await wbPost("/workbench/locate", { name: file.name, size: file.size, fingerprint: print }, fetcher);
    if (r.status !== "ok") setWhere({ state: "error", reason: r.reason });
    else if (r.data.found) setWhere({ state: "found", recording: r.data.recording });
    else setWhere({ state: "missing", complete: r.data.searched_everything });
  };
  useEffect(() => { delivered.current = null; setJob(null); setProblem(""); if (file) onResults(null); find(); }, [file]); // eslint-disable-line react-hooks/exhaustive-deps

  // D42: the declared camera's lanes over the picture, before anything is analysed, so a
  // camera that does not match this video shows as lanes off its roads.
  useEffect(() => {
    const chosen = cameras.find((c) => c.id === camera);
    lanes.preview(chosen?.geometry?.lanes && !making && file ? { camera: chosen.id, ...chosen.geometry } : null);
  }, [camera, making, cameras, file]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => lanes.preview(null), []); // eslint-disable-line react-hooks/exhaustive-deps

  const [length, setLength] = useState(7);
  const [replayProblem, setReplayProblem] = useState("");
  const replay = async () => {
    setReplayProblem("");
    const r = await wbPost("/workbench/replay/start", { recording: where.recording, camera: job.camera, minutes: length }, fetcher);
    if (r.status !== "ok") { setReplayProblem(r.reason); return; }
    window.location.hash = "#live";
  };

  const showFolder = async () => {
    setAsking(true);
    const r = await wbPost("/workbench/folder", {}, fetcher);
    setAsking(false);
    if (r.status !== "ok") { setWhere({ state: "error", reason: r.reason }); return; }
    if (r.data.added) find();
  };

  // While a job runs, follow it; when it is ready, read its results and hand them over.
  const running = job?.running;
  useEffect(() => {
    if (!running) return undefined;
    let alive = true;
    const timer = setInterval(async () => {
      const r = await wbGet("/workbench/jobs/current", fetcher);
      if (alive && r.status === "ok") setJob(r.data);
    }, 1000);
    return () => { alive = false; clearInterval(timer); };
  }, [running, fetcher]);
  useEffect(() => {
    const key = job?.key;
    if (!key || delivered.current === key) return;
    delivered.current = key;
    (async () => {
      const r = await get(`/workbench/analysis/${key}`, fetcher);
      if (r.status !== "ok") { setProblem(`The finished results could not be read: ${r.reason ?? "not found"}.`); return; }
      const checked = validateAnalysis(r.data);
      if (!checked.ok) { setProblem(`The finished results were refused: ${checked.reason}.`); return; }
      onResults(checked.data);
      if (job.camera) loadCameras();
    })();
  }, [job?.key]); // eslint-disable-line react-hooks/exhaustive-deps

  const analyse = async () => {
    setProblem("");
    if (!camera) { setProblem("Choose the camera that recorded this video first."); return; }
    const r = await wbPost("/workbench/jobs", { recording: where.recording, camera }, fetcher);
    if (r.status !== "ok") { setProblem(r.reason); return; }
    const state = await wbGet("/workbench/jobs/current", fetcher);
    if (state.status === "ok") setJob(state.data.key ? state.data : { ...state.data, running: true });
  };
  const stop = () => wbPost("/workbench/jobs/stop", {}, fetcher);

  if (!file) {
    return (
      <section className={styles.assistant} aria-label="Analyze on this computer" data-assistant="idle">
        <p className={styles.lead}><b>Any video on this computer.</b> Open it above; it plays here, and the workbench analyses the same file where it lies. Nothing is uploaded.</p>
      </section>
    );
  }
  const camOptions = cameras.map((c) => ({
    value: c.id, label: c.id,
    detail: `${c.lanes} lane${c.lanes === 1 ? "" : "s"}${c.provisional ? (c.levels_set ? ", levels set" : ", levels set by the first analysis") : ", reviewed profile"}`,
    tag: c.provisional ? "provisional" : null,
  }));
  const busy = job?.running;
  return (
    <section className={styles.assistant} aria-label="Analyze on this computer" data-assistant={where.state}>
      <h3>2. Analyze it on this computer</h3>
      <p className={styles.where} data-where={where.state}>
        {where.state === "finding" && "Finding this file on this computer…"}
        {where.state === "found" && <><span className={styles.ok} aria-hidden="true">✓</span> Found on this computer</>}
        {where.state === "missing" && (where.complete
          ? "The workbench cannot see the folder this file is in."
          : "The workbench looked for a while and did not find this file.")}
        {where.state === "error" && `Not available: ${where.reason}`}
      </p>
      {where.state === "missing" && (
        <div className={styles.row}>
          <button type="button" className={styles.primary} onClick={showFolder} disabled={asking} data-show-folder="true">
            {asking ? "A folder window is open on this computer…" : "Show the workbench where it is"}
          </button>
          <span className={styles.small}>Your own folder window opens; only the folder's name comes back to this page.</span>
        </div>
      )}
      {where.state === "found" && !making && (
        <>
          <p className={styles.label}>The camera that recorded it <span className={styles.small}>You declare it; nothing guesses it.</span></p>
          <Choice label="Cameras" options={camOptions} value={camera} onChange={setCamera} disabled={busy} />
          {camera && <p className={styles.preview} data-preview-note="true">The dashed lanes on the picture are {camera}'s. If they do not sit on this
            video's roads, the video is from a different camera: choose another, or place its lanes. A wrong camera counts the wrong places.</p>}
          <button type="button" className={styles.linkButton} onClick={() => setMaking(true)} disabled={busy} data-make-camera="true">+ A camera not listed: place its lanes</button>
          <div className={styles.row}>
            <button type="button" className={styles.primary} onClick={analyse} disabled={busy} data-analyse="true">Analyze</button>
            {busy && <button type="button" className={styles.button} onClick={stop}>Stop</button>}
          </div>
        </>
      )}
      {where.state === "found" && making && (
        <NewCamera lanes={lanes} recording={where.recording} fetcher={fetcher}
                   onSaved={async (id) => { await loadCameras(); setCamera(id); setMaking(false); }} onCancel={() => setMaking(false)} />
      )}
      {problem && <p className={styles.problem} data-assistant-problem="true">{problem}</p>}
      {job && <Stages job={job} />}
      {job?.key && !job.running && (
        <div className={styles.next} data-replay-this="true">
          <p className={styles.label}>Replay this video through the system <span className={styles.small}>The same video, in real time,
            through the edge, MQTT, the server and Live. The page says REPLAY.</span></p>
          <span className={styles.segment} role="radiogroup" aria-label="How much to replay">
            {[[7, "7 min"], [30, "30 min"], ["whole", "Whole video"]].map(([v, label]) => (
              <button key={label} type="button" role="radio" aria-checked={length === v} onClick={() => setLength(v)}>{label}</button>
            ))}
          </span>
          <div className={styles.row}><button type="button" className={styles.button} onClick={replay} data-replay-start="true">Replay on Live</button></div>
          {replayProblem && <p className={styles.problem}>{replayProblem}</p>}
        </div>
      )}
    </section>
  );
}

// What runs through the whole deployed system, from the Live section: a recorded
// clip replayed in real time, or the live camera (D42). While it runs, the panels
// below read that run's server through the workbench. The camera's address is never
// in this page: the workbench was started with STMS_CAMERA_URL, and the page only
// learns whether it is set.
export function ReplayPanel({ fetcher, caps = {} }) {
  const [clips, setClips] = useState([]);
  const [clip, setClip] = useState(null);
  const [cameras, setCameras] = useState([]);
  const [camera, setCamera] = useState(null);
  const [mode, setMode] = useState("clip");
  const [state, setState] = useState(null);
  const [problem, setProblem] = useState("");
  useEffect(() => {
    let alive = true;
    wbGet("/workbench/replay/clips", fetcher).then((r) => { if (alive && r.status === "ok") { setClips(r.data); setClip(r.data[0]?.number ?? null); } });
    wbGet("/workbench/cameras", fetcher).then((r) => { if (alive && r.status === "ok") setCameras(r.data.filter((c) => c.levels_set)); });
    const tick = async () => { const r = await wbGet("/workbench/replay/state", fetcher); if (alive && r.status === "ok") setState(r.data); };
    tick();
    const timer = setInterval(tick, 2000);
    return () => { alive = false; clearInterval(timer); };
  }, [fetcher]);
  const run = async () => {
    setProblem("");
    const r = mode === "camera"
      ? await wbPost("/workbench/camera/start", { camera }, fetcher)
      : await wbPost("/workbench/replay/start", { clip }, fetcher);
    if (r.status !== "ok") setProblem(r.reason);
  };
  const stop = () => wbPost("/workbench/replay/stop", {}, fetcher);
  const running = state?.running;
  const live = state?.kind === "camera";
  return (
    <details className={styles.replay} open={running || undefined} data-replay-panel="true">
      <summary><b>Run through the system</b> <span className={styles.small}>{state?.status ?? ""}</span></summary>
      {running ? (
        <p className={styles.where} data-replaying={live ? "camera" : "replay"}>
          {live ? <>Live camera, counted as <b className={styles.mono}>{state.camera}</b>.</>
            : <>Replaying <b className={styles.mono}>{state.clip}</b>{state.minutes ? `, ${state.minutes} min of footage` : ""}.</>}
          {" "}The panels below show it while it runs.
        </p>
      ) : (
        <>
          <span className={styles.segment} role="radiogroup" aria-label="What to run">
            <button type="button" role="radio" aria-checked={mode === "clip"} onClick={() => setMode("clip")}>Recorded clip</button>
            <button type="button" role="radio" aria-checked={mode === "camera"} onClick={() => setMode("camera")} data-mode-camera="true">Live camera</button>
          </span>
          {mode === "clip" && (
            <>
              <p className={styles.small}><b>Recorded footage, not a camera.</b> The page says REPLAY; a real camera stream has not been
                qualified yet (S65). To replay any other video, analyse it on Analyze a video first, then choose "Replay on Live" there.</p>
              <Choice label="Clips" options={clips.map((c) => ({ value: c.number, label: c.id, tag: c.rehearsed ? "rehearsed" : null }))}
                      value={clip} onChange={setClip} />
            </>
          )}
          {mode === "camera" && !caps.camera_configured && (
            <div className={styles.steps} data-camera-steps="true">
              <p className={styles.small}><b>No camera is configured on this computer.</b> The camera's address can hold a password, so it is never
                typed into this page. To connect one:</p>
              <ol>
                <li>Find the camera's stream address: an IP camera's RTSP address, or a phone camera app's stream address on the same Wi-Fi.</li>
                <li>Stop the workbench. In the terminal that starts it, set the address, for example in PowerShell:
                  <code>$env:STMS_CAMERA_URL = "rtsp://user:password@192.168.1.20:554/stream1"</code></li>
                <li>Start the workbench again in that terminal and come back here.</li>
                <li>The camera needs its lanes placed once: record a few minutes from it, open that file in Analyze a video, and choose
                  "A camera not listed". Its first analysis sets its levels.</li>
              </ol>
            </div>
          )}
          {mode === "camera" && caps.camera_configured && (
            <>
              <p className={styles.small}><b>A camera is configured on this computer.</b> Choose which camera profile it is: its lanes must fit this
                camera's picture. The page will say LIVE CAMERA. A live stream has not been qualified yet (S65), so treat a run as a rehearsal.</p>
              <Choice label="Cameras" options={cameras.map((c) => ({ value: c.id, label: c.id, detail: `${c.lanes} lanes`, tag: c.provisional ? "provisional" : null }))}
                      value={camera} onChange={setCamera} />
            </>
          )}
        </>
      )}
      <p className={styles.small}>It forecasts traffic, not the signal: it sends no signal commands, and the signal heads read "not connected" (P97a).
        The forecast check is agreement with the detector's own later counts, not accuracy. Runs and analyses take turns: both need the GPU.</p>
      <div className={styles.row}>
        {!running && mode === "clip" && <button type="button" className={styles.primary} onClick={run} disabled={clip === null}>Run the replay</button>}
        {!running && mode === "camera" && caps.camera_configured &&
          <button type="button" className={styles.primary} onClick={run} disabled={!camera} data-connect-camera="true">Connect the camera</button>}
        {running && <button type="button" className={styles.button} onClick={stop} disabled={state?.stopping}>Stop</button>}
        {!running && mode === "clip" && <span className={styles.small}>Plays in real time; the first forecasts take a few minutes because the forecasters need history.</span>}
      </div>
      {state && (state.running || state.code !== null) && (
        <ul className={styles.checks} data-milestones="true">
          {state.milestones.map((m) => <li key={m.name} data-reached={String(m.at_s !== null)}><span>{m.name}</span><span>{m.at_s !== null ? `at ${clock(m.at_s)}` : m.expected}</span></li>)}
        </ul>
      )}
      {(problem || state?.problem) && <p className={styles.problem}>{problem || state.problem}</p>}
    </details>
  );
}
