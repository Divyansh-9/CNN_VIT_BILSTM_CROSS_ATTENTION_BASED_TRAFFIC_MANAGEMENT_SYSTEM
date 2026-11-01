import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Intersection } from "./Intersection.jsx";
import { StatusBanner, operatorStatus, overview } from "./Panels.jsx";
import styles from "./Tour.module.css";

// D33: the walkthrough and the glossary. Both only explain: they send nothing,
// and the tour never replaces what the page shows. On a monitor, a tour that
// swapped real forecasts for examples could be mistaken for the real state, so
// its examples are drawn inside the card, marked as examples, and the page
// behind keeps showing real data throughout.

const ok = (data) => ({ status: "ok", data });
const CLASS_EXAMPLE = { model: "persistence@000000000000", role: "congestion_class (persistence)", age_s: 12, stale: false,
  predictions: { N: "HIGH", S: "MEDIUM", E: "HIGH", W: "LOW" }, missing_approaches: [] };
const COUNT_EXAMPLE = { model: "ridge@000000000000", role: "next_minute_count (ridge)", age_s: 12, stale: false, horizon_sec: 60,
  counts: { N: 2.4, S: 1.1, E: 1.9, W: 0.3 }, missing_approaches: [] };
const beat = (over = {}) => ok({ age_s: 2, stale: false, source: null, lanes: null, ...over });
const REPLAY = { kind: "replay", session: "000000000000", label: "example", position_s: 142, duration_s: 3599 };
const STALE = { stale: true, age_s: 72 };
const health = ok({ status: "ok" });
const NO_W = { predictions: { N: "HIGH", S: "MEDIUM", E: "HIGH" }, missing_approaches: ["W"] };
const NO_W_COUNT = { counts: { N: 2.4, S: 1.1, E: 1.9 }, missing_approaches: ["W"] };
const fresh = { cls: ok(CLASS_EXAMPLE), count: ok(COUNT_EXAMPLE) };

export const EXAMPLES = {
  normal: { label: "Normal", health, ...fresh, heartbeat: beat() },
  replay: { label: "Replay", health, ...fresh, heartbeat: beat({ source: REPLAY }) },
  partial: { label: "One approach missing", health, cls: ok({ ...CLASS_EXAMPLE, ...NO_W }), count: ok({ ...COUNT_EXAMPLE, ...NO_W_COUNT }), heartbeat: beat() },
  silent: { label: "Edge unit silent", health, ...fresh, heartbeat: beat({ stale: true, age_s: 30 }) },
  stale: { label: "Out of date", health, cls: ok({ ...CLASS_EXAMPLE, ...STALE }), count: ok({ ...COUNT_EXAMPLE, ...STALE }), heartbeat: beat({ stale: true, age_s: 75 }) },
  none: { label: "No forecast yet", health, cls: { status: "unavailable" }, count: { status: "unavailable" }, heartbeat: { status: "unavailable" } },
  down: { label: "Server unreachable", health: { status: "error", reason: "example" }, cls: { status: "error", reason: "example" }, count: { status: "error", reason: "example" }, heartbeat: { status: "error", reason: "example" } },
};

