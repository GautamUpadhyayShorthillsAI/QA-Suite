import { test, expect } from '@playwright/test';

test('Written with DeploySentinel Recorder', async ({ page }) => {
  // Load "https://valueinsightpro.jumpiq.com/auth/login?redirect=/"
  await page.goto('https://valueinsightpro.jumpiq.com/auth/login?redirect=/');

  // Resize window to 1920 x 966
  await page.setViewportSize({ width: 1920, height: 966 });

  // Click on <input> [data-testid="company-email-input"]
  await page.click('[data-testid="company-email-input"]');

  // Fill "test3" on <input> [data-testid="company-email-input"]
  await page.fill('[data-testid="company-email-input"]', "test3");

  // Click on <input> [data-testid="password-input"]
  await page.click('[data-testid="password-input"]');

  // Fill "value@123" on <input> [data-testid="password-input"]
  await page.fill('[data-testid="password-input"]', "value@123");

  // Click on <input> .ant-checkbox-input
  await page.click('.ant-checkbox-input');

  // Click on <button> "Sign In"
  await Promise.all([
    page.click('button'),
    page.waitForNavigation()
  ]);

  // Click on <input> .ant-input-compact-first-item
  await page.click('.ant-input-compact-first-item');

  // Fill "9" on <input> .ant-input-compact-first-item
  await page.fill('.ant-input-compact-first-item', "9");

  // Fill "9" on <input> .ant-input:nth-child(2)
  await page.fill('.ant-input:nth-child(2)', "9");

  // Fill "9" on <input> .ant-input:nth-child(3)
  await page.fill('.ant-input:nth-child(3)', "9");

  // Fill "9" on <input> .ant-input:nth-child(4)
  await page.fill('.ant-input:nth-child(4)', "9");

  // Fill "9" on <input> .ant-input-compact-last-item
  await page.fill('.ant-input-compact-last-item', "9");

  // Click on <button> "Verify"
  await Promise.all([
    page.click('.ant-btn-default'),
    page.waitForNavigation()
  ]);

  // Click on <div> "Instant Report"
  await page.click('.card:nth-child(1) > .overlay');

  // Click on <input> #home_screen_new_val_drop_down
  await page.click('#home_screen_new_val_drop_down');

  // Click on <div> "1 BROOKVILLE CHEVROLET-Ch..."
  await page.click('.ant-select-item-option-active > .ant-select-item-option-content');

  // Click on <span> "Next"
  await Promise.all([
    page.click('text=Next'),
    page.waitForNavigation()
  ]);

  // Click on <span> "Exit"
  await Promise.all([
    page.click('text=Exit'),
    page.waitForNavigation()
  ]);
});