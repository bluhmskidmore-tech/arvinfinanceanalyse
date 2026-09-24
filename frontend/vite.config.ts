import http from "node:http";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/** Dev proxy target; override if the API runs elsewhere, e.g. `MOSS_VITE_API_PROXY=http://127.0.0.1:8765`. */
const apiTarget = process.env.MOSS_VITE_API_PROXY ?? "http://127.0.0.1:7888";

/**
 * Without an explicit agent, http-proxy forces `Connection: close` and opens a
 * fresh TCP connection to the backend for every proxied request (measured: one
 * TIME_WAIT socket per request, ~50ms extra per 18-request page load plus
 * 100-250ms tail spikes). A keep-alive agent lets the proxy reuse connections.
 */
const apiProxyAgent = new http.Agent({ keepAlive: true, maxSockets: 32 });

/** DuckDB / storage bootstrap on first request can be slow; avoid proxy timing out mid-migration. */
const apiProxy = {
  target: apiTarget,
  changeOrigin: true,
  timeout: 120_000,
  agent: apiProxyAgent,
} as const;

function isReactVendorModule(normalizedId: string) {
  return (
    /(?:^|\/)node_modules\/react(?:\/|$)/.test(normalizedId) ||
    /(?:^|\/)node_modules\/react-dom(?:\/|$)/.test(normalizedId) ||
    /(?:^|\/)node_modules\/scheduler(?:\/|$)/.test(normalizedId) ||
    /(?:^|\/)node_modules\/react-router(?:\/|$)/.test(normalizedId) ||
    /(?:^|\/)node_modules\/react-router-dom(?:\/|$)/.test(normalizedId) ||
    /(?:^|\/)node_modules\/@remix-run\/router(?:\/|$)/.test(normalizedId) ||
    /(?:^|\/)node_modules\/\.vite\/deps\/react(?:[._-]|$)/.test(normalizedId) ||
    /(?:^|\/)node_modules\/\.vite\/deps\/react-dom(?:[._-]|$)/.test(normalizedId) ||
    /(?:^|\/)node_modules\/\.vite\/deps\/react_jsx-(?:dev-)?runtime(?:[._-]|$)/.test(normalizedId) ||
    /(?:^|\/)node_modules\/\.vite\/deps\/scheduler(?:[._-]|$)/.test(normalizedId) ||
    /\0(?:commonjs-proxy:)?react(?:[/?]|$)/.test(normalizedId) ||
    /\0(?:commonjs-proxy:)?react-dom(?:[/?]|$)/.test(normalizedId) ||
    /\0(?:commonjs-proxy:)?scheduler(?:[/?]|$)/.test(normalizedId)
  );
}

function getHomeStartupChunkName(id: string) {
  const normalizedId = id.split("\\").join("/");

  if (isReactVendorModule(normalizedId)) {
    return "react-vendor";
  }

  if (
    normalizedId.includes("/ag-grid-react/") ||
    normalizedId.includes("/ag-grid-community/")
  ) {
    return undefined;
  }

  if (!normalizedId.includes("node_modules")) {
    return undefined;
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

  return "vendor-misc";
}

export default defineConfig({
  plugins: [tailwindcss(), react()],
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
        codeSplitting: {
          includeDependenciesRecursively: false,
          groups: [
            {
              name: getHomeStartupChunkName,
            },
          ],
        },
      },
    },
  },
});
