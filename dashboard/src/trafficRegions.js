const STEP = 2;
const RECENT = 15;
const center = ([x1, y1, x2, y2]) => [(x1 + x2) / 2, (y1 + y2) / 2];
const vector = (a, b) => [b[0] - a[0], b[1] - a[1]];
const cross = (a, b) => a[0] * b[1] - a[1] * b[0];
const mean = values => values.reduce((sum, n) => sum + n, 0) / values.length;

export function inside(point, polygon) {
  const [x, y] = point;
  let contained = false;
  for (let index = 0; index < polygon.length; index += 1) {
    const [ax, ay] = polygon[index];
    const [bx, by] = polygon[(index + 1) % polygon.length];
    if ((ay > y) !== (by > y) && x < ax + (bx - ax) * (y - ay) / (by - ay)) contained = !contained;
  }
  return contained;
}

export function crossing(from, to, [start, end]) {
  const line = vector(start, end);
  const origin = vector(start, from);
  const first = cross(line, origin);
  const second = cross(line, vector(start, to));
  if (first === 0 || first * second > 0 || first === second) return 0;
  const position = first / (first - second);
  const movement = vector(from, to);
  const relative = origin.map((value, index) => value + movement[index] * position);
  const along = (line[0] * relative[0] + line[1] * relative[1]) / (line[0] ** 2 + line[1] ** 2);
  return along >= 0 && along <= 1 ? Math.sign(second - first) : 0;
}

function detections(row, minimum) {
  return row.boxes.flatMap((box, index) => row.detections?.[index]?.[1] >= minimum
    ? [{ point: center(box), id: row.track_ids?.[index] }] : []);
}

function consecutive(previous, row, point) {
  return previous?.t + STEP === row.t
    && Math.hypot(...vector(previous.point, point)) <= .35;
}

export function regionMetrics(samples, minimum, region, direction, cutoffs) {
  const tracks = new Set();
  const counted = new Set();
  const previous = new Map();
  let occupied = 0;
  const visible = [];
  for (const row of samples) {
    let count = 0;
    for (const { point, id } of detections(row, minimum)) {
      if (inside(point, region.polygon)) {
        count += 1;
        if (id != null) tracks.add(id);
      }
      if (!region.line || id == null) continue;
      const old = previous.get(id);
      if (!counted.has(id) && consecutive(old, row, point)
          && (inside(old.point, region.polygon) || inside(point, region.polygon))) {
        const sign = crossing(old.point, point, region.line);
        if (sign && (!direction || sign === direction)) counted.add(id);
      }
      previous.set(id, { t: row.t, point });
    }
    if (count) occupied += 1;
    visible.push(count);
  }
  const duration = samples.length > 1 ? samples.at(-1).t - samples[0].t : 0;
  const window = visible.slice(-RECENT);
  const contiguous = samples.length >= RECENT
    && samples.slice(-RECENT).every((row, index, rows) => !index || row.t - rows[index - 1].t === STEP);
  const prediction = contiguous ? mean(window) : null;
  const level = cutoffs && window.length
    ? ["Low", "Moderate", "High", "Severe"][cutoffs.filter(n => mean(window) >= n).length] : null;
  return {
    tracks: tracks.size, crossings: region.line ? counted.size : null, level,
    now: visible.at(-1), occupancy: visible.length ? occupied / visible.length : null,
    rate: duration && region.line ? 60 * counted.size / duration : null, prediction,
  };
}

// A candidate describes an envelope of observed track positions in a direction
// cluster. It has no assumed lane boundaries or compass heading.
export function movementCandidates(samples, minimum) {
  const previous = new Map();
  const groups = new Map();
  const recent = samples.slice(-90);
  for (const row of recent) {
    for (const { point, id } of detections(row, minimum)) {
      if (id == null) continue;
      const old = previous.get(id);
      previous.set(id, { t: row.t, point });
      if (!consecutive(old, row, point)) continue;
      const [dx, dy] = vector(old.point, point);
      if (Math.hypot(dx, dy) < .025) continue;
      const angle = Math.atan2(dy, dx);
      const bin = (Math.round(angle / (Math.PI / 4)) + 8) % 8;
      if (!groups.has(bin)) groups.set(bin, { tracks: new Set(), points: [] });
      const group = groups.get(bin);
      group.tracks.add(id);
      group.points.push(old.point, point);
    }
  }
  return [...groups.values()].filter(group => group.tracks.size >= 4)
    .sort((a, b) => b.tracks.size - a.tracks.size).slice(0, 3).map(({ points, tracks }) => {
      const bounds = axis => {
        const items = points.map(point => point[axis]).sort((a, b) => a - b);
        return [Math.max(0, items[Math.floor(items.length * .1)] - .025),
                Math.min(1, items[Math.floor(items.length * .9)] + .025)];
      };
      const [left, right] = bounds(0), [top, bottom] = bounds(1);
      return { polygon: [[left, top], [right, top], [right, bottom], [left, bottom]], tracks: tracks.size };
    });
}


export function movementTrails(samples, minimum) {
  const tracks = new Map();
  const recent = samples.slice(-11);
  for (const row of recent) {
    for (const { point, id } of detections(row, minimum)) {
      if (id == null) continue;
      const previous = tracks.get(id);
      const points = consecutive(previous, row, point) ? [...previous.points, point] : [point];
      tracks.set(id, { id, t: row.t, point, points });
    }
  }
  return [...tracks.values()].filter(track => track.points.length > 1)
    .sort((a, b) => b.t - a.t || b.points.length - a.points.length).slice(0, 24);
}
