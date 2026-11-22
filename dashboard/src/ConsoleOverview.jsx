import styles from "./ConsoleOverview.module.css";
import panel from "./Panels.module.css";
import { LiveEngineering, ViewToggle } from "./Engineering.jsx";
import { Icon } from "./icons.jsx";
import { JunctionMap, junction } from "./Intersection.jsx";
import { detectorFps, edgeState, modelIds, SEVERITY_ORDER, worstSeverity } from "./ops.js";
import { ApproachAlertLinks, RecentActivity, Severity, VehicleMix } from "./OpsPages.jsx";
import { Overview, StatusBanner, Tile } from "./Panels.jsx";
import { SourceBadge } from "./Source.jsx";
import { APPROACHES, validateHeartbeat, validateHistory, validateLatestCounts, validateSites } from "./validate.js";

// The console's Overview: the few answers an operator needs first, each from a
// poll App already makes, and each saying in words when it cannot answer.
// It reuses the Live panels' own logic (StatusBanner, Overview),
// so a number here can never disagree with the same number on Live. Like Live,
// it is the live region: no benchmark or evaluation number appears (ADR-014).

// The latest counted vehicles, from GET /vehicle_count/{id}/latest. Only lanes
// that are current are summed; a lane that has not reported is absent, never 0.
export function vehiclesNow(state) {
  if (state.status === "loading") return { value: null, text: "Waiting", sub: "Asking the server" };
  if (state.status === "unavailable") return { value: null, text: "None yet", sub: "No counts received yet" };
  if (state.status === "error") return { value: null, text: "Unknown", sub: "Server not reachable" };
  const checked = validateLatestCounts(state.data);
  if (!checked.ok) return { value: null, text: "Invalid", sub: `Refused: ${checked.reason}` };
  const lanes = Object.values(checked.data.lanes);
  if (lanes.length === 0) return { value: null, text: "None yet", sub: "No lane has reported" };
  const fresh = lanes.filter((l) => !l.stale);
  if (fresh.length === 0) {
    const age = Math.min(...lanes.map((l) => l.age_s));
    return { value: null, text: "Out of date", sub: `Last counted ${age.toFixed(0)} s ago` };
  }
  const total = fresh.reduce((sum, l) => sum + l.count, 0);
  const lagging = lanes.length - fresh.length;
  return { value: total,
           sub: `${fresh.length} of ${lanes.length} lanes current${lagging ? `, ${lagging} out of date` : ""}. Bicycles not counted.` };
}

const NEXT = [
  ["live", "live", "Live monitoring", "The intersection drawing, each approach's forecast, and the forecast check."],
  ["signals", "signal", "Signal timing", "The demand-based green split, the safety limits and the fail-safe. Advisory only."],
  ["analyze", "film-strip", "Analyze a video", "Open a recording and its results file, and step through what was counted."],
  ["analytics", "chart-line", "Analytics", "When each lane is busy, observed counts, and forecast history."],
  ["results", "results", "Results", "The committed evaluation evidence, each with its commit."],
  ["system", "cpu", "System health", "Server, camera unit, detector and forecast streams, from their last reports."],
];

const SEV = { critical: "Critical", serious: "Serious", warning: "Warning", info: "Info" };

function Kpi({ label, icon, result, ...rest }) {
  return (
    <Tile label={<><Icon name={icon} size={14} /> {label}</>} sub={result.sub} {...rest}>
      {result.value !== null ? <span className={styles.mono}>{result.value}</span> : <span className={styles.none}>{result.text}</span>}
    </Tile>
  );
}

