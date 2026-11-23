import { useRef } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { RegionOverlay, TrafficRegions, useTrafficRegions } from "./TrafficRegions.jsx";

afterEach(cleanup);

function Player() {
  const region = useTrafficRegions();
  const stage = useRef(null);
  return <>
    <div ref={stage} aria-label="Recording picture" onClick={e => region.updateDraft(e, stage.current)}>
      <RegionOverlay region={region} />
    </div>
    <TrafficRegions region={region} live={false} time={0} pause={() => {}} />
  </>;
}

it("draws a region, adds a finite line and can remove the region", () => {
  const { container } = render(<Player />);
  const stage = screen.getByLabelText("Recording picture");
  stage.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100 });
  fireEvent.click(screen.getByText("Custom regions and counting lines"));
  fireEvent.click(screen.getByRole("button", { name: "Draw region" }));
  for (const [clientX, clientY] of [[10, 10], [85, 10], [85, 85], [10, 85]]) {
    fireEvent.click(stage, { clientX, clientY });
  }
  fireEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(container.querySelector("polygon")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Draw counting line" }));
  fireEvent.click(stage, { clientX: 50, clientY: 20 });
  fireEvent.click(stage, { clientX: 50, clientY: 70 });
  fireEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(container.querySelector("line")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Remove region" }));
  expect(container.querySelector("polygon")).toBeNull();
});
