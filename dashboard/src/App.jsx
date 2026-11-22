import { useEffect, useRef, useState } from "react";
import { Agreement } from "./Agreement.jsx";
import { AnalyzeVideo } from "./Analyze.jsx";
import { get } from "./api.js";
import { AnalyzeAssistant, ReplayPanel } from "./Workbench.jsx";
import { wbGet } from "./workbench.js";
import { BusyByHour } from "./Busy.jsx";
import { ObservedCounts } from "./Analytics.jsx";
import styles from "./App.module.css";
import { ConsoleOverview } from "./ConsoleOverview.jsx";
import { AlertsPage, PageHead, SignalTiming, SystemPage } from "./OpsPages.jsx";
import { downloadText, toCsv, worstSeverity } from "./ops.js";
import { useAlerts } from "./useAlerts.js";
import { LiveEngineering, ViewToggle } from "./Engineering.jsx";
import { Icon } from "./icons.jsx";
import { ThemeSwitch } from "./ThemeSwitch.jsx";
import { AccountMenu } from "./AuthGate.jsx";
import { ModelPerformance, ReplayOverview } from "./ReplayOverview.jsx";
import { CountBenchmark } from "./CountBenchmark.jsx";
import { Horizon, Intersection } from "./Intersection.jsx";
import { ClassPanel, CountPanel, EvidencePanel, ExpectedShare, ForecastTable, HistoryPanel, Overview, SiteStrip, StatusBanner, StatusPanel, SummaryTiles, TimingSuggestion } from "./Panels.jsx";
import { ReplayNote, SourceBadge } from "./Source.jsx";
import { RecordingPage } from "./RecordingPages.jsx";
import { useRecording } from "./useRecording.js";
import { LiveMonitoring } from "./LiveMonitoring.jsx";
import { Glossary } from "./Glossary.jsx";
import { useHealth, usePoll } from "./usePoll.js";
import { validateHeartbeat } from "./validate.js";

const REFRESH_MS = 2000; // PRD: dashboard refresh within 2 s
const HISTORY_MS = 10000; // a record of the last minutes; the live panels carry the 2 s budget

function ProcessingStatus({ enabled, fetcher }) {
  const [jobs, setJobs] = useState(null);
  const seen = useRef(new Set());
  useEffect(() => {
    if (!enabled) return undefined;
    let active = true;
    let polling = false;
    async function poll() {
      if (polling) return;
      polling = true;
      const reply = await wbGet("/workbench/jobs/active", fetcher);
      if (active && reply.status === "ok") {
        for (const job of Object.values(reply.data)) if (job.running && job.job_id) seen.current.add(job.job_id);
        setJobs(reply.data);
      }
      polling = false;
    }
    poll();
    const timer = setInterval(poll, 1500);
    return () => { active = false; clearInterval(timer); };
  }, [enabled, fetcher]);
  if (!enabled || !jobs || (!jobs.live.running && !jobs.offline.running)) return null;
  return <div className={styles.processingJobs} aria-label="Video processing status">
    {[["Live", jobs.live], ["Video analysis", jobs.offline]].map(([label, job]) => <p key={label}>
      <strong>{label}</strong>
      <span>{job.running ? (label === "Live" && job.progress && !job.stopping ? "Receiving frames" : job.status) : seen.current.has(job.job_id) ? job.status : "Idle"}</span>
      {job.running && job.recording && <span>{job.recording}</span>}
      {job.running && job.progress && <span>{job.progress.done} / {job.progress.total} samples</span>}
    </p>)}
  </div>;
}

// The console's sections, one shown at a time. Results is its own section, so live
// numbers and historical evidence can never share a screen (ADR-014).
// Analytics (D21) holds what was counted and what was forecast; it replaced
// History, whose old address still opens it. Overview is the console's front
// page (where Launch project lands): the live headline answers only, from the
// same polls and panels as Live, so it is part of the live region.
// Signal timing is advisory (P97a: no forecast reaches a signal), Alerts reads
// the live polls, and System is each part's last report; all three are live
// region, so none of them shows evaluation evidence.
export const SECTIONS = [["overview", "Overview"], ["live", "Live"], ["replay", "Guided replay"], ["signals", "Signal timing"], ["analyze", "Analyze a video"],
  ["analytics", "Analytics"], ["alerts", "Alerts"], ["results", "Results"], ["system", "System"]];
const ALIASES = { history: "analytics" };
const ICON_FOR = { overview: "squares-four", live: "live", replay: "history", signals: "signal", analyze: "film-strip", analytics: "chart-line",
  alerts: "warning", results: "results", system: "cpu" };

