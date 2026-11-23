import { useMemo, useState } from "react";
import { downloadText, toCsv } from "./ops.js";
import { movementCandidates, movementTrails, regionMetrics } from "./trafficRegions.js";
import styles from "./Analyze.module.css";

const STORE = "stms.trafficRegions.v1";
const read = () => {
  try { return JSON.parse(localStorage.getItem(STORE)) ?? {}; } catch { return {}; }
};
const pointsOf = points => points.map(point => point.join(",")).join(" ");

export function useTrafficRegions() {
  const [regions, setRegions] = useState([]);
  const [draft, draw] = useState(null);
  const [selected, select] = useState(null);
  const [direction, setDirection] = useState(0);
  const [saved, setSaved] = useState(read);
  const [config, setConfig] = useState("");
  const [notice, message] = useState("");
  const [suggestions, propose] = useState([]);
  const [trails, showTrails] = useState(false);
  const active = useMemo(() => regions.filter(region => selected === null || selected.includes(region.id)), [regions, selected]);
  const reset = () => { setRegions([]); draw(null); select(null); setDirection(0); propose([]); message(""); };
  const add = polygon => {
    if (regions.length >= 8) return;
    const id = String(Date.now()) + "-" + regions.length;
    setRegions(items => [...items, { id, name: "Region " + (items.length + 1), polygon, line: null }]);
    select([id]);
  };
  const edit = (id, fields) => setRegions(items => items.map(item => item.id === id ? { ...item, ...fields } : item));
  const updateDraft = (event, stage) => {
    if (!stage) return;
    const box = stage.getBoundingClientRect();
    const point = [(event.clientX - box.left) / box.width, (event.clientY - box.top) / box.height];
    if (point.every(value => value >= 0 && value <= 1)) draw(current =>
      current && current.points.length < (current.line ? 2 : 16)
        ? { ...current, points: [...current.points, point] } : current);
  };
  const apply = () => {
    const { points, id, line } = draft;
    if (line && Math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]) < .015) {
      message("Place two distinct line endpoints."); return;
    }
    if (!line) {
      const area = Math.abs(points.reduce((sum, p, i) => {
        const next = points[(i + 1) % points.length];
        return sum + p[0] * next[1] - p[1] * next[0];
      }, 0)) / 2;
      if (area < .001) { message("Draw a region with at least three distinct corners and a visible area."); return; }
    }
    if (id) edit(id, line ? { line: points } : { polygon: points });
    else add(points);
    draw(null); message("");
  };
  const save = () => {
    const name = config.trim();
    if (!name) { message("Enter a name for the configuration."); return; }
    const next = { ...saved, [name]: regions };
    try {
      localStorage.setItem(STORE, JSON.stringify(next)); setSaved(next); message("Configuration saved in this browser.");
    } catch { message("This browser could not save the configuration."); }
  };
  const load = key => {
    if (!Object.hasOwn(saved, key)) return;
    setRegions(saved[key]); select(null); draw(null); setConfig(key); message("Configuration loaded. Confirm that it fits this camera.");
  };
  return { regions, active, draft, draw, selected, select, direction, setDirection, add, edit, notice, message,
    reset, updateDraft, apply, save, load, config, setConfig, saved, suggestions, propose, trails, showTrails,
    remove: id => { setRegions(items => items.filter(item => item.id !== id)); select(null); } };
}

export function RegionOverlay({ region, result, time }) {
  const paths = region.trails && result
    ? movementTrails(result.samples.filter(row => row.t <= time), result.min_confidence ?? .45) : [];
  const drafts = region.draft?.points ?? [];
  return <svg className={styles.regionsOverlay} viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
    {region.active.map(item => <g key={item.id}>
      <polygon points={pointsOf(item.polygon)} vectorEffect="non-scaling-stroke" />
      {item.line && <>
        <line x1={item.line[0][0]} y1={item.line[0][1]} x2={item.line[1][0]} y2={item.line[1][1]} vectorEffect="non-scaling-stroke" />
        {item.line.map(([x, y], i) => <text key={i} x={x} y={y}>{i + 1}</text>)}
      </>}
    </g>)}
    {paths.map(track => <polyline key={track.id} className={styles.trackTrail} points={pointsOf(track.points)} vectorEffect="non-scaling-stroke" />)}
    {drafts.length > 0 && <polyline points={pointsOf(drafts)} vectorEffect="non-scaling-stroke" />}
    {drafts.map(([x, y], index) => <circle key={index} cx={x} cy={y} r={.008} vectorEffect="non-scaling-stroke" />)}
  </svg>;
}

