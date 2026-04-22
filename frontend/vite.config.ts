import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Dev proxy target; override if the API runs elsewhere, e.g. `MOSS_VITE_API_PROXY=http://127.0.0.1:8765`. */
const apiTarget = process.env.MOSS_VITE_API_PROXY ?? "http://127.0.0.1:7888";

/** DuckDB / storage bootstrap on first request can be slow; avoid proxy timing out mid-migration. */
const apiProxy = { target: apiTarget, changeOrigin: true, timeout: 120_000 } as const;

export default defineConfig({
  plugins: [react()],
  /** `vite preview` does not inherit `server.proxy` unless mirrored here — without it, `/api` and `/ui` hit the static server and return 404. */
  preview: {
    host: true,
    port: 5888,
    strictPort: true,
    proxy: {
      "/ui": apiProxy,
      "/api": apiProxy,
      "/health": apiProxy,
    },
  },
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
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.split("\\").join("/");

          if (!normalizedId.includes("node_modules")) {
            return undefined;
          }

          if (
            normalizedId.includes("/react/") ||
            normalizedId.includes("/react-dom/") ||
            normalizedId.includes("/scheduler/") ||
            normalizedId.includes("/react-router/") ||
            normalizedId.includes("/react-router-dom/") ||
            normalizedId.includes("/@remix-run/router/")
          ) {
            return "react-vendor";
          }

          if (
            normalizedId.includes("/@tanstack/react-query/") ||
            normalizedId.includes("/@tanstack/query-core/")
          ) {
            return "query-vendor";
          }

          if (
            normalizedId.includes("/antd/") ||
            normalizedId.includes("/@ant-design/") ||
            normalizedId.includes("/@rc-component/") ||
            normalizedId.includes("/rc-")
          ) {
            return "antd-vendor";
          }

          if (normalizedId.includes("/echarts-for-react/")) {
            return "echarts-vendor";
          }

          if (
            normalizedId.includes("/echarts/") ||
            normalizedId.includes("/zrender/")
          ) {
            return "echarts-vendor";
          }

          if (
            normalizedId.includes("/ag-grid-community/") ||
            normalizedId.includes("/ag-grid-react/")
          ) {
            return "ag-grid-vendor";
          }

          return "vendor-misc";
        },
      },
    },
  },
});
