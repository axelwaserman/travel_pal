import { test, expect } from '@playwright/test'

test('frontend loads with airport heading', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'TravelPal' })).toBeVisible()
})

test('flight lookup form is interactable', async ({ page }) => {
  await page.goto('/')
  const search = page.getByRole('textbox').first()
  await expect(search).toBeVisible()
  await search.fill('AA100')
  await expect(search).toHaveValue('AA100')
})
