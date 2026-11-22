import { useState } from "react";
import { Icon } from "./icons.jsx";
import { advisorySplit, CLASS_LABELS, classTotals, detectorFps, downloadText, edgeState, failSafe, modelIds,
  safetyLimits, SEVERITY_ORDER, splitExplanation, toCsv, worstSeverity } from "./ops.js";
import styles from "./OpsPages.module.css";
import { operatorStatus } from "./Panels.jsx";
import { sourceStatus } from "./Source.jsx";
import { validateClass, validateCount, validateSites } from "./validate.js";

// Three console pages around the forecasts: Signal timing (advisory only),
// Alerts and System. Every value is read from a poll App already makes. What the
// system does not measure or report is listed as such, never filled in: no
// signal state reaches this system (P97a), and the server reports no CPU, memory
// or uptime figures.

const NOT = (what) => <span className={styles.not}>{what}</span>;

function Card({ title, sub, children, ...rest }) {
  return (
    <section className={styles.card} {...rest}>
      <header className={styles.cardHead}><h3>{title}</h3>{sub && <span>{sub}</span>}</header>
      {children}
    </section>
  );
}

function Field({ label, children }) {
  return <div className={styles.field}><dt>{label}</dt><dd>{children}</dd></div>;
}

export function PageHead({ title, lead, children }) {
  return (
    <header className={styles.pageHead}>
      <div><h2>{title}</h2>{lead && <p>{lead}</p>}</div>
      {children && <div className={styles.actions}>{children}</div>}
    </header>
  );
}

// ------------------------------------------------------------------ signal timing

const ALL_RED = 2; // an all-red clearance after each of the two greens

export function greenTimes(split, cycle, limits) {
  if (!split || !limits) return null;
  const lost = ALL_RED * limits.all_red_s;
  const available = Math.max(cycle - lost, 0);
  return split.map((s) => {
    const raw = available * s.share;
    const green = Math.min(Math.max(raw, limits.min_green_s), limits.max_green_s);
    return { ...s, raw, green, clamped: green !== raw };
  });
}

function Head({ label }) {
  return (
    <div className={styles.head} aria-label={`${label} signal: state not reported`}>
      <i /><i /><i /><b>?</b><span>{label}</span>
    </div>
  );
}

