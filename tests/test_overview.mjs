
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const html=fs.readFileSync(path.join(root,'site/index.html'),'utf8');
const script=html.split('<script>')[1].split('</script>')[0];
const boot=script.slice(0,script.indexOf('\nloadData().catch('));
// Render historical snapshots deterministically, not against the runner's wall clock.
const releaseSnapshot=JSON.parse(fs.readFileSync(path.join(root,'site/data/model-releases-30d.json'),'utf8'));
const snapshotTime=Date.parse(releaseSnapshot.windowEnd+'T23:59:59+08:00');
assert.ok(Number.isFinite(snapshotTime),'release snapshot requires a valid windowEnd');
function setup({query='',fail=[],defer,now=snapshotTime}={}){
 const fixedTime=typeof now==='number'?now:Date.parse(now);assert.ok(Number.isFinite(fixedTime));
 class SnapshotDate extends Date{constructor(...args){super(...(args.length?args:[fixedTime]))}static now(){return fixedTime}}
 const requested=[];
 const nodes=new Map();
 function node(id){
  if(!nodes.has(id))nodes.set(id,{id,innerHTML:'',textContent:'',value:'',classList:{toggle(){},remove(){}},addEventListener(){},insertAdjacentHTML(where,value){this.innerHTML=where==='afterbegin'?value+this.innerHTML:this.innerHTML+value},querySelectorAll(){return []},querySelector(){return null}});
  return nodes.get(id);
 }
 const location={search:query,protocol:'https:'};const entries=[];let cursor=-1;const history={state:null,replaceState(s,_,url){this.state=s;location.search=url.split('#')[0];if(cursor<0){entries.push({state:s,url});cursor=0}else entries[cursor]={state:s,url}},pushState(s,_,url){entries.splice(cursor+1);entries.push({state:s,url});cursor++;this.state=s;location.search=url},back(){if(cursor>0){cursor--;this.state=entries[cursor].state;location.search=entries[cursor].url;vm.runInContext('restoreNavigation(window.history.state)',ctx)}}};
 const ctx=vm.createContext({URL,URLSearchParams,Intl,Date:SnapshotDate,console,location,window:{location,history,scrollY:0,scrollTo(x,y){this.scrollY=y}},document:{querySelectorAll(){return []},getElementById:node,addEventListener(){}},localStorage:{getItem(){return null}},fetch:async url=>{
  const name=url.split('/').pop().split('?')[0];requested.push(name);
  if(defer)await defer(name);
  if(fail.includes(name))return {ok:false,status:503};
  return {ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,'site/data',name),'utf8'))};
 }});
 vm.runInContext(fs.readFileSync(path.join(root,'site/creator-intel.js'),'utf8'),ctx);
 vm.runInContext(boot,ctx);
 return {ctx,node,requested,run:s=>vm.runInContext(s==='loadAllForTests()'?'(async()=>{await loadData();await Promise.all(Object.keys(dataFiles).map(requestData));await ensureSearchData();render()})()':s,ctx)};
}
test('default overview and original ranking entry are preserved',()=>{
 assert.equal(setup().run('state.view'),'overview');
 assert.equal(setup({query:'?view=rankings'}).run('state.view'),'rankings');
 assert.equal(setup({query:'?view=unknown'}).run('state.view'),'overview');
 assert.equal(setup({query:'?view=evaluations'}).run('state.view'),'today');
 assert.equal((html.match(/<button[^>]*data-view="[^"]+"/g)||[]).filter(x=>!x.includes("'+")).length>=9,true);
});
test('calendar windows, issue dates, and undated discoveries are distinct',()=>{
 const {run}=setup();
 assert.equal(run("withinDays('2026-11-20',7,new Date('2026-11-26T06:00:00Z'))"),true);
 assert.equal(run("withinDays('2026-11-19',7,new Date('2026-11-26T06:00:00Z'))"),false);
 assert.equal(run("withinDays('2026-11-27',7,new Date('2026-11-26T06:00:00Z'))"),false);
 assert.equal(run("chinaDay('2026-11-25T17:00:00Z')"),'2026-11-26');
 assert.equal(run("briefIssueDay({title:'AI 日报（2026 年 11 月 25 日）',fetchedAt:'2026-11-26'})"),'2026-11-25');
 run("state.modelReleases=[{publishedAt:'2026-11-24'}];state.modelReleaseData={pending:[{publishedAt:null,discoveredAt:'2026-11-25'},{publishedAt:'2026-10-01',discoveredAt:'2026-11-26'}]};");
 assert.equal(run("overviewSummary(new Date('2026-11-26T06:00:00Z')).confirmed.length"),0);
 assert.equal(run("state.modelReleaseData.pending.filter(x=>!x.publishedAt&&withinDays(x.discoveredAt,7,new Date('2026-11-26T06:00:00Z'))).length"),1);
 assert.equal(run("Object.prototype.hasOwnProperty.call(overviewSummary(new Date('2026-11-26T06:00:00Z')),'pending')"),false);
});
test('briefing source links are explicit; adjacent headlines do not become originals',()=>{
 const {run}=setup();
 const out=run("JSON.stringify(briefArticleLinks({title:'A',links:[{label:'B',url:'https://example.com/b'},{label:'原文',url:'https://example.com/a'},{label:'A',url:'https://example.com/item'}]}))");
 assert.deepEqual(JSON.parse(out),[{url:'https://example.com/a',label:'原文'},{url:'https://example.com/item',label:'资讯条目'}]);
});
test('overview loads only five snapshots; other routes load on demand and reuse requests',async()=>{
 let release;const blocker=new Promise(r=>release=r);
 const {run,node,requested}=setup({defer:name=>name==='models.json'?blocker:Promise.resolve()});
 await run('loadData()');
 assert.equal(run('state.overviewReady'),true);assert.equal(run('state.dataReady'),true);
 assert.equal(requested.length,5);assert.ok(!requested.includes('models.json'));assert.ok(!requested.includes('unified-rankings.json'));
 assert.match(node('content').innerHTML,/今日概览/);
 run("setView('models')");assert.match(node('content').innerHTML,/正在加载模型库/);
 const done=run('ensureViewData()');release();await done;
 assert.equal(run('state.dataReady'),true);assert.equal(requested.filter(x=>x==='models.json').length,1);
 for(const view of ['overview','today','feeds','social','models','rankings','topics','practice','platforms','opportunities']){
  run("setView("+JSON.stringify(view)+")");await run('ensureViewData()');
  assert.ok(node('content').innerHTML.includes('<h1'),view);
 }
 assert.equal(requested.filter(x=>x==='models.json').length,1);
 run("state.briefingTab='selected';setView('feeds')");assert.match(node('content').innerHTML,/AIHOT 精选/);
});
test('failed source does not block other modules and missing data is explicit',async()=>{
 const {run,node}=setup({fail:['model-releases-30d.json','models.json']});await run('loadAllForTests()');
 assert.equal(run('state.dataReady'),true);assert.match(node('content').innerHTML,/部分概览数据未加载/);
 assert.match(node('content').innerHTML,/发布数据暂不可用/);
 run("setView('models')");assert.match(node('content').innerHTML,/部分数据未加载/);
 run("setView('feeds')");assert.match(node('content').innerHTML,/行业简报/);
});

test('overview and old pending routes stay on verified release projection',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');
 assert.doesNotMatch(node('content').innerHTML,/data-release-mode-target="pending"/);
 run("state.modelReleaseData.pending.push({title:'Unverified injected model',id:'candidate',category:'video',publishedAt:new Date().toISOString()});state.releaseMode='pending';setView('today')");
 assert.match(node('content').innerHTML,/aria-pressed="true" data-release-mode="confirmed"/);
 assert.doesNotMatch(node('content').innerHTML,/Unverified injected model|data-release-mode="pending"/);
 run('buildGlobalIndex()');assert.equal(run("globalIndex.some(x=>x.type==='release'&&x.title==='Unverified injected model')"),false);
 assert.ok(run("state.modelReleaseData.pending.some(x=>x.id==='candidate')"));
 const old=setup({query:'?view=today&status=pending'});await old.run('loadData()');assert.equal(old.run('state.releaseMode'),'confirmed');
});

test('global index finds exact versions and cross-module records',async()=>{
 const {run}=setup();await run('loadAllForTests()');
 const result=JSON.parse(run("JSON.stringify(searchGlobal('Seedance 2.0','model').slice(0,1))"));
 assert.equal(result[0].action.family,'seedance');assert.equal(result[0].action.version,'seedance-2-0');
 assert.ok(run("searchGlobal('CPP','program').length")>0);
 assert.ok(run("searchGlobal('Seedance','resource').length")>0);
 assert.ok(run("searchGlobal('Veo','topic').length")>0);
 assert.ok(run("searchGlobal('视频','ranking').length")>0);
 assert.equal(run("searchGlobal('not-a-real-model-00000000','all').length"),0);
});
test('version deep link and browser back restore originating filters',async()=>{
 const {run,node}=setup({query:'?view=models&category=image&region=%E6%B5%B7%E5%A4%96&q=Nano'});
 await run('loadAllForTests()');assert.equal(run('state.modelCategory'),'image');assert.equal(run('state.regionFilter'),'海外');assert.equal(run('state.query'),'Nano');
 run("window.scrollY=250;openModelDetails('seedance','seedance-2-0')");
 assert.match(run('window.location.search'),/model=seedance&version=seedance-2-0/);
 assert.match(node('content').innerHTML,/model-detail-version-selected" data-version-id="seedance-2-0"/);
 run('closeModelDetails()');assert.equal(run('state.selectedModelId'),null);assert.equal(run('state.modelCategory'),'image');assert.equal(run('state.query'),'Nano');assert.equal(run('window.scrollY'),250);
});
test('direct version links survive reload, unknown version degrades to family',async()=>{
 const a=setup({query:'?view=models&model=seedance&version=seedance-2-0'});await a.run('loadAllForTests()');assert.equal(a.run('state.selectedVersionId'),'seedance-2-0');
 const b=setup({query:'?view=models&model=seedance&version=unknown'});await b.run('loadAllForTests()');assert.equal(b.run('state.selectedVersionId'),null);assert.match(b.node('content').innerHTML,/具体型号不存在/);b.run('render()');assert.match(b.node('content').innerHTML,/具体型号不存在/);b.run("setView('overview')");assert.doesNotMatch(b.node('content').innerHTML,/具体型号不存在/);
});
test('page filters and deep links survive browser back',async()=>{
 const {run}=setup();await run('loadAllForTests()');run("setView('today',{releaseMode:'announcements'});state.releaseCategory='video';state.query='Seed';render();window.scrollY=380;setView('feeds',{briefingTab:'selected'});window.history.back()");
 assert.equal(run('state.view'),'today');assert.equal(run('state.releaseMode'),'announcements');assert.equal(run('state.releaseCategory'),'video');assert.equal(run('state.query'),'Seed');assert.equal(run('window.scrollY'),380);
});

test('rankings search indexes visible source rows and keeps task identity',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');
 const candidate=JSON.parse(run("JSON.stringify(globalIndex.find(function(x){return x.type==='ranking'&&x.action.options&&x.action.options.rankVideoTask}))"));
 assert.ok(candidate);assert.match(candidate.meta,/原榜 #/);
 run("setView('rankings',"+JSON.stringify(candidate.action.options)+")");
 assert.equal(run('state.rankVideoTask'),candidate.action.options.rankVideoTask);
 assert.equal(run('state.query'),candidate.title);
 assert.match(node('content').innerHTML,/原榜 #/);
});

test('grouped release list, recent known date and readable briefing preserve source links',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('today')");
 const hasReleases=run("(state.modelReleases||[]).some(x=>releaseCategoryOrder(x.category)<99&&withinDays(x.publishedAt,30,new Date()))");
 if(hasReleases){assert.match(node('content').innerHTML,/class="release-main"/);assert.match(node('content').innerHTML,/class="release-actions"/);assert.match(node('content').innerHTML,/data-model-version=/)}
 else{assert.doesNotMatch(node('content').innerHTML,/class="release-main"/);assert.match(node('content').innerHTML,/最近 30 天没有符合当前筛选的已核实发布事件/)}
 run("setView('models')");assert.match(node('content').innerHTML,/最近发布日期/);assert.match(node('content').innerHTML,/table-scroll-hint/);
 run("setView('feeds')");assert.doesNotMatch(node('content').innerHTML,/class="briefing-intro"/);assert.match(node('content').innerHTML,/briefing-original-links/);
});

test('creator opportunities distinguish date precision and program registration',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('opportunities')");
 assert.match(node('content').innerHTML,/AI 创作比赛/);assert.match(node('content').innerHTML,/Runway AI Festival 2027/);assert.doesNotMatch(node('content').innerHTML,/Higgsfield Talent Contest/);
 assert.equal(run("contestStatus({deadlineDate:'2026-11-26',deadlineAt:'2026-11-26T19:00:00Z'},new Date('2026-11-26T18:59:00Z')).key"),'window');
 assert.equal(run("contestStatus({deadlineDate:'2026-11-26',deadlineAt:'2026-11-26T19:00:00Z'},new Date('2026-11-26T19:00:00Z')).key"),'closed');
 assert.equal(run("contestStatus({deadlineDate:'2026-11-26'},new Date('2026-11-26T10:00:00Z')).key"),'unknown');
 run("state.opportunityTab='programs';render()");assert.match(node('content').innerHTML,/开放状态待确认/);assert.ok(run('creatorPrograms().length')>20);assert.equal(run("searchGlobal('Higgsfield Talent Contest','contest').length"),0);assert.ok(run("searchGlobal('Runway AI Festival','contest').length")>0);
});
test('prompt and selection views preserve source and avoid invented scores',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('practice',{practiceCategory:'视频',modelPracticeType:'prompt'})");assert.match(node('content').innerHTML,/data-copy-template="product-tvc"/);assert.match(node('content').innerHTML,/官方提示词指南/);assert.match(node('content').innerHTML,/提示词节选/);
 run("state.modelPracticeType='select';render()");assert.match(node('content').innerHTML,/对照能力原榜/);assert.match(node('content').innerHTML,/不生成主观评分/);
});

