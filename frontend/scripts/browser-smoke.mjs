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
      await page.getByRole('tab', { name: 'Plan operations' }).click()
      await page.getByText('Shareholding plan').last().waitFor()
      await page.getByRole('tab', { name: 'Payroll batches' }).click()
      await page.getByRole('cell', { name: 'REJECTED' }).waitFor()
      await page.getByRole('tab', { name: 'Transfer requests' }).click()
      await page.getByText('TR-001').first().waitFor()
      await page.getByRole('tab', { name: 'Exceptions' }).click()
      await page.getByText('BREAK-STOCK-001').waitFor()
      await assertOperationalCopy(page.locator('.app-shell'))
      await page.screenshot({ path: resolve(screenshots, 'stock-operations.png'), fullPage: true })
    }
    if (name === 'Corporate Pension') {
      await page.getByRole('tab', { name: 'Projection' }).click()
      await page.getByLabel('Monthly contribution (JPY)').fill('10000')
      await page.getByLabel('Years').fill('5')
      await page.getByLabel('Annual return assumption (%)').fill('0')
      await page.getByRole('button', { name: 'Calculate' }).click()
      await page.getByText('¥4,100,000').first().waitFor()
      await page.getByRole('tab', { name: 'Plan operations' }).click()
      await page.getByText('Corporate pension plan').waitFor()
      await page.getByRole('tab', { name: 'Fund positions' }).click()
      await page.getByText('Domestic equity index').waitFor()
      await page.getByRole('tab', { name: 'Instruction queue' }).click()
      await page.getByText('PEN-INST-001').waitFor()
      await page.getByRole('tab', { name: 'Exceptions' }).click()
      await page.getByText('BREAK-PEN-001').waitFor()
      await assertOperationalCopy(page.locator('.app-shell'))
      await page.screenshot({ path: resolve(screenshots, 'pension-operations.png'), fullPage: true })
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
      await page.getByRole('tab', { name: 'Program overview' }).click()
      await page.getByText('Published content').waitFor()
      await page.getByRole('tab', { name: 'Content library' }).click()
      await page.getByText('ED-DRAFT-01').waitFor()
      await page.getByRole('tab', { name: 'Benefit rules' }).click()
      await page.getByText('TOYOTA-SHARE-01/RULES/2026').waitFor()
      await page.getByRole('tab', { name: 'Seminars' }).click()
      await page.getByText('SEM-TOYOTA-01').waitFor()
      await assertOperationalCopy(page.locator('.app-shell'))
      await page.screenshot({ path: resolve(screenshots, 'wellness-operations.png'), fullPage: true })
    }
    if (name === 'Trust & Custody') {
      await page.getByRole('tab', { name: 'Valuations' }).click()
      assert.equal(await page.locator('.section tbody tr').count(), 3)
      await page.getByRole('tab', { name: 'Settlements' }).click()
      await page.getByLabel('Status').selectOption('pending')
      assert.equal(await page.locator('.section tbody tr').count(), 1)
      await page.getByRole('tab', { name: 'Account registry' }).click()
      await page.getByText('Custody accounts').waitFor()
      await page.getByRole('tab', { name: 'Position detail' }).click()
      await page.getByText('Pending transfer units').waitFor()
      await page.getByRole('tab', { name: 'Dividend processing' }).click()
      await page.getByText('CU-DIV-SCHEDULED').waitFor()
      await page.getByRole('tab', { name: 'Action register' }).click()
      await page.getByText('CU-SPLIT-001').waitFor()
      await page.getByRole('tab', { name: 'Settlement monitor' }).click()
      await page.getByText('TR-001').first().waitFor()
      await assertOperationalCopy(page.locator('.app-shell'))
      await page.screenshot({ path: resolve(screenshots, 'custody-operations.png'), fullPage: true })
    }
    if (name === 'Equity Compensation') {
      await page.getByRole('tab', { name: 'Vesting', exact: true }).click()
      assert.ok(await page.locator('.section tbody tr').count() > 0)
      await page.getByRole('tab', { name: 'Equity plan' }).click()
      await page.getByText('Remaining reserve').waitFor()
      await page.getByRole('tab', { name: 'Grant register' }).click()
      await page.getByText('G-PROPOSED-001').waitFor()
      await page.getByRole('tab', { name: 'Vesting schedule' }).click()
      await page.getByText('G-001').first().waitFor()
      await page.getByRole('tab', { name: 'Release queue' }).click()
      await page.getByText('REL-G-001').waitFor()
      await page.getByRole('tab', { name: 'Equity exceptions' }).click()
      await page.getByText('EQ-CASE-001').waitFor()
      await assertOperationalCopy(page.locator('.app-shell'))
      await page.screenshot({ path: resolve(screenshots, 'equity-operations.png'), fullPage: true })
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
