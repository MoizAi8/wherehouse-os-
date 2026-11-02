// Additional regression: actual NextAuth -> frontend proxy -> one-use approval.
import {createRequire} from 'node:module';
import {writeFileSync} from 'node:fs';
const require=createRequire(import.meta.url);
const {chromium}=require('../.tools/qa-browser/node_modules/playwright');
const browser=await chromium.launch({channel:'msedge',headless:true});
const context=await browser.newContext({baseURL:'http://127.0.0.1:3318'});
const page=await context.newPage();
const results=[];
function check(value,message){if(!value)throw Error(message);}
try{
 await page.goto('/api/auth/signin?callbackUrl=%2Fdashboard%2Fchat');
 await page.locator('input[name=email]').fill('qa-admin@example.com');
 await page.locator('input[name=password]').fill('isolated-qa-password');
 await page.locator('button[type=submit]').click();await page.waitForURL(/\/dashboard\/chat/);
 const session=await (await context.request.get('/api/auth/session')).json();
 const count=async()=>{const r=await context.request.get('/api/v1/orders',{headers:{Authorization:`Bearer ${session.accessToken}`}});check(r.ok(),'Fixture order retrieval failed');return (await r.json()).total;};
 const before=await count();
 const input=page.getByPlaceholder('Ask anything about your warehouse...');
 async function send(text){await input.fill(text);await input.press('Enter');await page.getByRole('button',{name:'Confirm warehouse action',exact:true}).waitFor();}
 await send('create order browser-cancel@example.com Lahore 2kg');
 check(await count()===before,'Unconfirmed operation wrote an order');results.push('unconfirmed action preserves order count');
 await page.getByRole('button',{name:'Cancel action',exact:true}).click();
 check(await page.getByRole('button',{name:'Confirm warehouse action',exact:true}).count()===0,'Cancelled approval remains actionable');
 check(await count()===before,'Cancelled action wrote an order');results.push('cancel action preserves order count');
 await send('create order browser-confirm@example.com Lahore 3kg');
 const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/chat');
 await page.getByRole('button',{name:'Confirm warehouse action',exact:true}).click();
 const body=await (await response).json();check(body.action==='create_order_created','Confirmed proxy request failed');
 check(await count()===before+1,'Confirmation did not create exactly one fixture order');results.push('confirmed action forwarded once through real NextAuth proxy');
 const orders=await (await context.request.get('/api/v1/orders',{headers:{Authorization:`Bearer ${session.accessToken}`}})).json();
 const created=orders.orders.find(x=>x.customer_email==='browser-confirm@example.com');
 check(created&&created.status==='pending','Order was automatically routed');results.push('creation does not automatically dispatch a shipment');
 writeFileSync(new URL('../reports/teacher-demo-20261103/confirmation-browser.json',import.meta.url),JSON.stringify({real_browser:true,synthetic_only:true,passed:results.length,checks:results},null,2));
 console.log(`${results.length} real confirmation browser checks passed`);
}finally{await context.close();await browser.close();}