const APPROACH_LABELS = { N: "N", S: "S", E: "E", W: "W" };
const reportTime = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function ApproachDetail({ approach, lane, latestCounts, heartbeat, classHistory }) {
  const beat = heartbeat.status === "ok" ? validateHeartbeat(heartbeat.data) : null;
  const counts = latestCounts.status === "ok" ? validateLatestCounts(latestCounts.data) : null;
  const laneName = Object.entries(beat?.ok ? beat.data.lanes ?? {} : {})
    .find(([, label]) => label === approach)?.[0];
  const observed = counts?.ok && laneName ? counts.data.lanes[laneName] : null;
  const history = classHistory?.status === "ok" ? validateHistory(classHistory.data, "class") : null;
  const trend = history?.ok ? [...history.data.rows].sort((a, b) => a.at - b.at).slice(-8) : [];

  return (
    <section className={styles.detail} aria-label={`Approach ${approach} details`}>
      <h3>Approach {approach}</h3>
      <dl className={styles.metrics}>
        <div><dt>Vehicles in view now</dt><dd>{observed?.stale ? "Out of date" : observed?.count ?? "Unavailable"}</dd></div>
        <div><dt>Next 60 seconds</dt><dd>{lane.count === undefined ? "Unavailable" : `${lane.count.toFixed(1)} veh`}</dd></div>
        <div><dt>Forecast congestion</dt><dd>{lane.cls
          ? <span className={`${panel.chip} ${lane.kind === "stale" ? "" : panel[lane.cls]}`}>{lane.cls}{lane.kind === "stale" && " · expired"}</span>
          : "Unavailable"}</dd></div>
      </dl>
      <h4>Recent congestion forecasts</h4>
      {trend.some((row) => row.predictions[approach]) ? (
        <ol className={styles.trend} aria-label="Congestion forecast trend, oldest first">
          {trend.map((row, index) => {
            const level = row.predictions[approach];
            const date = new Date(row.at * 1000);
            const time = Number.isFinite(date.getTime()) ? reportTime.format(date) : "Time unavailable";
            const label = `${time} · ${level ?? "Unavailable"}`;
            return <li key={`${row.at}-${index}`} aria-label={label} title={label}>
              {level ? <span className={`${panel.chip} ${panel[level]}`}>{level[0]}</span> : "–"}
            </li>;
          })}
        </ol>
      ) : <p className={styles.empty}>No recent forecasts for this approach.</p>}
    </section>
  );
}

function OperationsHeader({ id, sites, heartbeat, sample, alerts }) {
  const checked = sites?.status === "ok" ? validateSites(sites.data) : null;
  const choices = [id, ...(checked?.ok && !sample ? checked.data.sites.filter((site) => site.kind !== null && site.id !== id).map((site) => site.id) : [])];
  const sorted = [...alerts].sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));
  return (
    <div className={styles.opsBar} role="group" aria-label="Operations status">
      <label className={styles.siteChoice}>
        <span>Intersection</span>
        <select value={id} onChange={(event) => { window.location.href = `?id=${encodeURIComponent(event.target.value)}#overview`; }}>
          {choices.map((site) => <option key={site} value={site}>{sample ? "Sample intersection" : site}</option>)}
        </select>
      </label>
      <div className={styles.opsSource}>
        <span>Source · Last update</span>
        <SourceBadge state={heartbeat} sample={sample} />
      </div>
      {sorted.length ? (
        <details className={styles.opsAlerts} onClick={(event) => {
          if (event.target.closest("a")) event.currentTarget.open = false;
        }}>
          <summary><Icon name="warning" size={16} />{sorted.length} active alert{sorted.length === 1 ? "" : "s"}</summary>
          <div className={styles.alertMenu}>
            <ul>{sorted.map((alert) => (
              <li key={alert.key}>
                <Severity level={alert.severity} />
                <b>{alert.title}</b>
                <p>{alert.detail}</p>
                <ApproachAlertLinks approaches={alert.approaches} />
              </li>
            ))}</ul>
            <a href="#alerts">Open alert centre</a>
          </div>
        </details>
      ) : <a className={styles.opsLink} href="#alerts"><Icon name="check-circle" size={16} />0 active alerts</a>}
      <a className={styles.opsLink} href="#replay"><Icon name="history" size={16} />Guided replay</a>
    </div>
  );
}

function Diagnostics({ cls, count, heartbeat, latestCounts, laneMap, snapshot }) {
  const fps = detectorFps(latestCounts);
  const edge = edgeState(heartbeat);
  const models = modelIds(cls, count);
  const absentForecasts = APPROACHES.filter((approach) => {
    const lane = snapshot.lanes[approach];
    return lane.count === undefined || !lane.cls;
  });
  const checked = latestCounts.status === "ok" ? validateLatestCounts(latestCounts.data) : null;
  const missingLanes = checked?.ok && laneMap
    ? Object.keys(laneMap).filter((lane) => !Object.hasOwn(checked.data.lanes, lane))
    : null;
  return (
    <section className={styles.card} aria-label="Detector and forecast diagnostics">
      <h3>Detector and forecast diagnostics</h3>
      <dl className={styles.diagnostics}>
        <div><dt>Detector FPS</dt><dd>{fps?.fps.toFixed(2) ?? "Unavailable"}</dd></div>
        <div><dt>Last heartbeat</dt><dd>{edge ? `${edge.age.toFixed(0)} s ago · ${edge.stale ? "Stale" : "Current"}` : "Unavailable"}</dd></div>
        <div><dt>Missing lane counts</dt><dd>{missingLanes ? missingLanes.join(", ") || "None" : "Unavailable"}</dd></div>
        <div><dt>Incomplete approach forecasts</dt><dd>{absentForecasts.join(", ") || "None"}</dd></div>
        <div><dt>Congestion model</dt><dd>{models.level ?? "Unavailable"}</dd></div>
        <div><dt>Vehicle-count model</dt><dd>{models.number ?? "Unavailable"}</dd></div>
      </dl>
      <LiveEngineering state={latestCounts} cls={cls} count={count} lanes={laneMap} />
    </section>
  );
}

