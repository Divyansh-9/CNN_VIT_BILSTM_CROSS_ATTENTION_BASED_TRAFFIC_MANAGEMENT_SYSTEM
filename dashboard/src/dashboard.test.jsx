import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App, { SECTIONS, intersectionFromUrl, sectionFromHash } from "./App.jsx";
import { get, isAllowed } from "./api.js";
import { ICONS } from "./icons.jsx";
import { ObservedCounts, scaleTop } from "./Analytics.jsx";
import { Horizon, Intersection, SCALE_MAX, TURN, horizon, junction, ribbonLength, ribbonPath } from "./Intersection.jsx";
import { ClassPanel, CountPanel, ExpectedShare, EvidencePanel, ForecastTable, HistoryPanel, Overview, SiteStrip, StatusBanner, StatusPanel, SummaryTiles, TimingSuggestion, operatorStatus, overview, recentCounts, timingSuggestion } from "./Panels.jsx";
import { EXAMPLES, GLOSSARY, LIVE_STEPS, MORE_STEPS, QUIZ } from "./Tour.jsx";
import { ReplayNote, SourceBadge } from "./Source.jsx";
import { Agreement, AGREEMENT_LABEL } from "./Agreement.jsx";
import { AnalyzeVideo, sampleAt } from "./Analyze.jsx";
import { BusyByHour, busyByHour } from "./Busy.jsx";
import { validateAnalysis, validateClass, validateCount, validateCountHistory, validateHeartbeat, validateHistory, validateChecks, validateSites, agreement } from "./validate.js";

afterEach(cleanup);

const COUNT = {
  at: 1000, model: "ridge@73532968dcf2", role: "next_minute_count (ridge)", age_s: 4.0,
  stale: false, horizon_sec: 60, counts: { N: 2.5, E: 0.0 }, missing_approaches: ["S", "W"],
};
const CLASS = {
  at: 1000, model: "persistence@2431c6641b9c", role: "congestion_class (persistence)", age_s: 3.0,
  stale: false, predictions: { N: "HIGH", E: "LOW" }, confidences: { N: 0.8, E: 0.76 },
  missing_approaches: ["S", "W"],
};
const ok = (data) => ({ status: "ok", data });
const CLASS_ROW = { at: 1000, model: "persistence@2431c6641b9c", role: "congestion_class (persistence)",
  predictions: { N: "HIGH", E: "LOW" }, missing_approaches: ["S", "W"] };
const COUNT_ROW = { at: 1000, model: "ridge@73532968dcf2", role: "next_minute_count (ridge)",
  counts: { N: 2.5, E: 0.0 }, missing_approaches: ["S", "W"] };
const lane = (a) => document.querySelector(`[data-approach="${a}"]`);

describe("read-only by construction", () => {
  it("allows only the listed GET endpoints", () => {
    for (const p of ["/count_forecast/j1/latest", "/prediction/j1/latest", "/evidence", "/health",
                     "/prediction/j1/history", "/count_forecast/j1/history",
                     "/vehicle_count/j1/history?window=1h", "/vehicle_count/j1/history?window=24h"]) {
      expect(isAllowed(p)).toBe(true);
    }
    for (const p of ["/observation", "/prediction/j1", "/count_forecast/j1", "/history/j1", "/x",
                     "/healthz", "/prediction/j1/history/x", "/prediction/j1/history?limit=500",
                     "/count_forecast/j1/history/x", "/count_forecast/j1/history?limit=500",
                     "/count_forecast/j1/latest/x", "/vehicle_count/j1/lane_0",
                     "/vehicle_count/j1/history", "/vehicle_count/j1/history?window=2h",
                     "/vehicle_count/j1/history?window=1h&x=1"]) {
      expect(isAllowed(p)).toBe(false);
    }
  });
  it("takes an id only in the server's pattern, length included (P142)", () => {
    expect(isAllowed(`/prediction/${"x".repeat(32)}/latest`)).toBe(true);
    expect(isAllowed(`/prediction/${"x".repeat(33)}/latest`)).toBe(false);
    expect(intersectionFromUrl(`?id=${"x".repeat(32)}`)).toBe("x".repeat(32));
    expect(intersectionFromUrl(`?id=${"x".repeat(33)}`)).toBe("j1");
    expect(intersectionFromUrl("?id=j1.x")).toBe("j1");
  });
  it("refuses to call anything else, and uses GET", async () => {
    await expect(get("/observation", async () => ({}))).rejects.toThrow(/not an allowed endpoint/);
    let method;
    await get("/evidence", async (_, init) => { method = init.method; return { ok: true, status: 200, json: async () => ({}) }; });
    expect(method).toBe("GET");
  });
  it("contains no write call anywhere in the source", () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    for (const f of readdirSync(dir).filter((n) => /\.(js|jsx)$/.test(n) && !n.includes(".test."))) {
      // Code only: a comment saying /observation is unreachable is not a call to it.
      const text = readFileSync(join(dir, f), "utf8")
        .replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
      expect(text).not.toMatch(/method:\s*["'](POST|PUT|PATCH|DELETE)/i);
      expect(text).not.toMatch(/\/observation|signal\/command/);
    }
  });
});

describe("API errors become explicit states", () => {
  it("maps 404, 5xx, unreachable and non-JSON", async () => {
    expect(await get("/evidence", async () => ({ ok: false, status: 404 }))).toEqual({ status: "unavailable" });
    expect((await get("/evidence", async () => ({ ok: false, status: 503 }))).status).toBe("error");
    expect((await get("/evidence", async () => { throw new Error("down"); })).status).toBe("error");
    expect((await get("/evidence", async () => ({ ok: true, status: 200, json: async () => { throw new Error(); } }))).status).toBe("error");
  });
  it("renders each one", () => {
    render(<CountPanel state={{ status: "unavailable" }} />);
    expect(document.querySelector('[data-state="unavailable"]')).toBeTruthy();
    cleanup();
    render(<CountPanel state={{ status: "error", reason: "server answered 503" }} />);
    expect(screen.getByText(/503/)).toBeTruthy();
  });
});

describe("missing is never zero and never LOW", () => {
  it("count panel: real zero stays zero, absent approaches say no forecast", () => {
    render(<CountPanel state={ok(COUNT)} />);
    expect(lane("E").textContent).toMatch(/0\.0/);
    for (const a of ["S", "W"]) {
      expect(lane(a).querySelector('[data-missing="true"]')).toBeTruthy();
      expect(lane(a).textContent).not.toMatch(/\d/);
    }
  });
  it("class panel: absent approaches carry no class", () => {
    render(<ClassPanel state={ok(CLASS)} />);
    expect(lane("E").textContent).toContain("LOW");
    for (const a of ["S", "W"]) {
      expect(lane(a).textContent).not.toMatch(/LOW|MEDIUM|HIGH/);
      expect(lane(a).querySelector('[data-missing="true"]')).toBeTruthy();
    }
  });
});

describe("stale and invalid responses", () => {
  it("labels a stale forecast", () => {
    render(<CountPanel state={ok({ ...COUNT, stale: true, age_s: 75 })} />);
    expect(document.querySelector('[data-state="stale"]')).toBeTruthy();
  });
  // UX step 1b: the warning measured 2.27:1 while it was dimmed with the data.
  it("puts the stale warning above the data, not inside it, with its age", () => {
    for (const Panel of [CountPanel, ClassPanel]) {
      const data = Panel === CountPanel ? COUNT : CLASS;
      render(<Panel state={ok({ ...data, stale: true, age_s: 75 })} />);
      const warning = document.querySelector('[data-state="stale"]');
      expect(warning.closest("[data-freshness]")).toBeNull();
      expect(warning.textContent).toMatch(/Stale, 75 s old/);
      expect(document.querySelector('[data-freshness="stale"]')).toBeTruthy();
      cleanup();
    }
  });
  it("keeps stale values readable rather than hiding them", () => {
    render(<ClassPanel state={ok({ ...CLASS, stale: true, age_s: 75 })} />);
    expect(lane("N").textContent).toContain("HIGH");
    cleanup();
    render(<CountPanel state={ok({ ...COUNT, stale: true, age_s: 75 })} />);
    expect(lane("N").textContent).toMatch(/2\.5/);
  });
  it("marks fresh data as fresh and shows no warning", () => {
    render(<CountPanel state={ok(COUNT)} />);
    expect(document.querySelector('[data-freshness="fresh"]')).toBeTruthy();
    expect(document.querySelector('[data-state="stale"]')).toBeNull();
  });
  it("refuses a class response in the count panel, and a count in the class panel", () => {
    render(<CountPanel state={ok(CLASS)} />);
    expect(document.querySelector('[data-state="invalid"]').textContent).toMatch(/wrong role/);
    cleanup();
    render(<ClassPanel state={ok(COUNT)} />);
    expect(document.querySelector('[data-state="invalid"]').textContent).toMatch(/wrong role/);
  });
  it("rejects bad values, unknown approaches, wrong model ids and inconsistent absences", () => {
    expect(validateCount({ ...COUNT, counts: { N: -1 } }).ok).toBe(false);
    expect(validateCount({ ...COUNT, counts: { N: Infinity } }).ok).toBe(false);
    expect(validateCount({ ...COUNT, model: "G@0123456789ab" }).ok).toBe(false);
    expect(validateCount({ ...COUNT, missing_approaches: [] }).ok).toBe(false);
    expect(validateClass({ ...CLASS, predictions: { N: "MED" } }).ok).toBe(false);
    expect(validateClass({ ...CLASS, predictions: { X: "LOW" } }).ok).toBe(false);
    expect(validateClass({ ...CLASS, model: "ridge@73532968dcf2" }).ok).toBe(false);
    expect(validateCount(COUNT).ok && validateClass(CLASS).ok).toBe(true);
  });
});

describe("evidence is fetched until it first succeeds, then never again", () => {
  it("retries a failed first request and stops after success", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { usePoll } = await import("./usePoll.js");
    let calls = 0;
    const flaky = async () => {
      calls += 1;
      return calls === 1 ? { ok: false, status: 503 } : { ok: true, status: 200, json: async () => ({ x: 1 }) };
    };
    const { result } = renderHook(() => usePoll("/evidence", 0, flaky, 20));
    await waitFor(() => expect(result.current.status).toBe("ok"));
    const settled = calls;
    await new Promise((r) => setTimeout(r, 80));
    expect(calls).toBe(settled);
  });
});

