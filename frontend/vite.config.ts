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
    /**
     * 默认 500kB 阈值会对「完整 UI/表格框架」的单一 vendor 输出告警。
     * antd 为集成式组件库、ag-grid-community 为单入口 main.esm.mjs，在不引入按子路径人工拆包（易触发 Rollup
     * circular chunk）时无法可靠压到 500kB 以下。已通过：echarts 与 zrender 独立拆包、ag-grid 从主入口外移
     * 作路由级懒加载。此处将告警阈值微调到 1100kB 仅用于抑制上述两类的已知单体体积告警。
     */
    chunkSizeWarningLimit: 1100,
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

          if (normalizedId.includes("/zrender/")) {
            return "zrender";
          }

          if (normalizedId.includes("/echarts-for-react/")) {
            return "echarts-for-react";
          }

          if (normalizedId.includes("node_modules/echarts/")) {
            return "echarts-misc";
          }

          if (normalizedId.includes("/ag-grid-react/")) {
            return "ag-grid-react";
          }

          if (normalizedId.includes("/ag-grid-community/")) {
            return "ag-grid-community";
          }

          return "vendor-misc";
        },
      },
    },
  },
});