// Observed counts as rows: one per bucket, one column per lane (named by approach
// when the edge has reported its lane map). A gap stays empty, never 0.
function observedCsv(state, laneMap) {
  if (state.status !== "ok" || !Array.isArray(state.data?.buckets)) return null;
  const lanes = [...new Set(state.data.buckets.flatMap((b) => Object.keys(b.lanes ?? {})))].sort();
  const name = (lane) => (laneMap?.[lane] ? `${laneMap[lane]} (${lane})` : lane);
  const rows = state.data.buckets.map((b) => Object.fromEntries([["time", new Date(b.t * 1000).toISOString()],
    ...lanes.map((l) => [name(l), b.lanes?.[l]?.mean ?? ""])]));
  return toCsv(["time", ...lanes.map(name)], rows);
}
const COUNTS_MS = 30000; // buckets are a minute or longer, so the counts view polls slowly

export function intersectionFromUrl(search) {
  const id = new URLSearchParams(search).get("id") || "j1";
  // The server's INTERSECTION_ID (contracts/mqtt.py, P142), length included.
  return /^[A-Za-z0-9_-]{1,32}$/.test(id) ? id : "j1";
}

// D40: the key of a finished analysis, handed over by the local workbench, or null.
export function analysisFromUrl(search) {
  const key = new URLSearchParams(search).get("analysis");
  return key && /^[0-9a-f]{64}$/.test(key) ? key : null;
}

// Read once: a stored result does not change. Only when the address carries a key.
function useHanded(key, fetcher) {
  const [state, setState] = useState(() => (key ? { status: "loading" } : null));
  useEffect(() => {
    if (!key) return undefined;
    let alive = true;
    get(`/workbench/analysis/${key}`, fetcher).then((result) => { if (alive) setState(result); });
    return () => { alive = false; };
  }, [key, fetcher]);
  return state;
}

// D41: whether the local workbench serves this page. The server has no such route,
// so there this is false and nothing of the workbench renders.
function useWorkbench(fetcher) {
  const [caps, setCaps] = useState(null);
  useEffect(() => {
    let alive = true;
    wbGet("/workbench/capabilities", fetcher).then((r) => { if (alive) setCaps(r.status === "ok" && r.data?.workbench === true ? r.data : false); });
    return () => { alive = false; };
  }, [fetcher]);
  return caps;
}

// Anything that is not a known section opens Live.
const APPROACH_ROUTE = /^#\/?overview\/([NSEW])$/;

