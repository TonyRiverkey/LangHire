/// <reference types="vitest/config" />
import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";

const dataDir = process.env.LANGHIRE_DATA_DIR || (process.platform === "win32"
  ? path.join(process.env.APPDATA || path.join(homedir(), "AppData/Roaming"), "langhire")
  : path.join(homedir(), process.platform === "darwin" ? "Library/Application Support/langhire" : ".config/langhire"));
const backendPort = Number(process.env.VITE_DEV_BACKEND_PORT) || 8743;

// Single version source: package.json (tauri.conf.json also reads it).
const pkg = JSON.parse(
  readFileSync(path.resolve(__dirname, "package.json"), "utf-8"),
) as { version: string };

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [react(), tailwindcss()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
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
    proxy: {
      "/api": {
        target: "http://127.0.0.1:" + backendPort,
        rewrite: (url) => url.replace(/^\/api/, ""),
        configure: (proxy) => {
          proxy.on("proxyReq", (request) => {
            // Read the current token on the dev server so it survives backend restarts.
            try {
              const token = readFileSync(path.join(dataDir, ".api_token"), "utf8").trim();
              request.setHeader("Authorization", "Bearer " + token);
            } catch {
              request.removeHeader("Authorization");
            }
          });
        },
      } satisfies ProxyOptions,
    },
    strictPort: true,
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
