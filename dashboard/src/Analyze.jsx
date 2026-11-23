import { RegionOverlay, TrafficRegions, useTrafficRegions } from "./TrafficRegions.jsx";
import { SceneForecast } from "./SceneForecast.jsx";
import { useEffect, useMemo, useRef, useState } from "react";
import { downloadText, toCsv } from "./ops.js";
import panel from "./Panels.module.css";
import styles from "./Analyze.module.css";
import { VideoEngineering } from "./Engineering.jsx";
import { VideoCheck } from "./VideoCheck.jsx";
import { CLASSES, validateAnalysis } from "./validate.js";

// D34: a recording beside the results of scripts/analyze_video.py. Both files are
// opened in this browser and neither is sent anywhere: this page stays read-only,
// and nothing it shows is invented. With no results file it shows no numbers; with
// no video it shows the numbers and no picture.

const fmt = (t) => `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const CELLS = 48;
const LENGTH_TOLERANCE_S = 5;
export const COMMAND = "python scripts/analyze_video.py --video YOUR_VIDEO.mp4 --profile cameras/150th_Eastgate.json --out results.json";

export function sampleAt(analysis, t) {
  const k = Math.min(Math.max(Math.floor(t / analysis.step_s), 0), analysis.samples.length - 1);
  return analysis.samples[k];
}

function Chip({ level }) {
  return <span className={`${panel.chip} ${panel[level]}`}>{level}</span>;
}

function Results({ analysis, sample, lane, vehicleClass }) {
  if (analysis.traffic?.scope === "frame") return <p>{vehicleClass ? countClass(sample, "frame", vehicleClass) : sample.counts.frame} vehicles visible in this frame.</p>;
  const note = !sample.level ? "Forecasts need history. The level starts at 01:00 and the number at 02:00."
    : !sample.number ? "The vehicle number starts at 02:00." : "";
  return (
    <>
      {note && <p className={styles.note} data-analysis-note="true">{note}</p>}
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead><tr><th scope="col">Lane</th><th scope="col">Counted now</th><th scope="col">Forecast level</th><th scope="col">Forecast number</th><th scope="col">What then happened</th></tr></thead>
          <tbody>
            {analysis.lanes.map(({ name, approach }, i) => {
              if (lane && name !== lane) return null;
              const level = sample.level?.[approach], then = sample.then?.[approach];
              return (
                <tr key={name} data-analysis-row={name}>
                  <th scope="row"><b>L{i}</b> <span className={styles.muted}>{analysis.directions_verified ? `from ${approach}` : `label ${approach}`}</span></th>
                  <td className={styles.mono}>{vehicleClass ? countClass(sample, name, vehicleClass) : sample.counts[name]}</td>
                  <td>{level ? <Chip level={level} /> : <span className={styles.absent}>waiting</span>}</td>
                  <td className={styles.mono}>{sample.number ? sample.number[approach].toFixed(1) : <span className={styles.absent}>waiting</span>}</td>
                  <td>{then ? <span className={styles.mono}>{then.level} {then.number.toFixed(1)}{level && then.level !== level ? <span className={styles.differs}> differs</span> : null}</span>
                    : <span className={styles.absent}>{sample.level ? "video ends first" : "none"}</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={styles.small}>
        {vehicleClass && <>The counted column shows {vehicleClass}. Forecasts use all classes. </>}
        Forecasts cover the next 60 seconds. "What then happened" comes from the same detector's counts, so it is
        not accuracy. At this camera LOW is up to {analysis.limits.low.toFixed(2)} vehicles in view, MEDIUM up to{" "}
        {analysis.limits.med.toFixed(2)}, and HIGH above that.
      </p>
    </>
  );
}

function Timeline({ analysis, t, onSeek }) {
  const rows = useMemo(() => analysis.lanes.map(({ name, approach }) => ({
    name, cells: Array.from({ length: CELLS }, (_, c) => {
      const from = (c / CELLS) * analysis.duration_s;
      const s = sampleAt(analysis, from);
      return { from, level: s.level?.[approach] ?? null };
    }),
  })), [analysis]);
  const seek = (e) => {
    const row = e.target.closest("[data-timeline-cells]");
    if (!row) return;
    const r = row.getBoundingClientRect();
    onSeek(((e.clientX - r.left) / (r.width || 1)) * analysis.duration_s);
  };
  return (
    <div className={styles.timeline} onClick={seek} data-timeline="true">
      {rows.map(({ name, cells }, i) => (
        <div key={name} className={styles.timelineRow}>
          <b>L{i}</b>
          <div className={styles.timelineCells} data-timeline-cells="true" style={{ "--played": `${(t / analysis.duration_s) * 100}%` }}>
            {cells.map(({ from, level }) => (
              <i key={from} className={CLASSES.includes(level) ? styles[level] : styles.waiting}
                 title={`${fmt(from)}: ${level ?? "no forecast yet"}`} />
            ))}
          </div>
        </div>
      ))}
      <div className={styles.axis}><span>00:00</span><i aria-hidden="true" /><span>{fmt(analysis.duration_s)}</span></div>
    </div>
  );
}

const PLOT = { width: 640, height: 124, left: 36, right: 624, top: 10, bottom: 104 };

function countClass(sample, lane, vehicleClass) {
  return sample.detections.filter(([label, , assigned]) =>
    label === vehicleClass && assigned && (!lane || assigned === lane)).length;
}

function countAt(sample, lane, vehicleClass) {
  if (vehicleClass) return countClass(sample, lane, vehicleClass);
  return lane ? sample.counts[lane] : Object.values(sample.counts).reduce((sum, value) => sum + value, 0);
}

function CountTimeline({ analysis, t, onSeek, lane, vehicleClass }) {
  const { points, spikes, maxCount } = useMemo(() => {
    const rows = analysis.samples.map((sample) => ({ t: sample.t, count: countAt(sample, lane, vehicleClass) }));
    const grouped = new Map();
    for (const [index, row] of rows.entries()) {
      const gain = index ? row.count - rows[index - 1].count : 0;
      if (gain < 2) continue;
      const window = Math.floor(row.t / 15);
      if (gain > (grouped.get(window)?.gain ?? 0)) grouped.set(window, { ...row, gain });
    }
    const spikes = [...grouped.values()].sort((a, b) => b.gain - a.gain).slice(0, 4).sort((a, b) => a.t - b.t);
    const stride = Math.max(1, Math.ceil(rows.length / 280));
    const points = [];
    for (let start = 0; start < rows.length; start += stride) {
      const block = rows.slice(start, start + stride);
      points.push(block.reduce((peak, row) => row.count > peak.count ? row : peak));
    }
    return { points, spikes, maxCount: rows.reduce((max, row) => Math.max(max, row.count), 1) };
  }, [analysis, lane, vehicleClass]);
  const x = (seconds) => PLOT.left + seconds / analysis.duration_s * (PLOT.right - PLOT.left);
  const y = (count) => PLOT.bottom - count / maxCount * (PLOT.bottom - PLOT.top);
  const series = points.map((point) => `${x(point.t)},${y(point.count)}`).join(" ");
  const seek = (event) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    if (!bounds.width) return;
    const position = (event.clientX - bounds.left) / bounds.width * PLOT.width;
    onSeek((position - PLOT.left) / (PLOT.right - PLOT.left) * analysis.duration_s);
  };
  return (
    <div className={styles.countTimeline}>
      <h4>Vehicles in view</h4>
      <p className={styles.small}>Click the chart or select a count spike to jump to that moment.</p>
      <svg className={styles.countPlot} viewBox={`0 0 ${PLOT.width} ${PLOT.height}`} role="img"
           aria-label="Vehicles in view over the recording" onClick={seek}>
        {[0, maxCount].map((count) => (
          <g key={count}>
            <line className={styles.plotGrid} x1={PLOT.left} x2={PLOT.right} y1={y(count)} y2={y(count)} />
            <text className={styles.plotLabel} x={PLOT.left - 7} y={y(count) + 4} textAnchor="end">{count}</text>
          </g>
        ))}
        <polyline className={styles.countLine} points={series} />
        {spikes.map((spike) => <circle key={spike.t} className={styles.spikeDot} cx={x(spike.t)} cy={y(spike.count)} r="4">
          <title>{fmt(spike.t)} · {spike.gain} more vehicles</title>
        </circle>)}
        <line className={styles.plotCursor} x1={x(Math.min(t, analysis.duration_s))} x2={x(Math.min(t, analysis.duration_s))}
              y1={PLOT.top} y2={PLOT.bottom} />
        <text className={styles.plotLabel} x={PLOT.left} y="120">00:00</text>
        <text className={styles.plotLabel} x={PLOT.right} y="120" textAnchor="end">{fmt(analysis.duration_s)}</text>
      </svg>
      {spikes.length > 0 && <div className={styles.spikes} aria-label="Count spikes">
        {spikes.map((spike) => <button type="button" key={spike.t} onClick={() => onSeek(spike.t)}>
          <b>{fmt(spike.t)}</b> +{spike.gain} vehicles
        </button>)}
      </div>}
    </div>
  );
}

function reviewFindings(analysis, lane, vehicleClass) {
  const lanes = analysis.lanes.filter((item) => !lane || item.name === lane);
  const counts = analysis.samples.map((sample) => countAt(sample, lane, vehicleClass));
  const windowSize = Math.ceil(60 / analysis.step_s);
  let peak = null, busiest = null, gap = null, windowSum = 0;
  for (const [index, sample] of analysis.samples.entries()) {
    const count = counts[index];
    if (!peak || count > peak.value) peak = { at: sample.t, value: count };
    windowSum += count - (counts[index - windowSize] ?? 0);
    if (index >= windowSize - 1 && (!busiest || windowSum / windowSize > busiest.value)) {
      busiest = { at: analysis.samples[index - windowSize + 1].t, value: windowSum / windowSize };
    }
    if (!vehicleClass) for (const { approach } of lanes) {
      const forecast = sample.number?.[approach];
      const observed = sample.then?.[approach]?.number;
      if (forecast == null || observed == null) continue;
      const value = Math.abs(forecast - observed);
      if (!gap || value > gap.value) gap = { at: sample.t, value, approach };
    }
  }
  return [
    { title: "Peak count", result: peak, format: ({ value }) => `${value} vehicles` },
    { title: "Busiest minute", result: busiest, format: ({ value }) => `${value.toFixed(1)} vehicles on average` },
    { title: "Largest forecast difference", result: gap,
      format: ({ value, approach }) => `${value.toFixed(1)} vehicles · approach ${approach}` },
  ];
}

function VideoSummary({ analysis, lane, vehicleClass, onSeek, onExport }) {
  const findings = useMemo(() => reviewFindings(analysis, lane, vehicleClass), [analysis, lane, vehicleClass]);
  const print = () => {
    document.documentElement.dataset.stmsVideoSummary = "true";
    try { window.print(); } finally { delete document.documentElement.dataset.stmsVideoSummary; }
  };
  return (
    <section className={`${styles.card} ${styles.wide} ${styles.brief}`} aria-label="Recording findings" data-video-summary="true">
      <header>
        <h3>Recording findings</h3>
        <p>{analysis.clip} · {analysis.camera} · {fmt(analysis.duration_s)} · {analysis.samples.length.toLocaleString()} samples</p>
        {(lane || vehicleClass) && <p>{lane || "All lanes"} · {vehicleClass || "All vehicle classes"}</p>}
      </header>
      <dl>{findings.map(({ title, result, format }) => (
        <div key={title}>
          <dt>{title}</dt>
          <dd>{result ? <>{format(result)} <button type="button" onClick={() => onSeek(result.at)} aria-label={`Jump to ${title.toLowerCase()} at ${fmt(result.at)}`}>{fmt(result.at)}</button></>
            : vehicleClass && title.includes("forecast") ? "Forecasts use all classes" : "Insufficient data"}</dd>
        </div>
      ))}</dl>
      <p className={styles.small}>Forecast comparisons use detector counts. Peak count measures vehicles in view.</p>
      <div className={styles.summaryActions}>
        <button type="button" className={styles.export} onClick={onExport} data-export="analysis">Export results (CSV)</button>
        <button type="button" className={styles.export} onClick={print}>Print one-page summary</button>
      </div>
    </section>
  );
}

// `handed` (D40) is a finished analysis the local workbench made, read by App from
// its address: null, { status: "loading" }, or what api.get answered. It is checked
// here exactly as an opened file is. The video is still opened by the viewer.
// `assistant` (D41) is given only when the local workbench serves this page: a render
// function for the panel that analyses the opened file where it lies on this computer.
// This file holds the picture and lends it for lane placement; the assistant holds
// everything that talks to the workbench, so nothing here sends anything anywhere.
export function AnalyzeVideo({ view = "operator", handed = null, assistant = null, onAnalysis, onFile, onRejected, seekTo, replay, caps, monitor, browserPreview, legacyFiles = false }) {
  const [video, setVideo] = useState(null);       // { url, name, file }
  const [length, setLength] = useState(null);
  const [aspect, setAspect] = useState(16 / 9);
  const [fullScreen, setFullScreen] = useState(false);
  const [screenProblem, setScreenProblem] = useState("");
  const [monitorStarted, setMonitorStarted] = useState(false);
  const [monitorRevision, setMonitorRevision] = useState(0);
  const [monitorArmed, setMonitorArmed] = useState(false);
  const chooseWhenToStart = Boolean(monitor && caps?.hosted);
  const monitorJob = useRef(null);
  const wantsPlayback = useRef(false);
  const [buffering, setBuffering] = useState(false);
  const [streamComplete, setStreamComplete] = useState(false);
  const streaming = Boolean(monitor && caps?.streaming_demo);
  const liveView = Boolean(monitor || browserPreview);
  const [analysis, setAnalysis] = useState(null);
  const [problem, setProblem] = useState("");
  const [videoProblem, setVideoProblem] = useState("");
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [showLanes, setShowLanes] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);
  const [showClasses, setShowClasses] = useState(false);
  const [laneFilter, setLaneFilter] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const player = useRef(null);
  const viewport = useRef(null);
  const stageRef = useRef(null);
  const region = useTrafficRegions();
  const requestPlayback = (node) => {
    node.play()?.catch(error => {
      // Native play promises are interrupted by intentional pauses, seeks and
      // source changes. Those controls must leave the recording playable.
      if (error.name === "AbortError" || player.current !== node) return;
      wantsPlayback.current = false;
      setBuffering(false);
      setVideoProblem("Playback could not start. Check the video format and try again.");
    });
  };
  // D41: lanes being placed for a new camera, as fractions of the picture.
  const [placing, setPlacing] = useState(false);
  const [points, setPoints] = useState([]);
  const [reach, setReach] = useState(0.25);
  const [preview, setPreview] = useState(null);   // D42: { camera, max_radius, lanes } of the chosen camera
  const lanes = {
    points,
    preview: setPreview,
    begin: () => { setPoints([]); setPlacing(true); if (player.current) player.current.pause(); },
    end: () => { setPlacing(false); setPoints([]); },
    setReach,
    setApproach: (i, a) => setPoints((ps) => ps.map((p, j) => (j === i ? { ...p, approach: a } : p))),
    remove: (i) => setPoints((ps) => ps.filter((_, j) => j !== i)),
  };
  const place = (event) => {
    if (region.draft) { region.updateDraft(event, stageRef.current); return; }
    if (!placing || !stageRef.current || points.length >= 4) return;
    const box = stageRef.current.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width, y = (event.clientY - box.top) / box.height;
    if (!(x >= 0 && x <= 1 && y >= 0 && y <= 1)) return;
    const free = ["N", "S", "E", "W"].find((a) => !points.some((p) => p.approach === a));
    setPoints((ps) => [...ps, { x, y, approach: free }]);
  };
  // `null` clears the page's results: the workbench's assistant does that when another video is opened.
  const resetPlayback = () => {
    wantsPlayback.current = false;
    setBuffering(false);
    setT(0);
    setPlaying(false);
    setMonitorStarted(false);
    if (player.current) {
      if (!player.current.paused) player.current.pause();
      player.current.currentTime = 0;
    }
  };
  const accept = (data, jobId) => {
    if (streaming && data) {
      streamAnalysis(data, jobId);
      setStreamComplete(true);
      return;
    }
    setProblem(""); setAnalysis(data); setFromWorkbench(Boolean(data)); resetPlayback();
    if (monitor) monitorJob.current = jobId ?? null;
    if (data) onAnalysis?.(data, jobId);
  };
  const streamAnalysis = (data, jobId) => {
    if (jobId && monitorJob.current !== jobId) {
      resetPlayback();
      monitorJob.current = jobId;
      wantsPlayback.current = true;
      setStreamComplete(false);
      setMonitorStarted(true);
    }
    if (!data) resetPlayback();
    setAnalysis(data);
  };
  const resetMonitor = (restart) => {
    monitor?.onReset?.();
    resetPlayback();
    setAnalysis(null);
    setStreamComplete(false);
    monitorJob.current = null;
    if (restart) setMonitorRevision(n => n + 1);
    else { region.reset(); setMonitorArmed(false); setVideo(null); setLength(null); }
  };

  useEffect(() => () => { if (video?.file instanceof Blob) URL.revokeObjectURL(video.url); }, [video]);
  useEffect(() => {
    const update = () => setFullScreen(document.fullscreenElement === viewport.current);
    document.addEventListener("fullscreenchange", update);
    return () => document.removeEventListener("fullscreenchange", update);
  }, []);

  const [fromWorkbench, setFromWorkbench] = useState(false);
  useEffect(() => {
    if (!handed) return;
    if (handed.status === "loading") {
      if (replay) { setAnalysis(null); setVideo(null); setLength(null); setT(0); setPlaying(false); }
      return;
    }
    if (handed.status === "empty") { setAnalysis(null); setProblem(""); return; }
    if (handed.status !== "ok") {
      setProblem("These results are unavailable. Check the analysis link and the account that created it.");
      return;
    }
    const checked = validateAnalysis(handed.data);
    if (!checked.ok) { setProblem(`The workbench's results were refused: ${checked.reason}.`); return; }
    setProblem(""); setAnalysis(checked.data); setFromWorkbench(true); setT(0); setPlaying(false);
    if (replay) {
      setVideoProblem(""); setLength(null);
      setVideo(handed.videoUrl ? { url: handed.videoUrl, name: checked.data.processing.filename,
        file: { size: checked.data.processing.source_size } } : null);
    }
  }, [handed, replay]);

  useEffect(() => {
    if (!seekTo) return;
    if (monitor) {
      wantsPlayback.current = false;
      player.current?.pause();
      setBuffering(false);
    }
    const next = seekTo.time;
    setT(next);
    if (player.current) player.current.currentTime = next;
  }, [seekTo]);
  const onProgress = monitor?.onProgress;
  useEffect(() => {
    if (onProgress) onProgress(monitorStarted && analysis && video && !videoProblem ? analysis : null, t);
  }, [analysis, monitorStarted, onProgress, t, video, videoProblem]);

  const watermark = streamComplete ? Infinity : (analysis?.samples.at(-1)?.t ?? 0);
  const limit = useRef(0);
  limit.current = watermark;
  useEffect(() => {
    if (!streaming || !monitorStarted || !player.current || videoProblem || !wantsPlayback.current) return;
    const node = player.current;
    if (node.paused && !node.ended && watermark > node.currentTime + .08) {
      setBuffering(false);
      requestPlayback(node);
    } else if (node.paused && !node.ended) setBuffering(true);
  }, [streaming, monitorStarted, watermark, length, videoProblem]);
  useEffect(() => {
    if (!streaming || !monitorStarted) return undefined;
    let frame;
    const tick = () => {
      const node = player.current;
      if (node && !node.paused && node.currentTime >= limit.current) {
        node.pause();
        node.currentTime = limit.current;
        setT(limit.current);
        if (wantsPlayback.current) setBuffering(true);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [streaming, monitorStarted]);

  // With no picture there is no video clock, so the page keeps its own.
  useEffect(() => {
    if (!playing || video || !analysis) return undefined;
    const started = performance.now(), from = t;
    const timer = setInterval(() => {
      const next = from + ((performance.now() - started) / 1000) * rate;
      if (next >= analysis.duration_s) { setT(analysis.duration_s); setPlaying(false); } else setT(next);
    }, 200);
    return () => clearInterval(timer);
    // `t` is the starting point only: restarting on every tick would stall the clock.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, video, analysis, rate]);

  const maxBytes = caps?.max_video_bytes ?? 2 * 1024 ** 3;
  const uploadSize = maxBytes >= 1024 ** 3 ? maxBytes / 1024 ** 3 + " GB" : maxBytes / 1024 ** 2 + " MiB";
  const openVideo = (file) => {
    if (!file) return;
    region.reset();
    if (!/\.(mp4|m4v|avi|webm|mov|mkv)$/i.test(file.name)) {
      setVideo(null); setAnalysis(null); resetPlayback(); onRejected?.(file, "format");
      setVideoProblem(`${file.name} is unsupported. Choose MP4, MOV, AVI, MKV, M4V or WebM.`);
      return;
    }
    if (file.size === 0 || file.size > maxBytes) {
      setVideo(null); setAnalysis(null); resetPlayback(); onRejected?.(file, "size");
      setVideoProblem("The recording must be non-empty and no larger than " + uploadSize + ".");
      return;
    }
    onFile?.(file);
    if (monitor) {
      setMonitorArmed(false);
      setAnalysis(null); resetPlayback(); setStreamComplete(false); monitorJob.current = null;
    }
    if (caps?.uploads || (analysis && (file.name.replace(/\.[^.]+$/, "") !== analysis.clip
        || (analysis.processing && file.size !== analysis.processing.source_size)))) setAnalysis(null);
    setVideoProblem(""); setScreenProblem(""); setLength(null); setT(0); setPlaying(false); setAspect(16 / 9);
    setVideo({ url: URL.createObjectURL(file), name: file.name, file });
  };
  const openResults = async (file) => {
    if (!file) return;
    let json;
    try { json = JSON.parse(await file.text()); } catch { setProblem(`${file.name} is not a results file.`); setAnalysis(null); return; }
    const checked = validateAnalysis(json);
    if (!checked.ok) { setProblem(`${file.name} was refused: ${checked.reason}.`); setAnalysis(null); return; }
    setProblem(""); setAnalysis(checked.data); setFromWorkbench(false); resetPlayback();
    onAnalysis?.(checked.data);
  };
  const seek = (value) => {
    const end = length ?? analysis?.duration_s ?? 0;
    const next = Math.min(Math.max(value, 0), end);
    setT(next);
    if (player.current) player.current.currentTime = next;
    else setPlaying(false);
  };
  const togglePlay = () => {
    if (player.current) {
      if (streaming && wantsPlayback.current && !player.current.ended) {
        wantsPlayback.current = false;
        player.current.pause();
        setBuffering(false);
        return;
      }
      if (player.current.paused) {
        if (monitor) setMonitorStarted(true);
        if (streaming) {
          if (player.current.ended) seek(0);
          wantsPlayback.current = true;
          if (watermark <= player.current.currentTime + .08) { setBuffering(true); return; }
        }
        requestPlayback(player.current);
      } else player.current.pause();
      return;
    }
    if (analysis) { if (t >= analysis.duration_s) setT(0); setPlaying(!playing); }
  };
  const changeRate = () => {
    const next = { 1: 2, 2: 4, 4: 8, 8: 1 }[rate];
    setRate(next);
    if (player.current) player.current.playbackRate = next;
  };
  const toggleFullScreen = async () => {
    setScreenProblem("");
    try {
      if (document.fullscreenElement === viewport.current) await document.exitFullscreen();
      else await viewport.current.requestFullscreen();
    } catch {
      setScreenProblem("Full-screen is unavailable in this browser window.");
    }
  };

  const pictureReady = Boolean(video && length !== null && !videoProblem);
  const durationMismatch = video && analysis && length !== null && Math.abs(length - analysis.duration_s) > LENGTH_TOLERANCE_S;
  // A hint, not a refusal: a renamed copy is the same recording. The length check refuses.
  const otherName = video && analysis && video.name.replace(/\.[^.]+$/, "") !== analysis.clip;
  const identityMismatch = analysis?.processing && video && (otherName || video.file.size !== analysis.processing.source_size);
  const mismatch = durationMismatch || identityMismatch;
  const synced = analysis && !mismatch;
  const instant = synced && (!monitor || monitorStarted) ? sampleAt(analysis, t) : null;
  const sample = instant && monitor ? { ...instant, then: null } : instant;
  const vehicleClasses = useMemo(() => monitor ? [] : [...new Set(analysis?.samples.flatMap((row) =>
    row.detections?.map(([label]) => label) ?? []) ?? [])].sort(), [analysis, monitor]);
  const wholeFrame = analysis?.traffic?.scope === "frame";
  const lane = analysis?.lanes.some(({ name }) => name === laneFilter) ? laneFilter : "";
  const vehicleClass = vehicleClasses.includes(classFilter) ? classFilter : "";
  const showDetection = (index) => {
    const detection = sample?.detections?.[index];
    const visible = !analysis?.traffic || detection?.[1] >= analysis.min_confidence || (sample.track_ids?.[index] != null && detection?.[1] >= .25);
    return visible && (!lane || detection?.[2] === lane) && (!vehicleClass || detection?.[0] === vehicleClass);
  };
  const end = length ?? analysis?.duration_s ?? 0;
  // Drag-and-drop onto either picker: the same checks as choosing the file.
  const dropTo = (open) => ({
    onDragOver: (e) => { e.preventDefault(); e.currentTarget.dataset.over = "true"; },
    onDragLeave: (e) => { delete e.currentTarget.dataset.over; },
    onDrop: (e) => { e.preventDefault(); delete e.currentTarget.dataset.over; open(e.dataTransfer.files[0]); },
  });
  // The results as a table: one row per 2 s sample, counts per lane, then each
  // approach's level and vehicle forecast. Numbers only, never a frame.
  const exportCsv = () => {
    const lanesOf = analysis.lanes.map((l) => l.name), appr = analysis.lanes.map((l) => l.approach);
    const cols = ["time_s", ...lanesOf.map((l) => `count_${l}`), ...appr.map((a) => `level_${a}`), ...appr.map((a) => `next_minute_${a}`), "detections"];
    const rows = analysis.samples.map((x) => Object.fromEntries([["time_s", x.t],
      ...lanesOf.map((l) => [`count_${l}`, x.counts[l]]), ...appr.map((a) => [`level_${a}`, x.level?.[a] ?? ""]),
      ...appr.map((a) => [`next_minute_${a}`, x.number?.[a] ?? ""]), ["detections", x.boxes.length]]));
    downloadText(`${analysis.clip}.analysis.csv`, toCsv(cols, rows));
  };
  const resultsPicker = (
    <label className={styles.drop} {...dropTo(openResults)}>
      <input type="file" accept=".json,application/json" data-open-results="true" onChange={(e) => openResults(e.target.files[0])} />
      <b>{analysis ? `${analysis.clip} · ${analysis.camera}` : handed?.status === "loading" ? "Loading the workbench's results" : "Choose a results file"}</b>
      <span className={styles.small}>{fromWorkbench ? "Made by the workbench on this computer, and checked here." : "Made once per video by the analysis tool, on the computer that holds it."}</span>
    </label>
  );
  return (
    <section aria-label={browserPreview ? "Demo Live video preview" : monitor ? "Demo Live monitoring player" : replay ? "Guided replay" : "Analyze a video"} data-tour={liveView ? undefined : "analyze"}>
      {!liveView && <div className={styles.intro}>
        <h2>{replay ? "Guided replay" : "Analyze a video"}</h2>
        <p>{replay ? "Inspect a completed recording and its saved detections." : "Upload a traffic video for detection, tracking and a saved report."}</p>
      </div>}
      {monitor?.tools}
      {monitor && assistant?.({ file: videoProblem || (chooseWhenToStart && !monitorArmed) ? null : video?.file, duration: length, revision: monitorRevision,
        onResults: accept, onStream: streamAnalysis })}
      {liveView && !video && <>
        <label className={`${styles.drop} ${styles.liveDrop}`} {...dropTo(openVideo)}>
          <input type="file" aria-label="Choose a video for live monitoring" accept="video/*,.mp4,.avi,.mov,.m4v,.mkv,.webm"
            data-open-video="true" onChange={e => openVideo(e.target.files[0])} />
          <span className={styles.uploadIcon} aria-hidden="true">↑</span>
          <b>Upload Traffic Video for Live Monitoring</b>
          <span className={styles.small}>{chooseWhenToStart ? "Choose a recording, then start monitoring." : "Drop a video here. Playback starts when the feed is ready."}</span>
          <span className={styles.browseVideo}>Browse Video</span>
          <span className={styles.small}>MP4, AVI, MOV, MKV, M4V or WebM · Up to {uploadSize}</span>
        </label>
        {videoProblem && <p className={panel.problem} role="alert">{videoProblem}</p>}
      </>}
      {(!liveView || video) && <div className={liveView ? (monitor ? styles.liveWatchLayout : styles.livePreviewLayout) : `${styles.layout} ${assistant ? styles.withAssistant : ""}`}>
        {!liveView && <section className={styles.card} aria-label="Choose the files" data-tour="analyze-files">
          <h3>{replay ? "Video source" : "Upload traffic video"}</h3>
          {(!replay || !handed?.videoUrl) && <label className={styles.drop} {...dropTo(openVideo)}>
            <input type="file" accept="video/*,.mp4,.avi,.mov,.m4v,.mkv,.webm" data-open-video="true" onChange={(e) => openVideo(e.target.files[0])} />
            <b>{video ? video.name : "Choose a video, or drop it here"}</b>
            <span className={styles.small}>{video ? `${(video.file.size / 1024 ** 2).toFixed(2)} MB${length == null ? "" : ` · ${fmt(length)}`}`
              : "Browse files · MP4, AVI, MOV, MKV, M4V or WebM"}</span>
          </label>}
          {replay && handed?.videoUrl && <p className={styles.notice}>{video?.name ?? "Loading saved video…"}</p>}
          {videoProblem && <p className={panel.problem} role="alert" data-state="invalid">{videoProblem}</p>}
          {length !== null && length < 120 && <p className={styles.note}>
            {caps?.uploads && length < caps.minimum_duration_s
              ? `Choose a recording at least ${caps.minimum_duration_s} seconds long.`
              : "Short recordings support detection and counting. The next-minute count forecast needs about two minutes of history."}
          </p>}
          {assistant && assistant({ file: video?.file ?? null, duration: length ?? undefined, lanes, onResults: accept, onStream: streamAnalysis })}
          {!assistant && !replay && !legacyFiles && <div className={styles.note}>
            <p role="status">{caps === null ? "Checking the AI analysis service…" : "The AI analysis service is unavailable on this site. You can still preview your video here."}</p>
          </div>}
          {fromWorkbench && analysis && !video && (
            <p className={styles.notice} data-handed="true">Saved results are available. If the original video was kept outside STMS, choose <b>{analysis.processing?.filename ?? analysis.clip}</b> to see its overlays.</p>
          )}
          {otherName && <p className={styles.notice} data-state="name-differs">This video is named {video.name}; the results are for {analysis.clip}.</p>}
          {legacyFiles && (assistant ? (
            <details className={styles.how}><summary>Open existing results</summary>{resultsPicker}</details>
          ) : <><h3>2. Open its results</h3>{resultsPicker}</>)}
          {problem && <p className={panel.problem} data-state="invalid">{problem}</p>}
          {analysis && !synced && <button type="button" className={styles.export} onClick={exportCsv} data-export="analysis">Export results (CSV)</button>}
          {legacyFiles && !analysis && !assistant && (
            <details className={styles.how} data-analysis-how="true">
              <summary>How to make a results file</summary>
              <p>Run this on the computer with the detector, naming the camera that recorded the video:</p>
              <code>{COMMAND}</code>
              <p>Choose the recording's camera profile. Forecasts appear once enough history is available.</p>
            </details>
          )}
          {analysis?.known_limits.length > 0 && (
            <div className={styles.limits} data-known-limits="true"><h3>Known limits of this camera</h3><ul>{analysis.known_limits.map((l) => <li key={l}>{l}</li>)}</ul></div>
          )}
        </section>}

        <section className={styles.card} aria-label="Watch" data-tour="analyze-watch">
          <h3>{liveView ? "Demo Live feed" : "Video preview"}</h3>
          {liveView && <p className={styles.liveFilename}>{video.name}</p>}
          <div className={styles.playerViewport} ref={viewport}>
          <div className={styles.stageFrame}>
          <div className={`${styles.stage} ${placing || region.draft ? styles.placing : ""}`} style={{ "--video-aspect": aspect }} data-stage="true"
               ref={stageRef} onClick={place} data-placing={placing || undefined}>
            {video ? (
              <video ref={player} src={video.url} muted playsInline data-player="true"
                     onLoadedMetadata={(e) => {
                       const player = e.currentTarget;
                       setLength(player.duration);
                       if (player.videoWidth && player.videoHeight) setAspect(player.videoWidth / player.videoHeight);
                       player.playbackRate = rate;
                       if (browserPreview) requestPlayback(player);
                       if (seekTo && analysis && video.name.replace(/\.[^.]+$/, "") === analysis.clip) {
                         player.currentTime = Math.min(seekTo.time, player.duration);
                       }
                     }}
                     onTimeUpdate={(e) => setT(Math.min(e.target.currentTime, streaming ? limit.current : Infinity))} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
                     onEnded={() => {
                       if (monitor && analysis) {
                         wantsPlayback.current = false;
                         monitor.onFinish(analysis, monitorJob.current);
                       }
                     }}
                     onError={() => setVideoProblem("This browser cannot play this video's format. MP4 with H.264 usually works.")} />
            ) : <p className={styles.noPicture}>{replay && handed?.status === "loading" ? "Loading the saved session…"
              : replay ? "A saved video appears here when its session is selected." : "Choose a video to preview it here."}</p>}
            {pictureReady && <span className={`${styles.tag} ${monitor || browserPreview ? styles.liveTag : ""}`}>
              {monitor || browserPreview ? <><b>LIVE MONITORING</b><small>Demo / Recorded source</small></> : "Recorded video"}
            </span>}
            {video && !videoProblem && preview && !placing && !analysis && (
              <>
                <svg className={styles.boxes} viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
                  {preview.lanes.map((l) => <ellipse key={l.name} className={styles.reach} cx={l.centre[0]} cy={l.centre[1]} rx={preview.max_radius} ry={preview.max_radius} vectorEffect="non-scaling-stroke" />)}
                </svg>
                {preview.lanes.map((l, i) => (
                  <span key={l.name} className={`${styles.pin} ${styles.previewPin}`} data-preview-lane={`L${i}`} style={{ left: `${l.centre[0] * 100}%`, top: `${l.centre[1] * 100}%` }}><b>L{i}</b> {l.approach}</span>
                ))}
                <span className={styles.placeHint} data-preview-hint="true">{preview.camera}'s lanes: do they sit on this video's roads?</span>
              </>
            )}
            {video && !videoProblem && placing && (
              <>
                <svg className={styles.boxes} viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
                  {points.map((p, i) => <ellipse key={i} className={styles.reach} cx={p.x} cy={p.y} rx={reach} ry={reach} vectorEffect="non-scaling-stroke" />)}
                </svg>
                {points.map((p, i) => (
                  <span key={i} className={styles.pin} data-placed={`L${i}`} style={{ left: `${p.x * 100}%`, top: `${p.y * 100}%` }}><b>L{i}</b> {p.approach}</span>
                ))}
                <span className={styles.placeHint}>{points.length < 4 ? `Click a lane's centre (${points.length} of up to 4)` : "Four lanes placed"}</span>
              </>
            )}
            {pictureReady && (region.active.length > 0 || region.draft || region.trails) && <RegionOverlay region={region} result={synced ? analysis : null} time={t} />}
            {pictureReady && sample && showBoxes && (
              <svg className={styles.boxes} viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
                {showLanes && analysis.traffic?.lines.map(({ lane: name, endpoints: [[x1, y1], [x2, y2]] }) =>
                  <line key={name} x1={x1} y1={y1} x2={x2} y2={y2} vectorEffect="non-scaling-stroke" />)}
                {sample.boxes.map(([x1, y1, x2, y2], i) => showDetection(i) &&
                  <rect key={i} data-box="true" x={x1} y={y1} width={x2 - x1} height={y2 - y1} vectorEffect="non-scaling-stroke" />)}
              </svg>
            )}
            {pictureReady && sample && ((view === "engineering" && showClasses) || (analysis.traffic && showBoxes)) && sample.detections?.map(([cls, confidence], i) => showDetection(i) && (
              <span key={i} className={styles.classLabel} data-box-class="true" style={{ left: `${sample.boxes[i][0] * 100}%`, top: `${sample.boxes[i][1] * 100}%` }}>{cls}{sample.track_ids?.[i] != null && ` #${sample.track_ids[i]}`} · {Math.round(confidence * 100)}%</span>
            ))}
            {pictureReady && sample && showLanes && !wholeFrame && analysis.lanes.map(({ name, centre }, i) => (!lane || name === lane) && (
              <span key={name} className={styles.pin} data-pin={`L${i}`} style={{ left: `${centre[0] * 100}%`, top: `${centre[1] * 100}%` }}><b>L{i}</b> {countAt(sample, name, vehicleClass)}</span>
            ))}
          </div>
          </div>
          {videoProblem && video && <p className={panel.problem}>{videoProblem}</p>}
          {mismatch && (
            <p className={panel.stale} data-state="mismatch">
              <span className={panel.staleMark} aria-hidden="true" />
              <span><b>These files do not match.</b> {identityMismatch ? `Open ${analysis.processing.filename} to see its overlays.`
                : `The video is ${fmt(length)} long and the results cover ${fmt(analysis.duration_s)}, so no results are shown over it.`}</span>
            </p>
          )}
          {(video || analysis) && <div className={styles.transport}>
            <button type="button" onClick={togglePlay} disabled={monitor ? !synced || !pictureReady || t >= end : !video && !analysis} data-play="true">
              {playing || buffering ? "Pause" : monitor && t < end ? "Resume" : "Play"}
            </button>
            <input type="range" min="0" max={end} step="1" value={Math.min(t, end)} aria-label="Position in the video" disabled={!end || Boolean(monitor)} onChange={(e) => seek(Number(e.target.value))} />
            <span className={styles.mono}>{fmt(t)} / {fmt(end)}</span>
            {!monitor && <button type="button" onClick={changeRate} aria-label="Playback speed">{rate}×</button>}
            {pictureReady && <button type="button" className={styles.fullScreenButton} onClick={toggleFullScreen}>
              {fullScreen ? "Exit full screen" : "Full screen"}
            </button>}
          </div>}
          {replay && analysis?.traffic?.alerts.length > 0 && <div role="group" aria-label="Replay alert markers" className={styles.summaryActions}>
            {analysis.traffic.alerts.map(event => <button key={event.id} type="button" className={styles.export}
              onClick={() => seek(event.t)}>{fmt(event.t)} · {event.type}</button>)}
          </div>}
          {liveView && <div className={styles.summaryActions}>
            {chooseWhenToStart && !monitorArmed && <button type="button" className={styles.export}
              disabled={!pictureReady || Boolean(videoProblem) || caps.analysis_ready === false}
              onClick={() => setMonitorArmed(true)}>Start monitoring</button>}
            {chooseWhenToStart && caps.analysis_ready === false && <p role="alert">{caps.analysis_problem}</p>}
            <button type="button" className={styles.export} onClick={() => resetMonitor(false)}>Stop</button>
            {monitor && (!chooseWhenToStart || monitorArmed) && <button type="button" className={styles.export} onClick={() => resetMonitor(true)}>Restart</button>}
          </div>}
          {pictureReady && !region.draft && monitor?.calibration?.({ file: video.file, lanes })}
          {pictureReady && !placing && <TrafficRegions region={region} result={synced ? analysis : null} time={t} live={liveView}
            pause={() => { wantsPlayback.current = false; setBuffering(false); player.current?.pause(); }} />}
          {buffering && <p className={styles.small} role="status">Buffering live detections. Playback resumes when the next sample is ready.</p>}
          {screenProblem && <p className={styles.small} role="status">{screenProblem}</p>}
          </div>
          {synced && (
            <div className={styles.toggles}>
              {!wholeFrame && <label>Lane <select value={lane} onChange={(event) => setLaneFilter(event.target.value)}>
                <option value="">Analyze all configured lanes</option>
                {analysis.lanes.map(({ name, approach }, i) => <option key={name} value={name}>L{i} · {approach}</option>)}
              </select></label>}
              {vehicleClasses.length > 0 && <label>Vehicle class <select value={vehicleClass} onChange={(event) => setClassFilter(event.target.value)}>
                <option value="">All classes</option>
                {vehicleClasses.map((label) => <option key={label} value={label}>{label}</option>)}
              </select></label>}
              {pictureReady && <>
                {!wholeFrame && <label><input type="checkbox" checked={showLanes} onChange={(e) => setShowLanes(e.target.checked)} /> Lane markers</label>}
                <label><input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} /> Vehicle boxes</label>
                {view === "engineering" && sample?.detections && <label><input type="checkbox" checked={showClasses} data-show-classes="true" onChange={(e) => setShowClasses(e.target.checked)} /> Class labels</label>}
                <span className={styles.small}>Boxes update every 2 seconds, the rate the system samples at.</span>
              </>}
            </div>
          )}
        </section>
        {monitor?.panel}

        {synced && !monitor && !wholeFrame && <VideoSummary analysis={analysis} lane={lane} vehicleClass={vehicleClass} onSeek={seek} onExport={exportCsv} />}

        {!liveView && <section className={styles.card} aria-label="Results at this moment" data-tour="analyze-results">
          <h3>At {fmt(t)}</h3>
          {sample ? <Results analysis={analysis} sample={sample} lane={lane} vehicleClass={vehicleClass} />
            : <p className={styles.absent} data-state="no-results">{mismatch ? "Choose the video that matches this analysis." : "Vehicle counts and forecasts appear here when analysis is available."}</p>}
          {sample && !wholeFrame && !analysis.directions_verified && <p className={styles.notice} data-directions="unverified">N, S, E and W are labels. Their directions have not been verified for this camera.</p>}
          {synced && analysis.models?.scene && <SceneForecast result={analysis} sample={sample} />}
        </section>}

        {sample && view === "engineering" && <VideoEngineering analysis={analysis} sample={sample} className={`${styles.card} ${styles.wide}`} />}

        {synced && !monitor && !wholeFrame && (
          <section className={`${styles.card} ${styles.wide}`} aria-label="The whole video">
            <h3>The whole video <span className={styles.small}>Forecast level. Click to jump there.</span></h3>
            <Timeline analysis={analysis} t={t} onSeek={seek} />
            <CountTimeline analysis={analysis} t={t} onSeek={seek} lane={lane} vehicleClass={vehicleClass} />
          </section>
        )}
        {synced && !monitor && !wholeFrame && <VideoCheck analysis={analysis} t={t} onSeek={seek} />}
      </div>}
      {!liveView && <p className={styles.small}>{caps?.uploads ? "Starting analysis uploads the recording to STMS for processing and saved replay." : "The preview uses your local video file."} Signal recommendations are advisory.</p>}
    </section>
  );
}
