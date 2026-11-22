export const SAMPLE_INTERVAL = 15;
export const FORECAST_HORIZON = 60;
export const APPROACH_NAMES = { N: "North", E: "East", S: "South", W: "West" };
export const APPROACHES = Object.keys(APPROACH_NAMES);

// Illustrative snapshots, one per 15 seconds. A null snapshot is a camera gap.
const COUNTS = [
  [4, 6, 2, 3], [5, 6, 3, 3], [5, 7, 3, 4], [6, 8, 4, 4],
  [7, 11, 4, 5], [7, 14, 5, 5], [8, 17, 5, 6], [9, 19, 6, 6],
  [8, 22, 6, 7], [9, 20, 6, 7], null, null, null, null, null, null,
  [8, 12, 4, 5], [7, 11, 4, 4], [6, 9, 4, 4], [6, 8, 3, 3], [5, 7, 3, 3],
];

export const DEMO_LENGTH = (COUNTS.length - 1) * SAMPLE_INTERVAL;
export const CHAPTERS = [
  { at: 0, name: "Steady traffic", note: "Select an approach to inspect its count and forecast." },
  { at: 60, name: "Traffic builds", note: "Counts rise on the east approach. Compare the observed count with the next-minute forecast." },
  { at: 150, name: "Camera feed drops", note: "The chart leaves a gap in observations. The last forecast ages while the feed is silent." },
  { at: 240, name: "Feed recovers", note: "New counts and forecasts appear. The gap stays visible in the history." },
];
export const GUIDED_CHAPTERS = CHAPTERS.slice(1);

const WINDOW = FORECAST_HORIZON / SAMPLE_INTERVAL;
const round = (value) => Math.round(value * 10) / 10;

function estimate(values, index, lane) {
  const current = values[index][lane];
  const previous = values[index - 1]?.[lane] ?? current;
  return round(Math.max(0, current + (current - previous) * 1.2));
}

export const SAMPLE_FRAMES = COUNTS.map((counts, index) => ({
  at: index * SAMPLE_INTERVAL,
  counts,
  forecasts: counts?.map((_, lane) => estimate(COUNTS, index, lane)) ?? null,
}));

export function replayAt(seconds) {
  const index = Math.floor(seconds / SAMPLE_INTERVAL);
  const last = SAMPLE_FRAMES.slice(0, index + 1).findLast((frame) => frame.counts !== null);
  return {
    last,
    age: seconds - last.at,
    online: SAMPLE_FRAMES[index].counts !== null,
    chapter: CHAPTERS.findLast((chapter) => chapter.at <= seconds),
  };
}

export function forecastLevel(value) {
  if (value >= 13) return "HIGH";
  if (value >= 7) return "MEDIUM";
  return "LOW";
}

export function comparisonAt(playhead, lane) {
  return SAMPLE_FRAMES.map(({ at }, index) => {
    const issue = SAMPLE_FRAMES[index - WINDOW];
    const counted = COUNTS.slice(Math.max(0, index - WINDOW + 1), index + 1);
    const complete = at <= playhead && index >= WINDOW && counted.every(Boolean);
    return {
      at,
      observed: complete ? round(counted.reduce((sum, frame) => sum + frame[lane], 0) / WINDOW) : null,
      forecast: issue?.at <= playhead ? issue.forecasts?.[lane] ?? null : null,
      issuedAt: issue?.at ?? null,
    };
  });
}

export function replayTime(seconds) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
