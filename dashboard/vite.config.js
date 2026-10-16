import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served by the FastAPI server at /dashboard (same origin, no CORS). In
// development, Vite proxies the three read-only endpoints to the server.
export default defineConfig({
  base: "/dashboard/",
  plugins: [react()],
  server: {
    proxy: {
      "/count_forecast": "http://127.0.0.1:8000",
      "/prediction": "http://127.0.0.1:8000",
      "/evidence": "http://127.0.0.1:8000",
    },
  },
  test: { environment: "jsdom" },
});
