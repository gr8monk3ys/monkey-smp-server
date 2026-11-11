// The browser checks (`bun run test:a11y`): every built page in a real Chrome at phone and desktop width, with
// axe-core's WCAG A/AA rules, the same guard lscaturchio.xyz runs. They read the built site in out/, so run
// `bun run build` first (tools/checks.py site does). They use the Chrome already on the machine (the GitHub
// runners have it), so nothing downloads a browser; PW_CHANNEL picks another (msedge, or "" for Playwright's own).
import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PW_PORT ?? 4317);
const channel = process.env.PW_CHANNEL ?? "chrome";

export default defineConfig({
  testDir: "./e2e",
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    ...(channel ? { channel } : {}),
    // The pages start every block in place under reduced motion, so what axe reads is what a reader sees.
    contextOptions: { reducedMotion: "reduce" },
  },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], ...(channel ? { channel } : {}) } },
    { name: "desktop", use: { ...devices["Desktop Chrome"], ...(channel ? { channel } : {}) } },
  ],
  webServer: {
    command: `bun e2e/serve.ts ${PORT}`,
    url: `http://127.0.0.1:${PORT}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
