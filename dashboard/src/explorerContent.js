// The project explorer's content, as data. Written from the source code and the
// committed results, not from the original plan: where the PRD planned something
// the code does not do, the topic's status says so.
//
// status: "built"   implemented and covered by tests
//         "sim"     implemented, in simulation only
//         "partial" implemented, not yet validated where it matters
//         "future"  not implemented
//
// Each topic answers six questions: what, why, use (how this project uses it),
// inside (how it works internally), where (the component that implements it)
// and output. `visual` names an interactive figure drawn by Explorer.jsx.

export const STATUS = {
  built: "Built and tested",
  sim: "Simulation only",
  partial: "Built, validation pending",
  future: "Future enhancement",
};

export const GROUPS = ["Overview", "Design", "How it works", "System", "Outcome"];

export const TOPICS = [
  {
    id: "introduction", group: "Overview", title: "Project introduction", status: "built", icon: "house",
    summary: "STMS turns an ordinary fixed traffic camera into a lane-by-lane counter and a one-minute traffic forecaster, and studies in simulation whether such forecasts help a learned signal controller.",
    what: "A camera-based traffic monitoring and forecasting system with a research model (MFSTNet) and a signal-control study, built as a final-year B.Tech CSE (ML/AI) major project.",
    why: "Intersections are managed with fixed timers or expensive road sensors. A camera is cheap and already common, but its video has to be turned into numbers a controller could use.",
    use: "One camera watches an intersection. The edge computer counts vehicles per lane every 2 seconds, forecasts the next 60 seconds, and sends only numbers to a server that this dashboard reads.",
    inside: "The edge path sends YOLO counts and forecasts to FastAPI over MQTT. The local workbench runs YOLO and ByteTrack on recordings and saves results in SQLite and JSON. Both feed the React dashboard. MFSTNet and PPO in SUMO are research experiments.",
    where: "edge/, server/, contracts/, dashboard/, mfstnet/, simulation/",
    output: "Per approach (N, S, E, W): a congestion level and an expected vehicle count for the next minute, plus history, analytics and evaluation results.",
  },
  {
    id: "problem", group: "Overview", title: "Problem statement", status: "built", icon: "warning",
    summary: "Signals that cannot see traffic waste green time, and Indian traffic breaks the assumptions most detection methods make.",
    what: "The gap between what a signal knows (nothing, on a fixed timer) and what is actually waiting at each approach.",
    why: "Mixed vehicles, two-wheelers filtering between lanes and weak lane discipline defeat loop detectors and methods built for orderly traffic. Sensors per lane are also costly to install and maintain.",
    use: "The project measures traffic from the camera image itself, counting per lane by position rather than by painted lane markings, and forecasts a minute ahead.",
    inside: "The camera's view is divided by hand-placed lane centres. Each detected vehicle is assigned to its nearest centre, so no lane discipline is assumed.",
    where: "mfstnet/corpus/lanes.py, cameras/<id>.json",
    output: "A defensible, measured count per approach instead of a fixed assumption.",
  },
  {
    id: "objectives", group: "Overview", title: "Project objectives", status: "built", icon: "target",
    summary: "Five objectives, each with where it stands today.",
    points: [
      ["built", "Count vehicles per lane from a fixed camera, in near real time."],
      ["built", "Forecast each approach's next 60 seconds: a level and a vehicle count."],
      ["built", "Deliver forecasts edge → server → dashboard, keeping video on the edge."],
      ["built", "Build and evaluate MFSTNet (CNN + ViT + BiLSTM) camera by camera."],
      ["sim", "Test whether forecasts improve a PPO signal controller against Webster timing."],
    ],
    what: "The measurable goals the project committed to.",
    why: "Clear objectives make it possible to say, with numbers, what worked and what did not.",
    use: "Each objective maps to a component and to a committed result file.",
    inside: "Requirements are numbered (FR-*, NFR-*) in the PRD and traced to tests in the requirements traceability matrix.",
    where: "docs/00-planning/PRD.md, docs/01-requirements/RTM.md",
    output: "Four objectives met in software; the fifth answered in simulation with a null result.",
  },
  {
    id: "comparison", group: "Overview", title: "Existing vs proposed system", status: "built", icon: "scales", visual: "compare",
    summary: "What changes when the intersection has a camera-based counter and forecaster.",
    what: "A side-by-side of the conventional approach and this project's.",
    why: "It shows the value of the work and, just as importantly, where it stops.",
    use: "The proposed system adds measurement and forecasting. It does not yet switch a real signal.",
    inside: "Compare the two columns in the figure.",
    where: "The whole system.",
    output: "A clear statement of what is new.",
  },
  {
    id: "architecture", group: "Design", title: "System architecture", status: "built", icon: "tree-structure", visual: "architecture",
    summary: "Five layers from camera to screen. Click any block to see what it does and where it lives in the code.",
    what: "The deployed path: input, processing on the edge, forecasting, transport and storage, and presentation.",
    why: "Separating the layers lets each be tested alone, and keeps video on the edge while only numbers travel.",
    use: "Forecasting runs on the edge because the input is frames and frames must not leave it (ADR-026, NFR-13).",
    inside: "The edge publishes over MQTT; an ingest process writes to SQLite; the FastAPI server serves GET endpoints; the dashboard polls every 2 seconds.",
    where: "edge/run.py, contracts/mqtt.py, server/app.py, dashboard/src/",
    output: "A working pipeline, verified end to end on recorded footage.",
  },
  {
    id: "stack", group: "Design", title: "Technology stack", status: "built", icon: "stack", visual: "stack",
    summary: "Every technology in the project and the job it does.",
    what: "The languages, libraries and services the system is built from.",
    why: "Each was chosen for a reason that fits a ₹0 budget and a laptop: open source, well documented, runs on CPU or a 6 GB GPU.",
    use: "Python for everything on the edge, server and research side; React for the dashboard.",
    inside: "Versions are pinned in requirements.txt and dashboard/package.json.",
    where: "requirements.txt, dashboard/package.json",
    output: "A reproducible environment.",
  },
  {
    id: "requirements", group: "Design", title: "Hardware and software requirements", status: "built", icon: "cpu",
    summary: "What it takes to run each part.",
    points: [
      ["built", "Edge node: a laptop (ADR-003, ₹0 budget), not a Jetson. CPU works; a CUDA GPU is faster."],
      ["built", "Training: an RTX 4050 laptop GPU (6 GB) on cached, frozen-backbone features (ADR-005)."],
      ["built", "Software: Python 3.12 (supported), PyTorch, Ultralytics, OpenCV, FastAPI, Paho-MQTT."],
      ["built", "Broker: Mosquitto with authentication; Docker Compose for the server stack (CI-verified)."],
      ["sim", "Simulation: SUMO 1.27.1 with TraCI, Stable-Baselines3 2.9 and Gymnasium."],
      ["built", "Dashboard: any modern browser; Node.js only to build it."],
    ],
    what: "The minimum machine and software for the edge, server, training and dashboard.",
    why: "The project had no hardware budget, so everything had to run on team laptops.",
    use: "A single laptop can run the whole demonstration: broker, server, edge and dashboard.",
    inside: "scripts/check_env.py checks a machine before installation; scripts/check_deployment.py after.",
    where: "scripts/check_env.py, docs/90-manual/EXECUTION_MANUAL.md",
    output: "A pass/fail report per requirement.",
  },
  {
    id: "mechanism", group: "How it works", title: "Complete working mechanism", status: "built", icon: "flow-arrow", visual: "pipeline",
    summary: "Follow one frame from the camera to the dashboard. Press play, or click a step.",
    what: "The sequence every 2 seconds of video goes through.",
    why: "Seeing the whole chain makes each later topic easier to place.",
    use: "This is exactly what edge/run.py does, live or on a recording.",
    inside: "Each step is a separate, tested function; the frame is dropped right after detection.",
    where: "edge/run.py, edge/node.py",
    output: "A forecast per approach, published and displayed.",
  },
  {
    id: "dataflow", group: "How it works", title: "Data flow diagram", status: "built", icon: "graph", visual: "dataflow",
    summary: "What travels where, and on which MQTT topic.",
    what: "The messages between the edge, the broker, the ingest, the database, the API and the dashboard.",
    why: "Every message has a defined shape and delivery guarantee, so nothing is lost or misread silently.",
    use: "Topics and payloads are defined once, in contracts/mqtt.py, with the delivery level (QoS) attached to the topic.",
    inside: "Counts use QoS 1 (at least once); forecasts and heartbeats QoS 0; emergency QoS 2 (exactly once).",
    where: "contracts/mqtt.py",
    output: "Typed, validated messages end to end.",
  },
  {
    id: "detection", group: "How it works", title: "Traffic detection mechanism", status: "built", icon: "eye",
    summary: "YOLO detects vehicles. The local analysis also uses ByteTrack to associate detections over time.",
    what: "Object detection: drawing a box around each vehicle in an image and naming its class.",
    why: "Counting needs to know where each vehicle is, not just that the image looks busy.",
    use: "The reference edge configuration uses ITD-trained YOLOv8 at 992 px and 0.45 confidence. The current local demo uses YOLO11s at 960 px and 0.30.",
    inside: "YOLO returns normalised boxes, classes and confidence scores. The workbench tracks detections at up to four frames per second and saves measurements every two seconds.",
    where: "edge/run.py, scripts/tracked_video.py, indiatrafficnet/class_mapping.yaml",
    output: "Timestamped boxes, classes and confidence scores, with track IDs for associated detections.",
  },
  {
    id: "counting", group: "How it works", title: "Vehicle classification and counting", status: "built", icon: "car", visual: "pcu",
    summary: "Each box is mapped to a vehicle class and assigned to the nearest lane centre.",
    what: "Turning boxes into a count per lane, and per class.",
    why: "Forecasts and congestion are per approach, so the count must be per lane, and a bus is not the same load as a motorcycle.",
    use: "Classes map to the contract's set (car, motorcycle, auto-rickshaw, bus, truck). Bicycles are dropped from published counts. Each box's centre is assigned to the closest lane centre within a maximum radius; anything further is not counted.",
    inside: "Nearest-centre assignment is disjoint by construction, unlike overlapping polygons (P23). Passenger car units (PCU) from Indo-HCM 2017 weight each class.",
    where: "mfstnet/corpus/counting.py, mfstnet/corpus/lanes.py, mfstnet/corpus/pcu.py",
    output: "Per lane: a vehicle count and a breakdown by class.",
  },
  {
    id: "congestion", group: "How it works", title: "Traffic density and congestion analysis", status: "built", icon: "gauge", visual: "levels",
    summary: "The congestion level is the class of the last minute's mean count, against thresholds calibrated for that camera.",
    what: "A level, LOW, MEDIUM or HIGH, for each approach.",
    why: "Raw counts mean different things on different cameras. A level relative to the camera's own range is comparable.",
    use: "The persistence forecaster: mean of each lane's last 30 counts (60 s), then LOW if ≤ low threshold, MEDIUM if ≤ medium threshold, otherwise HIGH.",
    inside: "Thresholds are the 33rd and 67th percentiles of 60-second means in a calibration hour (ADR-017), frozen in a spec whose SHA-256 names the model.",
    where: "edge/persistence.py, experiments/results/bellevue_pilot/persistence_v1.json",
    output: "A level per approach, with the measured precision of that call as its confidence.",
  },
  {
    id: "signals", group: "How it works", title: "Traffic signal management", status: "sim", icon: "signal",
    summary: "Signal timing is studied in simulation, and safety rules are implemented, but no forecast reaches a real signal.",
    what: "Deciding how long each direction gets green.",
    why: "This is the end goal of intersection management, and the reason for forecasting at all.",
    use: "The dashboard shows what green shares a forecast would suggest, labelled as reaching no signal. Signal heads are drawn as unknown because no signal state reaches this system.",
    inside: "server/safety.py enforces 10 s minimum green, 90 s maximum, 3 s all-red and a 3 s emergency response. If MQTT is silent for more than 10 s, the edge falls back to a local Webster cycle (FR-A06).",
    where: "server/safety.py, edge/node.py, simulation/",
    output: "Safe, clamped decisions in simulation; no command to physical signals.",
  },
  {
    id: "prediction", group: "How it works", title: "Traffic prediction and optimisation", status: "built", icon: "chart-line", visual: "mfstnet",
    summary: "Three forecasting efforts: a ridge count model (deployed), persistence (deployed), and MFSTNet (research), plus PPO for signal optimisation.",
    what: "Predicting the next minute and using it to choose signal timing.",
    why: "A controller that knows what is coming can, in principle, allocate green time better than one that only reacts.",
    use: "Ridge forecasts the next minute's mean count from five difference features of the last 2 minutes, with no intercept so it carries no camera's level to another. MFSTNet fuses ResNet-50 and DINOv2 features with gated cross-attention, a BiLSTM and per-lane heads. PPO chooses among 12 actions (NS or EW green × 6 durations) from a 17-value state.",
    inside: "Ridge: count = max(0, mean of last 30 + Δ̂). MFSTNet gate: g = sigmoid(W[Z_A; Z_B]), fused = g·Z_A + (1−g)·Z_B. PPO is trained in SUMO against Webster's best configuration.",
    where: "edge/count_forecast.py, mfstnet/, simulation/, scripts/train_ppo.py",
    output: "Next-minute counts (MAE 0.748 vs 0.972 for persistence); MFSTNet and PPO results in Results.",
  },
  {
    id: "backend", group: "System", title: "Backend architecture", status: "built", icon: "database",
    summary: "FastAPI serves edge telemetry and runs local recording analysis jobs.",
    what: "The server side: ingest, storage, safety and API.",
    why: "The dashboard and any future controller need one trusted, timestamped record.",
    use: "MQTT ingest writes telemetry to SQLite using a token. The loopback workbench separately accepts local uploads and records analysis jobs.",
    inside: "Telemetry responses include freshness flags. Job history links completed results and locally stored recordings by analysis ID.",
    where: "server/app.py, server/safety.py, deploy/server.Dockerfile",
    output: "JSON over HTTP, and a SQLite database file.",
  },
  {
    id: "frontend", group: "System", title: "Frontend architecture", status: "built", icon: "squares-four",
    summary: "React 18 and Vite, with three experiences: this explorer, the landing page and the console.",
    what: "The dashboard you are using.",
    why: "Operators need the answer at a glance; evaluators need to understand the system.",
    use: "The console polls every 2 seconds, validates every response before showing it, and shows missing, stale and invalid data as such, never as zero or LOW.",
    inside: "api.js reads listed routes. The local workbench client handles uploads and job actions. Colours use design tokens with contrast tests.",
    where: "dashboard/src/ (App.jsx, Panels.jsx, validate.js, api.js, theme.css)",
    output: "A console that shows telemetry, runs local video analysis and previews advisory signal timing.",
  },
  {
    id: "database", group: "System", title: "Database and data storage", status: "built", icon: "database",
    summary: "One SQLite file, seven tables, with raw counts kept 48 hours.",
    what: "Where forecasts, counts, heartbeats and checks are stored.",
    why: "SQLite needs no server and is enough for one intersection; the planned PostgreSQL stack was dropped (ADR-008).",
    use: "Tables: observations, predictions, count_forecasts, vehicle_counts, vehicle_count_latest, forecast_checks, heartbeats.",
    inside: "Raw counts are pruned after 48 hours by the store itself after a write; forecast checks are kept one hour.",
    where: "server/app.py (connect, schema)",
    output: "data/server/stms.sqlite",
  },
  {
    id: "api", group: "System", title: "API communication", status: "built", icon: "plugs", visual: "api",
    summary: "The endpoints, which are open for reading, and which need a token.",
    what: "The HTTP contract between the server and its clients.",
    why: "A small, explicit API is easy to test and hard to misuse.",
    use: "The dashboard reads edge data over GET. Edge ingest uses bearer-token POSTs. The local workbench also accepts same-origin uploads and job actions on loopback.",
    inside: "Intersection ids are validated against one pattern; a 404 means nothing published yet, which the page shows as such.",
    where: "server/app.py, dashboard/src/api.js",
    output: "JSON responses with age and stale flags.",
  },
  {
    id: "video", group: "System", title: "Video processing and live camera", status: "partial", icon: "film-strip",
    summary: "The local workbench analyzes recordings and can connect to compatible camera streams. Physical CCTV still needs validation.",
    what: "The detector tracks vehicles between frames and publishes measurements at two-second intervals.",
    why: "Demonstrations and evaluation use recordings; deployment needs a camera.",
    use: "Analyze a Video uploads the selected file to the loopback workbench. Demo Live buffers playback behind the latest analyzed sample. Real Camera uses a separate stream connection.",
    inside: "YOLO finds vehicles and ByteTrack associates detections across frames. A camera profile enables lane crossings, approach forecasts and advisory timing. Whole-frame mode counts confirmed track IDs.",
    where: "scripts/analyze_video.py, scripts/tracked_video.py, server/camera_monitor.py, dashboard/src/Analyze.jsx",
    output: "Timestamped counts, boxes, forecasts, alerts and a saved recording for Guided Replay.",
  },
  {
    id: "security", group: "System", title: "Security and reliability", status: "built", icon: "shield-check",
    summary: "Authenticated edge telemetry and a local workbench restricted to same-origin requests on loopback.",
    what: "How the system protects data and keeps behaving safely when parts fail.",
    why: "A traffic system that fails silently, or can be commanded by anyone, is worse than none.",
    use: "The edge configuration uses authenticated MQTT over TLS. Telemetry writes require a bearer token. Workbench writes require a matching local origin.",
    inside: "If inference fails, control falls back to raw counts; if MQTT is silent over 10 s, the edge runs its local Webster cycle. Stale data is labelled by the server's clock.",
    where: "deploy/mosquitto.conf, server/app.py, edge/node.py, server/safety.py",
    output: "Defined behaviour under every tested fault.",
  },
  {
    id: "results", group: "Outcome", title: "Results and performance", status: "built", icon: "results", visual: "results",
    summary: "What was measured, with the numbers.",
    what: "The committed evaluation results.",
    why: "Claims are only as good as the measurements behind them.",
    use: "Every number here comes from a committed result file; the console's Results section shows them with their commit.",
    inside: "Evaluation is leave-one-camera-out, so a model is always scored on a camera it never saw.",
    where: "experiments/results/, docs/TEAM-STATUS.md",
    output: "See the figure, and the Results section of the console.",
  },
  {
    id: "tradeoffs", group: "Outcome", title: "Advantages and limitations", status: "built", icon: "scales",
    summary: "Where the system is strong, and where it is not yet.",
    points: [
      ["built", "Advantage: needs only a fixed camera and a laptop, no road sensors."],
      ["built", "The edge publishes measurements. The local workbench saves uploaded recordings on the same computer for replay."],
      ["built", "Advantage: every number is validated and dated; missing data is never shown as zero."],
      ["built", "Advantage: the count forecast beats repeating the last minute on unseen cameras."],
      ["partial", "The evidence includes Bellevue recordings and annotated Bengaluru CCTV stills. Results vary by camera and vehicle type."],
      ["partial", "Vehicle counts in still frames have reference checks. Inbound crossing accuracy needs labeled tracks and crossing events."],
      ["future", "Limitation: no forecast reaches a real signal, and the control study found no benefit."],
      ["partial", "Limitation: levels are relative to one calibration hour, so HIGH can be only a few vehicles."],
    ],
    what: "An honest assessment.",
    why: "Knowing the limits is what makes the results usable.",
    use: "The limitations are shown on the console too, beside the numbers they qualify.",
    inside: "Two paper claims (domain, class coverage) are deliberately kept failing until the data supports them.",
    where: "docs/00-planning/CLAIMS.yaml, scripts/check_claims.py",
    output: "A list of strengths and open items.",
  },
  {
    id: "future", group: "Outcome", title: "Future scope", status: "future", icon: "lightbulb",
    summary: "The next steps, in the order they unlock value.",
    points: [
      ["future", "Evaluate on Indian intersections, including the campus camera set."],
      ["future", "Validate counts against human counts (V1) and latency on a real camera (V2)."],
      ["future", "Connect forecasts to signal control only after the fault-behaviour study (P97a Part 2)."],
      ["future", "Push updates over WebSocket instead of polling; add light and high-contrast themes."],
      ["future", "Run the edge on a Jetson-class device instead of a laptop."],
    ],
    what: "Work that is planned or would add value.",
    why: "It shows where the project can go from here.",
    use: "Each item is tracked on the build log.",
    inside: "Items blocked on people or hardware are marked with who and what would unblock them.",
    where: "BUILD-LOG.md",
    output: "A roadmap.",
  },
  {
    id: "conclusion", group: "Outcome", title: "Conclusion", status: "built", icon: "flag-checkered",
    summary: "A complete, tested camera-to-dashboard system with one supported claim and two honest null results.",
    what: "What the project achieved.",
    why: "To leave the reader with the right picture.",
    use: "The project includes counting, two forecasts, telemetry, storage and local video analysis. MFSTNet and signal control are separate research studies.",
    inside: "The deployed edge reproduced the offline counts exactly on 10 clips (71,140 of 71,140 values).",
    where: "The whole repository.",
    output: "A next-minute count forecast that beats the obvious baseline on unseen cameras, and a clear account of what remains to be shown.",
  },
];