export function TrafficRegions({ region, result, time, live, pause }) {
  const [wholeReport, setWholeReport] = useState(true);
  const limit = live || !wholeReport ? time : Infinity;
  const { regions, active, draft, direction } = region;
  const samples = useMemo(() => result?.samples.filter(row => row.t <= limit) ?? [], [result?.samples, limit]);
  const cutoffs = result?.traffic?.policy?.density;
  const metrics = useMemo(() => active.map(item => regionMetrics(samples, result?.min_confidence ?? .45, item, direction || item.direction || 0, cutoffs)),
    [active, samples, result?.min_confidence, direction, cutoffs]);
  const begin = (id = null, line = false) => { pause(); region.message(""); region.draw({ id, line, points: [] }); };
  const exportMetrics = () => {
    const rows = active.map((item, i) => ({ name: /^[=+@-]/.test(item.name) ? "'" + item.name : item.name,
      from_s: samples[0]?.t, to_s: samples.at(-1)?.t, ...metrics[i] }));
    downloadText("stms-regions.csv", toCsv(["name","from_s","to_s","tracks","crossings","level","now","occupancy","rate","prediction"], rows));
  };
  return <details className={styles.how}>
    <summary>Custom regions and counting lines</summary>
    <p className={styles.small}>Draw a polygon over the road. Add a finite line to count sampled crossing tracks. Confirm any suggested movement region against the video.</p>
    <div className={styles.regionActions}>
      <button type="button" disabled={Boolean(draft) || regions.length >= 8} onClick={() => begin()}>Draw region</button>
      <button type="button" disabled={Boolean(draft) || !samples.length} onClick={() => {
        const candidates = movementCandidates(samples, result.min_confidence);
        region.propose(candidates);
        region.message(candidates.length ? "" : "Too few consistent tracks to propose a movement region.");
      }}>Suggest movement regions</button>
      <label><input type="checkbox" checked={region.trails} onChange={e => region.showTrails(e.target.checked)} /> Recent track trails</label>
    </div>
    {region.suggestions.map((item, i) => <button type="button" key={i} disabled={Boolean(draft) || regions.length >= 8}
      onClick={() => region.add(item.polygon)}>Review candidate {i + 1} ? {item.tracks} tracks</button>)}
    {draft && <div className={styles.regionActions}>
      <span role="status">{draft.line ? "Click two endpoints on the picture" : "Click at least three polygon corners on the picture"} ? {draft.points.length} placed</span>
      <button type="button" onClick={region.apply} disabled={draft.points.length < (draft.line ? 2 : 3)}>Apply</button>
      <button type="button" onClick={() => region.draw({ ...draft, points: draft.points.slice(0, -1) })} disabled={!draft.points.length}>Undo point</button>
      <button type="button" onClick={() => region.draw(null)}>Cancel</button>
    </div>}
    <div className={styles.regionActions}>
      <label>Saved configuration <select value="" disabled={Boolean(draft)} onChange={e => region.load(e.target.value)}>
        <option value="">Choose saved configuration</option>
        {Object.keys(region.saved).map(name => <option key={name}>{name}</option>)}</select></label>
      {regions.length > 0 && <><label>Configuration name <input value={region.config} maxLength={60} onChange={e => region.setConfig(e.target.value)} /></label>
        <button type="button" onClick={region.save}>Save configuration</button></>}
    </div>
    {region.notice && <p role="status">{region.notice}</p>}
    {regions.length > 0 && <>
      <div className={styles.regionActions}>
        <fieldset className={styles.regionActions}>
          <legend>Analyze selected regions</legend>
          <button type="button" onClick={() => region.select(null)} disabled={region.selected === null}>Analyze all regions</button>
          {regions.map(item => {
            const selectedIds = region.selected ?? regions.map(value => value.id);
            return <label key={item.id}><input type="checkbox" checked={selectedIds.includes(item.id)} onChange={e =>
              region.select(e.target.checked ? [...selectedIds, item.id] : selectedIds.filter(id => id !== item.id))} /> {item.name}</label>;
          })}
        </fieldset>
        <label>Crossing direction <select value={direction} onChange={e => region.setDirection(Number(e.target.value))}>
          <option value={0}>Use region directions</option><option value={1}>Across to right of line (point 1 ? 2)</option>
          <option value={-1}>Across to left of line (point 1 ? 2)</option>
        </select></label>
        {!live && <label><input type="checkbox" checked={wholeReport} onChange={e => setWholeReport(e.target.checked)} /> Entire report</label>}
        <button type="button" disabled={!samples.length || !active.length} onClick={exportMetrics}>Export region metrics (CSV)</button>
      </div>
      {active.map((item, i) => <section key={item.id} className={styles.regionSummary}>
        <div className={styles.regionActions}>
          <label>Region name <input value={item.name} maxLength={40} onChange={e => region.edit(item.id, { name: e.target.value })} /></label>
          <button type="button" disabled={Boolean(draft)} onClick={() => begin(item.id)}>Redraw region</button>
          <button type="button" disabled={Boolean(draft)} onClick={() => begin(item.id, true)}>Draw counting line</button>
          {item.line && <>
            <label>Region crossing direction <select value={item.direction ?? 0} onChange={e => region.edit(item.id, { direction: Number(e.target.value) })}>
              <option value={0}>Both directions</option><option value={1}>Across to right (1 ? 2)</option>
              <option value={-1}>Across to left (1 ? 2)</option>
            </select></label>
            <button type="button" disabled={Boolean(draft)} onClick={() => region.edit(item.id, { line: null })}>Remove line</button>
          </>}
          <button type="button" disabled={Boolean(draft)} onClick={() => region.remove(item.id)}>Remove region</button>
        </div>
        {samples.length > 0 && <p>{metrics[i].now} visible ? {metrics[i].tracks} distinct tracker IDs
          {metrics[i].occupancy !== null && <> ? {Math.round(metrics[i].occupancy * 100)}% of samples occupied</>}
          {metrics[i].level && <> ? {metrics[i].level} estimated demand</>}
          {metrics[i].crossings !== null && <> ? {metrics[i].crossings} distinct sampled crossings</>}
          {metrics[i].rate !== null && <> ? {metrics[i].rate.toFixed(1)} crossings/min</>}
          {metrics[i].prediction !== null && <> ? Next 30 s baseline: {metrics[i].prediction.toFixed(1)} vehicles in view</>}
        </p>}
      </section>)}
      <p className={styles.small}>These estimates use the saved detections every 2 s. Short crossings and occluded tracks can be missed. Regions and lines are saved separately in this browser.</p>
    </>}
  </details>;
}
