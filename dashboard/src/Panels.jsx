import styles from "./Panels.module.css";
import { APPROACHES, CLASSES, validateClass, validateCount, validateCountHistory, validateHeartbeat, validateHistory, validateSites } from "./validate.js";

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

// Rendered above the data, never inside it: the warning keeps full contrast
// while the stale values below it change style (UX step 1b).
function Stale({ data }) {
  return data.stale ? (
    <p className={styles.stale} data-state="stale">
      <span className={styles.staleMark} aria-hidden="true" />
      <span>
        <b>Stale, {data.age_s.toFixed(0)} s old.</b> Past its {data.horizon_sec ?? 60} s horizon,
        so it describes a minute that has passed.
      </span>
    </p>
  ) : null;
}

// Stale values stay readable; they turn muted and class chips become outlines,
// so nothing old looks current and nothing is hidden.
function freshness(data) {
  return { className: data.stale ? styles.staled : undefined, "data-freshness": data.stale ? "stale" : "fresh" };
}

function Missing({ children = "no forecast" }) {
  // Never 0 and never LOW: an approach without a forecast has no value at all.
  return <span className={styles.missing} data-missing="true">{children}</span>;
}

const WORST_FIRST = [...CLASSES].reverse();

// "Approach N", not "North": the letters are labels until a camera's directions are verified (ADR-028).
function named(approaches) {
  const list = approaches.map((a) => `Approach ${a}`);
  return list.length < 2 ? list.join("") : `${list.slice(0, -1).join(", ")} and ${list.at(-1)}`;
}

function summary(predictions) {
  const known = APPROACHES.filter((a) => a in predictions);
  const missing = APPROACHES.filter((a) => !(a in predictions));
  const worst = WORST_FIRST.find((c) => known.some((a) => predictions[a] === c));
  const top = known.filter((a) => predictions[a] === worst);
  const where = top.length > 1 && top.length === known.length
    ? `all ${known.length}${missing.length ? " available" : ""} approaches` : named(top);
  const absent = missing.length
    ? `${named(missing)} ${missing.length === 1 ? "has" : "have"} no forecast. This does not mean ${missing.length === 1 ? "it is" : "they are"} empty.` : "";
  return { lead: `Highest congestion expected: ${where}`, worst, absent,
           list: known.map((a) => `${a} ${predictions[a]}`).join(", ") };
}

const NOT_EMPTY = "This does not mean the roads are empty.";

// The forecast's headline: how congested each approach is in the next 60 s.
// Built only from a current, valid class forecast (reviewer rule 2), so a
// stale, refused, missing or unreachable forecast never produces a class word
// in the headline: nothing old reads as current, and nothing unknown reads as
// "no congestion".
export function overview(state) {
  if (state.status === "loading") return { kind: "loading", headline: "Waiting for the first forecast", detail: "" };
  if (state.status === "unavailable")
    return { kind: "none", headline: "No forecast published yet", detail: `Nothing has been published for this intersection. ${NOT_EMPTY}` };
  if (state.status === "error") return { kind: "bad", headline: "Forecasts unavailable", detail: `No forecast is available. ${NOT_EMPTY}` };
  const checked = validateClass(state.data);
  if (!checked.ok)
    return { kind: "bad", headline: "Forecast refused", detail: `It failed validation, so it is not shown. ${NOT_EMPTY}` };
  const { predictions, stale, age_s } = checked.data;
  const s = summary(predictions);
  if (stale)
    return { kind: "stale", headline: "No current forecast",
             detail: `The last one is ${age_s.toFixed(0)} s old and describes a minute that has passed. It read: ${s.list}.` };
  return { kind: "fresh", lead: s.lead, worst: s.worst, headline: `${s.lead} ${s.worst}`, detail: s.absent };
}

const OVERVIEW_MARK = { stale: styles.k_stale, bad: styles.k_bad, none: styles.k_none, loading: styles.k_loading };