// The architecture figure: five layers, each block clickable.
export const ARCHITECTURE = [
  { layer: "Input", blocks: [
    { id: "camera", title: "Fixed camera", text: "A fixed, elevated view of the intersection, live (STMS_CAMERA_URL) or a recording.", where: "edge/run.py --source" },
    { id: "profile", title: "Camera profile", text: "Hand-placed lane centres, the lane-to-approach map and the calibrated thresholds, one committed file per camera.", where: "cameras/<id>.json" },
  ] },
  { layer: "Processing (edge)", blocks: [
    { id: "detector", title: "YOLOv8 detector", text: "Finds vehicles in one frame every 2 s. The frame is dropped right after.", where: "edge/run.py" },
    { id: "counter", title: "Lane counter", text: "Assigns each vehicle to its nearest lane centre and counts per lane and class.", where: "mfstnet/corpus/counting.py" },
  ] },
  { layer: "Analysis (edge)", blocks: [
    { id: "persistence", title: "Persistence level", text: "LOW / MEDIUM / HIGH for the next 60 s from the last minute's mean.", where: "edge/persistence.py" },
    { id: "ridge", title: "Ridge count", text: "The expected vehicle count for the next minute.", where: "edge/count_forecast.py" },
    { id: "check", title: "Forecast check", text: "Pairs each forecast with what the next minute then showed.", where: "edge/check.py" },
  ] },
  { layer: "Transport and storage", blocks: [
    { id: "mqtt", title: "MQTT broker", text: "Mosquitto, authenticated, TLS. Topics and QoS defined once.", where: "contracts/mqtt.py" },
    { id: "server", title: "FastAPI + SQLite", text: "Ingests, stores and serves the forecasts read-only, with ages and stale flags.", where: "server/app.py" },
  ] },
  { layer: "Presentation", blocks: [
    { id: "dashboard", title: "React dashboard", text: "Polls every 2 s, validates every response, and cannot send commands.", where: "dashboard/src/" },
  ] },
];

