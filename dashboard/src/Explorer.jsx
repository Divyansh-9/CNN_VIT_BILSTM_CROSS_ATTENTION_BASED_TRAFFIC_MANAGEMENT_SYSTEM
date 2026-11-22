import { lazy, Suspense, useEffect, useRef, useState } from "react";
import styles from "./Explorer.module.css";
import {
  ARCHITECTURE, COMPARISON, COUNT_BENCHMARK, DATAFLOW, ENDPOINTS, EXAMPLE_LIMITS, GROUPS, PCU, PIPELINE, STATUS, TOPICS,
} from "./explorerContent.js";
import { Icon } from "./icons.jsx";
import { SITE } from "./site.js";
import { ThemeSwitch } from "./ThemeSwitch.jsx";
import { AccountMenu } from "./AuthGate.jsx";
import { PipelineWalkthrough, useLocalExample } from "./PipelineWalkthrough.jsx";
const ExplorerTour = lazy(() => import("./ExplorerTour.jsx"));

// The project explorer (#explore/<topic>): a guided technical tour, one topic
// at a time, for someone who has never seen the project. It polls nothing:
// every figure is drawn from explorerContent.js, never from live data, so
// nothing here can be mistaken for a reading (ADR-014).

const SEEN_KEY = "stms.explorerSeen";
function loadSeen() {
  try { return new Set(JSON.parse(window.localStorage.getItem(SEEN_KEY) || "[]")); } catch { return new Set(); }
}
function saveSeen(seen) {
  try { window.localStorage.setItem(SEEN_KEY, JSON.stringify([...seen])); } catch { /* a convenience only */ }
}

export function topicIndex(id) {
  const i = TOPICS.findIndex((t) => t.id === id);
  return i < 0 ? 0 : i;
}

const QUESTIONS = [
  ["what", "What is it?", "lightbulb"],
  ["why", "Why is it needed?", "target"],
  ["use", "How does our project use it?", "gear"],
  ["inside", "How does it work internally?", "cpu"],
  ["where", "Which component implements it?", "code"],
  ["output", "What output does it produce?", "check-circle"],
];

function StatusPill({ status }) {
  return <span className={styles.pill} data-status={status}>{STATUS[status]}</span>;
}

// ---------------------------------------------------------------- figures

function ArchitectureFigure() {
  const [picked, setPicked] = useState("detector");
  const all = ARCHITECTURE.flatMap((l) => l.blocks);
  const block = all.find((b) => b.id === picked);
  return (
    <div className={styles.figure} data-figure="architecture">
      <div className={styles.arch}>
        {ARCHITECTURE.map((layer, i) => (
          <div key={layer.layer} className={styles.layerWrap}>
            <div className={styles.layer}>
              <p className={styles.layerName}>{layer.layer}</p>
              <div className={styles.blocks}>
                {layer.blocks.map((b) => (
                  <button key={b.id} type="button" className={styles.block} aria-pressed={b.id === picked} onClick={() => setPicked(b.id)}>
                    {b.title}
                  </button>
                ))}
              </div>
            </div>
            {i < ARCHITECTURE.length - 1 && <div className={styles.flowDown} aria-hidden="true"><i /></div>}
          </div>
        ))}
      </div>
      <aside className={styles.detail} aria-live="polite">
        <p className={styles.detailKicker}>Selected component</p>
        <h4>{block.title}</h4>
        <p>{block.text}</p>
        <p className={styles.where}><Icon name="code" size={14} /><code>{block.where}</code></p>
        <p className={styles.hint}>Click any block to see its role.</p>
      </aside>
    </div>
  );
}

