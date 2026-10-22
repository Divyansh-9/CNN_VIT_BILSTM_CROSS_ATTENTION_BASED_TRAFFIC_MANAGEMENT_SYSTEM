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
- **Hide P97a.** The live region states that 0.0 in the controller's state
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

## Scope

This is a deliberately small, ADR-008-descoped shape:

- it polls every 2 s, the PRD's refresh budget, rather than using WebSockets;
- there are no charts;
- there is no deferred-agreement ribbon or detection overlay (ADR-014 §2–3);
- there is no login, because the page only reads. The server's write
  endpoints need a bearer token (D9), which the dashboard never holds.

It is dark mode only (`#0D1117`, accent `#6366F1`), with no external font or
script requests.
