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

          if (id.includes("@tanstack/react-query")) {
            return "query-vendor";
          }

          if (id.includes("@ant-design/icons")) {
            return "ant-icons";
          }

          return undefined;
        },
      },
    },
  },
});
