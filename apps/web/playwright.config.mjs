import {defineConfig, devices} from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  testIgnore: ['**/unit/**'],
  workers: 1,
  retries: 0,
  timeout: 30000,
  reporter: [['list'], ['json', {outputFile: '../../.local/logs/dev/browser-results.json'}]],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.WEB_ORIGIN || 'http://localhost:3000',
    channel: process.env.PLAYWRIGHT_CHANNEL === 'bundled' ? undefined : process.env.PLAYWRIGHT_CHANNEL || undefined,
    trace: 'retain-on-failure',
  },
});