test('existing community repositories are reachable in prompt views and global search',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('practice',{practiceCategory:'视频',modelPracticeType:'prompt'})");
 assert.match(node('content').innerHTML,/开源提示词与 Skill 索引/);assert.match(node('content').innerHTML,/LearnPrompt\/awesome-seedance/);
 assert.ok(run("searchGlobal('Awesome Seedance','resource').length")>0);
 assert.equal(run("stableCreatorKey('https://example.com/apply')===stableCreatorKey('https://example.com/apply')"),true);
 run("setView('opportunities',{opportunityTab:'programs'})");assert.match(node('content').innerHTML,/creator-link-health/);
});

test('direct ranking route does not fetch model registry or legacy data; global search loads only active search sources',async()=>{
 const {run,requested}=setup({query:'?view=rankings'});await run('loadData()');
 assert.deepEqual(requested,['unified-rankings.json']);
 await run('ensureSearchData()');assert.equal(run('state.indexReady'),true);
 assert.ok(requested.includes('models.json'));assert.ok(!requested.includes('maomu-rankings.json'));assert.ok(!requested.includes('reference-rankings.json'));
 assert.ok(!requested.includes('model-evaluations.json'));assert.ok(!requested.includes('model-updates.json'));
 assert.equal(requested.filter(x=>x==='unified-rankings.json').length,1);
});
test('model details from recent releases lazily load board evidence',async()=>{
 const {run,node,requested}=setup({query:'?view=today'});await run('loadData()');assert.ok(!requested.includes('models.json'));
 run("openModelDetails('seedance','seedance-2-0')");await run('ensureViewData()');
 assert.match(node('content').innerHTML,/model-detail-version-selected" data-version-id="seedance-2-0"/);
 assert.ok(requested.includes('reference-rankings.json'));assert.ok(requested.includes('maomu-rankings.json'));
});

test('canonical history preserves audited combined events and audio subclasses',async()=>{
 const {run,node}=setup({query:'?view=topics&topic=google'});await run('loadData()');
 assert.equal(run('isLocalAihot()'),false);
 assert.equal(run("topicEventCategoryMatches({modelCategory:'music'},'audio',{})"),true);
 assert.equal(run("topicEventCategoryMatches({modelCategory:['tts']},'audio',{})"),true);
 run("state.topics=[{id:'google',group:'公司与模型',name:'Google',milestones:[{auditId:'joint',date:'2026-01-01',title:'Veo 3 and Imagen 4 combined',url:'https://example.com/verified',kind:'模型',verificationStatus:'已确认：型号、日期与事件性质',modelCategory:['image','video']},{date:'2026-01-02',title:'Candidate',kind:'模型发布',autoCollected:true}]}];render()");
 assert.match(node('content').innerHTML,/Veo 3 and Imagen 4 combined/);
 assert.doesNotMatch(node('content').innerHTML,/Candidate|来源日期非首发确认/);
 run("state.topicCategory='image';state.query='combined';render()");
 assert.match(node('content').innerHTML,/Veo 3 and Imagen 4 combined/);
 assert.doesNotMatch(node('content').innerHTML,/<h3[^>]*>.*Candidate/);
});
test('active frontend no longer ships unreachable ranking or evaluation renderers',()=>{
 for(const name of ['legacyRankingsPage','aihotLeaderboardPage','evaluationTargets','modelCard','expandTopicMilestones'])assert.ok(!html.includes('function '+name+'('),name);
});


test('creator program evidence ages independently of links and scan candidates stay separate',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');
 assert.equal(run("programReview({applicationReview:{status:'open',checkedAt:'2026-11-26'}},new Date('2026-11-27T00:00:00Z')).label"),'官方说明开放');
 assert.equal(run("programReview({applicationReview:{status:'open',checkedAt:'2026-11-26'}},new Date('2026-12-12T00:00:00Z')).key"),'unknown');
 assert.equal(run("programReview({applicationReview:{status:'application-listed',checkedAt:'2026-11-26'}},new Date('2026-11-27T00:00:00Z')).key"),'unknown');
 run("state.opportunityDiscovery={checkedAt:'2026-11-26T00:00:00Z',sources:[],programSignals:[{platformId:'demo',scope:'global',sourceUrl:'https://example.com',status:'reachable',signal:'closure-signal'}],candidates:[{title:'Pending Example Festival',url:'https://example.com/contest',sourceName:'Demo',provenance:'directory'}]};setView('opportunities')");
 assert.equal(run("programReview({platformId:'demo',scope:'global',applicationReview:{status:'open',checkedAt:'2026-11-26',sourceUrl:'https://example.com'}},new Date('2026-11-27T00:00:00Z')).key"),'unknown');
 assert.doesNotMatch(node('content').innerHTML,/Pending Example Festival/);assert.ok(run("state.opportunityDiscovery.candidates.some(x=>x.title==='Pending Example Festival')"));
 assert.equal(run("state.opportunityData.items.some(x=>x.title==='Pending Example Festival')"),false);
});


