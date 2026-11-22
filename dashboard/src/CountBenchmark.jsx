import bellevue from "../../experiments/results/stms_bellevue_count_benchmark.json";
import crossings from "../../experiments/results/bellevue_crossing_review.json";
import cctv from "../../experiments/results/stms_cctv_count_benchmark.json";
import forecast from "../../experiments/results/video_count_forecast_review.json";
import styles from "./OpsPages.module.css";

export function CountBenchmark() {
  return <section className={styles.card} aria-label="Vehicle count benchmark">
    <h3>Vehicle count benchmark</h3>
    <p className={styles.muted}>
      Bellevue counts were visually checked on {bellevue.tuned.images} sampled frames from the morning and afternoon recordings in a fixed region. BMD-45 scores use {cctv.tuned.images} CCTV images from the validation split and {cctv.calibration_images.length} separate images for tuning.
    </p>
    <div style={{ overflowX: "auto" }}>
      <table className={styles.table}>
        <thead><tr><th>Footage</th><th>Detector</th><th>Mean absolute error</th><th>Weighted count error</th><th>CPU time per image</th></tr></thead>
        <tbody>{[
          ["Bellevue", bellevue.baseline],
          ["Bellevue", bellevue.tuned],
          ["BMD-45", cctv.baseline],
          ["BMD-45", cctv.tuned],
        ].map(([source, row]) => <tr key={`${source}-${row.model}-${row.size}-${row.confidence}`}>
          <th scope="row">{source}</th><td>{row.model} · {row.size} px · {Math.round(row.confidence * 100)}% confidence</td>
          <td>{row.mae.toFixed(2)} vehicles</td><td>{(row.wape * 100).toFixed(1)}%</td><td>{row.milliseconds_per_image.toFixed(0)} ms</td>
        </tr>)}</tbody>
      </table>
    </div>
    <p className={styles.muted}>The workbench defaults to the 960 px YOLO11s profile when its checkpoint is installed. Weighted count error is the sum of absolute frame count errors divided by the total reference vehicles.</p>
    <h4>Bellevue crossing verification</h4>
    <p className={styles.muted}>
      A visual review of the north and south approaches covered the first {crossings.review_end_s} seconds.
      The updated counting rule matched {crossings.after.matched} of {crossings.events.length} observed crossings.
      False crossings fell from {crossings.before.unmatched.length} to {crossings.after.unmatched.length}.
      These results apply to the two approaches and the reviewed clip only.
    </p>
    <h4>Next-minute forecast replay comparison</h4>
    <p className={styles.muted}>
      Across {forecast.p105.lane_forecasts.toLocaleString()} matched approach forecasts from {forecast.p105.recordings} recordings,
      mean absolute error fell from {forecast.p105.ridge_mae.toFixed(3)} to {forecast.p105.blend_mae.toFixed(3)} vehicles in view.
      The video blend was evaluated retrospectively against detector counts.
    </p>
  </section>;
}
