import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // `npm run dev` talks to an API running on its usual port
  server: { proxy: { "/api": { target: "http://127.0.0.1:3000", ws: true } } },
});
