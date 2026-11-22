import { useEffect, useRef } from "react";
import styles from "./Glossary.module.css";

export const GLOSSARY = [
  ["Approach", "One road arm entering the intersection. N, S, E and W are its labels."],
  ["Lane", "A counted area in the camera's picture. The edge unit says which approach each lane feeds."],
  ["Congestion level", "LOW, MEDIUM or HIGH: the vehicles in view over 60 seconds, compared with limits set from one calibration hour of that camera. It does not measure speed or queues, and HIGH can be only a few vehicles."],
  ["Expected vehicles in view", "A forecast of the average number of vehicles visible in that lane over the next 60 seconds. It is not how many will pass through."],
  ["Counted", "What the detector measured in the video. Bicycles are left out of these counts."],
  ["Forecast", "An estimate of the next 60 seconds. After 60 seconds it is out of date."],
  ["Edge unit", "The computer that reads the video and counts vehicles. The video stays there; only numbers leave it."],
  ["Detector", "The vision model that finds vehicles in the video."],
  ["Replay", "Recorded footage run through the system as if it were arriving now. It is never a live camera."],
  ["Out of date", "Older than its 60 seconds, so it describes a minute that has passed."],
  ["Check", "A past forecast beside what the counts then showed. Both sides come from the same detector."],
  ["Persistence", "The forecast method behind the level: it expects the current level to continue."],
  ["Ridge", "The forecast method behind the vehicle number: a simple statistical model of recent counts."],
  ["Engineering view", "The same page with its underlying measurements: counts by class, PCU, and where each number came from."],
  ["PCU", "Passenger car unit. Weights each vehicle by the road space it takes, with a car as 1. It is not a measure of saturation."],
  ["Webster", "A long-established formula that sets signal timing from traffic demand."],
  ["PPO", "A reinforcement learning method, tested on signal timing only in simulation here."],
  ["95% interval", "The range the measured value plausibly falls in. Wide means less certain."],
];

export function Glossary({ onClose }) {
  const box = useRef(null);
  useEffect(() => {
    const el = box.current;
    if (typeof el.showModal === "function") el.showModal(); else el.setAttribute("open", "");
  }, []);
  return (
    <dialog ref={box} className={styles.glossary} aria-labelledby="glossaryTitle" onClose={onClose} data-glossary="true">
      <div className={styles.glossaryHead}>
        <h2 id="glossaryTitle">Glossary</h2>
        <button type="button" className={styles.ghost} onClick={onClose}>Close</button>
      </div>
      <dl>{GLOSSARY.map(([term, meaning]) => <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>)}</dl>
    </dialog>
  );
}
