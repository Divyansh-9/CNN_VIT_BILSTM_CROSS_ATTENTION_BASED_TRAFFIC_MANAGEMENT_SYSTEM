import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Self-hosted type: bundled with the page, so nothing is fetched from outside.
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "./theme.css";
import Root from "./Root.jsx";
import { AuthGate } from "./AuthGate.jsx";
import { PREVIEW_SITE, fetchPreview, needsSignIn } from "./preview.js";
import { applyTheme, storedTheme } from "./theme.js";

applyTheme(storedTheme());

const operatorView = import.meta.env.VITE_STMS_HOSTED === "1" || needsSignIn(window.location.search, window.location.hash);
const redesign = new URLSearchParams(window.location.search).get("preview") === "redesign";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    {operatorView ? (
      <AuthGate><Root /></AuthGate>
    ) : (
      <Root fetcher={fetchPreview} previewSite={PREVIEW_SITE} redesign={redesign} />
    )}
  </StrictMode>,
);
