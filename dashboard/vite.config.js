import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served by the FastAPI server at /dashboard (same origin, no CORS). In
// development, Vite proxies the read-only endpoints to the server.
export default defineConfig({
  base: "/dashboard/",
  plugins: [react()],
  server: {
    proxy: {
      "/count_forecast": "http://127.0.0.1:8000",
      "/prediction": "http://127.0.0.1:8000",
      "/vehicle_count": "http://127.0.0.1:8000",
      "/heartbeat": "http://127.0.0.1:8000",
      "/forecast_check": "http://127.0.0.1:8000",
      "/sites": "http://127.0.0.1:8000",
      "/evidence": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      // Sign-in (server/auth.py). The server checks Origin against Host, so keep the
      // browser's Host: the session cookie then belongs to this dev page.
      "/auth": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  test: { environment: "jsdom" },
});