export function sectionFromHash(hash) {
  if (APPROACH_ROUTE.test(hash)) return "overview";
  const raw = String(hash || "").replace(/^#\/?/, "");
  const name = ALIASES[raw] ?? raw;
  return SECTIONS.some(([key]) => key === name) ? name : "live";
}

function useConsoleHash(initialHash) {
  const [hash, setHash] = useState(initialHash);
  useEffect(() => {
    const follow = () => setHash(window.location.hash);
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, []);
  return hash;
}

function AnalysisControls({ busy, onAction }) {
  const dialog = useRef(null);
  const open = () => {
    const element = dialog.current;
    if (typeof element.showModal === "function") element.showModal();
    else element.setAttribute("open", "");
  };
  const close = () => {
    if (typeof dialog.current.close === "function") dialog.current.close();
    else dialog.current.removeAttribute("open");
  };
  return <>
    <div className={styles.analysisActions}>
      <button type="button" className={styles.toolButton} disabled={busy} onClick={() => onAction("new")}>New Analysis</button>
      <button type="button" className={styles.toolButton} disabled={busy} onClick={open}>Reset All Analysis Data</button>
    </div>
    <dialog className={styles.analysisDialog} ref={dialog} aria-labelledby="offline-reset-title" aria-describedby="offline-reset-warning">
      <h3 id="offline-reset-title">Restart / Reset Analysis</h3>
      <p id="offline-reset-warning">Are you sure you want to permanently delete all previous analysis results and start fresh? This action cannot be undone.</p>
      <form method="dialog" className={styles.analysisActions}>
        <button type="button" className={styles.toolButton} autoFocus onClick={close}>Cancel</button>
        <button type="button" className={styles.toolButton} onClick={() => {
          close();
          onAction("reset");
        }}>Delete All Results &amp; Restart</button>
      </form>
    </dialog>
  </>;
}

export default function App({ fetcher, previewSite, redesign, search = window.location.search, hash = window.location.hash }) {
  const id = previewSite ?? intersectionFromUrl(search);
  const consoleHash = useConsoleHash(hash);
  const section = sectionFromHash(consoleHash);
  const replayOverview = section === "replay" || (redesign && section === "overview" && !APPROACH_ROUTE.test(consoleHash));
  const approach = APPROACH_ROUTE.exec(consoleHash)?.[1] ?? "E";
  const handed = useHanded(analysisFromUrl(search), fetcher);
  const workbench = useWorkbench(fetcher);
  const recording = useRecording(workbench, fetcher, section === "results");
  const [analyzeReportId, setAnalyzeReportId] = useState(null);
  const [analysisVersion, setAnalysisVersion] = useState(0);
  const [analysisStarting, setAnalysisStarting] = useState(false);
  const changeWorkspace = async (action) => {
    if (await recording.manage(action)) {
      setAnalyzeReportId(null);
      setAnalysisVersion(version => version + 1);
    }
  };
  const [monitorFrame, setMonitorFrame] = useState(null);
  const hasMonitoring = Boolean(workbench?.monitoring);
  const showMonitoring = Boolean(monitorFrame && (section === "live" ||
    (!recording.entry && !["results", "analyze", "replay"].includes(section))));
  const activeContext = showMonitoring ? { ...recording, entry: { result: monitorFrame.result }, selected: null,
    jobs: [], browseHistory: null, openEvent: () => { window.location.hash = "#live"; } } : recording;
  const real = recording.real;
  const showEdge = !real && (!previewSite || workbench !== null);
  const edgePath = path => showEdge ? path : null;
  const savedReplay = real && section === "replay";
  const recordingPage = (real || monitorFrame) && section !== "analyze" && section !== "replay"
    && (section !== "live" || (Boolean(previewSite) && !hasMonitoring));
  const [countWindow, setCountWindow] = useState("1h");
  const count = usePoll(edgePath(`/count_forecast/${id}/latest`), REFRESH_MS, fetcher);
  const cls = usePoll(edgePath(`/prediction/${id}/latest`), REFRESH_MS, fetcher);
  const evidence = usePoll(edgePath("/evidence"), 0, fetcher);
  const health = useHealth(REFRESH_MS, fetcher);
  const classHistory = usePoll(edgePath(`/prediction/${id}/history`), HISTORY_MS, fetcher);
  const countHistory = usePoll(edgePath(`/count_forecast/${id}/history`), HISTORY_MS, fetcher);
  const observed = usePoll(edgePath(`/vehicle_count/${id}/history?window=${countWindow}`), COUNTS_MS, fetcher);
  const recent = usePoll(edgePath(`/vehicle_count/${id}/history?window=1h`), COUNTS_MS, fetcher);
  const day = usePoll(edgePath(`/vehicle_count/${id}/history?window=24h`), COUNTS_MS, fetcher);
  const sites = usePoll(edgePath("/sites"), HISTORY_MS, fetcher);
  const latestCounts = usePoll(edgePath(`/vehicle_count/${id}/latest`), REFRESH_MS, fetcher);
  // D35: Operator is the default, and a reload returns to it. Shared by Live and
  // Analyze, so one choice holds across both.
  const [view, setView] = useState("operator");
  const [glossary, setGlossary] = useState(false);
  const heartbeat = usePoll(edgePath(`/heartbeat/${id}/latest`), REFRESH_MS, fetcher);
  const checks = usePoll(edgePath(`/forecast_check/${id}/recent`), REFRESH_MS, fetcher);
  // D22: the edge's lane map, from any valid heartbeat. It is configuration,
  // so a stale heartbeat still says how the lanes were mapped.
  const beat = heartbeat.status === "ok" ? validateHeartbeat(heartbeat.data) : null;
  const laneMap = beat?.ok ? beat.data.lanes : null;
  // D23: only a valid heartbeat that has gone stale says the edge is silent.
  // No heartbeat at all is unknown, and claims nothing.
  const edgeSilentFor = beat?.ok && beat.data.stale ? beat.data.age_s : null;
  // D26: no check yet reads as warming up only while the edge is reporting.
  const edgeLive = Boolean(beat?.ok && !beat.data.stale);
  const runSession = beat?.ok ? beat.data.source?.session ?? null : null;
  // ADR-028: the letters are labels unless the edge says evidence matches its camera.
  const directionsVerified = beat?.ok && beat.data.directions_verified === true;
  const directions = !directionsVerified && (
    <p className={styles.directions} data-directions="unverified">
      N, S, E and W are labels. Their directions have not been verified for this camera.
    </p>
  );
  const alerts = useAlerts(id, { health, cls, count, heartbeat, latestCounts });
  const liveRef = useRef(null);
  const fullScreen = () => {
    const el = liveRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen?.();
    else el.requestFullscreen?.();
  };
  const csv = observedCsv(observed, laneMap);
  return (
    <>
    <main className={styles.page} data-replay-overview={replayOverview || undefined}>
      <header className={styles.top} data-tour="top">
        <h1 className={styles.brand}>
          <a href="#home" className={styles.brandLink} title="Back to the project home page">
            <span className={styles.mark}><Icon name="signal" size={20} /></span>
            STMS
          </a>
          <span className={styles.sub}>{real ? "Real analysis" : replayOverview ? "Intersection demo" : <>intersection <span className={styles.mono}>{id}</span></>}</span>
        </h1>
        <nav aria-label="Sections" className={styles.nav}>
          {SECTIONS.map(([key, label]) => (
            <a key={key} href={`#${key}`} aria-current={key === section ? "page" : undefined}>
              <Icon name={ICON_FOR[key]} size={16} />{label}
            </a>
          ))}
        </nav>
        <nav aria-label="Project" className={styles.outNav}>
          <a href="#home"><Icon name="house" size={16} />Back to home</a>
        </nav>
        <div className={styles.chips}>
          {/* The badge reports the edge. The Analyze page shows a recording, so it must not say Live camera. */}
          {real && <div className={styles.recordingSource} data-mode="real-analysis">
            <b>Real analysis</b>
            <span>{showMonitoring ? monitorFrame.result.processing.filename : recording.fileName || "Choose a recording"}</span>
            {showMonitoring ? <b>{monitorFrame.source === "demo" ? "Demo Live – Recorded Video" : "Live camera monitoring"}</b> : <>
              {recording.entry?.id && <span>Analysis {recording.entry.id.slice(0, 8)}</span>}
              {recording.selected?.finished_at && <time dateTime={recording.selected.finished_at}>{new Date(recording.selected.finished_at).toLocaleString()}</time>}
            </>}
          </div>}
          {showEdge && previewSite && (section === "overview" || section === "analyze" || replayOverview) &&
            <div className={styles.recordingSource} data-mode="demo"><b>Demo mode</b><span>Bundled traffic data</span></div>}
          {showEdge && section !== "analyze" && section !== "overview" && !replayOverview && <SourceBadge state={heartbeat} sample={Boolean(previewSite)} />}
          {workbench?.history && previewSite && <button type="button" className={styles.linkButton} onClick={() => recording.setMode(real ? "demo" : "real")}>
            {real ? "Switch to demo mode" : "Switch to real analysis"}
          </button>}
          {showEdge && section !== "overview" && !replayOverview && alerts.current.length > 0 && (
            <a href="#alerts" className={styles.alertChip} data-severity={worstSeverity(alerts.current)} data-alert-chip="true">
              <Icon name="warning" size={14} />{alerts.current.length} alert{alerts.current.length > 1 ? "s" : ""}
            </a>
          )}
          <ThemeSwitch />
          <AccountMenu />
          <div className={styles.help}>
            <button type="button" className={styles.linkButton} onClick={() => setGlossary(true)}>Glossary</button>
          </div>
          <p className={styles.readonly} data-mode={workbench ? "workbench" : "read-only"}>
            {workbench ? "Local workbench · no signal commands" : "Read-only: this page cannot send commands"}
          </p>
        </div>
      </header>
      <div className={styles.content}>
      <ProcessingStatus enabled={workbench?.parallel_analysis} fetcher={fetcher} />
      {showEdge && section !== "live" && section !== "analyze" && !replayOverview && !previewSite && <ReplayNote state={heartbeat} />}
      {showEdge && section === "analytics" && directions}
      {(section === "live" && !recordingPage || section === "analyze" || savedReplay) && <ViewToggle view={view} onChange={setView} />}
      {real && recording.error && <p role="alert">{recording.error}</p>}
      {recordingPage && <RecordingPage key={activeContext.entry?.id ?? activeContext.entry?.result.clip ?? "empty"}
        section={section} context={activeContext} caps={workbench}
        monitoringTime={showMonitoring ? monitorFrame.time : undefined} fetcher={fetcher} />}
      {(hasMonitoring || (section === "live" && previewSite)) &&
        <LiveMonitoring workbench={workbench} fetcher={fetcher} active={section === "live"}
          onProgress={setMonitorFrame} onSaved={(result, id) => {
            setMonitorFrame(null);
            if (!workbench?.manage_history && !recording.fileName) recording.accept(result, id);
          }} />}

      {showEdge && replayOverview && <ReplayOverview />}
      {showEdge && section === "overview" && !replayOverview && (
        <ConsoleOverview id={id} health={health} cls={cls} count={count} heartbeat={heartbeat}
                         latestCounts={latestCounts} classHistory={classHistory} sample={Boolean(previewSite)} sites={sites}
                         approach={approach} onApproachChange={(value) => { window.location.hash = `overview/${value}`; }}
                         view={view} onViewChange={setView} laneMap={laneMap}
                         edgeSilentFor={edgeSilentFor} alerts={alerts} />
      )}

      {showEdge && section === "live" && !recordingPage && (!hasMonitoring || !monitorFrame) && (
        <section className={styles.live} aria-label="Live monitor" ref={liveRef}>
          <div className={styles.toolbar}>
            <button type="button" className={styles.toolButton} onClick={fullScreen} data-fullscreen="true">
              <Icon name="squares-four" size={16} />Full screen
            </button>
          </div>
          {workbench && workbench.replay !== false && <ReplayPanel fetcher={fetcher} caps={workbench} />}
          <SiteStrip state={sites} current={id} />
          <div data-tour="status"><StatusBanner health={health} cls={cls} count={count} heartbeat={heartbeat} sample={Boolean(previewSite)} /></div>
          {!previewSite && <ReplayNote state={heartbeat} />}
          <div className={styles.tiles} data-tour="tiles">
            <Overview state={cls} count={count} edgeSilentFor={edgeSilentFor} />
            <SummaryTiles cls={cls} count={count} />
          </div>
          <div className={styles.main}>
            <section className={styles.card} data-tour="drawing" aria-label="The intersection, next 60 seconds">
              <div className={styles.cardHead}><h2>The intersection, next 60 seconds</h2><span>Diagram, not a map</span></div>
              <Intersection cls={cls} count={count} />
              <p className={styles.limit} data-tour="limit" data-limit="signal">
                This system forecasts traffic conditions. It does not control physical traffic signals.
              </p>
            </section>
            <section className={styles.card} data-tour="approaches" aria-label="Approaches">
              <div className={styles.cardHead}><h2>Approaches</h2><span>Forecast beside what was counted</span></div>
              {directions}
              <ForecastTable cls={cls} count={count} recent={recent} lanes={laneMap} />
              <p className={styles.levels} data-levels="true">
                LOW, MEDIUM and HIGH compare the vehicles in view with this camera's own range, set from one
                calibration hour. They do not measure speed or queues, and HIGH can be only a few vehicles.
              </p>
              <ExpectedShare state={count} />
              <div data-tour="what-if"><TimingSuggestion state={count} /></div>
              <details className={styles.how}>
                <summary>How to read these numbers</summary>
                <p>
                  These are forecasts, not measurements. The vehicle number is the average of the counts across
                  the next 60 seconds, which is why it can be a fraction; it counts vehicles in view, not vehicles
                  passing through. Levels are set separately for each camera, so HIGH here is not the same amount
                  of traffic as HIGH elsewhere, and a busier hour than the calibration hour can read HIGH almost
                  all the time. The level and the vehicle number are two separate forecasts, so
                  they may not always match. Counted values leave out bicycles; forecasts include them.
                </p>
              </details>
            </section>
          </div>
          {view === "engineering" && <LiveEngineering state={latestCounts} cls={cls} count={count} lanes={laneMap} />}
          <div data-tour="heat"><Agreement state={checks} edgeLive={edgeLive} runSession={runSession} /></div>
          <details className={styles.technical} data-technical="true" data-tour="technical">
            <summary>Technical details and research information</summary>
            <Horizon cls={cls} count={count} />
            <p className={styles.warning} data-p97a="true">
              Display only: neither forecast is connected to signal timing. In the controller's state,
              0.0 means an approach has no forecast and LOW is encoded as 1/3 (ADR-020 as amended,
              P110). Still open: P97a Part 2, the controller's behaviour under forecast faults, which
              is deferred.
            </p>
            <StatusPanel health={health} cls={cls} count={count} heartbeat={heartbeat} />
            <div className={`${styles.grid} ${styles.below}`}>
              <CountPanel state={count} />
              <ClassPanel state={cls} />
            </div>
            <p className={styles.footnote}>
              No accuracy is shown here: a live score against the detector's own counts would be circular
              (ADR-014). The forecasters are persistence and ridge, not MFSTNet (ADR-027). The count is the mean
              of the next 30 samples at 2 s, per lane (P105), and includes bicycles, which the published counts
              do not (D1). Signal heads are drawn as not connected (P97a). No vehicles or video are shown (NFR-13).
            </p>
          </details>
        </section>
      )}

      {showEdge && section === "signals" && <SignalTiming health={health} count={count} heartbeat={heartbeat} />}
      {showEdge && section === "alerts" && <AlertsPage alerts={alerts} />}
      {showEdge && section === "system" && <SystemPage health={health} cls={cls} count={count} heartbeat={heartbeat} latestCounts={latestCounts} sites={sites} />}

      {(section === "analyze" || real || recording.entry) && (
        <div hidden={section !== "analyze"}>
        {workbench?.manage_history && <AnalysisControls busy={analysisStarting || recording.managing} onAction={changeWorkspace} />}
        <fieldset className={styles.analysisWorkspace} disabled={recording.managing}>
        <AnalyzeVideo key={analysisVersion} view={view} handed={workbench?.uploads ? null : recording.handed ?? handed} caps={workbench}
                      legacyFiles={view === "engineering" && !workbench?.uploads}
                      onAnalysis={(result, id) => { setAnalyzeReportId(id); recording.accept(result, id); }}
                      onFile={file => { setAnalyzeReportId(null); recording.openFile(file); }}
                      onRejected={(file, reason) => { setAnalyzeReportId(null); recording.rejectFile(file, reason); }}
                      assistant={workbench ? (props) => <AnalyzeAssistant {...props} onStarting={setAnalysisStarting} fetcher={fetcher} caps={workbench} /> : null} />
        {workbench?.uploads && analyzeReportId && recording.entry?.id === analyzeReportId &&
          <RecordingPage section="analyze-report" context={recording} caps={workbench} />}
        </fieldset>
        </div>
      )}
      {savedReplay && <section aria-label="Saved recordings">
        {!recording.historyOpen && <button type="button" className={styles.toolButton} onClick={recording.browseHistory}>Browse saved sessions</button>}
        {recording.historyOpen && <label>Completed session <select aria-label="Completed session"
          value={recording.jobs.some(job => job.id === recording.entry?.id) ? recording.entry.id : ""}
          onChange={event => recording.select(recording.jobs.find(job => job.id === event.target.value))}>
          <option value="" disabled>Choose a completed session</option>
          {recording.jobs.filter(job => job.status === "Completed" && job.result_key).map(job =>
            <option key={job.id} value={job.id}>{job.filename} · {new Date(job.finished_at).toLocaleString()}</option>)}
        </select></label>}
        <AnalyzeVideo view={view} replay handed={recording.handed} seekTo={recording.seek} caps={workbench} />
      </section>}

      {showEdge && section === "analytics" && (
        <section aria-label="Analytics" data-tour="analytics">
          <PageHead title="Analytics" lead="What was counted, and what was forecast. Measurements, not accuracy.">
            <button type="button" className={styles.toolButton} disabled={!csv} data-export="observed"
                    onClick={() => downloadText(`stms-${id}-counts-${countWindow}.csv`, csv)}>
              <Icon name="code" size={16} />Export counts (CSV)
            </button>
            <button type="button" className={styles.toolButton} onClick={() => window.print()} data-print="true">
              <Icon name="results" size={16} />Print / save as PDF
            </button>
          </PageHead>
          <BusyByHour state={day} lanes={laneMap} />
          <ObservedCounts state={observed} window={countWindow} onWindow={setCountWindow} lanes={laneMap} />
          <HistoryPanel classHistory={classHistory} countHistory={countHistory} />
        </section>
      )}

      {showEdge && section === "results" && (
        <section aria-label="Results" data-tour="results">
          <PageHead title="Results" lead="Forecast comparisons and historical evaluation evidence.">
            <button type="button" className={styles.toolButton} onClick={() => window.print()} data-print="true">
              <Icon name="results" size={16} />Print / save as PDF
            </button>
          </PageHead>
          <ModelPerformance />
          <CountBenchmark />
          {!previewSite && <EvidencePanel state={evidence} />}
        </section>
      )}
      </div>
    </main>
    {glossary && <Glossary onClose={() => setGlossary(false)} />}
    </>
  );
}
