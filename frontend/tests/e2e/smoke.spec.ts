import { test, expect } from '@playwright/test'

test('landing page loads with all three sections', async ({ page }) => {
  await page.goto('/')

  await expect(page.locator('h1', { hasText: 'TravelPal' })).toBeVisible()
  await expect(
    page.getByRole('heading', { level: 2, name: /historic timeliness/i })
  ).toBeVisible({ timeout: 15000 })
  await expect(
    page.getByRole('heading', { level: 2, name: 'Flight Lookup' })
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { level: 2, name: /cancellations/i })
  ).toBeVisible({ timeout: 15000 })

  // Highcharts renders an SVG per chart (Carriers + Routes). Cancellation
  // fixtures must be uploaded to SeaweedFS frontend-exports/{airport}/ for this
  // assertion to pass — the E2E CI workflow uploads the stub parquets from
  // pipeline/tests/fixtures/{carrier,route}_cancellations.parquet.
  await expect(page.locator('.cancellation-section svg')).toHaveCount(2, {
    timeout: 15000,
  })
})

test('no console errors on first load', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', m => {
    if (m.type() === 'error') errors.push(m.text())
  })
  await page.goto('/', { waitUntil: 'networkidle' })
  await page.waitForTimeout(3000)
  expect(errors, errors.join('\n')).toEqual([])
})
