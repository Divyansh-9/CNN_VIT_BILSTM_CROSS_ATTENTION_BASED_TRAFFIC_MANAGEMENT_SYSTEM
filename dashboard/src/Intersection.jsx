import styles from "./Intersection.module.css";
import { APPROACHES, validateClass, validateCount } from "./validate.js";

// The intersection drawing (UX step 3). It draws only what is forecast: no
// vehicles, because the system knows counts and not positions, and no video
// (NFR-13). Signal heads are drawn but marked not connected, because no
// forecast drives a signal (P97a).

export const SCALE_MAX = 10; // a full-length ribbon: 10 vehicles in the next minute, fixed so lengths compare over time
const SIZE = 320, C = SIZE / 2, HALF = 34, STOP = HALF + 14, REACH = C - STOP - 6, LANE = HALF / 2, THICK = 10;

// A real zero is a stub, not an absence; above the scale the ribbon stops at full length.
export function ribbonLength(count) {
  return 8 + (Math.min(Math.max(count, 0), SCALE_MAX) / SCALE_MAX) * (REACH - 8);
}

// What each approach shows. A ribbon needs both forecasts: its length is the
// count (ridge) and its colour and label the class (persistence), the two
// roles of ADR-027. When either forecast is not valid, nothing is drawn; when
// either is stale, every ribbon is drawn hollow, as a reading that is past.
export function junction(cls, count) {
  const c = cls.status === "ok" ? validateClass(cls.data) : null;
  const k = count.status === "ok" ? validateCount(count.data) : null;
  if (!c?.ok || !k?.ok) {
    const note = cls.status === "loading" || count.status === "loading" ? "Waiting" : "No data";
    return { stale: false, age: null, horizon: 60, lanes: Object.fromEntries(APPROACHES.map((a) => [a, { kind: "none", note }])) };
  }
  const stale = c.data.stale || k.data.stale;
  const lanes = {};
  for (const a of APPROACHES) {
    if (!(a in c.data.predictions)) lanes[a] = { kind: "none", note: "No forecast" };
    else if (!(a in k.data.counts)) lanes[a] = { kind: "none", note: "No count", cls: c.data.predictions[a] };
    else lanes[a] = { kind: stale ? "stale" : "fresh", cls: c.data.predictions[a], count: k.data.counts[a] };
  }
  // The older of the two forecasts sets the age: the drawing is only as current as its staler half.
  return { stale, age: Math.max(c.data.age_s, k.data.age_s), horizon: c.data.horizon_sec ?? k.data.horizon_sec ?? 60, lanes };
}

// Inbound lanes, right-hand traffic: southbound on the west half of the north
// arm, northbound on the east half of the south arm, and so on. Each ribbon is
// drawn once, on the north arm, and turned about the centre to its own arm.
export const TURN = { N: 0, E: 90, S: 180, W: 270 };
const RX = C - LANE, HEAD = C - STOP, TAPER = 6, W2 = THICK / 2;

// Step 3b: the ribbon tapers to a point at its stop line, so it reads as
// traffic heading into the junction. Direction is shape; colour stays the class.
export function ribbonPath(len) {
  const out = HEAD - len, neck = HEAD - Math.min(TAPER, len);
  return `M${RX - W2},${out} H${RX + W2} V${neck} L${RX},${HEAD} L${RX - W2},${neck} Z`;
}

// Above the scale the ribbon stops at full length, and two road-coloured cuts
// near its outer end say so: the usual scale-break sign, and unlike the single
// stop line. A cut's contrast is the class colour against the road, which the
// palette already measures; an ink bar on the MEDIUM ribbon would not be.
function overflowBars() {
  const out = HEAD - ribbonLength(SCALE_MAX);
  return [out + 4, out + 9].map((y) => ({ x: RX - W2 - 3, y, width: THICK + 6, height: 2 }));
}

const STOP_LINES = {
  N: { x: C - HALF, y: C - STOP, width: HALF, height: 2.5 },
  S: { x: C, y: C + STOP - 2.5, width: HALF, height: 2.5 },
  E: { x: C + STOP - 2.5, y: C - HALF, width: 2.5, height: HALF },
  W: { x: C - STOP, y: C, width: 2.5, height: HALF },
};

// Each label sits in the corner beside its approach, outside the road, on two
// short lines so the longest ("no forecast", "MEDIUM") stays inside the drawing.
const LABELS = {
  N: { x: C - HALF - 8, y: 20, anchor: "end" },
  E: { x: SIZE - 6, y: C - HALF - 30, anchor: "end" },
  S: { x: C + HALF + 8, y: SIZE - 30, anchor: "start" },
  W: { x: 6, y: C + HALF + 20, anchor: "start" },
};

export function labelLines(a, lane) {
  if (lane.kind === "none") return lane.cls ? [`${a} ${lane.cls}`, lane.note.toLowerCase()] : [a, lane.note.toLowerCase()];
  return [`${a} ${lane.cls}`, `${lane.count.toFixed(1)} veh${lane.count > SCALE_MAX ? ` >${SCALE_MAX}` : ""}`];
}

