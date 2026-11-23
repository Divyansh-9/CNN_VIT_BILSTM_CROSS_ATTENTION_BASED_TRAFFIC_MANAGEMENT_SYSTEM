import { describe, expect, it } from "vitest";
import { crossing, inside, movementCandidates, regionMetrics } from "./trafficRegions.js";

const polygon = [[.1,.1], [.9,.1], [.9,.9], [.1,.9]];
const line = [[.5,.3], [.5,.7]];
const row = (t, points) => ({
  t, boxes: points.map(([x,y]) => [x-.01,y-.01,x+.01,y+.01]),
  detections: points.map(() => ["car", .75]),
  track_ids: points.map((_, i) => i + 1),
});

describe("custom traffic regions", () => {
  it("respects finite lines and only counts a confirmed track once", () => {
    expect(inside([.5,.5], polygon)).toBe(true);
    expect(crossing([.4,.2], [.6,.2], line)).toBe(0);
    const rows = [row(0, [[.4,.5]]), row(2, [[.6,.5]]), row(4, [[.4,.5]]), row(6, [[.6,.5]])];
    const measurements = regionMetrics(rows, .4, { polygon, line }, 0, [1,3,6]);
    expect(measurements).toMatchObject({ tracks: 1, crossings: 1, occupancy: 1, rate: 10 });
    expect(regionMetrics(rows.slice(0, 2), .4, { polygon, line }, 1).crossings).toBe(0);
    expect(regionMetrics([rows[0], rows[3]], .4, { polygon, line }, 0).crossings).toBe(0);
  });

  it("gives proposals only after a multi-vehicle direction cluster", () => {
    const first = [[.2,.24], [.2,.34], [.2,.44], [.2,.54]];
    const second = first.map(([x,y]) => [x+.1,y]);
    expect(movementCandidates([row(0,first.slice(0,3)), row(2,second.slice(0,3))], .4)).toEqual([]);
    expect(movementCandidates([row(0,first), row(2,second)], .4)).toMatchObject([{ tracks: 4 }]);
  });
});
