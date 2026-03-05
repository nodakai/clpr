import { test, expect } from '@playwright/test';

test('homepage has title', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/AWS Pricing Calculator/i);
});

test('renders header', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('AWS Pricing Calculator');
});

test('displays service filter', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Service')).toBeVisible();
});

test('can toggle dark mode', async ({ page }) => {
  await page.goto('/');
  const toggle = page.getByLabel(/Switch to dark mode/i);
  await toggle.click();
  await expect(page.getByLabel(/Switch to light mode/i)).toBeVisible();
});

test('shows results table after loading', async ({ page }) => {
  await page.goto('/');
  // Wait for results to load (the table should appear)
  await expect(page.locator('table')).toBeVisible({ timeout: 10000 });
});
