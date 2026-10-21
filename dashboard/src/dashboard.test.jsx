import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App, { intersectionFromUrl } from "./App.jsx";
import { get, isAllowed } from "./api.js";
import { ClassPanel, CountPanel } from "./Panels.jsx";
import { validateClass, validateCount } from "./validate.js";

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
const lane = (a) => document.querySelector(`[data-approach="${a}"]`);

describe("read-only by construction", () => {
  it("allows only the three GET endpoints", () => {
    expect(isAllowed("/count_forecast/j1/latest")).toBe(true);
    expect(isAllowed("/prediction/j1/latest")).toBe(true);
    expect(isAllowed("/evidence")).toBe(true);
    for (const p of ["/observation", "/prediction/j1", "/count_forecast/j1", "/history/j1", "/x"]) {
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
    const body = path.startsWith("/count_forecast") ? COUNT : path.startsWith("/prediction") ? CLASS : evidence;
    return { ok: true, status: 200, json: async () => body };
  };
  it("keeps live forecasts and historical evidence in separate regions, with the P97a warning", async () => {
    render(<App fetcher={fetcher} search="?id=j1" />);
    const live = screen.getByLabelText("Live monitor");
    const results = screen.getByLabelText("Results");
    await waitFor(() => expect(within(results).getByText(/abc1234/)).toBeTruthy());
    expect(within(live).queryByText(/abc1234|macro-F1|MAE/)).toBeNull();
    expect(within(results).queryByText(/ridge · point estimate/)).toBeNull();
    const banner = live.querySelector('[data-p97a="true"]').textContent;
    expect(banner).toMatch(/P97a/);
    // D2: the encoding as it is since P110, not as it was before.
    expect(banner).toMatch(/0\.0 means an approach has no forecast/);
    expect(banner).toMatch(/LOW is encoded as 1\/3/);
    expect(banner).not.toMatch(/same value as LOW/);
    await waitFor(() => expect(within(live).getByText("ridge@73532968dcf2")).toBeTruthy());
    expect(within(live).getByText("persistence@2431c6641b9c")).toBeTruthy();
  });
});