export const LIVE_STEPS = [
  { target: "top", section: "live", title: "The top bar: where you are, and what you are watching",
    what: "Moves between the four sections and shows where the numbers come from.",
    read: ["Live, Analyze a video, Analytics and Results are the sections. Only one shows at a time.", "The source badge says Live camera, Replay, or that the source is out of date or unknown.", "The clock is this computer's clock.", "Read-only means this page cannot send commands to anything."],
    limit: "Live camera appears only while the edge unit has reported recently. If it goes quiet the badge changes, so a recording or an old feed is not mistaken for live." },
  { target: "status", section: "live", title: "The status banner: read this first",
    what: "Tells you whether you can trust the rest of the page right now. It updates every 2 seconds.",
    read: ["The large line is the answer: are updates arriving?", "The smaller line says how old the forecast is and how long it holds.", "Each state has its own shape as well as its colour."],
    examples: ["normal", "replay", "silent", "stale", "none", "down"], preview: "banner", tryLabel: "What each situation looks like:",
    now: (live) => { const s = operatorStatus(live); return `It reads: ${s.head}. ${s.sub}`; },
    limit: "The broker and the ingest service do not report their own health. If one of them stops, you see it here as updates stopping." },
  { target: "tiles", section: "live", title: "The four tiles: the situation at a glance",
    what: "Four short answers, so you do not need to read the whole page.",
    read: ["Highest congestion expected: the worst level in the next 60 seconds, and where.", "Busiest approach: the largest expected vehicle number.", "Approaches reporting: how many of the four have both forecasts.", "Forecast valid for: seconds left before this forecast expires."],
    now: (live) => overview(live.cls).headline,
    limit: "The first two tiles can name different approaches. Level and vehicle number are two separate forecasts, and levels are set per camera." },
  { target: "drawing", section: "live", title: "The drawing: the next 60 seconds at each approach",
    what: "A diagram of the four approaches. It is not a map or a video, and the marks are not vehicles.",
    read: ["Ribbon length: expected vehicles, on a fixed scale of 0 to 10, so lengths compare over time.", "Outlined track: that 0 to 10 scale. It is not the road's capacity.", "Colour and word: the congestion level.", "Dashed ribbon: out of date.", "No track and no ribbon: no forecast. That does not mean the road is empty.", "Two cuts near the end of a ribbon: more than 10.", "Squares with a ?: signals, which are not connected. The system forecasts traffic, and does not know their colour."],
    examples: ["normal", "partial", "stale"], preview: "drawing", tryLabel: "How the drawing changes:",
    limit: "N, S, E and W are labels until a camera's directions are verified. N is drawn at the top either way." },
  { target: "approaches", section: "live", title: "The approaches table: the exact numbers",
    what: "The same forecast as the drawing, in numbers, beside what was recently counted.",
    read: ["Congestion level: LOW, MEDIUM or HIGH, comparing vehicles in view with this camera's own range. It does not measure speed or queues.", "Expected vehicles in view: an average across the next 60 seconds, which is why it can be 2.4.", "Counted, last 15 min: a measurement, not a forecast. The dot is the latest value, and a break in the line means no counts.", "Share of expected vehicles: how the expected total divides across approaches."],
    limit: "It counts vehicles in view, not vehicles passing through. Forecasts include bicycles and counted values do not, so the two are not exactly like for like." },
  { target: "what-if", section: "live", title: "If signals were timed from this forecast",
    what: "A calculation that shows how a share of green time would follow the expected vehicles. It is not the real signal.",
    read: ["Each pair is two approaches, joined by their labels.", "The share follows the expected vehicles in view, for illustration.", "The squares on the drawing stay marked with a ?, because the real signal's colour does not reach this system."],
    limit: "It reaches no signal and is not a tested timing plan. In simulation, Webster timing had less delay than PPO, which Results shows." },
  { target: "heat", section: "live", title: "The 20-minute row: what happened, and how forecasts did",
    what: "Each cell is one checked minute, oldest on the left. It shows both the recent pattern and whether the forecast matched.",
    read: ["Colour and letter: the level the counts showed that minute.", "Cut corner: the forecast had said a different level.", "Dashed cell: no valid check that minute. It is a gap, not a good or bad result.", "Level matched k of n: forecasts that matched, out of those checked. It is never a percentage."],
    limit: "This is not accuracy. Both sides come from the same detector's counts, not from a person checking the traffic. These are the persistence and ridge forecasts, not MFSTNet." },
  { target: "limit", section: "live", title: "What this system does not do",
    what: "This line stays on the page in every state, because it is the most important limit.",
    read: ["It forecasts traffic: it reads video, counts vehicles and estimates the next minute.", "It does not change any traffic light. No forecast is connected to signal timing."],
    limit: "Nothing on this page should be read as instructions for operating a signal." },
  { target: "technical", section: "live", openTechnical: true, title: "Technical details: for reviewers",
    what: "Everything an engineer or examiner needs, kept out of the way until wanted. You can ignore it to use the page.",
    read: ["Forecasters and model ids: which version produced the forecast.", "Forecast age and system status: the timing behind the banner.", "Round trip: how long this browser waited for the server.", "References such as ADR-014 and P97a: where each decision is recorded."] },
];
export const MORE_STEPS = [
  { target: "analyze", section: "analyze", title: "Analyze a video: a recording with its results",
    what: "Plays a recording beside what the system found in it. You can jump anywhere, and the results follow the picture.",
    read: ["Open the video: it plays in this browser, and nothing is uploaded.", "Open its results: a file the analysis tool makes once per video, holding numbers and never frames.", "L0 to L3 mark the counted lanes in the picture, and boxes show what the detector found.", "What then happened: the following 60 seconds of counts, which only a recording can show."],
    limit: "Both sides come from the same detector's counts, so this is not accuracy. A recording is not a live camera test." },
  { target: "analytics", section: "analytics", title: "Analytics: what was counted, and what was forecast",
    what: "Looks back over what the server recorded. Nothing here is a forecast of the future.",
    read: ["Observed counts: measured per lane, over 1, 6 or 24 hours.", "A gap in a lane's chart means nothing was counted. It is not zero traffic.", "Forecast history: what was published, with the model that made it."],
    limit: "No accuracy is shown here. Counts leave out bicycles and are kept for 48 hours." },
  { target: "results", section: "results", title: "Results: what the studies found",
    what: "Past measurements from committed files. Nothing here is live, and live numbers never appear beside them.",
    read: ["The signal study shows each controller's delay in a simulator, with its 95% interval. Further left means less delay.", "Each other study names its question, its cameras and how much data it used.", "Each row gives the values, the difference with its 95% interval, and whether it was significant.", "The file, commit and date say where each number came from."],
    limit: "These numbers are historical evidence, not a guarantee of how the system is doing now." },
];
export const QUIZ = [
  { q: "What should you read first on the Live page?", a: ["The status banner", "The 20-minute row", "Technical details"], ok: 0, why: "It says whether the rest of the page can be trusted right now." },
  { q: "An approach shows no forecast. What does that mean?", a: ["The road is empty", "Traffic there is LOW", "The system does not know"], ok: 2, why: "Missing is never zero and never LOW." },
  { q: "Does this system change the traffic lights?", a: ["Yes, automatically", "Only for HIGH traffic", "No"], ok: 2, why: "It forecasts traffic and is not connected to any signal." },
];