// D23: `edgeSilentFor` is the age of a valid, stale heartbeat, else null. A
// forecast inside its horizon stays valid when the edge stops, so it is still
// shown; the label says it is the last one, and the status banner says why.
export function Overview({ state, edgeSilentFor = null }) {
  const o = overview(state);
  const last = o.kind === "fresh" && edgeSilentFor !== null;
  return (
    <section className={styles.overview} aria-label="Next 60 seconds" data-overview={o.kind}>
      <p className={styles.overviewLabel} data-edge-silent={last ? "true" : undefined}>
        {last ? "Last forecast received, next 60 seconds" : "Next 60 seconds"}
      </p>
      <p className={styles.overviewHead} aria-live="polite">
        {o.kind === "fresh"
          ? <>{o.lead} <span className={`${styles.chip} ${styles[o.worst]}`}>{o.worst}</span></>
          : <><span className={`${styles.dot} ${OVERVIEW_MARK[o.kind]}`} aria-hidden="true" />{o.headline}</>}
      </p>
      {o.detail && <p className={styles.overviewDetail}>{o.detail}</p>}
    </section>
  );
}

// The page's first answer: is anything arriving, and how old is what is shown.
// Worked out only from what the page already polls, in the order a problem
// hides the next one. It claims "arriving" only from a fresh heartbeat: a
// forecast stays valid for 60 s after the edge stops, so a current forecast
// alone does not show that another is coming.
export function operatorStatus({ health, cls, count, heartbeat = { status: "unavailable" } }) {
  if (health.status === "loading") return { kind: "loading", head: "Checking for updates", sub: "Waiting for the server." };
  if (health.status !== "ok")
    return { kind: "bad", head: "Cannot reach the server", sub: "This page is not receiving anything, so it cannot say what the system or the roads are doing." };
  if (health.data?.status !== "ok")
    return { kind: "bad", head: "The server reports a problem", sub: "It answered, but did not report that it is working. Forecasts below may not be current." };
  if (cls.status === "loading" || count.status === "loading") return { kind: "loading", head: "Checking for updates", sub: "Waiting for the first forecast." };
  const read = (state, validate) => (state.status === "ok" ? validate(state.data) : null);
  const streams = [["congestion level", cls, read(cls, validateClass)], ["vehicle number", count, read(count, validateCount)]];
  if (streams.some(([, state, checked]) => state.status === "error" || (checked && !checked.ok)))
    return { kind: "bad", head: "A forecast cannot be shown", sub: "It could not be read or failed validation. The reason is in the technical details." };
  const present = streams.filter(([, , checked]) => checked).map(([name, , checked]) => ({ name, ...checked.data }));
  if (present.length === 0)
    return { kind: "none", head: "No forecast yet", sub: "The server is reachable, but nothing has been published for this intersection." };
  const old = present.filter((p) => p.stale);
  const age = Math.max(...(old.length ? old : present).map((p) => p.age_s));
  if (old.length === present.length)
    return { kind: "stale", head: "No recent updates", sub: `Last updated ${age.toFixed(0)} s ago. The forecast below describes a minute that has passed.` };
  if (old.length)
    return { kind: "stale", head: `The ${old[0].name} forecast is out of date`, sub: `It is ${age.toFixed(0)} s old and describes a minute that has passed. The other forecast is still current.` };
  if (present.length === 1)
    return { kind: "none", head: `Only the ${present[0].name} forecast is arriving`, sub: `Nothing has been published for the other one yet. The level starts after 1 minute of counts and the vehicle number after 2.` };
  const left = `valid for ${Math.max((present[1].horizon_sec ?? 60) - age, 0).toFixed(0)} s more.`;
  const beat = read(heartbeat, validateHeartbeat);
  if (beat?.ok && beat.data.stale)
    return { kind: "stale", head: "The edge unit has stopped reporting", sub: `Last heard from ${beat.data.age_s.toFixed(0)} s ago. This is its last forecast, ${left} No new forecast is being made.` };
  const live = Boolean(beat?.ok);
  const lead = !live ? "A current forecast is available"
    : beat.data.source?.kind === "replay" ? "Updates are arriving from a recording" : "Updates are arriving";
  const missing = APPROACHES.filter((a) => !(a in present[0].predictions) || !(a in present[1].counts));
  const without = missing.length ? `, with approach${missing.length > 1 ? "es" : ""} ${missing.join(", ")} missing` : "";
  return { kind: "ok", head: `${lead}${without}`,
           sub: `Last updated ${age.toFixed(0)} s ago. This forecast is ${left}${live ? "" : " The edge unit is not reporting its status, so more updates may not follow."}` };
}

