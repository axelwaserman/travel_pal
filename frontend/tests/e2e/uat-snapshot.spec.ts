import { test, expect } from '@playwright/test'

/**
 * UAT snapshot — runs ad-hoc to capture full-page screenshot + per-section DOM
 * dumps + per-section screenshots, then prints text content of each section
 * so the controlling agent can verify rendering without a browser.
 *
 * Not part of the smoke suite. Skipped unless TRAVELPAL_UAT_SNAPSHOT=1.
 */
test.describe.configure({ mode: 'serial' })

test('full-page UAT snapshot', async ({ page }) => {
  test.skip(
    process.env.TRAVELPAL_UAT_SNAPSHOT !== '1',
    'UAT snapshot only runs when TRAVELPAL_UAT_SNAPSHOT=1'
  )

  const consoleErrors: string[] = []
  page.on('pageerror', e => consoleErrors.push(`pageerror: ${e.message}`))
  page.on('console', m => {
    if (m.type() === 'error') consoleErrors.push(`console.error: ${m.text()}`)
  })

  await page.goto('/', { waitUntil: 'networkidle' })

  await expect(page.locator('h1', { hasText: 'TravelPal' })).toBeVisible()
  await expect(page.locator('.cancellation-section svg')).toHaveCount(2, {
    timeout: 20_000,
  })

  await page.screenshot({
    path: 'test-results/uat-fullpage.png',
    fullPage: true,
  })

  const sections = ['historic-timeliness', 'flight-lookup', 'cancellations']
  for (const slug of sections) {
    const sec = page.locator(`section[aria-labelledby*="${slug}"]`).first()
    if ((await sec.count()) === 0) continue
    await sec.screenshot({ path: `test-results/uat-${slug}.png` })
    const text = (await sec.innerText()).split('\n').slice(0, 20).join(' | ')
    console.log(`SECTION[${slug}]: ${text}`)
  }

  const cancellationText = await page
    .locator('.cancellation-section')
    .innerText()
  console.log('CANCELLATION_TEXT:', cancellationText)

  const svgCount = await page.locator('.cancellation-section svg').count()
  console.log('CANCELLATION_SVG_COUNT:', svgCount)

  // ------------------------------------------------------------------
  // Flight Lookup search + RoutePanel drill-down snapshot
  // ------------------------------------------------------------------
  await page.getByRole('textbox', { name: /flight route or airport/i }).fill('JFK')
  await page.getByRole('button', { name: 'Search' }).click()

  // Wait for result cards to appear (DuckDB-WASM fetch)
  await page.waitForFunction(
    () => document.querySelectorAll('.result-card--clickable').length > 0,
    { timeout: 20_000 }
  )

  const firstCard = page.locator('.result-card--clickable').first()
  await firstCard.click()

  // Wait for the panel slide-in and at least one sub-section to render
  await expect(page.locator('.route-panel')).toBeVisible({ timeout: 10_000 })
  // Allow sub-charts to settle (loading spinner → chart or empty state)
  await page.waitForTimeout(3000)

  await page.screenshot({
    path: 'test-results/uat-route-panel.png',
    fullPage: true,
  })

  const panelText = (await page.locator('.route-panel').innerText())
    .split('\n')
    .slice(0, 30)
    .join(' | ')
  console.log('ROUTE_PANEL_TEXT:', panelText)

  // Close the panel before final console-error assertion
  await page.keyboard.press('Escape')
  await expect(page.locator('.route-panel')).toHaveCount(0, { timeout: 5000 })

  console.log('CONSOLE_ERRORS:', JSON.stringify(consoleErrors))
  expect(consoleErrors).toEqual([])
})