test('board row indexing preserves first-match rank semantics and snapshot isolation',()=>{
 const {run}=setup();
 assert.equal(run("(()=>{const rows=[{name:'A',rank:7},{name:'A',rank:2}];return firstBoardRow(rows,'A').rank})()"),7);
 assert.equal(run("(()=>{const rows=[{name:'A',rank:7}];firstBoardRow(rows,'A');return firstBoardRow([{name:'A',rank:2}],'A').rank})()"),2);
 assert.equal(run("firstBoardRow([], 'missing')"),undefined);
});

 test('rank evidence resolves current snapshot rather than stale aliases',()=>{
 const {run}=setup();
 const result=run("JSON.stringify(modelRanksFor({leaderboardAliases:[{source:'reference',boardId:'demo',name:'A',rank:99},{source:'reference',boardId:'demo',name:'B',rank:1}]},[{source:'reference',boardId:'demo',rows:[{name:'A',rank:7},{name:'A',rank:2},{name:'B',rank:0}]}]).map(x=>x.alias.rank))");
 assert.deepEqual(JSON.parse(result),[7]);
});

 test('release event grouping preserves versions, dates and exact evidence',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');
 const fixtures=[{id:'a',modelFamilyId:'tencent-hy-mt',modelName:'Hy-MT3-1.8B',publishedAt:'2026-11-24',category:'llm',vendor:'腾讯混元',url:'https://huggingface.co/tencent/Hy-MT3-1.8B'},{id:'b',modelFamilyId:'tencent-hy-mt',modelName:'Hy-MT3-7B',publishedAt:'2026-11-24',category:'llm',vendor:'腾讯混元',url:'https://huggingface.co/tencent/Hy-MT3-7B'},{id:'c',modelFamilyId:'tencent-hy-mt',modelName:'Hy-MT3-30B-A3B',publishedAt:'2026-11-24',category:'llm',vendor:'腾讯混元',url:'https://huggingface.co/tencent/Hy-MT3-30B-A3B'},{id:'d',modelFamilyId:'gpt',modelName:'GPT-6.2 Astra',publishedAt:'2026-11-17',category:'llm',vendor:'OpenAI'},{id:'e',modelFamilyId:'gpt',modelName:'GPT-6.2 (November 23)',publishedAt:'2026-11-23',category:'llm',vendor:'OpenAI'},{id:'f',modelFamilyId:'ovhcloud-olala',modelName:'Other',publishedAt:'2026-11-25',category:'llm',vendor:'OVHcloud'}];
 const events=JSON.parse(run("JSON.stringify(releaseEvents("+JSON.stringify(fixtures)+",'priority'))"));
 assert.equal(events.length,4);assert.equal(events.reduce((n,e)=>n+e.versions.length,0),fixtures.length);
 const mt=events.find(e=>e.modelName==='Hy-MT3 系列');assert.equal(mt.versions.length,3);assert.equal(new Set(mt.versions.map(v=>v.url)).size,3);
 assert.ok(events.filter(e=>e.category==='llm').findIndex(e=>e.vendor==='OpenAI')<events.filter(e=>e.category==='llm').findIndex(e=>e.vendor==='OVHcloud'));
 assert.equal(events.filter(e=>e.modelFamilyId==='gpt').length,2);
 run("setView('today',{releaseCategory:'llm'})");assert.match(node('content').innerHTML,/创作优先/);
 assert.equal(run("releaseEvents([{id:'a',modelFamilyId:'gpt',modelName:'A',publishedAt:'2026-11-25',evidenceType:'official-model-card',url:'https://example.com/card'},{id:'b',modelFamilyId:'gpt',modelName:'B',publishedAt:'2026-11-25',evidenceType:'official-model-card',url:'https://example.com/card'}]).length"),2);
 const chronological=JSON.parse(run("JSON.stringify(releaseEvents(state.modelReleases,'date').map(e=>e.publishedAt))"));assert.deepEqual(chronological,[...chronological].sort().reverse());
});

test('combined news merges only primary identities and preserves every report',()=>{
 const {run}=setup();
 run("state.aihotDaily={title:'AI 日报（2026 年 11 月 25 日）',items:[{title:'Claude Install as app 桌面应用',category:'头条',links:[{label:'原文',url:'https://claude.com/blog/install-as-app'},{label:'邻近新闻',url:'https://example.com/other'}]}]};state.juyaDaily={title:'AI 早报 2026-11-25',items:[{title:'Anthropic artifacts 桌面应用',category:'要闻',url:'https://claude.com/resources/articles/install-as-app'},{title:'一条完全独立的邻近新闻',url:'https://example.com/other'}]};state.aihot={items:[{title:'Claude 安装桌面应用',selected:true,category:'ai-products',publishedAt:'2026-11-24T00:00:00Z',links:{original:'https://claude.com/blog/install-as-app?utm_source=test'}}]};");
 const events=JSON.parse(run('JSON.stringify(combinedNews())'));assert.equal(events.length,2);assert.equal(events.reduce((n,e)=>n+e.rows.length,0),4);
 const merged=events.find(e=>e.rows.length===3);assert.equal(merged.sources.length,3);assert.equal(merged.rows.find(r=>r.source==='AIHOT 精选').day,'2026-11-24');
 assert.notEqual(run("newsUrlKey('https://example.com/notes#v1')"),run("newsUrlKey('https://example.com/notes#v2')"));
});
test('overview exposes all modules without duplicating raw daily feeds',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');const markup=node('content').innerHTML;
 assert.match(markup,/今日行业简报/);assert.doesNotMatch(markup,/快捷入口|overview-module-grid|overview-stage-count/);assert.doesNotMatch(markup,/完整日报与精选/);assert.doesNotMatch(markup,/<h2>官方发现 · 待复核<\/h2>/);
 assert.match(markup,/data-briefing-target="combined"/);assert.doesNotMatch(markup,/data-briefing-target="(?:aihot|juya|selected)"/);for(const view of ['today','feeds'])assert.ok(markup.includes('data-view="'+view+'"'),view);
 run("setView('feeds',{briefingTab:'combined'})");assert.match(node('content').innerHTML,/综合资讯/);assert.match(node('content').innerHTML,/条原始报道/);
});