function PipelineFigure() {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return undefined;
    const t = setInterval(() => setStep((s) => (s + 1) % PIPELINE.length), 1600);
    return () => clearInterval(t);
  }, [playing]);
  const s = PIPELINE[step];
  return (
    <div className={styles.figureCol} data-figure="pipeline">
      <div className={styles.pipeControls}>
        <button type="button" className={styles.smallButton} onClick={() => setPlaying((p) => !p)} aria-pressed={playing}>
          <Icon name={playing ? "timer" : "lightning"} size={16} />{playing ? "Pause" : "Play the sequence"}
        </button>
        <span className={styles.muted}>Step {step + 1} of {PIPELINE.length}</span>
      </div>
      <ol className={styles.pipeline}>
        {PIPELINE.map((p, i) => (
          <li key={p.title} data-state={i < step ? "done" : i === step ? "active" : "next"}>
            <button type="button" onClick={() => { setPlaying(false); setStep(i); }} aria-current={i === step ? "step" : undefined}>
              <span className={styles.pipeIcon}><Icon name={p.icon} size={20} /></span>
              <span className={styles.pipeTitle}>{p.title}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className={styles.detail} aria-live="polite">
        <p className={styles.detailKicker}>Step {step + 1}</p>
        <h4>{s.title}</h4>
        <p>{s.text}</p>
      </div>
    </div>
  );
}

function DataFlowFigure() {
  const node = Object.fromEntries(DATAFLOW.nodes.map((n) => [n.id, n]));
  const W = 150, H = 56;
  return (
    <div className={styles.figureCol} data-figure="dataflow">
      <div className={styles.svgWrap}>
        <svg viewBox="0 0 660 360" className={styles.flowSvg} role="img" aria-label="Data flow: edge node to MQTT broker to ingest to SQLite to FastAPI to dashboard">
          <defs>
            <marker id="arrowHead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" className={styles.arrowHead} />
            </marker>
          </defs>
          {DATAFLOW.edges.map((e) => {
            const a = node[e.from], b = node[e.to];
            const horizontal = a.y === b.y;
            const dir = horizontal ? Math.sign(b.x - a.x) : Math.sign(b.y - a.y);
            const x1 = horizontal ? a.x + dir * W / 2 : a.x, y1 = horizontal ? a.y : a.y + dir * H / 2;
            const x2 = horizontal ? b.x - dir * (W / 2 + 4) : b.x, y2 = horizontal ? b.y : b.y - dir * (H / 2 + 4);
            const lx = (x1 + x2) / 2, ly = (y1 + y2) / 2;
            return (
              <g key={`${e.from}-${e.to}`}>
                <line x1={x1} y1={y1} x2={x2} y2={y2} className={styles.edge} markerEnd="url(#arrowHead)" />
                <text x={horizontal ? lx : lx + 10} y={horizontal ? ly - 10 : ly} className={styles.edgeLabel}
                      textAnchor={horizontal ? "middle" : "start"}>{e.label}</text>
              </g>
            );
          })}
          {DATAFLOW.nodes.map((n) => (
            <g key={n.id} className={styles.node}>
              <rect x={n.x - W / 2} y={n.y - H / 2} width={W} height={H} rx="10" />
              <text x={n.x} y={n.y - 3} textAnchor="middle" className={styles.nodeLabel}>{n.label}</text>
              <text x={n.x} y={n.y + 15} textAnchor="middle" className={styles.nodeSub}>{n.sub}</text>
            </g>
          ))}
        </svg>
      </div>
      <p className={styles.caption}>
        No image crosses any arrow: the edge publishes only counts, forecasts, heartbeats and checks (NFR-13).
        The dashboard reads the API, never MQTT directly.
      </p>
    </div>
  );
}

const LEVEL_OF = (m, { low, med }) => (m <= low ? "LOW" : m <= med ? "MEDIUM" : "HIGH");

function LevelsFigure() {
  const [mean, setMean] = useState(0.5);
  const level = LEVEL_OF(mean, EXAMPLE_LIMITS);
  const max = 3;
  const pct = (v) => `${(Math.min(v, max) / max) * 100}%`;
  return (
    <div className={styles.figureCol} data-figure="levels">
      <label className={styles.sliderLabel}>
        Mean vehicles in view over the last 60 s (30 counts):
        <strong className={styles.mono}>{mean.toFixed(2)}</strong>
        <input type="range" min="0" max={max} step={1 / 30} value={mean} onChange={(e) => setMean(Number(e.target.value))} />
      </label>
      <div className={styles.scale} aria-hidden="true">
        <i className={styles.marker} style={{ left: pct(EXAMPLE_LIMITS.low) }}><span>low {EXAMPLE_LIMITS.low.toFixed(3)}</span></i>
        <i className={styles.marker} style={{ left: pct(EXAMPLE_LIMITS.med) }}><span>med {EXAMPLE_LIMITS.med.toFixed(3)}</span></i>
        <b className={styles.thumb} style={{ left: pct(mean) }} />
      </div>
      <p className={styles.result}>Forecast for the next 60 s: <span className={`${styles.chip} ${styles[level]}`}>{level}</span></p>
      <p className={styles.caption}>
        Thresholds are {EXAMPLE_LIMITS.camera}'s own, from its calibration hour (a quiet Sunday evening), so HIGH here
        means about one vehicle in view on average. That is why levels are compared within a camera, never across cameras.
      </p>
    </div>
  );
}

const STACK_ROLES = [
  ["Python", "The edge, server, training and scripts."],
  ["PyTorch", "MFSTNet training and inference; bf16 mixed precision."],
  ["Ultralytics YOLOv8", "Vehicle detection on the edge."],
  ["ResNet-50 + DINOv2 ViT-S/14", "Frozen image encoders inside MFSTNet."],
  ["ONNX Runtime", "Exported models for CPU inference."],
  ["SUMO + TraCI", "The simulated four-way intersection."],
  ["Stable-Baselines3 PPO", "The reinforcement-learning signal controller."],
  ["MQTT (Mosquitto)", "Authenticated edge-to-server messaging."],
  ["FastAPI + Pydantic", "The validated HTTP API."],
  ["SQLite", "The server's store, one file."],
  ["Docker Compose", "Broker, API and ingest as one stack (verified in CI)."],
  ["React 18 + Vite", "This dashboard, with CSS Modules and measured design tokens."],
];

function StackFigure() {
  return (
    <ul className={styles.stackGrid} data-figure="stack">
      {STACK_ROLES.map(([name, role]) => (
        <li key={name}><strong>{name}</strong><span>{role}</span></li>
      ))}
    </ul>
  );
}

function CompareFigure() {
  return (
    <div className={styles.tableWrap} data-figure="compare">
      <table className={styles.compare}>
        <thead><tr><th scope="col">Aspect</th><th scope="col">Conventional</th><th scope="col">STMS (proposed)</th></tr></thead>
        <tbody>
          {COMPARISON.map(([aspect, old, ours]) => (
            <tr key={aspect}><th scope="row">{aspect}</th><td>{old}</td><td>{ours}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ApiFigure() {
  return (
    <ul className={styles.api} data-figure="api">
      {ENDPOINTS.map(([method, path, text]) => (
        <li key={path}>
          <span className={styles.method} data-method={method}>{method}</span>
          <code>{path}</code>
          <span className={styles.muted}>{text}</span>
        </li>
      ))}
    </ul>
  );
}

function PcuFigure() {
  return (
    <div className={styles.figureCol} data-figure="pcu">
      <ul className={styles.pcu}>
        {PCU.map(([name, w]) => (
          <li key={name}><span>{name}</span><i style={{ width: `${(Number(w) / 5) * 100}%` }} /><strong className={styles.mono}>{w}</strong></li>
        ))}
      </ul>
      <p className={styles.caption}>Passenger car units, Indo-HCM 2017 (ADR-017). A class with no decided value raises an error rather than defaulting to 1.0.</p>
    </div>
  );
}

const MFST = [
  ["Frames", "60 frames, 5 s apart: the last five minutes."],
  ["ResNet-50 · DINOv2 ViT-S/14", "Two frozen encoders: local texture (CNN) and global layout (ViT, 257 tokens)."],
  ["Gated bidirectional cross-attention", "CNN queries ViT and ViT queries CNN; a learned gate g mixes the two. The gate is logged as a research artifact."],
  ["BiLSTM, 2 × 128", "Reads the fused sequence in both directions."],
  ["Temporal self-attention + attention pooling", "Weighs which moments matter."],
  ["Per-lane ROI pooling → heads", "One LOW / MEDIUM / HIGH prediction per lane, 60 s ahead."],
];

function MfstnetFigure() {
  const [open, setOpen] = useState(2);
  return (
    <div className={styles.figureCol} data-figure="mfstnet">
      <ol className={styles.mfst}>
        {MFST.map(([title, text], i) => (
          <li key={title}>
            <button type="button" aria-expanded={open === i} onClick={() => setOpen(open === i ? -1 : i)}>
              <span className={styles.mfstNo}>{i + 1}</span>{title}<Icon name="caret-down" size={14} />
            </button>
            {open === i && <p>{text}</p>}
          </li>
        ))}
      </ol>
      <p className={styles.caption}>
        Eight ablation variants (A–H, H being a linear probe) are evaluated leave-one-camera-out over five seeds.
        The deployed forecasts are persistence and ridge, not MFSTNet (ADR-027).
      </p>
    </div>
  );
}

const EVIDENCE = [
  { title: "Ridge count forecast", scope: "Deployed · P105", result: `${COUNT_BENCHMARK.ridge} vs ${COUNT_BENCHMARK.persistence} vehicles MAE`,
    question: "Does Ridge improve next-minute vehicle counts on held-out cameras?", baseline: "Repeat the previous minute’s mean count.",
    protocol: "The paired error reduction was 0.224 vehicles. Its 95% interval was 0.181 to 0.271.",
    file: "bellevue_pilot/p105_results.json" },
  { title: "Persistence congestion forecast", scope: "Deployed · P103", result: "0.706 vs 0.483 macro-F1",
    question: "Which congestion forecaster transfers to a new camera?", baseline: "C1-L count model trained on one camera.",
    protocol: "The comparison uses camera-calibrated congestion thresholds. It measures class forecasts.",
    file: "bellevue_pilot/p103_results.json" },
  { title: "MFSTNet", scope: "Research · Four held-out cameras", result: "Could not distinguish the models",
    question: "Does learned fusion improve on a linear probe?", baseline: "Frozen visual features with a linear probe.",
    protocol: "The paired macro-F1 difference had a 95% interval from −0.154 to +0.066 across folds.",
    file: "gate_vs_probe.csv" },
  { title: "SUMO signal control", scope: "Simulation · P130", result: "No demonstrated delay reduction",
    question: "Does a perfect forecast reduce simulated signal delay?", baseline: "PPO with no forecast and PPO with persistence.",
    protocol: "In 28 evaluation seeds, perfect-forecast PPO averaged 5.41 s more delay than no-forecast PPO. The difference was not statistically significant.",
    file: "ceiling/ceiling_stats.json" },
];

function CountAudit() {
  const audit = useLocalExample("count-audit.json");
  const source = `${SITE.repository}/blob/main/experiments/results/bellevue_pilot`;
  const glare = audit?.hours["2017-09-11_08-08-31"];
  return (
    <section className={styles.auditCase} aria-label="Human count case study">
      <h3>Case study · Bellevue detector under glare</h3>
      <p>The P99b audit counted sampled frames blind, with detector boxes hidden. It covered dawn, morning glare, and dusk on one camera.</p>
      {audit && <>
        <div className={styles.tableWrap}>
          <table className={styles.auditTable}>
            <caption>{audit.frames} hand-counted frames · ITD-xl · Counts per lane</caption>
            <thead><tr><th scope="col">Approach</th><th scope="col">Mean absolute error</th><th scope="col">Mean detector minus hand count</th></tr></thead>
            <tbody>{Object.entries(audit.lanes).map(([name, lane]) => (
              <tr key={name}><th scope="row">{name}</th><td>{lane.mae.toFixed(2)}</td><td>{lane.signed.toFixed(2)}</td></tr>
            ))}</tbody>
          </table>
        </div>
        {glare && <p>The strongest-glare hour had the highest mean absolute error, {glare.mae3.toFixed(2)} vehicles per lane, and undercounted by {Math.abs(glare.signed).toFixed(2)} on average across {glare.frames} frames.</p>}
      </>}
      <p>This audit measures counting against human observations on one camera. The walkthrough shows a separate Bellevue recording.</p>
      <div className={styles.auditLinks}>
        <a href={`${source}/p99b_comparison.json`}>Lane-by-lane results</a>
        <a href={`${source}/p99b_manual.json`}>Blind hand counts</a>
        <a href={`${source}/PREREGISTRATION_P99b.md`}>Audit protocol</a>
      </div>
    </section>
  );
}

function ResultsFigure() {
  return (
    <div className={styles.figureCol} data-figure="results">
      <h2>Research evidence</h2>
      <div className={styles.evidenceGrid}>
        {EVIDENCE.map((study) => (
          <article className={styles.evidenceCard} key={study.title}>
            <p className={styles.muted}>{study.scope}</p>
            <h3>{study.title}</h3>
            <p>{study.question}</p>
            <strong>{study.result}</strong>
            <details>
              <summary>Baseline and protocol</summary>
              <p>{study.baseline} {study.protocol}</p>
            </details>
            <a className={styles.inlineLink} href={`${SITE.repository}/blob/main/experiments/results/${study.file}`} target="_blank" rel="noreferrer">
              <Icon name="code" size={15} />{study.file.split("/").at(-1)}
            </a>
          </article>
        ))}
      </div>
      <CountAudit />
      <a className={styles.inlineLink} href="#results"><Icon name="results" size={16} />Open the full evidence in the console's Results section</a>
    </div>
  );
}

const FIGURES = {
  architecture: ArchitectureFigure, pipeline: PipelineFigure, dataflow: DataFlowFigure, levels: LevelsFigure,
  stack: StackFigure, compare: CompareFigure, api: ApiFigure, pcu: PcuFigure, mfstnet: MfstnetFigure, results: ResultsFigure,
};

// ---------------------------------------------------------------- the page

export function Explorer({ topic, stage, fetcher }) {
  const index = topicIndex(topic);
  const t = TOPICS[index];
  const prev = TOPICS[index - 1], next = TOPICS[index + 1];
  const [seen, setSeen] = useState(loadSeen);
  const [menu, setMenu] = useState(false);
  const [tour, setTour] = useState(false);
  const head = useRef(null);
  const tourOrigin = useRef(null);
  useEffect(() => {
    setSeen((old) => {
      if (old.has(t.id)) return old;
      const updated = new Set(old).add(t.id);
      saveSeen(updated);
      return updated;
    });
    setMenu(false);
    window.scrollTo?.(0, 0);
    head.current?.focus({ preventScroll: true });
  }, [t.id]);
  useEffect(() => { setTour(false); }, [t.id, stage]);
  const done = TOPICS.filter((x) => seen.has(x.id)).length;
  const Figure = t.visual ? FIGURES[t.visual] : null;
  const intro = t.id === "introduction" && (topic == null || topic === t.id);
  return (
    <div className={styles.page} data-project-explorer>
      <header className={styles.bar}>
        <a className={styles.brand} href="#home"><span className={styles.mark}><Icon name="signal" size={18} /></span>{SITE.short}<span className={styles.barSub}>Project explorer</span></a>
        <div className={styles.barRight}>
          <button type="button" className={styles.menuButton} onClick={() => setMenu((m) => !m)} aria-label="Contents" aria-expanded={menu} aria-controls="explorerToc">
            <Icon name={menu ? "x" : "list"} size={18} /><span>Contents</span>
          </button>
          <ThemeSwitch compact />
          <AccountMenu compact />
          <a className={styles.barLink} href="#home"><Icon name="house" size={16} />Home</a>
          <a className={styles.barCta} href="#overview" aria-label="Launch Dashboard">
            <Icon name="rocket-launch" size={16} /><span>Launch <span className={styles.launchWord}>Dashboard</span></span>
          </a>
        </div>
      </header>
      <div className={styles.progress} role="progressbar" aria-label="Topics visited" aria-valuemin={0} aria-valuemax={TOPICS.length} aria-valuenow={done}>
        <i style={{ width: `${(done / TOPICS.length) * 100}%` }} />
      </div>

      <div className={styles.layout}>
        <nav id="explorerToc" className={styles.toc} data-open={menu} aria-label="Explorer contents">
          <p className={styles.tocHead}>{done} of {TOPICS.length} topics visited</p>
          {GROUPS.map((g) => (
            <div key={g} className={styles.tocGroup}>
              <p className={styles.tocGroupName}>{g}</p>
              <ol>
                {TOPICS.map((x, i) => x.group === g && (
                  <li key={x.id}>
                    <a href={`#explore/${x.id}`} aria-current={x.id === t.id ? "page" : undefined} data-seen={seen.has(x.id) || undefined}>
                      <span className={styles.tocNo}>{seen.has(x.id) && x.id !== t.id ? <Icon name="check" size={12} /> : String(i + 1).padStart(2, "0")}</span>
                      {x.title}
                    </a>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </nav>

        <main className={styles.main} key={t.id}>
          <p className={styles.crumb}>{t.group} · Topic {String(index + 1).padStart(2, "0")} of {TOPICS.length}</p>
          <div className={styles.titleRow}>
            <span className={styles.topicIcon}><Icon name={t.icon} size={26} /></span>
            <h1 ref={head} tabIndex={-1} className={styles.h1}>{t.title}</h1>
            <StatusPill status={t.status} />
          </div>
          <p className={styles.summary}>{t.summary}</p>

          <nav className={styles.quickLinks} aria-label="Explore project shortcuts">
            <button type="button" className={styles.tourButton} onClick={event => {
              tourOrigin.current = { trigger: event.currentTarget, left: window.scrollX, top: window.scrollY };
              setTour(true);
            }}>
              <Icon name="compass" size={16} />Take a Tour
            </button>
            {intro && <>
              <a href="#explore/pipeline/camera"><Icon name="flow-arrow" size={16} />Pipeline walkthrough</a>
              <a href="#explore/results"><Icon name="results" size={16} />Research evidence</a>
              <a href="#live"><Icon name="live" size={16} />Live Monitoring</a>
              <a href="#analyze"><Icon name="film-strip" size={16} />Analyze a Video</a>
            </>}
          </nav>
          {intro && <PipelineWalkthrough stage={stage} />}
          {Figure && <section className={styles.figureBox} aria-label="Interactive figure"><Figure /></section>}

          {t.points && (
            <ul className={styles.points}>
              {t.points.map(([status, text]) => (
                <li key={text}><StatusPill status={status} /><span>{text}</span></li>
              ))}
            </ul>
          )}

          <div className={styles.questions}>
            {QUESTIONS.map(([key, label, icon], i) => (
              <details key={key} className={styles.question} open={i < 3 || undefined}>
                <summary><Icon name={icon} size={16} />{label}<Icon name="caret-down" size={14} /></summary>
                {key === "where" ? <p><code>{t[key]}</code></p> : <p>{t[key]}</p>}
              </details>
            ))}
          </div>

          <nav className={styles.pager} aria-label="Previous and next topic">
            {prev ? <a href={`#explore/${prev.id}`} className={styles.pageLink}><Icon name="arrow-left" size={16} /><span><small>Previous</small>{prev.title}</span></a> : <a href="#home" className={styles.pageLink}><Icon name="arrow-left" size={16} /><span><small>Back to</small>Home</span></a>}
            {next ? <a href={`#explore/${next.id}`} className={`${styles.pageLink} ${styles.pageNext}`}><span><small>Next</small>{next.title}</span><Icon name="arrow-right" size={16} /></a>
              : <a href="#overview" className={`${styles.pageLink} ${styles.pageNext}`}><span><small>Tour complete</small>Launch the project</span><Icon name="rocket-launch" size={16} /></a>}
          </nav>
        </main>
      </div>
      {tour && <Suspense fallback={<p role="status" className={styles.presentationLoading}>Opening presentation…</p>}>
        <ExplorerTour fetcher={fetcher} origin={tourOrigin.current} onClose={() => setTour(false)} />
      </Suspense>}
    </div>
  );
}