describe("the page", () => {
  const evidence = {
    label: "Historical evaluation evidence. Not a live performance guarantee.",
    limitations: ["labels are detector counts (A32)"],
    studies: [{
      id: "P105", role: "next_minute_count (ridge)", question: "q", file: "f.json", commit: "abc1234",
      date: "2026-10-16", scope: { cameras: ["c"], excluded_cameras: [], windows: 9, blocks: 2 },
      rows: [{ metric: "count MAE (vehicles)", lower_is_better: true, values: { ridge: 0.7, persistence: 0.9 },
               difference: 0.2, ci95: [0.1, 0.3], significant: true }],
    }],
  };
  const fetcher = async (path) => {
    const body = path.endsWith("/history")
      ? { rows: [path.startsWith("/count") ? COUNT_ROW : CLASS_ROW] }
      : path === "/health" ? { status: "ok" }
        : path.startsWith("/count_forecast") ? COUNT : path.startsWith("/prediction") ? CLASS : evidence;
    return { ok: true, status: 200, json: async () => body };
  };
  it("opens on Live, with the P97a warning and both forecasts, and no evidence", async () => {
    render(<App fetcher={fetcher} search="?id=j1" hash="" />);
    const live = screen.getByLabelText("Live monitor");
    expect(screen.queryByLabelText("Results")).toBeNull();
    const banner = live.querySelector('[data-p97a="true"]').textContent;
    expect(banner).toMatch(/P97a/);
    // D2: the encoding as it is since P110, not as it was before.
    expect(banner).toMatch(/0\.0 means an approach has no forecast/);
    expect(banner).toMatch(/LOW is encoded as 1\/3/);
    expect(banner).not.toMatch(/same value as LOW/);
    await waitFor(() => expect(within(live).getByText("ridge@73532968dcf2")).toBeTruthy());
    expect(within(live).getByText("persistence@2431c6641b9c")).toBeTruthy();
    expect(within(live).queryByText(/abc1234|macro-F1|MAE/)).toBeNull();
    await waitFor(() => expect(document.querySelector('[data-check="Server"]').dataset.kind).toBe("fresh"));
  });
  it("shows the evidence only in Results, with no live panel beside it (ADR-014)", async () => {
    render(<App fetcher={fetcher} search="?id=j1" hash="#results" />);
    const results = screen.getByLabelText("Results");
    await waitFor(() => expect(within(results).getByText(/abc1234/)).toBeTruthy());
    expect(screen.queryByLabelText("Live monitor")).toBeNull();
    expect(screen.queryByLabelText(/System status|Forecast history|Next 60 seconds/)).toBeNull();
    expect(within(results).queryByText(/ridge · point estimate/)).toBeNull();
  });
  it("keeps forecast history in its own section, never in Results", async () => {
    render(<App fetcher={fetcher} search="?id=j1" hash="#history" />);
    expect(screen.getByLabelText("Forecast history")).toBeTruthy();
    expect(screen.queryByLabelText("Results")).toBeNull();
    expect(screen.queryByLabelText("Live monitor")).toBeNull();
    await waitFor(() => expect(document.querySelector('[data-history="count"] table')).toBeTruthy());
  });
  it("never puts live and historical evidence on screen together, whatever the address says", () => {
    for (const hash of ["", "#live", "#history", "#results", "#/results", "#nope", "#results?x"]) {
      render(<App fetcher={fetcher} search="?id=j1" hash={hash} />);
      const shown = ["Live monitor", "Analytics", "Results"].filter((l) => screen.queryByLabelText(l, { selector: "section" }));
      expect(shown).toHaveLength(1);
      cleanup();
    }
  });
});

describe("sections and navigation (UX step 2)", () => {
  it("reads the section from the address, and opens Live for anything unknown", () => {
    expect(sectionFromHash("")).toBe("live");
    expect(sectionFromHash("#analytics")).toBe("analytics");
    expect(sectionFromHash("#history")).toBe("analytics");      // the old address still opens it (D21)
    expect(sectionFromHash("#/results")).toBe("results");
    for (const h of ["#nope", "#results?x", "#Live", "#evidence", undefined]) expect(sectionFromHash(h)).toBe("live");
  });
  it("marks the open section, and names every link in text, not by icon alone", () => {
    render(<App fetcher={async () => ({ ok: false, status: 404 })} search="?id=j1" hash="#history" />);
    const links = within(screen.getByRole("navigation", { name: "Sections" })).getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual(SECTIONS.map(([k]) => `#${k}`));
    expect(links.filter((a) => a.getAttribute("aria-current") === "page").map((a) => a.textContent)).toEqual(["Analytics"]);
    for (const a of links) {
      expect(a.textContent.trim().length).toBeGreaterThan(0);
      expect(a.querySelector("svg").getAttribute("aria-hidden")).toBe("true");
    }
  });
  it("follows the address when it changes", async () => {
    window.location.hash = "";
    render(<App fetcher={async () => ({ ok: false, status: 404 })} search="?id=j1" />);
    expect(screen.getByLabelText("Live monitor")).toBeTruthy();
    window.location.hash = "#results";
    await waitFor(() => expect(screen.getByLabelText("Results")).toBeTruthy());
    window.location.hash = "";
  });
  it("vendors only the icons it uses, each hidden from assistive technology", () => {
    expect([...ICONS].sort()).toEqual(["history", "live", "results", "signal"]);
  });
});

describe("the intersection (UX step 3)", () => {
  const CLASS4 = { ...CLASS, predictions: { N: "HIGH", S: "MEDIUM", E: "LOW", W: "HIGH" }, missing_approaches: [] };
  const COUNT4 = { ...COUNT, counts: { N: 0.8, S: 0.0, E: 7.3, W: 12 }, missing_approaches: [] };
  const ribbon = (a) => document.querySelector(`[data-ribbon="${a}"]`);
  const label = (a) => [...document.querySelectorAll(`[data-label="${a}"] tspan`)].map((t) => t.textContent).join(" ");

  it("scales a ribbon to the count on a fixed scale: zero is a stub, not an absence", () => {
    expect(ribbonLength(0)).toBe(8);
    expect(ribbonLength(SCALE_MAX)).toBeGreaterThan(ribbonLength(SCALE_MAX / 2));
    expect(ribbonLength(25)).toBe(ribbonLength(SCALE_MAX));
    expect(ribbonLength(-1)).toBe(8);
  });
  it("draws a ribbon only where both forecasts give the approach a value", () => {
    const j = junction(ok(CLASS), ok(COUNT));            // class N, E; count N, E (S and W missing in both)
    expect(Object.fromEntries(Object.entries(j.lanes).map(([a, l]) => [a, l.kind])))
      .toEqual({ N: "fresh", S: "none", E: "fresh", W: "none" });
    expect(j.lanes.S.note).toBe("No forecast");
    const k = junction(ok(CLASS4), ok({ ...COUNT, counts: { N: 1, S: 1, E: 1 }, missing_approaches: ["W"] }));
    expect([k.lanes.W.kind, k.lanes.W.note, k.lanes.W.cls]).toEqual(["none", "No count", "HIGH"]);
  });
  it("names the class in words beside every ribbon, never by colour alone", () => {
    render(<Intersection cls={ok(CLASS4)} count={ok(COUNT4)} />);
    for (const a of ["N", "S", "E", "W"]) {
      expect(ribbon(a).dataset.kind).toBe("fresh");
      expect(label(a)).toContain(CLASS4.predictions[a]);
    }
    expect(label("S")).toBe("S MEDIUM 0.0 veh");
    expect(label("W")).toBe("W HIGH 12.0 veh >10");                // above the scale, and said so
  });
  it("draws a missing approach as missing: no ribbon, no track, no class, no zero", () => {
    render(<Intersection cls={ok(CLASS)} count={ok(COUNT)} />);
    expect(document.querySelector('[data-track="N"]')).toBeTruthy();
    for (const a of ["S", "W"]) {
      expect(ribbon(a)).toBeNull();
      expect(document.querySelector(`[data-track="${a}"]`)).toBeNull();   // an empty track would read as an empty lane
      expect(label(a)).toBe(`${a} no forecast`);
    }
  });
  it("draws every ribbon hollow when either forecast is stale", () => {
    render(<Intersection cls={ok(CLASS4)} count={ok({ ...COUNT4, stale: true, age_s: 75 })} />);
    expect(document.querySelector("[data-junction]").dataset.junction).toBe("stale");
    for (const a of ["N", "S", "E", "W"]) expect(ribbon(a).dataset.kind).toBe("stale");
  });
  it("draws nothing when a forecast is unreachable, refused or not there yet", () => {
    for (const [cls, count, note] of [
      [{ status: "error", reason: "down" }, ok(COUNT4), "No data"],
      [ok(CLASS4), ok({ ...COUNT4, counts: { N: -1 } }), "No data"],
      [ok(COUNT4), ok(COUNT4), "No data"],
      [{ status: "loading" }, ok(COUNT4), "Waiting"],
    ]) {
      render(<Intersection cls={cls} count={count} />);
      expect(document.querySelectorAll("[data-ribbon]")).toHaveLength(0);
      expect(label("N")).toBe(`N ${note.toLowerCase()}`);
      cleanup();
    }
  });
  it("shows the signal heads as not connected, and says what is and is not drawn", () => {
    render(<Intersection cls={ok(CLASS4)} count={ok(COUNT4)} />);
    expect([...document.querySelectorAll("[data-signal]")].map((s) => s.dataset.signal)).toEqual(Array(4).fill("not connected"));
    const caption = document.querySelector("figcaption").textContent;
    expect(caption).toMatch(/longer ribbon means more vehicles expected/);
    expect(caption).toMatch(/congestion level/);
    expect(caption).toMatch(/signals, which are not connected, so their colour is not known/);
    // A signal's state is not known here, so no head may ever show a colour or a timing.
    for (const head of document.querySelectorAll("[data-signal]")) expect(head.textContent).toBe("?");
  });
  it("states the forecast's age against its horizon in words, using the older forecast", () => {
    const fresh = horizon(junction(ok({ ...CLASS4, age_s: 3 }), ok({ ...COUNT4, age_s: 5 })));
    expect([fresh.kind, fresh.age, fresh.text]).toEqual(["fresh", 5, "Fresh, valid 55 s more"]);
    const stale = horizon(junction(ok({ ...CLASS4, stale: true, age_s: 75 }), ok(COUNT4)));
    expect([stale.kind, stale.text]).toEqual(["stale", "Stale, 15 s past its 60 s horizon"]);
    expect(horizon(junction({ status: "error", reason: "x" }, ok(COUNT4)))).toEqual({ kind: "unknown", text: "", age: null });
    render(<Horizon cls={ok({ ...CLASS4, stale: true, age_s: 75 })} count={ok(COUNT4)} />);
    expect(document.querySelector("[data-horizon]").dataset.horizon).toBe("stale");
    cleanup();
    render(<Horizon cls={{ status: "error", reason: "down" }} count={ok(COUNT4)} />);
    expect(document.querySelector("[data-horizon]").textContent).toMatch(/^Forecast age unknown/);
    expect(document.querySelector("[data-horizon]").textContent).not.toMatch(/of 60 s/);
  });
});

// Reviewer rule 2: the overview is built from valid, current data only.
describe("the overview", () => {
  const CLASS4 = { ...CLASS, predictions: { N: "HIGH", S: "HIGH", E: "MEDIUM", W: "LOW" }, missing_approaches: [] };
  const CLASS_WORDS = /\b(LOW|MEDIUM|HIGH)\b/;
  it("answers with the worst current class across the available approaches", () => {
    expect(overview(ok(CLASS4)).headline).toBe("Highest congestion expected: Approach N and Approach S HIGH");
    expect(overview(ok(CLASS4)).detail).toBe("");
    const allLow = { ...CLASS4, predictions: { N: "LOW", S: "LOW", E: "LOW", W: "LOW" } };
    expect(overview(ok(allLow)).headline).toBe("Highest congestion expected: all 4 approaches LOW");
  });
  it("counts only the approaches that have a forecast, and names the ones that do not", () => {
    const o = overview(ok(CLASS));                        // N HIGH, E LOW; S and W missing
    expect(o.headline).toBe("Highest congestion expected: Approach N HIGH");
    expect(o.detail).toMatch(/Approach S and Approach W have no forecast\. This does not mean they are empty\./);
    const two = overview(ok({ ...CLASS, predictions: { N: "HIGH", S: "HIGH" }, missing_approaches: ["E", "W"] }));
    expect(two.headline).toBe("Highest congestion expected: all 2 available approaches HIGH");
    expect(two.detail).toMatch(/Approach E and Approach W have no forecast/);
    const one = overview(ok({ ...CLASS, predictions: { E: "MEDIUM" }, missing_approaches: ["N", "S", "W"] }));
    expect(one.headline).toBe("Highest congestion expected: Approach E MEDIUM");
    expect(one.detail).toMatch(/Approach N, Approach S and Approach W have no forecast/);
  });
  it("never answers with a class from a stale forecast", () => {
    const o = overview(ok({ ...CLASS4, stale: true, age_s: 78 }));
    expect(o.kind).toBe("stale");
    expect(o.headline).toBe("No current forecast");
    expect(o.headline).not.toMatch(CLASS_WORDS);
    expect(o.detail).toMatch(/78 s old and describes a minute that has passed/);
  });
  it("never answers with a class when nothing valid and current arrived", () => {
    const cases = [
      [{ status: "loading" }, "loading", "Waiting for the first forecast"],
      [{ status: "unavailable" }, "none", "No forecast published yet"],
      [{ status: "error", reason: "server unreachable (Failed to fetch)" }, "bad", "Forecasts unavailable"],
      [ok({ ...CLASS, predictions: { N: "MED" } }), "bad", "Forecast refused"],
      [ok(COUNT), "bad", "Forecast refused"],
      [ok({ ...CLASS, predictions: {}, missing_approaches: ["N", "S", "E", "W"] }), "bad", "Forecast refused"],
    ];
    for (const [state, kind, headline] of cases) {
      const o = overview(state);
      expect([o.kind, o.headline]).toEqual([kind, headline]);
      expect(o.headline).not.toMatch(CLASS_WORDS);
      render(<Overview state={state} />);
      expect(document.querySelector("[data-overview]").dataset.overview).toBe(kind);
      expect(document.querySelector("[data-overview] [aria-live]").textContent).not.toMatch(CLASS_WORDS);
      cleanup();
    }
  });
  it("shows the class word as a labelled chip only when the answer is current", () => {
    render(<Overview state={ok(CLASS4)} />);
    expect(document.querySelector("[data-overview='fresh'] [aria-live]").textContent)
      .toBe("Highest congestion expected: Approach N and Approach S HIGH");
  });
});

