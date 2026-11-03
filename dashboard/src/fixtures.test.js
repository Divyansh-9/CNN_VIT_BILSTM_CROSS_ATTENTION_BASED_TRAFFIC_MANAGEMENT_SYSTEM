// D36: the committed fixtures in ./fixtures/, generated from the real server by
// scripts/ui_fixture.py. tests/test_ui_fixture.py proves each file is still exactly what the
// server sends; this file proves the page accepts the same files with its own checks, and
// renders each state as the state says. A change on either side fails one of the two.
import { createElement } from "react";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App.jsx";
import { isAllowed } from "./api.js";
import { validateChecks, validateClass, validateCount, validateCountHistory, validateHeartbeat, validateHistory,
         validateLatestCounts, validateSites } from "./validate.js";

afterEach(cleanup);

const FILES = import.meta.glob("./fixtures/*.json", { eager: true, import: "default" });
const FIXTURES = Object.fromEntries(Object.values(FILES).map((f) => [f.state, f]));
const ID = "test-fixture";
const NAMES = Object.keys(FIXTURES).sort();

// The page's own validator for each endpoint. /health has none in validate.js: the status banner
// reads `status`, so this mirrors exactly that.
const VALIDATORS = [
  [/^\/prediction\/[^/]+\/latest$/, (json) => validateClass(json)],
  [/^\/count_forecast\/[^/]+\/latest$/, (json) => validateCount(json)],
  [/^\/prediction\/[^/]+\/history$/, (json) => validateHistory(json, "class")],
  [/^\/count_forecast\/[^/]+\/history$/, (json) => validateHistory(json, "count")],
  [/^\/vehicle_count\/[^/]+\/history\?window=(1h|6h|24h)$/, (json, path) => validateCountHistory(json, path.split("=")[1])],
  [/^\/vehicle_count\/[^/]+\/latest$/, (json) => validateLatestCounts(json)],
  [/^\/heartbeat\/[^/]+\/latest$/, (json) => validateHeartbeat(json)],
  [/^\/forecast_check\/[^/]+\/recent$/, (json) => validateChecks(json)],
  [/^\/sites$/, (json) => validateSites(json)],
  [/^\/health$/, (json) => (json?.status === "ok" ? { ok: true } : { ok: false, reason: "health is not ok" })],
];
const validatorFor = (path) => VALIDATORS.find(([pattern]) => pattern.test(path))?.[1];

// Answers exactly what the server answered: the status, and the body as JSON.
const fetcherFor = (fixture, requested) => async (path) => {
  requested.add(path);
  const reply = fixture.responses[path];
  if (!reply) return { status: 404, ok: false, json: async () => ({ detail: "not in this fixture" }) };
  return { status: reply.status, ok: reply.status >= 200 && reply.status < 300, json: async () => structuredClone(reply.body) };
};

const banner = () => document.querySelector('section[aria-label="Are updates arriving"]');

