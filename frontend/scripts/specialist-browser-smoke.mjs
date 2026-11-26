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
const chromePath = process.env.NMR_CHROME_PATH || (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : chromium.executablePath())
const baseUrl = process.env.NMR_PORTAL_URL || 'http://127.0.0.1:5173'
const outputDir = resolve(root, 'docs/screenshots/specialist')
mkdirSync(outputDir, {recursive:true})
const browser = await chromium.launch({headless:true,executablePath:chromePath})
const page = await browser.newPage({viewport:{width:1480,height:980}})
const errors=[]
page.on('pageerror',e=>errors.push(e.message))

const cases=[
  {nav:'Employee Stock Ownership',heading:'Shareholding operations',panel:'Payroll batch processing',
   open:'Receive / review payroll',detail:'Receive payroll batch',file:'stock.png'},
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
  // Screenshot regression: participant record header and metric grid should remain
  // readable and balanced at desktop, laptop and phone widths.
  await page.setViewportSize({width:1480,height:980})
  await nav.getByRole('button',{name:'Employee Stock Ownership'}).click()
  await page.getByRole('tab',{name:'Overview'}).click()
  await page.locator('.v2-source-bar').waitFor()
  await page.locator('.v2-stock-metrics .metric').first().waitFor()
  assert.equal(await page.locator('.v2-stock-metrics .metric').count(),4)
  const desktop = await page.evaluate(() => {
    const bar=document.querySelector('.v2-source-bar')
    const cards=[...document.querySelectorAll('.v2-stock-metrics .metric')]
    const nav=[...document.querySelectorAll('.domain-navigation .subtabs')]
    return {
      barDisplay:getComputedStyle(bar).display,
      barTitleSize:parseFloat(getComputedStyle(document.querySelector('.v2-source-ident strong')).fontSize),
      rows:cards.map(x=>Math.round(x.getBoundingClientRect().top)),
      navClipped:nav.some(x=>x.scrollWidth > x.clientWidth + 2),
    }
  })
  assert.equal(desktop.barDisplay,'flex','V2 source header should have a defined layout')
  assert.ok(desktop.barTitleSize>=15,'V2 source header should use readable type')
  assert.equal(new Set(desktop.rows).size,1,'All four stock metrics should share one desktop row')
  assert.equal(desktop.navClipped,false,'Service navigation must wrap rather than horizontally scroll')
  await page.screenshot({path:resolve(outputDir,'stock-record-desktop.png'),fullPage:true})

  await page.setViewportSize({width:1024,height:850})
  const laptop = await page.evaluate(() => [...document.querySelectorAll('.v2-stock-metrics .metric')]
    .map(x=>Math.round(x.getBoundingClientRect().top)))
  assert.equal(new Set(laptop).size,2,'Stock cards should form a balanced 2 by 2 grid on a laptop')
  await page.screenshot({path:resolve(outputDir,'stock-record-laptop.png'),fullPage:true})

  await page.setViewportSize({width:460,height:850})
  const phone = await page.evaluate(() => ({
    metricRows:new Set([...document.querySelectorAll('.v2-stock-metrics .metric')]
      .map(x=>Math.round(x.getBoundingClientRect().top))).size,
    pageOverflows:document.documentElement.scrollWidth > window.innerWidth+2,
  }))
  assert.equal(phone.metricRows,4,'Stock metrics should stack in one column on narrow phones')
  assert.equal(phone.pageOverflows,false,'The page must not require horizontal scrolling on mobile')
  await page.screenshot({path:resolve(outputDir,'stock-record-mobile.png'),fullPage:true})
  await page.setViewportSize({width:1480,height:980})

  assert.deepEqual(errors,[],'There should be no uncaught browser errors')
  console.log('PASS: all five specialist workbenches load V2 records and navigate to operational workflows')
}finally{
  await browser.close()
}
