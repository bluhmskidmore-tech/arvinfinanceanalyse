import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
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
