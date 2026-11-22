import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import App from "./App.jsx";

afterEach(() => {
  cleanup();
  window.location.hash = "";
  window.localStorage.removeItem("stms.offlineAnalysisId");
  vi.unstubAllGlobals();
});

const key = "a".repeat(64);
const job = { id: "recording-1", filename: "traffic.mp4", status: "Completed", result_key: key,
  started_at: "2026-11-20T10:00:00Z", finished_at: "2026-11-20T10:01:00Z", alert_statuses: {} };
const result = {
  kind: "stms-video-analysis", schema: 2, clip: "traffic", camera: "demo", step_s: 2, duration_s: 2,
  pcu: { weights: { car: 1 }, assumed: [], source: "test" },
  min_confidence: .45, limits: { low: 1, med: 2 }, directions_verified: false, known_limits: [],
  lanes: [{ name: "lane_0", centre: [.4, .5], approach: "N" }],
  samples: [{ t: 0, counts: { lane_0: 1 }, boxes: [[.4, .4, .5, .5]], detections: [["car", .9, "lane_0"]],
    track_ids: [1], level: null, number: null, then: null }],
  processing: { filename: "traffic.mp4", resolution: [1280, 720], seconds: 1, frames: 8, fps: 8,
    model: "yolo11n.pt", tracker: "ByteTrack", supported_classes: ["car"], source_size: 2000 },
  traffic: { lines: [], by_type: { car: 1, motorcycle: 0, bus: 0, truck: 0 }, average_visible: 1,
    policy: { greens: [15, 30, 45, 60], previous_green: 30, yellow: 4, all_red: 2 },
    windows: [{ t: 0, end: 2, visible: 1, crossings: 1, level: "Low", green: { N: 30 }, approaches: { N: 1 } }],
    crossings: [{ t: .5, track_id: 1, type: "car", approach: "N" }],
    alerts: [{ id: "stopped:0:1", t: 0, type: "Possible stopped vehicle", severity: "Warning", reason: "Track evidence" }] },
};

it("opens without old data and loads saved analysis only after the user chooses it", async () => {
  const fetcher = vi.fn(async (url) => {
    const replies = {
      "/workbench/capabilities": { workbench: true, history: true, analysis_ready: true },
      "/workbench/jobs": [job], [`/workbench/analysis/${key}`]: result,
      "/workbench/cameras": [],
    };
    return { ok: url in replies, status: url in replies ? 200 : 404, json: async () => replies[url] };
  });
  window.location.hash = "#overview";
  render(<App previewSite="test-fixture" fetcher={fetcher} />);
  const nav = screen.getByRole("navigation", { name: "Sections" });
  const browse = await screen.findByRole("button", { name: "Browse saved sessions" });
  expect(screen.queryByText("Unique inbound crossings")).toBeNull();
  expect(screen.queryByText(job.filename)).toBeNull();
  expect(fetcher.mock.calls.some(([url]) => url === "/workbench/jobs" || url.startsWith("/workbench/analysis/") ||
    url.startsWith("/count_forecast/"))).toBe(false);
  fireEvent.click(browse);
  expect(await screen.findByText(job.filename)).toBeTruthy();
  expect(fetcher.mock.calls.some(([url]) => url.startsWith("/workbench/analysis/"))).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "View" }));
  expect(await screen.findByText("Unique inbound crossings")).toBeTruthy();
  expect(screen.queryByText(/Bundled traffic data/i)).toBeNull();

  fireEvent.click(within(nav).getByRole("link", { name: "Signal timing" }));
  expect(await screen.findByText("Simulated phase")).toBeTruthy();
  fireEvent.click(within(nav).getByRole("link", { name: "Alerts" }));
  expect(await screen.findByText("Track evidence")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /replay evidence/i }));
  expect(await screen.findByRole("heading", { name: "Guided replay" })).toBeTruthy();
  expect(screen.getByText("A saved video appears here when its session is selected.")).toBeTruthy();
  expect(document.querySelector("[data-box-class]")).toBeNull();

  fireEvent.click(within(nav).getByRole("link", { name: "Results" }));
  expect(await screen.findByText("Report and processing details")).toBeTruthy();
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  fireEvent.click(screen.getByRole("button", { name: "Save report as PDF" }));
  expect(print).toHaveBeenCalledOnce();
  fireEvent(window, new Event("afterprint"));
  print.mockRestore();
});

it("restores an offline report on Results and separates New Analysis from confirmed Reset", async () => {
  vi.stubGlobal("URL", class extends URL {
    static createObjectURL() { return "blob:traffic"; }
    static revokeObjectURL() {}
  });
  const offlineJob = { ...job, mode: "offline", metrics: { crossings: 1, density: "Low", green: { N: 30 } } };
  const liveJob = { ...job, id: "live-1", filename: "live.mp4", mode: "demo" };
  let list = [offlineJob, liveJob];
  const fetcher = vi.fn(async (url) => {
    const replies = {
      "/workbench/capabilities": { workbench: true, history: true, uploads: true, manage_history: true, analysis_ready: true },
      "/workbench/jobs": list, [`/workbench/analysis/${key}`]: result,
      "/workbench/cameras": [], "/workbench/history/new": { ready: true },
      "/workbench/history/reset": { deleted: 1 },
    };
    if (url === "/workbench/history/reset") list = [liveJob];
    return { ok: url in replies, status: url in replies ? 200 : 404, json: async () => replies[url] };
  });
  window.location.hash = "#results";
  const first = render(<App previewSite="test-fixture" fetcher={fetcher} />);
  expect(await screen.findByRole("heading", { name: "Analysis history" })).toBeTruthy();
  expect(screen.queryByText("live.mp4")).toBeNull();
  fireEvent.click(await screen.findByRole("button", { name: "View Results" }));
  expect(await screen.findByText("Report and processing details")).toBeTruthy();
  expect(window.localStorage.getItem("stms.offlineAnalysisId")).toBe(job.id);
  first.unmount();

  render(<App previewSite="test-fixture" fetcher={fetcher} />);
  expect(await screen.findByText("Report and processing details")).toBeTruthy();
  const nav = screen.getByRole("navigation", { name: "Sections" });
  fireEvent.click(within(nav).getByRole("link", { name: "Analyze a video" }));
  const newAnalysis = await screen.findByRole("button", { name: "New Analysis" });
  const input = document.querySelector("[data-open-video]");
  fireEvent.change(input, { target: { files: [new File(["recording"], "other.mp4", { type: "video/mp4" })] } });
  expect(await screen.findAllByText("other.mp4")).not.toHaveLength(0);
  fireEvent.click(newAnalysis);
  expect(await screen.findByText("Choose a video, or drop it here")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reset All Analysis Data" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
  expect(fetcher.mock.calls.some(([path]) => path === "/workbench/history/reset")).toBe(false);
  fireEvent.click(within(nav).getByRole("link", { name: "Results" }));
  expect(await screen.findByRole("button", { name: "View Results" })).toBeTruthy();

  fireEvent.click(within(nav).getByRole("link", { name: "Analyze a video" }));
  fireEvent.click(await screen.findByRole("button", { name: "Reset All Analysis Data" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete All Results & Restart" }));
  fireEvent.click(within(nav).getByRole("link", { name: "Results" }));
  expect(await screen.findByText("No saved sessions.")).toBeTruthy();
  expect(window.localStorage.getItem("stms.offlineAnalysisId")).toBeNull();
});
