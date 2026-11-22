import { useEffect, useRef, useState } from "react";
import { get } from "./api.js";
import { validateAnalysis } from "./validate.js";
import { wbGet, wbPost } from "./workbench.js";

const SELECTION = "stms.offlineAnalysisId";

function remember(id) {
  try {
    if (id) window.localStorage.setItem(SELECTION, id);
    else window.localStorage.removeItem(SELECTION);
  } catch { /* A storage preference is optional. */ }
}

export function useRecording(caps, fetcher, showResults) {
  const [mode, setMode] = useState(null);
  const [entry, setEntry] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  const [offline, setOffline] = useState(false);
  const [fileName, setFileName] = useState("");
  const [seek, setSeek] = useState(null);
  const [handed, setHanded] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [refreshKey, refreshHistory] = useState(0);
  const [managing, setManaging] = useState(false);
  const restoreAttempt = useRef(false);
  const historyVisible = historyOpen || Boolean(caps?.manage_history && showResults);
  const revision = useRef(0);
  const real = mode === "real" || (mode === null && Boolean(caps?.history));
  const jobId = entry?.id;

  useEffect(() => {
    if (!caps?.history || (!historyVisible && !jobId)) return undefined;
    let active = true;
    const refresh = async () => {
      const result = await wbGet("/workbench/jobs", fetcher);
      if (!active) return;
      setOffline(result.status !== "ok");
      if (result.status === "ok") {
        setJobs(result.data);
        setHistoryLoaded(true);
      }
    };
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => { active = false; clearInterval(timer); };
  }, [caps?.history, fetcher, historyVisible, jobId, refreshKey]);

  const select = async (job) => {
    const turn = ++revision.current;
    setEntry(null);
    setError("");
    setMode("real");
    setFileName(job.filename);
    setSeek(null);
    setHanded({ status: "loading" });
    if (!job.result_key) {
      setHanded({ status: "empty" });
      return;
    }
    const response = await get(`/workbench/analysis/${job.result_key}`, fetcher);
    if (revision.current !== turn) return;
    const checked = response.status === "ok" ? validateAnalysis(response.data) : { ok: false, reason: response.reason };
    if (!checked.ok) {
      setHanded({ status: "error" });
      setError(checked.reason ?? "The stored analysis could not be loaded.");
      return;
    }
    setEntry({ result: checked.data, id: job.id });
    if (caps?.manage_history && job.mode === "offline") remember(job.id);
    setHanded({ status: "ok", data: checked.data, videoUrl: job.has_video ? `/workbench/video/${job.id}` : null });
  };

  useEffect(() => {
    if (!caps?.manage_history || !showResults || !historyLoaded || restoreAttempt.current) return;
    restoreAttempt.current = true;
    if (entry || fileName) return;
    let id;
    try { id = window.localStorage.getItem(SELECTION); } catch { return; }
    const saved = jobs.find(job => job.id === id && job.mode === "offline" && job.result_key);
    if (saved) select(saved);
    else if (id) remember(null);
  }, [caps?.manage_history, showResults, historyLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  const selected = jobs.find((job) => job.id === entry?.id);

  const clearSelection = () => {
    revision.current += 1;
    restoreAttempt.current = true;
    remember(null);
    setEntry(null);
    setHanded(null);
    setFileName("");
    setSeek(null);
    setMode("real");
  };

  const manage = async (action, job) => {
    setManaging(true);
    const response = await wbPost(`/workbench/history/${action}`,
      action === "delete" ? { job_id: job.id } : action === "reset" ? { confirm: true } : {}, fetcher);
    setManaging(false);
    if (response.status !== "ok") {
      setError(response.reason ?? "Could not update saved analyses.");
      return false;
    }
    setError("");
    if (action !== "delete" || entry?.id === job.id) clearSelection();
    if (action !== "new") {
      setJobs(list => list.filter(item => action === "reset" ? item.mode !== "offline" : item.id !== job.id));
    }
    refreshHistory(key => key + 1);
    return true;
  };

  const accept = (result, id) => {
    revision.current += 1;
    setEntry({ result, id });
    setFileName(result.processing?.filename ?? result.clip);
    setMode("real");
    setError("");
    if (caps?.manage_history && id) remember(id);
    if (id) setHanded({ status: "ok", data: result,
      videoUrl: caps?.uploads && result.processing?.source !== "camera" ? `/workbench/video/${id}` : null });
  };
  const openFile = (file) => {
    revision.current += 1;
    setMode("real");
    setFileName(file.name);
    setError("");
    if (caps?.manage_history) { restoreAttempt.current = true; remember(null); }
    if (caps?.uploads || (entry && ((entry.result.processing?.filename ?? `${entry.result.clip}.${file.name.split(".").at(-1)}`) !== file.name
        || (entry.result.processing && entry.result.processing.source_size !== file.size)))) {
      setEntry(null);
      setHanded({ status: "empty" });
    }
  };
  const rejectFile = (file, reason) => {
    revision.current += 1;
    setEntry(null);
    setFileName(file.name);
    setMode("real");
    if (caps?.manage_history) { restoreAttempt.current = true; remember(null); }
    setHanded({ status: "empty" });
    if (caps?.history) {
      wbPost("/workbench/rejected", { filename: file.name, size: file.size, reason }, fetcher).then(response => {
        if (response.status !== "ok") setError(response.reason ?? "Could not record the failed file.");
      });
    }
  };
  const openEvent = (time) => {
    setSeek({ time });
    window.location.hash = "#replay";
  };
  const updateAlert = async (jobId, eventId, status) => {
    const response = await wbPost("/workbench/alerts/status", { job_id: jobId, event_id: eventId, status }, fetcher);
    if (response.status !== "ok") {
      setError(response.reason ?? "Could not update the alert");
      return;
    }
    setError("");
    setJobs((list) => list.map((job) => job.id === jobId
      ? { ...job, alert_statuses: { ...job.alert_statuses, [eventId]: status } } : job));
  };
  return { real, setMode, entry, selected, jobs: historyVisible ? jobs : [], historyOpen: historyVisible, historyLoaded,
    browseHistory: caps?.history ? () => setHistoryOpen(true) : null,
    error, offline, fileName, seek, handed, select, accept, openFile, rejectFile, openEvent, updateAlert, manage, managing };
}
