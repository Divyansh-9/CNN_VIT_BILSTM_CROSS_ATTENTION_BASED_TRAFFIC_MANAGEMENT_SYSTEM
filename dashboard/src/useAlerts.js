import { useEffect, useRef, useState } from "react";
import { alertEvents, currentAlerts } from "./ops.js";

// Watches the live polls and keeps a history of what was raised and cleared,
// for this browser session only (sessionStorage, per intersection). The server
// keeps no alert log, so this is a record of what this page saw, dated by this
// computer's clock, and it says so on the page.
const KEY = (id) => `stms.alerts.${id}`;
const KEEP = 200;

function load(id) {
  try { return JSON.parse(window.sessionStorage.getItem(KEY(id)) || "[]"); } catch { return []; }
}
function save(id, history) {
  try { window.sessionStorage.setItem(KEY(id), JSON.stringify(history.slice(-KEEP))); } catch { /* a convenience only */ }
}

export function useAlerts(id, snapshot, now = () => Date.now()) {
  const [history, setHistory] = useState(() => load(id));
  const previous = useRef(null);
  const current = currentAlerts(snapshot);
  const signature = current.map((a) => a.key).join("|");
  // Ready once every live poll has answered at least once: before that, "no
  // alerts" only means "not loaded yet".
  const ready = ["health", "cls", "count", "heartbeat"].every((k) => snapshot[k] && snapshot[k].status !== "loading");
  useEffect(() => {
    if (!ready) return;
    // The first complete reading only sets the baseline: conditions present when
    // the page opened are shown as current, not announced as new events.
    if (previous.current === null) { previous.current = current; return; }
    const events = alertEvents(previous.current, current, now());
    previous.current = current;
    if (events.length) setHistory((h) => { const next = [...h, ...events].slice(-KEEP); save(id, next); return next; });
  }, [signature, ready]); // eslint-disable-line react-hooks/exhaustive-deps
  const clear = () => { setHistory([]); save(id, []); };
  return { current, history, clear };
}
