import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          framework: ["react", "react-dom", "react/jsx-runtime"],
          map: ["maplibre-gl"],
          charts: ["recharts"],
          motion: ["motion"],
        },
      },
    },
  },
});
