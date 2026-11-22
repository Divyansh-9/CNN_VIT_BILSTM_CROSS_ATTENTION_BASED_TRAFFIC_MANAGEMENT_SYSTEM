# STMS read-only dashboard

For the local recorded-video workbench, installation, tracking, analytics and
teacher walkthrough, see [STMS recorded-video demonstration](../docs/90-manual/VIDEO_ANALYSIS_DEMO.md).

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

## Project preview and operator access

The default address opens the team page. **Explore the project** opens the
technical walkthrough, and **Launch project** opens the console with bundled
sample data. This preview needs no account and makes no API requests.

Open the same dashboard with `?id=<intersection>` for real traffic data, or
with an analysis link from the workbench. These views and their data endpoints
require sign-in.

- **Sign in** (`src/Auth.jsx`) offers Create account, Forgot password and, from the link in a
  reset message, Choose a new password. `src/AuthGate.jsx` asks `GET /auth/me` and shows the project only
  when it names a user; after sign-in it opens `#home`, then Explore or Launch as before.
- **Sessions:** an HttpOnly, SameSite=Strict cookie set by the server. The page never reads, stores or sends
  it itself, and keeps nothing about it in browser storage. Any read that answers 401, a check every minute,
  tab focus and a back/forward-cache restore all end at the sign-in screen when the session has ended.
- **Sign out** is in the account menu beside the theme switch on every page. It replaces the history
  entry, so Back does not reopen the console, and the server deletes the session.
- **The second POST client:** `src/auth.js` posts only to `/auth/register|login|logout|forgot|reset`.
  `api.js` stays GET-only. Both are pinned by `dashboard.test.jsx`.
- **The server side** is `server/auth.py`; its settings are in `.env.example`. In development, `npm run dev`
  proxies `/auth` to port 8000 with the browser's Host, which the server's same-origin check needs.

The sign-in screens use a navy and electric-cyan look from the `--auth-*` tokens in `theme.css`, the
same in every theme and never used on traffic data.

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

Then start the server (`python -m uvicorn server.app:app --port 8000`) from
the project root and open `http://127.0.0.1:8000/`. During development, run
`npm run dev`, which proxies the operator API routes to port 8000.

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
- since D46 there is a login: see "Signing in" below. The server's write
  endpoints still need a bearer token (D9), which the dashboard never holds,
  and a signed-in session can only read.

It is dark mode only, in the D18 brand palette (`#080808` background, `#EC7C22`
for chrome only), with every colour in `src/theme.css` and no external font or
script requests.

**Making a results file for Analyze a video:** see Execution Manual §5.5. It
needs a camera profile, and today only the three `150th_*` cameras have one.
**The local workbench (D40, D41, Manual §5.5.1).** `scripts/demo_launcher.py`
serves this same build on 127.0.0.1 as its only page.
- **Workbench mode:** the page asks `/workbench/capabilities`. When that is answered, Analyze gains the
  whole analysis inline (find the opened file on disk, declare or place a camera, analyse, results beside
  the video), and Live gains the replay.
- **Since D42:** choosing a camera previews its lanes over the video, and an analysed video can be replayed
  on Live. Live can also connect the camera named by `STMS_CAMERA_URL` in the workbench's environment, which
  the page never sees (Manual §5.5.2).
- **Server mode:** the server has no `/workbench` route, so served by the server this page is exactly the
  read-only page it was.
- **Two clients:** `api.js` stays GET-only. `workbench.js` is the only module that may POST, only to the
  workbench's own actions, and only plain data, never a file's bytes. The video plays from the file the
  viewer opened.

**Future scope, not before submission (D38):**
- **A local analysis component:** built in D40 and D41 as the workbench, on
  the owner's instructions of 2026-11-06. That includes provisional cameras,
  placed in the page and kept on that computer. Still future: promoting a
  provisional camera to a reviewed profile in `cameras/`, which stays a
  reviewed change under ADR-028.
- **Section-aware tours.** Separate Operator and Engineering tours for Live
  and for Analyze a video.
- **A visual prototype of a glossier style,** judged against D18's measured
  contrast before any adoption.
