# STMS recorded-video demonstration

## Objective and problem

Turn recorded intersection footage into replayable evidence that a reviewer can check. The system estimates approach demand, counts tracked vehicles entering through configured lines, flags conditions that meet documented rules, and proposes demonstration signal timings. Manual video review is slow, and a frame-by-frame detection total overcounts vehicles that remain visible.

## Code changes

- `scripts/analyze_video.py` runs the media-clock analyzer in `scripts/tracked_video.py`. `scripts/video_traffic.py` implements line crossings, observed density, advice and evidence-backed alerts.
- `scripts/workbench.py` checks paths, formats and sizes, runs jobs and validates result files. `scripts/video_history.py` stores job and alert history. `server/local_analysis.py` exposes these through the loopback API.
- `dashboard/src/App.jsx`, `App.module.css`, `useRecording.js` and `RecordingPages.jsx` with its CSS connect the sidebar to a common recording and show reports, charts and signal advice.
- `dashboard/src/Analyze.jsx`, `Analyze.module.css`, `Workbench.jsx`, `workbench.js` and `validate.js` handle file selection, progress, tracked overlays, evidence replay and input validation.
- `tests/test_video_traffic.py`, `tests/test_workbench.py`, `tests/test_analyze_video.py` and `dashboard/src/recording.test.jsx` cover the new workflow. `requirements.txt` adds the ByteTrack association dependency. `.gitignore` excludes local demo data.

## Setup on Windows

From the project root, use Python 3.12 and Node.js with npm. The commands below use PowerShell and the existing Vite build. Visual C++ runtime support may be needed by the Windows PyTorch and OpenCV wheels.

```powershell
$stmsEnvironment = Join-Path $env:LOCALAPPDATA 'stms-env'
py -3.12 -m venv $stmsEnvironment
$stmsPython = Join-Path $stmsEnvironment 'Scripts/python.exe'
& $stmsPython -m pip install "torch==2.13.0+cpu" "torchvision==0.28.0+cpu" --index-url https://download.pytorch.org/whl/cpu
& $stmsPython -m pip install fastapi uvicorn pyyaml ultralytics==8.4.118 lap==0.5.14 scipy pytest
npm.cmd --prefix dashboard ci
npm.cmd --prefix dashboard run build
$env:STMS_LOCAL_ANALYSIS = '1'
& $stmsPython -m uvicorn server.app:app --host 127.0.0.1 --port 8083
```

