// Signal timing, Alerts, System and the exports, on the committed fixtures: the
// real server's own responses (scripts/ui_fixture.py).
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App.jsx";
import normal from "./fixtures/normal.json";
import partial from "./fixtures/partial.json";
import staleEdge from "./fixtures/stale_edge.json";
import high from "./fixtures/high.json";
import { greenTimes } from "./OpsPages.jsx";
import { advisorySplit, alertEvents, classTotals, currentAlerts, detectorFps, failSafe, safetyLimits, splitExplanation, toCsv } from "./ops.js";

window.scrollTo = () => {};
afterEach(() => { cleanup(); window.location.hash = ""; try { window.sessionStorage.clear(); } catch { /* none */ } });

const ID = "test-fixture";
const state = (f, path) => {
  const r = f.responses[path];
  return !r || r.status === 404 ? { status: "unavailable" } : { status: "ok", data: r.body };
};
const snap = (f) => ({ health: state(f, "/health"), cls: state(f, `/prediction/${ID}/latest`), count: state(f, `/count_forecast/${ID}/latest`),
  heartbeat: state(f, `/heartbeat/${ID}/latest`), latestCounts: state(f, `/vehicle_count/${ID}/latest`) });
const fetcherFor = (f) => async (path, init) => {
  if (init?.method && init.method !== "GET") throw new Error(`sent ${init.method}`);
  const r = f.responses[path];
  if (!r) return { ok: false, status: 404, json: async () => ({}) };
  return { ok: r.status < 400, status: r.status, json: async () => r.body };
};

describe("signal timing is advisory and kept honest", () => {
  it("splits green by expected vehicles per axis, from a current forecast for all four approaches", () => {
    const split = advisorySplit(snap(normal).count);
    expect(split.map((s) => s.axis)).toEqual(["N–S", "E–W"]);
    expect(split[0].demand).toBeCloseTo(4.3);
    expect(split[1].demand).toBeCloseTo(7.2);
    expect(split[0].share + split[1].share).toBeCloseTo(1);
    expect(splitExplanation(split)).toMatch(/E and W expect 7\.2 vehicles/);
  });

  it("gives no split when an approach is missing or the forecast is out of date", () => {
    expect(advisorySplit(snap(partial).count)).toBeNull();
    expect(advisorySplit(snap(staleEdge).count)).toBeNull();
    expect(splitExplanation(null)).toMatch(/needs a current vehicle forecast/);
  });

  it("takes two all-red clearances from the cycle and holds each green between the server's limits", () => {
    const limits = safetyLimits(snap(normal).health);
    expect(limits).toMatchObject({ min_green_s: 10, max_green_s: 90, all_red_s: 3 });
    const g = greenTimes([{ axis: "A", share: 0.95, demand: 19 }, { axis: "B", share: 0.05, demand: 1 }], 60, limits);
    expect(g[0].green).toBeCloseTo(51.3);
    expect(g[1].green).toBe(10);                 // 2.7 s would break the minimum green
    expect(g[1].clamped).toBe(true);
    expect(greenTimes(null, 60, limits)).toBeNull();
  });

  it("states the fail-safe rule from the heartbeat, and claims nothing it cannot see", () => {
    const limits = safetyLimits(snap(normal).health);
    expect(failSafe(snap(normal).heartbeat, limits).kind).toBe("normal");
    expect(failSafe(snap(staleEdge).heartbeat, limits)).toMatchObject({ kind: "fallback" });
    expect(failSafe({ status: "unavailable" }, limits).kind).toBe("unknown");
  });

  it("shows unlit signal heads, says no signal is controlled, and shows no evidence", async () => {
    window.location.hash = "#signals";
    render(<App fetcher={fetcherFor(normal)} search={`?id=${ID}`} hash="#signals" />);
    await waitFor(() => expect(document.querySelector('[data-split="ok"]')).toBeTruthy());
    const page = document.querySelector('[data-section="signals"]');
    expect(page.textContent).toMatch(/No traffic signal is controlled by this system/);
    expect(page.querySelectorAll('[aria-label$="state not reported"]').length).toBe(2);
    expect(page.textContent).not.toMatch(/macro-F1|P105|ridge 0\.748/);
  });
});

