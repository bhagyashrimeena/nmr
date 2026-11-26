import assert from 'node:assert/strict'
import { existsSync, mkdirSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '../..')
const envPath = resolve(root, 'backend/.env')
const env = existsSync(envPath) ? readFileSync(envPath, 'utf8') : ''
const password = process.env.NMR_ADMIN_PASSWORD || env.match(/^NMR_ADMIN_PASSWORD=(.+)$/m)?.[1]?.trim()
if (!password) throw Error('Set NMR_ADMIN_PASSWORD or configure backend/.env')
const chromePath = process.env.NMR_CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const baseUrl = process.env.NMR_PORTAL_URL || 'http://127.0.0.1:5173'
const outputDir = resolve(root, 'docs/screenshots/specialist')
mkdirSync(outputDir, {recursive:true})
const browser = await chromium.launch({headless:true,executablePath:chromePath})
const page = await browser.newPage({viewport:{width:1480,height:980}})
const errors=[]
page.on('pageerror',e=>errors.push(e.message))

const cases=[
  {nav:'Employee Stock Ownership',heading:'Shareholding operations',panel:'Payroll batch processing',
   open:'Receive / review payroll',detail:'Receive a payroll batch',file:'stock.png'},
  {nav:'Corporate Pension',heading:'Pension investment administration',panel:'Investment funds and dated NAV',
   open:'Review instructions',detail:'Future contribution instructions',file:'pension.png'},
  {nav:'Financial Wellness',heading:'Financial education programmes',panel:'Editorial pipeline',
   open:'Open editorial reviews',detail:'Education content',file:'wellness.png'},
  {nav:'Trust & Custody',heading:'Asset servicing and settlement',panel:'Settlement and transfer monitor',
   open:'Open settlement monitor',detail:'Transfer settlement',file:'custody.png'},
  {nav:'Equity Compensation',heading:'Equity award administration',panel:'Award grant register',
   open:'Open grant approvals',detail:'Award grants',file:'equity.png'}
]

try {
  await page.goto(baseUrl,{waitUntil:'networkidle'})
  await page.getByLabel('Username').fill('nmr-admin')
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button',{name:'Sign in'}).click()
  await page.getByRole('heading',{name:'Overview',level:1}).waitFor()
  const nav=page.getByRole('navigation',{name:'Main navigation'})
  for(const item of cases){
    await nav.getByRole('button',{name:item.nav}).click()
    await page.getByRole('heading',{name:item.heading,level:2}).waitFor()
    await page.getByRole('heading',{name:item.panel}).waitFor()
    const sourceRows=await page.locator('.domain-workbench .dw-table-wrap tbody tr').count()
    assert.ok(sourceRows>0,item.nav+' must show persisted operational data')
    await page.screenshot({path:resolve(outputDir,item.file),fullPage:true})
    await page.getByRole('button',{name:item.open}).click()
    await page.getByRole('heading',{name:item.detail}).waitFor()
    assert.ok(await page.getByRole('tab',{name:'Workbench'}).count(),item.nav+' retains workbench navigation')
    await page.getByRole('tab',{name:'Workbench'}).click()
    await page.getByRole('heading',{name:item.heading,level:2}).waitFor()
  }
  assert.deepEqual(errors,[],'There should be no uncaught browser errors')
  console.log('PASS: all five specialist workbenches load V2 records and navigate to operational workflows')
}finally{
  await browser.close()
}
