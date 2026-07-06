// @ts-check
const { defineConfig, devices } = require("@playwright/test");

const baseURL =
  process.env.BASE_URL ||
  process.env.SERVER_URL ||
  "https://staging.example.com";

module.exports = defineConfig({
  testDir: "./specs",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