describe("alerts", () => {
  it("raises nothing when everything is current and nothing is HIGH beyond one approach", () => {
    const keys = currentAlerts(snap(normal)).map((a) => a.key);
    expect(keys).toEqual(["high"]);                          // E is HIGH in the normal state
    expect(currentAlerts(snap(normal))[0].severity).toBe("warning");
  });

  it("calls heavy congestion serious, and a silent edge critical", () => {
    expect(currentAlerts(snap(high)).find((a) => a.key === "high")).toMatchObject({ severity: "serious", title: "Heavy congestion forecast" });
    const stale = currentAlerts(snap(staleEdge));
    expect(stale.find((a) => a.key === "edge-silent").severity).toBe("critical");
    expect(stale.map((a) => a.key)).toContain("level-stale");
    expect(stale.map((a) => a.key)).not.toContain("high");   // an old HIGH is not a current alert
  });

  it("says when an approach has no forecast, never treating it as LOW", () => {
    expect(currentAlerts(snap(partial)).find((a) => a.key === "missing").detail).toMatch(/No level for E, W/);
  });

  it("records a condition starting and clearing as events", () => {
    const a = currentAlerts(snap(normal)), b = currentAlerts(snap(staleEdge));
    const events = alertEvents(a, b, 1000);
    expect(events.filter((e) => e.kind === "raised").map((e) => e.key)).toContain("edge-silent");
    expect(events.filter((e) => e.kind === "cleared").map((e) => e.key)).toEqual(["high"]);
  });
});

describe("detector and vehicle mix", () => {
  it("reads the edge's frame rate and the vehicles by class from current lanes", () => {
    expect(detectorFps(snap(normal).latestCounts)).toMatchObject({ fps: 0.5, frameEvery: 2 });
    expect(classTotals(snap(normal).latestCounts)).toMatchObject({ total: 11, totals: { car: 8, bus: 1, "auto-rickshaw": 1, motorcycle: 1 } });
    expect(detectorFps({ status: "unavailable" })).toBeNull();
  });
});

describe("system page", () => {
  it("shows each part's state in words, and lists what the server does not report", async () => {
    window.location.hash = "#system";   // the console follows the address; set it so a late hashchange cannot move the page
    render(<App fetcher={fetcherFor(normal)} search={`?id=${ID}`} hash="#system" />);
    await waitFor(() => expect(document.querySelector('[data-health="Detector (YOLO)"]').textContent).toMatch(/0\.50 fps/));
    expect(document.querySelector('[data-health="Server"]').getAttribute("data-kind")).toBe("ok");
    expect(screen.getByText("CPU, memory and GPU use")).toBeTruthy();
  });
});

describe("exports", () => {
  it("quotes every CSV field, so commas and quotes cannot break a row", () => {
    expect(toCsv(["a", "b"], [{ a: 'x, "y"', b: 1 }, { a: null }])).toBe('"a","b"\r\n"x, ""y""","1"\r\n"",""');
  });
});

describe("the alert log", () => {
  it("does not log conditions that were already present when the page opened", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAlerts } = await import("./useAlerts.js");
    const loading = { health: { status: "loading" }, cls: { status: "loading" }, count: { status: "loading" }, heartbeat: { status: "loading" } };
    const { result, rerender } = renderHook(({ s }) => useAlerts("t1", s), { initialProps: { s: loading } });
    rerender({ s: snap(normal) });               // first complete reading: E is HIGH, already present
    expect(result.current.current.map((a) => a.key)).toEqual(["high"]);
    expect(result.current.history).toEqual([]);
    rerender({ s: snap(staleEdge) });            // a real change: the edge goes silent, HIGH clears
    const kinds = result.current.history.map((e) => `${e.kind}:${e.key}`);
    expect(kinds).toContain("raised:edge-silent");
    expect(kinds).toContain("cleared:high");
  });
});
