import styles from "./App.module.css";
import { ClassPanel, CountPanel, EvidencePanel } from "./Panels.jsx";
import { usePoll } from "./usePoll.js";

const REFRESH_MS = 2000; // PRD: dashboard refresh within 2 s

export function intersectionFromUrl(search) {
  const id = new URLSearchParams(search).get("id") || "j1";
  // The server's INTERSECTION_ID (contracts/mqtt.py, P142), length included.
  return /^[A-Za-z0-9_-]{1,32}$/.test(id) ? id : "j1";
}

export default function App({ fetcher, search = window.location.search }) {
  const id = intersectionFromUrl(search);
  const count = usePoll(`/count_forecast/${id}/latest`, REFRESH_MS, fetcher);
  const cls = usePoll(`/prediction/${id}/latest`, REFRESH_MS, fetcher);
  const evidence = usePoll("/evidence", 0, fetcher);
  return (
    <main className={styles.page}>
      <header className={styles.top}>
        <h1>STMS monitor · intersection <span className={styles.mono}>{id}</span></h1>
        <p className={styles.readonly}>Read-only. This page cannot send commands.</p>
      </header>

      {/* ADR-014: live and benchmark are two separated regions, never merged. */}
      <section className={styles.live} aria-label="Live monitor">
        <h2 className={styles.region}>Live forecasts</h2>
        <p className={styles.warning} data-p97a="true">
          Display only: neither forecast is connected to signal timing. In the controller's state,
          0.0 means an approach has no forecast and LOW is encoded as 1/3 (ADR-020 as amended,
          P110). Still open: P97a Part 2, the controller's behaviour under forecast faults, which
          is deferred.
        </p>
        <div className={styles.grid}>
          <CountPanel state={count} />
          <ClassPanel state={cls} />
        </div>
        <p className={styles.footnote}>No accuracy is shown here: a live score against the detector's own counts would be circular (ADR-014).</p>
      </section>

      <section className={styles.results} aria-label="Results">
        <h2 className={styles.region}>Results: historical evaluation evidence</h2>
        <EvidencePanel state={evidence} />
      </section>
    </main>
  );
}
