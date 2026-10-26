import styles from "./Panels.module.css";
import { APPROACHES, validateClass, validateCount, validateHistory } from "./validate.js";

const BUDGET_MS = 2000; // PRD: dashboard refresh within 2 s

// Panel states, in the order a response is judged:
//   loading -> unavailable (404) | error (unreachable, non-2xx, not JSON)
//   -> invalid (fails validation; reason shown, nothing partly shown)
//   -> ok, stale or fresh.
function Status({ state }) {
  if (state.status === "loading") return <p className={styles.note} data-state="loading">Waiting for the server…</p>;
  if (state.status === "unavailable")
    return <p className={styles.note} data-state="unavailable">Nothing published yet for this intersection.</p>;
  if (state.status === "error")
    return <p className={styles.problem} data-state="error">Unavailable: {state.reason}</p>;
  return null;
}

function Meta({ data }) {
  return (
    <dl className={styles.meta}>
      <dt>model</dt><dd className={styles.mono}>{data.model}</dd>
      <dt>role</dt><dd>{data.role}</dd>
      <dt>received</dt><dd>{new Date(data.at * 1000).toLocaleTimeString()}</dd>
      <dt>age</dt><dd>{data.age_s.toFixed(1)} s</dd>
    </dl>
  );
}

function Stale({ data }) {
  return data.stale ? (
    <p className={styles.stale} data-state="stale">
      Stale: older than its {data.horizon_sec ?? 60} s horizon. It describes a minute that has passed.
    </p>
  ) : null;
}

function Missing() {
  // Never 0 and never LOW: an approach without a forecast has no value at all.
  return <span className={styles.missing} data-missing="true">no forecast</span>;
}

export function CountPanel({ state }) {
  const checked = state.status === "ok" ? validateCount(state.data) : null;
  return (
    <section className={`${styles.panel} ${styles.count}`} aria-label="Next-minute vehicle count">
      <header className={styles.head}>
        <h2>Next-minute vehicle count</h2>
        <span className={styles.badge}>ridge · point estimate</span>
      </header>
      <Status state={state} />
      {checked && !checked.ok && (
        <p className={styles.problem} data-state="invalid">Invalid response, not shown: {checked.reason}</p>
      )}
      {checked?.ok && (
        <div className={checked.data.stale ? styles.dim : undefined}>
          <Stale data={checked.data} />
          <ul className={styles.lanes}>
            {APPROACHES.map((a) => (
              <li key={a} data-approach={a}>
                <span className={styles.approach}>{a}</span>
                {a in checked.data.counts ? (
                  <span className={styles.value}>
                    {checked.data.counts[a].toFixed(1)} <small>vehicles, 60 s mean</small>
                  </span>
                ) : <Missing />}
              </li>
            ))}
          </ul>
          <Meta data={checked.data} />
          <p className={styles.note}>A forecast, not a measurement, and not a congestion class.</p>
        </div>
      )}
    </section>
  );
}

export function ClassPanel({ state }) {
  const checked = state.status === "ok" ? validateClass(state.data) : null;
  return (
    <section className={`${styles.panel} ${styles.cls}`} aria-label="Congestion class">
      <header className={styles.head}>
        <h2>Congestion class, next 60 s</h2>
        <span className={styles.badge}>persistence</span>
      </header>
      <Status state={state} />
      {checked && !checked.ok && (
        <p className={styles.problem} data-state="invalid">Invalid response, not shown: {checked.reason}</p>
      )}
      {checked?.ok && (
        <div className={checked.data.stale ? styles.dim : undefined}>
          <Stale data={checked.data} />
          <ul className={styles.lanes}>
            {APPROACHES.map((a) => (
              <li key={a} data-approach={a}>
                <span className={styles.approach}>{a}</span>
                {a in checked.data.predictions ? (
                  <span className={`${styles.chip} ${styles[checked.data.predictions[a]]}`}>
                    {checked.data.predictions[a]}
                  </span>
                ) : <Missing />}
              </li>
            ))}
          </ul>
          <Meta data={checked.data} />
        </div>
      )}
    </section>
  );
}

// One forecast stream, judged by the same rules as its own panel. Its age is
// the server's clock, so a stream going stale is how a stopped edge, broker
// or ingest shows here: the server does not report those itself.
function stream(state, validate) {
  if (state.status === "loading") return { kind: "loading", text: "waiting for the server" };
  if (state.status === "unavailable") return { kind: "none", text: "nothing published yet" };
  if (state.status === "error") return { kind: "bad", text: `unavailable: ${state.reason}` };
  const checked = validate(state.data);
  if (!checked.ok) return { kind: "bad", text: `invalid response: ${checked.reason}` };
  const age = `${checked.data.age_s.toFixed(1)} s old`;
  return checked.data.stale ? { kind: "stale", text: `stale, ${age}` } : { kind: "fresh", text: `fresh, ${age}` };
}

