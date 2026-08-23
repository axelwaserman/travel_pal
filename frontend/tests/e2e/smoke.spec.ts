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

test('flight lookup search + carrier tab + airport drill-down + panel close', async ({ page }) => {
  await page.goto('/')

  // ------------------------------------------------------------------
  // 1. Airport search: type "JFK", click Search, expect ≥1 result card
  // ------------------------------------------------------------------
  await page.getByRole('textbox', { name: /flight route or airport/i }).fill('JFK')
  await page.getByRole('button', { name: 'Search' }).click()

  // Wait for DuckDB-WASM to respond — parquet fetch can take several seconds
  await page.waitForFunction(
    () => document.querySelectorAll('.result-card').length > 0,
    { timeout: 20_000 }
  )
  expect(await page.locator('.result-card').count()).toBeGreaterThan(0)

  // ------------------------------------------------------------------
  // 2. Switch to Carriers tab — URL should reflect the tab change
  // ------------------------------------------------------------------
  await page.getByRole('tab', { name: 'Carriers' }).click()
  await expect(page).toHaveURL(/tab=carriers/, { timeout: 5000 })

  // Search for a carrier on the Carriers tab
  await page.getByRole('textbox', { name: /flight route or airport/i }).fill('DAL')
  await page.getByRole('button', { name: 'Search' }).click()

  await page.waitForFunction(
    () => document.querySelectorAll('.result-card').length > 0,
    { timeout: 20_000 }
  )
  expect(await page.locator('.result-card').count()).toBeGreaterThan(0)

  // Note: carrier cards do NOT open the route panel (no result-card--clickable).
  // The drill-down flow is airport-only — switch back to test it.

  // ------------------------------------------------------------------
  // 3. Switch back to Airports tab and search again to populate clickable cards
  // ------------------------------------------------------------------
  await page.getByRole('tab', { name: 'Airports' }).click()

  await page.getByRole('textbox', { name: /flight route or airport/i }).fill('JFK')
  await page.getByRole('button', { name: 'Search' }).click()

  await page.waitForFunction(
    () => document.querySelectorAll('.result-card--clickable').length > 0,
    { timeout: 20_000 }
  )

  // Click the first clickable airport result card to open the drill-down panel
  await page.locator('.result-card--clickable').first().click()

  // Panel should appear and URL should contain ?route=XXXX-YYYY
  await expect(page.locator('.route-panel')).toBeVisible({ timeout: 10_000 })
  await expect(page).toHaveURL(/route=[A-Z]{3,4}-[A-Z]{3,4}/, { timeout: 5000 })

  // ------------------------------------------------------------------
  // 4. Close panel via Escape — panel unmounts and ?route= is cleared
  // ------------------------------------------------------------------
  await page.keyboard.press('Escape')
  await expect(page.locator('.route-panel')).toHaveCount(0, { timeout: 5000 })
  await expect(page).not.toHaveURL(/route=/, { timeout: 5000 })
})