export function Intersection({ cls, count }) {
  const j = junction(cls, count);
  const zebra = [];
  for (let i = 0; i < 8; i++) {
    const o = -HALF + 3 + i * 8.5;
    zebra.push([C + o, C - HALF - 13, 4, 10], [C + o, C + HALF + 3, 4, 10], [C - HALF - 13, C + o, 10, 4], [C + HALF + 3, C + o, 10, 4]);
  }
  const g = HALF + 22;
  return (
    <figure className={styles.figure} data-junction={j.stale ? "stale" : "current"}>
      <svg className={styles.svg} viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE} aria-hidden="true" focusable="false">
        <rect className={styles.road} x="0" y={C - HALF} width={SIZE} height={HALF * 2} />
        <rect className={styles.road} x={C - HALF} y="0" width={HALF * 2} height={SIZE} />
        <rect className={styles.box} x={C - HALF} y={C - HALF} width={HALF * 2} height={HALF * 2} />
        {zebra.map(([x, y, w, h], i) => <rect key={i} className={styles.zebra} x={x} y={y} width={w} height={h} />)}
        <path className={styles.centre} d={`M${C},0 V${C - STOP} M${C},${C + STOP} V${SIZE} M0,${C} H${C - STOP} M${C + STOP},${C} H${SIZE}`} />
        {APPROACHES.map((a) => <rect key={a} className={styles.stop} {...STOP_LINES[a]} />)}
        {APPROACHES.filter((a) => j.lanes[a].kind !== "none").map((a) => (
          <g key={a} transform={`rotate(${TURN[a]} ${C} ${C})`}>
            <path data-ribbon={a} data-kind={j.lanes[a].kind} strokeLinejoin="round"
                  className={`${styles[j.lanes[a].cls]} ${j.lanes[a].kind === "stale" ? styles.hollow : ""}`}
                  d={ribbonPath(ribbonLength(j.lanes[a].count))} />
            {j.lanes[a].count > SCALE_MAX && overflowBars().map((bar, i) => (
              <rect key={i} data-overflow={a} className={styles.overflow} {...bar} />
            ))}
          </g>
        ))}
        {[[C - g, C - g], [C + g - 12, C - g], [C + g - 12, C + g - 12], [C - g, C + g - 12]].map(([x, y], i) => (
          <rect key={i} className={styles.head} x={x} y={y} width="12" height="12" rx="2" data-signal="not connected" />
        ))}
        {APPROACHES.map((a) => (
          <text key={a} data-label={a} className={j.lanes[a].kind === "fresh" ? styles.label : styles.labelMuted}
                x={LABELS[a].x} y={LABELS[a].y} textAnchor={LABELS[a].anchor}>
            {labelLines(a, j.lanes[a]).map((line, i) => (
              <tspan key={i} x={LABELS[a].x} dy={i ? 15 : 0} className={i ? undefined : styles.labelHead}>{line}</tspan>
            ))}
          </text>
        ))}
      </svg>
      <figcaption className={styles.caption}>
        Ribbon length: next-minute count forecast (ridge), 0 to {SCALE_MAX} vehicles; two cuts near its outer
        end mean more than {SCALE_MAX}, with the exact count written beside it. Each ribbon points into the
        junction. Colour and word: congestion class (persistence). Hollow ribbons are past their horizon. Dashed
        squares: signal heads, not connected (P97a). No vehicles or video are shown (NFR-13).
      </figcaption>
    </figure>
  );
}

// How old the forecast is against its horizon. Text carries the answer; the
// ticks only picture it.
export function horizon(j) {
  if (j.age === null) return { kind: "unknown", text: "", age: null }; // the age line already says "unknown"
  const age = Math.round(j.age);
  if (j.stale) return { kind: "stale", text: `Stale, ${Math.max(age - j.horizon, 0)} s past its ${j.horizon} s horizon`, age };
  return { kind: "fresh", text: `Fresh, valid ${Math.max(j.horizon - age, 0)} s more`, age };
}

export function Horizon({ cls, count }) {
  const j = junction(cls, count);
  const h = horizon(j);
  const ticks = [];
  for (let i = 0; i <= 60; i++) {
    const lit = h.age !== null && i <= Math.min(h.age, 60);
    ticks.push(<rect key={i} x={4 + i * 9.6 - 0.75} y={i % 10 ? 9 : 3} width="1.5" height={i % 10 ? 14 : 22} rx="0.75"
                     className={lit ? (h.kind === "stale" ? styles.tickStale : styles.tickLit) : styles.tickDim} />);
  }
  return (
    <div className={styles.horizon} data-horizon={h.kind}>
      <p className={styles.age}>
        {h.age === null ? <>Forecast age <b>unknown</b></>
          : <>Forecast age <b className={styles.mono}>{h.age} s</b> of {j.horizon} s</>}
      </p>
      <svg className={styles.ticks} viewBox="0 0 584 28" aria-hidden="true" focusable="false">{ticks}</svg>
      {h.text && <p className={styles.horizonText}>{h.text}</p>}
    </div>
  );
}