export function StatusPanel({ health, cls, count }) {
  const server =
    health.status === "loading" ? { kind: "loading", text: "checking" }
      : health.status !== "ok" ? { kind: "bad", text: `unreachable: ${health.reason ?? "no health endpoint"}` }
        : health.data?.status !== "ok" ? { kind: "bad", text: "reachable, but did not report ok" }
          : { kind: "fresh", text: "reachable, reports ok" };
  const rows = [
    ["Server", server],
    ["Class forecast stream", stream(cls, validateClass)],
    ["Count forecast stream", stream(count, validateCount)],
  ];
  const rtt = typeof health.rtt_ms === "number" ? health.rtt_ms : null;
  return (
    <section className={`${styles.panel} ${styles.status}`} aria-label="System status">
      <header className={styles.head}>
        <h2>System status</h2>
        <span className={styles.badge}>live · read-only</span>
      </header>
      <ul className={styles.checks}>
        {rows.map(([name, s]) => (
          <li key={name} data-check={name} data-kind={s.kind}>
            <span className={`${styles.dot} ${styles[`k_${s.kind}`]}`} aria-hidden="true" />
            <span>{name}</span>
            <span className={styles.checkText}>{s.text}</span>
          </li>
        ))}
      </ul>
      {rtt !== null && (
        <p className={styles.note} data-rtt={rtt}>
          Server round trip <span className={styles.mono}>{rtt} ms</span>, measured by this browser
          on the last health check{rtt > BUDGET_MS ? ", over the 2 s refresh budget" : ""}.
        </p>
      )}
      <p className={styles.note}>
        The server does not report the broker, the ingest or the edge. A stream going stale is how
        a stopped one shows here. No edge-to-server delay is recorded live; measured latency is in
        the committed benchmarks, not on this page.
      </p>
    </section>
  );
}

function HistoryTable({ title, state, kind }) {
  const checked = state.status === "ok" ? validateHistory(state.data, kind) : null;
  const field = kind === "count" ? "counts" : "predictions";
  return (
    <div className={styles.history} data-history={kind}>
      <h3>{title}</h3>
      <Status state={state} />
      {checked && !checked.ok && (
        <p className={styles.problem} data-state="invalid">Invalid response, not shown: {checked.reason}</p>
      )}
      {checked?.ok && checked.data.rows.length === 0 && (
        <p className={styles.note} data-state="empty">Nothing recorded yet.</p>
      )}
      {checked?.ok && checked.data.rows.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr><th scope="col">received</th>{APPROACHES.map((a) => <th key={a} scope="col">{a}</th>)}<th scope="col">model</th></tr>
          </thead>
          <tbody>
            {checked.data.rows.map((row) => (
              <tr key={`${row.at}-${row.model}`}>
                <td className={styles.mono}>{new Date(row.at * 1000).toLocaleTimeString()}</td>
                {APPROACHES.map((a) => (
                  <td key={a} data-cell={a}>
                    {!(a in row[field]) ? <Missing />
                      : kind === "count" ? <span className={styles.mono}>{row[field][a].toFixed(1)}</span>
                        : <span className={`${styles.chip} ${styles[row[field][a]]}`}>{row[field][a]}</span>}
                  </td>
                ))}
                <td className={`${styles.mono} ${styles.small}`}>{row.model.split("@")[0]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function HistoryPanel({ classHistory, countHistory }) {
  return (
    <section className={`${styles.panel} ${styles.historyPanel}`} aria-label="Forecast history">
      <header className={styles.head}>
        <h2>Forecast history</h2>
        <span className={styles.badge}>recorded by this server · newest first</span>
      </header>
      <p className={styles.note}>
        What was published, not whether it was right: no accuracy is shown, because a live score
        against the detector's own counts would be circular (ADR-014).
      </p>
      <HistoryTable title="Congestion class, next 60 s" state={classHistory} kind="class" />
      <HistoryTable title="Next-minute vehicle count (ridge)" state={countHistory} kind="count" />
    </section>
  );
}

export function EvidencePanel({ state }) {
  return (
    <section className={`${styles.panel} ${styles.evidence}`} aria-label="Evaluation evidence">
      <header className={styles.head}>
        <h2>Evaluation evidence</h2>
        <span className={styles.badge}>historical · frozen</span>
      </header>
      <Status state={state} />
      {state.status === "ok" && (
        <>
          <p className={styles.label}>{state.data.label}</p>
          {state.data.studies.map((s) => (
            <article key={s.id} className={styles.study} data-study={s.id}>
              <h3>{s.id}: {s.question}</h3>
              <p className={styles.note}>
                {s.role} · {s.scope.windows} windows in {s.scope.blocks} ten-minute blocks · cameras{" "}
                {s.scope.cameras.join(", ")}
                {s.scope.excluded_cameras?.length ? ` · excluded ${s.scope.excluded_cameras.join(", ")}` : ""}
              </p>
              <div className={styles.rows} role="table" aria-label={`${s.id} results`}>
                <div className={styles.rowHead} role="row">
                  <span role="columnheader">metric</span><span role="columnheader">values</span>
                  <span role="columnheader">difference [95% CI]</span><span role="columnheader">verdict</span>
                </div>
                {s.rows.map((r) => (
                  <div key={r.metric} className={styles.row} role="row">
                    <span role="cell" data-label="metric">{r.metric}{r.lower_is_better ? " (lower is better)" : ""}</span>
                    <span role="cell" data-label="values" className={styles.mono}>
                      {Object.entries(r.values).map(([k, v]) => `${k} ${v}`).join(" · ")}
                    </span>
                    <span role="cell" data-label="difference" className={styles.mono}>
                      {r.difference_of}: {r.difference > 0 ? "+" : ""}{r.difference} [{r.ci95[0]}, {r.ci95[1]}]
                      <small className={styles.favours}>positive favours {r.positive_favours}</small>
                    </span>
                    <span role="cell" data-label="verdict" data-verdict={r.significant ? "significant" : "not significant"}>
                      {r.significant ? "significant" : "not significant"}
                    </span>
                  </div>
                ))}
              </div>
              <p className={styles.source}>
                source <span className={styles.mono}>{s.file}</span> · commit{" "}
                <span className={styles.mono}>{s.commit}</span> · {s.date}
              </p>
            </article>
          ))}
          <ul className={styles.limits}>
            {state.data.limitations.map((l) => <li key={l}>{l}</li>)}
          </ul>
        </>
      )}
    </section>
  );
}
