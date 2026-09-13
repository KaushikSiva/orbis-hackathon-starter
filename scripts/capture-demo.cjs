/* Record actual SHOWROOM interactions. Never stubs a provider or changes app markup. */
const { chromium } = require('../tooling/node_modules/playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname,'..');
const output = path.join(root,'artifacts/video');
const shots = path.join(root,'artifacts/screenshots');
const stamp = t => {const h=Math.floor(t/3600),m=Math.floor(t/60)%60,s=t%60;return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')},000`;};
(async()=>{
 await fs.mkdir(output,{recursive:true});await fs.mkdir(shots,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1600,height:900},deviceScaleFactor:1,recordVideo:{dir:path.join(output,'raw-capture'),size:{width:1600,height:900}}});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const health=await fetch('http://localhost:8190/api/health').then(r=>r.json());
 const captions=[];const add=(a,b,text)=>captions.push({a,b,text});
 await page.goto('http://localhost:5190',{waitUntil:'networkidle'});
 const started=Date.now();const until=async sec=>{const ms=sec*1000-(Date.now()-started);if(ms>0)await page.waitForTimeout(ms);};
 await page.screenshot({path:path.join(shots,'desktop.png'),fullPage:true});
 add(0,8,'SHOWROOM — a room you can make your own.');
 await until(8);await page.getByLabel('Upload room photo',{exact:true}).setInputFiles(path.join(root,'frontend/public/images/sample-room.jpg'));
 add(8,18,'Upload a room photograph. This demo uses the labeled sample room.');
 await until(18);await page.locator('#budget').fill('900');await page.getByLabel('Add a keep constraint',{exact:true}).fill('existing artwork');await page.getByRole('button',{name:'Add keep constraint',exact:true}).click();
 add(18,28,'A $900 furniture budget. Keep the sofa, layout, windows and artwork.');
 await until(28);await page.getByRole('button',{name:'Start Orbis',exact:true}).click();
 await page.waitForTimeout(5000);
 const hasLiveFrames=async()=>page.locator('video').evaluate(v=>v.readyState>=2&&v.videoWidth>0&&!!v.srcObject&&v.getVideoPlaybackQuality().totalVideoFrames>0);
 let live=await hasLiveFrames();
 if(!live&&health.integrations.reactor.configured){await page.waitForTimeout(7000);live=await hasLiveFrames();}
 add(28,45,live?'Orbis is streaming this room in the browser.':'Orbis is unavailable. The connection error offers a retry.');
 await until(45);
 if(live){
   await page.getByLabel('Live design direction',{exact:true}).fill('Make it warmer with natural oak and soft evening light. Keep all protected pieces.');
   await page.getByRole('button',{name:'Send live direction',exact:true}).click();
   add(45,60,'First direction: warmer oak and soft evening light. The interface waits for acknowledgment.');
 }else{
   await page.getByRole('button',{name:'Connections',exact:true}).click();
   await page.screenshot({path:path.join(shots,'connections.png'),fullPage:true});
   add(45,60,'Check connection status: Orbis, Neo4j and Ambiguous.');
 }
 await until(60);
 if(live){
   await page.getByLabel('Live design direction',{exact:true}).fill('Add softer layered textures. Keep the sofa and layout, and stay within the $900 budget.');
   await page.getByRole('button',{name:'Send live direction',exact:true}).click();
   add(60,74,'Second direction: softer textures. The same budget and keep constraints remain in the prompt.');
 }else{
   await page.getByRole('button',{name:'Close connections',exact:true}).click();
   await page.getByLabel('Live design direction',{exact:true}).fill('A warmer palette, keeping the sofa and layout.');
   add(60,74,'Start a live session to send design instructions.');
 }
 await until(74);await page.getByRole('button',{name:'Find the pieces',exact:true}).click();await page.locator('.shopping-section').scrollIntoViewIfNeeded();await page.waitForTimeout(1200);
 await page.locator('.shopping-section').screenshot({path:path.join(shots,'shopping.png')});
 add(74,87,'Review sourced products, dimensions and the calculated subtotal.');
 await until(87);await page.getByRole('button',{name:'Save design brief',exact:true}).click();await page.waitForTimeout(750);await page.screenshot({path:path.join(shots,'brief.png'),fullPage:true});
 add(87,102,'Review the brief and shopping list before saving.');
 await until(102);const beforeSave=await fetch('http://localhost:8190/api/health').then(r=>r.json());
 // Never perform a real external write merely to obtain footage.
 const safeFailureDemo=!beforeSave.integrations.ambiguous.configured;
 if(safeFailureDemo)await page.getByRole('button',{name:'Approve & save to Ambiguous',exact:true}).click();
 await page.waitForTimeout(2500);
 const saved=await page.getByRole('heading',{name:'Consider it saved.',exact:true}).count()>0;
 add(102,114,saved?'Approved and saved. Returned Ambiguous links make the result inspectable.':safeFailureDemo?'The write failed. The service error remains visible for retry.':'Ambiguous is available. The concrete brief is ready for the user’s approval before any remote write.');
 await page.screenshot({path:path.join(shots,saved?'saved.png':'save-status.png'),fullPage:true});
 await until(114);await page.getByRole('button',{name:'Close save review',exact:true}).click();await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
 add(114,120,'SHOWROOM — from a room photo to a practical design brief.');
 await until(120);
 const roomId=await page.evaluate(()=>localStorage.getItem('showroom.room'));
 const room=roomId?await fetch(`http://localhost:8190/api/rooms/${roomId}`).then(r=>r.json()):null;
 const videoPath=await page.video().path();await context.close();
 const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});await mobile.goto('http://localhost:5190',{waitUntil:'networkidle'});await mobile.screenshot({path:path.join(shots,'mobile.png'),fullPage:true});
 const mobileOverflow=await mobile.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
 await browser.close();
 const srt=captions.map((c,i)=>`${i+1}\n${stamp(c.a)} --> ${stamp(c.b)}\n${c.text}\n`).join('\n');await fs.writeFile(path.join(output,'showroom-demo.srt'),srt);
 const captionFilter="subtitles=artifacts/video/showroom-demo.srt:force_style='FontName=Arial,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00302923,BorderStyle=3,Outline=1,Shadow=0,MarginV=25,Alignment=2'";
 const ff=spawnSync('ffmpeg',['-y','-i',videoPath,'-vf',`tpad=stop_mode=clone:stop_duration=5,${captionFilter}`,'-t','120','-r','30','-c:v','libx264','-preset','medium','-crf','21','-pix_fmt','yuv420p','-an','-movflags','+faststart',path.join(output,'showroom-demo.mp4')],{cwd:root,encoding:'utf8',maxBuffer:8_000_000});
 if(ff.status!==0)throw new Error(ff.stderr);
 const poster=spawnSync('ffmpeg',['-y','-ss','20','-i',videoPath,'-frames:v','1','-q:v','2',path.join(output,'poster.jpg')],{encoding:'utf8'});if(poster.status!==0)throw new Error(poster.stderr);
 const probe=spawnSync('ffprobe',['-v','error','-show_entries','format=duration,size:stream=codec_name,pix_fmt,width,height','-of','json',path.join(output,'showroom-demo.mp4')],{encoding:'utf8'});
 const record={captured_at:new Date().toISOString(),url:'http://localhost:5190',footage:'Actual browser recording; no mock routes, generated UI, or prerecorded provider output inserted.',live_orbis_observed:live,ambiguous_save_observed:saved,approval_attempted_without_credentials:safeFailureDemo,health,room_id:roomId,budget:room?.budget,keep:room?.keep,directive_statuses:room?.directives?.map(x=>({instruction:x.instruction,status:x.status})),shopping_total:room?.total,graph:room?.graph,exports:room?.exports,page_errors:errors,mobile_overflow:mobileOverflow,video:JSON.parse(probe.stdout)};
 await fs.writeFile(path.join(root,'docs/evidence/capture.json'),JSON.stringify(record,null,2)+'\n');console.log(JSON.stringify(record,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
