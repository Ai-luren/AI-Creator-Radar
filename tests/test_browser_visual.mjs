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
 for(const viewport of [{width:1440,height:900},{width:390,height:844},{width:360,height:800}]){
  const label=viewport.width===1440?'desktop':String(viewport.width);
  let context,page;const errors=[];
  // Each scenario begins from a fresh browser context; within a scenario reloads
  // retain storage/history. A crashed renderer must not poison following scenarios.
  const routes=['overview','today','feeds','social','models','rankings','topics','practice','platforms','opportunities'];
  async function check(name,fn){
   context=null;page=null;
   try{
    context=await browser.newContext({viewport,locale:'zh-CN',deviceScaleFactor:1,reducedMotion:'reduce'});
    await context.route('**/*',route=>route.request().url().startsWith(base)?route.continue():route.abort());
    page=await context.newPage();page.on('pageerror',e=>errors.push(name+': '+e.message));
    await page.clock.setFixedTime(new Date(digest.windowEnd+'T14:00:00+08:00'));
    await fn();console.log('PASS '+label+' '+name)
   }catch(e){
    failures.push(label+' '+name+': '+e.message);console.log('FAIL '+label+' '+name+': '+e.stack);
    if(page)await page.screenshot({path:path.join(out,label+'-failure-'+name.replaceAll(' ','-')+'.png'),animations:'disabled',timeout:5000}).catch(()=>{})
   }finally{if(context)await context.close().catch(e=>{failures.push(label+' '+name+' context close: '+e.message)})}
  }
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
   if(view==='overview'){assert.equal(await page.locator('.overview-dashboard .overview-column').count(),2);assert.equal(await page.locator('.overview-category').count(),6);assert.equal(await page.locator('.overview-module').count(),9);if(viewport.width>=1280){const cols=await page.locator('.overview-category-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length);assert.equal(cols,6);}}
   if(view==='feeds'){const list=page.locator('.combined-news-list').first();if(await list.count()){const layout=await list.evaluate(el=>({display:getComputedStyle(el).display,cols:getComputedStyle(el).gridTemplateColumns.split(' ').length}));if(viewport.width>=1280){assert.equal(layout.display,'grid');assert.equal(layout.cols,2)}else assert.equal(layout.display,'block');}}
   if(view==='rankings'){
    assert.equal(await page.locator('.rank-row-evidence').count(),0);const evidence=page.locator('details.rank-board-nav').filter({has:page.locator('summary').filter({hasText:'原榜分数区间与名次范围'})});assert.equal(await evidence.count(),1);assert.equal(await page.locator('.rank-table tbody tr').count(),10);if(viewport.width>=1200){const rect=await page.locator('.rank-table').evaluate(el=>({bottom:el.getBoundingClientRect().bottom,viewport:window.innerHeight,width:el.scrollWidth,container:el.parentElement.clientWidth}));assert.ok(rect.bottom<=rect.viewport,'Top 10 must fit in viewport '+JSON.stringify(rect));assert.ok(rect.width<=rect.container+2,'rank table horizontal overflow');}
    const principles=page.locator('.rank-principles details');assert.equal(await principles.evaluate(el=>el.open),false);await principles.locator('summary').click();assert.equal(await principles.evaluate(el=>el.open),true);await principles.locator('summary').click();
    const table=await page.locator('.rank-table').evaluate(el=>({font:parseFloat(getComputedStyle(el).fontSize),header:getComputedStyle(el.querySelector('th')).position,numeric:getComputedStyle(el.querySelector('th:nth-child(3)')).textAlign}));
    assert.ok(table.font>=13);assert.equal(table.header,'sticky');assert.equal(table.numeric,'right');if(viewport.width<761){const fit=await page.locator('.rank-table').evaluate(el=>({width:el.scrollWidth,container:el.parentElement.clientWidth}));assert.ok(fit.width<=fit.container+2,'mobile ranking must show score and samples without horizontal scroll');}
   }
   if(view==='models'&&viewport.width>=1200){const fit=await page.locator('.model-table').evaluate(el=>({width:el.scrollWidth,container:el.parentElement.clientWidth}));assert.ok(fit.width<=fit.container+2,'model table horizontal overflow '+JSON.stringify(fit));}
   if(view==='platforms'){const fav=page.locator('.platform-favorite').first();if(await fav.count()){const checkCenter=async()=>{const delta=await fav.evaluate(el=>{const a=el.getBoundingClientRect(),b=el.querySelector('svg').getBoundingClientRect();return {x:Math.abs(a.x+a.width/2-b.x-b.width/2),y:Math.abs(a.y+a.height/2-b.y-b.height/2)}});assert.ok(delta.x<=1&&delta.y<=1,'favorite star not centered '+JSON.stringify(delta));};await checkCenter();await fav.click();await checkCenter();await fav.click();}}
   if(viewport.width>=1440&&['practice','platforms'].includes(view)){const grid=page.locator(view==='practice'?'.practice-grid':'.platform-grid').first();if(await grid.count())assert.equal(await grid.evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length),4);}
   if(view==='today')assert.ok(await page.locator('.release-main').count()>0);
   if(view==='overview'){assert.equal(loaded.size,5);assert.ok(!loaded.has('models.json'));assert.ok(!loaded.has('unified-rankings.json'))}if(view==='rankings')assert.deepEqual([...loaded],['unified-rankings.json']);page.off('request',capture);
   console.log('DATA '+label+' '+view+' '+loaded.size+' requests');
  });
  await check('video rankings responsive comparison',async()=>{
   await page.goto(base+'?view=rankings&category=video&task=image-to-video-audio',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   const panels=page.locator('.rank-task-panel');assert.equal(await panels.count(),2);
   const selected=page.locator('.rank-task-selected');assert.equal(await selected.getAttribute('aria-label'),'有声图生视频');
   if(viewport.width>=1440){assert.equal(await panels.first().isVisible(),true);assert.equal(await panels.last().isVisible(),true);assert.equal(await page.locator('.ranking-task-tabs').isVisible(),false);for(const panel of await panels.all()){const table=panel.locator('.rank-table');if(await table.count()){assert.ok(await table.locator('tbody tr').count()<=10);const fit=await table.evaluate(el=>({width:el.scrollWidth,container:el.parentElement.clientWidth,bottom:el.getBoundingClientRect().bottom,height:innerHeight}));assert.ok(fit.width<=fit.container+2,'video rank horizontal overflow '+JSON.stringify(fit));assert.ok(fit.bottom<=fit.height,'video top ten below fold '+JSON.stringify(fit));}}}
   else{assert.equal(await panels.first().isVisible(),false);assert.equal(await panels.last().isVisible(),true);await page.locator('[data-rank-video-task="text-to-video-audio"]').click();assert.equal(await panels.first().isVisible(),true);assert.equal(await panels.last().isVisible(),false);}
   await page.screenshot({path:path.join(out,label+'-video-dual-rank.png')});
  });
  if(viewport.width===1440)await check('desktop folding navigation',async()=>{
   await page.goto(base+'?view=overview',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   const sidebar=page.locator('#sidebar'),toggle=sidebar.locator('#desktopNavToggle');
   assert.equal(await toggle.getAttribute('aria-expanded'),'true');const expanded=await sidebar.evaluate(el=>el.getBoundingClientRect().width);
   await toggle.click();assert.equal(await toggle.getAttribute('aria-expanded'),'false');await page.waitForFunction(()=>document.getElementById('sidebar').getBoundingClientRect().width<=66);assert.ok(await sidebar.evaluate(el=>el.getBoundingClientRect().width)<expanded);
   await page.screenshot({path:path.join(out,label+'-compact-nav.png')});
   await page.reload();await page.waitForFunction(()=>state.dataReady);assert.equal(await toggle.getAttribute('aria-expanded'),'false');await page.waitForFunction(()=>document.getElementById('sidebar').getBoundingClientRect().width<=66);
   await sidebar.locator('[data-view="models"]').click();await page.waitForFunction(()=>state.dataReady);assert.equal(await page.evaluate(()=>state.view),'models');
   await toggle.click();await page.waitForFunction(()=>document.getElementById('sidebar').getBoundingClientRect().width>=214);const group=sidebar.locator('[data-nav-group-toggle="resources"]');await group.click();assert.equal(await group.getAttribute('aria-expanded'),'false');assert.equal(await sidebar.locator('[data-view="practice"]').isVisible(),false);
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
  if(viewport.width!==360)await check('release controls',async()=>{
   await page.goto(base+'?view=today',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   await page.locator('[data-release-window]').selectOption('7');assert.equal(await page.evaluate(()=>state.releaseWindow),'7');
   await page.locator('[data-release-sort-select]').selectOption('date');assert.equal(await page.evaluate(()=>state.releaseSort),'date');
   await page.screenshot({path:path.join(out,label+'-release-controls.png')});
  });
  if(viewport.width!==360)await check('news category and details',async()=>{
   await page.goto(base+'?view=feeds',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   await page.locator('[data-briefing-category="模型"]').click();assert.equal(await page.evaluate(()=>state.briefingCategory),'模型');
   const details=page.locator('.combined-news-card details').first();await details.locator('summary').click();assert.equal(await details.evaluate(el=>el.open),true);
   await page.screenshot({path:path.join(out,label+'-news-detail.png')});
  });
  if(viewport.width!==360)await check('social views',async()=>{
   await page.goto(base+'?view=social',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);
   const brand=page.locator('.social-brand-record').first(),button=brand.locator('[data-social-detail]');assert.equal(await page.locator('.social-matrix th').count(),10);assert.equal(await page.locator('.social-brand-record').count(),12);assert.equal(await page.locator('.social-total').count(),12);if(viewport.width===1440){const fit=await page.locator('.social-matrix-footer').evaluate(el=>({bottom:el.getBoundingClientRect().bottom,height:innerHeight}));assert.ok(fit.bottom<=fit.height,'social matrix page and total must fit '+JSON.stringify(fit));}const firstTotal=await page.locator('.social-matrix-footer strong').textContent();await page.locator('[data-social-page="1"]').click();assert.equal(await page.locator('.social-matrix-footer strong').textContent(),firstTotal);await page.locator('[data-social-page="-1"]').click();await button.click();assert.equal(await button.getAttribute('aria-expanded'),'true');assert.equal(await page.locator('.social-matrix-detail').first().isVisible(),true);await page.screenshot({path:path.join(out,label+'-social-brand-expanded.png')});
   await page.locator('[data-social-view="platforms"]').click();assert.equal(await page.locator('section.social-platform-record').count(),8);assert.equal(await page.locator('details.social-platform-record').count(),0);for(const panel of await page.locator('.social-platform-record').all()){assert.ok(await panel.isVisible());assert.ok(await panel.locator('.social-platform-rank').count()<=5);}if(viewport.width>=1440){const fit=await page.locator('.social-platform-grid').evaluate(el=>({bottom:el.getBoundingClientRect().bottom,height:innerHeight,cols:getComputedStyle(el).gridTemplateColumns.split(' ').length}));assert.equal(fit.cols,4);assert.ok(fit.bottom<=fit.height,'all eight platform summaries must fit '+JSON.stringify(fit));}await page.screenshot({path:path.join(out,label+'-social-platform-overview.png')});await page.locator('[data-social-platform-open="X"]').click();assert.equal(await page.locator('.social-platform-record').count(),1);assert.equal(await page.locator('[data-social-platform-filter]').inputValue(),'platform:X');const evidence=page.locator('.social-platform-evidence-toggle').first();if(await evidence.count()){await evidence.click();assert.equal(await evidence.getAttribute('aria-expanded'),'true');assert.ok(await page.locator('.social-platform-evidence').first().isVisible());await evidence.click();}await page.screenshot({path:path.join(out,label+'-social-platform-single.png')});
   await page.locator('[data-social-view="posts"]').click();assert.equal(await page.evaluate(()=>state.socialView),'posts');await page.screenshot({path:path.join(out,label+'-social-posts.png')});
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
   await page.goto(base+'?view=platforms',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>state.dataReady);const fav=page.locator('[data-platform-favorite]').first(),favoriteId=await fav.getAttribute('data-platform-favorite');await fav.click();await page.reload();await page.waitForFunction(()=>state.dataReady);assert.equal(await page.locator('[data-platform-favorite="'+favoriteId+'"]').getAttribute('aria-pressed'),'true');
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
  await check('no runtime errors',async()=>assert.deepEqual(errors,[]));
 }
}finally{await browser.close()}
if(failures.length){console.error(failures.join('\n'));process.exitCode=1}
