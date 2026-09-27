import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { PLAY_ID_PATTERN, resolveOfficialClip } from "./privateVideoResolver.ts";

export default defineConfig(({ mode }) => ({
  // Available only while running the private app on localhost with Vite.
  plugins: [react(), ...(mode === "private" ? [{
    name: "private-official-video",
    configureServer(server: { middlewares: { use: (path: string, handler: (req: import("node:http").IncomingMessage, res: import("node:http").ServerResponse) => void) => void } }) {
      const cache = new Map<string, string>();
      const pending = new Map<string, Promise<string | null>>();
      server.middlewares.use("/__private_video_source", (req, res) => {
        const playId = new URL(req.url ?? "", "http://localhost").searchParams.get("playId") ?? "";
        res.setHeader("Cache-Control", "no-store");
        res.setHeader("Content-Type", "application/json");
        if (req.method !== "GET" || !PLAY_ID_PATTERN.test(playId)) {
          res.statusCode = 400;
          res.end("{}");
          return;
        }
        const cached = cache.get(playId);
        if (cached) {
          res.end(JSON.stringify({ url: cached }));
          return;
        }
        let work = pending.get(playId);
        if (!work) {
          work = resolveOfficialClip(playId).catch(() => null).finally(() => pending.delete(playId));
          pending.set(playId, work);
        }
        void work.then((url) => {
          if (url) {
            cache.set(playId, url);
            if (cache.size > 256) cache.delete(cache.keys().next().value!);
            res.end(JSON.stringify({ url }));
          } else {
            res.statusCode = 404;
            res.end("{}");
          }
        });
      });
    },
  }] : [])],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      reportsDirectory: "./coverage",
    },
  },
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
  },
}));
