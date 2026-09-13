const { chromium } = require('../tooling/node_modules/playwright');
const path = require('node:path');
const fs = require('node:fs/promises');
const root = path.resolve(__dirname, '..');
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  const page = await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});
  await page.goto(`file://${path.join(root,'docs/deck/showroom-deck.html')}`);
  await page.evaluate(() => document.fonts.ready);
  const broken = await page.locator('img').evaluateAll(imgs => imgs.filter(i => !i.complete || i.naturalWidth===0).map(i=>i.src));
  if (broken.length) throw new Error(`Deck images missing: ${broken.join(', ')}`);
  if (await page.locator('.slide').count() !== 5) throw new Error('Deck must contain five pages');
  await page.emulateMedia({media:'print'});
  await fs.mkdir(path.join(root,'artifacts/deck-preview'),{recursive:true});
  await page.pdf({path:path.join(root,'artifacts/showroom-deck.pdf'),printBackground:true,preferCSSPageSize:true,displayHeaderFooter:false});
  for(let i=0;i<5;i++) await page.locator('.slide').nth(i).screenshot({path:path.join(root,`artifacts/deck-preview/page-${i+1}.png`)});
  await browser.close();
  console.log('Rendered five-slide PDF and editable HTML source.');
})().catch(e=>{console.error(e);process.exit(1)});
