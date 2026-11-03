import { useEffect, useState } from "react";
import { Agreement } from "./Agreement.jsx";
import { AnalyzeVideo } from "./Analyze.jsx";
import { BusyByHour } from "./Busy.jsx";
import { ObservedCounts } from "./Analytics.jsx";
import styles from "./App.module.css";
import { LiveEngineering, ViewToggle } from "./Engineering.jsx";
import { Icon } from "./icons.jsx";
import { Horizon, Intersection } from "./Intersection.jsx";
import { ClassPanel, CountPanel, EvidencePanel, ExpectedShare, ForecastTable, HistoryPanel, Overview, SiteStrip, StatusBanner, StatusPanel, SummaryTiles, TimingSuggestion } from "./Panels.jsx";
import { ReplayNote, SourceBadge } from "./Source.jsx";
import { Glossary, Tour } from "./Tour.jsx";
import { useHealth, usePoll } from "./usePoll.js";
import { validateHeartbeat } from "./validate.js";

const REFRESH_MS = 2000; // PRD: dashboard refresh within 2 s
const HISTORY_MS = 10000; // a record of the last minutes; the live panels carry the 2 s budget

// Three sections, one shown at a time. Results is its own section, so live
// numbers and historical evidence can never share a screen (ADR-014).
// Analytics (D21) holds what was counted and what was forecast; it replaced
// History, whose old address still opens it.
export const SECTIONS = [["live", "Live"], ["analyze", "Analyze a video"], ["analytics", "Analytics"], ["results", "Results"]];
const ALIASES = { history: "analytics" };
const ICON_FOR = { live: "live", analyze: "signal", analytics: "history", results: "results" };
const COUNTS_MS = 30000; // buckets are a minute or longer, so the counts view polls slowly

export function intersectionFromUrl(search) {
  const id = new URLSearchParams(search).get("id") || "j1";
  // The server's INTERSECTION_ID (contracts/mqtt.py, P142), length included.
  return /^[A-Za-z0-9_-]{1,32}$/.test(id) ? id : "j1";
}

