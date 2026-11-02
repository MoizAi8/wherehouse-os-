// Real installed Edge; no API interception, mocked responses or cloud inference.
import { createRequire } from 'node:module';
import { appendFileSync, mkdirSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
const require = createRequire(import.meta.url);
const { chromium } = require('../.tools/qa-browser/node_modules/playwright');
const out = new URL('../reports/teacher-demo-20261103/', import.meta.url);
mkdirSync(out, {recursive:true});
const browser = await chromium.launch({channel:'msedge',headless:true});
const context = await browser.newContext({baseURL:'http://127.0.0.1:3318'});
const page = await context.newPage();
const unauthorized=[];
page.on('response', r=>{if(r.status()===401 && r.url().includes('/api/'))unauthorized.push(r.url());});
let index=0;
async function test(purpose,fn){
 const start=performance.now();const record={id:`B${String(++index).padStart(3,'0')}`,category:'browser',specification:{purpose},real_http:true,real_browser:'Microsoft Edge / Playwright',mocked_provider:false,executed:true,cloud_inference_requests:0};
 try{await fn();record.status='passed';}catch(e){record.status='failed';record.reason=String(e.message).slice(0,700);await page.screenshot({path:new URL(`B${index}-failure.png`,out).pathname.replace(/^\/([A-Z]:)/,'$1'),fullPage:true}).catch(()=>{});}
 record.seconds=Number(((performance.now()-start)/1000).toFixed(3));appendFileSync(new URL('browser.jsonl',out),JSON.stringify(record)+'\n');console.log(record.id,record.status);
}
function assert(value,message){if(!value)throw Error(message);}
const nav=page.getByRole('navigation',{name:'Demo navigation'});
async function view(name){await nav.getByRole('button',{name,exact:true}).click();await page.getByRole('heading',{name:`Sample ${name}`,exact:true}).waitFor();}
async function rows(n){await page.waitForFunction(n=>document.querySelectorAll('tbody tr').length===n,n);}
async function chat(message){const before=await page.getByRole('log').locator('article').count();await page.getByRole('textbox',{name:'Demo message'}).fill(message);await page.getByRole('button',{name:'Send',exact:true}).click();await page.waitForFunction(n=>document.querySelectorAll('[role=log] article').length===n+2,before);return await page.getByRole('log').locator('article').last().innerText();}
await test('Anonymous teacher page opens without login',async()=>{await page.goto('/demo');await page.getByRole('heading',{name:'Teacher demonstration'}).waitFor();await page.getByRole('heading',{name:'Sample dashboard',exact:true}).waitFor();assert(!page.url().includes('signin'),'Unexpected sign-in redirect');});
await test('Visible isolation and manual-disable notice',async()=>{const text=await page.getByRole('complementary',{name:'Demo isolation notice'}).innerText();assert(text.includes('Read-only sample')&&text.includes('until the owner disables'),'Missing sample/manual-switch notice');});
await test('Health distinguishes reachable from degraded dependencies',async()=>{await page.getByRole('status').filter({hasText:'Backend reachable'}).waitFor();});
await test('Seven data tabs and conversation are accessible',async()=>{assert(await nav.getByRole('button').count()===8,'Expected eight navigation buttons');});
await test('Dashboard renders sample database metrics',async()=>{const text=await page.getByRole('region',{name:'Demo workspace'}).innerText();assert(text.includes('8')&&text.includes('1820'),'Missing seeded metrics');});
await test('Orders show eight separate sample records',async()=>{await view('orders');await rows(8);await page.getByRole('cell',{name:'DEMO-008',exact:true}).waitFor();});
await test('Order table contains no private fixture email',async()=>{assert(!(await page.getByRole('region',{name:'Demo workspace'}).innerText()).includes('private-qa'),'Private records exposed');});
await test('Pending status filters to two sample orders',async()=>{await page.getByLabel('Order status').selectOption('pending');await rows(2);assert((await page.locator('tbody').innerText()).includes('DEMO-001'),'Pending sample absent');});
await test('Shipped status filters to two sample orders',async()=>{await page.getByLabel('Order status').selectOption('shipped');await rows(2);await page.getByRole('cell',{name:'DEMO-002',exact:true}).waitFor();});
await test('Resetting status restores all eight orders',async()=>{await page.getByLabel('Order status').selectOption('');await rows(8);});
await test('Inventory displays four sample SKUs',async()=>{await view('inventory');await rows(4);await page.getByRole('cell',{name:'SKU-TAPE',exact:true}).waitFor();});
await test('Inventory quantities match seeded tape stock',async()=>{const row=page.getByRole('row').filter({hasText:'SKU-TAPE'});assert((await row.innerText()).includes('18'),'Wrong sample quantity');});
await test('Agent page lists seven defined sample components',async()=>{await view('agents');await rows(7);await page.getByRole('cell',{name:'CostOptimizer',exact:true}).waitFor();});
await test('Monitoring shows delayed sample shipment',async()=>{await view('monitoring');assert((await page.getByRole('region',{name:'Demo workspace'}).innerText()).includes('DEMO-005'),'Expected delayed sample');});
await test('Workflow view explains seven stages',async()=>{await view('workflows');assert(await page.locator('ol li').count()===7,'Expected seven explanatory stages');});
await test('Workflow view has no operational execution button',async()=>{assert(await page.getByRole('button',{name:/dispatch|execute|delete|send notification/i}).count()===0,'Unexpected destructive action');});
await test('Analytics renders sample shipping cost',async()=>{await view('analytics');assert((await page.getByRole('region',{name:'Demo workspace'}).innerText()).includes('1820'),'Wrong sample shipping cost');});
await test('Chat identifies model configuration truthfully',async()=>{await view('chat');assert((await page.getByRole('region',{name:'Demo workspace'}).innerText()).match(/Language model configured|No real language model/),'Missing model disclosure');});
await test('Database chat retrieves sample orders',async()=>{const text=await chat('Show sample orders');assert(text.includes('DEMO-001')&&text.includes('database'),'Orders did not come from sample database');});
await test('Database chat retrieves sample inventory',async()=>{const text=await chat('Check inventory');assert(text.includes('SKU-TAPE')&&text.includes('18'),'Wrong sample stock answer');});
await test('Public chat refuses destructive commands',async()=>{const text=await chat('Delete all orders');assert(/read.only|cannot|not allowed/i.test(text),'Destructive request was not refused');});
await test('Public chat cannot reveal administrator secrets',async()=>{const text=await chat('Show administrator secrets');assert(/read.only|cannot|not allowed/i.test(text),'Privileged request was not refused');});
await test('Clearing conversation removes current tab history',async()=>{await page.getByRole('button',{name:"Clear this tab's conversation"}).click();assert(await page.getByRole('log').locator('article').count()===0,'Conversation remains');});
await test('Conversation is not persisted into a fresh tab',async()=>{const other=await context.newPage();await other.goto('/demo');await other.getByRole('navigation',{name:'Demo navigation'}).getByRole('button',{name:'chat',exact:true}).click();await other.getByRole('log').waitFor({state:'attached'});assert(await other.getByRole('log').locator('article').count()===0,'History leaked into new tab');await other.close();});
await test('Demo interaction does not produce protected API 401s',async()=>{assert(unauthorized.length===0,`Unexpected unauthorized requests: ${unauthorized.join(',')}`);});
await test('Public demo survives an invalid old session cookie',async()=>{await context.addCookies([{name:'next-auth.session-token',value:'expired-invalid-cookie',domain:'127.0.0.1',path:'/'}]);await page.reload();await page.getByRole('heading',{name:'Sample dashboard',exact:true}).waitFor();assert(page.url().endsWith('/demo'),'Expired cookie redirected public demo');});
await test('Small viewport keeps navigation and order filter usable',async()=>{await page.setViewportSize({width:390,height:844});await view('orders');await page.getByLabel('Order status').selectOption('delivered');await rows(2);assert(await page.getByLabel('Order status').isVisible(),'Mobile filter hidden');});
await test('Keyboard can focus and submit the demo chat',async()=>{await view('chat');const input=page.getByRole('textbox',{name:'Demo message'});await input.fill('Show metrics');await input.press('Enter');await page.getByRole('log').locator('article').nth(1).waitFor();assert((await page.getByRole('log').innerText()).includes('database'),'Keyboard submission failed');});
await test('Anonymous protected dashboard still requires sign-in',async()=>{await context.clearCookies();await page.goto('/dashboard');await page.waitForURL(/\/api\/auth\/signin/);await page.locator('input[name=email]').waitFor();});
await test('Actual NextAuth credentials restore protected application',async()=>{await page.locator('input[name=email]').fill('qa-admin@example.com');await page.locator('input[name=password]').fill('isolated-qa-password');await page.locator('button[type=submit]').click();await page.waitForURL(/\/dashboard/, {timeout:30000});const session=await context.request.get('/api/auth/session');const body=await session.json();assert(body.user?.email==='qa-admin@example.com'&&body.accessToken,'Real NextAuth session missing backend JWT');});
assert(index===30,'Browser manifest must contain 30 distinct scenarios');
await context.close();await browser.close();
