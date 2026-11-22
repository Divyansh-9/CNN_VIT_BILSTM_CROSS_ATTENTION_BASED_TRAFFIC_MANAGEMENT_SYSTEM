// The landing page, the project explorer and the console's Overview: the three
// experiences around the console, and the router that chooses between them.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { vehiclesNow } from "./ConsoleOverview.jsx";
import { Explorer, topicIndex } from "./Explorer.jsx";
import { TOPICS } from "./explorerContent.js";
import { Landing } from "./Landing.jsx";
import { PipelineWalkthrough } from "./PipelineWalkthrough.jsx";
import { fetchPreview, needsSignIn, PREVIEW_SITE } from "./preview.js";
import Root, { routeOf } from "./Root.jsx";
import { SITE } from "./site.js";
import { ThemeSwitch } from "./ThemeSwitch.jsx";
import { applyTheme, storedTheme } from "./theme.js";

// jsdom has no layout, so scrolling is a no-op here rather than a logged "not implemented".
window.scrollTo = () => {};
afterEach(() => { cleanup(); window.location.hash = ""; });

const ok = (data) => ({ status: "ok", data });

it("shows the Bellevue still and its matching measurements in the pipeline", () => {
  render(<PipelineWalkthrough stage="forecast" />);
  expect(screen.getByRole("img", { name: /intersection in Bellevue, Washington/ }).getAttribute("src")).toMatch(/bellevue\.jpg/);
  expect(screen.getByText(/Bellevue, Washington, USA · 02:32 in the recording/)).toBeTruthy();
  expect(screen.getByText(/detector averages cover 02:34–03:32/)).toBeTruthy();
  expect(screen.getAllByRole("row")).toHaveLength(5);
});

