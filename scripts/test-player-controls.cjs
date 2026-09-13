/* Isolated browser checks: synthetic video + mocked Reactor, never live-provider evidence. */
const {chromium}=require('../tooling/node_modules/playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const sdk=`export class Reactor {
 constructor(){this.handlers={};window.testReactor=this;window.testCommands=[];this.tick=0;}
 on(name,fn){(this.handlers[name]??=[]).push(fn)} off(name,fn){this.handlers[name]=(this.handlers[name]||[]).filter(x=>x!==fn)}
 emit(name,...args){for(const fn of [...(this.handlers[name]||[])])fn(...args)}
 reply(type,data={}){this.emit('message',{type,data})}
 async connect(){this.emit('statusChanged','ready')}
 async disconnect(){clearInterval(this.timer);this.emit('statusChanged','disconnected')}
 async uploadFile(){return {id:'fixture-image'}}
 draw(){const ctx=this.canvas.getContext('2d');ctx.fillStyle=(this.tick++%2)?'#64784b':'#b58e62';ctx.fillRect(0,0,640,360);ctx.fillStyle='white';ctx.font='28px sans-serif';ctx.fillText('SYNTHETIC VIDEO · TEST ONLY '+this.tick,25,180)}
 async sendCommand(command,data){window.testCommands.push({command,data});
  if(command==='set_image')setTimeout(()=>{this.reply('image_accepted');this.reply('conditions_ready')},10);
  if(command==='set_prompt')setTimeout(()=>this.reply('prompt_accepted'),10);
  if(command==='start'){this.reply('generation_started');this.canvas=document.createElement('canvas');this.canvas.width=640;this.canvas.height=360;this.draw();this.timer=setInterval(()=>this.draw(),40);const stream=this.canvas.captureStream(25);this.emit('trackReceived','main_video',stream.getVideoTracks()[0],stream);}
  if(command==='resume')setTimeout(()=>this.reply('generation_resumed'),10);
 }
}`;
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'],executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},permissions:['microphone']});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/node_modules/@reactor-team/js-sdk/dist/index.js*',r=>r.fulfill({contentType:'application/javascript',body:sdk}));
  const room={id:'player-controls-fixture',name:'The living room',budget:900,preferences:['Warm minimal','Natural textures'],keep:['existing sofa','windows & layout'],image_url:'/images/sample-room.jpg',directives:[],products:[],total:0,graph:{status:'not_queried'},exports:[]};
  await page.route('**/api/**',r=>{
   const path=new URL(r.request().url()).pathname,body=r.request().headers()['content-type']?.includes('application/json')?r.request().postDataJSON():null;let result=room;
   if(path==='/api/transcriptions'){assert(r.request().postDataBuffer().length>100);return r.fulfill({json:{text:'A brass floor lamp'}});}
   if(path.endsWith('/recommendations')){assert.equal(body.source,'amazon');assert.equal(body.query,'A brass floor lamp');}
   if(path==='/api/health')result={integrations:Object.fromEntries(['reactor','neo4j','ambiguous'].map(x=>[x,{configured:true,status:'connected'}]))};
   else if(path==='/api/reactor/token')result={jwt:'test-only',model:'test-only',api_url:'https://invalid.test',prompt:'Fixture room'};
   else if(path.endsWith('/directives')){const directive={id:'directive-'+room.directives.length,instruction:body.instruction,prompt:body.instruction,status:'pending'};room.directives.push(directive);result={room,directive};}
   else if(path.endsWith('/ack'))room.directives.at(-1).status=body.status;
   else if(r.request().method()==='PATCH')Object.assign(room,body);
   if(path.endsWith('/export'))throw Error('Tests must never save documents');
   return r.fulfill({json:result});
  });
  await page.addInitScript(()=>{localStorage.setItem('showroom.room','player-controls-fixture');const get=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);window.testMedia=[];navigator.mediaDevices.getUserMedia=async(...args)=>{const stream=await get(...args);window.testMedia.push(stream);return stream;};});
  await page.goto('http://127.0.0.1:5190');
  const direction=page.getByRole('textbox',{name:'Live design direction'});
  await direction.fill('Keep this composition');
  await page.getByRole('button',{name:'View room fullscreen',exact:true}).click();
  await page.waitForFunction(()=>document.fullscreenElement?.classList.contains('room-player'));
  assert.equal(await direction.inputValue(),'Keep this composition');
  await page.getByRole('button',{name:'Start Orbis',exact:true}).filter({visible:true}).first().click();
  await page.waitForFunction(()=>document.querySelector('.preview-label')?.textContent==='LIVE · ORBIS');
  await direction.press('Enter');await page.locator('.fullscreen-feedback').filter({hasText:'Direction accepted by Orbis. Watch the next moments of your room.'}).waitFor();
  await page.getByRole('button',{name:'Pause room',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.preview-label')?.textContent==='PAUSING · FRAME HELD');
  const frozen=await page.locator('canvas.held-frame').evaluate(c=>c.toDataURL());
  await page.waitForTimeout(180);assert.equal(await page.locator('canvas.held-frame').evaluate(c=>c.toDataURL()),frozen);
  await page.evaluate(()=>window.testReactor.reply('generation_paused'));
  await page.getByRole('button',{name:'Resume room',exact:true}).waitFor();
  await direction.fill('Add a warm lamp without moving the sofa');await direction.press('Enter');
  await page.locator('.fullscreen-feedback').filter({hasText:'Direction accepted by Orbis. Resume when you’re ready to see the change.'}).waitFor();
  assert.equal(await page.locator('canvas.held-frame').evaluate(c=>c.toDataURL()),frozen);
  await page.getByRole('button',{name:'Exit room fullscreen',exact:true}).click();
  assert.equal(await page.evaluate(()=>document.fullscreenElement),null);
  await page.getByRole('button',{name:'Resume room',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.preview-label')?.textContent==='LIVE · ORBIS'&&!document.querySelector('canvas.held-frame').classList.contains('visible'));
  // Reject pause: no false paused state, playback is restored and the error is visible.
  await page.getByRole('button',{name:'Pause room',exact:true}).click();
  await page.evaluate(()=>window.testReactor.reply('command_error',{message:'Pause rejected for test'}));
  await page.getByRole('alert').filter({hasText:'Pause rejected for test'}).filter({visible:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.preview-label')?.textContent==='LIVE · ORBIS');
  // Mobile fallback (including browsers without the Fullscreen API).
  await page.setViewportSize({width:391,height:700});
  await page.evaluate(()=>document.querySelector('.room-player').requestFullscreen=undefined);
  await direction.fill('Retain this draft');
  await page.getByRole('button',{name:'View room fullscreen',exact:true}).click();
  assert.equal(await direction.inputValue(),'Retain this draft');
  const bounds=await direction.boundingBox();assert(bounds.y>=0&&bounds.y+bounds.height<=700);
  await page.setViewportSize({width:391,height:360});await page.waitForTimeout(100);const keyboardBounds=await direction.boundingBox();assert(keyboardBounds.y>=0&&keyboardBounds.y+keyboardBounds.height<=360);await page.setViewportSize({width:391,height:700});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.getByRole('button',{name:'Pause room',exact:true}).click();await page.evaluate(()=>window.testReactor.reply('generation_paused'));
  await page.getByRole('button',{name:'Resume room',exact:true}).waitFor();
  // A rejected resume leaves the held frame and retry available.
  await page.evaluate(()=>{const sdk=window.testReactor,send=sdk.sendCommand.bind(sdk);sdk.sendCommand=async(command,data)=>{if(command==='resume'){window.testCommands.push({command,data});setTimeout(()=>sdk.reply('command_error',{message:'Resume rejected for test'}),10)}else return send(command,data)}});
  await page.getByRole('button',{name:'Resume room',exact:true}).click();
  await page.locator('.fullscreen-feedback').filter({hasText:'Resume rejected for test'}).waitFor();
  await page.getByRole('button',{name:'Resume room',exact:true}).waitFor();
  assert(await page.locator('canvas.held-frame').evaluate(c=>c.classList.contains('visible')));
  await page.keyboard.press('Escape');assert(!await page.locator('.room-player').evaluate(e=>e.classList.contains('is-expanded')));
  assert.equal(await direction.inputValue(),'Retain this draft');
  await page.getByRole('button',{name:'End live session',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('canvas.held-frame').classList.contains('visible'));
  await page.getByRole('button',{name:'Record products by voice',exact:true}).click();
  await page.getByRole('button',{name:'Stop recording products',exact:true}).waitFor();await page.waitForTimeout(250);
  await page.getByRole('button',{name:'Stop recording products',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Search furniture"]').value==='A brass floor lamp');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  assert(await page.evaluate(()=>window.testMedia.every(s=>s.getTracks().every(t=>t.readyState==='ended'))));
  await page.getByRole('button',{name:'View room fullscreen',exact:true}).click();
  await page.getByRole('button',{name:'Record direction by voice',exact:true}).click();
  await page.getByRole('button',{name:'Stop recording direction',exact:true}).waitFor();await page.waitForTimeout(250);
  await page.getByRole('button',{name:'Stop recording direction',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Live design direction"]').value==='Retain this draft A brass floor lamp');
  await page.evaluate(()=>navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Microphone access denied','NotAllowedError')});
  await page.getByRole('button',{name:'Record direction by voice',exact:true}).click();
  await page.locator('.fullscreen-feedback').filter({hasText:'Microphone access denied'}).waitFor();
  assert(await direction.isEditable());
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,provider:'mocked SDK / synthetic frames, no external calls',checks:['native fullscreen direction and acknowledgment','draft persists through expansion','instant frame hold before provider acknowledgment','steering while paused preserves held frame','resume continues playback','pause and resume rejection recovery','mobile expanded fallback input in viewport','Escape restores view and draft','end clears pause state','microphone recording transcribed into Amazon query','voice direction editable inside fullscreen','microphone tracks stop after recording','permission denial keeps typing available'],commands:await page.evaluate(()=>window.testCommands.map(x=>x.command))},null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