const targetOf = (name) => document.querySelector(`[data-tour="${name}"]`);
const technical = () => document.querySelector("[data-technical]");

function Preview({ kind, example }) {
  const e = EXAMPLES[example];
  return (
    <div className={styles.preview} data-tour-example={example}>
      <span className={styles.exampleTag}>Example, not real data</span>
      {kind === "banner" ? <StatusBanner {...e} /> : <Intersection cls={e.cls} count={e.count} />}
    </div>
  );
}

function Intro({ onPick, onExit }) {
  return (
    <>
      <div className={styles.eyebrow}><span>Welcome</span><button type="button" className={styles.exit} onClick={onExit}>Exit</button></div>
      <h2 id="tourTitle" tabIndex={-1}>What is STMS?</h2>
      <p>
        STMS watches an intersection through a camera and forecasts traffic on each approach for the next 60
        seconds. This page shows those forecasts, how recent they are, and what can go wrong. It is a monitor: it
        does not control traffic signals.
      </p>
      <div className={styles.block}>
        <h3>How the numbers reach this page</h3>
        <ol className={styles.flow}>
          <li><b>Camera</b>Video, live or recorded</li>
          <li><b>Edge unit</b>Counts vehicles per lane</li>
          <li><b>Two forecasts</b>A level and a vehicle number</li>
          <li><b>Server</b>Stores what it receives</li>
          <li><b>This page</b>Shows it, read-only</li>
        </ol>
      </div>
      <p className={styles.small}>The video stays on the edge unit. Only counts and forecasts travel. The page behind this card keeps showing real data.</p>
      <div className={styles.nav}>
        <button type="button" className={styles.primary} data-tour-mode="live" onClick={() => onPick(LIVE_STEPS)}>Tour the Live page ({LIVE_STEPS.length} steps)</button>
        <button type="button" className={styles.ghost} data-tour-mode="full" onClick={() => onPick([...LIVE_STEPS, ...MORE_STEPS])}>Tour every section ({LIVE_STEPS.length + MORE_STEPS.length} steps)</button>
      </div>
    </>
  );
}

