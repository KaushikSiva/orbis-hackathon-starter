/* Browser contract verification; every API call is intercepted, no invitations sent. */
const {chromium}=require('../tooling/node_modules/playwright');const assert=require('node:assert/strict');const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));let saves=0;
  const room={id:'sharing-contract',name:'Room',budget:500,keep:['sofa'],preferences:['warm'],image_url:null,directives:[],products:[{id:'table',name:'Table',category:'table',price:50,source_url:'https://example.com/table'}],total:50,graph:{status:'connected'},exports:[]};
  await page.route('**/api/**',r=>{const path=new URL(r.request().url()).pathname;
   if(path==='/api/health')return r.fulfill({json:{integrations:{}}});
   if(path.endsWith('/export-preview'))return r.fulfill({json:{approval_id:'approved-contract',title:'Room brief',content:'Reviewed brief',shopping_rows:[],share_recipient:'owner@example.com'}});
   if(path.endsWith('/export')){
    assert.deepEqual(r.request().postDataJSON(),{approval_id:'approved-contract',approved:true});saves++;
    room.exports=[{id:'saved-contract',title:'Room brief',url:'https://example.com/doc',approval_id:'approved-contract',verified:true,sharing:{recipient:'owner@example.com',role:'viewer',status:saves===1?'failed':saves===2?'pending':'shared',message:saves===1?'The document is saved, but sharing was rejected. Retry sharing.':saves===2?'Accept the Ambiguous invitation sent to this address.':'Document access is confirmed.'}}];
    return r.fulfill({json:{room,exports:room.exports}});
   }
   return r.fulfill({json:room});
  });
  await page.addInitScript(()=>localStorage.setItem('showroom.room','sharing-contract'));
  await page.goto('http://127.0.0.1:5190');await page.getByRole('button',{name:'Save design brief',exact:true}).click();
  await page.getByText('Save the brief and shopping list, then share view access with owner@example.com. No furniture is purchased.',{exact:true}).waitFor();assert.equal(saves,0);
  await page.getByRole('button',{name:'Approve & save to Ambiguous'}).click();await page.getByRole('button',{name:'Retry sharing',exact:true}).click();
  await page.getByText('Invitation pending for owner@example.com',{exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.getByRole('button',{name:'Check sharing',exact:true}).click();await page.getByText('Shared with owner@example.com',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Check sharing',exact:true}).count(),0);assert.equal(errors.length,0);
  const receipt={passed:true,provider_mode:'mocked API; no external writes',recipient_visible_before_approval:true,sharing_failure_visible:true,retry_preserves_approval_id:true,pending_and_confirmed_access_visible:true,mobile_horizontal_overflow:false,page_errors:errors};
  fs.writeFileSync('docs/evidence/sharing-browser.json',JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
