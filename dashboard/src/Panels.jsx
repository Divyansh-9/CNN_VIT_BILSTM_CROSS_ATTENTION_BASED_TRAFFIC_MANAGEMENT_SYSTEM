import styles from "./Panels.module.css";
import { APPROACHES, validateClass, validateCount } from "./validate.js";

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
