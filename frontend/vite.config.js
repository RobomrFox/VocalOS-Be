import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./", // ✅ ensures relative paths work in production (dist build)
  server: {
    host: true, // ✅ allows access via localhost for Electron
    port: 5173, // optional - ensure consistency with your main.js
    open: false,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  optimizeDeps: {
    exclude: ["electron"], // ✅ prevents Electron preload errors
  },
  esbuild: {
    jsxInject: `import React from 'react'`,
  },
});
