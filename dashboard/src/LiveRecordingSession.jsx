import { useEffect, useRef, useState } from "react";
import { get } from "./api.js";
import { uploadVideo, wbGet, wbPost } from "./workbench.js";
import { validateAnalysis } from "./validate.js";
import styles from "./OpsPages.module.css";

export function recordingCamera(filename, profiles, selected) {
  if (selected) return selected;
  const name = filename.replace(/\.[^.]+$/, "").toLowerCase();
  const matches = profiles.filter(({ id }) => {
    const camera = id.toLowerCase();
    return name === camera || (name.startsWith(camera) && /[_\- ]/.test(name[camera.length] ?? ""));
  });
  matches.sort((a, b) => b.id.length - a.id.length);
  return matches[0]?.id ?? "whole-frame";
}

function addSamples(previous, items) {
  if (!items.length) return previous;
  const head = previous ?? items[0].head;
  return {
    ...head,
    samples: [...head.samples, ...items.map(item => item.sample)],
    processing: items.at(-1).processing,
    traffic: {
      ...head.traffic,
      crossings: [...head.traffic.crossings, ...items.flatMap(item => item.crossings)],
      alerts: [...head.traffic.alerts, ...items.flatMap(item => item.alerts)],
    },
  };
}

const delay = () => new Promise(resolve => setTimeout(resolve, 400));
function data(response) {
  if (response.status !== "ok") throw new Error(response.reason ?? "The workbench did not respond.");
  return response.data;
}

export function LiveRecordingSession({ file, duration, revision, profiles, selected, onStream, onResults, caps, fetcher }) {
  const [status, setStatus] = useState("");
  const [problem, setProblem] = useState("");
  const tail = useRef(Promise.resolve());
  const staged = useRef(null);
  const callbacks = useRef(null);
  callbacks.current = { onStream, onResults };
  const profile = file && profiles && recordingCamera(file.name, profiles, selected);
  const minimum = caps.minimum_duration_s ?? 2;
  const ready = caps.analysis_ready !== false;
  const jobPath = caps.parallel_analysis ? "/workbench/jobs/current?mode=live" : "/workbench/jobs/current";

  useEffect(() => {
    if (!profile || !Number.isFinite(duration) || duration < minimum || !ready) return undefined;
    const controller = new AbortController();
    const { signal } = controller;
    callbacks.current.onStream(null);
    setStatus("Starting live feed…");
    setProblem("");
    const run = async () => {
      if (signal.aborted) return;
      let id, completed = false;
      try {
        if (staged.current?.file !== file) {
          const uploaded = await uploadVideo(file, fetcher, signal);
          if (signal.aborted) return;
          staged.current = { file, recording: data(uploaded).recording };
        }
        if (signal.aborted) return;
        const started = data(await wbPost("/workbench/jobs",
          { recording: staged.current.recording, camera: profile, monitoring: true }, fetcher));
        id = started.job_id;
        let offset = 0, result = null;
        while (!signal.aborted) {
          const state = data(await wbGet(jobPath, fetcher));
          if (signal.aborted) break;
          if (state.job_id !== id) throw new Error("This monitoring session was replaced.");
          if (state.problem) throw new Error(state.problem === "stopped" ? "Monitoring stopped." : state.problem);
          if (!state.running && state.key) {
            const checked = validateAnalysis(data(await get(`/workbench/analysis/${state.key}`, fetcher)));
            if (signal.aborted) break;
            if (!checked.ok) throw new Error(checked.reason);
            completed = true;
            callbacks.current.onResults(checked.data, id);
            return;
          }
          const batch = data(await wbGet(`/workbench/monitor/demo/${id}?offset=${offset}`, fetcher));
          if (signal.aborted) break;
          if (batch.items.length) {
            result = addSamples(result, batch.items);
            offset = batch.next;
            setStatus("Live feed connected");
            callbacks.current.onStream(result, id);
          }
          await delay();
        }
      } catch (error) {
        if (!signal.aborted) {
          setStatus("");
          setProblem(error.message);
          callbacks.current.onStream(null);
        }
      } finally {
        if (id && !completed) await wbPost("/workbench/jobs/stop", { job_id: id }, fetcher);
      }
    };
    tail.current = tail.current.then(run);
    return () => controller.abort();
  }, [file, duration, profile, minimum, ready, revision, fetcher, jobPath]);

  if (!file) return null;
  if (!ready) return <p role="alert">{caps.analysis_problem || "The local detector is unavailable."}</p>;
  if (Number.isFinite(duration) && duration < minimum) return <p role="alert">Choose a video at least {minimum} seconds long.</p>;
  if (problem) return <p role="alert">{problem} Use Restart to try again.</p>;
  return <p role="status" className={styles.muted}>{status || "Preparing video…"}
    {profile && profile !== "whole-frame" && ` · ${profile}`}</p>;
}
