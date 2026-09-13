/* Verify the built SDK/WASM in a real browser; no provider request or token. */
const {chromium}=require('../tooling/node_modules/playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

(async()=>{
 const server=spawn(path.join(root,'frontend/node_modules/.bin/vite'),['preview','--host','127.0.0.1','--port','5191'],{cwd:path.join(root,'frontend'),stdio:'ignore'});
 let browser,startupError;
 server.on('error',error=>{startupError=error;});
 try{
  let ready=false;
  for(let attempt=0;attempt<50;attempt++){
   if(startupError)throw startupError;
   try{ready=(await fetch('http://127.0.0.1:5191')).ok;if(ready)break;}catch{}
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert(ready,'Build the frontend before running SDK runtime verification');
  browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:fs.existsSync(chrome)?{executablePath:chrome}:{})});
  const page=await browser.newPage();const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto('http://127.0.0.1:5191');
  const result=await page.evaluate(async()=>{
   const javascript=await fetch('/reactor/wasm/reactor_wasm.js');
   const binary=await fetch('/reactor/wasm/reactor_wasm_bg.wasm');
   const bytes=await binary.arrayBuffer();
   const module=await import('/reactor/wasm/reactor_wasm.js');
   const wasm=await module.default();
   return {javascript:{status:javascript.status,mime:javascript.headers.get('content-type')},binary:{status:binary.status,mime:binary.headers.get('content-type'),bytes:bytes.byteLength},initialized:Boolean(wasm),reactorClientExport:typeof module.ReactorClient};
  });
  assert.equal(result.javascript.status,200);assert.equal(result.binary.status,200);
  assert(result.javascript.mime.includes('javascript'));assert(result.binary.mime.includes('application/wasm'));
  assert(result.initialized);assert.equal(result.reactorClientExport,'function');assert.deepEqual(errors,[]);
  const evidence={checked_at:new Date().toISOString(),surface:'production Vite preview5191',...result,pageErrors:errors,providerCalls:0,liveStreamVerified:false};
  fs.writeFileSync(path.join(root,'docs/evidence/wasm-verification.json'),JSON.stringify(evidence,null,2)+'\n');
  console.log(JSON.stringify(evidence,null,2));
 }finally{await browser?.close();server.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
