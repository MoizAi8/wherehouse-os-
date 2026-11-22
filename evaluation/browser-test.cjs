const { chromium } = require('../.tools/qa-browser/node_modules/playwright');

const { execFileSync } = require('node:child_process');

const assert = require('node:assert/strict');

const fs=require('node:fs');

const origin=process.env.EVALUATION_ORIGIN || 'http://127.0.0.1:8387';
const remote=origin!=='http://127.0.0.1:8387';
if(remote && !/^https:\/\/[a-z0-9-]+\.trycloudflare\.com$/.test(origin)) throw Error('Unexpected acceptance origin');

(async()=>{

 const browser=await chromium.launch({channel:'msedge',headless:true});

 try {

 const c=await browser.newContext(), p=await c.newPage();

 const issue=()=>execFileSync('order-fulfillment-coordinator/apps/api/.venv/Scripts/python.exe',['evaluation/workspace.py','invite'],{encoding:'utf8'}).trim();

 assert.equal((await c.request.get(origin+'/api/v1/orders')).status(),401);

 const link=issue();

 await p.goto(link); await p.waitForURL(origin+'/dashboard',{timeout:60000});

 assert.equal((await c.request.post(origin+'/exchange',{headers:{Origin:origin},data:{credential:link.split('#')[1]}})).status(),403);

 const sid=(await c.cookies()).find(x=>x.name===(remote?'__Host-evaluation':'evaluation-local'));assert.ok(sid.httpOnly);assert.equal(sid.secure,remote);assert.equal(sid.sameSite,"Strict");

 const sess=await (await c.request.get(origin+'/api/auth/session')).json();assert.ok(!sess.accessToken);

 for(const path of ['/api/v1/integrations','/api/auth/users','/api/v1/settings','/api/auth/login','/api/v1/webhooks/shipment-event']){

 assert.equal((await c.request.post(origin+path,{headers:{Origin:origin},data:{}})).status(),403)}

 assert.equal((await c.request.post(origin+'/api/evaluation/workflow',{headers:{Origin:'https://invalid.example'}})).status(),403);

 await p.goto(origin+'/dashboard/inventory'); const sku='INSTRUCTOR-'+Date.now();await p.getByLabel('SKU',{exact:true}).fill(sku);

 await p.getByLabel('Product name').fill('Instructor boxes'); await p.getByRole('button',{name:'Add product'}).click();

 await p.getByRole('option',{name:new RegExp(sku)}).first().waitFor({state:'attached'});

 await p.getByLabel('Product',{exact:true}).selectOption(sku);

 await p.getByLabel('Fulfillment center').selectOption({label:'Evaluation Center'});

 await p.getByRole('button',{name:'Add stock location'}).click();

 await p.getByLabel('Quantity change').fill('5');await p.getByLabel('Movement reason').fill('Instructor receipt');

 await p.getByRole('button',{name:'Record movement'}).click();await p.getByText(/On hand 5.*Reserved 0.*Available 5/).waitFor();

 await p.goto(origin+'/dashboard/agents');const run=p.getByRole('button',{name:'Run Evaluation Workflow'});const submitted=p.waitForResponse(r=>r.url().endsWith('/api/evaluation/workflow')&&r.request().method()==='POST');await run.click();assert.equal((await submitted).status(),202);assert.equal((await c.request.post(origin+'/api/evaluation/workflow',{headers:{Origin:origin}})).status(),409);

 await p.reload();await p.waitForFunction(()=>document.querySelector('section p[aria-live]')?.textContent?.startsWith('Completed'),null,{timeout:180000});

 const data=await (await c.request.get(origin+'/api/evaluation/workflow')).json();

 assert.equal(data.stage,'Completed');assert.equal(data.result.dashboard_status.length,7);assert.equal(data.result.order_state,'delivered');

 await p.getByRole('button',{name:'Refresh agent status'}).click();

 for(const a of data.result.dashboard_status){const card=p.getByRole('heading',{name:a.name,exact:true}).locator('../..');await card.locator('summary').click();await card.getByText('Event '+a.event_id,{exact:true}).waitFor()}

 await p.screenshot({path:'.tools/instructor-workspace/verified-cards.png',fullPage:true});

 await p.goto(origin+'/dashboard/chat');const msg=p.getByPlaceholder('Ask anything about your warehouse...');await msg.fill('List orders');const reply=p.waitForResponse(r=>r.url().endsWith('/api/chat')&&r.request().method()==='POST');await msg.press('Enter');assert.equal((await reply).status(),200);await p.reload();await p.getByLabel('Chat messages').getByText('List orders',{exact:true}).waitFor();

 execFileSync('order-fulfillment-coordinator/apps/api/.venv/Scripts/python.exe',['evaluation/workspace.py','revoke']);

 assert.equal((await c.request.get(origin+'/api/v1/orders')).status(),401);

 fs.writeFileSync('.tools/instructor-workspace/browser-pass.json',JSON.stringify({at:new Date().toISOString(),id:data.id,checks:['anonymous rejection','one-time redemption','HttpOnly','scope','CSRF','inventory creation','workflow','refresh','7 cards','fallback chat/history','revocation']}));

 console.log('PASS local fresh-browser instructor experience');

 }finally{await browser.close()}

})().catch(e=>{console.error(String(e.message).replace(/#[A-Za-z0-9_-]{30,}/g,'#[redacted]').slice(0,1000));process.exitCode=1})
