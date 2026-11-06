# STMS read-only dashboard

A minimal, **read-only** monitor for one intersection. It has three things on
it, in two regions that never merge (ADR-014):

| region | panel | source | model |
|---|---|---|---|
| **Live forecasts** | next-minute vehicle count | `GET /count_forecast/{id}/latest` | ridge v1, `ridge@73532968dcf2` (P105) |
| **Live forecasts** | congestion class, next 60 s | `GET /prediction/{id}/latest` | persistence v1, `persistence@2431c6641b9c` (P103/P104) |
| **Results** | evaluation evidence | `GET /evidence` | frozen P103/P105 results, read from the committed files, each with its commit |

The roles are ADR-027's. The page cannot send anything: its API client
(`src/api.js`) issues only `GET`, and only to those three endpoints, and a test
pins that.

Live also shows what was counted, from `GET /vehicle_count/{id}/history` and the
heartbeat's lane map, and a walkthrough and glossary (`src/Tour.jsx`, D33). The
walkthrough's examples stay inside its card: it never replaces real data.

Analyze a video (D34) plays a recording beside a results file from
`scripts/analyze_video.py`. Both are opened in the browser and nothing is sent
anywhere. Live also lists what has reported (`GET /sites`) and a labelled
calculation of green shares, which reaches no signal. The signal heads stay `?`.

The Engineering view (D35) sits behind one control on Live and on Analyze, and is off by default. It adds
counts by class, PCU with its working, and the source of each number, from `GET /vehicle_count/{id}/latest`
or the results file. Queue reads "Not measured", because nothing on the camera path measures one.

## What the page refuses to do

- **Show a missing approach as zero or LOW.** An approach with no forecast
  shows *no forecast*. A real zero stays a zero.
- **Show a stale forecast as current.** Anything older than its 60 s horizon,
  by the server's clock, is labelled stale and dimmed.
- **Show part of a bad response.** A response with the wrong role for its
  panel, an unknown model id, an out-of-range value, an unknown approach, or a
  `missing_approaches` list that disagrees with the values is shown as
  *invalid*, with the reason.
- **Show live accuracy.** Scoring forecasts against the detector's own counts
  would be circular (ADR-014). Evaluation numbers appear only in Results, as
  historical evidence.
- **Hide P97a.** The live region's technical details state that 0.0 in the controller's state
  means "no forecast for this approach" and that LOW is encoded as 1/3
  (ADR-020 as amended, P110), and that P97a Part 2 (the controller under
  forecast faults) is deferred and still open. Before D2 it said a missing
  approach was 0.0, the same as LOW, which stopped being true at P110.

## Run, build, test

```bash
cd dashboard
npm install          # exact versions pinned in package.json
npm test             # vitest: read-only API, error/stale/invalid states, missing never zero/LOW
npm run build        # -> dashboard/dist, served by the FastAPI server at /dashboard
```

Then start the server (`uvicorn server.app:app --port 8000`) and open
`http://127.0.0.1:8000/dashboard/?id=<intersection>`. During development, run
`npm run dev`, which proxies the three endpoints to port 8000.

## Testing a state without a camera (D36)

`scripts/ui_fixture.py` runs the real server, holding one chosen state, behind a small page host.
No camera, broker or edge is needed, and nothing touches the deployment database.

```bash
python scripts/ui_fixture.py --list                  # the states
python scripts/ui_fixture.py --state missing_count   # then open the address it prints
```

While it runs, type a state name to switch with the page left open (`normal`, `stale_edge`,
`edge_silent`, `partial`, `no_data`, `high`, `low`), `server_down` to stop only the API, or `quit`.
The page stays open while the API is down and recovers when it returns. `--clean` removes folders
left by a run that was killed.

The values are made up to exercise the page. The badge reads `Replay · TEST_FIXTURE_<state>`, the
model ids are `persistence@000000000000` and `ridge@000000000000`, and nothing here is evidence of
anything.

`src/fixtures/` holds each state's responses, generated from the real server with its clock fixed.
`tests/test_ui_fixture.py` fails if the server no longer sends exactly them, and
`src/fixtures.test.js` fails if the page's own validators refuse them. After an intended change to
what the server sends, run `python scripts/ui_fixture.py --write-fixtures` and review the diff.

## Scope

This is a deliberately small, ADR-008-descoped shape:

- it polls every 2 s, the PRD's refresh budget, rather than using WebSockets;
- there are no charts;
- the agreement ribbon (D26) is on Live, but there is no detection overlay on
  Live; boxes appear only on Analyze a video, from a results file;
- there is no login, because the page only reads. The server's write
  endpoints need a bearer token (D9), which the dashboard never holds.

It is dark mode only, in the D18 brand palette (`#080808` background, `#EC7C22`
for chrome only), with every colour in `src/theme.css` and no external font or
script requests.

**Making a results file for Analyze a video:** see Execution Manual §5.5. It
needs a camera profile, and today only the three `150th_*` cameras have one.

**Future scope, not before submission (D38):**
- **A local analysis component.** The user picks a compatible recording and a
  camera profile; a separate local component runs the existing pipeline,
  validates the results file, and opens the video and results together.
  Frames stay on that machine, and this page and the server keep their roles.
  It needs its own architecture and requirements review.
- **Section-aware tours.** Separate Operator and Engineering tours for Live
  and for Analyze a video.
- **A visual prototype of a glossier style,** judged against D18's measured
  contrast before any adoption.