function Quiz({ onBack, onAgain, onExit }) {
  const [answers, setAnswers] = useState({});
  const right = QUIZ.filter((q, n) => answers[n] === q.ok).length;
  return (
    <>
      <div className={styles.eyebrow}><span>Check your understanding</span><button type="button" className={styles.exit} onClick={onExit}>Exit</button></div>
      <h2 id="tourTitle" tabIndex={-1}>Three questions</h2>
      {QUIZ.map((q, n) => (
        <fieldset key={q.q} className={styles.question}>
          <legend>{n + 1}. {q.q}</legend>
          {q.a.map((text, k) => (
            <label key={text}>
              <input type="radio" name={`quiz${n}`} checked={answers[n] === k} onChange={() => setAnswers({ ...answers, [n]: k })} />{text}
            </label>
          ))}
          {n in answers && <p className={styles.feedback} data-quiz-feedback={n}>{answers[n] === q.ok ? "Correct." : `The answer is: ${q.a[q.ok]}.`} {q.why}</p>}
        </fieldset>
      ))}
      {Object.keys(answers).length === QUIZ.length && <p data-quiz-score="true"><b>{right} of {QUIZ.length} correct.</b></p>}
      <p className={styles.small}>Answers stay on this page and are not recorded.</p>
      <div className={styles.nav}>
        <button type="button" className={styles.ghost} onClick={onBack}>Back</button>
        <span className={styles.navEnd}>
          <button type="button" className={styles.ghost} onClick={onAgain}>Tour again</button>
          <button type="button" className={styles.primary} onClick={onExit}>Finish</button>
        </span>
      </div>
    </>
  );
}

function StepCard({ step, n, total, live, example, onExample, onGo, onExit }) {
  const now = step.now ? step.now(live) : "";
  return (
    <>
      <div className={styles.eyebrow}><span>Step {n + 1} of {total}</span><button type="button" className={styles.exit} onClick={onExit}>Exit</button></div>
      <h2 id="tourTitle" tabIndex={-1}>{step.title}</h2>
      <p className={styles.what}>{step.what}</p>
      <div className={styles.block}><h3>How to read it</h3><ul>{step.read.map((r) => <li key={r}>{r}</li>)}</ul></div>
      {now && <div className={`${styles.block} ${styles.now}`} data-tour-now="true"><h3>On the page right now</h3><p>{now}</p></div>}
      {step.examples && (
        <div className={styles.block}>
          <h3>{step.tryLabel}</h3>
          <div className={styles.tryRow}>
            {step.examples.map((k) => (
              <button key={k} type="button" data-try={k} aria-pressed={k === example} onClick={() => onExample(k)}>{EXAMPLES[k].label}</button>
            ))}
          </div>
          <Preview kind={step.preview} example={example} />
        </div>
      )}
      {step.limit && <div className={`${styles.block} ${styles.keep}`}><h3>Keep in mind</h3><p>{step.limit}</p></div>}
      <div className={styles.dots} role="group" aria-label="Go to a step">
        {Array.from({ length: total }, (_, k) => (
          <button key={k} type="button" aria-label={`Step ${k + 1}`} aria-current={k === n ? "step" : undefined} className={k < n ? styles.done : undefined} onClick={() => onGo(k)} />
        ))}
      </div>
      <div className={styles.nav}>
        <button type="button" className={styles.ghost} data-tour-prev="true" onClick={() => onGo(n - 1)}>Back</button>
        <button type="button" className={styles.primary} data-tour-next="true" onClick={() => onGo(n + 1)}>{n === total - 1 ? "Check your understanding" : "Next"}</button>
      </div>
    </>
  );
}

