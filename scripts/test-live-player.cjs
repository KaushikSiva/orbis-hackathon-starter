/* Opt-in live Orbis pause/resume verification. Uses a separate room; no document writes. */
const {chromium}=require('../tooling/node_modules/playwright');const fs=require('node:fs');const assert=require('node:assert/strict');
(async()=>{
 if(!process.argv.includes('--live'))throw Error('Pass --live to use one real Orbis session.');
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 let page;
 try{
  page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(90000);
  await page.route('**/api/rooms/*/export',r=>r.abort());
  await page.addInitScript(()=>{window.playerEvents=[];window.addEventListener('showroom:stream-event',e=>window.playerEvents.push(e.detail));});
  await page.goto('http://127.0.0.1:5190');await page.getByRole('button',{name:'Start Orbis',exact:true}).filter({visible:true}).click();
  console.log('Requested one live session');
  await page.waitForFunction(()=>document.querySelector('.preview-label')?.textContent==='LIVE · ORBIS'||document.querySelector('.feedback.error'),{},{timeout:300000});
  const error=page.locator('.feedback.error');if(await error.count())throw Error(await error.innerText());
  await page.getByRole('button',{name:'View room fullscreen',exact:true}).click();
  await page.getByRole('button',{name:'Pause room',exact:true}).click();
  await page.getByRole('button',{name:'Resume room',exact:true}).waitFor();
  const held=await page.locator('canvas.held-frame').evaluate(c=>c.toDataURL());
  await page.waitForTimeout(2200);assert.equal(await page.locator('canvas.held-frame').evaluate(c=>c.toDataURL()),held);
  await page.getByRole('textbox',{name:'Live design direction'}).fill('Keep the camera fixed and preserve the existing sofa. Make the room lighting warmer.');
  await page.getByRole('button',{name:'Send live direction',exact:true}).click();
  await page.locator('.fullscreen-feedback').filter({hasText:'Resume when you’re ready'}).waitFor();
  await page.screenshot({path:'artifacts/screenshots/fullscreen-paused.png'});
  await page.getByRole('button',{name:'Resume room',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.preview-label')?.textContent==='LIVE · ORBIS'&&!document.querySelector('canvas.held-frame').classList.contains('visible'));
  const events=await page.evaluate(()=>window.playerEvents),types=events.map(e=>e.type);
  assert(types.includes('generation_paused')&&types.includes('generation_resumed')&&types.filter(t=>t==='prompt_accepted').length>=2);
  const evidence={verified_at:new Date().toISOString(),provider:'actual Orbis SDK session',room_id:await page.evaluate(()=>localStorage.getItem('showroom.room')),fullscreen:true,frame_held_for_ms:2200,paused_direction_accepted:true,resumed:true,events:events.filter(e=>['generation_paused','generation_resumed','prompt_accepted','browser_frame_presented'].includes(e.type)),external_document_writes:0};
  fs.writeFileSync('docs/evidence/player-live-verification.json',JSON.stringify(evidence,null,2)+'\n');console.log(JSON.stringify(evidence,null,2));
 }finally{if(page)await page.evaluate(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent?.trim()==='End live session');b?.click()}).catch(()=>{});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
