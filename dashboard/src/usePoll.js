import { useEffect, useState } from "react";
import { get } from "./api.js";

export const RETRY_MS = 5000;

// Polls one read-only endpoint. The dashboard's refresh budget is 2 s (PRD),
// so live panels poll at 2 s. With intervalMs 0 the endpoint is fetched until
// it first succeeds and then never again: evidence does not change while the
// dashboard runs (ADR-014), but one failed first request must not leave the
// panel waiting forever.
const clock = () => performance.now();

// Polls /health and times each round trip in this browser. It is the only
// live latency the system can state honestly: the server dates everything by
// its own clock, because edge clocks drift, and records no edge-to-server delay.
export function useHealth(intervalMs, fetcher, now = clock) {
  const [state, setState] = useState({ status: "loading" });
  useEffect(() => {
    let alive = true;
    const run = async () => {
      const started = now();
      const result = await get("/health", fetcher);
      if (alive) setState({ ...result, rtt_ms: Math.round(now() - started) });
    };
    run();
    const interval = setInterval(run, intervalMs);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, [intervalMs, fetcher, now]);
  return state;
}

export function usePoll(path, intervalMs, fetcher, retryMs = RETRY_MS) {
  const [state, setState] = useState({ status: "loading" });
  useEffect(() => {
    let alive = true;
    let timer = null;
    const run = async () => {
      const result = await get(path, fetcher);
      if (!alive) return;
      setState(result);
      if (!intervalMs && result.status !== "ok") timer = setTimeout(run, retryMs);
    };
    run();
    const interval = intervalMs ? setInterval(run, intervalMs) : null;
    return () => {
      alive = false;
      if (interval) clearInterval(interval);
      if (timer) clearTimeout(timer);
    };
  }, [path, intervalMs, fetcher, retryMs]);
  return state;
}