test('release range and order persist in route',async()=>{
 const {run,node}=setup({query:'?view=today&days=7&sort=date'});await run('loadAllForTests()');assert.equal(run('state.releaseWindow'),'7');assert.equal(run('state.releaseSort'),'date');assert.match(node('content').innerHTML,/data-release-window/);
});

test('briefing category and practice links keep full resources accessible',async()=>{
 const {run,node}=setup({now:'2026-11-27T02:00:00Z'});await run('loadAllForTests()');
 // New day with only a non-model selected article must show a legitimate empty filter.
 run("state.aihotDaily={title:'AI 日报 2026-11-26',items:[]};state.juyaDaily={title:'AI 早报 2026-11-26',items:[]};state.aihot={items:[{title:'观点示例',selected:true,category:'opinion',publishedAt:'2026-11-27T00:00:00Z'}]};setView('feeds',{briefingTab:'combined',briefingCategory:'模型'})");
 assert.match(node('content').innerHTML,/aria-pressed="true" data-briefing-category="模型"/);
 assert.match(node('content').innerHTML,/当前筛选下暂无综合资讯/);
 // Explicit same-day model fixture verifies the expandable summary and source link.
 run("state.aihot.items.push({title:'模型发布示例',summary:'确定的摘要',selected:true,category:'ai-models',publishedAt:'2026-11-27T01:00:00Z',links:{original:'https://example.com/model'}});render()");
 assert.match(node('content').innerHTML,/完整摘要与来源/);assert.match(node('content').innerHTML,/https:\/\/example\.com\/model/);
 run("setView('practice',{modelPracticeType:'model'})");assert.doesNotMatch(node('content').innerHTML,/模型库详情 ↗/);assert.match(node('content').innerHTML,/模型库详情 →/);
});

test('social views separate actual verified homepages, search entries and posts',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('social')");assert.match(node('content').innerHTML,/social-matrix/);assert.match(node('content').innerHTML,/social-brand-record/);assert.match(node('content').innerHTML,/粉丝合计/);assert.match(node('content').innerHTML,/已核验主页/);assert.equal(run("socialAccountState({status:'verified-search'})"),'暂无已核实主页');assert.doesNotMatch(node('content').innerHTML,/候选主页|待核验/);
 run("setView('social',{socialView:'platforms',socialRegion:'platform:X'})");assert.match(node('content').innerHTML,/social-brand-record/);assert.doesNotMatch(node('content').innerHTML,/social-platform-record/);
 run("setView('social',{socialView:'posts',socialRegion:'all'})");assert.equal(run('state.socialView'),'brands');assert.match(node('content').innerHTML,/social-brand-record/);assert.doesNotMatch(node('content').innerHTML,/data-social-view="posts"|未去重/);assert.match(node('content').innerHTML,/不同平台可能有重复用户/);assert.equal(setup({query:'?view=social&tab=posts'}).run('state.socialView'),'brands');
});

test('reported internal-model concern is industry news, not a release',()=>{
 const {run}=setup();assert.equal(run("newsCategory({category:'要闻',title:'报道称 OpenAI 和 Anthropic 员工忧内部模型难以安全发布'})"),'行业');
});

test('library prioritization, history year and review filters retain records',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');assert.equal(run('state.modelSort'),'recent');assert.equal(run("latestDatedVersion({versions:[{name:'unknown'},{name:'old',releaseDate:'2025-01-01'},{name:'new',releaseDate:'2026-01-01'}]}).name"),'new');
 run("state.topics=[{id:'google',group:'公司与模型',name:'Google',milestones:[{date:'2025-01-01',title:'Old checked',url:'https://example.com/old',verificationStatus:'已确认'},{date:'2026-01-01',title:'New checked',url:'https://example.com/new',verificationStatus:'已确认'},{date:'2026-01-02',title:'Pending discovery',autoCollected:true}]}];setView('topics',{activeTopic:'google',topicYear:'2026',topicReview:'verified'})");assert.match(node('content').innerHTML,/New checked/);assert.doesNotMatch(node('content').innerHTML,/Old checked|Pending discovery/);
 run("state.topicReview='all';render()");assert.doesNotMatch(node('content').innerHTML,/Pending discovery/);
 run("state.topicYear='all';render()");assert.match(node('content').innerHTML,/Old checked/);assert.match(node('content').innerHTML,/New checked/);assert.doesNotMatch(node('content').innerHTML,/Pending discovery/);
});

test('resource summaries and favorites do not change source data',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('platforms')");assert.match(node('content').innerHTML,/data-platform-favorite/);assert.deepEqual(JSON.parse(run('JSON.stringify(platformFavorites())')),[]);
 run("setView('opportunities')");assert.match(node('content').innerHTML,/近7天按公告截止/);assert.match(node('content').innerHTML,/已核验开放计划/);
});

test('verified service stages remain outside release event counts',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');assert.ok(run('Array.isArray(state.modelReleaseData.verifiedStages)'));assert.ok(run("state.modelReleaseData.verifiedStages.every(x=>!state.modelReleases.some(y=>y.id===x.id))"));
 run("setView('today',{releaseCategory:'music'})");assert.match(node('content').innerHTML,/已核实模型上线阶段|当前时间范围没有已核实/);
});

test('Scribe variants form one reviewed batch with two preserved versions',()=>{
 const {run}=setup();const fixtures=['Scribe v3','Scribe v3 Live'].map((modelName,i)=>({id:'asr-'+i,modelFamilyId:'eleven-scribe',modelVersionId:'asr-'+i,modelName,category:'audio',vendor:'ElevenLabs',publishedAt:'2026-11-09'}));const events=JSON.parse(run('JSON.stringify(releaseEvents('+JSON.stringify(fixtures)+'))'));assert.equal(events.length,1);assert.equal(events[0].versions.length,2);assert.equal(events[0].modelName,'Scribe v3 系列');
});

test('single platform filter and sorting remain in brand matrix',async()=>{const {run,node}=setup();await run('loadAllForTests()');run("setView('social',{socialRegion:'platform:X'})");assert.match(node('content').innerHTML,/social-matrix/);assert.doesNotMatch(node('content').innerHTML,/data-social-view="platforms"|social-platform-record/);assert.match(node('content').innerHTML,/data-platform="X"/);assert.doesNotMatch(node('content').innerHTML,/data-platform="抖音"/);run("state.socialSort='X';render()");assert.match(node('content').innerHTML,/X 粉丝/);run("setView('opportunities')");assert.match(node('content').innerHTML,/opportunity-summary summary-grid/);});

 test('follower sums exclude unknown and unverified counts, deduplicate identical accounts and preserve zero',async()=>{const {run}=setup();assert.equal(run("socialFollowerTotal([{status:'verified',platform:'X',url:'https://x.com/a',followers:100},{status:'verified',platform:'X',url:'https://x.com/a',followers:100},{status:'review',platform:'X',url:'https://x.com/b',followers:500},{status:'verified',platform:'YouTube',url:'https://youtube.com/@a',followers:0},{status:'verified',platform:'Instagram',followers:null}]).total"),100);assert.equal(run("socialFollowerTotal([{status:'verified',platform:'X',url:'https://x.com/a',followers:0}]).count"),1);assert.equal(run("socialFollowerFormat(236000)"),'23.6万');});