export const PIPELINE = [
  { icon: "video-camera", title: "Camera input", text: "A frame is taken from the camera or recording every 2 seconds." },
  { icon: "eye", title: "Vehicle detection", text: "YOLOv8 finds each vehicle (confidence ≥ 0.45, 992 px input)." },
  { icon: "car", title: "Classification", text: "Each detection is mapped to car, motorcycle, auto-rickshaw, bus or truck." },
  { icon: "path", title: "Lane counting", text: "Each vehicle goes to its nearest lane centre; the frame is discarded." },
  { icon: "gauge", title: "Congestion level", text: "The last 60 s mean, against the camera's thresholds → LOW / MEDIUM / HIGH." },
  { icon: "chart-line", title: "Count forecast", text: "Ridge predicts the next minute's mean vehicle count." },
  { icon: "plugs", title: "Publish", text: "Counts and forecasts go out over MQTT. No image ever does." },
  { icon: "database", title: "Store and serve", text: "The server stores them in SQLite and serves them with their age." },
  { icon: "squares-four", title: "Dashboard", text: "This page shows them within 2 seconds, or says why it cannot." },
];

export const DATAFLOW = {
  nodes: [
    { id: "edge", label: "Edge node", sub: "detect · count · forecast", x: 90, y: 110 },
    { id: "broker", label: "MQTT broker", sub: "Mosquitto · TLS", x: 330, y: 110 },
    { id: "ingest", label: "Ingest", sub: "subscriber", x: 570, y: 110 },
    { id: "db", label: "SQLite", sub: "7 tables", x: 570, y: 270 },
    { id: "api", label: "FastAPI", sub: "GET endpoints", x: 330, y: 270 },
    { id: "ui", label: "Dashboard", sub: "polls every 2 s", x: 90, y: 270 },
  ],
  edges: [
    { from: "edge", to: "broker", label: "stms/{id}/…/vehicle_count · QoS 1" },
    { from: "broker", to: "ingest", label: "prediction, count/forecast · QoS 0" },
    { from: "ingest", to: "db", label: "INSERT" },
    { from: "db", to: "api", label: "SELECT" },
    { from: "api", to: "ui", label: "JSON over HTTP" },
  ],
};

