import { useEffect, useState } from "react";
import App from "./App.jsx";
import { Explorer } from "./Explorer.jsx";
import { Landing } from "./Landing.jsx";

// Three experiences, chosen by the address, with the console unchanged inside:
//
//   #home, or no hash at all       the landing page
//   #explore, #explore/<topic>     the project explorer
//   anything else                  the console (App), which reads its own section
//
// An address that already names an intersection or a handed-over analysis
// (?id=..., ?analysis=...) is someone operating the system, such as the local
// workbench opening /dashboard/?id=live. It goes straight to the console, as it
// always did, and only a bare /dashboard/ opens the landing page.
const EXPLORE = /^explore(?:\/([a-z0-9-]+))?$/;
const PIPELINE = /^explore\/pipeline\/(camera|detection|counts|forecast|dashboard)$/;

export function routeOf(hash, search = "") {
  const raw = String(hash || "").replace(/^#\/?/, "");
  const stage = PIPELINE.exec(raw);
  if (stage) return { page: "explore", topic: null, stage: stage[1] };
  const topic = EXPLORE.exec(raw);
  if (topic) return { page: "explore", topic: topic[1] ?? null };
  if (raw === "home") return { page: "home" };
  if (raw === "") {
    const params = new URLSearchParams(search);
    return params.has("id") || params.has("analysis") ? { page: "console" } : { page: "home" };
  }
  return { page: "console" };
}

function useRoute() {
  const [route, setRoute] = useState(() => routeOf(window.location.hash, window.location.search));
  useEffect(() => {
    const follow = () => setRoute(routeOf(window.location.hash, window.location.search));
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, []);
  return route;
}

export default function Root({ fetcher, previewSite, redesign }) {
  const route = useRoute();
  // A new page starts at its top; moving between explorer topics is handled there.
  useEffect(() => { window.scrollTo?.(0, 0); }, [route.page]);
  if (route.page === "home") return <Landing redesign />;
  if (route.page === "explore") return <Explorer topic={route.topic} stage={route.stage} fetcher={fetcher} />;
  return <App fetcher={fetcher} previewSite={previewSite} redesign={redesign} />;
}