test('overview explicitly identifies delayed snapshots without treating them as current',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');
 run("state.modelMonitorStatus={checkedAt:'2000-01-01T00:00:00Z'};state.aihot.updatedAt='2000-01-01T00:00:00Z';state.aihot.checkedAt='';state.aihotDaily.fetchedAt='2000-01-01T00:00:00Z';state.juyaDaily.fetchedAt='2000-01-01T00:00:00Z';state.aihotDaily.title='2000-01-01';state.juyaDaily.title='2000-01-01';setView('overview');render()");
 assert.match(node('content').innerHTML,/同步延迟 · [^<]*模型信源[^<]*AIHOT 精选[^<]*AIHOT 日报[^<]*橘鸦早报/);
 run("var freshStamp=new Date().toISOString();state.modelMonitorStatus.checkedAt=freshStamp;state.modelReleaseData.updatedAt=freshStamp;state.aihot.updatedAt=freshStamp;state.aihotDaily.fetchedAt=freshStamp;state.juyaDaily.fetchedAt=freshStamp;state.aihotDaily.title=chinaDay(new Date());state.juyaDaily.title=chinaDay(new Date());render()");
 assert.doesNotMatch(node('content').innerHTML,/同步延迟 · /);
});

test('creator link reachability is independent of live snapshot state',()=>{
 const {run}=setup();
 const url='https://example.com/apply';
 run("state.creatorLinkStatus={results:[]}");
 assert.match(run("creatorReachability('"+url+"')"),/未检测/);
 for(const [status,label] of [['available','链接响应正常'],['restricted','访问受限'],['missing','链接可能失效'],['server-error','服务器异常'],['unknown','无法确认'],['unexpected','未确认']]){
   run("state.creatorLinkStatus="+JSON.stringify({checkedAt:'2026-11-26T12:00:00Z',results:[{url,status}]}));
   const markup=run("creatorReachability('"+url+"#form')");
   assert.ok(markup.includes(label),status+' => '+markup);
   assert.ok(markup.includes('2026-11-26'));
 }
});
test('program page renders both pre-collection and post-collection link snapshots',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');
 run("setView('opportunities',{opportunityTab:'programs'});state.creatorLinkStatus={results:[]};render()");
 assert.match(node('content').innerHTML,/未检测/);
 run("state.creatorLinkStatus={checkedAt:'2026-11-26T12:00:00Z',results:creatorPrograms().map(p=>({url:p.url.split('#')[0],status:'available'}))};render()");
 assert.match(node('content').innerHTML,/链接响应正常/);
 assert.doesNotMatch(node('content').innerHTML,/class="creator-link-health">未检测/);
});

test('official announcement route renders verified stages without raw discovery',async()=>{
 const {run,node,requested}=setup({query:'?view=today&status=announcements'});await run('loadData()');
 assert.ok(!requested.includes('model-updates.json'));assert.match(node('content').innerHTML,/已核实公告/);
 run("state.modelReleaseData.pending.push({official:true,title:'Raw official candidate',vendor:'Example',category:'video',url:'https://example.com/news',publishedAt:new Date().toISOString().slice(0,10)});state.modelReleaseData.verifiedStages.push({id:'test-stage',stage:'api-availability',stageDate:new Date().toISOString().slice(0,10),modelName:'Verified service stage',vendor:'Example',category:'video',url:'https://example.com/stage',verifiedAt:new Date().toISOString().slice(0,10)});render()");
 assert.match(node('content').innerHTML,/Verified service stage/);assert.doesNotMatch(node('content').innerHTML,/Raw official candidate|class="release-company"/);
});

test('ranked MAGI-2 has the same model family and version IDs as its release',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('rankings',{rankTab:'video'})");
 const exists=run("(state.unifiedRankings.categories.find(c=>c.id==='video').primaryLeaderboards['image-to-video-audio'].rows||[]).some(r=>r.name==='MAGI-2')");
 if(exists)assert.match(node('content').innerHTML,/data-model-open="magi-2" data-model-version="magi-2"/);
 assert.equal(run("state.models.find(m=>m.id==='magi-2').versions.find(v=>v.id==='magi-2').releaseEvidence.chronicleTopicId"),'sandai');
});

test('daily edition freshness is based on Beijing publication window, not four-hour age',()=>{const {run}=setup();assert.equal(run("briefIssueStale({title:'2026-11-26',fetchedAt:'2026-11-26T00:10:00Z'},8,new Date('2026-11-26T12:00:00Z'))"),false);assert.equal(run("briefIssueStale({title:'2026-11-26',fetchedAt:'2026-11-27T00:04:00Z'},8,new Date('2026-11-27T00:06:00Z'))"),true);assert.equal(run("briefIssueStale({title:'2026-11-26',fetchedAt:'2026-11-26T02:10:00Z'},10,new Date('2026-11-27T01:00:00Z'))"),false);});

test('V3.4 grouped model library preserves flat view and family links',async()=>{
 const {run,node}=setup({query:'?view=models&category=video'});await run('loadAllForTests()');run("setView('models',{modelCategory:'video',modelGrouping:'vendor'})");
 assert.match(node('content').innerHTML,/model-table-grouped/);assert.match(node('content').innerHTML,/data-model-group=/);assert.match(node('content').innerHTML,/data-model-open="magi-2"/);
 run("state.modelGrouping='flat';render()");assert.doesNotMatch(node('content').innerHTML,/model-table-grouped|data-model-group=/);assert.match(node('content').innerHTML,/data-model-open="magi-2"/);
});
test('V3.4 chronology keeps evidence in default collapsed disclosure',async()=>{
 const {run,node}=setup({query:'?view=topics&topic=openai'});await run('loadAllForTests()');run("setView('topics',{activeTopic:'openai'})");
 assert.match(node('content').innerHTML,/<details class="topic-event-disclosure"><summary/);assert.doesNotMatch(node('content').innerHTML,/<details class="topic-event-disclosure" open/);assert.match(node('content').innerHTML,/原始公告/);assert.match(node('content').innerHTML,/data-topic-events="expand"/);
});
test('history publication gate retains audited and proof-backed nodes, rejects unverified stages',()=>{
 const {run}=setup();const base={date:'2026-11-17',title:'Model A 发布',kind:'模型',url:'https://example.com/a'};
 const rows=[{...base,verificationStatus:'已确认'},{...base,title:'Introducing Model A',autoCollected:true},{...base,title:'Model A Preview',externalUnreviewed:true,verificationStatus:'已确认'},{...base,title:'Machine verified',autoCollected:true,verificationMethod:'automatic-dual-official',automaticReleaseEventId:'r1',corroboratingSources:[{url:'https://a.example/a'},{url:'https://b.example/a'}]},{...base,title:'Incomplete proof',autoCollected:true,verificationMethod:'automatic-dual-official',automaticReleaseEventId:'r2',corroboratingSources:[]}];
 const result=JSON.parse(run('JSON.stringify('+JSON.stringify(rows)+'.filter(publishedChronicleNode))'));assert.deepEqual(result.map(x=>x.title),['Model A 发布','Machine verified']);
 assert.equal(run('topicMilestoneCounts({milestones:'+JSON.stringify(rows)+'}).verified'),2);
});

test('V3.4 shared semantic icons and readable provider labels',()=>{
 const {run}=setup();assert.equal(run("rankProviderLabel('openai')"),'OpenAI');assert.equal(run("rankProviderLabel('unknown-provider')"),'unknown-provider');assert.match(run("icon('panel')"),/M9 3v18/);assert.match(run("icon('external')"),/stroke-width="1.75"/);
});
test('V3.4 each vendor has its own semantic table row group',async()=>{
 const {run,node}=setup({query:'?view=models&category=video'});await run('loadAllForTests()');run("setView('models',{modelCategory:'video',modelGrouping:'vendor'})");const markup=node('content').innerHTML;assert.ok((markup.match(/<tbody class="model-vendor-group">/g)||[]).length>1);assert.equal((markup.match(/<tbody class="model-vendor-group">/g)||[]).length,(markup.match(/scope="rowgroup"/g)||[]).length);
});

