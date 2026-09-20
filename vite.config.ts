import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  root: "frontend",
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  build: {
    outDir: "../splunk_actionstack/appserver/static",
    emptyOutDir: false,
    lib: {
      entry: "src/main.tsx",
      name: "ActionStack",
      formats: ["iife"],
      fileName: () => "actionstack.js",
      cssFileName: "actionstack",
    },
  },
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
});