Open [STMS Analyze a video](http://127.0.0.1:8083/dashboard/#analyze). FastAPI serves the built React application. Keep it bound to localhost. For frontend work, run `npm.cmd --prefix dashboard run dev` and rebuild before testing the same-origin local workbench. The local analysis API intentionally checks the loopback address and the browser's origin.

## Adaptive phase scheduling demonstration

1. Open **Analyze a video**, select a supported recording, choose its matching camera profile, and click **Analyze Video with AI**. The backend processes to the end independently of the player and the selected dashboard page. **Cancel analysis** is a separate job control.
2. Open **Results** to show tracked inbound crossings, occupancy, flow and alerts. Under **Offline optimized schedule**, scrub the phase timeline and export its CSV. The report also supports PDF through the print dialog and a JSON download.
3. Open **Live → Demo Live – Upload Video** and select the same clip. Playback and monitoring start automatically. STMS matches known recording filenames to the corresponding camera ID. For other footage, choose its matching intersection profile if one exists. The next phase, start time and green duration update beside the player as frames reach the playback clock. Pause and resume to show the countdown following playback.
4. Show the current phase, the upcoming recommendation and the latest measurements. The recommendation can change before yellow begins. Once clearance starts, the next phase is committed. **Live → Real Live Camera / Server** uses the same streaming scheduler for connected frames.

The explainable scheduler ranks eligible phases using vehicles in view, recent tracked inbound crossings per minute and simulated red time. Each phase receives one slot per round. Green bounds are reduced when needed to keep the configured maximum red feasible through the worst-case round order. Timing includes explicit yellow and all-red. The offline optimizer uses complete 30-second measurement windows, including the rest of a window when a phase starts inside it. Live recommendations use only data at or before the displayed frame. Emergency preemption and physical signal state require a verified source. Queue length, individual waiting time, comparative delay and throughput improvements require additional calibration, baseline timings or a scenario-specific validated simulation. The recorded detector output can be viewed with overlays in Guided Replay.

### Camera-specific configuration

Set `STMS_SIGNAL_CONFIG` to the path of a local JSON file and restart the backend. The top-level key is the camera profile ID. Lane geometry and approach mapping continue to come from the selected camera profile. An example for a four-approach simulation follows. Use compatibility pairs only when the grouped movements have been reviewed for that scenario.

```json
{
  "Bellevue_116th_NE12th": {
    "refresh_s": 4,
    "yellow_s": 4,
    "all_red_s": 2,
    "max_red_s": 240,
    "compatible": [["N", "S"], ["E", "W"]],
    "phases": [
      {"name": "North and south", "approaches": ["N", "S"], "min_green_s": 15, "max_green_s": 45},
      {"name": "East and west", "approaches": ["E", "W"], "min_green_s": 15, "max_green_s": 45},
      {"name": "Pedestrian service", "pedestrian": true, "walk_s": 7, "pedestrian_clearance_s": 12}
    ]
  }
}
```

Without an override, mapped approaches get exclusive single-approach phases. Whole-frame analysis has no signal recommendations. Invalid or infeasible phase configurations appear as Alerts while vehicle analysis remains available. Walk and pedestrian clearance occupy one exclusive service slot in the advisory simulation. The configured seconds are demonstration settings. [FHWA guidance on signal changes and clearances](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm)

### Implementation files

- New `scripts/adaptive_signal.py` contains phase validation, causal decisions and offline schedule generation.
- Updated `scripts/tracked_video.py`, `scripts/analyze_video.py`, `scripts/video_traffic.py`, `scripts/workbench.py` and `server/camera_monitor.py` connect the scheduler to detection, stored results, camera updates and alerts.
- New `dashboard/src/AdaptiveSignals.jsx` renders the timeline and live prediction. Updated `LiveMonitoring.jsx`, `RecordingPages.jsx`, `RecordingPages.module.css`, `Workbench.jsx` and `validate.js` integrate it with the existing dashboard.
- New `tests/test_adaptive_signal.py` and updated `dashboard/src/LiveMonitoring.test.jsx` cover demand changes, causality, clearances, phase compatibility, missing measurements, fairness and timeline display.

The configured ITD checkpoint belongs at `models/external/best_xl_ITD_v1.2.pt`. Verify its hash using `experiments/results/model_artifacts.sha256`. For a run with the public Ultralytics YOLO11n checkpoint, obtain it from the official Ultralytics release and explicitly set `$env:STMS_VIDEO_WEIGHTS = (Resolve-Path 'path/to/yolo11n.pt').Path` before starting the server. Each result reports its actual checkpoint. The frozen ridge and persistence models were calibrated under the project detector. Treat their outputs with alternate weights as demonstration forecasts. [Ultralytics tracking reference](https://docs.ultralytics.com/modes/track/)

On the existing demo machine, substitute `../.run-python/tools/python.exe` for `python.exe`. Its separately installed dependencies use `$env:PYTHONPATH = Join-Path $env:TEMP 'stms-bellevue-deps'`. The local test checkpoint is `data/bellevue-demo/yolo11n.pt`. These paths are machine-specific.

SQLite is created automatically in `data/server/video_analysis/jobs.sqlite`. It indexes attempts, file metadata, timestamps, summary metrics, alert status and the saved recording reference. The workbench stores uploaded video bytes in `data/server/video_analysis/uploads` on the same computer. Identical uploads with the same name reuse the stored file. Guided Replay loads completed sessions from the loopback workbench. Older sessions without a saved copy can still be inspected with their original video selected by hand. Repeating a job makes a new history row and can reuse a result for matching video, camera, model, policy and analyzer inputs.

## Teacher walkthrough

### Accuracy profile

The local workbench uses YOLO11s at 960 px and 0.30 confidence when the official `yolo11s.pt` checkpoint is installed at `data/bellevue-demo/yolo11s.pt`. Remove any old detector environment overrides to select this profile automatically. For an explicit override, point `STMS_VIDEO_WEIGHTS` to the absolute checkpoint path and set `STMS_VIDEO_IMGSZ=960` and `STMS_VIDEO_CONF=0.30`. Reanalyze a recording to get results under the updated profile. Stored reports identify the model that produced them.

Results shows an exploratory comparison against visually reviewed vehicle counts in a fixed region on 12 frames from the two Bellevue recordings. Reproduce it with `python -m scripts.benchmark_bellevue_counts --morning <morning.mp4> --afternoon <afternoon.mp4> --weights data/bellevue-demo/yolo11s.pt --cctv-weights <bmd45-yolov12s.pt> --out experiments/results/stms_bellevue_count_benchmark.json`. The separately labeled BMD-45 test is reproducible with `python -m scripts.benchmark_cctv_counts --cache data/bellevue-demo --baseline data/bellevue-demo/yolo11s.pt --candidate <bmd45-yolov12s.pt> --out experiments/results/stms_cctv_count_benchmark.json --download`. [IISc CCTV checkpoint and provenance](https://huggingface.co/iisc-aim/BMD-45/tree/main/weights/YOLOv12-S)

The IISc detector performed better on its dataset and was less accurate on the Bellevue sample. Both benchmarks measure visible vehicle counts per frame. Inbound crossings and forecasts need separate reference data.

### Live monitoring with a recording

Open [Live](http://127.0.0.1:8083/dashboard/#live), choose **Demo Live – Upload Video**, and select a recording. STMS analyzes frames while the recording plays at 1×. Playback buffers if it reaches the latest analyzed timestamp. Counts, charts, alerts and the signal countdown use the video clock. Pause freezes that clock. Restart starts a fresh monitoring session for the same file, and Stop ends it. The session appears in Results and Guided Replay after playback reaches the end.

Live and **Analyze a Video** have separate session IDs and workers. You can select the same recording or a different one on each page. Open **Analyze a Video**, start a job, then return to **Live**. Both statuses stay visible, and completed offline reports can be opened in **Results** while Live continues. Stopping a job affects only the selected session.

The local workbench runs one offline job and one live source at a time. The background worker uses CPU, leaving GPU acceleration available to Live when configured, and video workers limit CPU inference threads. On hosts with fewer than four logical CPUs, the offline worker waits while Live has the processing slot and resumes automatically. To enable this policy on another machine, set `STMS_QUEUE_OFFLINE_DURING_LIVE=1` and restart the server.

After two minutes of contiguous samples, the video workbench forecasts the mean vehicles in view for the next minute. It weights the frozen Ridge forecast at 70% and the preceding two-minute mean at 30%. The original edge forecast and the simulated signal controller use their existing logic. See Results for the retrospective comparison against detector counts. Run `python -m scripts.benchmark_video_forecast --out forecast-review.json` to repeat the matched P105 comparison. Add `--analysis PATH` for each saved Ridge-only report you want to compare.

In **Analyze a Video**, choose a recording and click **Analyze Video with AI**. The completed report appears on the page with CSV and JSON downloads and a browser PDF print option. Whole-frame mode estimates visible traffic and counts distinct tracker IDs. Choose a matching camera under **Camera profile and lane setup** for line crossings, lane forecasts and advisory signal timing. Browser preview and replay depend on the file's video codec. MP4 with H.264 is widely supported. The hosted demonstration links to the local workbench for Python inference.

The alternate **Real Live Camera / Server** option accepts RTSP and compatible HTTP/HTTPS streams, or a local device such as `webcam:0`. Select a profile for the physical viewpoint before connecting. The panel displays the latest analyzed frame with detection overlays and retries temporary stream failures. Disconnecting saves the measurements obtained so far. Raw camera footage is displayed in the local browser during monitoring, while the saved report contains numerical results. A camera must be reachable from the computer running STMS. Signal timings remain advisory.

1. Open STMS and explain the objective. Keep **Real analysis** visible. The hosted **Demo mode** shows bundled examples.
2. Open **Analyze a video** and select the original MP4. The workbench supports MP4, MOV, AVI, M4V, MKV and WebM up to 2 GB. Browser playback also depends on the codec. H.264 MP4 is useful for the evaluation.
3. For approach-specific results, choose a matching camera under **Camera profile and lane setup**. For a new camera, place approach centres on the inbound roads, set their reach and inspect their positions. Click **Analyze Video with AI** to follow the job through validation, detection, tracking and completion.
4. Play the recording after analysis. The overlay shows boxes, tracked IDs, confidence, approach markers and the lines derived from the camera profile. Counts and forecasts update every two seconds. Explain that the track ID identifies a detection sequence within one recording.
5. Open **Overview** and compare inbound crossings with the average number of vehicles in view. A vehicle can appear in many occupancy samples and contribute one inbound crossing for its track ID.
6. Open **Signal timing**. Move the demand window and simulated-cycle sliders. Explain the configured previous duration, suggested green, yellow and all-red sequence. Actual controller state is unavailable from ordinary footage.
7. Open **Alerts**, check the trigger and replay its timestamp. Acknowledging or resolving a saved alert updates its SQLite status.
8. Open **Analytics**. Compare the type chart, occupancy, crossings over time, and historical rows. Use **View** to switch the whole dashboard to another completed attempt.
9. Open **Results**. Show the filename, analysis ID, resolution, processing time and frames. Download CSV or JSON, or choose **Save report as PDF** and select the browser's PDF destination.
10. Open **System** to show the actual local service and model status. Open **Live** to show the connected-camera path or its explicit unavailable state.

## Methods and interpretation

- **Stack.** React and Vite for the UI, FastAPI for the local HTTP API, SQLite and JSON for job and result storage, OpenCV for decoding, YOLO and ByteTrack for detection and association. Existing live telemetry and simulated demonstration data have separate sources.
- **Processing.** The workbench locates and preflights the selected recording. An isolated child process decodes using media timestamps and runs tracking at up to four frames per second. It saves overlays and occupancy samples every two seconds. Persistence predicts congestion bands and ridge forecasts the next minute's average visible vehicles after sufficient history.
- **Crossings.** A finite line across each approach centre is perpendicular to the direction toward the estimated intersection centre. A track must move inward across the line between consecutive tracked observations. Each ID contributes at most one count. String labels on provisional geometry identify approaches within the dashboard.
- **Density.** The average visible vehicle total over a 30-second window is classified as Low below 3, Moderate from 3, High from 6 and Severe from 10 by default. This is an image-occupancy proxy for the configured roads. Crossings per window are the measured flow indicator. A partial final window is displayed with its own duration.
- **Signals.** The default per-approach demand cutoffs are 1, 3 and 5 visible vehicles, with green times of 15, 30, 45 and 60 seconds. A simulated opposing phase takes the larger recommendation and uses 4 seconds yellow plus 2 seconds all red. A JSON policy can override `density`, `lane_demand`, `greens`, `previous_green`, `yellow`, `all_red` and `stopped_seconds` through `STMS_VIDEO_POLICY`. These are configurable demonstration settings.
- **Alerts.** A complete 30-second window entering High or Severe produces a congestion alert. A new interval requiring more green than the configured duration produces a timing warning by approach. A continuously tracked vehicle that stays within the position tolerance in the monitored junction core for 20 seconds produces a possible stopped-vehicle alert. This excludes typical approach queues through geometry. Failed jobs produce operational alerts. Unverified signal states cannot trigger red-light violations.
- **Limitations and future work.** Occlusion, camera angle, compression, tracker ID switches and approximate lines can affect counts. A provisional profile and thresholds need independent review and hand-counted validation. Physical speed, queue length and signal-violation enforcement require calibrated geometry, validated monitoring regions or controller state. Future work includes reviewed lines and signal states, manual ground-truth evaluation and any authorized controller integration.

## Verification commands

```powershell
npm.cmd --prefix dashboard test
& $stmsPython -m pytest -q tests/test_video_traffic.py tests/test_workbench.py tests/test_analyze_video.py
```

Evaluate light, heavy and empty-road cases in Analytics, and use an invalid file to demonstrate the failed job and operational alert. Repeating a valid recording should create a different analysis ID. Compare an alert's timestamp and reason with the replay window. Leave the browser on a timestamp after about 2:00 if the teacher wants to see both forecast models immediately.

## Twenty viva questions

1. **What problem does STMS solve?** It turns footage into checkable traffic counts, recommendations and reports.
2. **What is detection?** It locates a vehicle in one image and labels its likely class.
3. **What is tracking?** It links detections over time and gives each track an ID.
4. **Why use YOLO?** It locates and classifies objects in one inference pipeline.
5. **Why use ByteTrack?** It associates consecutive vehicle detections into tracks.
6. **How do you avoid frame-by-frame double counting?** Each tracked ID contributes one inbound line crossing.
7. **What is a counting line?** A finite image segment placed across a configured approach.
8. **What happens when a vehicle is hidden?** Tracking can reconnect it or assign a new ID. Hand-counted validation quantifies the error.
9. **What vehicle classes are supported?** Cars, motorcycles, buses and trucks when the loaded checkpoint supplies those classes.
10. **What does confidence mean?** It is the detector score for that detection, subject to the chosen cutoff.
11. **What is the difference between occupancy and flow?** Occupancy is the number in view. Flow counts line crossings during an interval.
12. **How is congestion assigned?** The mean observed occupancy is compared with documented thresholds.
13. **Why do forecasts sometimes contain decimals?** They forecast the average number in view across the next minute.
14. **Why does a short clip have no forecast?** The models first collect a history window.
15. **How is green time recommended?** The average approach demand is mapped to one of the configured green durations.
16. **What keeps the simulated phases apart?** The plan inserts a yellow interval and an all-red interval between greens.
17. **When is a stopped vehicle reported?** A track stays nearly stationary in the monitored intersection core for the configured time.
18. **Why are red-light alerts unavailable here?** Reliable alerts require verified signal state, stop lines and motion evidence.
19. **Where are results stored?** SQLite indexes jobs and statuses. Validated JSON stores measurements and events.
20. **How would you prove counting accuracy?** Label vehicle crossings manually on independent clips and compare events, totals and classes.
