/* Opt-in integration check with a supplied test WAV as Chrome's microphone input. */
const {chromium}=require('../tooling/node_modules/playwright');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 if(process.argv[2]!=='--live'||!process.argv[3])throw Error('Usage: node scripts/test-live-voice-search.cjs --live /path/to/test.wav (calls OpenAI and Exa).');
 const audio=path.resolve(process.argv[3]);assert(fs.existsSync(audio));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+audio]});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},permissions:['microphone']});page.setDefaultTimeout(100000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/rooms/*/export',r=>r.abort());await page.route('**/api/reactor/token',r=>r.abort());
  await page.goto('http://127.0.0.1:5190');await page.locator('#budget').fill('500');
  await page.getByRole('button',{name:'Record products by voice',exact:true}).click();await page.getByRole('button',{name:'Stop recording products',exact:true}).waitFor();
  await page.waitForTimeout(4500);
  const transcriptPromise=page.waitForResponse(r=>r.url().endsWith('/api/transcriptions'));
  await page.getByRole('button',{name:'Stop recording products',exact:true}).click();const response=await transcriptPromise;const transcript=await response.json();assert(response.ok(),JSON.stringify(transcript));
  await page.waitForFunction(text=>document.querySelector('[aria-label="Search furniture"]').value===text,transcript.text);
  assert(/brass/i.test(transcript.text)&&/lamp/i.test(transcript.text));
  console.log('Real microphone-file transcription:',transcript.text);
  const searchPromise=page.waitForResponse(r=>r.url().endsWith('/recommendations'));
  await page.getByRole('button',{name:'Search',exact:true}).click();const result=await searchPromise;const room=await result.json();assert(result.ok(),JSON.stringify(room));assert(room.products.length>0);
  assert(room.products.every(p=>p.source_url.startsWith('https://www.amazon.com/dp/')&&(p.price===null||p.price<=100)));
  assert(room.graph.status==='connected');await page.locator('.product-row').first().waitFor();
  await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(600);
  await page.locator('.product-image img').evaluateAll(images=>Promise.all(images.map(img=>img.complete?Promise.resolve():new Promise(resolve=>{img.addEventListener('load',resolve,{once:true});img.addEventListener('error',resolve,{once:true});setTimeout(resolve,8000)}))));
  await page.locator('.shopping-section').screenshot({path:'artifacts/screenshots/amazon-voice-search.png',animations:'disabled'});
  assert.deepEqual(errors,[]);
  const evidence={verified_at:new Date().toISOString(),microphone_input:'Locally synthesized test WAV supplied to Chromium fake microphone; actual MediaRecorder WebM upload',transcription:transcript,search_provider:'actual Exa API',room_id:room.id,products:room.products,priced_subtotal:room.total,unpriced_count:room.unpriced_count,graph_status:room.graph.status,page_errors:errors,external_document_writes:0};
  fs.writeFileSync('docs/evidence/voice-search-live-verification.json',JSON.stringify(evidence,null,2)+'\n');console.log(JSON.stringify({passed:true,product_count:room.products.length,priced_subtotal:room.total,unpriced_count:room.unpriced_count,graph:room.graph.status}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
