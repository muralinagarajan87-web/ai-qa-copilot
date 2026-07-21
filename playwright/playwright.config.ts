import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'html',
  use: {
    // Defaults to the current demo target (SauceDemo, a public QA practice
    // site) so generated tests are runnable out of the box. Override with
    // BASE_URL when pointing at a different application.
    baseURL: process.env.BASE_URL || 'https://www.saucedemo.com',
    trace: 'on-first-retry',
    // SauceDemo uses `data-test`, not Playwright's default `data-testid`.
    // Revisit this if/when a second real application with a different
    // convention is targeted alongside it.
    testIdAttribute: 'data-test',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
