import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Served by the FastAPI server at /dashboard (same origin, no CORS). In
// development, Vite proxies requests to the configured server.
export default defineConfig(({ mode }) => {
  const backend = loadEnv(mode, process.cwd(), "STMS_DEV_API_ORIGIN").STMS_DEV_API_ORIGIN ?? "http://127.0.0.1:8000";
  return {
    base: "/dashboard/",
    plugins: [react()],
    server: {
      proxy: {
        "/count_forecast": backend,
        "/prediction": backend,
        "/vehicle_count": backend,
        "/heartbeat": backend,
        "/forecast_check": backend,
        "/sites": backend,
        "/evidence": backend,
        "/health": backend,
        // Sign-in (server/auth.py). The server checks Origin against Host, so keep the
        // browser's Host: the session cookie then belongs to this dev page.
        "/auth": { target: backend, changeOrigin: false },
        "/workbench": { target: backend, changeOrigin: false },
      },
    },
    test: { environment: "jsdom" },
  };
});
