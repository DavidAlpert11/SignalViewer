import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";

/* The 3D view (CesiumJS) needs its web workers and a few data files next to the page, under
   /cesium/. They are copied from node_modules into the build - nothing is fetched from the
   internet. Left out: sky / moon textures (switched off in the app) and the celestial data used
   only for space views. */
const CESIUM = join("node_modules", "cesium", "Build", "Cesium");
let outDir = "dist";
const cesiumFiles = (): Plugin => ({
  name: "sv-cesium-files",
  apply: "build",
  configResolved(c) { outDir = c.build.outDir; },          // (into the build's own output folder)
  closeBundle() {
    const out = join(outDir, "cesium");
    for (const part of ["Workers", "ThirdParty", join("Assets", "approximateTerrainHeights.json"), join("Assets", "Images"),
      join("Widgets", "CesiumWidget")]) {
      const src = join(CESIUM, part);
      if (!existsSync(src)) continue;
      mkdirSync(dirname(join(out, part)), { recursive: true });
      cpSync(src, join(out, part), { recursive: true });
    }
  },
});

// `npm run dev`: start the backend first with `python run.py --port 8765 --no-open`.
export default defineConfig({
  plugins: [react(), cesiumFiles()],
  // The engines the app is built for: offline computers often keep an old Edge WebView2 / Edge /
  // Chrome for years, and code built for newer engines does not even start there (a blank window).
  // Chromium 87 (late 2020) is the floor - run.py checks the same number (MIN_CHROMIUM) and
  // polyfills.ts adds the few newer functions the code and CesiumJS call.
  build: { target: ["es2020", "chrome87", "edge88", "firefox78", "safari14"],
    cssTarget: ["chrome87", "edge88", "firefox78", "safari14"] },
  // CesiumJS: its ready-built bundle (its ES sources re-export internals the bundler cannot resolve)
  // (SV_CESIUM_UNMINIFIED=1: its readable build, for profiling)
  resolve: { alias: [{ find: /^cesium$/, replacement: join(process.cwd(), process.env.SV_CESIUM_UNMINIFIED
    ? join("node_modules", "cesium", "Build", "CesiumUnminified") : CESIUM, "index.js") }] },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
