import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
    // Em desenvolvimento, o servidor Python corre na porta 7860.
    proxy: { "/api": { target: "http://localhost:7860", changeOrigin: true } },
  },
});