// `live` holds the page's own polled states, read only to say what they show now.
export function Tour({ section, live, onClose }) {
  const [steps, setSteps] = useState(null);
  const [i, setI] = useState(0);
  const [example, setExample] = useState("normal");
  const card = useRef(null);
  const spot = useRef(null);
  const start = useRef({ hash: window.location.hash, technical: technical()?.open ?? false, padding: document.body.style.paddingBottom });
  const step = steps && i < steps.length ? steps[i] : null;

  // Scroll room, so a section near the bottom can still reach the top of the window.
  useEffect(() => {
    const was = start.current;
    document.body.style.paddingBottom = "80vh";
    return () => {
      document.body.style.paddingBottom = was.padding;
      const t = technical();
      if (t) t.open = was.technical;
      if (window.location.hash !== was.hash) window.location.hash = was.hash;
      window.scrollTo?.(0, 0);
    };
  }, []);

  const place = () => {
    const el = card.current, mark = spot.current;
    if (!el || !mark) return;
    const target = step && step.section === section ? targetOf(step.target) : null;
    const narrow = window.innerWidth <= 640;
    el.classList.toggle(styles.sheet, narrow);
    el.classList.toggle(styles.center, !target);
    el.classList.remove(styles.wide);
    mark.hidden = !target;
    if (!target) { el.style.left = ""; el.style.top = ""; return; }
    const r = target.getBoundingClientRect(), vw = document.documentElement.clientWidth, vh = window.innerHeight, pad = 6, m = 14;
    const top = Math.max(r.top - pad, 2), left = Math.max(r.left - pad, 2);
    Object.assign(mark.style, { top: `${top}px`, left: `${left}px`, width: `${Math.min(r.right + pad, vw - 2) - left}px`, height: `${Math.max(Math.min(r.bottom + pad, vh - 2) - top, 4)}px` });
    if (narrow) { el.style.left = ""; el.style.top = ""; return; }
    // With no room at the side, a wider, shorter card can sit under or over the section.
    if (r.right + m + el.offsetWidth > vw - 8 && r.left - m - el.offsetWidth < 2) el.classList.add(styles.wide);
    const cw = el.offsetWidth, ch = el.offsetHeight;
    const clampY = (y) => Math.min(Math.max(y, 12), vh - ch - 12), clampX = (x) => Math.min(Math.max(x, 12), vw - cw - 12);
    let x, y;
    if (r.right + m + cw <= vw - 8) { x = r.right + m; y = clampY(r.top); }
    else if (r.left - m - cw >= 2) { x = r.left - m - cw; y = clampY(r.top); }
    else if (r.bottom + m + ch <= vh - 8) { x = clampX(r.left); y = r.bottom + m; }
    else if (r.top - m - ch >= 8) { x = clampX(r.left); y = r.top - m - ch; }
    else { x = vw - cw - 12; y = vh - ch - 12; }
    el.style.left = `${x}px`; el.style.top = `${y}px`;
  };

  // Each step: go to its section, open what it needs, bring it into view.
  useEffect(() => {
    if (step && step.section !== section) { window.location.hash = `#${step.section}`; return; }
    const t = technical();
    if (t) t.open = step?.openTechnical ? true : start.current.technical;
    if (step) {
      const target = targetOf(step.target);
      target?.scrollIntoView?.({ block: "start" });
    } else if (!steps) window.scrollTo?.(0, 0);
    card.current?.querySelector("h2")?.focus({ preventScroll: true });
  }, [step, steps, section]);

  // Polled data changes the page's layout, so the card and the highlight follow it on every render.
  useLayoutEffect(place);
  useEffect(() => {
    window.addEventListener("scroll", place, { passive: true });
    window.addEventListener("resize", place);
    return () => { window.removeEventListener("scroll", place); window.removeEventListener("resize", place); };
  });

  const go = (k) => {
    if (k < 0) { setSteps(null); setI(0); return; }
    setExample("normal");
    setI(k);
  };
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (!steps || e.target?.matches?.("input")) return;
      if (e.key === "ArrowRight" && i < steps.length) go(i + 1);
      if (e.key === "ArrowLeft" && i > 0) go(i - 1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <div className={`${styles.shield} ${step ? "" : styles.dim}`} />
      <div ref={spot} className={styles.spot} hidden />
      <section ref={card} className={styles.card} role="dialog" aria-modal="true" aria-labelledby="tourTitle" data-tour-card="true">
        {!steps && <Intro onPick={(s) => { setSteps(s); setI(0); }} onExit={onClose} />}
        {step && <StepCard step={step} n={i} total={steps.length} live={live} example={example} onExample={setExample} onGo={go} onExit={onClose} />}
        {steps && !step && <Quiz onBack={() => setI(steps.length - 1)} onAgain={() => { setSteps(null); setI(0); }} onExit={onClose} />}
      </section>
    </>
  );
}