const BANNER_MARK = { ok: styles.k_fresh, stale: styles.k_stale, bad: styles.k_bad, none: styles.k_none, loading: styles.k_loading };

export function StatusBanner(props) {
  const s = operatorStatus(props);
  // Only the headline is announced: the line below it changes every 2 s with the age.
  return (
    <section className={styles.banner} aria-label="Are updates arriving" data-status={s.kind}>
      <span className={`${styles.dot} ${styles.bannerMark} ${BANNER_MARK[s.kind]}`} aria-hidden="true" />
      <h2 aria-live="polite">{s.head}</h2>
      <p>{s.sub}</p>
    </section>
  );
}

function forecastCell(state, checked, a, field, show) {
  if (state.status === "loading") return <Missing>waiting</Missing>;
  if (state.status === "unavailable") return <Missing />;
  if (!checked?.ok) return <Missing>no data</Missing>;
  return a in checked.data[field] ? show(checked.data[field][a]) : <Missing />;
}

const RECENT_S = 900; // the table's counted column: the last 15 minutes

// D33: what was counted, per approach, from the same read-only history Analytics
// uses. Only a lane the edge has mapped can be named, and a bucket with no
// samples stays absent, so a gap is drawn as a break and never as zero.
export function recentCounts(state, lanes) {
  if (state?.status !== "ok" || !lanes) return null;
  const checked = validateCountHistory(state.data, "1h");
  if (!checked.ok) return null;
  const { buckets, end, bucket_s: step } = checked.data;
  const out = {};
  for (const [lane, approach] of Object.entries(lanes)) {
    out[approach] = buckets.filter((b) => b.t + step > end - RECENT_S)
      .map((b) => ({ t: b.t, mean: b.lanes[lane]?.mean ?? null }));
  }
  return out;
}

