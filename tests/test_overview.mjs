
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
function setup({query='',fail=[],defer}={}){
 const requested=[];
 const nodes=new Map();
 function node(id){
  if(!nodes.has(id))nodes.set(id,{id,innerHTML:'',textContent:'',value:'',classList:{toggle(){},remove(){}},addEventListener(){},insertAdjacentHTML(where,value){this.innerHTML=where==='afterbegin'?value+this.innerHTML:this.innerHTML+value},querySelectorAll(){return []},querySelector(){return null}});
  return nodes.get(id);
 }
 const location={search:query,protocol:'https:'};const entries=[];let cursor=-1;const history={state:null,replaceState(s,_,url){this.state=s;location.search=url.split('#')[0];if(cursor<0){entries.push({state:s,url});cursor=0}else entries[cursor]={state:s,url}},pushState(s,_,url){entries.splice(cursor+1);entries.push({state:s,url});cursor++;this.state=s;location.search=url},back(){if(cursor>0){cursor--;this.state=entries[cursor].state;location.search=entries[cursor].url;vm.runInContext('restoreNavigation(window.history.state)',ctx)}}};
 const ctx=vm.createContext({URL,URLSearchParams,Intl,Date,console,location,window:{location,history,scrollY:0,scrollTo(x,y){this.scrollY=y}},document:{querySelectorAll(){return []},getElementById:node,addEventListener(){}},localStorage:{getItem(){return null}},fetch:async url=>{
  const name=url.split('/').pop().split('?')[0];requested.push(name);
  if(defer)await defer(name);
  if(fail.includes(name))return {ok:false,status:503};
  return {ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,'site/data',name),'utf8'))};
 }});
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
 assert.equal(run("overviewSummary(new Date('2026-11-26T06:00:00Z')).pendingUndated"),1);
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

test('overview jumps to distinct confirmed and pending release views',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');
 assert.match(node('content').innerHTML,/data-release-mode-target="pending"/);
 run("state.releaseMode='pending';setView('today')");assert.match(node('content').innerHTML,/aria-pressed="true" data-release-mode="pending"/);assert.doesNotMatch(node('content').innerHTML,/class="release-company"/);
 run("state.releaseMode='confirmed';render()");assert.match(node('content').innerHTML,/aria-pressed="true" data-release-mode="confirmed"/);assert.doesNotMatch(node('content').innerHTML,/<h2>官方动态 · 待复核<\/h2>/);
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
 const {run}=setup();await run('loadAllForTests()');run("setView('today',{releaseMode:'pending'});state.releaseCategory='video';state.query='Seed';render();window.scrollY=380;setView('feeds',{briefingTab:'selected'});window.history.back()");
 assert.equal(run('state.view'),'today');assert.equal(run('state.releaseMode'),'pending');assert.equal(run('state.releaseCategory'),'video');assert.equal(run('state.query'),'Seed');assert.equal(run('window.scrollY'),380);
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
 assert.match(node('content').innerHTML,/class="release-main"/);assert.match(node('content').innerHTML,/class="release-actions"/);assert.match(node('content').innerHTML,/data-model-version=/);
 run("setView('models')");assert.match(node('content').innerHTML,/最近发布日期/);assert.match(node('content').innerHTML,/table-scroll-hint/);
 run("setView('feeds')");assert.doesNotMatch(node('content').innerHTML,/class="briefing-intro"/);assert.match(node('content').innerHTML,/briefing-original-links/);
});

test('creator opportunities distinguish date precision and program registration',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('opportunities')");
 assert.match(node('content').innerHTML,/AI 创作比赛/);assert.match(node('content').innerHTML,/Higgsfield Talent Contest/);
 assert.equal(run("contestStatus({deadlineDate:'2026-11-26',deadlineAt:'2026-11-26T19:00:00Z'},new Date('2026-11-26T18:59:00Z')).key"),'window');
 assert.equal(run("contestStatus({deadlineDate:'2026-11-26',deadlineAt:'2026-11-26T19:00:00Z'},new Date('2026-11-26T19:00:00Z')).key"),'closed');
 assert.equal(run("contestStatus({deadlineDate:'2026-11-26'},new Date('2026-11-26T10:00:00Z')).key"),'unknown');
 run("state.opportunityTab='programs';render()");assert.match(node('content').innerHTML,/开放状态待确认/);assert.ok(run('creatorPrograms().length')>20);assert.ok(run("searchGlobal('Higgsfield Talent Contest','contest').length")>0);
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
 run("setView('opportunities',{opportunityTab:'programs'})");assert.match(node('content').innerHTML,/未检测/);
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
 run("state.topics=[{id:'google',group:'公司与模型',name:'Google',milestones:[{auditId:'joint',date:'2026-01-01',title:'Veo 3 and Imagen 4 combined',kind:'模型',verificationStatus:'已确认：型号、日期与事件性质',modelCategory:['image','video']},{date:'2026-01-02',title:'Candidate',kind:'模型发布',autoCollected:true}]}];render()");
 assert.match(node('content').innerHTML,/Veo 3 and Imagen 4 combined/);
 assert.match(node('content').innerHTML,/来源日期非首发确认/);
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
 assert.match(node('content').innerHTML,/Pending Example Festival/);
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
 assert.match(markup,/重点 AI 资讯/);assert.match(markup,/探索工作台/);assert.doesNotMatch(markup,/完整日报与精选/);assert.doesNotMatch(markup,/<h2>官方发现 · 待复核<\/h2>/);
 assert.match(markup,/data-briefing-target="combined"/);assert.doesNotMatch(markup,/data-briefing-target="(?:aihot|juya|selected)"/);for(const view of ['today','feeds','social','models','rankings','topics','practice','opportunities','platforms'])assert.ok(markup.includes('data-view="'+view+'"'),view);
 run("setView('feeds',{briefingTab:'combined'})");assert.match(node('content').innerHTML,/综合资讯/);assert.match(node('content').innerHTML,/条原始报道/);
});

