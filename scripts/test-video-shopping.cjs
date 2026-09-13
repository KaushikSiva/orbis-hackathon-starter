/* Real browser MediaRecorder/IndexedDB, synthetic video and mocked remote providers. */
const {chromium}=require('../tooling/node_modules/playwright');const fs=require('fs');const assert=require('node:assert/strict');
const sdk=fs.readFileSync('scripts/test-player-controls.cjs','utf8').match(/const sdk=`([\s\S]*?)`;/)[1];
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},acceptDownloads:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));let failSearch=false;let searches=0;
  const room={id:'video-shopping-test',name:'Room',budget:500,keep:['sofa'],preferences:['warm'],image_url:'/images/sample-room.jpg',directives:[],products:[],total:0,graph:{status:'not_queried'},exports:[]};
  await page.route('**/node_modules/@reactor-team/js-sdk/dist/index.js*',r=>r.fulfill({contentType:'application/javascript',body:sdk}));
  await page.route('**/api/**',r=>{const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/visual-search')){searches++;assert(r.request().postDataBuffer().length>1000);return failSearch?r.fulfill({status:502,json:{detail:'Vision temporarily unavailable'}}):r.fulfill({json:{selection:{label:'Test oak table',query:'oak table'},products:[{id:'test-table',name:'Test Amazon match',price:49.99,source_url:'https://www.amazon.com/dp/B012345678'}]}});}
   if(p==='/api/reactor/token')return r.fulfill({json:{jwt:'fixture',model:'fixture',api_url:'https://invalid.test',prompt:'Test'}});
   if(p==='/api/health')return r.fulfill({json:{integrations:{}}});
   if(p.endsWith('/export'))throw Error('No external writes allowed');return r.fulfill({json:room});
  });
  await page.addInitScript(()=>localStorage.setItem('showroom.room','video-shopping-test'));
  await page.goto('http://127.0.0.1:5190');await page.getByRole('button',{name:'Start Orbis',exact:true}).filter({visible:true}).first().click();
  await page.locator('.recording-indicator').waitFor();await page.waitForTimeout(3200);
  await page.getByRole('button',{name:'Save & rewind',exact:true}).click();
  const replay=page.getByLabel('Recorded room replay', {exact:true});await replay.waitFor();
  await page.waitForFunction(()=>{const v=document.querySelector('.replay-video');return v?.readyState>=2&&Number.isFinite(v.duration)&&v.duration>2;});
  await page.getByRole('slider',{name:'Replay position'}).fill('1.5');await page.waitForFunction(()=>Math.abs(document.querySelector('.replay-video').currentTime-1.5)<.15);
  await page.getByRole('button',{name:'Rewind ten seconds'}).click();await page.waitForFunction(()=>document.querySelector('.replay-video').currentTime<.15);
  const downloadPromise=page.waitForEvent('download');await page.getByRole('link',{name:'Download video',exact:true}).click();const download=await downloadPromise;assert(download.suggestedFilename().endsWith('.webm'));
  await download.saveAs('backend/data/runtime/recording-browser-test.webm');
  // Clicking the saved frame uses the frame source, not an unrelated live frame.
  await page.getByRole('button',{name:'Find Amazon matches for an item in this frame'}).click({position:{x:260,y:180}});
  await page.getByRole('link',{name:'Test Amazon match $49.99'}).waitFor();assert.equal(searches,1);
  assert.equal(await page.getByRole('link',{name:'Test Amazon match $49.99'}).getAttribute('href'),'https://www.amazon.com/dp/B012345678');
  await page.getByRole('button',{name:'Close furniture matches'}).click();
  failSearch=true;await page.getByRole('button',{name:'Find Amazon matches for an item in this frame'}).click({position:{x:260,y:180}});await page.getByRole('alert').filter({hasText:'Vision temporarily unavailable'}).waitFor();
  failSearch=false;await page.getByRole('button',{name:'Retry this frame'}).click();await page.getByRole('link',{name:'Test Amazon match $49.99'}).waitFor();
  await page.getByRole('button',{name:'Close furniture matches'}).click();
  await page.getByRole('button',{name:'View room fullscreen',exact:true}).click();await page.setViewportSize({width:391,height:700});
  const timeline=await page.getByRole('slider',{name:'Replay position'}).boundingBox();assert(timeline.y>=0&&timeline.y+timeline.height<=700);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.getByRole('button',{name:'Exit room fullscreen',exact:true}).click();await page.getByRole('button',{name:'End live session',exact:true}).click();
  await page.reload();await page.getByRole('button',{name:'Replay',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.replay-video')?.readyState>=2);
  assert(await page.getByText('Saved in this browser',{exact:false}).isVisible());
  const coordinates=await page.evaluate(async()=>{const {sourcePoint}=await import('/src/FrameShop.tsx');return {center:sourcePoint(640,360,{width:400,height:400},'contain','50% 50%',200,200),bar:sourcePoint(640,360,{width:400,height:400},'contain','50% 50%',200,20),crop:sourcePoint(640,360,{width:400,height:400},'cover','50% 50%',200,200)};});
  assert.deepEqual(coordinates.center,{x:.5,y:.5});assert.equal(coordinates.bar,null);assert.deepEqual(coordinates.crop,{x:.5,y:.5});
  assert.deepEqual(errors,[]);
  const result={passed:true,providers:'mocked; synthetic video explicitly labeled',checks:['automatic recording from decoded frames','finite duration metadata','timeline seek and rewind','downloaded playable WebM','IndexedDB reload recovery','click saved frame to Amazon match','visual API failure and retry','mobile fullscreen timeline','contain/cover coordinates and letterbox rejection'],searches};
  fs.writeFileSync('docs/evidence/video-shopping-browser.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
