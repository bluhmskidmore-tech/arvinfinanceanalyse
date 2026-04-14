import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Dev proxy target; override if the API runs elsewhere, e.g. `MOSS_VITE_API_PROXY=http://127.0.0.1:8765`. */
const apiTarget = process.env.MOSS_VITE_API_PROXY ?? "http://127.0.0.1:7888";

/** DuckDB / storage bootstrap on first request can be slow; avoid proxy timing out mid-migration. */
const apiProxy = { target: apiTarget, changeOrigin: true, timeout: 120_000 } as const;

export default defineConfig({
  plugins: [react()],
  server: {
    // true：同时监听 IPv4/常见 IPv6，避免浏览器用 http://localhost:5888 时解析到 ::1 却连不上仅绑定 127.0.0.1 的情况
    host: true,
    port: 5888,
    strictPort: true,
    proxy: {
      "/ui": apiProxy,
      "/api": apiProxy,
      "/health": apiProxy,
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return undefined;
          }

          if (
            id.includes("/react/") ||
            id.includes("/react-dom/") ||
            id.includes("/scheduler/") ||
            id.includes("/react-router/") ||
            id.includes("/react-router-dom/") ||
            id.includes("/@remix-run/router/")
          ) {
            return "react-vendor";
          }

          if (
            id.includes("/@tanstack/react-query/") ||
            id.includes("/@tanstack/query-core/")
          ) {
            return "query-vendor";
          }

          if (id.includes("/zrender/")) {
            return "zrender-vendor";
          }

          return undefined;
        },
      },
    },
  },
});
