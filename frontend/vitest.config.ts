import { defineConfig } from "vitest/config";

// T1: unit tests of the frontend's logic (no browser - the e2e tests drive the real app):
// `npm test`. Files next to what they test: src/**/*.test.ts
export default defineConfig({
  test: { include: ["src/**/*.test.ts"], environment: "node", setupFiles: ["src/test/setup.ts"],
    css: { include: [/index\.css/] } },   // A1: tokens.test.ts reads the tokens (index.css?raw)
});