export const ENDPOINTS = [
  ["GET", "/health", "Is the server up; the page measures its round trip."],
  ["GET", "/prediction/{id}/latest", "Latest congestion level per approach, with age and stale flag."],
  ["GET", "/prediction/{id}/history", "Recent level forecasts, each with its model id."],
  ["GET", "/count_forecast/{id}/latest", "Latest next-minute vehicle count per approach."],
  ["GET", "/count_forecast/{id}/history", "Recent count forecasts."],
  ["GET", "/vehicle_count/{id}/latest", "Each lane's latest count, by class, with PCU weights."],
  ["GET", "/vehicle_count/{id}/history?window=1h|6h|24h", "Observed counts in 1, 5 or 15 minute buckets."],
  ["GET", "/heartbeat/{id}/latest", "The edge's heartbeat: source, lane map, age."],
  ["GET", "/forecast_check/{id}/recent", "The last 20 minutes of forecast-versus-outcome checks."],
  ["GET", "/sites", "Every intersection that has reported."],
  ["GET", "/evidence", "The committed evaluation results, each with its commit."],
  ["POST", "/prediction/{id} · /count_forecast/{id} · /vehicle_count/{id}/{lane} · /heartbeat/{id} · /forecast_check/{id}", "Written by the ingest, with a bearer token. The dashboard never calls these."],
];

