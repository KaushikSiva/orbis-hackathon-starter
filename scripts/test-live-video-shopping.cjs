/* Opt-in: one actual Orbis session, OpenAI frame identification and Exa search. */
const {chromium}=require('../tooling/node_modules/playwright');const fs=require('fs');const assert=require('node:assert/strict');
(async()=>{
 if(!process.argv.includes('--live'))throw Error('Pass --live to use Orbis, OpenAI and Exa.');
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});let page;
 try{
  page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.setDefaultTimeout(120000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/rooms/*/export',r=>r.abort());
  await page.goto('http://127.0.0.1:5190');await page.getByRole('button',{name:'Start Orbis',exact:true}).filter({visible:true}).first().click();console.log('Requested actual Orbis session');
  await page.waitForFunction(()=>document.querySelector('.preview-label')?.textContent==='LIVE · ORBIS'||document.querySelector('.feedback.error'),{},{timeout:300000});
  if(await page.locator('.feedback.error').count())throw Error(await page.locator('.feedback.error').innerText());
  await page.locator('.recording-indicator').waitFor();await page.waitForTimeout(10000);
  await page.getByRole('button',{name:'Save & rewind',exact:true}).click();
  await page.waitForFunction(()=>{const v=document.querySelector('.replay-video');return v?.readyState>=2&&Number.isFinite(v.duration)&&v.duration>5;});
  await page.getByRole('slider',{name:'Replay position'}).fill('3');await page.waitForFunction(()=>Math.abs(document.querySelector('.replay-video').currentTime-3)<.2);
  const clip=await page.locator('.replay-video').evaluate(v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,seek:v.currentTime}));
  const downloadPromise=page.waitForEvent('download');await page.getByRole('link',{name:'Download video',exact:true}).click();const download=await downloadPromise;await download.saveAs('backend/data/runtime/actual-room-recording.webm');
  // End the paid stream before inspecting the saved frame.
  await page.getByRole('button',{name:'End live session',exact:true}).click();await page.getByRole('button',{name:'View room fullscreen',exact:true}).click();
  const rect=await page.locator('.replay-video').boundingBox();const ratio=clip.width/clip.height,drawH=Math.min(rect.height,rect.width/ratio),drawW=drawH*ratio;
  const responsePromise=page.waitForResponse(r=>r.url().endsWith('/visual-search'));
  await page.mouse.click(rect.x+(rect.width-drawW)/2+drawW*.52,rect.y+(rect.height-drawH)/2+drawH*.68);
  const response=await responsePromise;const result=await response.json();assert(response.ok(),JSON.stringify(result));
  await page.locator('.visual-match-list a').first().waitFor();assert(result.products.every(p=>p.source_url.startsWith('https://www.amazon.com/dp/')));
  await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:'artifacts/screenshots/click-video-amazon.png',animations:'disabled'});
  await page.getByRole('button',{name:'Close furniture matches'}).click();await page.screenshot({path:'artifacts/screenshots/saved-video-replay.png',animations:'disabled'});
  const evidence={verified_at:new Date().toISOString(),providers:['actual Orbis stream','actual OpenAI vision','actual Exa search'],room_id:await page.evaluate(()=>localStorage.getItem('showroom.room')),recording:clip,selection:result.selection,products:result.products,graph:result.graph,page_errors:errors,external_document_writes:0};
  fs.writeFileSync('docs/evidence/video-shopping-live.json',JSON.stringify(evidence,null,2)+'\n');console.log(JSON.stringify({passed:true,recording:clip,selection:result.selection,product_count:result.products.length,graph:result.graph.status}));
 }finally{if(page)await page.evaluate(()=>[...document.querySelectorAll('button')].find(b=>b.textContent?.trim()==='End live session')?.click()).catch(()=>{});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
