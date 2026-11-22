import { useEffect, useState } from "react";
import { Icon } from "./icons.jsx";
import styles from "./PipelineWalkthrough.module.css";
import bellevue from "./explorer-example/bellevue.json";
import bellevueImage from "./explorer-example/bellevue.jpg";

const STEPS = [
  { id: "camera", name: "Camera", icon: "video-camera", input: "Fixed camera footage", output: "A timestamped frame",
    detail: "The edge takes a frame every two seconds. The source image stays with the camera or recording." },
  { id: "detection", name: "YOLO detection", icon: "target", input: "Timestamped frame", output: "Vehicle boxes, classes and confidence scores",
    detail: "The detector locates vehicles. Inspect a box to see its class and confidence." },
  { id: "counts", name: "Lane counts", icon: "car", input: "Vehicle boxes and configured lane centres", output: "Vehicles in view per lane",
    detail: "The edge assigns each detection to the closest lane centre within the configured radius." },
  { id: "forecast", name: "Forecast", icon: "chart-line", input: "Recent lane counts and congestion levels", output: "Expected mean vehicles in view over the next 60 seconds",
    detail: "Ridge uses two minutes of counts. The deployed persistence model separately forecasts congestion level." },
  { id: "dashboard", name: "Dashboard", icon: "squares-four", input: "Counts, forecasts and the camera heartbeat", output: "Per-lane readings with source and freshness",
    detail: "MQTT delivers the readings to FastAPI and SQLite. The dashboard shows the latest values next to their source." },
];

export const LOCAL_EXAMPLE = `${import.meta.env.BASE_URL}local-example/`;
const href = (stage) => `#explore/pipeline/${stage}`;

export function useLocalExample(file) {
  const [frame, setFrame] = useState(null);
  useEffect(() => {
    if (!["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) return undefined;
    const controller = new AbortController();
    fetch(`${LOCAL_EXAMPLE}${file}`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : null)
      .then((example) => {
        if (!controller.signal.aborted && example) setFrame(example);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [file]);
  return frame;
}

const percent = (n) => `${n * 100}%`;
const laneLabel = (name) => name.replace("lane_", "L");

function ExampleFrame({ frame, active }) {
  const assigned = active >= 2;
  return (
    <figure className={styles.frame}>
      <div className={styles.picture}>
        <img src={bellevueImage} alt="Traffic at the 116th Avenue NE and NE 12th Street intersection in Bellevue, Washington" />
        {active >= 1 && frame.boxes.map(({ bounds: [x1, y1, x2, y2], label, confidence, lane }, i) => (
          <span key={i} className={styles.box} data-unassigned={assigned && !lane || undefined} title={`${label} · ${Math.round(confidence * 100)}%${assigned && lane ? ` · ${laneLabel(lane)}` : ""}`}
                style={{ left: percent(x1), top: percent(y1), width: percent(x2 - x1), height: percent(y2 - y1) }} />
        ))}
        {assigned && frame.lanes.map(({ name, centre: [x, y], count }) => (
          <span key={name} className={styles.marker} style={{ left: percent(x), top: percent(y) }}>{laneLabel(name)} · {count}</span>
        ))}
      </div>
      <figcaption>{frame.site} · {frame.timestamp} in the recording · {active === 0 ? "Source frame" : active === 1 ? `${frame.boxes.length} retained detections` : "Saved lane assignments"}</figcaption>
    </figure>
  );
}

function ExampleReadings({ frame, active }) {
  const forecast = active >= 3;
  return (
    <div className={styles.readings}>
      <table>
        <thead><tr><th scope="col">Lane</th><th scope="col">At {frame.timestamp}</th>
          {forecast && <><th scope="col">Ridge</th><th scope="col">Repeat last minute</th><th scope="col">Observed next minute</th></>}</tr></thead>
        <tbody>{frame.lanes.map(({ name, count, forecast: expected, baseline, observed }) => (
          <tr key={name}><th scope="row">{laneLabel(name)}</th><td>{count}</td>
            {forecast && <><td>{expected.toFixed(2)}</td><td>{baseline.toFixed(2)}</td><td>{observed.toFixed(2)}</td></>}</tr>
        ))}</tbody>
      </table>
      {forecast && <p>Forecast and observed detector averages cover {frame.forecastWindow} in the recording. Model <code>{frame.model}</code>.</p>}
    </div>
  );
}

export function PipelineWalkthrough({ stage }) {
  const active = Math.max(0, STEPS.findIndex(({ id }) => id === stage));
  const step = STEPS[active];
  const frame = bellevue;
  return (
    <section className={styles.walkthrough} aria-labelledby="walkthrough-title">
      <header>
        <h2 id="walkthrough-title">From camera to dashboard</h2>
        <p>Follow the information through five stages of the STMS architecture.</p>
      </header>
      <nav aria-label="Pipeline architecture">
        <ol className={styles.flow} aria-label="Pipeline steps">
          {STEPS.map(({ id, name, icon }, index) => (
            <li key={id}>
              <a href={href(id)} aria-current={active === index ? "step" : undefined} aria-controls="pipeline-step">
                <Icon name={icon} size={20} /><span>{name}</span>
              </a>
            </li>
          ))}
        </ol>
      </nav>
      <div id="pipeline-step" className={styles.detail} aria-live="polite">
        <h3>{step.name}</h3>
        <p>{step.detail}</p>
        <dl>
          <div><dt>Input</dt><dd>{step.input}</dd></div>
          <div><dt>Output</dt><dd>{step.output}</dd></div>
        </dl>
      </div>
      <ExampleFrame frame={frame} active={active} />
      {active === 1 && <p>Saved detector <code>{frame.detector}</code></p>}
      {active >= 2 && <ExampleReadings frame={frame} active={active} />}
      <div className={styles.actions}>
        <a href="#explore/architecture">Full system architecture</a>
        {active < STEPS.length - 1
          ? <a className={styles.replay} href={href(STEPS[active + 1].id)}>Next stage <Icon name="arrow-right" size={15} /></a>
          : <a className={styles.replay} href="#replay">Try the guided replay <Icon name="arrow-right" size={15} /></a>}
      </div>
    </section>
  );
}