export const COMPARISON = [
  ["How traffic is sensed", "Fixed timer, or loop detectors cut into the road", "An ordinary fixed camera, counted lane by lane"],
  ["Mixed, lane-free traffic", "Assumes lane discipline", "Assigns vehicles by position to the nearest lane centre"],
  ["Looking ahead", "Reacts to now, or not at all", "Forecasts each approach's next 60 seconds"],
  ["Privacy", "Video often recorded centrally", "Frames never leave the edge; only numbers travel"],
  ["When data is missing", "Often silent", "Shown as missing or stale, never as zero"],
  ["Signal control", "Applied directly", "Studied in simulation; not connected to real signals"],
];

export const COUNT_BENCHMARK = { ridge: 0.748, persistence: 0.972, difference: 0.224, interval: [0.181, 0.271] };

export const RESULTS = [
  { value: COUNT_BENCHMARK.ridge.toFixed(3), unit: "vehicles", label: "Next-minute count error (ridge), held-out cameras",
    note: `vs ${COUNT_BENCHMARK.persistence} for repeating the last minute; difference ${COUNT_BENCHMARK.difference}, 95% CI ${COUNT_BENCHMARK.interval.join("–")} (P105)` },
  { value: "0.706", unit: "macro-F1", label: "Persistence level forecast on new cameras", note: "vs 0.483 for a count model trained on one camera (P103)" },
  { value: "71,140", unit: "of 71,140", label: "Edge counts identical to offline counts", note: "on 10 clips, through a real broker" },
  { value: "Null", unit: "", label: "MFSTNet vs linear probe", note: "could not be told apart on four foreign cameras" },
  { value: "Null", unit: "", label: "Forecasts for signal control", note: "no demonstrated control benefit under the tested conditions (P130)" },
];

export const PCU = [["Car", "1.0"], ["Motorcycle", "0.3"], ["Auto-rickshaw", "1.2"], ["Bus", "4.5"], ["Truck", "5.0"]];

// 150th_Eastgate's frozen thresholds (persistence_v1.json, P103), for the levels figure.
export const EXAMPLE_LIMITS = { camera: "150th_Eastgate", low: 0.13333333333333333, med: 0.9666666666666667 };
