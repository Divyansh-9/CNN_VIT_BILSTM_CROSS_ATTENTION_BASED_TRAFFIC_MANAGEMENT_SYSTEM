import { useEffect, useMemo, useRef, useState } from "react";
import panel from "./Panels.module.css";
import styles from "./Analyze.module.css";
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

function Results({ analysis, sample }) {
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
              const level = sample.level?.[approach], then = sample.then?.[approach];
              return (
                <tr key={name} data-analysis-row={name}>
                  <th scope="row"><b>L{i}</b> <span className={styles.muted}>{analysis.directions_verified ? `from ${approach}` : `label ${approach}`}</span></th>
                  <td className={styles.mono}>{sample.counts[name]}</td>
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

export function AnalyzeVideo() {
  const [video, setVideo] = useState(null);       // { url, name }
  const [length, setLength] = useState(null);
  const [aspect, setAspect] = useState("16 / 9");
  const [analysis, setAnalysis] = useState(null);
  const [problem, setProblem] = useState("");
  const [videoProblem, setVideoProblem] = useState("");
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [showLanes, setShowLanes] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);
  const player = useRef(null);

  useEffect(() => () => { if (video) URL.revokeObjectURL(video.url); }, [video]);

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

  const openVideo = (file) => {
    if (!file) return;
    if (!file.type.startsWith("video/") && !/\.(mp4|webm|mov|mkv)$/i.test(file.name)) {
      setVideoProblem(`${file.name} is not a video.`);
      return;
    }
    setVideoProblem(""); setLength(null); setT(0); setPlaying(false); setAspect("16 / 9");
    setVideo({ url: URL.createObjectURL(file), name: file.name });
  };
  const openResults = async (file) => {
    if (!file) return;
    let json;
    try { json = JSON.parse(await file.text()); } catch { setProblem(`${file.name} is not a results file.`); setAnalysis(null); return; }
    const checked = validateAnalysis(json);
    if (!checked.ok) { setProblem(`${file.name} was refused: ${checked.reason}.`); setAnalysis(null); return; }
    setProblem(""); setAnalysis(checked.data); setT(0); setPlaying(false);
  };
  const seek = (value) => {
    const end = length ?? analysis?.duration_s ?? 0;
    const next = Math.min(Math.max(value, 0), end);
    setT(next);
    if (player.current) player.current.currentTime = next;
  };
  const togglePlay = () => {
    if (player.current) { if (player.current.paused) player.current.play(); else player.current.pause(); return; }
    if (analysis) { if (t >= analysis.duration_s) setT(0); setPlaying(!playing); }
  };
  const changeRate = () => {
    const next = { 1: 2, 2: 4, 4: 8, 8: 1 }[rate];
    setRate(next);
    if (player.current) player.current.playbackRate = next;
  };

  const mismatch = video && analysis && length !== null && Math.abs(length - analysis.duration_s) > LENGTH_TOLERANCE_S;
  const synced = analysis && !mismatch;
  const sample = synced ? sampleAt(analysis, t) : null;
  const end = length ?? analysis?.duration_s ?? 0;
  return (
    <section aria-label="Analyze a video" data-tour="analyze">
      <div className={styles.intro}>
        <h2>Analyze a video</h2>
        <p>Watch a recording with its counts and forecasts beside the picture. It is always a recording, never live.</p>
      </div>
      <div className={styles.layout}>
        <section className={styles.card} aria-label="Choose the files" data-tour="analyze-files">
          <h3>1. Open the video</h3>
          <label className={styles.drop}>
            <input type="file" accept="video/*" data-open-video="true" onChange={(e) => openVideo(e.target.files[0])} />
            <b>{video ? video.name : "Choose a video"}</b>
            <span className={styles.small}>It plays in this browser. Nothing is uploaded.</span>
          </label>
          {videoProblem && <p className={panel.problem} data-state="invalid">{videoProblem}</p>}
          <h3>2. Open its results</h3>
          <label className={styles.drop}>
            <input type="file" accept=".json,application/json" data-open-results="true" onChange={(e) => openResults(e.target.files[0])} />
            <b>{analysis ? `${analysis.clip} · ${analysis.camera}` : "Choose a results file"}</b>
            <span className={styles.small}>Made once per video by the analysis tool, on the computer that holds it.</span>
          </label>
          {problem && <p className={panel.problem} data-state="invalid">{problem}</p>}
          {!analysis && (
            <details className={styles.how} data-analysis-how="true">
              <summary>How to make a results file</summary>
              <p>Run this on the computer with the detector, naming the camera that recorded the video:</p>
              <code>{COMMAND}</code>
              <p>The video must be at least 5 minutes long, and the camera needs a profile in the cameras folder.</p>
            </details>
          )}
          {analysis?.known_limits.length > 0 && (
            <div className={styles.limits} data-known-limits="true"><h3>Known limits of this camera</h3><ul>{analysis.known_limits.map((l) => <li key={l}>{l}</li>)}</ul></div>
          )}
        </section>

        <section className={styles.card} aria-label="Watch" data-tour="analyze-watch">
          <h3>3. Watch</h3>
          <div className={styles.stage} style={{ aspectRatio: aspect }} data-stage="true">
            {video ? (
              <video ref={player} src={video.url} muted playsInline data-player="true"
                     onLoadedMetadata={(e) => { setLength(e.target.duration); if (e.target.videoWidth) setAspect(`${e.target.videoWidth} / ${e.target.videoHeight}`); e.target.playbackRate = rate; }}
                     onTimeUpdate={(e) => setT(e.target.currentTime)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
                     onError={() => setVideoProblem("This browser cannot play this video's format. MP4 with H.264 usually works.")} />
            ) : <p className={styles.noPicture}>{analysis ? "No picture: the numbers only" : "Open a video, its results, or both"}</p>}
            <span className={styles.tag}>Recording</span>
            {sample && showBoxes && (
              <svg className={styles.boxes} viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
                {sample.boxes.map(([x1, y1, x2, y2], i) => <rect key={i} data-box="true" x={x1} y={y1} width={x2 - x1} height={y2 - y1} vectorEffect="non-scaling-stroke" />)}
              </svg>
            )}
            {sample && showLanes && analysis.lanes.map(({ name, centre }, i) => (
              <span key={name} className={styles.pin} data-pin={`L${i}`} style={{ left: `${centre[0] * 100}%`, top: `${centre[1] * 100}%` }}><b>L{i}</b> {sample.counts[name]}</span>
            ))}
          </div>
          {videoProblem && video && <p className={panel.problem}>{videoProblem}</p>}
          {mismatch && (
            <p className={panel.stale} data-state="mismatch">
              <span className={panel.staleMark} aria-hidden="true" />
              <span><b>These files do not match.</b> The video is {fmt(length)} long and the results cover {fmt(analysis.duration_s)}, so no results are shown over it.</span>
            </p>
          )}
          <div className={styles.transport}>
            <button type="button" onClick={togglePlay} disabled={!video && !analysis} data-play="true">{playing ? "Pause" : "Play"}</button>
            <input type="range" min="0" max={end} step="1" value={Math.min(t, end)} aria-label="Position in the video" disabled={!end} onChange={(e) => seek(Number(e.target.value))} />
            <span className={styles.mono}>{fmt(t)} / {fmt(end)}</span>
            <button type="button" onClick={changeRate} aria-label="Playback speed">{rate}×</button>
          </div>
          {synced && (
            <div className={styles.toggles}>
              <label><input type="checkbox" checked={showLanes} onChange={(e) => setShowLanes(e.target.checked)} /> Lane markers</label>
              <label><input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} /> Vehicle boxes</label>
              <span className={styles.small}>Boxes update every 2 seconds, the rate the system samples at.</span>
            </div>
          )}
        </section>

        <section className={styles.card} aria-label="Results at this moment" data-tour="analyze-results">
          <h3>At {fmt(t)}</h3>
          {sample ? <Results analysis={analysis} sample={sample} />
            : <p className={styles.absent} data-state="no-results">{mismatch ? "Open the results for this video." : "No results yet. Open a results file to see counts and forecasts here."}</p>}
          {sample && !analysis.directions_verified && <p className={styles.notice} data-directions="unverified">N, S, E and W are labels. Their directions have not been verified for this camera.</p>}
        </section>

        {synced && (
          <section className={`${styles.card} ${styles.wide}`} aria-label="The whole video">
            <h3>The whole video <span className={styles.small}>Forecast level. Click to jump there.</span></h3>
            <Timeline analysis={analysis} t={t} onSeek={seek} />
          </section>
        )}
      </div>
      <p className={styles.small}>The video stays on this computer. Results hold counts and forecasts, never frames. A recording is not a live camera test, and nothing here controls a signal.</p>
    </section>
  );
}
