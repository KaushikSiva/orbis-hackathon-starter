/* Explicitly approved, content-matched save of the prepared brief, on the existing browser. */
const{chromium}=require('../tooling/node_modules/playwright');const fs=require('node:fs/promises');const path=require('node:path');const{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),out=path.join(root,'artifacts/video'),sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 if(!process.argv.includes('--execute-approved-save'))throw Error('External save not authorized: run only after the user approves the exact prepared brief, with --execute-approved-save.');
 const approved=JSON.parse(await fs.readFile(path.join(root,'backend/data/design-brief-approval.json'),'utf8'));
 const browser=await chromium.connectOverCDP('http://127.0.0.1:9223');const context=browser.contexts()[0];const page=context.pages().find(p=>p.url().includes('5190'));
 if(!page)throw Error('Existing SHOWROOM page required.');
 const connections=page.getByRole('button',{name:'Close connections',exact:true});if(await connections.count())await connections.click();
 const rid=await page.evaluate(()=>localStorage.getItem('showroom.room'));if(rid!==approved.room_id)throw Error('Room differs from approved brief.');
 const rawDir=path.join(out,'approved-save-raw');await fs.mkdir(rawDir,{recursive:true});const cdp=await context.newCDPSession(page);const frames=[];const start=Date.now();
 const pump=(async()=>{let i=0;while(Date.now()-start<20_000){const t=(Date.now()-start)/1000;const{data}=await cdp.send('Page.captureScreenshot',{format:'jpeg',quality:80,fromSurface:true,captureBeyondViewport:false});const file=path.join(rawDir,`frame-${String(i++).padStart(4,'0')}.jpg`);await fs.writeFile(file,Buffer.from(data,'base64'));frames.push({file,t});await sleep(100);}})();
 let preview;
 if(process.argv.includes('--resume-approved-save')){
  const recovery=JSON.parse(await fs.readFile(path.join(root,'docs/evidence/ambiguous-save-recovery.json'),'utf8'));
  const read=spawnSync('python3',['-c','import sqlite3,json,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute("SELECT body FROM approvals WHERE id=?",(sys.argv[2],)).fetchone()[0])',path.join(root,'backend/data/showroom.db'),recovery.approval_id],{encoding:'utf8'});
  if(read.status!==0)throw Error('Cannot inspect persisted approval.');preview=JSON.parse(read.stdout);
  if(preview.room_id!==rid)throw Error('Persisted approval belongs to another room.');
  if(['in_flight','uncertain'].includes(preview.write_status)&&!preview.exports?.length)throw Error('Reconcile the uncertain provider outcome before resuming.');
  await page.getByRole('dialog',{name:'One last look.'}).waitFor();
 }else{
  const current=await page.request.get(`http://127.0.0.1:8190/api/rooms/${rid}`).then(r=>r.json());
  if(current.exports?.length)throw Error('An export already exists. Do not create another preview.');
  const existing=page.getByRole('button',{name:'Close save review',exact:true});if(await existing.count())await existing.click();
  const pendingPreview=page.waitForResponse(r=>r.url().endsWith(`/api/rooms/${rid}/export-preview`)&&r.request().method()==='POST');await page.getByRole('button',{name:'Save design brief',exact:true}).click();preview=await(await pendingPreview).json();
 }
 if(preview.content!==approved.content||preview.title!==approved.title||JSON.stringify(preview.shopping_rows)!==JSON.stringify(approved.shopping_rows))throw Error('Prepared content changed: no write performed.');
 await sleep(Math.max(0,5000-(Date.now()-start)));
 const responsePromise=page.waitForResponse(r=>r.url().endsWith(`/api/rooms/${rid}/export`)&&r.request().method()==='POST'&&r.request().postDataJSON().approval_id===preview.approval_id);await page.getByRole('button',{name:'Approve & save to Ambiguous',exact:true}).click();const response=await responsePromise;const result=await response.json();
 if(!response.ok())throw Error(`Approved save returned HTTP ${response.status()}: ${JSON.stringify(result)}`);
 if(!result.exports?.length||!result.exports.every(e=>e.verified===true))throw Error('Save returned without verified read-back. Do not retry creation.');
 const savedAtSeconds=(Date.now()-start)/1000;
 await page.screenshot({path:path.join(root,'artifacts/screenshots/saved.png'),fullPage:true});await page.getByRole('dialog').screenshot({path:path.join(root,'artifacts/screenshots/saved-dialog.png')});
 await sleep(Math.max(0,20_000-(Date.now()-start)));await pump;
 await fs.writeFile(path.join(rawDir,'frames.ffconcat'),frames.map((f,i)=>`file '${f.file}'\nduration ${Math.max(.001,(frames[i+1]?.t??20)-f.t).toFixed(6)}\n`).join('')+`file '${frames.at(-1).file}'\n`);
 const ff=spawnSync('ffmpeg',['-v','error','-y','-f','concat','-safe','0','-i',path.join(rawDir,'frames.ffconcat'),'-vf','scale=1600:900:in_range=full:out_range=limited,format=yuv420p,tpad=stop_mode=clone:stop_duration=2','-t','20','-r','30','-c:v','libx264','-preset','medium','-crf','21','-pix_fmt','yuv420p','-color_range','tv','-an','-movflags','+faststart',path.join(out,'approved-save.mp4')],{encoding:'utf8',maxBuffer:8e6});if(ff.status!==0)throw Error(ff.stderr);
 const evidence={recorded_at:new Date().toISOString(),user_authorization:'Parent relayed explicit approval of the exact prepared design brief before this script was run.',room_id:rid,prepared_approval_id:approved.approval_id,ui_approval_id:preview.approval_id,exact_content_compared:true,title:preview.title,budget:approved.budget,total:approved.total,exports:result.exports,outbound_save_attempts:process.argv.includes('--resume-approved-save')?2:1,verified_document_count:result.exports.length,recovery_evidence:process.argv.includes('--resume-approved-save')?'ambiguous-save-recovery.json':null,verified_readback:true,saved_at_seconds:savedAtSeconds};await fs.writeFile(path.join(root,'docs/evidence/approved-save.json'),JSON.stringify(evidence,null,2)+'\n');console.log(JSON.stringify(evidence,null,2));process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
