import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.join(process.env.RADAR_BROWSER_DEPS||process.cwd(),'package.json'));
const engine=process.env.RADAR_BROWSER_ENGINE||'chromium';
const browserType=require('playwright')[engine];
assert.ok(browserType,'unsupported browser engine '+engine);
const base='http://127.0.0.1:8765/';
const out=process.env.RADAR_SCREENSHOTS||'/tmp/radar-screenshots';
fs.mkdirSync(out,{recursive:true});
const digest=JSON.parse(fs.readFileSync('site/data/model-releases-30d.json','utf8'));
const browser=await browserType.launch({headless:true});
const overviewFiles=['model-releases-30d.json','model-monitor-status.json','aihot-items.json','aihot-daily.json','juya-daily.json'];
const overviewBytes=overviewFiles.reduce((n,f)=>n+fs.statSync(path.join('site/data',f)).size,0);
const htmlBytes=fs.statSync('site/index.html').size;
console.log('BUDGET '+engine+' HTML '+htmlBytes+' bytes; overview JSON '+overviewBytes+' bytes');
assert.ok(htmlBytes<=320*1024,'HTML exceeds 320 KiB; review payload growth');
assert.ok(overviewBytes<=256*1024,'overview snapshots exceed 256 KiB; review data growth');
const failures=[];
try{
 for(const viewport of [{width:1440,height:1000},{width:390,height:844},{width:360,height:800}]){
  const label=viewport.width===1440?'desktop':String(viewport.width);
  const context=await browser.newContext({viewport,locale:'zh-CN',deviceScaleFactor:1,reducedMotion:'reduce'});
  await context.route('**/*',route=>route.request().url().startsWith(base)?route.continue():route.abort());
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.clock.setFixedTime(new Date(digest.windowEnd+'T14:00:00+08:00'));
  const routes=['overview','today','feeds','social','models','rankings','topics','practice','platforms','opportunities'];
  async function check(name,fn){try{await fn();console.log('PASS '+label+' '+name)}catch(e){failures.push(label+' '+name+': '+e.message);console.log('FAIL '+label+' '+name+': '+e.stack);await page.screenshot({path:path.join(out,label+'-failure-'+name.replaceAll(' ','-')+'.png'),animations:'disabled'}).catch(()=>{})}}
  for(const view of routes)await check(view,async()=>{
   const loaded=new Set();const capture=req=>{if(req.url().includes('/data/'))loaded.add(new URL(req.url()).pathname.split('/').pop())};page.on('request',capture);
   await page.goto(base+'?view='+view,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>state.dataReady);
   await page.locator('#content h1').first().waitFor();
   await page.screenshot({path:path.join(out,label+'-'+view+'.png'),animations:'disabled'});
   const sizes=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,heading:parseFloat(getComputedStyle(document.querySelector('#content h1')).fontSize)}));
   assert.ok(sizes.scroll<=sizes.width+2,'document overflow '+JSON.stringify(sizes));
   assert.ok(sizes.heading>=23,'heading too small');
   if(view==='models'){
    const result=await page.locator('.model-table').evaluate(t=>({font:parseFloat(getComputedStyle(t).fontSize),vendor:getComputedStyle(t.querySelector('tbody td:first-child')).position,model:getComputedStyle(t.querySelector('tbody td:nth-child(2)')).position,wrap:t.parentElement.clientWidth,table:t.scrollWidth}));
    assert.ok(result.font>=13);assert.equal(result.model,'sticky');if(viewport.width<761){assert.equal(result.vendor,'static');assert.ok(result.table>result.wrap)}
   }
   if(view==='overview')assert.equal(await page.locator('.overview-dashboard .overview-column').count(),2);
   if(view==='rankings'){
    const principles=page.locator('.rank-principles details');assert.equal(await principles.evaluate(el=>el.open),false);await principles.locator('summary').click();assert.equal(await principles.evaluate(el=>el.open),true);await principles.locator('summary').click();
    const table=await page.locator('.rank-table').evaluate(el=>({font:parseFloat(getComputedStyle(el).fontSize),header:getComputedStyle(el.querySelector('th')).position,numeric:getComputedStyle(el.querySelector('th:nth-child(3)')).textAlign}));
    assert.ok(table.font>=13);assert.equal(table.header,'sticky');assert.equal(table.numeric,'right');
   }
   if(view==='today')assert.ok(await page.locator('.release-main').count()>0);
   if(view==='overview'){assert.equal(loaded.size,5);assert.ok(!loaded.has('models.json'));assert.ok(!loaded.has('unified-rankings.json'))}if(view==='rankings')assert.deepEqual([...loaded],['unified-rankings.json']);page.off('request',capture);
   console.log('DATA '+label+' '+view+' '+loaded.size+' requests');
  });
  if(viewport.width===1440)await check('desktop folding navigation',async()=>{
   await page.goto(base+'?view=overview',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   const toggle=page.locator('#desktopNavToggle'),sidebar=page.locator('#sidebar');
   assert.equal(await toggle.getAttribute('aria-expanded'),'true');const expanded=await sidebar.evaluate(el=>el.getBoundingClientRect().width);
   await toggle.click();assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert.ok(await sidebar.evaluate(el=>el.getBoundingClientRect().width)<expanded);
   await page.screenshot({path:path.join(out,label+'-compact-nav.png')});
   await page.reload();await page.waitForFunction(()=>state.dataReady);assert.equal(await toggle.getAttribute('aria-expanded'),'false');
   await sidebar.locator('[data-view="models"]').click();await page.waitForFunction(()=>state.dataReady);assert.equal(await page.evaluate(()=>state.view),'models');
   await toggle.click();const group=sidebar.locator('[data-nav-group-toggle="resources"]');await group.click();assert.equal(await group.getAttribute('aria-expanded'),'false');assert.equal(await sidebar.locator('[data-view="practice"]').isVisible(),false);
   await page.reload();await page.waitForFunction(()=>state.dataReady);assert.equal(await group.getAttribute('aria-expanded'),'false');await group.click();
   assert.equal(await sidebar.locator('[data-view="practice"]').isVisible(),true);
  });
  if(viewport.width<761)await check('mobile navigation',async()=>{
   await page.goto(base+'?view=overview',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   const menu=page.locator('#mobileMenu'),sidebar=page.locator('#sidebar');
   assert.equal(await menu.getAttribute('aria-expanded'),'false');
   assert.equal(await sidebar.evaluate(el=>el.inert),true,'closed sidebar must be inert');
   await menu.click();assert.equal(await menu.getAttribute('aria-expanded'),'true');
   assert.equal(await page.locator('main').evaluate(el=>el.inert),true,'open menu must make main inert');
   await page.waitForFunction(()=>document.activeElement===document.getElementById('mobileNavClose'),null,{timeout:2000});
   await page.keyboard.press('Shift+Tab');assert.equal(await sidebar.locator('[data-view]').last().evaluate(el=>el===document.activeElement),true,'reverse Tab must wrap');
   await page.keyboard.press('Tab');assert.equal(await page.locator('#mobileNavClose').evaluate(el=>el===document.activeElement),true,'Tab must wrap');
   await page.screenshot({path:path.join(out,label+'-mobile-nav.png')});
   await page.keyboard.press('Escape');assert.equal(await menu.getAttribute('aria-expanded'),'false');
   await page.waitForFunction(()=>document.activeElement===document.getElementById('mobileMenu'),null,{timeout:2000});
   await menu.click();await sidebar.locator('[data-view="models"]').click();await page.waitForFunction(()=>state.dataReady);
   assert.equal(await page.evaluate(()=>state.view),'models');assert.equal(await menu.getAttribute('aria-expanded'),'false');
   assert.equal(await page.locator('main').evaluate(el=>el.inert),false);
   await menu.click();await page.locator('#navBackdrop').click({position:{x:viewport.width-10,y:100}});assert.equal(await menu.getAttribute('aria-expanded'),'false');
  });
  if(viewport.width!==360)await check('search-and-version',async()=>{
   await page.goto(base+'?view=models&category=image',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   await page.keyboard.press('Control+k');await page.locator('#globalSearchDialog').waitFor({state:'visible'});await page.waitForFunction(()=>state.indexReady);
   await page.locator('#globalSearchInput').fill('Seedance 2.0');
   await page.locator('[data-global-type="model"]').click();await page.screenshot({path:path.join(out,label+'-search.png')});
   await page.locator('#globalSearchInput').press('Enter');await page.locator('.model-detail-version-selected').waitFor({state:'visible'});
   assert.equal(await page.locator('.model-detail-version-selected').getAttribute('data-version-id'),'seedance-2-0');
   await page.screenshot({path:path.join(out,label+'-version.png')});
   await page.keyboard.press('Escape');await page.locator('.model-detail-panel').waitFor({state:'hidden'});
   assert.equal(await page.evaluate(()=>state.modelCategory),'image');
  });
  if(viewport.width!==360)await check('creator workflow',async()=>{
   await page.goto(base+'?view=opportunities&tab=programs',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   const progress=page.locator('[data-creator-progress]').first();await progress.selectOption('watch');await page.reload();await page.waitForFunction(()=>state.dataReady);assert.equal(await page.locator('[data-creator-progress]').first().inputValue(),'watch');
   await page.screenshot({path:path.join(out,label+'-programs.png')});
   await page.goto(base+'?view=practice&type=prompt',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);assert.ok(await page.locator('[data-copy-template="product-tvc"]').count());await page.screenshot({path:path.join(out,label+'-prompts.png')});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+2));
  });
  if(viewport.width!==360)await check('public history and cold model navigation',async()=>{
   const local=[];const listener=req=>{if(req.url().includes('/__local/'))local.push(req.url())};page.on('request',listener);
   await page.goto(base+'?view=topics&topic=google',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   await page.locator('.topic-event').first().waitFor();assert.equal(local.length,0);
   await page.locator('[data-topic-cat="image"]').click();assert.equal(await page.evaluate(()=>state.topicCategory),'image');
   await page.screenshot({path:path.join(out,label+'-history.png')});
   await page.goto(base+'?view=today',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   assert.equal(await page.evaluate(()=>!!dataSettled.models),false);
   const first=page.locator('.release-model-link').first();const version=await first.getAttribute('data-model-version');await first.click();
   await page.locator('.model-detail-panel').waitFor({state:'visible'});if(version)assert.equal(await page.locator('.model-detail-version-selected').getAttribute('data-version-id'),version);
   await page.keyboard.press('Escape');await page.locator('.model-detail-panel').waitFor({state:'hidden'});assert.equal(await page.evaluate(()=>state.view),'today');
   page.off('request',listener);
  });
  await check('no runtime errors',async()=>assert.deepEqual(errors,[]));await context.close();
 }
}finally{await browser.close()}
if(failures.length){console.error(failures.join('\n'));process.exitCode=1}
