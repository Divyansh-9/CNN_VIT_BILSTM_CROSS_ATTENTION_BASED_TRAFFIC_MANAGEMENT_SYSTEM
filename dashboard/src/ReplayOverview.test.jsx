import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PipelineWalkthrough } from "./PipelineWalkthrough.jsx";
import { ReplayOverview } from "./ReplayOverview.jsx";
import { comparisonAt } from "./replaySample.js";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

it("selects approaches and handles the silent, expired, and recovered replay states", () => {
  render(<ReplayOverview />);
  fireEvent.click(screen.getByRole("button", { name: "North approach" }));
  expect(screen.getByRole("heading", { name: "North approach" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "North approach" }).getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByRole("button", { name: /Camera feed drops/ }));
  expect(screen.getByText("Feed silent")).toBeTruthy();
  expect(screen.getByText("No update")).toBeTruthy();
  fireEvent.change(screen.getByRole("slider", { name: "Replay position" }), { target: { value: 210 } });
  expect(screen.getByText("Expired forecast")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Feed recovers/ }));
  expect(screen.getByText("Feed reporting")).toBeTruthy();
  expect(screen.queryByText("Expired forecast")).toBeNull();
});

it("plays at the chosen speed, pauses, and restarts from the end", () => {
  vi.useFakeTimers();
  render(<ReplayOverview />);
  const position = screen.getByRole("slider", { name: "Replay position" });
  fireEvent.change(screen.getByRole("combobox", { name: "Speed" }), { target: { value: "8" } });
  fireEvent.click(screen.getByRole("button", { name: "Play" }));
  act(() => vi.advanceTimersByTime(1000));
  expect(position.value).toBe("128");
  fireEvent.click(screen.getByRole("button", { name: "Pause" }));
  act(() => vi.advanceTimersByTime(1000));
  expect(position.value).toBe("128");
  fireEvent.change(position, { target: { value: "300" } });
  fireEvent.click(screen.getByRole("button", { name: "Replay" }));
  expect(position.value).toBe("0");
});

it("aligns forecasts with their target window and leaves gaps for unavailable observations", () => {
  const east = 1;
  const rows = comparisonAt(120, east);
  expect(rows.find(({ at }) => at === 120)).toEqual({ at: 120, observed: 18, forecast: 14.6, issuedAt: 60 });
  expect(rows.find(({ at }) => at === 180)).toEqual({ at: 180, observed: null, forecast: 25.6, issuedAt: 120 });
  expect(comparisonAt(240, east).find(({ at }) => at === 195).observed).toBeNull();
});

it("links to each technical stage and reveals its input and output", () => {
  const { rerender } = render(<PipelineWalkthrough />);
  const steps = within(screen.getByRole("list", { name: "Pipeline steps" }));
  expect(steps.getAllByRole("link")).toHaveLength(5);
  expect(steps.getByRole("link", { name: "Forecast" }).getAttribute("href")).toBe("#explore/pipeline/forecast");
  rerender(<PipelineWalkthrough stage="forecast" />);
  expect(screen.getByText("Recent lane counts and congestion levels")).toBeTruthy();
  expect(screen.getByText(/Expected mean vehicles/)).toBeTruthy();
  rerender(<PipelineWalkthrough stage="dashboard" />);
  expect(screen.getByRole("link", { name: "Try the guided replay" }).getAttribute("href")).toBe("#replay");
});
