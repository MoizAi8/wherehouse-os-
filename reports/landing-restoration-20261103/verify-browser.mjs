import {createRequire} from 'node:module';
import {writeFileSync,mkdirSync} from 'node:fs';
const require=createRequire(import.meta.url);const {chromium}=require(process.env.PLAYWRIGHT_MODULE || '../../.tools/qa-browser/node_modules/playwright');
const dir='reports/landing-restoration-20261103';mkdirSync(dir,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});const context=await browser.newContext({baseURL:'http://127.0.0.1:3330',viewport:{width:1440,height:1000}});const page=await context.newPage();
await context.addInitScript(() => {
 localStorage.setItem('warehouse-os-settings',JSON.stringify({appName:'PRIVATE_OWNER_PREFERENCE',apiEndpoint:'https://private.example.invalid'}));
 localStorage.setItem('fulfillos_chat_session','owner-chat-do-not-use');
});
const results=[];const unauthorized=[];page.on('response',r=>{if(r.status()===401)unauthorized.push(new URL(r.url()).pathname)});
const check=(name,value)=>{results.push({name,passed:!!value});if(!value)throw Error(name)};
try{
 await page.goto('/');await page.getByRole('heading',{name:/Intelligence.*orchestrating.*your warehouse/}).waitFor();
 await page.getByRole('button',{name:'Launch Dashboard',exact:true}).waitFor();await page.waitForTimeout(2500);
 check('root displays original landing instead of redirecting',new URL(page.url()).pathname==='/');
 check('original warehouse canvas is visible',await page.locator('canvas').isVisible());
 check('original warehouse descriptions and launch button are present',(await page.locator('body').innerText()).includes('Deploy, monitor, and scale autonomous agents'));
 await page.screenshot({path:dir+'/original-landing.png'});await page.screenshot({path:dir+'/original-landing-full.png',fullPage:true});
 await page.getByRole('button',{name:'Launch Dashboard',exact:true}).click();await page.waitForURL('**/dashboard');
 check('original landing button opens dashboard without login',await page.locator('input[type=password]').count()===0);
await page.getByRole('heading',{name:'Warehouse OS',exact:true}).waitFor();await page.getByRole('button',{name:/Demo Guest/}).waitFor();await page.waitForTimeout(1500);
 check('original landing launches full Warehouse OS dashboard',true);
 check('original sidebar and styling retained',await page.locator('aside.glass-sidebar').isVisible());
 check('separate demo landing is absent',await page.getByRole('heading',{name:'Teacher demonstration',exact:true}).count()===0);
 await page.screenshot({path:dir+'/dashboard-desktop.png',fullPage:true});
 const session=await (await context.request.get('/api/auth/session')).json();check('restricted viewer guest session issued without credentials',session.demoGuest&&session.user.role==='VIEWER');
 for(const [route,title] of [['chat','Chat'],['agents','Agents'],['workflows','Workflows'],['orders','Orders'],['monitoring','Monitoring'],['integrations','Integrations'],['analytics','Analytics'],['team','Team'],['notifications','Notifications'],['settings','Settings']]){
   await page.locator('aside').getByRole('link',{name:title,exact:true}).click();await page.waitForURL('**/dashboard/'+route);await page.locator('h1').first().waitFor();await page.waitForTimeout(400);
   check('original '+route+' page renders',!((await page.locator('main').last().innerText()).includes('Application error')));
   if(route==='settings')check('guest preferences do not expose cached owner configuration',!(await page.locator('main').last().innerText()).includes('PRIVATE_OWNER_PREFERENCE')&&!(await page.locator('main').last().innerText()).includes('private.example.invalid'));
   if(route==='orders'){await page.getByText('sample-demo-001@example.invalid',{exact:true}).waitFor();check('original order table uses isolated samples',true)}
   if(['chat','agents','orders','analytics','integrations'].includes(route))await page.screenshot({path:dir+'/'+route+'-desktop.png',fullPage:true});
 }
 await page.goto('/dashboard/chat');const input=page.getByPlaceholder('Ask anything about your warehouse...');await input.fill('show me all orders');await input.press('Enter');await page.getByText(/DEMO-001/).first().waitFor({timeout:20000});check('original chat reads isolated warehouse records',true);
 await input.fill('delete all orders');await input.press('Enter');await page.getByText(/cannot change orders/).first().waitFor({timeout:20000});check('original chat refuses destructive actions without faking success',true);
 await page.screenshot({path:dir+'/chat-readonly.png',fullPage:true});
 check('guest chat uses a separate local session identifier',await page.evaluate(()=>localStorage.getItem('fulfillos_chat_session')==='owner-chat-do-not-use'&&!!localStorage.getItem('fulfillos_chat_session_guest')));
 check('guest browsing and chat produce no HTTP 401 errors',unauthorized.length===0);
 const headers={Authorization:'Bearer '+session.accessToken};
 check('guest mutation returns explicit 403',(await context.request.post('/api/demo/guest/data?path=/api/v1/orders',{headers,data:{}})).status()===403);
 check('guest token cannot access production orders',(await context.request.get('/api/v1/orders',{headers})).status()===401);
 await page.goto('/demo');await page.waitForURL('**/dashboard');check('old demo URL redirects to original dashboard',true);
 await page.locator('aside').getByRole('link',{name:'Orders',exact:true}).click();await page.waitForURL('**/dashboard/orders');await page.goBack({waitUntil:'domcontentloaded'});await page.waitForURL('**/dashboard');await page.goForward({waitUntil:'domcontentloaded'});await page.waitForURL('**/dashboard/orders');check('browser history navigation works',true);
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:dir+'/orders-mobile-original-layout.png',fullPage:true});check('original navigation remains available at mobile viewport',await page.locator('aside').getByRole('link',{name:'Orders',exact:true}).isVisible());
}catch(e){results.push({name:'browser execution',passed:false,error:String(e.message).slice(0,350)});await page.screenshot({path:dir+'/failure.png',fullPage:true}).catch(()=>{});}
finally{writeFileSync(dir+'/browser.json',JSON.stringify({local_isolated_backend:true,real_browser:'Microsoft Edge',results},null,2));await browser.close()}
console.log(JSON.stringify({checks:results.length,passed:results.filter(r=>r.passed).length,failures:results.filter(r=>!r.passed)}));if(results.some(r=>!r.passed))process.exitCode=1;
