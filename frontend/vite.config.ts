import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = "http://127.0.0.1:7888";

export default defineConfig({
  plugins: [react()],
  server: {
    // true：同时监听 IPv4/常见 IPv6，避免浏览器用 http://localhost:5888 时解析到 ::1 却连不上仅绑定 127.0.0.1 的情况
    host: true,
    port: 5888,
    strictPort: true,
    proxy: {
      "/ui": { target: apiTarget, changeOrigin: true },
      "/api": { target: apiTarget, changeOrigin: true },
      "/health": { target: apiTarget, changeOrigin: true },
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

          if (id.includes("/echarts-for-react/")) {
            return "charts-react";
          }

          if (id.includes("/zrender/")) {
            return "zrender-vendor";
          }

          if (id.includes("/echarts/lib/chart/")) {
            return "charts-series";
          }

          if (id.includes("/echarts/lib/component/")) {
            return "charts-components";
          }

          if (
            id.includes("/echarts/lib/coord/") ||
            id.includes("/echarts/lib/feature/")
          ) {
            return "charts-components";
          }

          if (id.includes("/echarts/")) {
            return "charts-core";
          }

          return undefined;
        },
      },
    },
  },
});