function Sparkline({ points }) {
  const W = 100, H = 26;
  const top = Math.max(4, ...points.map((p) => p.mean ?? 0));
  const x = (i) => 3 + (i / Math.max(points.length - 1, 1)) * (W - 6), y = (v) => H - 3 - (v / top) * (H - 6);
  let d = "", open = false;
  points.forEach((p, i) => {
    if (p.mean === null) { open = false; return; }
    d += `${open ? "L" : "M"}${x(i).toFixed(1)},${y(p.mean).toFixed(1)} `;
    open = true;
  });
  const lastIndex = points.findLastIndex((p) => p.mean !== null);
  return (
    <svg className={styles.spark} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Counted over the last 15 minutes, latest ${points[lastIndex].mean.toFixed(1)}`}>
      <path d={d} />
      <circle cx={x(lastIndex)} cy={y(points[lastIndex].mean)} r="2.5" />
    </svg>
  );
}

function CountedCell({ points }) {
  if (!points?.some((p) => p.mean !== null)) return <Missing>no counts</Missing>;
  const last = points.findLast((p) => p.mean !== null).mean;
  return <span className={styles.counted}><Sparkline points={points} /><span className={styles.mono}>{last.toFixed(1)}</span></span>;
}

// The table's fourth column appears only when the page hands it the counted history.
export function ForecastTable({ cls, count, recent, lanes }) {
  const history = recent ? recentCounts(recent, lanes) : null;
  const c = cls.status === "ok" ? validateClass(cls.data) : null;
  const k = count.status === "ok" ? validateCount(count.data) : null;
  return (
    <table className={styles.forecast} data-forecast-table="true">
      <thead>
        <tr><th scope="col">Approach</th><th scope="col">Congestion level</th><th scope="col">Expected vehicles in view (60 s avg)</th>{recent && <th scope="col" className={styles.countedCol}>Counted, last 15 min</th>}</tr>
      </thead>
      <tbody>
        {APPROACHES.map((a) => (
          <tr key={a} data-forecast-row={a}>
            <th scope="row" className={styles.approach}>{a}</th>
            <td {...(c?.ok ? freshness(c.data) : {})}>
              {forecastCell(cls, c, a, "predictions", (v) => <span className={`${styles.chip} ${styles[v]}`}>{v}</span>)}
            </td>
            <td {...(k?.ok ? freshness(k.data) : {})}>
              {forecastCell(count, k, a, "counts", (v) => <span className={styles.value}>{v.toFixed(1)}</span>)}
            </td>
            {recent && <td className={styles.countedCol} data-counted={a}><CountedCell points={history?.[a]} /></td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// How the expected vehicles divide across approaches: current forecasts only,
// and nothing at all when none is expected, since a share of zero means nothing.
export function ExpectedShare({ state }) {
  const checked = state.status === "ok" ? validateCount(state.data) : null;
  if (!checked?.ok || checked.data.stale) return null;
  const known = APPROACHES.filter((a) => a in checked.data.counts);
  const total = known.reduce((t, a) => t + checked.data.counts[a], 0);
  if (total <= 0) return null;
  const pct = (a) => Math.round((checked.data.counts[a] / total) * 100);
  return (
    <div className={styles.share} data-share="true">
      <h3>Share of expected vehicles</h3>
      <div className={styles.shareBar} role="img" aria-label={known.map((a) => `${a} ${pct(a)}%`).join(", ")}>
        {known.map((a) => <i key={a} className={styles[`share${a}`]} style={{ flex: checked.data.counts[a] }} />)}
      </div>
      <div className={styles.shareKey}>
        {known.map((a) => <span key={a}><i className={styles[`share${a}`]} /><b>{a}</b> {pct(a)}%</span>)}
      </div>
    </div>
  );
}

// D34: what demand-proportional timing would give each pair of approaches, from
// the current count forecast. A calculation shown beside the forecast, and never
// the signal: the real signal's state does not reach this system, so the signal
// heads stay unknown, and nothing here goes anywhere. Needs all four approaches,
// because a missing one is not a zero (P97a).
const PAIRS = [["N", "S"], ["E", "W"]];

export function timingSuggestion(state) {
  const checked = state.status === "ok" ? validateCount(state.data) : null;
  if (!checked?.ok || checked.data.stale) return null;
  const { counts } = checked.data;
  if (!APPROACHES.every((a) => a in counts)) return null;
  const demand = PAIRS.map((pair) => pair.reduce((t, a) => t + counts[a], 0));
  const total = demand[0] + demand[1];
  if (total <= 0) return null;
  return PAIRS.map((pair, i) => ({ name: pair.join(" + "), share: Math.round((demand[i] / total) * 100) }));
}

export function TimingSuggestion({ state }) {
  const pairs = timingSuggestion(state);
  return (
    <section className={styles.whatIf} aria-label="If signals were timed from this forecast" data-what-if={pairs ? "shown" : "none"}>
      <h3>If signals were timed from this forecast</h3>
      <p className={styles.whatIfWarn}><b>Not the real signal.</b> The current signal colour is not known here, and this reaches no signal.</p>
      {pairs ? (
        <ul>
          {pairs.map(({ name, share }) => (
            <li key={name}>
              <b>{name}</b>
              <span className={styles.whatIfBar}><i style={{ width: `${share}%` }} /></span>
              <span className={styles.mono}>{share}% of green</span>
            </li>
          ))}
        </ul>
      ) : <p className={styles.note}>No suggestion: it needs a current forecast for all four approaches, with some traffic expected.</p>}
      <p className={styles.tileSub}>
        A simple share of the expected vehicles in view, for illustration. It is not a tested timing plan, and it
        pairs approaches by their labels, which may not be real directions.
      </p>
    </section>
  );
}

// D34: the intersections the server has heard from. A site appears only because
// its edge unit reported, so this never claims a camera that is not running.
export function SiteStrip({ state, current }) {
  const checked = state.status === "ok" ? validateSites(state.data) : null;
  // A heartbeat that names no source is a test message or an old edge, not a camera to show.
  const shown = checked?.ok ? checked.data.sites.filter((s) => s.kind !== null) : [];
  if (shown.length === 0) return null;
  return (
    <nav className={styles.sites} aria-label="Intersections" data-sites="true">
      {shown.map((s) => (
        <a key={s.id} href={`?id=${encodeURIComponent(s.id)}#live`} aria-current={s.id === current ? "true" : undefined} data-site={s.id}>
          <span className={`${styles.dot} ${s.stale ? styles.k_stale : styles.k_fresh}`} aria-hidden="true" />
          <b>{s.id}</b>
          <span className={styles.siteState}>{s.stale ? `Silent for ${s.age_s.toFixed(0)} s` : s.kind === "replay" ? `Replay · ${s.label}` : `Live camera · ${s.label}`}</span>
        </a>
      ))}
    </nav>
  );
}

