import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const syntheticFile = fileURLToPath(new URL('../../synthetic-mutual-nda.docx', import.meta.url));

test('local UI can review synthetic NDA and download an approved snapshot', async ({page}) => {
  await page.goto('/');
  await expect(page.getByText('LOCAL • SYNTHETIC DATA ONLY')).toBeVisible();
  await page.getByLabel('New matter name').fill('Browser E2E synthetic NDA');
  await page.getByRole('button', {name: /Create matter/}).click();
  await expect(page.getByRole('heading', {name: 'Start with a source document'})).toBeVisible();

  await page.getByLabel('Select synthetic NDA document').setInputFiles(syntheticFile);
  await page.getByRole('button', {name: 'Upload synthetic document'}).click();
  await expect(page.getByRole('heading', {name: 'Confirm the review scope'})).toBeVisible();
  await page.getByRole('button', {name: 'Verify scope'}).click();
  await expect(page.getByText('Scope accepted for this technical demo.')).toBeVisible();
  await page.getByRole('button', {name: 'Run synthetic review checks'}).click();
  await expect(page.getByRole('heading', {name: 'Review queue'})).toBeVisible();
  await expect(page.locator('.finding-card')).toHaveCount(3);
  await expect(page.getByRole('button', {name: 'Record simulated approval'})).toBeDisabled();

  for (let index = 0; index < 3; index++) {
    const card = page.locator('.finding-card').nth(index);
    await card.click();
    await page.locator('.decision-actions').getByRole('button', {name: 'accepted', exact: true}).click();
    await expect(card).toContainText('accepted');
  }
  const approvalButton = page.getByRole('button', {name: 'Record simulated approval'});
  await expect(approvalButton).toBeEnabled();
  page.once('dialog', dialog => void dialog.accept());
  await approvalButton.click();
  await expect(page.getByText('Simulated approval recorded', {exact: true})).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Export report (DOCX)'}).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('synthetic-review-report.docx');
  await expect(page.getByText('Demo report created')).toBeVisible();
});

test('mobile viewport shows explicit disclaimer and a working creation flow', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/');
  await expect(page.getByText(/NOT LEGAL ADVICE/)).toBeVisible();
  await expect(page.getByRole('button', {name: /Create matter/})).toBeVisible();
  await expect(page.getByLabel('Demo user identity')).toBeVisible();
});