test('release range and order persist in route',async()=>{
 const {run,node}=setup({query:'?view=today&days=7&sort=date'});await run('loadAllForTests()');assert.equal(run('state.releaseWindow'),'7');assert.equal(run('state.releaseSort'),'date');assert.match(node('content').innerHTML,/data-release-window/);
});

test('briefing category and practice links keep full resources accessible',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('feeds',{briefingTab:'combined',briefingCategory:'模型'})");assert.match(node('content').innerHTML,/aria-pressed="true" data-briefing-category="模型"/);assert.match(node('content').innerHTML,/完整摘要与来源/);
 run("setView('practice',{modelPracticeType:'model'})");assert.doesNotMatch(node('content').innerHTML,/模型库详情 ↗/);assert.match(node('content').innerHTML,/模型库详情 →/);
});

test('social views separate actual verified homepages, search entries and posts',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');run("setView('social')");assert.match(node('content').innerHTML,/social-brand-record/);assert.match(node('content').innerHTML,/已核验主页/);assert.equal(run("socialAccountState({status:'verified-search'})"),'官方搜索入口');
 run("setView('social',{socialView:'platforms',socialRegion:'platform:X'})");assert.match(node('content').innerHTML,/social-platform-record/);assert.doesNotMatch(node('content').innerHTML,/social-brand-record/);
 run("setView('social',{socialView:'posts',socialRegion:'all'})");assert.match(node('content').innerHTML,/social-post-row/);assert.match(node('content').innerHTML,/原帖发布时间不等于模型首发日期/);
});

test('reported internal-model concern is industry news, not a release',()=>{
 const {run}=setup();assert.equal(run("newsCategory({category:'要闻',title:'报道称 OpenAI 和 Anthropic 员工忧内部模型难以安全发布'})"),'行业');
});

test('library prioritization, history year and review filters retain records',async()=>{
 const {run,node}=setup();await run('loadAllForTests()');assert.equal(run('state.modelSort'),'priority');assert.equal(run("latestDatedVersion({versions:[{name:'unknown'},{name:'old',releaseDate:'2025-01-01'},{name:'new',releaseDate:'2026-01-01'}]}).name"),'new');
 run("state.topics=[{id:'google',group:'公司与模型',name:'Google',milestones:[{date:'2025-01-01',title:'Old checked',verificationStatus:'已确认'},{date:'2026-01-01',title:'New checked',verificationStatus:'已确认'},{date:'2026-01-02',title:'Pending discovery',autoCollected:true}]}];setView('topics',{activeTopic:'google',topicYear:'2026',topicReview:'verified'})");assert.match(node('content').innerHTML,/New checked/);assert.doesNotMatch(node('content').innerHTML,/Old checked|Pending discovery/);
 run("state.topicReview='all';render()");assert.match(node('content').innerHTML,/Pending discovery/);
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

test('shared summary grid is used by official accounts and opportunities',async()=>{const {run,node}=setup();await run('loadAllForTests()');run("setView('social')");assert.match(node('content').innerHTML,/social-v2-stats summary-grid/);run("setView('opportunities')");assert.match(node('content').innerHTML,/opportunity-summary summary-grid/);});

test('creator pilot keeps partner evidence distinct from community authors and real posts',async()=>{const {run,node,requested}=setup({query:'?view=social&tab=creator-posts'});await run('loadAllForTests()');assert.ok(requested.includes('creator-watch.json'));assert.equal(run('state.creatorWatch.creators.length'),8);assert.equal(run('state.creatorWatch.posts.length'),4);assert.match(node('content').innerHTML,/Kaye Dream Island/);run("state.creatorType='教程';render()");assert.doesNotMatch(node('content').innerHTML,/Kaye Dream Island/);assert.match(node('content').innerHTML,/Exact Workflow/);run("setView('social',{socialView:'creators',creatorBrand:'PixVerse'})");assert.match(node('content').innerHTML,/Serge Donaldson/);assert.doesNotMatch(node('content').innerHTML,/kaye.creatives/);assert.match(node('content').innerHTML,/社媒主页待交叉核验/);});
