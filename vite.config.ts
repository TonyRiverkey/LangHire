/// <reference types="vitest/config" />
import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";

const dataDir = path.join(homedir(), process.platform === "win32"
  ? "AppData/Roaming/langhire"
  : process.platform === "darwin" ? "Library/Application Support/langhire" : ".config/langhire");

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Vite options tailored for Tauri development
  clearScreen: false,
  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8743",
        rewrite: (url) => url.replace(/^\/api/, ""),
        configure: (proxy) => {
          proxy.on("proxyReq", (request) => {
            // Keep the backend token on the server and reread it after backend restarts.
            try {
              request.setHeader("Authorization", `Bearer ${readFileSync(path.join(dataDir, ".api_token"), "utf8").trim()}`);
            } catch {
              request.removeHeader("Authorization");
            }
          });
        },
      } satisfies ProxyOptions,
    },
    watch: {
      ignored: ["**/backend/**"],
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "text-summary", "html", "lcov"],
      reportsDirectory: "./coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.{test,spec}.{ts,tsx}",
        "src/test/**",
        "src/main.tsx",
        "src/vite-env.d.ts",
        "src/**/*.d.ts",
        "src/locales/**",
        "src/i18n/**",
      ],
    },
  },
}));