describe("the router", () => {
  it("opens the project preview by default and signs in for operator and account links", () => {
    for (const hash of ["", "#home", "#explore", "#overview", "#live"]) {
      expect(needsSignIn("", hash)).toBe(false);
    }
    expect(needsSignIn("?id=live", "#analyze")).toBe(true);
    expect(needsSignIn("?analysis=recording", "")).toBe(true);
    expect(needsSignIn("", "#reset/sample-token")).toBe(true);
  });

  it("uses bundled data in the preview and keeps its site link in the preview", async () => {
    window.location.hash = "#live";
    render(<Root fetcher={fetchPreview} previewSite={PREVIEW_SITE} />);
    expect((await screen.findByText("Sample")).closest("[data-source]").dataset.source).toBe("sample");
    const sites = await screen.findByRole("navigation", { name: "Intersections" });
    expect(within(sites).getByRole("link").getAttribute("href")).toBe("#live");
    expect((await fetchPreview("/workbench/capabilities", { method: "GET" })).status).toBe(404);
  });

  it("opens the landing page on a bare address, the explorer on #explore, and the console otherwise", () => {
    expect(routeOf("", "")).toEqual({ page: "home" });
    expect(routeOf("#home", "")).toEqual({ page: "home" });
    expect(routeOf("#/home", "")).toEqual({ page: "home" });
    expect(routeOf("#explore", "")).toEqual({ page: "explore", topic: null });
    expect(routeOf("#explore/data-flow", "")).toEqual({ page: "explore", topic: "data-flow" });
    expect(routeOf("#explore/pipeline/forecast", "")).toEqual({ page: "explore", topic: null, stage: "forecast" });
    for (const h of ["#overview", "#live", "#analyze", "#analytics", "#results", "#history", "#nope", "#explorer"]) {
      expect(routeOf(h, "").page).toBe("console");
    }
  });

  it("keeps an operator's address on the console: ?id= or ?analysis= with no hash never shows the landing page", () => {
    expect(routeOf("", "?id=live")).toEqual({ page: "console" });          // the workbench's dashboard_url
    expect(routeOf("", `?analysis=${"a".repeat(64)}`)).toEqual({ page: "console" });
    expect(routeOf("#home", "?id=live")).toEqual({ page: "home" });          // asked for explicitly
  });

  it("polls nothing on the landing page or the explorer, and starts polling only in the console", async () => {
    const fetcher = vi.fn(async () => ({ ok: false, status: 404 }));
    window.location.hash = "";
    render(<Root fetcher={fetcher} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(SITE.title);
    act(() => { window.location.hash = "#explore"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(screen.getByRole("navigation", { name: "Explorer contents" })).toBeTruthy();
    expect(fetcher).not.toHaveBeenCalled();
    act(() => { window.location.hash = "#overview"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(fetcher.mock.calls.every(([, init]) => init.method === "GET")).toBe(true);
  });
});

describe("the landing page", () => {
  it("draws an image-free hero background with four signals and pause and resume controls", () => {
    const { container } = render(<Landing redesign />);
    const scene = container.querySelector("[data-traffic-paused]");
    expect(scene.parentElement).toBe(screen.getByRole("heading", { level: 1 }).closest("section"));
    expect([...scene.querySelectorAll("[data-direction]")].map((track) => track.dataset.direction))
      .toEqual(["east", "west", "north", "south"]);
    for (const track of scene.querySelectorAll("[data-direction]")) {
      const vehicles = [...track.querySelectorAll("[data-vehicle]")];
      expect(vehicles.map(({ dataset }) => dataset.vehicle)).toEqual(["car", "truck", "bike", "car"]);
      expect(vehicles.map((vehicle) => vehicle.parentElement.style.getPropertyValue("--queue-index")))
        .toEqual(["0", "1", "2", "3"]);
    }
    expect(scene.querySelector("img")).toBeNull();
    const signals = [...scene.querySelectorAll("[data-signal]")];
    expect(signals.map((signal) => signal.textContent)).toEqual(["E", "W", "N", "S"]);
    for (const signal of signals) {
      expect([...signal.querySelectorAll("[data-lamp]")].map(({ dataset }) => dataset.lamp))
        .toEqual(["red", "amber", "green"]);
    }
    fireEvent.click(screen.getByRole("button", { name: "Pause traffic animation" }));
    expect(scene.dataset.trafficPaused).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Resume traffic animation" }));
    expect(scene.dataset.trafficPaused).toBe("false");
  });

  it("has the title, the two ways in, and exactly four team cards", () => {
    render(<Landing />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(SITE.title);
    expect(document.querySelector('[data-cta="explore"]').getAttribute("href")).toBe("#explore");
    expect(document.querySelector('[data-cta="launch"]').getAttribute("href")).toBe("#overview");
    const team = screen.getByRole("heading", { name: /The people behind/ }).parentElement;
    expect(team.querySelectorAll("article").length).toBe(4);
  });

  it("invents no team member, photograph or institution: an unfilled entry is a labelled placeholder", () => {
    render(<Landing />);
    const unnamed = SITE.team.filter((m) => !m.name).length;
    expect(document.querySelectorAll('[data-placeholder="team-member"]').length).toBe(unnamed);
    if (!SITE.campusPhoto) expect(document.querySelector('[data-placeholder="campus-photo"]')).toBeTruthy();
    if (!SITE.institution.name) expect(screen.getByText("Institution name to be added")).toBeTruthy();
    // No <img> points at a file that has not been configured.
    expect([...document.querySelectorAll("img")].length).toBe(
      SITE.team.filter((m) => m.photo).length + (SITE.institution.logo ? 1 : 0));
  });

  it("states what is not shown and that signals are not controlled", () => {
    render(<Landing />);
    expect(document.body.textContent).toMatch(/does not control physical signals/);
    expect(document.body.textContent).toMatch(/0\.748/);
    expect(document.body.textContent).toMatch(/Not yet shown/);
  });
});

describe("the project explorer", () => {
  it("opens the dedicated presentation on click and renders every chapter", async () => {
    const fetcher = vi.fn(async () => Response.json([], { status: 404 }));
    render(<Explorer topic="architecture" fetcher={fetcher} />);
    const button = screen.getByRole("button", { name: "Take a Tour" });
    const name = /STMS.*Interactive Project Presentation/;
    expect(screen.queryByRole("dialog", { name })).toBeNull();
    fireEvent.click(button);
    const dialog = await screen.findByRole("dialog", { name });
    const presentation = within(dialog);
    const nav = within(presentation.getByRole("navigation", { name: "Presentation chapters" }));
    const titles = nav.getAllByRole("button").map(button => button.textContent.slice(2));
    expect(titles).toHaveLength(25);
    expect(presentation.getByRole("button", { name: "Previous" }).disabled).toBe(true);
    fireEvent.click(presentation.getByRole("button", { name: "Next" }));
    expect(presentation.getByText("Chapter 2 of 25")).toBeTruthy();
    fireEvent.keyDown(dialog, { key: "ArrowLeft" });
    expect(presentation.getByText("Chapter 1 of 25")).toBeTruthy();
    for (const [index, title] of titles.entries()) {
      fireEvent.click(nav.getByRole("button", { name: title }));
      expect(presentation.getByRole("heading", { name: title, exact: true })).toBeTruthy();
      expect(presentation.getByText(`Chapter ${index + 1} of 25`)).toBeTruthy();
    }
    expect(presentation.getByRole("button", { name: "Explore Freely" }).getAttribute("aria-pressed")).toBe("true");
    expect(presentation.getByRole("link", { name: "Launch STMS Dashboard" }).getAttribute("href")).toBe("#overview");
    expect(presentation.getByRole("link", { name: "Explore Technical Architecture" }).getAttribute("href")).toBe("#explore/architecture");
    fireEvent.click(presentation.getByRole("button", { name: "Finish" }));
    expect(screen.queryByRole("dialog", { name })).toBeNull();
    expect(screen.getByRole("heading", { name: "System architecture", level: 1 })).toBeTruthy();
    fireEvent.click(button);
    const reopened = await screen.findByRole("dialog", { name });
    expect(within(reopened).getByText("Chapter 1 of 25")).toBeTruthy();
    fireEvent.keyDown(reopened, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name })).toBeNull();
    expect(fetcher.mock.calls.every(([url, options]) => url === "/workbench/jobs" && options.method === "GET")).toBe(true);
  });

  it("explains verified evidence and updates the interactive examples", async () => {
    render(<Explorer />);
    fireEvent.click(screen.getByRole("button", { name: "Take a Tour" }));
    const presentation = within(await screen.findByRole("dialog", { name: /Interactive Project Presentation/ }));
    const choose = index => fireEvent.change(presentation.getByLabelText("Go to chapter"), { target: { value: index - 1 } });
    choose(5);
    fireEvent.click(presentation.getByRole("button", { name: "Tracking" }));
    expect(presentation.getByText(/ByteTrack links boxes across nearby frames/)).toBeTruthy();
    choose(10);
    const savedFrame = within(presentation.getByRole("region", { name: "Saved Bellevue detection frame" }));
    const detections = savedFrame.getAllByRole("button", { name: /Detection [0-9]/ }).length;
    fireEvent.change(savedFrame.getByLabelText("Minimum confidence"), { target: { value: "0.7" } });
    expect(savedFrame.queryAllByRole("button", { name: /Detection [0-9]/ }).length).toBeLessThan(detections);
    choose(11);
    fireEvent.change(presentation.getByRole("slider", { name: "Move the vehicle through the frames" }), { target: { value: "3" } });
    expect(presentation.getByText(/Inbound count 1/)).toBeTruthy();
    choose(17);
    fireEvent.change(presentation.getByRole("slider", { name: "East demand" }), { target: { value: "18" } });
    expect(presentation.getByText(/East green/)).toBeTruthy();
    fireEvent.click(presentation.getByRole("button", { name: "Advance to next signal" }));
    expect(presentation.getByText(/East yellow/)).toBeTruthy();
    choose(23);
    expect(presentation.getByText(/0.748 vehicles/)).toBeTruthy();
    expect(presentation.getByText(/0.972 vehicles/)).toBeTruthy();
    expect(presentation.getByText(/no demonstrated control benefit from forecasts/)).toBeTruthy();
  });

  it("lists every topic once, in order, and opens the first for an unknown topic", () => {
    render(<Explorer topic="nope" />);
    const links = within(screen.getByRole("navigation", { name: "Explorer contents" })).getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual(TOPICS.map((t) => `#explore/${t.id}`));
    expect(new Set(TOPICS.map((t) => t.id)).size).toBe(TOPICS.length);
    expect(TOPICS.length).toBe(24);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(TOPICS[0].title);
    expect(topicIndex(null)).toBe(0);
  });

  it("answers the six questions on every topic, draws its figure, and links back and forward", () => {
    for (const [i, t] of TOPICS.entries()) {
      render(<Explorer topic={t.id} />);
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(t.title);
      for (const key of ["what", "why", "use", "inside", "where", "output"]) expect(typeof t[key] === "string" && t[key].length > 0).toBe(true);
      expect(document.querySelectorAll("main > div > details").length).toBe(6);
      if (t.visual) expect(document.querySelector(`[data-figure="${t.visual}"]`)).toBeTruthy();
      const pager = within(screen.getByRole("navigation", { name: "Previous and next topic" })).getAllByRole("link");
      expect(pager[0].getAttribute("href")).toBe(i === 0 ? "#home" : `#explore/${TOPICS[i - 1].id}`);
      expect(pager[1].getAttribute("href")).toBe(i === TOPICS.length - 1 ? "#overview" : `#explore/${TOPICS[i + 1].id}`);
      cleanup();
    }
  });

  it("marks a visited topic as seen and counts progress", () => {
    try { window.localStorage.clear(); } catch { /* none */ }
    const { rerender } = render(<Explorer topic={TOPICS[0].id} />);
    rerender(<Explorer topic={TOPICS[1].id} />);
    expect(screen.getByText(`2 of ${TOPICS.length} topics visited`)).toBeTruthy();
    expect(document.querySelector('[role="progressbar"]').getAttribute("aria-valuenow")).toBe("2");
  });

  it("classes a mean count with the camera's own thresholds in the levels figure, and says the class in words", () => {
    render(<Explorer topic="congestion" />);
    const slider = screen.getByRole("slider");
    for (const [v, level] of [["0", "LOW"], ["0.5", "MEDIUM"], ["2", "HIGH"]]) {
      fireEvent.change(slider, { target: { value: v } });
      expect(document.querySelector('[data-figure="levels"]').textContent).toMatch(new RegExp(`next 60 s: ${level}`));
    }
  });

  it("shows the role of whichever architecture block is clicked", () => {
    render(<Explorer topic="architecture" />);
    fireEvent.click(screen.getByRole("button", { name: "MQTT broker" }));
    expect(screen.getByRole("button", { name: "MQTT broker" }).getAttribute("aria-pressed")).toBe("true");
    expect(document.querySelector('[data-figure="architecture"] aside').textContent).toMatch(/contracts\/mqtt\.py/);
  });

  it("never claims signal control is deployed", () => {
    const signals = TOPICS.find((t) => t.id === "signals");
    expect(signals.status).toBe("sim");
    expect(`${signals.summary} ${signals.use}`).toMatch(/no forecast reaches a real signal|reaches no signal/);
  });
});

describe("the console's Overview", () => {
  const lanes = (rows) => ok({ intersection_id: "j1", lanes: rows, pcu: { weights: { car: 1 }, assumed: [], source: "x" } });
  const lane = (count, stale = false) => ({ count, types: { car: count }, fps: 1, age_s: stale ? 30 : 1, stale });

  it("sums only current lanes, and never turns missing or old counts into a number", () => {
    expect(vehiclesNow({ status: "loading" })).toMatchObject({ value: null, text: "Waiting" });
    expect(vehiclesNow({ status: "unavailable" })).toMatchObject({ value: null, text: "None yet" });
    expect(vehiclesNow({ status: "error", reason: "x" })).toMatchObject({ value: null, text: "Unknown" });
    expect(vehiclesNow(ok({ lanes: "bad" }))).toMatchObject({ value: null, text: "Invalid" });
    expect(vehiclesNow(lanes({ lane_0: lane(3), lane_1: lane(4) }))).toMatchObject({ value: 7 });
    expect(vehiclesNow(lanes({ lane_0: lane(3), lane_1: lane(9, true) })).value).toBe(3);
    expect(vehiclesNow(lanes({ lane_0: lane(3, true) }))).toMatchObject({ value: null, text: "Out of date" });
    expect(vehiclesNow(lanes({ lane_0: lane(0) })).value).toBe(0);   // a real zero stays a zero
  });

  it("updates the approach details from the selected road and its mapped counts", async () => {
    window.location.hash = "#overview";
    render(<Root fetcher={fetchPreview} previewSite={PREVIEW_SITE} />);
    fireEvent.click(await screen.findByRole("button", { name: "N approach" }));
    const details = await screen.findByRole("region", { name: "Approach N details" });
    await waitFor(() => expect(within(details).getByText("3")).toBeTruthy());
    expect(within(details).getByText("3.2 veh")).toBeTruthy();
    expect(within(details).getByRole("list", { name: /congestion forecast trend/i })).toBeTruthy();
    const ops = screen.getByRole("group", { name: "Operations status" });
    const alertLink = await within(ops).findByRole("link", { name: "Inspect approach E", hidden: true });
    expect(alertLink.getAttribute("href")).toBe("#overview/E");
    window.location.hash = alertLink.getAttribute("href");
    expect(await screen.findByRole("region", { name: "Approach E details" })).toBeTruthy();
    expect(screen.queryByText("Detector FPS")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Engineering" }));
    expect(screen.getByText("Detector FPS")).toBeTruthy();
    expect(screen.getByText("ridge@000000000000")).toBeTruthy();
  });
});

describe("the theme switch (Dark / System / Light)", () => {
  const root = document.documentElement;
  afterEach(() => { delete root.dataset.theme; try { window.localStorage.removeItem("stms.theme"); } catch { /* none */ } });

  it("offers the three choices, and System is the default", () => {
    render(<ThemeSwitch />);
    const buttons = within(screen.getByRole("group", { name: "Colour theme" })).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Dark", "System", "Light"]);
    expect(document.querySelector('[data-theme-choice="system"]').getAttribute("aria-pressed")).toBe("true");
    expect(root.dataset.theme).toBeUndefined();
  });

  it("sets Dark or Light on the page, leaves System to the computer, and remembers the choice", () => {
    render(<ThemeSwitch />);
    fireEvent.click(document.querySelector('[data-theme-choice="light"]'));
    expect(root.dataset.theme).toBe("light");
    expect(storedTheme()).toBe("light");
    fireEvent.click(document.querySelector('[data-theme-choice="dark"]'));
    expect(root.dataset.theme).toBe("dark");
    fireEvent.click(document.querySelector('[data-theme-choice="system"]'));
    expect(root.dataset.theme).toBeUndefined();
    expect(storedTheme()).toBe("system");
  });

  it("ignores a stored value it does not know", () => {
    window.localStorage.setItem("stms.theme", "neon");
    expect(storedTheme()).toBe("system");
  });

  it("renders the same text in every theme: a theme never changes meaning (D18)", () => {
    const text = (choice) => { applyTheme(choice); const { container } = render(<Landing />); const t = container.textContent; cleanup(); return t; };
    const dark = text("dark");
    expect(text("light")).toBe(dark);
    expect(text("system")).toBe(dark);
  });
});