export function ConsoleOverview({ id, health, cls, count, heartbeat, latestCounts, classHistory, sample, sites,
  approach, onApproachChange, view, onViewChange, laneMap, edgeSilentFor, alerts }) {
  const snapshot = junction(cls, count);
  return (
    <section className={styles.overview} aria-label="Overview" data-section="overview">
      <div className={styles.intro}>
        <div>
          <h2 className={styles.title}>Overview</h2>
        </div>
        <p className={styles.limit}>
          <Icon name="warning" size={16} />This system forecasts traffic. It does not control physical traffic signals.
        </p>
      </div>
      <a className={styles.videoAction} href="#analyze"><Icon name="film-strip" size={18} />Analyze a video<Icon name="arrow-right" size={16} /></a>
      <OperationsHeader id={id} sites={sites} heartbeat={heartbeat} sample={sample} alerts={alerts.current} />
      <ViewToggle view={view} onChange={onViewChange} />
      <StatusBanner health={health} cls={cls} count={count} heartbeat={heartbeat} sample={sample} />
      <section className={`${styles.card} ${styles.junction}`} aria-label="The intersection, next 60 seconds">
        <header className={styles.mapHead}>
          <h3>The intersection, next 60 seconds</h3>
        </header>
        <div className={styles.junctionLayout}>
          <JunctionMap snapshot={snapshot} approachNames={APPROACH_LABELS} selected={approach} onSelect={onApproachChange} />
          <ApproachDetail approach={approach} lane={snapshot.lanes[approach]} latestCounts={latestCounts}
                          heartbeat={heartbeat} classHistory={classHistory} />
        </div>
      </section>
      <div className={styles.tiles}>
        <Overview state={cls} count={count} edgeSilentFor={edgeSilentFor} />
        <Kpi label="Vehicles in view now" icon="car" result={vehiclesNow(latestCounts)} data-kpi="vehicles" />
      </div>
      <div className={styles.tiles3}>
        <Kpi label="Traffic signal" icon="signal" data-kpi="signal"
             result={{ value: null, text: "Not connected", sub: "Forecasts only. See Signal timing for the advisory split." }} />
        <Kpi label="Alerts" icon="warning" data-kpi="alerts"
             result={alerts.current.length ? { value: `${alerts.current.length} active`, sub: `Worst: ${SEV[worstSeverity(alerts.current)]}. See Alerts.` }
                                           : { value: null, text: "None active", sub: "No alert conditions in the live data" }} />
      </div>
      {view === "engineering" && <Diagnostics cls={cls} count={count} heartbeat={heartbeat} latestCounts={latestCounts}
                                             laneMap={laneMap} snapshot={snapshot} />}
      <div className={styles.cards}>
          <section className={styles.card} aria-label="Vehicles in view by class">
            <h3>Vehicle mix now</h3>
            <VehicleMix latestCounts={latestCounts} />
          </section>
          <section className={styles.card} aria-label="Recent activity">
            <h3>Recent activity</h3>
            <RecentActivity history={alerts.history} />
          </section>
      </div>
      <h3 className={styles.region}>Go to</h3>
      <nav className={styles.next} aria-label="Console sections">
        {NEXT.map(([key, icon, title, text]) => (
          <a key={key} href={`#${key}`} className={styles.nextCard}>
            <span className={styles.nextIcon}><Icon name={icon} size={20} /></span>
            <span className={styles.nextText}><strong>{title}</strong><span>{text}</span></span>
            <Icon name="arrow-right" size={16} />
          </a>
        ))}
      </nav>
    </section>
  );
}
