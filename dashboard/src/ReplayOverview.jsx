import { useEffect, useState } from "react";
import { Icon } from "./icons.jsx";
import { COUNT_BENCHMARK } from "./explorerContent.js";
import { JunctionMap } from "./Intersection.jsx";
import panelStyles from "./Panels.module.css";
import {
  APPROACHES, APPROACH_NAMES, DEMO_LENGTH, FORECAST_HORIZON, GUIDED_CHAPTERS,
  SAMPLE_INTERVAL, comparisonAt, forecastLevel, replayAt, replayTime,
} from "./replaySample.js";
import styles from "./ReplayOverview.module.css";

const SPEEDS = [1, 4, 8, 16];
const WIDTH = 680;
const LEFT = 40;
const RIGHT = WIDTH - 34;
const TOP = 22;
const BOTTOM = 168;
const TIME_TICKS = [0, 60, 120, 180, 240, DEMO_LENGTH];
const COUNT_TICKS = [0, 7, 14, 21, 28];
const x = (at) => LEFT + at / DEMO_LENGTH * (RIGHT - LEFT);
const y = (value) => BOTTOM - value / COUNT_TICKS.at(-1) * (BOTTOM - TOP);
const displayCount = (value) => value === null ? "Unavailable" : value.toFixed(1);

function seriesPath(rows, key) {
  return rows.map((row, i) => {
    if (row[key] === null) return "";
    const move = i === 0 || rows[i - 1][key] === null ? "M" : "L";
    return `${move}${x(row.at)},${y(row[key])}`;
  }).join(" ");
}

function ForecastComparison({ playhead, direction, onSeek, highlightOutage = false }) {
  const [hovered, setHovered] = useState(null);
  const rows = comparisonAt(playhead, APPROACHES.indexOf(direction));
  const current = Math.floor(playhead / SAMPLE_INTERVAL);
  const row = rows[hovered ?? current];
  const blackoutStart = GUIDED_CHAPTERS[1].at;
  const blackoutEnd = Math.min(playhead, GUIDED_CHAPTERS[2].at);
  const indexAt = (event) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    if (!bounds.width) return current;
    const coordinate = (event.clientX - bounds.left) / bounds.width * WIDTH;
    const frame = Math.round((coordinate - LEFT) / (RIGHT - LEFT) * (rows.length - 1));
    return Math.max(0, Math.min(frame, rows.length - 1));
  };
  return (
    <section className={`${styles.card} ${styles.comparison}`} aria-labelledby="replay-comparison">
      <header className={styles.cardHead}>
        <div>
          <h3 id="replay-comparison">Forecast vs. observed</h3>
          <p>{APPROACH_NAMES[direction]} approach · Mean vehicles in view over each 60-second window</p>
        </div>
        <ul className={styles.legend} aria-label="Chart series">
          <li><i />Observed</li>
          <li><i />Earlier forecast</li>
          <li className={styles.gapKey}><i />Forecast difference</li>
        </ul>
      </header>
      <svg viewBox={`0 0 ${WIDTH} 200`} className={styles.chart} aria-hidden="true"
           onPointerMove={(event) => setHovered(indexAt(event))} onPointerLeave={() => setHovered(null)}
           onClick={onSeek ? (event) => onSeek(rows[indexAt(event)].at) : undefined}>
        {COUNT_TICKS.map((tick) => (
          <g key={tick}>
            <line x1={LEFT} x2={RIGHT} y1={y(tick)} y2={y(tick)} className={styles.gridLine} />
            <text x={LEFT - 9} y={y(tick) + 4} textAnchor="end">{tick}</text>
          </g>
        ))}
        {TIME_TICKS.map((tick) => <text key={tick} x={x(tick)} y="189" textAnchor="middle">{replayTime(tick)}</text>)}
        {highlightOutage && blackoutEnd > blackoutStart &&
          <rect className={styles.outageBand} x={x(blackoutStart)} y={TOP} width={x(blackoutEnd) - x(blackoutStart)} height={BOTTOM - TOP} />}
        {row.issuedAt !== null && row.forecast !== null && (
          <g>
            <line x1={x(row.issuedAt)} x2={x(row.issuedAt)} y1={TOP} y2={BOTTOM} className={styles.issueLine} />
            <text x={x(row.issuedAt) + 5} y="14" className={styles.issueLabel}>Forecast issued</text>
          </g>
        )}
        <line x1={x(row.at)} x2={x(row.at)} y1={TOP} y2={BOTTOM} className={styles.cursorLine} />
        {rows.slice(1).map((point, index) => {
          const previous = rows[index];
          if ([previous.observed, previous.forecast, point.observed, point.forecast].includes(null)) return null;
          return <path key={point.at} className={styles.difference}
                       d={`M${x(previous.at)},${y(previous.observed)} L${x(point.at)},${y(point.observed)} L${x(point.at)},${y(point.forecast)} L${x(previous.at)},${y(previous.forecast)} Z`} />;
        })}
        <path d={seriesPath(rows, "observed")} className={styles.observedLine} />
        <path d={seriesPath(rows, "forecast")} className={styles.forecastLine} />
        {rows.filter((point) => point.observed !== null).map((point) => (
          <circle key={point.at} cx={x(point.at)} cy={y(point.observed)} r="2.6" className={styles.observedPoint} />
        ))}
        {rows.filter((point) => point.forecast !== null).map((point) => (
          <circle key={point.at} cx={x(point.at)} cy={y(point.forecast)} r="2.6" className={styles.forecastPoint} />
        ))}
        {row.observed !== null && <circle cx={x(row.at)} cy={y(row.observed)} r="5" className={styles.observedPoint} />}
        {row.forecast !== null && <circle cx={x(row.at)} cy={y(row.forecast)} r="5" className={styles.forecastPoint} />}
      </svg>
      <dl className={styles.chartReadout} aria-label="Chart values at the selected time">
        <div><dt>Window ending</dt><dd>{replayTime(row.at)}</dd></div>
        <div><dt>Observed mean</dt><dd>{displayCount(row.observed)}</dd></div>
        <div><dt>Earlier forecast</dt><dd>{displayCount(row.forecast)}</dd></div>
        <div><dt>Issued at</dt><dd>{row.forecast === null ? "Unavailable" : replayTime(row.issuedAt)}</dd></div>
        <div><dt>Absolute difference</dt><dd>{row.observed === null || row.forecast === null ? "Unavailable" : displayCount(Math.abs(row.forecast - row.observed))}</dd></div>
      </dl>
      <p className={styles.chartNote}>
        Hover over the chart or use the time slider to inspect a window. Observations appear after a full minute of samples. Missing camera data leaves a gap.
      </p>
    </section>
  );
}