describe("UI fixtures from the real server (D36)", () => {
  it("covers the usability test's states", () => {
    for (const name of ["missing_count", "normal", "stale_edge"]) expect(NAMES).toContain(name);
  });

  it.each(NAMES)("%s: every response passes the page's own checks", (name) => {
    for (const [path, reply] of Object.entries(FIXTURES[name].responses)) {
      expect(isAllowed(path), path).toBe(true);
      if (reply.status === 404) continue;
      expect(reply.status, path).toBe(200);
      const validate = validatorFor(path);
      expect(validate, `no validator for ${path}`).toBeTruthy();
      const checked = validate(reply.body, path);
      expect(checked.ok, `${path}: ${checked.reason}`).toBe(true);
    }
  });

  it.each(NAMES)("%s: the page shows the banner the state was made for, and a test fixture as one", async (name) => {
    const fixture = FIXTURES[name], requested = new Set();
    render(createElement(App, { fetcher: fetcherFor(fixture, requested), search: `?id=${ID}`, hash: "#live" }));
    await waitFor(() => expect(banner().querySelector("h2").textContent).toBe(fixture.banner));
    // Every request the page made is in the fixture, so nothing it shows came from a 404 the
    // fixture never recorded. /evidence is left out on purpose: it is not database-backed.
    expect([...requested].filter((p) => p !== "/evidence" && !(p in fixture.responses))).toEqual([]);
    const badge = document.querySelector("[data-source]");
    expect(badge.dataset.source).not.toBe("camera");
    if (badge.dataset.source === "replay") expect(badge.textContent).toContain(`TEST_FIXTURE_${name}`);
  });

  // D37: the usability test's first state, on the real server's responses. Every part of the page
  // agrees that reporting is partial: no tile says none, and the drawing names the levels.
  it("missing_count: the tile says partial and the drawing names every level (F1, F2)", async () => {
    const fixture = FIXTURES.missing_count;
    render(createElement(App, { fetcher: fetcherFor(fixture, new Set()), search: `?id=${ID}`, hash: "#live" }));
    await waitFor(() => expect(banner().querySelector("h2").textContent).toBe(fixture.banner));
    await waitFor(() => expect(document.querySelector('[data-tile="reporting"]').textContent).toContain("Partial"));
    expect(document.querySelector('[data-tile="reporting"]').textContent).toContain("4 of 4 have a level. No vehicle number yet.");
    expect(document.body.textContent).not.toContain("None yet");
    // F6: the freshness tile names the current level instead of saying there is no forecast.
    expect(document.querySelector('[data-tile="valid"]').textContent).toBe("Forecast valid forLevel: currentNo vehicle number forecast yet");
    const levels = fixture.responses[`/prediction/${ID}/latest`].body.predictions;
    const label = (a) => [...document.querySelectorAll(`[data-label="${a}"] tspan`)].map((t) => t.textContent).join(" ");
    for (const [a, level] of Object.entries(levels)) expect(label(a)).toBe(`${a} ${level} no count yet`);
  });

  // D37, the reverse partial state, on the real server's `normal` responses with only the level
  // endpoint answering 404. The committed fixture is read, never changed.
  it("count only: the page shows the numbers, says the level has not arrived, and invents none", async () => {
    const fixture = FIXTURES.normal;
    const noLevel = { ...fixture, responses: { ...fixture.responses,
      [`/prediction/${ID}/latest`]: { status: 404, body: { detail: "no prediction for this intersection yet" } } } };
    render(createElement(App, { fetcher: fetcherFor(noLevel, new Set()), search: `?id=${ID}`, hash: "#live" }));
    await waitFor(() => expect(banner().querySelector("h2").textContent).toBe("Only the vehicle number forecast is arriving"));
    // F7: the first tile says the vehicle-count forecast is there, never that nothing was published.
    expect(document.querySelector("[data-overview]").dataset.overview).toBe("count");
    expect(document.querySelector("[data-overview]").textContent).toContain("Vehicle-count forecast available");
    expect(document.body.textContent).not.toContain("Nothing has been published for this intersection");
    expect(document.querySelector('[data-tile="reporting"]').textContent).toBe("Approaches reportingPartial4 of 4 have a vehicle number. No level yet.");
    expect(document.querySelector('[data-tile="valid"]').textContent).toBe("Forecast valid forVehicle number: currentNo level forecast yet");
    const counts = fixture.responses[`/count_forecast/${ID}/latest`].body.counts;
    const label = (a) => [...document.querySelectorAll(`[data-label="${a}"] tspan`)].map((t) => t.textContent).join(" ");
    for (const [a, n] of Object.entries(counts)) {
      expect(label(a)).toBe(`${a} no level yet ${n.toFixed(1)} veh`);
      expect(document.querySelector(`[data-ribbon="${a}"]`).dataset.level).toBe("none");
    }
    expect(document.querySelector('[data-tour="drawing"] figure').textContent).not.toMatch(/LOW|MEDIUM|HIGH/);
    expect(fixture.responses[`/prediction/${ID}/latest`].status).toBe(200);    // the committed fixture is untouched
  });

  it("server_down: every request fails as unreachable, and the page says so", async () => {
    const fetcher = async () => { throw new TypeError("Failed to fetch"); };
    render(createElement(App, { fetcher, search: `?id=${ID}`, hash: "#live" }));
    await waitFor(() => expect(banner().querySelector("h2").textContent).toBe("Cannot reach the server"));
    expect(banner().dataset.status).toBe("bad");
    expect(document.querySelector("[data-source]").textContent).toMatch(/server not reachable/);
  });
});

// The planted failures: a committed fixture with a field the page needs taken out must be
// refused by the page's own validator. A contract check that cannot fail proves nothing.
const REQUIRED = {
  [`/prediction/${ID}/latest`]: ["role", "model", "age_s", "stale", "predictions", "missing_approaches"],
  [`/count_forecast/${ID}/latest`]: ["role", "model", "age_s", "stale", "counts", "missing_approaches"],
  [`/prediction/${ID}/history`]: ["rows"],
  [`/count_forecast/${ID}/history`]: ["rows"],
  [`/vehicle_count/${ID}/history?window=1h`]: ["window", "bucket_s", "buckets"],
  [`/vehicle_count/${ID}/latest`]: ["lanes", "pcu"],
  [`/heartbeat/${ID}/latest`]: ["age_s", "stale", "source", "lanes"],
  [`/forecast_check/${ID}/recent`]: ["session", "age_s", "stale", "spacing_s", "slots", "summary"],
  "/sites": ["sites"],
};

describe("a fixture missing what the page needs is refused (D36)", () => {
  it.each(Object.entries(REQUIRED))("%s", (path, fields) => {
    const reply = FIXTURES.normal.responses[path];
    const validate = validatorFor(path);
    expect(validate(reply.body, path).ok).toBe(true);
    for (const field of fields) {
      const broken = structuredClone(reply.body);
      delete broken[field];
      expect(validate(broken, path).ok, `${path} without ${field}`).toBe(false);
    }
  });

  it("a nested field too: a replay with no label, a PCU table with no source", () => {
    const beat = structuredClone(FIXTURES.normal.responses[`/heartbeat/${ID}/latest`].body);
    delete beat.source.label;
    expect(validateHeartbeat(beat).ok).toBe(false);
    const counts = structuredClone(FIXTURES.normal.responses[`/vehicle_count/${ID}/latest`].body);
    delete counts.pcu.source;
    expect(validateLatestCounts(counts).ok).toBe(false);
  });
});
