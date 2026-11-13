// D43: the forecast check over a whole analysed video. The live page's check (D26)
// pairs each forecast with what the next 60 s then showed; this does the same over
// every sample of a recording, and adds P105's comparison: the ridge count forecast
// against simply repeating the last minute.
//
// What it is not: accuracy. Both sides come from the same detector's counts (S67,
// human-verified quality, is not done). It is reported as counts and means, "k of n"
// and vehicles, never as a percentage, as D26 reports the live check.

export const WINDOW = 30; // 60 s of 2 s samples: the forecasters' window and target

const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;

// The mean of a lane's last 30 counts up to and including sample k: what "repeat the
// last minute" forecasts for the next minute (P105's persistence baseline).
export function lastMinute(samples, k, lane) {
  if (k < WINDOW - 1) return null;
  let sum = 0;
  for (let j = k - WINDOW + 1; j <= k; j += 1) sum += samples[j].counts[lane];
  return sum / WINDOW;
}

// Per lane, and pooled: how the class forecast agreed with what then happened, and
// how far the count forecasts were from it. Only samples where every compared value
// exists are used, so each comparison is paired.
export function forecastCheck(analysis) {
  const { samples, lanes } = analysis;
  const rows = lanes.map(({ name, approach }) => {
    let levelN = 0, levelAgreed = 0;
    const ridgeErr = [], repeatErr = [];
    let ridgeCloser = 0, repeatCloser = 0, tied = 0;
    samples.forEach((s, k) => {
      const then = s.then?.[approach];
      if (!then) return;
      const level = s.level?.[approach];
      if (level) { levelN += 1; if (level === then.level) levelAgreed += 1; }
      const ridge = s.number?.[approach];
      const repeat = lastMinute(samples, k, name);
      if (ridge === undefined || ridge === null || repeat === null) return;
      const a = Math.abs(ridge - then.number), b = Math.abs(repeat - then.number);
      ridgeErr.push(a); repeatErr.push(b);
      if (a < b) ridgeCloser += 1; else if (b < a) repeatCloser += 1; else tied += 1;
    });
    return {
      lane: name, approach,
      level: { agreed: levelAgreed, n: levelN },
      count: ridgeErr.length ? { n: ridgeErr.length, ridge: mean(ridgeErr), repeat: mean(repeatErr), ridgeCloser, repeatCloser, tied } : null,
    };
  });
  const counted = rows.filter((r) => r.count);
  const pooledN = counted.reduce((n, r) => n + r.count.n, 0);
  const pooled = {
    level: { agreed: rows.reduce((n, r) => n + r.level.agreed, 0), n: rows.reduce((n, r) => n + r.level.n, 0) },
    count: pooledN ? {
      n: pooledN,
      ridge: counted.reduce((s, r) => s + r.count.ridge * r.count.n, 0) / pooledN,
      repeat: counted.reduce((s, r) => s + r.count.repeat * r.count.n, 0) / pooledN,
      ridgeCloser: counted.reduce((s, r) => s + r.count.ridgeCloser, 0),
      repeatCloser: counted.reduce((s, r) => s + r.count.repeatCloser, 0),
      tied: counted.reduce((s, r) => s + r.count.tied, 0),
    } : null,
  };
  return { rows, pooled };
}

// Means over blocks of `size` samples (one minute by default), for drawing: an hour
// of 2 s samples is 1,800 points a line, too dense to read. A block whose values are
// all missing stays missing. The summary table always uses every sample.
export function perMinute(points, size = WINDOW, stepS = 2) {
  const out = [];
  for (let i = 0; i < points.length; i += size) {
    const block = points.slice(i, i + size);
    const avg = (key) => {
      const xs = block.map((p) => p[key]).filter((v) => v !== null);
      return xs.length ? mean(xs) : null;
    };
    out.push({ t: block[0].t + ((block.length - 1) * stepS) / 2, from: block[0].t, then: avg("then"), ridge: avg("ridge"), repeat: avg("repeat") });
  }
  return out;
}

// One lane's three series for the chart, each value placed at the forecast's own time
// and describing the 60 s after it: what then happened, the ridge forecast, and the
// last minute repeated. A missing value is null, drawn as a gap, never as zero.
export function laneSeries(analysis, laneName) {
  const lane = analysis.lanes.find((l) => l.name === laneName);
  return analysis.samples.map((s, k) => ({
    t: s.t,
    then: s.then?.[lane.approach]?.number ?? null,
    ridge: s.number?.[lane.approach] ?? null,
    repeat: lastMinute(analysis.samples, k, laneName),
  }));
}
