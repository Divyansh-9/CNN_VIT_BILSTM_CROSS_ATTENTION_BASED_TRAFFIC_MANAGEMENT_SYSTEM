import { useEffect, useState } from "react";
import { ObservedCounts } from "./Analytics.jsx";
import styles from "./App.module.css";
import { Icon } from "./icons.jsx";
import { Horizon, Intersection } from "./Intersection.jsx";
import { ClassPanel, CountPanel, EvidencePanel, HistoryPanel, Overview, StatusPanel } from "./Panels.jsx";
import { ReplayNote, SourceBadge } from "./Source.jsx";
import { useHealth, usePoll } from "./usePoll.js";
import { validateHeartbeat } from "./validate.js";

const REFRESH_MS = 2000; // PRD: dashboard refresh within 2 s
const HISTORY_MS = 10000; // a record of the last minutes; the live panels carry the 2 s budget

// Three sections, one shown at a time. Results is its own section, so live
// numbers and historical evidence can never share a screen (ADR-014).
// Analytics (D21) holds what was counted and what was forecast; it replaced
// History, whose old address still opens it.
export const SECTIONS = [["live", "Live"], ["analytics", "Analytics"], ["results", "Results"]];
const ALIASES = { history: "analytics" };
const ICON_FOR = { live: "live", analytics: "history", results: "results" };
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
  const heartbeat = usePoll(`/heartbeat/${id}/latest`, REFRESH_MS, fetcher);
  // D22: the edge's lane map, from any valid heartbeat. It is configuration,
  // so a stale heartbeat still says how the lanes were mapped.
  const beat = heartbeat.status === "ok" ? validateHeartbeat(heartbeat.data) : null;
  const laneMap = beat?.ok ? beat.data.lanes : null;
  return (
    <main className={styles.page}>
      <header className={styles.top}>
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
          <SourceBadge state={heartbeat} />
          <p className={styles.readonly}>Read-only: this page cannot send commands</p>
        </div>
      </header>
      <ReplayNote state={heartbeat} />

      {section === "live" && (
        <section className={styles.live} aria-label="Live monitor">
          <h2 className={styles.region}>Live forecasts</h2>
          <div className={styles.hero}>
            <div className={styles.heroText}>
              <Overview state={cls} />
              <Horizon cls={cls} count={count} />
            </div>
            <Intersection cls={cls} count={count} />
          </div>
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
          <p className={styles.footnote}>No accuracy is shown here: a live score against the detector's own counts would be circular (ADR-014).</p>
        </section>
      )}

      {section === "analytics" && (
        <section aria-label="Analytics">
          <h2 className={styles.region}>Analytics: what was counted, and what was forecast</h2>
          <ObservedCounts state={observed} window={countWindow} onWindow={setCountWindow} lanes={laneMap} />
          <HistoryPanel classHistory={classHistory} countHistory={countHistory} />
        </section>
      )}

      {section === "results" && (
        <section aria-label="Results">
          <h2 className={styles.region}>Results: historical evaluation evidence</h2>
          <EvidencePanel state={evidence} />
        </section>
      )}
    </main>
  );
}
