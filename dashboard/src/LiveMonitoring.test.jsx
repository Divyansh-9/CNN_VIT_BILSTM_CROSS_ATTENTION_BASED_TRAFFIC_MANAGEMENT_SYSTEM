import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LiveMonitoring, monitoringPrefix, simulatedPhase } from "./LiveMonitoring.jsx";
import { LiveSignals, OfflineSignals } from "./AdaptiveSignals.jsx";
import { recordingCamera } from "./LiveRecordingSession.jsx";
import * as ops from "./ops.js";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("opens the browser file picker and then the camera form without a workbench", () => {
  vi.stubGlobal("URL", class extends URL {
    static createObjectURL() { return "blob:demo-clip"; }
    static revokeObjectURL() {}
  });
  render(<LiveMonitoring workbench={false} active onProgress={() => {}} onSaved={() => {}} />);
  const sources = within(screen.getByRole("group", { name: "Monitoring source" }));
  const demoButton = sources.getByRole("button", { name: /Demo Live/, pressed: true });
  const cameraButton = sources.getByRole("button", { name: "Real Live Camera / Server", pressed: false });
  const demo = screen.getByRole("region", { name: "Demo Live video preview" });
  const input = within(demo).getByLabelText(/Choose a video/);
  fireEvent.change(input, { target: { files: [new File(["recording"], "traffic.mp4", { type: "video/mp4" })] } });
  expect(demo.querySelector("video").getAttribute("src")).toBe("blob:demo-clip");
  expect(within(demo).getByText("traffic.mp4")).toBeTruthy();

  fireEvent.click(cameraButton);
  expect(cameraButton.getAttribute("aria-pressed")).toBe("true");
  expect(demoButton.getAttribute("aria-pressed")).toBe("false");
  const camera = screen.getByRole("region", { name: "Browser camera preview" });
  const url = within(camera).getByLabelText("HTTPS video stream");
  fireEvent.change(url, { target: { value: "rtsp://example.com/camera" } });
  fireEvent.click(within(camera).getByRole("button", { name: "Connect stream" }));
  expect(within(camera).getByText(/For RTSP, HTTP/)).toBeTruthy();
  fireEvent.change(url, { target: { value: "https://example.com/camera.mp4" } });
  fireEvent.click(within(camera).getByRole("button", { name: "Connect stream" }));
  expect(within(camera).getByLabelText("Camera preview").getAttribute("src")).toBe("https://example.com/camera.mp4");
  fireEvent.click(within(camera).getByRole("button", { name: "Disconnect" }));
  expect(within(camera).queryByLabelText("Camera preview")).toBeNull();
  fireEvent.click(demoButton);
  expect(demoButton.getAttribute("aria-pressed")).toBe("true");
  expect(cameraButton.getAttribute("aria-pressed")).toBe("false");
});

it("starts a mapped streaming job from the file alone and stops only that session", async () => {
  vi.stubGlobal("URL", class extends URL {
    static createObjectURL() { return "blob:live-source"; }
    static revokeObjectURL() {}
  });
  const camera = "Bellevue_116th_NE12th";
  const jobId = "f".repeat(32);
  const fetcher = vi.fn(async (path) => new Response(JSON.stringify({
    "/workbench/cameras": [{ id: camera }],
    "/workbench/upload": { recording: 1 },
    "/workbench/jobs": { job_id: jobId },
    "/workbench/jobs/current": { job_id: "a".repeat(32), running: true },
    "/workbench/jobs/current?mode=live": { job_id: jobId, running: true },
    [`/workbench/monitor/demo/${jobId}?offset=0`]: { items: [], next: 0 },
    "/workbench/jobs/stop": { stopping: true },
  }[path]), { headers: { "content-type": "application/json" } }));
  render(<LiveMonitoring workbench={{ monitoring: true, streaming_demo: true, parallel_analysis: true, analysis_ready: true, minimum_duration_s: 2 }}
    fetcher={fetcher} active onProgress={() => {}} onSaved={() => {}} />);
  const demo = screen.getByRole("region", { name: "Demo Live monitoring player" });
  expect(within(demo).getByText("Upload Traffic Video for Live Monitoring")).toBeTruthy();
  fireEvent.change(within(demo).getByLabelText(/Choose a video/), {
    target: { files: [new File(["recording"], camera + "__morning.mp4", { type: "video/mp4" })] },
  });
  const video = demo.querySelector("video");
  Object.defineProperty(video, "duration", { value: 32 });
  fireEvent.loadedMetadata(video);
  await waitFor(() => expect(fetcher.mock.calls.some(([path, options]) => path === "/workbench/jobs" &&
    JSON.parse(options.body).camera === camera && JSON.parse(options.body).monitoring)).toBe(true));
  await waitFor(() => expect(fetcher.mock.calls.some(([path]) => path === "/workbench/jobs/current?mode=live")).toBe(true));
  expect(fetcher.mock.calls.some(([path]) => path === "/workbench/jobs/current")).toBe(false);
  expect(within(demo).queryByText("Upload Traffic Video for Live Monitoring")).toBeNull();
  expect(within(demo).queryByRole("button", { name: /analyze|start live/i })).toBeNull();
  expect(within(demo).queryByText(/results file/i)).toBeNull();
  fireEvent.click(within(demo).getByRole("button", { name: "Stop" }));
  await waitFor(() => expect(fetcher.mock.calls.some(([path, options]) => path === "/workbench/jobs/stop" &&
    JSON.parse(options.body).job_id === jobId)).toBe(true));
  expect(within(demo).getByText("Browse Video")).toBeTruthy();
  expect(recordingCamera("unrelated.mp4", [{ id: camera }], "")).toBe("whole-frame");
});