function SignalStudy({ study }) {
  const top = Math.ceil(Math.max(...study.arms.map((a) => a.ci95[1])) / 10) * 10;
  const x = (v) => `${(v / top) * 100}%`;
  return (
    <article className={styles.study} data-signal-study={study.id}>
      <h3>{study.id}: {study.question}</h3>
      <p className={styles.note}>In a traffic simulator, not on a road · {study.metric}, lower is better · {study.seeds} seeds · squares are rule-based, circles are PPO</p>
      <div className={styles.plot}>
        {study.arms.map((arm) => (
          <div key={arm.name} className={styles.plotRow} data-arm={arm.kind}>
            <span>{arm.name}</span>
            <div className={styles.plotTrack} title={`${arm.name}: ${arm.mean} s [${arm.ci95[0]}, ${arm.ci95[1]}]`}>
              <i className={styles.plotCi} style={{ left: x(arm.ci95[0]), width: `${((arm.ci95[1] - arm.ci95[0]) / top) * 100}%` }} />
              <i className={arm.kind === "ppo" ? styles.plotPpo : styles.plotRule} style={{ left: x(arm.mean) }} />
            </div>
            <span className={styles.mono}>{arm.mean.toFixed(1)} [{arm.ci95[0].toFixed(1)}, {arm.ci95[1].toFixed(1)}]</span>
          </div>
        ))}
      </div>
      <p className={styles.label}>Reading: {study.reading}.</p>
      <ul className={styles.limits}>{study.qualifiers.map((q) => <li key={q}>{q}</li>)}</ul>
      <p className={styles.source}>source <span className={styles.mono}>{study.file}</span> · commit <span className={styles.mono}>{study.commit}</span> · {study.date}</p>
    </article>
  );
}

function Tile({ label, children, sub, ...rest }) {
  return (
    <section className={styles.tile} {...rest}>
      <p className={styles.tileLabel}>{label}</p>
      <div className={styles.tileValue}>{children}</div>
      {sub && <p className={styles.tileSub}>{sub}</p>}
    </section>
  );
}

