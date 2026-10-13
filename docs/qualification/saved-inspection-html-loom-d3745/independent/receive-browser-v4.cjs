'use strict';
// Versioned environment adaptation after Playwright failed before browser launch.
// Preserve the original fixed predicates, supplied HTML/oracle and failed v3 receipt.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const os=require('node:os'),assert=require('node:assert/strict');
const {isDeepStrictEqual}=require('node:util'),{pathToFileURL}=require('node:url');
const root=path.resolve(process.argv[2]),out=path.join(root,'browser-v4');
fs.mkdirSync(out);
const receipt={schema:'hamon.root.fanout-inspection-html-browser.v4',started:new Date().toISOString(),pid:process.pid,runtime:process.version,accepted:false,checks:[],requests:[],page_errors:[],browser_console_errors:[],scope:'Same frozen file-origin display/download observations, adapted after candidate exposure from broken installed Python Playwright to the independently verified native Firefox/Puppeteer route. Original failed v3 history retained; no renderer/CLI rerun.'};
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
function ident(p){const s=fs.lstatSync(p);assert(s.isFile()&&!s.isSymbolicLink());const b=fs.readFileSync(p);return{bytes:b.length,sha256:digest(b),mode:s.mode&0o777};}
const check=(name,actual,expected)=>{const passed=isDeepStrictEqual(actual,expected);receipt.checks.push({name,actual,expected,passed});assert.deepEqual(actual,expected,name);};
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(name,fn,ms=10000){const end=Date.now()+ms;while(Date.now()<end){if(await fn())return;await delay(40);}throw Error('Timeout: '+name);}
const inputs=Object.fromEntries(['typed.html','typed-oracle.json'].map(n=>[n,path.join(root,'inputs',n)]));
receipt.before=Object.fromEntries(Object.entries(inputs).map(([n,p])=>[n,ident(p)]));
const manifest=JSON.parse(fs.readFileSync(path.join(root,'browser-inputs.json'),'utf8'));
const profile=path.join(out,'owned-profile'),tmp=path.join(out,'tmp'),downloads=path.join(out,'downloads');
let browser,context,browserProcess,closedSafely=true;
async function run(){
 const user=os.userInfo();
 check('host',os.hostname(),'hamon-thinkpad');
 check('account',[user.username,user.uid,user.homedir],['jacob',1000,'/home/jacob']);
 for(const [name,p] of Object.entries(inputs))for(const k of ['bytes','sha256'])check(name+' '+k,receipt.before[name][k],manifest.inputs[name][k]);
 const oracle=fs.readFileSync(inputs['typed-oracle.json']),report=JSON.parse(oracle);
 check('fresh browser profile',fs.existsSync(profile),false);
 for(const p of [profile,tmp,downloads])fs.mkdirSync(p);
 const packageRoot='/home/jacob/.local/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer';
 const puppeteer=require(packageRoot);
 receipt.puppeteer_version=JSON.parse(fs.readFileSync(path.join(packageRoot,'package.json'),'utf8')).version;
 check('verified Puppeteer version',receipt.puppeteer_version,'25.12.0');
 closedSafely=false;
 browser=await puppeteer.launch({browser:'firefox',executablePath:'/usr/bin/firefox',headless:true,userDataDir:profile,env:{...process.env,TMPDIR:tmp}});
 browserProcess=browser.process();receipt.browser_pid=browserProcess.pid;receipt.browser_version=await browser.version();
 context=await browser.createBrowserContext({downloadBehavior:{policy:'allow',downloadPath:downloads}});
 const page=await context.newPage();await page.setViewport({width:1440,height:1000});
 page.on('request',request=>receipt.requests.push(request.url()));
 page.on('pageerror',error=>receipt.page_errors.push(String(error)));
 page.on('console',message=>{if(message.type()==='error')receipt.browser_console_errors.push(message.text());});
 const url=pathToFileURL(inputs['typed.html']).href;
 await page.goto(url,{waitUntil:'load',timeout:15000});
 check('file origin',page.url(),url);
 check('no active/external embedding',await page.$$eval('script,iframe,object,embed,form,input,textarea,button',items=>items.length),0);
 await page.$$eval('details',items=>{for(const item of items)if(!item.hasAttribute('open'))item.querySelector('summary').click();});
 const text=await page.$eval('body',e=>e.innerText);
 check('first label visible',text.toLowerCase().includes('first'),true);
 check('second label visible',text.toLowerCase().includes('second'),true);
 check('saved data scope visible',['saved data','saved-data','saved inspection'].some(s=>text.toLowerCase().includes(s)),true);
 for(const side of ['first','second'])check(side+' complete raw identity visible',text.includes(report[side].input_sha256),true);
 for(const token of ['nullable','ready','accepted','count','offset','outcome_unknown','blocked'])check('typed content visible '+token,text.includes(token),true);
 receipt.desktop_body_text=text;
 check('desktop no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true);
 await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
 const selector='a[download][href^="data:"]';
 check('one native download',await page.$$eval(selector,items=>items.length),1);
 const declaredHref=await page.$eval(selector,e=>e.href);
 await page.click(selector);
 let saved;
 await until('actual original JSON download',()=>{
  for(const n of fs.readdirSync(downloads)){
   const p=path.join(downloads,n);
   if(n.endsWith('.json')&&fs.lstatSync(p).isFile()&&fs.readFileSync(p).equals(oracle)){saved=p;return true;}
  }
  return false;
 });
 receipt.download={path:saved,...ident(saved)};
 check('actual downloaded original JSON',fs.readFileSync(saved).toString('base64'),oracle.toString('base64'));
 check('download completes without partial file',fs.readdirSync(downloads).filter(n=>n.endsWith('.part')),[]);
 await page.setViewport({width:390,height:844});
 check('narrow no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true);
 check('download remains reachable',await page.$eval(selector,e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;}),true);
 receipt.narrow_scroll_containers=await page.evaluate(()=>Array.from(document.querySelectorAll('*')).filter(e=>e.scrollWidth>e.clientWidth+2&&e.clientWidth>0).map(e=>({tag:e.tagName,width:e.clientWidth,scrollWidth:e.scrollWidth,overflow:getComputedStyle(e).overflowX})).slice(0,30));
 receipt.narrow_body_text=await page.$eval('body',e=>e.innerText);
 await page.screenshot({path:path.join(out,'narrow.png'),fullPage:true});
 check('page exceptions',receipt.page_errors,[]);
 check('browser console errors',receipt.browser_console_errors,[]);
 check('no page external requests',receipt.requests.filter(u=>u!==url&&u!==declaredHref),[]);
 await context.close();context=null;
 await browser.close();browser=null;
 await until('owned Firefox process exit',()=>browserProcess.exitCode!==null||browserProcess.signalCode!==null);
 receipt.browser_exit=browserProcess.exitCode;receipt.browser_signal=browserProcess.signalCode;
 check('owned browser exit',receipt.browser_exit,0);
 closedSafely=true;receipt.accepted=true;
}
(async()=>{
 try{await run();}
 catch(error){receipt.error=error.stack||String(error);}
 finally{
  if(context){try{await context.close();context=null;}catch(error){receipt.context_close_error=String(error);}}
  if(browser){try{await browser.close();browser=null;}catch(error){receipt.browser_close_error=String(error);}}
  if(browserProcess){
   if(browserProcess.exitCode===null&&browserProcess.signalCode===null){
    try{await until('owned browser cleanup exit',()=>browserProcess.exitCode!==null||browserProcess.signalCode!==null,3000);}
    catch(error){receipt.cleanup_wait_error=String(error);}
   }
   closedSafely=browserProcess.exitCode!==null||browserProcess.signalCode!==null;
   receipt.final_browser_exit=browserProcess.exitCode;receipt.final_browser_signal=browserProcess.signalCode;
  }
  receipt.after=Object.fromEntries(Object.entries(inputs).map(([n,p])=>[n,ident(p)]));
  if(!isDeepStrictEqual(receipt.before,receipt.after)){receipt.accepted=false;receipt.custody_error='inputs changed';}
  receipt.closed_safely=closedSafely;
  if(closedSafely){for(const p of [profile,tmp])if(fs.existsSync(p)){assert(path.dirname(p)===out&&!fs.lstatSync(p).isSymbolicLink());fs.rmSync(p,{recursive:true});}receipt.owned_profile_removed=!fs.existsSync(profile);}
  else{receipt.accepted=false;receipt.profile_retained_for_recovery=true;}
  receipt.finished=new Date().toISOString();
  fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({accepted:receipt.accepted,checks:receipt.checks.length,preserved:isDeepStrictEqual(receipt.before,receipt.after),browser_exit:receipt.final_browser_exit,error:receipt.error}));
  process.exitCode=receipt.accepted?0:1;
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