describe("forecast history (S42)", () => {
  const cell = (kind, a) => document.querySelector(`[data-history="${kind}"] [data-cell="${a}"]`);
  it("validates every row by its panel's rules, and shows all or nothing", () => {
    expect(validateHistory({ rows: [CLASS_ROW] }, "class").ok).toBe(true);
    expect(validateHistory({ rows: [COUNT_ROW] }, "count").ok).toBe(true);
    expect(validateHistory({ rows: [] }, "count").ok).toBe(true);
    expect(validateHistory({ rows: [COUNT_ROW] }, "class").reason).toMatch(/row 1: wrong role/);
    expect(validateHistory({ rows: [CLASS_ROW, { ...CLASS_ROW, predictions: { N: "MED" } }] }, "class").reason)
      .toMatch(/row 2/);
    expect(validateHistory({ rows: [{ ...COUNT_ROW, missing_approaches: [] }] }, "count").ok).toBe(false);
    expect(validateHistory({ rows: [{ ...COUNT_ROW, at: undefined }] }, "count").ok).toBe(false);
    expect(validateHistory({ rows: "x" }, "count").ok).toBe(false);
  });
  it("keeps a real zero, and never shows an absent approach as 0 or LOW", () => {
    render(<HistoryPanel classHistory={ok({ rows: [CLASS_ROW] })} countHistory={ok({ rows: [COUNT_ROW] })} />);
    expect(cell("count", "E").textContent).toBe("0.0");
    expect(cell("class", "E").textContent).toBe("LOW");
    for (const a of ["S", "W"]) {
      for (const kind of ["count", "class"]) {
        expect(cell(kind, a).querySelector('[data-missing="true"]')).toBeTruthy();
        expect(cell(kind, a).textContent).not.toMatch(/\d|LOW|MEDIUM|HIGH/);
      }
    }
  });
  it("names the model that produced each row, and never calls it MFSTNet", () => {
    render(<HistoryPanel classHistory={ok({ rows: [CLASS_ROW] })} countHistory={ok({ rows: [COUNT_ROW] })} />);
    const panel = screen.getByLabelText("Forecast history");
    expect(within(panel).getByText("persistence")).toBeTruthy();
    expect(within(panel).getByText("ridge")).toBeTruthy();
    expect(panel.textContent).not.toMatch(/MFSTNet/);
  });
  it("says when nothing is recorded, and refuses an invalid history whole", () => {
    render(<HistoryPanel classHistory={ok({ rows: [] })}
                         countHistory={ok({ rows: [COUNT_ROW, { ...COUNT_ROW, counts: { N: -1 } }] })} />);
    expect(document.querySelector('[data-history="class"] [data-state="empty"]')).toBeTruthy();
    expect(document.querySelector('[data-history="count"] [data-state="invalid"]')).toBeTruthy();
    expect(document.querySelector('[data-history="count"] table')).toBeNull();
  });
});

describe("system status (S42)", () => {
  const kind = (name) => document.querySelector(`[data-check="${name}"]`).dataset.kind;
  it("reports the server and each stream by what the server actually returns", () => {
    render(<StatusPanel health={{ ...ok({ status: "ok" }), rtt_ms: 12 }}
                        cls={ok(CLASS)} count={ok({ ...COUNT, stale: true, age_s: 75 })} />);
    expect(kind("Server")).toBe("fresh");
    expect(kind("Class forecast stream")).toBe("fresh");
    expect(kind("Count forecast stream")).toBe("stale");
    expect(document.querySelector("[data-rtt]").textContent).toMatch(/12 ms, measured by this browser/);
    expect(document.querySelector("[data-rtt]").textContent).not.toMatch(/over the 2 s/);
  });
  it("shows an unreachable server, a missing stream and an invalid one as such", () => {
    render(<StatusPanel health={{ status: "error", reason: "server unreachable (down)", rtt_ms: 3 }}
                        cls={{ status: "unavailable" }} count={ok(CLASS)} />);
    expect(kind("Server")).toBe("bad");
    expect(kind("Class forecast stream")).toBe("none");
    expect(kind("Count forecast stream")).toBe("bad");
    expect(screen.getByText(/invalid response: wrong role/)).toBeTruthy();
  });
  // Seen on the real stack: with the server down the page still read "round trip 10 ms",
  // which was how long the failed request took, not a round trip.
  it("reports no round trip when the health check failed", () => {
    render(<StatusPanel health={{ status: "error", reason: "server unreachable (Failed to fetch)", rtt_ms: 10 }}
                        cls={ok(CLASS)} count={ok(COUNT)} />);
    expect(document.querySelector("[data-rtt]")).toBeNull();
  });
  it("flags a round trip over the 2 s refresh budget", () => {
    render(<StatusPanel health={{ ...ok({ status: "ok" }), rtt_ms: 2500 }} cls={ok(CLASS)} count={ok(COUNT)} />);
    expect(document.querySelector("[data-rtt]").textContent).toMatch(/over the 2 s refresh budget/);
  });
  it("times the health round trip with the clock it is given", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useHealth } = await import("./usePoll.js");
    let t = 0;
    const clock = () => (t += 40);
    const fetcher = async () => ({ ok: true, status: 200, json: async () => ({ status: "ok" }) });
    const { result } = renderHook(() => useHealth(60000, fetcher, clock));
    await waitFor(() => expect(result.current.status).toBe("ok"));
    expect(result.current.rtt_ms).toBe(40);
  });
});

// D21: FR-UI03, observed counts per lane over 1, 6 or 24 hours.
describe("observed counts (FR-UI03)", () => {
  const view = (window = "1h", buckets) => ({
    intersection_id: "j1", window, bucket_s: { "1h": 60, "6h": 300, "24h": 900 }[window], start: 0, end: 180,
    buckets: buckets ?? [
      { t: 0, lanes: { lane_0: { mean: 2, n: 30 }, lane_1: { mean: 0, n: 30 } } },
      { t: 60, lanes: {} },                                     // a gap
      { t: 120, lanes: { lane_0: { mean: 4, n: 12 } } },        // lane_1 absent: not zero
    ],
    note: "observed",
  });
  const bars = (lane) => [...document.querySelectorAll(`[data-lane="${lane}"] [data-bucket]`)];

  it("accepts a whole view and refuses a bad one whole", () => {
    expect(validateCountHistory(view(), "1h").data.lanes).toEqual(["lane_0", "lane_1"]);
    expect(validateCountHistory(view("6h"), "1h").ok).toBe(false);                         // not the window asked for
    expect(validateCountHistory({ ...view(), bucket_s: 30 }, "1h").ok).toBe(false);
    for (const bad of [{ lane_0: { mean: -1, n: 1 } }, { lane_0: { mean: 1, n: 0 } }, { lane_0: { mean: 999, n: 1 } },
                       { "lane 0": { mean: 1, n: 1 } }, { lane_0: { mean: "1", n: 1 } }]) {
      expect(validateCountHistory(view("1h", [{ t: 0, lanes: bad }]), "1h").ok).toBe(false);
    }
    expect(validateCountHistory(view("1h", [{ t: "0", lanes: {} }]), "1h").ok).toBe(false);
  });
  it("draws a bar only where a lane had samples: a gap is no bar, and a real zero is a bar", () => {
    render(<ObservedCounts state={ok(view())} window="1h" onWindow={() => {}} />);
    expect(bars("lane_0").map((b) => b.dataset.bucket)).toEqual(["0", "120"]);
    expect(bars("lane_1").map((b) => b.dataset.bucket)).toEqual(["0"]);
    expect(document.querySelector('[data-lane="lane_1"] [data-bucket="0"] title').textContent).toMatch(/mean 0\.00 vehicles from 30 samples/);
  });
  it("puts every lane on one scale from zero", () => {
    expect(scaleTop(view().buckets)).toBe(4);
    expect(scaleTop([{ t: 0, lanes: {} }])).toBe(1);
    render(<ObservedCounts state={ok(view())} window="1h" onWindow={() => {}} />);
    const h = (lane, t) => Number(document.querySelector(`[data-lane="${lane}"] [data-bucket="${t}"]`).getAttribute("height"));
    expect(h("lane_0", 120) / h("lane_0", 0)).toBeCloseTo(2, 5);
    cleanup();
    // A quieter lane is not stretched to fill its own chart: 2 vehicles are as tall in either lane.
    const quiet = view("1h", [{ t: 0, lanes: { lane_0: { mean: 4, n: 3 }, lane_1: { mean: 2, n: 3 } } },
                              { t: 60, lanes: { lane_0: { mean: 2, n: 3 } } }]);
    render(<ObservedCounts state={ok(quiet)} window="1h" onWindow={() => {}} />);
    expect(h("lane_1", 0)).toBeCloseTo(h("lane_0", 60), 5);
  });
  it("keeps axis labels out of the stretched drawing, so they stay readable at phone width", () => {
    render(<ObservedCounts state={ok(view())} window="1h" onWindow={() => {}} />);
    const lane = document.querySelector('[data-lane="lane_0"]');
    expect(lane.querySelector("svg text")).toBeNull();
    expect(lane.querySelector('[data-axis="y"]').textContent).toBe("40");
    expect(lane.querySelector('[data-axis="x"]').textContent).toBe("−1 h−30 minnow");
  });
  it("says it is a measurement, not a forecast, and that an empty slot is a gap", () => {
    render(<ObservedCounts state={ok(view())} window="1h" onWindow={() => {}} />);
    const note = screen.getByLabelText("Observed vehicle counts").textContent;
    expect(note).toMatch(/Measured, not forecast/);
    expect(note).toMatch(/it is a gap, not zero/);
    expect(note).not.toMatch(/\b(LOW|MEDIUM|HIGH)\b/);
  });
  it("shows nothing counted, unreachable and invalid as such, and draws no bars", () => {
    for (const [state, kind] of [[ok(view("1h", [{ t: 0, lanes: {} }])), "empty"],
                                 [{ status: "error", reason: "server unreachable (down)" }, "error"],
                                 [ok({ ...view(), window: "6h" }), "invalid"], [{ status: "loading" }, "loading"]]) {
      render(<ObservedCounts state={state} window="1h" onWindow={() => {}} />);
      expect(document.querySelector(`[data-state="${kind}"]`)).toBeTruthy();
      expect(document.querySelectorAll("[data-bucket]")).toHaveLength(0);
      cleanup();
    }
  });
  it("offers exactly the three windows and asks for the one chosen", async () => {
    const asked = [];
    const fetcher = async (path) => {
      asked.push(path);
      return path.startsWith("/vehicle_count") ? { ok: true, status: 200, json: async () => view(path.endsWith("6h") ? "6h" : "1h") }
        : { ok: false, status: 404 };
    };
    render(<App fetcher={fetcher} search="?id=j1" hash="#analytics" />);
    const group = screen.getByRole("group", { name: "Window" });
    expect(within(group).getAllByRole("button").map((b) => [b.textContent, b.getAttribute("aria-pressed")]))
      .toEqual([["1 h", "true"], ["6 h", "false"], ["24 h", "false"]]);
    within(group).getByText("6 h").click();
    await waitFor(() => expect(asked).toContain("/vehicle_count/j1/history?window=6h"));
    await waitFor(() => expect(document.querySelector("[data-observed]").dataset.observed).toBe("6h"));
    expect(screen.getByLabelText("Forecast history")).toBeTruthy();      // the forecast log stays below
    expect(screen.queryByLabelText("Results")).toBeNull();
  });
});