it("reveals only crossings, alerts and forecasts reached on the video clock", () => {
  const result = {
    lanes: [{ name: "lane_0", approach: "N" }],
    samples: [{ t: 0, counts: { lane_0: 0 }, number: null, then: { N: { number: 9 } } },
      { t: 2, counts: { lane_0: 2 }, number: { N: 1 } },
      { t: 4, counts: { lane_0: 15 }, number: { N: 5 } }],
    traffic: { by_type: { car: 2 }, crossings: [{ t: 2, type: "car" }, { t: 4, type: "car" }],
      alerts: [{ id: "a", t: 4 }], policy: { density: [3, 6, 10], lane_demand: [1, 3, 5], greens: [15, 30, 45, 60] } },
  };
  const first = monitoringPrefix(result, 1);
  expect(first.samples.at(-1)).toMatchObject({ number: null, then: null });
  expect(first.traffic.crossings).toHaveLength(0);
  expect(first.traffic.alerts).toHaveLength(0);
  expect(first.traffic.windows[0].green.N).toBe(15);
  const second = monitoringPrefix(result, 2.3);
  expect(second.traffic.by_type.car).toBe(1);
  expect(second.traffic.average_visible).toBe(1);
  expect(second.traffic.windows[0].green.N).toBe(30);
  expect(second.traffic.alerts).toHaveLength(0);
  expect(monitoringPrefix(result, 4).traffic.alerts).toHaveLength(1);
  expect(monitoringPrefix(result, 0).traffic.by_type.car).toBe(0);
  const early = { as_of: 0 }, late = { as_of: 4 };
  result.samples[0].signal = early;
  result.samples[2].signal = late;
  result.traffic.signal_schedule = { mode: "offline" };
  const before = monitoringPrefix(result, 3.9);
  expect(before.samples[0].signal).toEqual(early);
  expect(before.samples.some(row => row.signal === late)).toBe(false);
  expect(before.traffic.signal_schedule).toBeUndefined();
});

it("shows causal predictions during playback and inspects offline clearance intervals separately", () => {
  const make = (phase, start) => ({ phase, start, approaches: [phase], visible: 7, green_s: 15,
    green_end: start + 15, yellow_end: start + 19, end: start + 21, red_wait_s: start, reason: "7 vehicles in view" });
  const phase = make("N", 0), next = make("E", 21), last = make("N", 42);
  const signal = { phase, as_of: 12, next_locked: false, upcoming: [next, last, make("E", 63)],
    measurements: { N: { visible: 7, inbound_per_min: null }, E: { visible: 0, inbound_per_min: 0 } } };
  const { rerender } = render(<LiveSignals signal={signal} elapsed={13} samples={[]} policy={{ lane_demand: [1, 3, 5] }} />);
  expect(screen.getByText("2 s remaining")).toBeTruthy();
  expect(screen.getByText(/Starts at 0:21 · in 8 s/)).toBeTruthy();
  rerender(<OfflineSignals schedule={{ phases: [phase, next], max_red_s: 100 }} result={{ clip: "queue" }} />);
  fireEvent.change(screen.getByRole("slider"), { target: { value: 19 } });
  expect(screen.getByText(/All red · 7 vehicles/)).toBeTruthy();
  const download = vi.spyOn(ops, "downloadText").mockImplementation(() => {});
  fireEvent.click(screen.getByRole("button", { name: "Download signal schedule CSV" }));
  expect(download.mock.calls[0][0]).toBe("queue.signal-schedule.csv");
  expect(download.mock.calls[0][1]).toContain('"N","N","0","15","19","21","15","7","0","7 vehicles in view"');
  expect(download.mock.calls[0][1]).toContain('"E","E","21","36","40","42","15","7","21","7 vehicles in view"');
});

it("keeps yellow and all-red clearances between adaptive phases", () => {
  const traffic = { windows: [{ t: 0, end: 30, green: { N: 60, E: 45 } }],
    policy: { previous_green: 30, yellow: 4, all_red: 2 } };
  expect(simulatedPhase(traffic, 29)).toEqual({ label: "N green", remaining: 1 });
  expect(simulatedPhase(traffic, 31)).toEqual({ label: "Yellow clearance", remaining: 3 });
  expect(simulatedPhase(traffic, 34)).toEqual({ label: "All red clearance", remaining: 2 });
  expect(simulatedPhase(traffic, 36)).toEqual({ label: "E green", remaining: 45 });
  traffic.windows.push({ t: 30, end: 36, green: { N: 15, E: 15 } });
  expect(simulatedPhase(traffic, 36)).toEqual({ label: "E green", remaining: 45 });
});
