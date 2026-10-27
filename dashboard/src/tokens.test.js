// The colour rules in theme.css, measured rather than eyeballed (UX step 1).
// Contrast is WCAG 2's relative-luminance ratio; hue gaps are on the colour wheel.
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const dir = dirname(fileURLToPath(import.meta.url));
const theme = readFileSync(join(dir, "theme.css"), "utf8");
const raw = Object.fromEntries([...theme.matchAll(/--([a-z-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));
const token = (name) => {
  const value = raw[name];
  const ref = /^var\(--([a-z-]+)\)$/.exec(value ?? "");
  return ref ? token(ref[1]) : value;
};

const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
const luminance = (hex) => {
  const [r, g, b] = rgb(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const hue = (hex) => {
  const [r, g, b] = rgb(hex);
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  if (d === 0) return 0;
  const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (h * 60 + 360) % 360;
};
const hueGap = (a, b) => {
  const d = Math.abs(hue(a) - hue(b));
  return Math.min(d, 360 - d);
};

const SCALE = ["low", "medium", "high"];
const STATES = ["ok", "stale", "bad"];

// Colour-vision simulation: Machado, Oliveira & Fernandes (2009), severity 1.0, in linear RGB,
// then CIELAB distance. The same maths as the design solver (themes.py).
const CVD = {
  protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
  tritan: [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.3039]],
};
const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lab = (hex, m) => {
  let c = rgb(hex).map(lin);
  if (m) c = m.map((row) => Math.min(1, Math.max(0, row[0] * c[0] + row[1] * c[1] + row[2] * c[2])));
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  const x = f((0.4124 * c[0] + 0.3576 * c[1] + 0.1805 * c[2]) / 0.95047);
  const y = f(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]);
  const z = f((0.0193 * c[0] + 0.1192 * c[1] + 0.9505 * c[2]) / 1.08883);
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
};
const apart = (names, m) => {
  let min = Infinity;
  for (let i = 0; i < names.length; i++) for (let j = i + 1; j < names.length; j++) {
    const [a, b] = [lab(token(names[i]), m), lab(token(names[j]), m)];
    min = Math.min(min, Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]));
  }
  return min;
};

describe("the palette's measured rules", () => {
  it("text is readable on the background and the panel", () => {
    for (const surface of ["bg", "panel"]) {
      expect(contrast(token("ink"), token(surface))).toBeGreaterThanOrEqual(7);
      expect(contrast(token("muted"), token(surface))).toBeGreaterThanOrEqual(4.5);
    }
    // White text on the brand orange measures 2.77, so text on orange is dark.
    expect(contrast(token("on-brand"), token("brand"))).toBeGreaterThanOrEqual(4.5);
  });

  it("the congestion scale stays at least 30 deg from the brand orange, and its classes 40 deg apart", () => {
    for (const c of SCALE) expect(hueGap(token(c), token("brand"))).toBeGreaterThanOrEqual(30);
    for (const [a, b] of [["low", "medium"], ["medium", "high"], ["low", "high"]]) {
      expect(hueGap(token(a), token(b))).toBeGreaterThanOrEqual(40);
    }
  });

  it("each class is visible on the panel and carries readable dark text", () => {
    for (const c of SCALE) {
      expect(contrast(token(c), token("panel"))).toBeGreaterThanOrEqual(3);
      expect(contrast(token("on-class"), token(c))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("state colours are kept apart from the scale, the brand and each other", () => {
    for (const s of STATES) {
      expect(hueGap(token(s), token("brand"))).toBeGreaterThanOrEqual(30);
      for (const c of SCALE) expect(hueGap(token(s), token(c))).toBeGreaterThanOrEqual(30);
    }
    expect(hueGap(token("stale"), token("bad"))).toBeGreaterThanOrEqual(30);
    expect(token("bad")).not.toBe(token("high"));    // an error must not look like congestion
    // stale and bad are read as text; ok is a status dot
    for (const s of ["stale", "bad"]) expect(contrast(token(s), token("panel"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("ok"), token("panel"))).toBeGreaterThanOrEqual(3);
  });

  it("the stale banner keeps its text readable on its own background", () => {
    expect(contrast(token("stale"), token("stale-bg"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("ink"), token("stale-bg"))).toBeGreaterThanOrEqual(7);
  });

  it("the focus ring stands out from every surface it sits on (WCAG 1.4.11)", () => {
    for (const s of ["bg", "panel", "stale-bg", "notice-bg"]) expect(contrast(token("focus"), token(s))).toBeGreaterThanOrEqual(3);
  });

  // A project criterion, not a WCAG requirement: WCAG asks only that colour is
  // never the sole signal, which the labels and shapes already satisfy.
  it("the classes stay at least 20 apart, and the states 12, under three colour-vision simulations", () => {
    for (const m of [null, ...Object.values(CVD)]) {
      expect(apart(SCALE, m)).toBeGreaterThanOrEqual(20);
      expect(apart(STATES, m)).toBeGreaterThanOrEqual(12);
    }
  });
});

describe("where each colour may be used", () => {
  const sheets = readdirSync(dir).filter((f) => f.endsWith(".css") && f !== "theme.css")
    .map((f) => [f, readFileSync(join(dir, f), "utf8")]);
  const rules = sheets.flatMap(([file, css]) =>
    [...css.replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/([^{}]+)\{([^}]*)\}/g)]
      .map((m) => ({ file, selector: m[1].trim(), body: m[2] })));

  it("congestion colours appear only on the class chips", () => {
    const users = rules.filter((r) => /var\(--(low|medium|high)\)/.test(r.body));
    expect(users.map((r) => r.selector).sort()).toEqual([".HIGH", ".LOW", ".MEDIUM"]);
  });

  it("the brand colours never appear on the data panels", () => {
    const panels = rules.filter((r) => r.file === "Panels.module.css");
    expect(panels.filter((r) => /var\(--(brand|brand-deep|accent)\)/.test(r.body))).toEqual([]);
  });

  it("nothing lowers contrast with opacity: stale data changes style, not transparency", () => {
    const dimmed = rules.filter((r) => /opacity\s*:\s*0?\.\d/.test(r.body));
    expect(dimmed.map((r) => `${r.file} ${r.selector}`)).toEqual([]);
  });

  it("each status has its own shape as well as its colour", () => {
    const body = (sel) => rules.find((r) => r.file === "Panels.module.css" && r.selector === sel)?.body ?? "";
    expect(body(".dot")).toMatch(/border-radius:\s*50%/);                 // fresh: a dot
    expect(body(".k_stale")).toMatch(/rotate\(45deg\)/);                   // stale: a diamond
    expect(body(".k_bad")).toMatch(/border-radius:\s*1px/);               // unreachable or invalid: a square
    expect(body(".k_none, .k_loading")).toMatch(/dashed/);               // nothing yet: an outline
  });

  it("no colour is hard-coded outside theme.css", () => {
    for (const [file, css] of sheets) expect([file, css.match(/#[0-9a-fA-F]{3,8}\b/g)]).toEqual([file, null]);
  });
});