// The summary tiles beside the headline. Each says when it cannot answer, in
// words, and none turns an unknown into a zero or an old forecast into a current one.
export function SummaryTiles({ cls, count }) {
  const c = cls.status === "ok" ? validateClass(cls.data) : null;
  const k = count.status === "ok" ? validateCount(count.data) : null;
  const down = cls.status === "error" || count.status === "error" || c?.ok === false || k?.ok === false;
  const waiting = cls.status === "loading" || count.status === "loading";
  const nothing = waiting ? "Waiting" : down ? "No data" : "No forecast";
  const fresh = k?.ok && !k.data.stale ? k.data.counts : null;
  const top = fresh ? Math.max(...Object.values(fresh)) : null;
  const busiest = fresh ? APPROACHES.filter((a) => fresh[a] === top) : [];
  const both = c?.ok && k?.ok ? APPROACHES.filter((a) => a in c.data.predictions && a in k.data.counts) : [];
  const lacking = APPROACHES.filter((a) => !both.includes(a));
  const stale = c?.ok && k?.ok && (c.data.stale || k.data.stale);
  const current = c?.ok && k?.ok && !stale;
  const horizon = k?.ok ? k.data.horizon_sec ?? 60 : 60;
  const left = current ? Math.max(horizon - Math.max(c.data.age_s, k.data.age_s), 0) : null;
  return (
    <>
      <Tile label="Busiest approach, next minute" data-tile="busiest"
            sub={fresh ? "vehicles in view on average" : undefined}>
        {fresh ? <>{named(busiest)} <span className={styles.mono}>{top.toFixed(1)}</span></>
          : <span className={styles.tileNone}>{k?.ok ? "Not current" : nothing}</span>}
      </Tile>
      <Tile label="Approaches reporting" data-tile="reporting"
            sub={c?.ok && k?.ok ? (lacking.length ? `${lacking.join(", ")} ${lacking.length > 1 ? "have" : "has"} no forecast` : stale ? "In the last forecast, now out of date" : "All have both forecasts") : undefined}>
        {c?.ok && k?.ok ? <span className={styles.mono}>{both.length} of 4</span> : <span className={styles.tileNone}>{waiting ? "Waiting" : down ? "Unknown" : "None yet"}</span>}
      </Tile>
      <Tile label="Forecast valid for" data-tile="valid">
        {left !== null ? <span className={styles.mono}>{left.toFixed(0)} s</span> : <span className={styles.tileNone}>{stale ? "Expired" : nothing}</span>}
        {left !== null && <div className={styles.validBar} aria-hidden="true"><i style={{ width: `${(left / horizon) * 100}%` }} /></div>}
      </Tile>
    </>
  );
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
      {checked?.ok && <Stale data={checked.data} />}
      {checked?.ok && (
        <div {...freshness(checked.data)}>
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
      {checked?.ok && <Stale data={checked.data} />}
      {checked?.ok && (
        <div {...freshness(checked.data)}>
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

export function StatusPanel({ health, cls, count, heartbeat = { status: "unavailable" } }) {
  const server =
    health.status === "loading" ? { kind: "loading", text: "checking" }
      : health.status !== "ok" ? { kind: "bad", text: `unreachable: ${health.reason ?? "no health endpoint"}` }
        : health.data?.status !== "ok" ? { kind: "bad", text: "reachable, but did not report ok" }
          : { kind: "fresh", text: "reachable, reports ok" };
  const rows = [
    ["Server", server],
    ["Class forecast stream", stream(cls, validateClass)],
    ["Count forecast stream", stream(count, validateCount)],
    ["Edge heartbeat", stream(heartbeat, validateHeartbeat)],
  ];
  // A failed request also has a duration, but it is how long it took to fail,
  // not a round trip: report one only for a health check that succeeded.
  const rtt = health.status === "ok" && typeof health.rtt_ms === "number" ? health.rtt_ms : null;
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
        The edge reports itself through its heartbeat; the broker and the ingest do not report
        their own health, so a stream going stale is how a stopped one shows here. No
        edge-to-server delay is recorded live; measured latency is in the committed benchmarks,
        not on this page.
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
          {state.data.signal_study && <SignalStudy study={state.data.signal_study} />}
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