// D22: what the edge counts from, and which approach each lane feeds.
describe("source badge and lane map (D22)", () => {
  const LANES = { lane_0: "W", lane_1: "N", lane_2: "E" };
  const REPLAY = { kind: "replay", session: "a1b2c3d4e5f6", label: "Bellevue_NE8th", position_s: 83, duration_s: 180 };
  const CAMERA = { kind: "camera", session: "0123456789ab", label: "NE8th", position_s: null, duration_s: null };
  const beat = (over = {}) => ({ at: 1000, age_s: 1.2, stale: false, edge_status: "online", mode: "M-NORMAL",
    source: REPLAY, lanes: LANES, note: "n", ...over });
  const badge = (state) => {
    render(<SourceBadge state={state} />);
    const el = document.querySelector("[data-source]");
    return [el.dataset.source, el.textContent];
  };

  it("says REPLAY and where in the clip, never live, for recorded footage", () => {
    const [kind, text] = badge(ok(beat()));
    expect(kind).toBe("replay");
    expect(text).toMatch(/Replay/);
    expect(text).toContain("Bellevue_NE8th · 01:23 / 03:00");
    expect(text).not.toMatch(/live/i);
    cleanup();
    expect(badge(ok(beat({ source: { ...REPLAY, duration_s: null } })))[1]).toContain("01:23 / length unknown");
  });
  it("says LIVE CAMERA only for a fresh, valid camera heartbeat", () => {
    expect(badge(ok(beat({ source: CAMERA })))).toEqual(["camera", "Live cameraNE8th"]);
  });
  it("never falls back to live: no heartbeat, no source, stale, invalid and unreachable all say so", () => {
    for (const [state, kind] of [
      [{ status: "loading" }, "unknown"], [{ status: "unavailable" }, "unknown"],
      [{ status: "error", reason: "down" }, "unknown"], [ok(beat({ source: null })), "unknown"],
      [ok(beat({ source: CAMERA, stale: true, age_s: 23 })), "stale"],
      [ok(beat({ source: { ...CAMERA, kind: "live" } })), "bad"],
      [ok(beat({ source: { ...REPLAY, position_s: 200 } })), "bad"],
      [ok(beat({ lanes: { lane_0: "N", lane_1: "N" } })), "bad"],
    ]) {
      const [got, text] = badge(state);
      expect(got).toBe(kind);
      expect(text).not.toMatch(/live camera|replay ·/i);
      cleanup();
    }
  });
  it("states, while a replay is current, that page times are receipt times", () => {
    render(<ReplayNote state={ok(beat())} />);
    expect(document.querySelector("[data-replay-note]").textContent).toMatch(/not when the footage was recorded.*01:23/);
    cleanup();
    for (const state of [ok(beat({ source: CAMERA })), ok(beat({ stale: true })), { status: "unavailable" }]) {
      render(<ReplayNote state={state} />);
      expect(document.querySelector("[data-replay-note]")).toBeNull();
      cleanup();
    }
  });
  it("validates the heartbeat whole, as the contract does", () => {
    expect(validateHeartbeat(beat()).ok).toBe(true);
    expect(validateHeartbeat(beat({ source: null, lanes: null })).ok).toBe(true);
    for (const bad of [{ source: { ...REPLAY, extra: 1 } }, { source: { ...REPLAY, session: "XYZ" } },
                       { source: { ...REPLAY, label: "has space" } }, { source: { ...CAMERA, position_s: 3 } },
                       { lanes: {} }, { lanes: { "lane 0": "N" } }, { lanes: { lane_0: "X" } }, { stale: "no" }]) {
      expect(validateHeartbeat(beat(bad)).ok).toBe(false);
    }
  });
  it("names each lane's approach in Analytics, and says the map is the current one", () => {
    const view = { intersection_id: "j1", window: "1h", bucket_s: 60, start: 0, end: 120, note: "o",
      buckets: [{ t: 0, lanes: { lane_0: { mean: 1, n: 2 }, lane_3: { mean: 2, n: 2 } } }, { t: 60, lanes: {} }] };
    render(<ObservedCounts state={ok(view)} window="1h" onWindow={() => {}} lanes={LANES} />);
    expect(document.querySelector('[data-lane="lane_0"] [data-lane-approach]').dataset.laneApproach).toBe("W");
    expect(document.querySelector('[data-lane="lane_3"] [data-lane-approach]')).toBeNull();   // unmapped stays unmapped
    expect(screen.getByLabelText("Observed vehicle counts").textContent).toMatch(/current lane map.*earlier run/);
    cleanup();
    render(<ObservedCounts state={ok(view)} window="1h" onWindow={() => {}} />);
    expect(document.querySelector("[data-lane-approach]")).toBeNull();
    expect(screen.getByLabelText("Observed vehicle counts").textContent).toMatch(/has not reported which approach/);
  });
  it("polls only the read-only heartbeat path and shows the edge in System status", async () => {
    expect(isAllowed("/heartbeat/j1/latest")).toBe(true);
    for (const p of ["/heartbeat/j1", "/heartbeat/j1/latest?x=1", "/heartbeat/j1/history"]) expect(isAllowed(p)).toBe(false);
    const fetcher = async (path) => path === "/heartbeat/j1/latest"
      ? { ok: true, status: 200, json: async () => beat() } : { ok: false, status: 404 };
    render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
    await waitFor(() => expect(document.querySelector("[data-source]").dataset.source).toBe("replay"));
    await waitFor(() => expect(document.querySelector('[data-check="Edge heartbeat"]').dataset.kind).toBe("fresh"));
    expect(document.querySelector("[data-replay-note]")).toBeTruthy();
  });
});

// D23: a stopped edge's last forecast is still valid, and is labelled as the last one.
describe("edge silent, forecast still valid (D23)", () => {
  const silent = () => document.querySelector("[data-edge-silent]");

  it("says the forecast is the edge's last one while it is still inside its horizon", () => {
    render(<Overview state={ok(CLASS)} edgeSilentFor={32.4} />);
    expect(silent().textContent).toMatch(/Last forecast received/);
    expect(document.querySelector("[data-overview]").dataset.overview).toBe("fresh");   // still shown, still valid
  });
  it("says nothing when the edge is reporting, or when there is no forecast to qualify", () => {
    for (const [state, age] of [[ok(CLASS), null], [ok({ ...CLASS, stale: true, age_s: 70 }), 70],
                                [{ status: "unavailable" }, 15], [{ status: "error", reason: "x" }, 15]]) {
      render(<Overview state={state} edgeSilentFor={age} />);
      expect(silent()).toBeNull();
      cleanup();
    }
  });
  it("takes silence only from a valid heartbeat gone stale, never from a missing one", async () => {
    const beat = { at: 1, age_s: 32, stale: true, edge_status: "online", mode: "M-NORMAL",
                   source: null, lanes: null, note: "n" };
    for (const [answer, row, expected] of [[{ ok: true, status: 200, json: async () => beat }, "stale", true],
                                           [{ ok: false, status: 404 }, "none", false],
                                           [{ ok: true, status: 200, json: async () => ({ ...beat, stale: false }) }, "fresh", false]]) {
      const fetcher = async (path) => path === "/heartbeat/j1/latest" ? answer
        : path === "/prediction/j1/latest" ? { ok: true, status: 200, json: async () => CLASS }
          : { ok: false, status: 404 };
      render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
      await waitFor(() => expect(document.querySelector("[data-overview]").dataset.overview).toBe("fresh"));
      // Wait until the heartbeat has been read, so a "no notice" is a decision, not a race.
      await waitFor(() => expect(document.querySelector('[data-check="Edge heartbeat"]').dataset.kind).toBe(row));
      expect(!!silent()).toBe(expected);
      cleanup();
    }
  });
});