test('latest briefing date is shared across sources and fixed before search or categories',()=>{
 const {run}=setup({now:'2026-11-26T14:00:00+08:00'});run("state.aihotDaily={title:'AI 日报 2026-11-25',items:[{title:'昨日旧报道',category:'行业',url:'https://example.com/old'}]};state.juyaDaily={title:'AI 早报 2026-11-26',items:[{title:'今日新报道',category:'行业',url:'https://example.com/new'}]};state.aihot={items:[{selected:true,title:'旧精选',publishedAt:'2026-11-25T00:00:00Z'},{selected:true,title:'新精选',publishedAt:'2026-11-26T00:00:00Z'},{selected:true,title:'未注明日期精选'},{selected:false,title:'未选资讯',publishedAt:'2026-11-26T00:00:00Z'}]};");
 assert.equal(run('latestBriefingDay()'),'2026-11-26');const events=JSON.parse(run('JSON.stringify(combinedNews(latestBriefingDay()))'));assert.equal(events.length,2);assert.ok(events.every(e=>e.day==='2026-11-26'&&e.rows.every(r=>r.day==='2026-11-26')));assert.equal(run('latestDigest(state.aihotDaily,latestBriefingDay()).items.length'),0);assert.equal(run('latestSelectedNews(latestBriefingDay()).length'),1);run("state.query='昨日旧报道'");assert.equal(run('latestBriefingDay()'),'2026-11-26');assert.equal(run('combinedNews(latestBriefingDay()).filter(newsMatches).length'),0);
});

test('V3.5 separates formal releases from service stages',async()=>{const {run,node}=setup();await run('loadAllForTests()');assert.doesNotMatch(node('content').innerHTML,/overview-stage-count|overview-count-track/);run("setView('today',{releaseMode:'confirmed',releaseCategory:'all'})");assert.doesNotMatch(node('content').innerHTML,/\+\s*\d+\s*上线|已核实模型上线阶段|data-release-mode="all"/);run("setView('today',{releaseMode:'announcements',releaseCategory:'all'})");assert.match(node('content').innerHTML,/官方公告/);if(run("(state.modelReleaseData.verifiedStages||[]).some(x=>withinDays(x.stageDate,30,new Date()))"))assert.match(node('content').innerHTML,/已核实模型上线阶段/);});

test('V3.5 model library defaults to strict latest dated family order and unknowns last',async()=>{
 const {run,node}=setup({query:'?view=models&category=video'});await run('loadAllForTests()');
 assert.equal(run('state.modelSort'),'recent');assert.equal(run('state.modelGrouping'),'flat');
 const ids=Array.from(node('content').innerHTML.matchAll(/class="model-row-open" data-model-open="([^"]+)"/g),m=>m[1]);
 const dates=JSON.parse(run('JSON.stringify('+JSON.stringify(ids)+'.map(id=>{const v=latestDatedVersion(libraryModels().find(m=>m.id===id));return v?v.releaseDate:""}))'));
 assert.ok(dates.length>1);assert.deepEqual(dates,dates.slice().sort().reverse());
});
test('V3.5 identical news summaries are displayed only once while distinct text remains',()=>{
 const {run}=setup();assert.deepEqual(JSON.parse(run('JSON.stringify((()=>{const seen=new Set();return [uniqueNewsSummary("A  summary",seen),uniqueNewsSummary("A summary",seen),uniqueNewsSummary("Another summary",seen)]})())')),['<p class="briefing-quote">A  summary</p>','','<p class="briefing-quote">Another summary</p>']);
});

test('V3.6 audio leaves are mutually exclusive and overview only counts formal releases',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');
 assert.deepEqual(JSON.parse(run('JSON.stringify(MODEL_TABS.map(x=>x[0]))')),['video','image','llm','audio']);
 for(const src of ['libraryModels()','state.modelReleases','(state.modelReleaseData||{}).verifiedStages||[]']){
  const p=JSON.parse(run('JSON.stringify((()=>{const a='+src+';return {total:a.filter(x=>categoryFilter(x,"audio")).length,parts:["music","speech","audio-other"].map(c=>a.filter(x=>categoryFilter(x,c)).length)}})())'));
  assert.equal(p.total,p.parts.reduce((a,b)=>a+b,0));
 }
 assert.equal(run('audioLeaf({category:"audio",audioSubtype:"语音识别 ASR"})'),'speech');assert.equal(run('audioLeaf({category:"audio",audioSubtype:"实时语音交互"})'),'audio-other');
 run("setView('overview')");assert.equal((node('content').innerHTML.match(/class="overview-category(?: zero)?"/g)||[]).length,4);
 for(const mode of ['confirmed','pending','announcements'])for(const c of ['all','video','image','llm','audio','music','speech','audio-other']){
  run("setView('today',{releaseMode:"+JSON.stringify(mode)+",releaseCategory:"+JSON.stringify(c)+"})");assert.doesNotMatch(node('content').innerHTML,/\+\s*\d+\s*上线/);
  if(mode==='confirmed')assert.doesNotMatch(node('content').innerHTML,/已核实模型上线阶段/);
 }
});

test('expired snapshot is a legitimate empty release window, not a broken page',async()=>{
 const {run,node}=setup({now:snapshotTime+60*86400000});await run('loadAllForTests()');
 run("setView('today',{releaseMode:'confirmed',releaseWindow:'30',releaseCategory:'all'})");
 assert.doesNotMatch(node('content').innerHTML,/class="release-main"/);
 assert.match(node('content').innerHTML,/最近 30 天没有符合当前筛选的已核实发布事件/);
 run("setView('overview')");
 assert.equal(run('overviewSummary(new Date()).confirmed.length'),0);
 assert.match(node('content').innerHTML,/同步延迟/);
});

test('a failed model source attempt does not make an old successful read current',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');
 run("state.modelMonitorStatus={checkedAt:new Date().toISOString(),lastSuccessfulCheckAt:'2000-01-01T00:00:00Z',successSources:0,failedSources:38,totalSources:38,sources:[]};setView('overview');render()");
 assert.equal(run('modelSuccessStamp(state.modelMonitorStatus)'),'2000-01-01T00:00:00Z');
 assert.match(node('content').innerHTML,/同步延迟 · [^<]*模型信源/);
 assert.match(node('content').innerHTML,/38 个采集异常/);
});


test('AIHOT unchanged content keeps download date but uses successful validation for freshness',()=>{
 const {run}=setup();
 run("state.aihot.updatedAt='2026-11-27T00:00:00Z';state.aihot.checkedAt='2026-11-27T02:00:00Z'");
 assert.equal(run('selectedValidationStamp()'),'2026-11-27T02:00:00Z');
 assert.equal(run('state.aihot.updatedAt'),'2026-11-27T00:00:00Z');
 run("state.aihot.checkedAt='2026-11-26T00:00:00Z'");
 assert.equal(run('selectedValidationStamp()'),'2026-11-27T00:00:00Z');
 run("state.aihot.checkedAt='invalid'");
 assert.equal(run('selectedValidationStamp()'),'2026-11-27T00:00:00Z');
});

// The retired broad-news snapshot must not affect current briefing availability.
test('briefings load only the three current snapshots and never request retired news',async()=>{
 const {run,node,requested}=setup({query:'?view=feeds',fail:['news-today.json']});
 await run('loadData()');
 assert.deepEqual([...requested].sort(),['aihot-daily.json','aihot-items.json','juya-daily.json']);
 assert.doesNotMatch(node('content').innerHTML,/部分数据未加载/);
 assert.equal(run("Object.prototype.hasOwnProperty.call(dataFiles,'news')"),false);
 run("state.briefingTab='selected';render()");
 assert.match(node('content').innerHTML,/AIHOT 精选/);
 await run('ensureSearchData()');
 assert.ok(!requested.includes('news-today.json'));
});

