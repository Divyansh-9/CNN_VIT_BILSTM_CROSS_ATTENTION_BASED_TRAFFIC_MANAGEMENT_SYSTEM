import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App, { SECTIONS, intersectionFromUrl, sectionFromHash } from "./App.jsx";
import { get, isAllowed } from "./api.js";
import { ICONS } from "./icons.jsx";
import { ObservedCounts, scaleTop } from "./Analytics.jsx";
import { Horizon, Intersection, SCALE_MAX, horizon, junction, ribbonLength } from "./Intersection.jsx";
import { ClassPanel, CountPanel, HistoryPanel, Overview, StatusPanel, overview } from "./Panels.jsx";
import { ReplayNote, SourceBadge } from "./Source.jsx";
import { validateClass, validateCount, validateCountHistory, validateHeartbeat, validateHistory } from "./validate.js";

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
    expect(label("W")).toBe("W HIGH 12.0 veh");
  });
  it("draws a missing approach as missing: no ribbon, no class, no zero", () => {
    render(<Intersection cls={ok(CLASS)} count={ok(COUNT)} />);
    for (const a of ["S", "W"]) {
      expect(ribbon(a)).toBeNull();
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
    expect(caption).toMatch(/count forecast \(ridge\)/);
    expect(caption).toMatch(/congestion\s+class \(persistence\)/);
    expect(caption).toMatch(/not connected\s+\(P97a\)/);
    expect(caption).toMatch(/No vehicles or video/);
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
    expect(overview(ok(CLASS4)).headline).toBe("2 of 4 approaches HIGH");
    expect(overview(ok(CLASS4)).detail).toMatch(/^North HIGH, South HIGH, East MEDIUM, West LOW\. Updated 3 s ago\.$/);
    const allLow = { ...CLASS4, predictions: { N: "LOW", S: "LOW", E: "LOW", W: "LOW" } };
    expect(overview(ok(allLow)).headline).toBe("All 4 approaches LOW");
  });
  it("counts only the approaches that have a forecast, and names the ones that do not", () => {
    const o = overview(ok(CLASS));                        // N HIGH, E LOW; S and W missing
    expect(o.headline).toBe("1 of 2 available approaches HIGH");
    expect(o.detail).toMatch(/South, West have no forecast/);
    const two = overview(ok({ ...CLASS, predictions: { N: "HIGH", S: "HIGH" }, missing_approaches: ["E", "W"] }));
    expect(two.headline).toBe("All 2 available approaches HIGH");
    expect(two.detail).toMatch(/East, West have no forecast/);
    const one = overview(ok({ ...CLASS, predictions: { E: "MEDIUM" }, missing_approaches: ["N", "S", "W"] }));
    expect(one.headline).toBe("East MEDIUM");
    expect(one.detail).toMatch(/North, South, West have no forecast/);
  });
  it("never answers with a class from a stale forecast", () => {
    const o = overview(ok({ ...CLASS4, stale: true, age_s: 78 }));
    expect(o.kind).toBe("stale");
    expect(o.headline).toBe("No current forecast");
    expect(o.headline).not.toMatch(CLASS_WORDS);
    expect(o.detail).toMatch(/78 s old, past its horizon/);
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
    expect(document.querySelector("[data-overview='fresh'] [aria-live]").textContent).toBe("2 of 4 approaches HIGH");
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
