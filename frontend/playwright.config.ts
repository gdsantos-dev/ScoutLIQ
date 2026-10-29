import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  expect: { timeout: 10000 },
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/playwright-report", open: "never" }],
  ],
  outputDir: "../artifacts/test-results",
  use: {
    baseURL: process.env.E2E_ORIGIN || "http://localhost:8001",
    browserName: "chromium",
    channel: "chrome",
    headless: true,
    locale: "pt-BR",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
