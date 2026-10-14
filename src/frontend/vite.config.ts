import react from "@vitejs/plugin-react";
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api/v1": {
        target: process.env.VITE_DEV_SERVER_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
        // Append the client address to X-Forwarded-For. Without it the backend
        // sees no header (dev) or a client-supplied one (whenever this dev
        // server is exposed directly, which is how the release kit publishes
        // the UI), and the login rate limit keys on whatever the caller sent.
        xfwd: true,
        rewrite: (path) => path.replace(/^\/api\/v1/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    exclude: ["tests/*.test.mjs"],
    // A non-UTC zone, so tests of "backend timestamps are UTC" fail when a
    // naive timestamp is read as local time (CI runners default to UTC).
    env: { TZ: "Europe/Warsaw" },
  },
});