// Step 3b: a count above the scale is marked, and every ribbon points into the junction.
describe("overflow and direction (step 3b)", () => {
  const CLASS4 = { ...CLASS, predictions: { N: "HIGH", S: "MEDIUM", E: "LOW", W: "HIGH" }, missing_approaches: [] };
  const draw = (counts, extra = {}) => render(<Intersection cls={ok(CLASS4)}
    count={ok({ ...COUNT, counts, missing_approaches: [], ...extra })} />);
  const cuts = (a) => document.querySelectorAll(`[data-overflow="${a}"]`).length;
  const label = (a) => [...document.querySelectorAll(`[data-label="${a}"] tspan`)].map((t) => t.textContent).join(" ");

  it("marks only a count above the scale, and writes the exact count", () => {
    draw({ N: 0, S: 9, E: 10, W: 11 });
    expect(["N", "S", "E", "W"].map(cuts)).toEqual([0, 0, 0, 2]);
    expect(label("E")).toBe("E LOW 10.0 veh");                       // at the scale is not above it
    expect(label("W")).toBe("W HIGH 11.0 veh >10");
    cleanup();
    draw({ N: 150, S: 9, E: 10, W: 11 });
    expect(label("N")).toBe("N HIGH 150.0 veh >10");                 // far above: same length, exact number
    expect(cuts("N")).toBe(2);
  });
  it("keeps the mark on a stale reading and draws none for a missing approach", () => {
    draw({ N: 12, S: 1, E: 1, W: 1 }, { stale: true, age_s: 75 });
    expect(document.querySelector('[data-ribbon="N"]').dataset.kind).toBe("stale");
    expect(cuts("N")).toBe(2);
    cleanup();
    render(<Intersection cls={ok(CLASS4)} count={ok({ ...COUNT, counts: { N: 12 }, missing_approaches: ["S", "E", "W"] })} />);
    expect(["S", "E", "W"].map(cuts)).toEqual([0, 0, 0]);
  });
  it("points every ribbon's tip at its own stop line, on its own inbound half", () => {
    const C = 160;
    const turn = ([x, y], deg) => {
      const r = (deg * Math.PI) / 180, dx = x - C, dy = y - C;
      return [C + dx * Math.cos(r) - dy * Math.sin(r), C + dx * Math.sin(r) + dy * Math.cos(r)];
    };
    const points = (d) => [...d.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
    const d = ribbonPath(ribbonLength(5));
    const tip = points(d).at(-2), tail = points(d)[0];
    expect(tip).toEqual([C - 17, C - 48]);               // on the stop line, in the middle of the lane
    expect(points(d).at(-1)[1]).toBeLessThan(tip[1]);    // a point, not a flat end: the neck stands back
    const side = { N: ([x, y]) => x < C && y < C, E: ([x, y]) => x > C && y < C,
                   S: ([x, y]) => x > C && y > C, W: ([x, y]) => x < C && y > C };
    for (const [a, deg] of Object.entries(TURN)) {
      const [t, b] = [turn(tip, deg), turn(tail, deg)];
      expect(side[a](t)).toBe(true);
      expect(Math.hypot(t[0] - C, t[1] - C)).toBeLessThan(Math.hypot(b[0] - C, b[1] - C));   // tip nearer the box
    }
    render(<Intersection cls={ok(CLASS4)} count={ok({ ...COUNT, counts: { N: 1, S: 1, E: 1, W: 1 }, missing_approaches: [] })} />);
    for (const [a, deg] of Object.entries(TURN))
      expect(document.querySelector(`[data-ribbon="${a}"]`).parentElement.getAttribute("transform")).toBe(`rotate(${deg} ${C} ${C})`);
  });
  it("says in the caption what the cuts and the direction mean", () => {
    draw({ N: 1, S: 1, E: 1, W: 1 });
    const caption = document.querySelector("figcaption").textContent;
    expect(caption).toMatch(/Two cuts\s+near its outer end mean more than 10/);
    expect(caption).toMatch(/points into the junction/);
  });
});

// D31, ADR-028: the letters are labels until direction evidence matches the camera.
describe("direction notice (ADR-028)", () => {
  const beat = (over) => ({ at: 1, age_s: 1, stale: false, edge_status: "online", mode: "M-NORMAL", source: null, lanes: null, note: "n", ...over });
  const notice = () => document.querySelector('[data-directions="unverified"]');
  const appWith = (answer, hash = "#live") => render(<App hash={hash} search="?id=j1" fetcher={async (path) =>
    path === "/heartbeat/j1/latest" && answer ? { ok: true, status: 200, json: async () => answer } : { ok: false, status: 404 }} />);
  const beatRead = (kind) => waitFor(() => expect(document.querySelector('[data-check="Edge heartbeat"]').dataset.kind).toBe(kind));

  it("shows when the edge says false, when it says nothing, and with no heartbeat at all", async () => {
    for (const [answer, kind] of [[beat({ directions_verified: false }), "fresh"], [beat({}), "fresh"], [null, "none"]]) {
      appWith(answer);
      await beatRead(kind);
      expect(notice().textContent).toBe("N, S, E and W are labels. Their directions have not been verified for this camera.");
      cleanup();
    }
  });
  it("goes only when the edge says true", async () => {
    appWith(beat({ directions_verified: true }));
    await beatRead("fresh");
    expect(notice()).toBeNull();
  });
  it("shows on Analytics, where lanes are named by those letters, and not on Results", async () => {
    appWith(beat({}), "#analytics");
    await waitFor(() => expect(notice()).toBeTruthy());
    cleanup();
    appWith(beat({}), "#results");
    expect(notice()).toBeNull();
  });
  it("refuses a heartbeat whose flag is not true or false", () => {
    expect(validateHeartbeat(beat({ directions_verified: "yes" })).ok).toBe(false);
    expect(validateHeartbeat(beat({ directions_verified: true })).ok).toBe(true);
    expect(validateHeartbeat(beat({})).ok).toBe(true);
  });
});

// D26: the ADR-014 agreement ribbon. Facts from the edge, k of n here, never a percentage.
describe("forecast check (D26, ADR-014)", () => {
  const SLOT = (made, cls, cnt) => ({ kind: "check", made_ts: made, checked_ts: made + 60, classes: cls, counts: cnt });
  const SLOTS = [
    SLOT(0, { N: { forecast: "HIGH", observed: "HIGH" }, S: { forecast: "LOW", observed: "LOW" } },
         { N: { forecast: 6.0, observed: 5.3 } }),
    { kind: "gap" },
    SLOT(120, { N: { forecast: "HIGH", observed: "MEDIUM" }, S: { forecast: "LOW", observed: "LOW" } },
         { N: { forecast: 4.0, observed: 3.3 }, S: { forecast: 0.5, observed: 0.5 } }),
  ];
  const view = (over = {}) => ({ intersection_id: "j1", session: "a1b2c3d4e5f6", age_s: 1.0, stale: false,
    spacing_s: 60, slots: SLOTS, summary: agreement(SLOTS), class_model: "persistence@2431c6641b9c",
    count_model: "ridge@73532968dcf2", label: "x", limits: "y", ...over });
  const panelText = () => screen.getByLabelText("Level over the last 20 minutes").textContent;
  const cells = (a) => [...document.querySelectorAll(`[data-check-row="${a}"] [data-cell]`)].map((c) => c.dataset.cell);

  it("counts k of n and the mean difference, with separate denominators, from the slots", () => {
    expect(agreement(SLOTS)).toEqual({
      N: { class: { agreed: 1, n: 2 }, count: { mean_abs_diff: 0.7, n: 2 } },
      S: { class: { agreed: 2, n: 2 }, count: { mean_abs_diff: 0, n: 1 } },
    });
  });
  it("accepts a whole response and refuses a bad one whole, including a summary that disagrees", () => {
    expect(validateChecks(view()).ok).toBe(true);
    for (const bad of [{ session: "XYZ" }, { spacing_s: 2 }, { slots: Array(21).fill({ kind: "gap" }), summary: {} },
                       { slots: [SLOT(10, { N: { forecast: "LOUD", observed: "LOW" } }, {})] },
                       { slots: [SLOT(10, {}, { N: { forecast: -1, observed: 1 } })] },
                       { slots: [{ kind: "check", made_ts: 70, checked_ts: 10, classes: {}, counts: {} }] },
                       { slots: [{ kind: "gap", extra: 1 }] },
                       { summary: { ...agreement(SLOTS), N: { class: { agreed: 2, n: 2 }, count: { mean_abs_diff: 0.7, n: 2 } } } },
                       { stale: "no" }]) {
      expect(validateChecks(view(bad)).ok).toBe(false);
    }
    // Python and JavaScript may round a halfway mean differently; that is not a disagreement.
    expect(validateChecks(view({ summary: { ...agreement(SLOTS), N: { class: { agreed: 1, n: 2 }, count: { mean_abs_diff: 0.71, n: 2 } } } })).ok).toBe(true);
  });
  it("draws agreement as shape, a broken minute as a gap, and an absent approach as not checkable", () => {
    render(<Agreement state={ok(view())} />);
    expect(cells("N")).toEqual(["agreed", "gap", "differed"]);
    expect(cells("S")).toEqual(["agreed", "gap", "agreed"]);
    expect(document.querySelector('[data-summary="N"]').textContent)
      .toBe("level matched 1 of 2 · vehicle number off by 0.70 on average over 2");
    expect(document.querySelector('[data-summary="S"]').textContent)
      .toBe("level matched 2 of 2 · vehicle number off by 0.00 on average over 1");
    expect(panelText()).not.toMatch(/%|accuracy of|accurate/i);
  });
  it("carries the ADR-014 label and says what it is not", () => {
    render(<Agreement state={ok(view())} />);
    expect(AGREEMENT_LABEL).toMatch(/^Rolling agreement with auto-labels over the last 20 checked minutes\. Not a benchmark/);
    expect(panelText()).toContain("the same detector counts the forecasts are made from");
    expect(panelText()).toMatch(/not MFSTNet/);
    expect(panelText()).toMatch(/No forecast drives a signal/);
  });
  it("says warming up only while the edge reports, and not reported otherwise", () => {
    for (const [state, live, kind] of [[{ status: "unavailable" }, true, "warming"], [{ status: "unavailable" }, false, "unreported"],
                                       [{ status: "loading" }, true, "loading"], [{ status: "error", reason: "down" }, true, "error"],
                                       [ok(view({ spacing_s: 2 })), true, "invalid"]]) {
      render(<Agreement state={state} edgeLive={live} />);
      expect(document.querySelector(`[data-state="${kind}"]`)).toBeTruthy();
      expect(document.querySelectorAll("[data-cell]")).toHaveLength(0);
      cleanup();
    }
  });
  it("explains a run whose first check falls mid-minute, and stops once a cell exists", () => {
    const run = "a1b2c3d4e5f6";
    const { rerender } = render(<Agreement state={ok(view({ slots: [], summary: {} }))} edgeLive runSession={run} />);
    expect(document.querySelector('[data-state="first-minute"]').textContent).toMatch(/next minute begins/);
    expect(document.querySelectorAll("[data-cell]")).toHaveLength(0);
    rerender(<Agreement state={ok(view())} edgeLive runSession={run} />);
    expect(document.querySelector('[data-state="first-minute"]')).toBeNull();
    expect(document.querySelectorAll("[data-cell]").length).toBeGreaterThan(0);
  });
  it("never says the first check is on its way when the checks are stale or another run's", () => {
    for (const over of [{ stale: true, age_s: 30 }, { session: "0123456789ab" }]) {
      render(<Agreement state={ok(view({ slots: [], summary: {}, ...over }))} edgeLive runSession="a1b2c3d4e5f6" />);
      expect(document.querySelector('[data-state="first-minute"]')).toBeNull();
      cleanup();
    }
  });
  it("refuses a missing or null summary as invalid, without failing, even with no slots", () => {
    for (const summary of [undefined, null]) {
      render(<Agreement state={ok(view({ slots: [], summary }))} edgeLive />);
      expect(document.querySelector('[data-state="invalid"]')).toBeTruthy();
      cleanup();
    }
  });
  it("calls checks the previous run's only when both sessions are known and differ", () => {
    const notice = () => document.querySelector("[data-previous-run]");
    const run = "0123456789ab";                          // the checks' own session is a1b2c3d4e5f6
    const { rerender } = render(<Agreement state={ok(view({ stale: true, age_s: 42 }))} edgeLive runSession={run} />);
    expect(notice().textContent).toMatch(/No new check for 42 s\. These are the last checks received, from the previous run\./);
    expect(cells("N")).toHaveLength(3);                  // shown, never discarded
    // The first check of the new run arrives: the notice goes.
    rerender(<Agreement state={ok(view({ session: run }))} edgeLive runSession={run} />);
    expect(notice()).toBeNull();
    // Not yet stale, but another run's: said at once.
    rerender(<Agreement state={ok(view())} edgeLive runSession={run} />);
    expect(notice().dataset.state).toBe("previous-run");
    // No heartbeat session: stale is still said, whose they are is not claimed.
    rerender(<Agreement state={ok(view({ stale: true, age_s: 42 }))} runSession={null} />);
    expect(notice().textContent).toMatch(/last checks received\.$/);
    // The same session, stale: not the previous run.
    rerender(<Agreement state={ok(view({ stale: true, age_s: 42 }))} runSession="a1b2c3d4e5f6" />);
    expect(notice().textContent).not.toMatch(/previous run/);
  });
  it("takes the run's session from the heartbeat, and none from a heartbeat without a source", async () => {
    const source = { kind: "replay", session: "0123456789ab", label: "clip", position_s: 4, duration_s: 100 };
    for (const [src, expected] of [[source, "true"], [null, "false"]]) {
      const beat = { at: 1, age_s: 1, stale: false, edge_status: "online", mode: "M-NORMAL", source: src, lanes: null, note: "n" };
      const fetcher = async (path) => path === "/heartbeat/j1/latest" ? { ok: true, status: 200, json: async () => beat }
        : path === "/forecast_check/j1/recent" ? { ok: true, status: 200, json: async () => view({ stale: true, age_s: 30 }) }
          : { ok: false, status: 404 };
      render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
      await waitFor(() => expect(document.querySelector('[data-check="Edge heartbeat"]').dataset.kind).toBe("fresh"));
      await waitFor(() => expect(document.querySelector("[data-previous-run]")?.dataset.previousRun).toBe(expected));
      cleanup();
    }
  });
  it("keeps stale checks readable under a warning, never dimmed or dropped", () => {
    render(<Agreement state={ok(view({ stale: true, age_s: 42 }))} />);
    expect(document.querySelector('[data-state="stale"]').textContent).toMatch(/No new check for 42 s/);
    expect(cells("N")).toHaveLength(3);
  });
  it("is read through one allowed path and shows warming up when the edge is live", async () => {
    expect(isAllowed("/forecast_check/j1/recent")).toBe(true);
    for (const p of ["/forecast_check/j1", "/forecast_check/j1/recent?all=1", "/forecast_check/j1/history"]) expect(isAllowed(p)).toBe(false);
    const beat = { at: 1, age_s: 1, stale: false, edge_status: "online", mode: "M-NORMAL", source: null, lanes: null, note: "n" };
    const asked = [];
    const fetcher = async (path) => {
      asked.push(path);
      return path === "/heartbeat/j1/latest" ? { ok: true, status: 200, json: async () => beat } : { ok: false, status: 404 };
    };
    render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
    await waitFor(() => expect(document.querySelector('[data-state="warming"]')).toBeTruthy());
    expect(asked).toContain("/forecast_check/j1/recent");
  });
});

// D32: the operator's first screen. Every word comes from what the page already polls.
describe("the operator's first screen (D32)", () => {
  const HEALTH = ok({ status: "ok" });
  const CLASS4 = { ...CLASS, predictions: { N: "HIGH", S: "MEDIUM", E: "LOW", W: "HIGH" }, missing_approaches: [] };
  const COUNT4 = { ...COUNT, age_s: 12, counts: { N: 2.4, S: 0, E: 0.3, W: 1 }, missing_approaches: [] };
  const beat = (over = {}) => ok({ at: 1, age_s: 2, stale: false, edge_status: "online", mode: "M-NORMAL", source: null, lanes: null, note: "n", ...over });
  const REPLAY = { kind: "replay", session: "a1b2c3d4e5f6", label: "clip", position_s: 4, duration_s: 100 };
  const status = (over = {}) => operatorStatus({ health: HEALTH, cls: ok(CLASS4), count: ok(COUNT4), heartbeat: beat(), ...over });
  const row = (a) => document.querySelector(`[data-forecast-row="${a}"]`);

  it("says updates are arriving, how old they are and how long they hold", () => {
    expect(status()).toEqual({ kind: "ok", head: "Updates are arriving",
      sub: "Last updated 12 s ago. This forecast is valid for 48 s more." });
  });
  it("never calls a recording live", () => {
    expect(status({ heartbeat: beat({ source: REPLAY }) }).head).toBe("Updates are arriving from a recording");
  });
  it("claims arriving only from a fresh heartbeat: a current forecast alone does not show that", () => {
    for (const heartbeat of [{ status: "unavailable" }, { status: "error", reason: "x" }, ok({ source: "bad" })]) {
      const s = status({ heartbeat });
      expect(s.head).toBe("A current forecast is available");
      expect(s.sub).toMatch(/not reporting its status/);
    }
  });
  it("names the approach a forecast is missing for, in either stream", () => {
    expect(status({ cls: ok({ ...CLASS4, predictions: { N: "HIGH", S: "LOW", E: "LOW" }, missing_approaches: ["W"] }) }).head)
      .toBe("Updates are arriving, with approach W missing");
    expect(status({ count: ok({ ...COUNT4, counts: { N: 1, S: 1 }, missing_approaches: ["E", "W"] }) }).head)
      .toBe("Updates are arriving, with approaches E, W missing");
  });
  it("says a silent edge's forecast is its last, with the time it has left", () => {
    expect(status({ heartbeat: beat({ stale: true, age_s: 30 }) })).toEqual({ kind: "stale", head: "The edge unit has stopped reporting",
      sub: "Last heard from 30 s ago. This is its last forecast, valid for 48 s more. No new forecast is being made." });
  });
  it("never reads as current once a forecast is past its horizon", () => {
    const stale = (d) => ok({ ...d, stale: true, age_s: 72 });
    expect(status({ cls: stale(CLASS4), count: stale(COUNT4) })).toMatchObject({ kind: "stale", head: "No recent updates" });
    expect(status({ count: stale(COUNT4) })).toMatchObject({ kind: "stale", head: "The vehicle number forecast is out of date" });
    expect(status({ cls: stale(CLASS4) })).toMatchObject({ kind: "stale", head: "The congestion level forecast is out of date" });
    expect(status({ cls: stale(CLASS4), count: { status: "unavailable" } }).head).toBe("No recent updates");
  });
  it("tells nothing published, an unreachable server, a failing one and a refused forecast apart", () => {
    expect(status({ cls: { status: "unavailable" }, count: { status: "unavailable" } })).toMatchObject({ kind: "none", head: "No forecast yet" });
    expect(status({ count: { status: "unavailable" } })).toMatchObject({ kind: "none", head: "Only the congestion level forecast is arriving" });
    expect(status({ health: { status: "error", reason: "x" } })).toMatchObject({ kind: "bad", head: "Cannot reach the server" });
    expect(status({ health: ok({ status: "degraded" }) })).toMatchObject({ kind: "bad", head: "The server reports a problem" });
    expect(status({ count: ok(CLASS4) })).toMatchObject({ kind: "bad", head: "A forecast cannot be shown" });
    expect(status({ cls: { status: "error", reason: "x" } })).toMatchObject({ kind: "bad", head: "A forecast cannot be shown" });
    expect(status({ health: { status: "loading" } }).kind).toBe("loading");
    expect(status({ cls: { status: "loading" } }).kind).toBe("loading");
  });
  it("announces only the headline, because the line under it changes with the age", () => {
    render(<StatusBanner health={HEALTH} cls={ok(CLASS4)} count={ok(COUNT4)} heartbeat={beat()} />);
    const banner = document.querySelector("[data-status='ok']");
    expect(banner.querySelector("[aria-live]").textContent).toBe("Updates are arriving");
    expect(banner.querySelector("p").closest("[aria-live]")).toBeNull();
  });
  it("shows level and number per approach, a real zero as zero and a missing one as missing", () => {
    render(<ForecastTable cls={ok(CLASS4)} count={ok({ ...COUNT4, counts: { N: 2.4, S: 0 }, missing_approaches: ["E", "W"] })} />);
    expect(row("N").textContent).toBe("NHIGH2.4");
    expect(row("S").textContent).toBe("SMEDIUM0.0");
    expect(row("E").textContent).toBe("ELOWno forecast");
    cleanup();
    render(<ForecastTable cls={ok(CLASS)} count={ok(COUNT)} />);
    for (const a of ["S", "W"]) {
      expect(row(a).querySelectorAll('[data-missing="true"]')).toHaveLength(2);
      expect(row(a).textContent).not.toMatch(/\d|LOW|MEDIUM|HIGH/);
    }
  });
  it("marks a stale forecast in its own column and keeps it readable", () => {
    render(<ForecastTable cls={ok(CLASS4)} count={ok({ ...COUNT4, stale: true, age_s: 72 })} />);
    const [level, number] = row("N").querySelectorAll("td");
    expect(level.dataset.freshness).toBe("fresh");
    expect(number.dataset.freshness).toBe("stale");
    expect(number.textContent).toBe("2.4");
  });
  it("shows nothing from a stream it cannot trust, and never fills it from the other", () => {
    for (const [cls, count, words] of [
      [{ status: "error", reason: "down" }, ok(COUNT4), "no data"], [ok(COUNT4), ok(COUNT4), "no data"],
      [{ status: "unavailable" }, ok(COUNT4), "no forecast"], [{ status: "loading" }, ok(COUNT4), "waiting"],
    ]) {
      render(<ForecastTable cls={cls} count={count} />);
      expect(row("N").querySelector("td").textContent).toBe(words);
      expect(row("N").querySelectorAll("td")[1].textContent).toBe("2.4");
      cleanup();
    }
  });
  it("keeps the signal statement on Live at all times, and the research detail in the closed drawer", async () => {
    render(<App fetcher={async () => ({ ok: false, status: 404 })} search="?id=j1" hash="#live" />);
    expect(document.querySelector('[data-limit="signal"]').textContent)
      .toBe("This system forecasts traffic conditions. It does not control physical traffic signals.");
    const drawer = document.querySelector("[data-technical]");
    expect(drawer.open).toBe(false);
    for (const inside of ['[data-p97a="true"]', "[data-horizon]", '[data-check="Server"]']) {
      expect(drawer.querySelector(inside)).toBeTruthy();
    }
    expect(drawer.textContent).toMatch(/NFR-13/);
    await waitFor(() => expect(document.querySelector("[data-status]").dataset.status).toBe("bad"));
  });
  it("puts the direction notice beside the forecast that uses the letters", () => {
    render(<App fetcher={async () => ({ ok: false, status: 404 })} search="?id=j1" hash="#live" />);
    expect(document.querySelector('[data-directions="unverified"]').nextElementSibling.dataset.forecastTable).toBe("true");
  });
  it("labels the check row's real span, and its right end as the latest check, not now", () => {
    const slots = (n) => Array(n).fill({ kind: "gap" });
    const view = (n) => ({ intersection_id: "j1", session: "a1b2c3d4e5f6", age_s: 1, stale: false, spacing_s: 60,
      slots: [...slots(n - 1), { kind: "check", made_ts: 0, checked_ts: 60, classes: { N: { forecast: "LOW", observed: "LOW" } }, counts: {} }],
      summary: { N: { class: { agreed: 1, n: 1 }, count: { mean_abs_diff: null, n: 0 } } } });
    render(<Agreement state={ok(view(14))} />);
    expect(document.querySelector("[data-axis='time']").textContent).toBe("13 min earlierLatest check");
    expect(document.querySelector("[data-axis='time']").textContent).not.toMatch(/now/i);
    cleanup();
    render(<Agreement state={ok(view(5))} />);
    expect(document.querySelector("[data-axis='time']")).toBeNull();     // too short to carry both ends
  });
});

// D33: the operator's Live page and walkthrough, from real responses only.
describe("summary tiles, counted history and share (D33)", () => {
  const CLASS4 = { ...CLASS, predictions: { N: "HIGH", S: "MEDIUM", E: "LOW", W: "LOW" }, missing_approaches: [] };
  const COUNT4 = { ...COUNT, age_s: 12, counts: { N: 2.4, S: 1.1, E: 2.4, W: 0.3 }, missing_approaches: [] };
  const tile = (n) => document.querySelector(`[data-tile="${n}"]`).textContent;
  const VIEW = (buckets) => ({ intersection_id: "j1", window: "1h", bucket_s: 60, start: 0, end: 3600, buckets, note: "n" });
  const LANES = { lane_0: "N", lane_1: "S" };
  const row = (t, lanes) => ({ t, lanes });

  it("names every approach tied for busiest, and how long the forecast holds", () => {
    render(<SummaryTiles cls={ok(CLASS4)} count={ok(COUNT4)} />);
    expect(tile("busiest")).toContain("Approach N and Approach E 2.4");
    expect(tile("reporting")).toContain("4 of 4");
    expect(tile("valid")).toContain("48 s");
  });
  it("counts only approaches with both forecasts, and names the rest", () => {
    render(<SummaryTiles cls={ok(CLASS4)} count={ok({ ...COUNT4, counts: { N: 1, S: 1 }, missing_approaches: ["E", "W"] })} />);
    expect(tile("reporting")).toMatch(/2 of 4.*E, W have no forecast/);
  });
  it("never gives a current answer from an old forecast, and never a zero for an unknown", () => {
    render(<SummaryTiles cls={ok({ ...CLASS4, stale: true, age_s: 72 })} count={ok({ ...COUNT4, stale: true, age_s: 72 })} />);
    expect(tile("busiest")).toContain("Not current");
    expect(tile("valid")).toContain("Expired");
    cleanup();
    for (const [state, words] of [[{ status: "unavailable" }, "No forecast"], [{ status: "error", reason: "x" }, "No data"], [{ status: "loading" }, "Waiting"]]) {
      render(<SummaryTiles cls={state} count={state} />);
      expect(tile("busiest")).toContain(words);
      expect(tile("busiest")).not.toMatch(/\d/);
      expect(tile("valid")).not.toMatch(/\d/);
      cleanup();
    }
  });
  it("keeps a gap as a gap in the counted history, and maps lanes to approaches", () => {
    const got = recentCounts(ok(VIEW([row(3000, { lane_0: { mean: 2, n: 3 } }), row(3060, {}), row(3120, { lane_0: { mean: 0, n: 3 }, lane_1: { mean: 1, n: 3 } })])), LANES);
    expect(got.N.map((p) => p.mean)).toEqual([2, null, 0]);
    expect(got.S.map((p) => p.mean)).toEqual([null, null, 1]);
    expect(recentCounts(ok(VIEW([])), null)).toBeNull();                   // no lane map, nothing can be named
    expect(recentCounts(ok({ ...VIEW([]), window: "6h" }), LANES)).toBeNull();   // a bad response is refused whole
  });
  it("uses only the last 15 minutes", () => {
    const got = recentCounts(ok(VIEW([row(2640, { lane_0: { mean: 9, n: 1 } }), row(2760, { lane_0: { mean: 1, n: 1 } })])), LANES);
    expect(got.N.map((p) => p.mean)).toEqual([1]);
  });
  it("draws counted values with a break for a gap, says no counts for a lane without any, and keeps a real zero", () => {
    render(<ForecastTable cls={ok(CLASS4)} count={ok(COUNT4)} lanes={LANES}
      recent={ok(VIEW([row(3000, { lane_0: { mean: 2, n: 3 } }), row(3060, {}), row(3120, { lane_0: { mean: 0, n: 3 } })]))} />);
    const cell = (a) => document.querySelector(`[data-counted="${a}"]`);
    expect(cell("N").textContent).toBe("0.0");
    expect(cell("N").querySelector("path").getAttribute("d").match(/M/g)).toHaveLength(2);
    for (const a of ["S", "E", "W"]) expect(cell(a).textContent).toBe("no counts");
  });
  it("shows the share of current forecasts only, and nothing when none is expected", () => {
    render(<ExpectedShare state={ok({ ...COUNT4, counts: { N: 3, S: 1 }, missing_approaches: ["E", "W"] })} />);
    expect(document.querySelector("[data-share]").textContent).toMatch(/N 75%.*S 25%/);
    cleanup();
    for (const state of [ok({ ...COUNT4, stale: true }), ok({ ...COUNT4, counts: { N: 0, S: 0, E: 0, W: 0 } }), { status: "unavailable" }]) {
      render(<ExpectedShare state={state} />);
      expect(document.querySelector("[data-share]")).toBeNull();
      cleanup();
    }
  });
});

describe("the 20-minute level row (D33)", () => {
  const SLOT = (classes) => ({ kind: "check", made_ts: 0, checked_ts: 60, classes, counts: {} });
  const SLOTS = [SLOT({ N: { forecast: "HIGH", observed: "HIGH" } }), { kind: "gap" }, SLOT({ N: { forecast: "HIGH", observed: "LOW" } })];
  const view = { intersection_id: "j1", session: "a1b2c3d4e5f6", age_s: 1, stale: false, spacing_s: 60, slots: SLOTS, summary: agreement(SLOTS) };
  const cell = (i) => document.querySelectorAll('[data-check-row="N"] [data-cell]')[i];
  it("colours a cell by what the counts showed, names it by letter, and marks a miss by shape", () => {
    render(<Agreement state={ok(view)} />);
    expect(cell(0).querySelector("text").textContent).toBe("H");
    expect(cell(0).querySelector("[data-cut]")).toBeNull();
    expect(cell(1).querySelector("text")).toBeNull();
    expect(cell(2).querySelector("text").textContent).toBe("L");
    expect(cell(2).querySelector("[data-cut]")).toBeTruthy();
  });
});

describe("the walkthrough and glossary (D33)", () => {
  const fetcher = async () => ({ ok: false, status: 404 });
  window.scrollTo = () => {};   // jsdom has no layout to scroll
  const open = async (mode) => {
    render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
    document.querySelector("[data-tour-start]").click();
    await waitFor(() => expect(document.querySelector("[data-tour-card]")).toBeTruthy());
    if (mode) { document.querySelector(`[data-tour-mode="${mode}"]`).click(); await waitFor(() => expect(screen.getByText(/^Step 1 of/)).toBeTruthy()); }
  };
  const press = (key) => document.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  afterEach(() => { window.location.hash = ""; try { window.localStorage.clear(); } catch { /* not available */ } });

  it("names a real part of the page in every Live step", async () => {
    render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
    for (const s of LIVE_STEPS) expect(document.querySelector(`[data-tour="${s.target}"]`), s.target).toBeTruthy();
    cleanup();
    for (const [hash, s] of [["#analyze", MORE_STEPS[0]], ["#analytics", MORE_STEPS[1]], ["#results", MORE_STEPS[2]]]) {
      render(<App fetcher={fetcher} search="?id=j1" hash={hash} />);
      expect(document.querySelector(`[data-tour="${s.target}"]`), s.target).toBeTruthy();
      cleanup();
    }
  });
  it("never claims what the system cannot do", () => {
    const words = JSON.stringify([LIVE_STEPS.concat(MORE_STEPS).map(({ title, what, read, limit }) => [title, what, read, limit]), GLOSSARY, QUIZ]);
    // Saying what the system does not measure is the point; claiming it measures them is the failure.
    expect(words.replace("It is not the road's capacity", "").replaceAll("not measure speed or queues", "")).not.toMatch(/capacity|queue|UTC|cryptographic|adaptive/i);
  });
  it("opens with the choice of tours, and blocks the page behind it", async () => {
    await open();
    expect(screen.getByText("What is STMS?")).toBeTruthy();
    expect(document.querySelector("main").hasAttribute("inert")).toBe(true);
    expect(document.querySelector('[data-tour-mode="live"]').textContent).toContain(`${LIVE_STEPS.length} steps`);
    expect(document.querySelector('[data-tour-mode="full"]').textContent).toContain(`${LIVE_STEPS.length + MORE_STEPS.length} steps`);
  });
  it("draws its examples inside the card, marked, and leaves the real page alone", async () => {
    await open("live");
    document.querySelector("[data-tour-next]").click();
    await waitFor(() => expect(document.querySelector("[data-try]")).toBeTruthy());
    const real = () => document.querySelector("main [data-status]").dataset.status;
    const before = real();
    document.querySelector('[data-try="stale"]').click();
    await waitFor(() => expect(document.querySelector('[data-tour-example="stale"]')).toBeTruthy());
    const example = document.querySelector('[data-tour-example="stale"]');
    expect(example.textContent).toMatch(/Example, not real data/);
    expect(example.textContent).toMatch(/No recent updates/);
    expect(real()).toBe(before);
    expect(document.querySelector('main [data-status]').textContent).not.toMatch(/No recent updates/);
  });
  it("gives each example the state it is named for", () => {
    const head = (k) => operatorStatus(EXAMPLES[k]).head;
    expect(head("normal")).toBe("Updates are arriving");
    expect(head("replay")).toBe("Updates are arriving from a recording");
    expect(head("partial")).toBe("Updates are arriving, with approach W missing");
    expect(head("silent")).toBe("The edge unit has stopped reporting");
    expect(head("stale")).toBe("No recent updates");
    expect(head("none")).toBe("No forecast yet");
    expect(head("down")).toBe("Cannot reach the server");
  });
  it("says what the page really shows now", async () => {
    await open("live");
    document.querySelector("[data-tour-next]").click();
    await waitFor(() => expect(document.querySelector("[data-tour-now]")).toBeTruthy());
    expect(document.querySelector("[data-tour-now]").textContent).toContain(document.querySelector("main [data-status] h2").textContent);
  });
  it("walks every step by keyboard, reaches the questions, and leaves on Escape with the page restored", async () => {
    await open("live");
    for (let i = 1; i < LIVE_STEPS.length; i++) {
      press("ArrowRight");
      await waitFor(() => expect(screen.getByText(`Step ${i + 1} of ${LIVE_STEPS.length}`)).toBeTruthy());
    }
    expect(document.querySelector("[data-technical]").open).toBe(true);
    press("ArrowRight");
    await waitFor(() => expect(screen.getByText("Three questions")).toBeTruthy());
    press("Escape");
    await waitFor(() => expect(document.querySelector("[data-tour-card]")).toBeNull());
    expect(document.querySelector("main").hasAttribute("inert")).toBe(false);
    expect(document.querySelector("[data-technical]").open).toBe(false);
  });
  it("goes to Analytics and Results on the full tour, and comes back", async () => {
    await open("full");
    for (let i = 1; i <= LIVE_STEPS.length; i++) { press("ArrowRight"); await waitFor(() => expect(screen.getByText(new RegExp(`^Step ${i + 1} of`))).toBeTruthy()); }
    await waitFor(() => expect(screen.getByLabelText("Analyze a video", { selector: "section" })).toBeTruthy());
    press("ArrowRight");
    await waitFor(() => expect(screen.getByLabelText("Analytics", { selector: "section" })).toBeTruthy());
    press("ArrowRight");
    await waitFor(() => expect(screen.getByLabelText("Results", { selector: "section" })).toBeTruthy());
    press("Escape");
    await waitFor(() => expect(screen.getByLabelText("Live monitor")).toBeTruthy());
  });
  it("marks the questions and records nothing", async () => {
    const asked = [];
    render(<App fetcher={async (p, init) => { asked.push(init?.method); return { ok: false, status: 404 }; }} search="?id=j1" hash="#live" />);
    document.querySelector("[data-tour-start]").click();
    await waitFor(() => expect(document.querySelector("[data-tour-mode]")).toBeTruthy());
    document.querySelector('[data-tour-mode="live"]').click();
    await waitFor(() => expect(document.querySelector("[data-tour-next]")).toBeTruthy());
    for (let i = 0; i < LIVE_STEPS.length; i++) { press("ArrowRight"); await new Promise((r) => setTimeout(r, 5)); }
    await waitFor(() => expect(screen.getByText("Three questions")).toBeTruthy());
    const pick = (n, k) => document.querySelectorAll(`input[name="quiz${n}"]`)[k].click();
    pick(0, 0); pick(1, 0); pick(2, 2);
    await waitFor(() => expect(document.querySelector("[data-quiz-score]")).toBeTruthy());
    expect(document.querySelector("[data-quiz-score]").textContent).toBe("2 of 3 correct.");
    expect(document.querySelector('[data-quiz-feedback="1"]').textContent).toMatch(/The answer is: The system does not know/);
    expect(asked.every((m) => m === "GET")).toBe(true);
  });
  it("invites once, and remembers a no", async () => {
    render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
    expect(document.querySelector("[data-tour-invite]")).toBeTruthy();
    screen.getByText("Not now").click();
    await waitFor(() => expect(document.querySelector("[data-tour-invite]")).toBeNull());
    cleanup();
    render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
    expect(document.querySelector("[data-tour-invite]")).toBeNull();
  });
  it("says what a level is, and what it is not", () => {
    render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
    const text = document.querySelector("[data-levels]").textContent;
    expect(text).toMatch(/this camera's own range/);
    expect(text).toMatch(/do not measure speed or queues/);
    expect(text).toMatch(/HIGH can be only a few vehicles/);
  });
  it("opens the glossary and closes it", async () => {
    render(<App fetcher={fetcher} search="?id=j1" hash="#live" />);
    screen.getByText("Glossary").click();
    await waitFor(() => expect(document.querySelector("[data-glossary]")).toBeTruthy());
    for (const [term] of GLOSSARY) expect(within(document.querySelector("[data-glossary]")).getByText(term)).toBeTruthy();
    screen.getByText("Close").click();
    await waitFor(() => expect(document.querySelector("[data-glossary]")).toBeNull());
  });
});

// D34: the rest of the console, from real data only.
describe("the timing suggestion (D34)", () => {
  const COUNT4 = { ...COUNT, counts: { N: 1, S: 1, E: 3, W: 3 }, missing_approaches: [] };
  it("shares green by expected vehicles, by pair", () => {
    expect(timingSuggestion(ok(COUNT4))).toEqual([{ name: "N + S", share: 25 }, { name: "E + W", share: 75 }]);
  });
  it("suggests nothing from a stale, partial, empty or absent forecast", () => {
    for (const state of [ok({ ...COUNT4, stale: true }), ok(COUNT), ok({ ...COUNT4, counts: { N: 0, S: 0, E: 0, W: 0 } }), { status: "unavailable" }, { status: "error", reason: "x" }]) {
      expect(timingSuggestion(state)).toBeNull();
    }
  });
  it("says it is not the real signal, in every state, and never names a colour as current", () => {
    for (const state of [ok(COUNT4), { status: "unavailable" }]) {
      render(<TimingSuggestion state={state} />);
      const text = document.querySelector("[data-what-if]").textContent;
      expect(text).toMatch(/Not the real signal/);
      expect(text).toMatch(/current signal colour is not known/);
      expect(text).not.toMatch(/green now|is green|is red|PPO|phase \d/i);
      cleanup();
    }
  });
  it("leaves the signal heads unknown beside it", () => {
    render(<Intersection cls={ok(CLASS)} count={ok(COUNT)} />);
    for (const head of document.querySelectorAll("[data-signal]")) expect(head.textContent).toBe("?");
  });
});

describe("the corridor strip (D34)", () => {
  const SITES = { sites: [{ id: "live", age_s: 1.2, stale: false, kind: "replay", label: "Eastgate" }, { id: "b", age_s: 40, stale: true, kind: "camera", label: "x" }] };
  it("shows only what has reported, and says when one has gone silent", () => {
    render(<SiteStrip state={ok(SITES)} current="live" />);
    const site = (id) => document.querySelector(`[data-site="${id}"]`);
    expect(site("live").textContent).toContain("Replay · Eastgate");
    expect(site("live").getAttribute("aria-current")).toBe("true");
    expect(site("b").textContent).toContain("Silent for 40 s");
    expect(site("b").textContent).not.toMatch(/Live camera/);
  });
  it("shows nothing when none has reported, or for a bad response", () => {
    const probe = { id: "readiness-probe", age_s: 90, stale: true, kind: null, label: null };
    for (const state of [ok({ sites: [] }), ok({ sites: [probe] }), ok({ sites: [{ id: "bad id" }] }), { status: "unavailable" }]) {
      render(<SiteStrip state={state} current="j1" />);
      expect(document.querySelector("[data-sites]")).toBeNull();
      cleanup();
    }
    expect(validateSites({ sites: [{ id: "a", age_s: 1, stale: "no", kind: null, label: null }] }).ok).toBe(false);
    expect(isAllowed("/sites")).toBe(true);
  });
});

describe("when each lane is busy (D34)", () => {
  const at = (hour, minute = 0) => new Date(2026, 0, 1, hour, minute).getTime() / 1000;
  const VIEW = (buckets) => ({ intersection_id: "j1", window: "24h", bucket_s: 900, start: 0, end: 1, buckets, note: "n" });
  it("weights a mean by its samples, per clock hour", () => {
    const got = busyByHour([{ t: at(9), lanes: { lane_0: { mean: 1, n: 1 } } }, { t: at(9, 15), lanes: { lane_0: { mean: 4, n: 3 } } }]);
    expect(got.lane_0[9]).toBeCloseTo(3.25, 5);
    expect(got.lane_0[10]).toBeNull();
  });
  it("marks an hour with no counts as a gap, and a real zero as a value", () => {
    render(<BusyByHour lanes={{ lane_0: "N" }} state={ok(VIEW([{ t: at(9), lanes: { lane_0: { mean: 0, n: 2 } } }, { t: at(10), lanes: { lane_0: { mean: 2, n: 2 } } }]))} />);
    expect(document.querySelector('[data-hour="9"]').dataset.value).toBe("0.00");
    expect(document.querySelector('[data-hour="11"]').dataset.value).toBe("none");
    expect(document.querySelector("[data-busiest]").textContent).toContain("10:00");
    expect(document.querySelector("[data-busy-lane]").textContent).toContain("N");
  });
  it("says so when nothing was counted, and refuses a bad response", () => {
    for (const state of [ok(VIEW([{ t: at(9), lanes: {} }])), { status: "unavailable" }, ok({ window: "1h" })]) {
      render(<BusyByHour lanes={null} state={state} />);
      expect(document.querySelectorAll("[data-hour]")).toHaveLength(0);
      expect(document.querySelector("[data-busy-empty]")).toBeTruthy();
      cleanup();
    }
  });
});

describe("the signal study in Results (D34)", () => {
  const STUDY = { id: "P130", question: "q", metric: "mean total delay (s)", seeds: 28, reading: "no demonstrated control benefit", qualifiers: ["simulation evidence only"],
    file: "f.json", commit: "abc1234", date: "2026-10-17", arms: [{ name: "Webster", kind: "rule", mean: 37.37, ci95: [34.1, 40.92] }, { name: "PPO", kind: "ppo", mean: 43.72, ci95: [38.75, 49.4] }] };
  it("shows every arm with its interval, the reading and its commit, and says it is a simulator", () => {
    render(<EvidencePanel state={ok({ label: "l", limitations: [], studies: [], signal_study: STUDY })} />);
    const text = document.querySelector("[data-signal-study]").textContent;
    expect(text).toMatch(/not on a road/);
    expect(text).toMatch(/37\.4 \[34\.1, 40\.9\]/);
    expect(text).toMatch(/no demonstrated control benefit/);
    expect(text).toMatch(/abc1234/);
    expect(document.querySelectorAll('[data-arm="ppo"]')).toHaveLength(1);
  });
  it("shows no study when the file is absent", () => {
    render(<EvidencePanel state={ok({ label: "l", limitations: [], studies: [], signal_study: null })} />);
    expect(document.querySelector("[data-signal-study]")).toBeNull();
  });
});

describe("Analyze a video (D34)", () => {
  const sample = (t, over = {}) => ({ t, counts: { lane_0: 2, lane_1: 0 }, boxes: [[0.1, 0.1, 0.2, 0.2]], level: null, number: null, then: null, ...over });
  const ANALYSIS = { kind: "stms-video-analysis", schema: 1, camera: "150th_Eastgate", clip: "clip", step_s: 2, duration_s: 6,
    lanes: [{ name: "lane_0", centre: [0.2, 0.7], approach: "N" }, { name: "lane_1", centre: [0.3, 0.2], approach: "S" }],
    limits: { low: 0.13, med: 0.97 }, known_limits: ["parked vehicles count"], directions_verified: false,
    models: { level: "persistence@x", number: "ridge@x" },
    samples: [sample(0), sample(2, { level: { N: "HIGH", S: "LOW" } }),
              sample(4, { level: { N: "HIGH", S: "LOW" }, number: { N: 2.4, S: 0.1 }, then: { N: { level: "MEDIUM", number: 0.8 }, S: { level: "LOW", number: 0 } } })] };
  const open = async (json) => {
    const input = document.querySelector("[data-open-results]");
    const file = new File([typeof json === "string" ? json : JSON.stringify(json)], "results.json", { type: "application/json" });
    file.text = async () => (typeof json === "string" ? json : JSON.stringify(json));
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  };
  const scrub = (v) => {
    const range = document.querySelector('input[type="range"]');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(range, String(v));
    range.dispatchEvent(new Event("input", { bubbles: true }));
  };
  const row = (n) => document.querySelector(`[data-analysis-row="${n}"]`).textContent;

  it("accepts a whole results file and refuses a bad one whole", () => {
    expect(validateAnalysis(ANALYSIS).ok).toBe(true);
    for (const bad of [{ kind: "x" }, { schema: 2 }, { step_s: 5 }, { lanes: [] }, { limits: { low: 2, med: 1 } }, { samples: [] },
                       { samples: [sample(0, { counts: { lane_0: 1 } })] }, { samples: [sample(0, { counts: { lane_0: -1, lane_1: 0 } })] },
                       { samples: [sample(0, { boxes: [[0, 0, 2, 1]] })] }, { samples: [sample(0, { level: { N: "LOUD", S: "LOW" } })] },
                       { samples: [sample(2), sample(0)] }, { directions_verified: "no" }]) {
      expect(validateAnalysis({ ...ANALYSIS, ...bad }).ok).toBe(false);
    }
  });
  it("finds the sample for a moment, and keeps to the file's ends", () => {
    expect(sampleAt(ANALYSIS, 3).t).toBe(2);
    expect(sampleAt(ANALYSIS, 999).t).toBe(4);
    expect(sampleAt(ANALYSIS, -1).t).toBe(0);
  });
  it("shows no numbers until a results file is open, and says how to make one", () => {
    render(<AnalyzeVideo />);
    expect(document.querySelector('[data-state="no-results"]')).toBeTruthy();
    expect(document.querySelector("[data-analysis-how]").textContent).toMatch(/analyze_video\.py/);
    expect(document.querySelector("[data-analysis-row]")).toBeNull();
    expect(document.querySelector("[data-box]")).toBeNull();
  });
  it("follows the position in the recording: waiting, then forecasts, then what happened", async () => {
    render(<AnalyzeVideo />);
    await open(ANALYSIS);
    await waitFor(() => expect(document.querySelector('[data-analysis-row="lane_0"]')).toBeTruthy());
    expect(document.querySelector("[data-analysis-note]").textContent).toMatch(/level starts at 01:00/);
    expect(row("lane_0")).toMatch(/L0 label N2waiting/);
    scrub(4);
    await waitFor(() => expect(row("lane_0")).toMatch(/HIGH2\.4MEDIUM 0\.8 differs/));
    expect(row("lane_1")).not.toMatch(/differs/);
    expect(document.querySelector("[data-box]")).toBeTruthy();
    expect(document.querySelector('[data-pin="L0"]').style.left).toBe("20%");
    expect(document.querySelector("[data-known-limits]").textContent).toMatch(/parked vehicles/);
    expect(document.querySelector('section[aria-label="Results at this moment"]').textContent).toMatch(/LOW is up to 0\.13/);
    expect(document.querySelector('[data-directions="unverified"]')).toBeTruthy();
  });
  it("refuses a file that is not a results file, and shows nothing from it", async () => {
    render(<AnalyzeVideo />);
    await open("not json");
    await waitFor(() => expect(screen.getByText(/is not a results file/)).toBeTruthy());
    cleanup();
    render(<AnalyzeVideo />);
    await open({ ...ANALYSIS, step_s: 5 });
    await waitFor(() => expect(screen.getByText(/was refused: invalid timing/)).toBeTruthy());
    expect(document.querySelector("[data-analysis-row]")).toBeNull();
  });
  it("is a section of its own, with no live badge over a recording", async () => {
    render(<App fetcher={async () => ({ ok: false, status: 404 })} search="?id=j1" hash="#analyze" />);
    expect(screen.getByLabelText("Analyze a video", { selector: "section" })).toBeTruthy();
    expect(screen.queryByLabelText("Live monitor")).toBeNull();
    expect(document.querySelector("[data-source]")).toBeNull();
  });
});