export const GLOSSARY = [
  ["Approach", "One road arm entering the intersection. N, S, E and W are its labels."],
  ["Lane", "A counted area in the camera's picture. The edge unit says which approach each lane feeds."],
  ["Congestion level", "LOW, MEDIUM or HIGH: the vehicles in view over 60 seconds, compared with limits set from one calibration hour of that camera. It does not measure speed or queues, and HIGH can be only a few vehicles."],
  ["Expected vehicles in view", "A forecast of the average number of vehicles visible in that lane over the next 60 seconds. It is not how many will pass through."],
  ["Counted", "What the detector measured in the video. Bicycles are left out of these counts."],
  ["Forecast", "An estimate of the next 60 seconds. After 60 seconds it is out of date."],
  ["Edge unit", "The computer that reads the video and counts vehicles. The video stays there; only numbers leave it."],
  ["Detector", "The vision model that finds vehicles in the video."],
  ["Replay", "Recorded footage run through the system as if it were arriving now. It is never a live camera."],
  ["Out of date", "Older than its 60 seconds, so it describes a minute that has passed."],
  ["Check", "A past forecast beside what the counts then showed. Both sides come from the same detector."],
  ["Persistence", "The forecast method behind the level: it expects the current level to continue."],
  ["Ridge", "The forecast method behind the vehicle number: a simple statistical model of recent counts."],
  ["Webster", "A long-established formula that sets signal timing from traffic demand."],
  ["PPO", "A reinforcement learning method, tested on signal timing only in simulation here."],
  ["95% interval", "The range the measured value plausibly falls in. Wide means less certain."],
];

export function Glossary({ onClose }) {
  const box = useRef(null);
  useEffect(() => {
    const el = box.current;
    if (typeof el.showModal === "function") el.showModal(); else el.setAttribute("open", "");
  }, []);
  return (
    <dialog ref={box} className={styles.glossary} aria-labelledby="glossaryTitle" onClose={onClose} data-glossary="true">
      <div className={styles.glossaryHead}>
        <h2 id="glossaryTitle">Glossary</h2>
        <button type="button" className={styles.ghost} onClick={onClose}>Close</button>
      </div>
      <dl>{GLOSSARY.map(([term, meaning]) => <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>)}</dl>
    </dialog>
  );
}
