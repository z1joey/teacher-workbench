import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  base: "/gao/",
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/gao/api": { target: "http://127.0.0.1:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/gao/, "") },
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
})
