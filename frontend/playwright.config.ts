import { defineConfig, devices } from '@playwright/test'

const PORT = 8765

/**
 * E2E runs against the production-style setup: the built SPA served by the
 * real backend, with a throwaway data directory.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run build && cd ../backend && rm -rf ../frontend/.e2e-data && GAMEBOOK_DATA_DIR=../frontend/.e2e-data GAMEBOOK_FRONTEND_DIST=../frontend/dist uv run gamebook serve --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
