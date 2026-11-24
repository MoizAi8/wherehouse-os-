const {chromium}=require('../.tools/qa-browser/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const origin='http://127.0.0.1:3397';
 const browser=await chromium.launch({channel:'msedge'});
 try{
 const page=await browser.newPage();
 page.on('response',r=>{if(r.status()>=400)console.log(r.status(),new URL(r.url()).pathname)});
 await page.goto(origin);
 await page.getByRole('button',{name:'Launch Dashboard'}).click();
 await page.waitForURL(origin+'/dashboard');
 await page.getByRole('link',{name:'Inventory',exact:true}).first().click();
 const sku='HOSTED-'+Date.now();
 await page.getByLabel('SKU',{exact:true}).fill(sku);await page.getByLabel('Product name').fill('Instructor boxes');await page.getByRole('button',{name:'Add product'}).click();
 await page.getByRole('option',{name:new RegExp(sku)}).first().waitFor({state:'attached'});
 await page.getByLabel('Product',{exact:true}).selectOption(sku);
 await page.getByLabel('Fulfillment center').selectOption({label:'Evaluation Center'});
 await page.getByRole('button',{name:'Add stock location'}).click();
 await page.getByLabel('Quantity change').fill('5');await page.getByLabel('Movement reason').fill('Instructor receipt');
 await page.getByRole('button',{name:'Record movement'}).click();await page.getByText(/On hand 5.*Reserved 0.*Available 5/).waitFor();
 const stock=await page.getByLabel('Stock location',{exact:true}).inputValue();
 await page.reload();await page.getByLabel('Stock location',{exact:true}).selectOption(stock);await page.getByText(/On hand 5.*Reserved 0.*Available 5/).waitFor();
 for(const [label,value] of Object.entries({'Order reference':sku,'Customer email':'instructor@example.com','Shipping address':'Sandbox','Postal code':'10001','Shipping city':'Test','State or region':'NY','Total weight (kg)':'1'})){
  await page.getByLabel(label,{exact:true}).fill(value)
 }
 await page.getByRole('button',{name:'Add order line'}).click();
 await page.getByLabel('Line 1 SKU').selectOption(sku);
 await page.getByLabel('Line 1 quantity').fill('1');
 const order=page.waitForResponse(r=>r.url().endsWith('/api/v1/orders')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Create and allocate order'}).click();
 assert.equal((await order).status(),201);
 await page.getByRole('link',{name:'Agents',exact:true}).first().click();
 const run = page.waitForResponse(r=>r.url().endsWith('/api/evaluation/workflow')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Run Evaluation Workflow'}).click();assert.equal((await run).status(),202);
 await page.waitForFunction(()=>document.querySelector('section p[aria-live]')?.textContent?.startsWith('Completed'),null,{timeout:120000});
 const cards=page.waitForResponse(r=>r.url().endsWith('/api/v1/agents/status'));
 await page.getByRole('button',{name:'Refresh agent status'}).click();
 const data=await(await cards).json();assert.equal(data.agents.length,7);
 for(const a of data.agents){assert.equal(a.status,'IDLE');const card=page.getByRole('heading',{name:a.name,exact:true}).locator('../..');await card.locator('summary').click();await card.getByText('Event '+a.event_id,{exact:true}).waitFor()}
 console.log('PASS browser root, original dashboard, inventory persistence, workflow and seven persisted event IDs');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1})