// Anything that is not a known section opens Live.
export function sectionFromHash(hash) {
  const raw = String(hash || "").replace(/^#\/?/, "");
  const name = ALIASES[raw] ?? raw;
  return SECTIONS.some(([key]) => key === name) ? name : "live";
}

function useSection(initialHash) {
  const [section, setSection] = useState(() => sectionFromHash(initialHash));
  useEffect(() => {
    const follow = () => setSection(sectionFromHash(window.location.hash));
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, []);
  return section;
}

// This browser's own clock: everything else on the page is dated by the server.
function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return <span className={styles.clock} title="This computer's clock">{now.toLocaleTimeString()}</span>;
}

const SEEN_KEY = "stms.tourSeen";
// A convenience only: where storage is blocked, the invitation just shows again.
function tourSeen() {
  try { return window.localStorage.getItem(SEEN_KEY) === "1"; } catch { return false; }
}
function rememberTour() {
  try { window.localStorage.setItem(SEEN_KEY, "1"); } catch { /* nothing to remember it in */ }
}

export default function App({ fetcher, search = window.location.search, hash = window.location.hash }) {
  const id = intersectionFromUrl(search);
  const section = useSection(hash);
  const [countWindow, setCountWindow] = useState("1h");
  // Every stream keeps polling whichever section is open, so the status and
  // the overview are current the moment Live is opened again.
  const count = usePoll(`/count_forecast/${id}/latest`, REFRESH_MS, fetcher);
  const cls = usePoll(`/prediction/${id}/latest`, REFRESH_MS, fetcher);
  const evidence = usePoll("/evidence", 0, fetcher);
  const health = useHealth(REFRESH_MS, fetcher);
  const classHistory = usePoll(`/prediction/${id}/history`, HISTORY_MS, fetcher);
  const countHistory = usePoll(`/count_forecast/${id}/history`, HISTORY_MS, fetcher);
  const observed = usePoll(`/vehicle_count/${id}/history?window=${countWindow}`, COUNTS_MS, fetcher);
  const recent = usePoll(`/vehicle_count/${id}/history?window=1h`, COUNTS_MS, fetcher);
  const day = usePoll(`/vehicle_count/${id}/history?window=24h`, COUNTS_MS, fetcher);
  const sites = usePoll("/sites", HISTORY_MS, fetcher);
  const latestCounts = usePoll(`/vehicle_count/${id}/latest`, REFRESH_MS, fetcher);
  // D35: Operator is the default, and a reload returns to it. Shared by Live and
  // Analyze, so one choice holds across both.
  const [view, setView] = useState("operator");
  const [touring, setTouring] = useState(false);
  const [glossary, setGlossary] = useState(false);
  const [invite, setInvite] = useState(() => !tourSeen());
  const startTour = () => { setInvite(false); rememberTour(); setTouring(true); };
  const declineTour = () => { setInvite(false); rememberTour(); };
  const heartbeat = usePoll(`/heartbeat/${id}/latest`, REFRESH_MS, fetcher);
  const checks = usePoll(`/forecast_check/${id}/recent`, REFRESH_MS, fetcher);
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
  const live = { health, cls, count, heartbeat };
  return (
    <>
    <main className={styles.page} inert={touring ? "" : undefined}>
      <header className={styles.top} data-tour="top">
        <h1 className={styles.brand}>
          <span className={styles.mark}><Icon name="signal" size={24} /></span>
          STMS <span className={styles.sub}>intersection <span className={styles.mono}>{id}</span></span>
        </h1>
        <nav aria-label="Sections" className={styles.nav}>
          {SECTIONS.map(([key, label]) => (
            <a key={key} href={`#${key}`} aria-current={key === section ? "page" : undefined}>
              <Icon name={ICON_FOR[key]} size={16} />{label}
            </a>
          ))}
        </nav>
        <div className={styles.chips}>
          <button type="button" className={styles.tourButton} data-tour-start="true" onClick={startTour}>Take the tour</button>
          <button type="button" className={styles.linkButton} onClick={() => setGlossary(true)}>Glossary</button>
          {/* The badge reports the edge. The Analyze page shows a recording, so it must not say Live camera. */}
          {section !== "analyze" && <SourceBadge state={heartbeat} />}
          <Clock />
          <p className={styles.readonly}>Read-only: this page cannot send commands</p>
        </div>
      </header>
      {invite && section === "live" && (
        <section className={styles.invite} aria-label="New here" data-tour-invite="true">
          <span>New here? The tour explains every part of this page, and shows what problems look like.</span>
          <button type="button" className={styles.tourButton} onClick={startTour}>Take the tour</button>
          <button type="button" className={styles.linkButton} onClick={declineTour}>Not now</button>
        </section>
      )}
      {section !== "live" && section !== "analyze" && <ReplayNote state={heartbeat} />}
      {section === "analytics" && directions}
      {(section === "live" || section === "analyze") && <ViewToggle view={view} onChange={setView} />}

      {section === "live" && (
        <section className={styles.live} aria-label="Live monitor">
          <SiteStrip state={sites} current={id} />
          <div data-tour="status"><StatusBanner health={health} cls={cls} count={count} heartbeat={heartbeat} /></div>
          <ReplayNote state={heartbeat} />
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

      {section === "analyze" && <AnalyzeVideo view={view} />}

      {section === "analytics" && (
        <section aria-label="Analytics" data-tour="analytics">
          <h2 className={styles.region}>Analytics: what was counted, and what was forecast</h2>
          <BusyByHour state={day} lanes={laneMap} />
          <ObservedCounts state={observed} window={countWindow} onWindow={setCountWindow} lanes={laneMap} />
          <HistoryPanel classHistory={classHistory} countHistory={countHistory} />
        </section>
      )}

      {section === "results" && (
        <section aria-label="Results" data-tour="results">
          <h2 className={styles.region}>Results: historical evaluation evidence</h2>
          <EvidencePanel state={evidence} />
        </section>
      )}
    </main>
    {touring && <Tour section={section} live={live} onClose={() => setTouring(false)} />}
    {glossary && <Glossary onClose={() => setGlossary(false)} />}
    </>
  );
}