export function ReplayOverview() {
  const [playhead, setPlayhead] = useState(120);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4);
  const [direction, setDirection] = useState("E");
  const sample = replayAt(playhead);
  const finished = playhead === DEMO_LENGTH;
  const running = playing && !finished;
  const stale = sample.age > FORECAST_HORIZON;
  const selectedLane = APPROACHES.indexOf(direction);
  const expected = sample.last.forecasts[selectedLane];
  const level = forecastLevel(expected);
  const snapshot = {
    stale,
    lanes: Object.fromEntries(APPROACHES.map((approach, index) => {
      const count = sample.last.forecasts[index];
      return [approach, { kind: stale ? "stale" : "fresh", count, cls: forecastLevel(count) }];
    })),
  };

  useEffect(() => {
    if (!running) return undefined;
    const timer = window.setInterval(() => {
      setPlayhead((time) => Math.min(DEMO_LENGTH, time + speed));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [running, speed]);

  const seek = (at) => {
    setPlaying(false);
    setPlayhead(at);
  };
  const jumpTo = (chapter) => {
    setDirection("E");
    seek(chapter.at);
  };
  const togglePlayback = () => {
    if (finished) setPlayhead(0);
    setPlaying(!running);
  };

  return (
    <section className={styles.replay} aria-label="Intersection replay">
      <header className={styles.heading}>
        <div>
          <h2>Guided intersection replay</h2>
          <p>Sample scenario · Use the three events to follow how forecasts and data freshness change.</p>
        </div>
        <a href="#explore" className={styles.walkthroughLink}>See how it works <Icon name="arrow-right" size={16} /></a>
      </header>
      <section className={`${styles.card} ${styles.guide}`} aria-label="Guided replay events">
        <div className={styles.chapters} aria-label="Replay chapters">
          {GUIDED_CHAPTERS.map((chapter) => (
            <button type="button" key={chapter.at} aria-current={chapter === sample.chapter ? "step" : undefined}
                    onClick={() => jumpTo(chapter)}>
              <span>{replayTime(chapter.at)}</span>{chapter.name}
            </button>
          ))}
        </div>
        <p aria-live="polite">{sample.chapter.note}</p>
      </section>

      <div className={styles.junctionLayout}>
        <section className={`${styles.card} ${styles.mapCard}`} aria-label="Interactive intersection">
          <header className={styles.cardHead}>
            <div><h3>Intersection map</h3><p>Next-minute forecast by approach</p></div>
            <span className={styles.feed} data-online={sample.online}>
              <Icon name={sample.online ? "video-camera" : "warning"} size={15} />
              {sample.online ? "Feed reporting" : "Feed silent"}
            </span>
          </header>
          <JunctionMap snapshot={snapshot} approachNames={APPROACH_NAMES} selected={direction} onSelect={setDirection} />
        </section>

        <section className={`${styles.card} ${styles.approachCard}`} aria-labelledby="replay-approach">
          <div className={styles.approachIcon}><Icon name="car" size={24} /></div>
          <header>
            <h3 id="replay-approach">{APPROACH_NAMES[direction]} approach</h3>
            <p>Inbound traffic</p>
          </header>
          <dl className={styles.metrics}>
            <div><dt>Vehicles in view</dt><dd>{sample.online ? sample.last.counts[selectedLane] : "No update"}</dd></div>
            <div><dt>{stale ? "Expired forecast" : "Next 60s forecast"}</dt><dd>{expected.toFixed(1)}</dd></div>
            <div>
              <dt>Congestion</dt>
              <dd className={`${styles.level} ${stale ? "" : `${panelStyles.chip} ${panelStyles[level]}`}`} data-expired={stale}>
                <Icon name={level === "HIGH" ? "warning" : "chart-line"} size={17} /> {level}{stale && " · expired"}
              </dd>
            </div>
            <div><dt>Last update</dt><dd>{replayTime(sample.last.at)} <small>{sample.age} s ago</small></dd></div>
          </dl>
          <p className={styles.approachNote}>
            {sample.online ? "Forecasts estimate how many vehicles will be in view. Signals are display-only."
              : "The camera has stopped reporting. Counts stay unavailable until it recovers."}
          </p>
        </section>
      </div>

      <section className={`${styles.card} ${styles.timeline}`} aria-labelledby="replay-timeline">
        <header className={styles.cardHead}>
          <div><h3 id="replay-timeline">Replay timeline</h3><p>Scrub or change playback speed.</p></div>
          <output className={styles.time} htmlFor="replay-position">{replayTime(playhead)} / {replayTime(DEMO_LENGTH)}</output>
        </header>
        <div className={styles.controls}>
          <button type="button" className={styles.play} onClick={togglePlayback}>
            <span aria-hidden="true">{running ? "Ⅱ" : "▶"}</span>
            {running ? "Pause" : finished ? "Replay" : "Play"}
          </button>
          <input id="replay-position" type="range" min="0" max={DEMO_LENGTH} step="1"
                 value={playhead} aria-label="Replay position" aria-valuetext={replayTime(playhead)}
                 onChange={(event) => seek(Number(event.target.value))} />
          <label className={styles.speed}>Speed
            <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
              {SPEEDS.map((value) => <option key={value} value={value}>{value}×</option>)}
            </select>
          </label>
        </div>
      </section>

      <ForecastComparison playhead={playhead} direction={direction} onSeek={seek} highlightOutage />
    </section>
  );
}

export function ModelPerformance() {
  const [direction, setDirection] = useState("E");
  const [at, setAt] = useState(120);
  const { ridge, persistence, difference, interval } = COUNT_BENCHMARK;
  return (
    <section className={styles.performance} aria-labelledby="model-performance">
      <div className={`${styles.card} ${styles.benchmark}`}>
        <header className={styles.cardHead}>
          <div><h3 id="model-performance">Model performance</h3><p>Held-out camera benchmark · P105</p></div>
          <span className={styles.benchmarkUnit}>Mean absolute error · vehicles</span>
        </header>
        <dl className={styles.bars}>
          {[[ "Ridge", ridge ], [ "Persistence baseline", persistence ]].map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt><dd>{value.toFixed(3)}</dd>
              <span aria-hidden="true"><i style={{ width: `${value / persistence * 100}%` }} /></span>
            </div>
          ))}
        </dl>
        <p className={styles.chartNote}>Ridge reduced mean absolute error by {difference.toFixed(3)} vehicles. The published 95% interval for the difference is {interval[0]} to {interval[1]} vehicles.</p>
      </div>
      <div className={`${styles.card} ${styles.performanceControls}`}>
        <div><h3>Forecast example</h3><p>Sample traffic data · A five-minute junction scenario</p></div>
        <label className={styles.speed}>Approach
          <select value={direction} onChange={(event) => setDirection(event.target.value)}>
            {APPROACHES.map((key) => <option key={key} value={key}>{APPROACH_NAMES[key]}</option>)}
          </select>
        </label>
        <label className={styles.performanceTime}>
          <span>Sample time</span>
          <input type="range" min="0" max={DEMO_LENGTH} step="1" value={at} aria-valuetext={replayTime(at)}
                 onChange={(event) => setAt(Number(event.target.value))} />
          <output>{replayTime(at)}</output>
        </label>
      </div>
      <ForecastComparison playhead={at} direction={direction} onSeek={setAt} />
    </section>
  );
}