export function SignalTiming({ health, count, heartbeat }) {
  const [cycle, setCycle] = useState(90);
  const limits = safetyLimits(health);
  const split = advisorySplit(count);
  const greens = greenTimes(split, cycle, limits);
  const safe = failSafe(heartbeat, limits);
  return (
    <section className={styles.page} aria-label="Signal timing" data-section="signals">
      <PageHead title="Signal timing" lead="What the current forecast would suggest for green time, and the safety rules any controller must keep. Advisory only." />
      <p className={styles.banner} data-advisory="true">
        <Icon name="warning" size={18} />
        <span><b>No traffic signal is controlled by this system.</b> No forecast is connected to signal timing (P97a), and no signal state is reported here,
          so the signal heads below show <b>?</b>. Every number on this page is a calculation from the vehicle forecast.</span>
      </p>

      <div className={styles.grid2}>
        <Card title="Signal state" sub="Not reported by any signal">
          <div className={styles.heads}><Head label="N–S" /><Head label="E–W" /></div>
          <dl className={styles.fields}>
            <Field label="Current phase">{NOT("Not reported")}</Field>
            <Field label="Next phase">{NOT("Not reported")}</Field>
            <Field label="Remaining green">{NOT("Not reported")}</Field>
            <Field label="Manual override">{NOT("Not available: this page is read-only by design")}</Field>
          </dl>
        </Card>

        <Card title="Fail-safe" sub="FR-A06" data-failsafe={safe.kind}>
          <p className={styles.state} data-kind={safe.kind}><i />{safe.kind === "normal" ? "Link normal" : safe.kind === "fallback" ? "Edge on local fallback" : "Unknown"}</p>
          <p className={styles.text}>{safe.text}</p>
          <p className={styles.muted}>Rule: if the edge hears nothing for {safe.timeout} s, it switches to its own fixed (Webster) cycle. If a forecast is missing, old (over 10 s) or invalid, a forecast-aware policy may not use it (ADR-020).</p>
        </Card>
      </div>

      <Card title="Demand-based green split" sub="From the next-minute vehicle forecast" data-split={split ? "ok" : "none"}>
        {split ? (
          <>
            <div className={styles.split} aria-label="Share of expected vehicles per axis">
              {split.map((s) => <i key={s.axis} style={{ flexGrow: Math.max(s.share, 0.02) }}><b>{s.axis}</b><span>{Math.round(s.share * 100)}%</span></i>)}
            </div>
            <p className={styles.text}>{splitExplanation(split)}</p>
            <label className={styles.slider}>
              <span>Example cycle length: <b className={styles.mono}>{cycle} s</b></span>
              <input type="range" min="40" max="150" step="5" value={cycle} onChange={(e) => setCycle(Number(e.target.value))} />
            </label>
            {greens ? (
              <table className={styles.table}>
                <thead><tr><th>Axis</th><th>Expected vehicles</th><th>Share</th><th>Green in a {cycle} s cycle</th></tr></thead>
                <tbody>
                  {greens.map((g) => (
                    <tr key={g.axis}>
                      <th>{g.axis}</th><td className={styles.mono}>{g.demand.toFixed(1)}</td><td className={styles.mono}>{Math.round(g.share * 100)}%</td>
                      <td className={styles.mono}>{g.green.toFixed(0)} s{g.clamped && <small> (held to the {g.green === limits.min_green_s ? "minimum" : "maximum"})</small>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p className={styles.muted}>Green times need the server's safety limits, which it has not reported.</p>}
            <p className={styles.muted}>
              Two all-red clearances of {limits?.all_red_s ?? "—"} s are taken from the cycle first, and each green is held between the minimum and maximum below.
              This is an illustration of demand, not a tested timing plan, and it reaches no signal.
            </p>
          </>
        ) : <p className={styles.empty}>No split: it needs a current vehicle forecast for all four approaches, with some traffic expected.</p>}
      </Card>

      <div className={styles.grid2}>
        <Card title="Safety limits" sub="server/safety.py, as the server reports them">
          {limits ? (
            <dl className={styles.fields}>
              <Field label="Minimum green"><span className={styles.mono}>{limits.min_green_s} s</span></Field>
              <Field label="Maximum green"><span className={styles.mono}>{limits.max_green_s} s</span></Field>
              <Field label="All-red clearance"><span className={styles.mono}>{limits.all_red_s} s</span></Field>
              <Field label="Emergency response"><span className={styles.mono}>{limits.emergency_response_s} s</span></Field>
              <Field label="Link timeout (fail-safe)"><span className={styles.mono}>{limits.mqtt_timeout_s} s</span></Field>
              <Field label="Yellow interval">{NOT("Not specified by the safety module")}</Field>
            </dl>
          ) : <p className={styles.empty}>The server has not reported its limits.</p>}
        </Card>
        <Card title="Switching history" sub="What signals did">
          <p className={styles.empty}>No switching history: no signal is controlled or observed by this system.</p>
          <p className={styles.muted}>Signal control was studied in a traffic simulator (SUMO), comparing PPO with Webster timing. That study is historical evidence and is on the <a href="#results">Results</a> page.</p>
        </Card>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ alerts

const SEV_LABEL = { critical: "Critical", serious: "Serious", warning: "Warning", info: "Info" };

function Severity({ level }) {
  return <span className={styles.sev} data-severity={level}><i />{SEV_LABEL[level]}</span>;
}

export function ApproachAlertLinks({ approaches }) {
  return approaches?.length > 0 && (
    <div className={styles.approachLinks}>
      {approaches.map((approach) => <a key={approach} href={`#overview/${approach}`}>Inspect approach {approach}</a>)}
    </div>
  );
}

export function AlertsPage({ alerts }) {
  const { current, history, clear } = alerts;
  const sorted = [...current].sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));
  const exportCsv = () => downloadText(`stms-alerts-${new Date().toISOString().slice(0, 10)}.csv`,
    toCsv(["time", "kind", "severity", "title", "detail"], history.map((e) => ({ ...e, time: new Date(e.at).toISOString() }))));
  return (
    <section className={styles.page} aria-label="Alerts" data-section="alerts">
      <PageHead title="Alerts" lead="Conditions this page can see in the live data, and a log of when they started and cleared.">
        <button type="button" className={styles.button} onClick={exportCsv} disabled={!history.length}><Icon name="code" size={16} />Export CSV</button>
      </PageHead>

      <Card title="Active now" sub={current.length ? `${current.length} active · worst: ${SEV_LABEL[worstSeverity(current)]}` : "None"} data-alerts-active={current.length}>
        {sorted.length ? (
          <ul className={styles.alerts}>
            {sorted.map((a) => (
              <li key={a.key} data-alert={a.key}><Severity level={a.severity} /><div><b>{a.title}</b><p>{a.detail}</p>
                <ApproachAlertLinks approaches={a.approaches} /></div></li>
            ))}
          </ul>
        ) : <p className={styles.empty}><Icon name="check-circle" size={18} />No alert conditions in the live data right now.</p>}
      </Card>

      <Card title="Alert history" sub="This browser session · times are this computer's clock">
        {history.length ? (
          <>
            <table className={styles.table}>
              <thead><tr><th>Time</th><th>Severity</th><th>Event</th><th>Detail</th></tr></thead>
              <tbody>
                {[...history].reverse().map((e, i) => (
                  <tr key={`${e.at}-${e.key}-${i}`} data-event={e.kind}>
                    <td className={styles.mono}>{new Date(e.at).toLocaleTimeString()}</td>
                    <td><Severity level={e.severity} /></td><td>{e.title}</td><td className={styles.muted}>{e.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button type="button" className={styles.linkButton} onClick={clear}>Clear history</button>
          </>
        ) : <p className={styles.empty}>Nothing has started or cleared since this page opened.</p>}
      </Card>

      <Card title="What is not watched" sub="The system does not measure these">
        <ul className={styles.notList}>
          <li>Queue length: the camera path has no stop line or speed.</li>
          <li>Emergency vehicles: the detector is not trained or validated for them.</li>
          <li>Signal errors: no signal state reaches this system.</li>
        </ul>
      </Card>
    </section>
  );
}

// ------------------------------------------------------------------ system

const STATE_WORD = { ok: "Healthy", stale: "Out of date", bad: "Problem", none: "Waiting", loading: "Checking" };

export function SystemPage({ health, cls, count, heartbeat, latestCounts, sites }) {
  const status = operatorStatus({ health, cls, count, heartbeat });
  const edge = edgeState(heartbeat);
  const source = sourceStatus(heartbeat);
  const fps = detectorFps(latestCounts);
  const models = modelIds(cls, count);
  const rtt = health.status === "ok" && typeof health.rtt_ms === "number" ? health.rtt_ms : null;
  const stream = (state, validate) => {
    if (state.status === "loading") return ["none", "Checking"];
    if (state.status === "unavailable") return ["none", "Nothing published yet"];
    if (state.status === "error") return ["bad", state.reason];
    const v = validate(state.data);
    if (!v.ok) return ["bad", `Refused: ${v.reason}`];
    return v.data.stale ? ["stale", `Out of date, ${v.data.age_s.toFixed(0)} s old`] : ["ok", `Current, ${v.data.age_s.toFixed(0)} s old`];
  };
  const level = stream(cls, validateClass), vehicles = stream(count, validateCount);
  const siteList = sites.status === "ok" ? validateSites(sites.data) : null;
  const tiles = [
    ["Server", health.status === "ok" && health.data?.status === "ok" ? "ok" : health.status === "loading" ? "none" : "bad",
      health.status === "ok" ? (health.data?.status === "ok" ? "Reachable" : "Reports a problem") : health.status === "loading" ? "Checking" : "Unreachable",
      rtt !== null ? `Round trip ${rtt} ms from this browser` : health.reason],
    ["Camera unit (edge)", !edge ? "none" : edge.stale ? "stale" : "ok", !edge ? "No heartbeat" : edge.stale ? "Silent" : "Reporting",
      edge ? `Last heard ${edge.age.toFixed(0)} s ago${edge.status ? ` · reports "${edge.status}"` : ""}${edge.mode ? ` · mode ${edge.mode}` : ""}` : "Nothing reported yet"],
    ["Detector (YOLO)", fps ? "ok" : "none", fps ? `${fps.fps.toFixed(2)} fps` : "No current rate",
      fps ? `One frame every ${fps.frameEvery?.toFixed(1) ?? "—"} s, as the edge reports it` : "Reported with each lane's counts"],
    ["Level forecast", level[0], level[0] === "ok" ? "Current" : STATE_WORD[level[0]], `${level[1]}${models.level ? ` · ${models.level}` : ""}`],
    ["Vehicle forecast", vehicles[0], vehicles[0] === "ok" ? "Current" : STATE_WORD[vehicles[0]], `${vehicles[1]}${models.number ? ` · ${models.number}` : ""}`],
    ["Data source", source.kind === "camera" || source.kind === "replay" ? "ok" : source.kind === "stale" ? "stale" : source.kind === "bad" ? "bad" : "none", source.title, source.detail],
  ];
  return (
    <section className={styles.page} aria-label="System" data-section="system">
      <PageHead title="System health" lead="Each part of the pipeline, from what it last reported. Refreshed every 2 seconds." />
      <p className={styles.overall} data-kind={status.kind}><i />{status.head}<span>{status.sub}</span></p>
      <div className={styles.health}>
        {tiles.map(([name, kind, word, detail]) => (
          <section key={name} className={styles.hcard} data-kind={kind} data-health={name}>
            <p className={styles.hname}>{name}</p>
            <p className={styles.hword}><i />{word}</p>
            <p className={styles.muted}>{detail}</p>
          </section>
        ))}
      </div>
      <div className={styles.grid2}>
        <Card title="Intersections reporting" sub="GET /sites">
          {siteList?.ok && siteList.data.sites.length ? (
            <table className={styles.table}>
              <thead><tr><th>Intersection</th><th>Source</th><th>Last heard</th></tr></thead>
              <tbody>{siteList.data.sites.map((s) => (
                <tr key={s.id}><th className={styles.mono}>{s.id}</th><td>{s.kind ?? "unknown"}{s.label ? ` · ${s.label}` : ""}</td>
                  <td className={styles.mono}>{s.age_s.toFixed(0)} s{s.stale ? " (out of date)" : ""}</td></tr>
              ))}</tbody>
            </table>
          ) : <p className={styles.empty}>No intersection has reported yet.</p>}
        </Card>
        <Card title="Not reported" sub="The server does not measure these">
          <ul className={styles.notList}>
            <li>CPU, memory and GPU use</li>
            <li>Server uptime</li>
            <li>Per-frame processing time on the edge</li>
            <li>Error logs (they are in the server's and edge's own console output)</li>
          </ul>
        </Card>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ overview extras

export function VehicleMix({ latestCounts }) {
  const mix = classTotals(latestCounts);
  if (!mix) return <p className={styles.empty}>No current counts to break down.</p>;
  const rows = Object.entries(mix.totals).sort((a, b) => b[1] - a[1]);
  const top = Math.max(1, ...rows.map(([, n]) => n));
  return (
    <ul className={styles.mix} aria-label="Vehicles in view by class">
      {rows.map(([cls, n]) => (
        <li key={cls}><span>{CLASS_LABELS[cls] ?? cls}</span><i style={{ width: `${(n / top) * 100}%` }} /><b className={styles.mono}>{n}</b></li>
      ))}
    </ul>
  );
}

export function RecentActivity({ history }) {
  const recent = [...history].reverse().slice(0, 6);
  if (!recent.length) return <p className={styles.empty}>No changes since this page opened.</p>;
  return (
    <ul className={styles.activity}>
      {recent.map((e, i) => (
        <li key={`${e.at}-${e.key}-${i}`}><Severity level={e.severity} /><span>{e.title}</span><time className={styles.mono}>{new Date(e.at).toLocaleTimeString()}</time></li>
      ))}
    </ul>
  );
}

export { Severity };
