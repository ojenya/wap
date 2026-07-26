import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Proxy API + health calls to the FastAPI orchestrator during development.
// The target is env-configurable so the web container can reach the API by its
// compose service name (http://api:8000) while local dev uses localhost.
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
      "/health": { target: apiTarget, changeOrigin: true },
    },
  },
});