test('overview release links use exact IDs, preserve grouped family and lazy loading',async()=>{
 const {run,node,requested}=setup();await run('loadData()');
 assert.equal(requested.length,5);
 assert.ok(!requested.includes('models.json'));
 run("state.modelReleaseData={items:[],pending:[],windowEnd:chinaDay(new Date())};state.modelReleases=[{id:'one',modelFamilyId:'seedance',modelVersionId:'seedance-2-0',modelName:'Seedance 2.0',category:'video',vendor:'ByteDance',publishedAt:chinaDay(new Date()),url:'https://example.com/release'}];render()");
 assert.match(node('content').innerHTML,/data-model-open="seedance" data-model-version="seedance-2-0"/);
 assert.match(node('content').innerHTML,/href="https:\/\/example.com\/release"/);
 run("openModelDetails('seedance','seedance-2-0')");await run('ensureViewData()');
 assert.match(node('content').innerHTML,/model-detail-version-selected" data-version-id="seedance-2-0"/);
 run('closeModelDetails()');assert.equal(run('state.view'),'overview');
 run("state.modelReleases=[{id:'a',modelFamilyId:'seedance',modelVersionId:'v1',modelName:'A',category:'video',vendor:'ByteDance',publishedAt:chinaDay(new Date()),evidenceType:'official-release',url:'https://example.com/blog/group'},{id:'b',modelFamilyId:'seedance',modelVersionId:'v2',modelName:'B',category:'video',vendor:'ByteDance',publishedAt:chinaDay(new Date()),evidenceType:'official-release',url:'https://example.com/blog/group'}];render()");
 assert.match(node('content').innerHTML,/data-model-open="seedance" aria-label="查看 A \/ B 家族详情"/);
 assert.doesNotMatch(node('content').innerHTML,/data-model-version="v[12]"/);
 run("state.modelReleases=[{id:'unknown',modelFamilyId:'bad id',modelVersionId:'v1',modelName:'Unknown',category:'video',vendor:'Unknown',publishedAt:chinaDay(new Date()),url:'https://example.com/unknown'}];render()");
 assert.doesNotMatch(node('content').innerHTML,/class="overview-model-open"/);
 assert.match(node('content').innerHTML,/href="https:\/\/example.com\/unknown"/);
});

test('release detail target is shared and never chooses a grouped first version',async()=>{
 const {run,node}=setup({query:'?view=today&status=confirmed'});await run('loadData()');
 const rows=[{id:'a',modelFamilyId:'seedance',modelVersionId:'v1',modelName:'A',category:'video',vendor:'ByteDance',evidenceType:'official-release',url:'https://example.com/blog/group'},{id:'b',modelFamilyId:'seedance',modelVersionId:'v2',modelName:'B',category:'video',vendor:'ByteDance',evidenceType:'official-release',url:'https://example.com/blog/group'}];
 run("state.modelReleases="+JSON.stringify(rows)+".map(x=>({...x,publishedAt:chinaDay(new Date())}));render()");
 assert.match(node('content').innerHTML,/class="text-link release-model-link" data-model-open="seedance">查看模型家族/);
 assert.match(node('content').innerHTML,/data-model-open="seedance" data-model-version="v1">型号详情/);
 assert.match(node('content').innerHTML,/data-model-open="seedance" data-model-version="v2">型号详情/);
 assert.match(node('content').innerHTML,/href="https:\/\/example.com\/blog\/group"/);
 run("state.modelReleases=state.modelReleases.slice(0,1);render()");
 assert.match(node('content').innerHTML,/class="text-link release-model-link" data-model-open="seedance" data-model-version="v1">查看模型版本/);
 assert.equal(run("releaseDetailTarget({modelFamilyId:'seedance',modelVersionId:'bad id'})"),null);
 assert.equal(run("releaseDetailTarget({modelFamilyId:'seedance',versions:[{modelFamilyId:'other',modelVersionId:'v1'}]})"),null);
 assert.equal(run("releaseDetailTarget({modelFamilyId:'seedance',versions:[]})"),null);
});

test('competitor and model intelligence separates publisher from platform integration and deduplicates exact originals',async()=>{
 const {run,node,requested}=setup({query:'?view=feeds&briefing=competitors',now:'2026-11-28T00:00:00+08:00'});await run('loadData()');
 assert.ok(requested.includes('aipick-data.json'));
 run("state.aihot.items=[{title:'LibTV 上架 MAGI-2',publishedAt:'2026-11-27T05:00:00Z',category:'ai-products',links:{original:'https://x.com/libtv/status/123'}}];state.aipick={items:[{title:'LibTV 上架 MAGI-2',publishedAt:'2026-11-27T05:00:00Z',category:'ai-products',links:{original:'https://twitter.com/libtv/status/123?utm_source=foo'}},{title:'Sand.ai发布MAGI-2',publishedAt:'2026-11-27T05:00:00Z',category:'ai-models',links:{original:'https://sand.ai/blog/magi-2'}}]};render()");
 assert.match(node('content').innerHTML,/LibTV 上架 MAGI-2/);assert.doesNotMatch(node('content').innerHTML,/Sand.ai发布MAGI-2/);
 assert.match(node('content').innerHTML,/1 条原文去重/);
 run("state.briefingTab='vendors';render()");assert.match(node('content').innerHTML,/Sand.ai发布MAGI-2/);assert.doesNotMatch(node('content').innerHTML,/LibTV 上架 MAGI-2/);
});
test('hot view preserves original source rank and excludes stale observations',async()=>{
 const {run,node}=setup({query:'?view=feeds&briefing=hot',now:'2026-11-28T00:00:00+08:00'});await run('loadData()');
 run("state.aipick={fetchedAt:'2026-11-27T12:00:00Z',hotTopics:[{rank:3,title:'Higgsfield 接入模型',latestAt:'2026-11-27T10:00:00Z',participantCount:6,sourceCount:5,sourceNames:['X · official','抖音'],links:{story:'https://aipick.news/story/demo'}},{rank:1,title:'旧热点',latestAt:'2026-11-20T00:00:00Z'}]};render()");
 assert.match(node('content').innerHTML,/原榜 3 · 6 位参与者 · 5 个来源/);assert.match(node('content').innerHTML,/报道合集/);assert.doesNotMatch(node('content').innerHTML,/旧热点/);assert.match(node('content').innerHTML,/AIHOT 原榜/);
});

test('official competitor changelog is distinct from model release and ignores other brand filter',async()=>{
 const {run,node,requested}=setup({query:'?view=feeds&briefing=competitors',now:'2026-11-28T00:00:00+08:00'});await run('loadData()');assert.ok(requested.includes('app-updates.json'));
 run("state.appUpdates={sources:[{id:'higgsfield-changelog',lastSuccessAt:'2026-11-27T12:00:00Z'}],events:[{sourceId:'higgsfield-changelog',claimType:'first-party-product-changelog',featureName:'Higgsfield Mangaka',publisherCalendarDay:'2026-11-02',updateType:'product-release',productArea:'Image Tools',sourceUrl:'https://higgsfield.ai/creator-hub/changelog'}]};render()");
 assert.match(node('content').innerHTML,/Higgsfield Mangaka/);assert.match(node('content').innerHTML,/2026-11-02 · 产品发布/);
 run("creatorBrand='LibTV';render()");assert.doesNotMatch(node('content').innerHTML,/Higgsfield Mangaka/);
});

test('competitor first-party views separate dated providers and expose stale source dates',async()=>{
 const {run,node}=setup({query:'?view=feeds&briefing=competitors',now:'2026-11-28T00:00:00+08:00'});await run('loadData()');
 run("state.appUpdates={sources:[{id:'flova-changelog',vendor:'Flova',role:'competitor',url:'https://www.flova.ai/en/docs/changelog/',lastSuccessAt:'2026-11-27T12:00:00Z'},{id:'tapnow-changelog',vendor:'TapNow',role:'competitor',url:'https://docs.tapnow.ai/en/docs/changelog',lastSuccessAt:'2026-11-27T12:00:00Z'},{id:'libtv-entry',vendor:'LibTV',role:'competitor',status:'navigation-only',url:'https://www.liblib.tv/show'}],events:[{sourceId:'flova-changelog',claimType:'first-party-product-changelog',featureName:'Audio separation',publisherCalendarDay:'2026-11-24',sourceUrl:'https://www.flova.ai/en/docs/changelog/'},{sourceId:'tapnow-changelog',claimType:'first-party-product-changelog',featureName:'Old relight',publisherCalendarDay:'2026-10-13',sourceUrl:'https://docs.tapnow.ai/en/docs/changelog'}]};render()");
 assert.match(node('content').innerHTML,/Audio separation/);assert.match(node('content').innerHTML,/超过30天/);assert.match(node('content').innerHTML,/正文未读/);assert.doesNotMatch(node('content').innerHTML,/Old relight/);
 run("creatorBrand='Flova';render()");assert.match(node('content').innerHTML,/Audio separation/);assert.doesNotMatch(node('content').innerHTML,/TapNow · 官方功能与模型接入/);
});

test('personal reader uses selected direct requests and independent cooldown without local server',async()=>{
 const {run,node,ctx}=setup({query:'?view=feeds&briefing=competitors',now:'2026-11-28T00:00:00+08:00'});await run('loadData()');
 assert.match(node('content').innerHTML,/个人阅读 · 双源最新精选/);
 const calls=[];ctx.mockRequest=async(url,options)=>{
  calls.push({url,options});
  if(url.startsWith('https://aipick.news'))return {ok:false,status:429,headers:{get:()=> '3600'}};
  return {ok:true,status:200,headers:{get:()=> 'etag'},text:async()=>JSON.stringify({items:[{title:'Higgsfield 新功能',links:{original:'https://higgsfield.ai/blog/demo'},publishedAt:'2026-11-27T08:00:00Z'}]})};
 };
 const result=JSON.parse(await run("readCreatorSources('competitors','Higgsfield',mockRequest).then(JSON.stringify)"));
 assert.equal(calls.length,2);assert.ok(calls.every(x=>x.url.includes('mode=selected')&&x.url.includes('q=Higgsfield')&&x.options.credentials==='omit'));
 assert.equal(result.sources.AIHOT.data.items.length,1);assert.match(result.sources.AIPick.error,/429/);
 await run("readCreatorSources('competitors','Higgsfield',mockRequest)");assert.equal(calls.length,2);
});

test('platform adoption phrased model-first is recognized without confusing the publisher',()=>{
 const {run}=setup();
 assert.equal(run("creatorIntegrationTarget('MAGI-2 视频模型上线 LibTV','LibTV')"),true);
 assert.equal(run("creatorIntegrationTarget('MAGI-2 视频模型上线 LibTVextra','LibTV')"),false);
 assert.equal(run("creatorIntegrationTarget('Sand.ai 发布 MAGI-2，LibTV 用户讨论','LibTV')"),false);
});

test('creator rows retain WeChat originals and distinguish story from representative original',()=>{
 const {run}=setup({now:'2026-11-28T00:00:00+08:00'});
 const rows=JSON.parse(run("JSON.stringify(creatorRows([{name:'AIPick',items:[{title:'Higgsfield 新功能',publishedAt:null,discoveredAt:'2026-11-27T06:00:00Z',links:{original:'http://mp.weixin.qq.com/s?mid=123&idx=1'}},{title:'Higgsfield 新功能',publishedAt:'2026-11-27T06:00:00Z',links:{original:'https://mp.weixin.qq.com/s?idx=1&mid=123'}},{title:'Higgsfield 热点合集',latestAt:'2026-11-27T07:00:00Z',links:{original:'https://mp.weixin.qq.com/s?mid=123&idx=1',story:'https://aipick.news/story/demo'}},{title:'不安全原文',publishedAt:'2026-11-27T07:00:00Z',links:{original:'http://example.org/article'}}]}],Date.now()))"));
 assert.equal(rows.length,2);
 assert.equal(rows.filter(x=>x.story).length,1);
 assert.equal(rows.filter(x=>!x.story).length,1);
 assert.equal(run("creatorOriginalUrl('http://mp.weixin.qq.com/s?mid=123')"),'https://mp.weixin.qq.com/s?mid=123');
 assert.equal(run("creatorOriginalUrl('http://mp.weixin.qq.com.evil.org/s?mid=123')"),'');
 assert.equal(run("creatorOriginalUrl('https://user:pass@mp.weixin.qq.com/s')"),'');
});

test('platform coverage displays measured originals, hot mentions and unexecuted queries separately',async()=>{
 const {run,node,requested}=setup({query:'?view=feeds&briefing=vendors',now:'2026-11-28T00:00:00+08:00'});await run('loadData()');
 assert.ok(requested.includes('app-updates.json'));
 run("state.appUpdates={platformCoverage:{platforms:[{id:'x',label:'X',role:'social',originalCount:3,providers:['AIHOT'],status:'original-observed'},{id:'instagram',label:'Instagram',role:'social',originalCount:0,hotSourceMentionCount:1,status:'hot-mention-only'},{id:'reddit',label:'Reddit',role:'social',originalCount:0,status:'not-observed'}]},targetedDiscovery:{queries:[{label:'MiniMax',provider:'AIPick'},{label:'MiniMax',provider:'AIHOT',lastAttemptAt:'2026-11-27T12:00:00Z',counts:{items:0}}]}};render()");
 assert.match(node('content').innerHTML,/社媒 1\/3/);
 assert.match(node('content').innerHTML,/仅热点来源提及/);
 assert.match(node('content').innerHTML,/样本未覆盖/);
 assert.match(node('content').innerHTML,/尚未执行/);
 assert.match(node('content').innerHTML,/0 条检索结果/);
 assert.equal(run("creatorBrandMatch('Seedance 2.5 上线 LibTV','vendors','Seedance')"),false);
 assert.equal(run("creatorBrandMatch('Creatify Aurora 2.0 上线 ElevenCreative','vendors','ElevenCreative')"),true);
 assert.equal(run("creatorBrandMatch('MAGI-2 视频模型上线 LibTV','competitors','LibTV')"),true);
});


test('recent release view defaults to seven days in reverse publication order',async()=>{
 const {run}=setup({query:'?view=today'});await run('loadAllForTests()');assert.equal(run('state.releaseWindow'),'7');assert.equal(run('state.releaseSort'),'date');
});

 test('product updates use publisher dates instead of fresh observation clocks and preserve provider links',async()=>{const {run,node}=setup({query:'?view=today&status=apps&days=7',now:'2026-11-28T12:00:00+08:00'});await run('loadAllForTests()');run(`state.appUpdates={events:[{featureName:'Old imported feature',publisherCalendarDay:'2026-11-01',claimType:'first-party-product-changelog',observedAt:'2026-11-28T00:00:00Z',sourceUrl:'https://example.com/old'},{featureName:'Newer publisher feature',publisherCalendarDay:'2026-11-27',claimType:'first-party-product-changelog',observedAt:'2026-11-27T00:00:00Z',sourceUrl:'https://example.com/new'},{featureName:'Earlier publisher feature',publisherCalendarDay:'2026-11-24',claimType:'first-party-product-changelog',observedAt:'2026-11-28T01:00:00Z',sourceUrl:'https://example.com/earlier'},{modelName:'Undated visible model',observedAt:'2026-11-28T00:00:00Z',sourceUrl:'https://example.com/model'}],targetedDiscovery:{queries:[{label:'Higgsfield',term:'Higgsfield',provider:'AIHOT'},{label:'Higgsfield',term:'Higgsfield',provider:'AIPick'}]}};render()`);let out=node('content').innerHTML;assert.doesNotMatch(out,/Old imported feature/);assert.ok(out.indexOf('Newer publisher feature')<out.indexOf('Earlier publisher feature'));assert.match(out,/日期待确认的近期自动观察/);assert.match(out,/观察时间 · 非发布日期/);assert.match(out,/https:\/\/aihot\.news\/api\/v1\/items[^"]*q=Higgsfield[^"]*"[^>]*>Higgsfield · AIHOT/);assert.match(out,/https:\/\/aipick\.news\/api\/v1\/items[^"]*q=Higgsfield[^"]*"[^>]*>Higgsfield · AIPick/);run("state.releaseWindow='30';render()");assert.match(node('content').innerHTML,/Old imported feature/);});

test('open source radar distinguishes curated research from metadata discovery and preserves safe links',async()=>{
 const {run,node,requested}=setup({query:'?view=platforms&category=opensource'});await run('loadData()');assert.ok(requested.includes('awesome-repos.json'));
 run("state.repoRadar={items:[{repo:'maker/whitebox',url:'https://github.com/maker/whitebox',name:'Whitebox',category:'video',license:'AGPL-3.0',research:{idea:'白模导演台',caution:'许可证需评估',review:'readme-reviewed',evidenceUrl:'https://github.com/maker/whitebox#readme'},metadataStatus:'ok'}],researchDiscovery:{items:[{repo:'maker/voice',url:'https://github.com/maker/voice',description:'audio separation',researchCategory:'audio',provider:'GitHub Search',stars:5,metadataCheckedAt:'2026-11-28T00:00:00Z'},{repo:'maker/unsafe',url:'https://github.com.evil.test/maker/unsafe',description:'Unsafe injected repository'}]}};render()");
 const out=node('content').innerHTML;assert.match(out,/白模导演台/);assert.match(out,/README 已阅读/);assert.match(out,/候选 · GitHub Search/);assert.match(out,/AGPL-3.0/);assert.doesNotMatch(out,/Unsafe injected repository/);assert.match(out,/非 GitHub 热榜/);
});
