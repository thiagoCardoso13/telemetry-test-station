import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests",
  // there is one tank, so one test at a time
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 20_000 },
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.STATION_URL ?? "http://127.0.0.1:3000",
    // the installed Google Chrome, so no browser has to be downloaded
    channel: "chrome",
    trace: "retain-on-failure",
  },
});
