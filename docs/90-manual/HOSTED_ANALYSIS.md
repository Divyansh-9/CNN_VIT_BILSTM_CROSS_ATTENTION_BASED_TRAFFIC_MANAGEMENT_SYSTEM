# Host the STMS dashboard with AI analysis

Deploy the FastAPI application and dashboard on one HTTPS origin. FastAPI serves the
dashboard at /dashboard/ and the existing analysis routes at /workbench/. The
browser uses relative API paths and the STMS session cookie. No CORS policy or
cross-origin cookies are needed for this layout. The static Sites build can show
the project and preview videos. Running YOLO and ByteTrack requires the Python
service and a detector checkpoint on a separate compute host.

## Linux host setup

Use a Linux host with Docker Compose, persistent storage, and a DNS name that
points to it. Start with at least 4 CPU cores and 8 GiB RAM for the two CPU video
workers. Allow ports 80 and 443 for the included HTTPS proxy. On the host:

1. Check out the STMS source with its Git history. The image uses the history
   to record the provenance of the published experiment results.
2. Obtain one of the detector checkpoints described in the project README
   and verify its checksum against experiments/results/model_artifacts.sha256
   where available. Keep the file outside the checkout. The container user
   (UID 10001) needs read access. A general-purpose YOLO checkpoint supports
   its own pretrained vehicle classes.
3. Set these variables in a private environment file on the host:

       STMS_HOSTNAME=stms.your-domain.example
       STMS_WEIGHTS_FILE=/srv/stms/models/yolov8s.pt
       STMS_API_TOKEN=<a long randomly generated server-ingest token>
       STMS_HOSTED_CAMERA_URL=

   Leave the optional camera URL empty until you have permission to show
   a feed to STMS users. Set it to a real RTSP or HTTP(S) camera reachable
   from the host. Credentials, if required, stay on the server. Users select a
   matching camera profile and connect to the configured feed. Camera URLs
   supplied by browser users are disabled in hosted mode.
4. Start the services from the repository root:

       docker compose --env-file /srv/stms/hosted.env -f deploy/compose.hosted.yml up -d --build
       docker compose --env-file /srv/stms/hosted.env -f deploy/compose.hosted.yml logs -f app https

5. Open the HTTPS address and register an STMS account. Each teammate registers
   a separate account. Uploaded recordings, camera profiles, analyses and
   alerts are isolated by account. For an internet deployment with an existing
   team access proxy, keep its ACL in place in front of the same origin.
   Set the existing STMS_SMTP_* options on the app service if password
   recovery emails are required.

This stack runs a single FastAPI process. Use one replica: video job control is
in memory and each account's index is stored in SQLite. The server can run one
Live workload and one offline workload at the same time. A second request for
an occupied workload slot receives a message to retry. A video is limited to
512 MiB and an account's saved videos to 2 GiB. Plan and monitor disk space
for all accounts and back up the analysis-data volume. Report deletion does not
currently delete the retained upload. A process restart interrupts current
work; completed reports remain available.

A trusted HTTPS reverse proxy may replace Caddy if it preserves the original
Host header and accepts uploads up to the advertised size. When supplying your
own proxy, set STMS_HOSTED_ORIGIN to its external origin without a path and
STMS_PUBLIC_URL to the dashboard address. STMS_COOKIE_SECURE must be 1 for
an HTTPS deployment. Keep Uvicorn behind the proxy. If the system also receives
MQTT data from an edge camera, configure the existing broker and ingest service
separately to use the same API/database. The included web deployment does not
need MQTT to process a selected video or a configured server camera.

## Verify from two browsers

- Sign in with a test account and open System. Confirm the detector
  configuration is ready.
- In Live, choose Demo Live, pick a browser-playable video and click
  Start monitoring. Confirm that detections and current traffic metrics
  update during playback. Use Pause, Resume and Stop.
- While Live runs, use Analyze a Video to choose a second video and click
  Start Analysis. Check both status indicators, then open Analytics and
  Results from the same dashboard. Check the report filename and saved replay.
- Sign in with another account in another browser. Confirm it only sees its
  own jobs. Give each test account a different video to check report ownership.
- If a camera is configured, connect using Real Live Camera / Server.
  Verify the incoming feed and its detections before sharing access.

For the demo, H.264 MP4 is a practical browser-playable format. With other
formats, server decoding and browser preview depend on the available codec.
Use a reviewed profile for lane counts and lane-based forecasts. Videos without
a matching profile still support whole-frame detection and traffic statistics.
