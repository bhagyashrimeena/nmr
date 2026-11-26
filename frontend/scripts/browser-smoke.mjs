import assert from 'node:assert/strict'
import { mkdirSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '../..')
const env = readFileSync(resolve(root, 'backend/.env'), 'utf8')
const password = process.env.NMR_ADMIN_PASSWORD || env.match(/^NMR_ADMIN_PASSWORD=(.+)$/m)?.[1]?.trim()
if (!password) throw new Error('Set NMR_ADMIN_PASSWORD in backend/.env before browser smoke testing')

const screenshots = resolve(root, 'docs/screenshots')
mkdirSync(screenshots, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.NMR_CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const page = await context.newPage()
const errors = []
page.on('pageerror', error => errors.push(error.message))
const presentationTerms = /\b(?:demo|fictional|synthetic|simulation|simulated|mock|poc|illustrative|hypothetical)\b/i
async function assertOperationalCopy(locator) {
  assert.doesNotMatch(await locator.innerText(), presentationTerms)
}

try {
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' })
  await assertOperationalCopy(page.locator('.login-shell'))
  await page.getByLabel('Username').fill('nmr-admin')
  await page.getByLabel('Password').fill('incorrect-demo-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('alert').getByText('Invalid administrator credentials.').waitFor()
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('heading', { name: 'Overview', level: 1 }).waitFor()
  await page.getByText('Externally accessible').waitFor()
  await assertOperationalCopy(page.locator('.app-shell'))
  await page.screenshot({ path: resolve(screenshots, 'overview.png'), fullPage: true })

  const nav = page.getByRole('navigation', { name: 'Main navigation' })
  for (const [name, marker] of [
    ['Employee Stock Ownership', 'Shares held'],
    ['Corporate Pension', 'Current balance'],
    ['Financial Wellness', 'Recommended reading'],
    ['Trust & Custody', 'Held positions'],
    ['Equity Compensation', 'Award grants'],
  ]) {
    await nav.getByRole('button', { name }).click()
    await page.getByRole('heading', { name, level: 1 }).waitFor()
    await page.getByText(marker).first().waitFor()
    await assertOperationalCopy(page.locator('.app-shell'))
    assert.equal(await page.locator('.subtabs button').count() > 0, true, `${name} has detailed views`)
    if (name === 'Employee Stock Ownership') {
      await page.screenshot({ path: resolve(screenshots, 'stock-ownership.png'), fullPage: true })
      await page.getByRole('tab', { name: 'Purchases' }).click()
      await page.getByLabel('Purchase year').selectOption('2026')
      assert.equal(await page.locator('.section tbody tr').count(), 11)
      await page.getByRole('tab', { name: 'Activity' }).click()
      assert.equal(await page.locator('.section tbody tr').count(), 36)
    }
    if (name === 'Corporate Pension') {
      await page.getByRole('tab', { name: 'Projection' }).click()
      await page.getByLabel('Monthly contribution (JPY)').fill('10000')
      await page.getByLabel('Years').fill('5')
      await page.getByLabel('Annual return assumption (%)').fill('0')
      await page.getByRole('button', { name: 'Calculate' }).click()
      await page.getByText('¥4,100,000').first().waitFor()
    }
    if (name === 'Financial Wellness') {
      await page.screenshot({ path: resolve(screenshots, 'financial-wellness.png'), fullPage: true })
      await page.getByLabel('Topic').selectOption('retirement')
      await page.getByLabel('Search').fill('contribution')
      await page.getByRole('button', { name: 'Apply filters' }).click()
      await page.waitForFunction(() => document.querySelectorAll('.resource').length === 2)
      assert.equal(await page.locator('.resource').count(), 2)
      await page.getByRole('tab', { name: 'Savings calculator' }).click()
      await page.getByLabel('Monthly amount (JPY)').fill('10000')
      await page.getByLabel('Years').fill('10')
      await page.getByLabel('Annual return assumption (%)').fill('0')
      await page.getByRole('button', { name: 'Calculate' }).click()
      await page.getByText('¥1,200,000').first().waitFor()
    }
    if (name === 'Trust & Custody') {
      await page.getByRole('tab', { name: 'Valuations' }).click()
      assert.equal(await page.locator('.section tbody tr').count(), 3)
      await page.getByRole('tab', { name: 'Settlements' }).click()
      await page.getByLabel('Status').selectOption('pending')
      assert.equal(await page.locator('.section tbody tr').count(), 1)
    }
    if (name === 'Equity Compensation') {
      await page.getByRole('tab', { name: 'Vesting' }).click()
      assert.ok(await page.locator('.section tbody tr').count() > 0)
    }
  }

  await nav.getByRole('button', { name: 'Employee Stock Ownership' }).click()
  await page.getByLabel('Employee').selectOption('EMP-003')
  await page.getByText('No stock account is recorded for this employee.').waitFor()
  await page.getByLabel('Employee').selectOption('EMP-001')

  await nav.getByRole('button', { name: 'Corporate Clients' }).click()
  await page.getByRole('heading', { name: 'Corporate Clients', level: 1 }).waitFor()
  await assertOperationalCopy(page.locator('.app-shell'))

  await nav.getByRole('button', { name: 'MCP Access Management' }).click()
  await page.getByRole('heading', { name: 'MCP Access Management', level: 1 }).waitFor()
  assert.equal(await page.locator('.service-access-row').count(), 5)
  await assertOperationalCopy(page.locator('.page-head'))
  await assertOperationalCopy(page.locator('.access-panel'))
  await assertOperationalCopy(page.locator('.service-access-list'))
  await assertOperationalCopy(page.locator('.app-shell'))
  await page.setViewportSize({ width: 1440, height: 1380 })
  await page.screenshot({ path: resolve(screenshots, 'access-management.png') })
  await page.setViewportSize({ width: 1440, height: 900 })

  const token = await page.evaluate(() => sessionStorage.getItem('nmr_admin_token'))
  assert.ok(token)
  const route = 'http://127.0.0.1:8000/api/v1/admin/tenants/toyota-demo/mcp-access'
  const before = await (await page.request.get(route, { headers: { Authorization: `Bearer ${token}` } })).json()
  const stock = before.services.find(service => service.service === 'stock')
  assert.ok(stock)
  const row = page.locator('.service-access-row').filter({ hasText: 'Employee Stock Ownership' })
  try {
    await row.getByRole('button', { name: stock.enabled ? 'Disable service' : 'Enable service' }).click()
    await page.getByRole('status').getByText(/Employee Stock Ownership/).waitFor()
    const changed = await (await page.request.get(route, { headers: { Authorization: `Bearer ${token}` } })).json()
    assert.equal(changed.services.find(service => service.service === 'stock').enabled, !stock.enabled)
  } finally {
    await page.request.patch('http://127.0.0.1:8000/api/v1/admin/tenants/toyota-demo/service-access/stock', {
      headers: { Authorization: `Bearer ${token}` },
      data: { enabled: stock.enabled, reason: 'Restore setting after browser smoke test' },
    })
  }

  await nav.getByRole('button', { name: 'Audit Logs' }).click()
  await page.getByRole('heading', { name: 'Audit Logs', level: 1 }).waitFor()
  await page.getByText('External calls and policy events').waitFor()
  await assertOperationalCopy(page.locator('.app-shell'))
  assert.deepEqual(errors, [])
  console.log('Browser smoke passed: five service screens, access controls, persisted UI toggle, audit screen; screenshots saved')
} finally {
  await browser.close()
}
