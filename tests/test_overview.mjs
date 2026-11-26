
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
 const nodes=new Map();
 function node(id){
  if(!nodes.has(id))nodes.set(id,{id,innerHTML:'',textContent:'',value:'',classList:{toggle(){},remove(){}},addEventListener(){},insertAdjacentHTML(where,value){this.innerHTML=where==='afterbegin'?value+this.innerHTML:this.innerHTML+value},querySelectorAll(){return []},querySelector(){return null}});
  return nodes.get(id);
 }
 const location={search:query,protocol:'https:'};const entries=[];let cursor=-1;const history={state:null,replaceState(s,_,url){this.state=s;location.search=url.split('#')[0];if(cursor<0){entries.push({state:s,url});cursor=0}else entries[cursor]={state:s,url}},pushState(s,_,url){entries.splice(cursor+1);entries.push({state:s,url});cursor++;this.state=s;location.search=url},back(){if(cursor>0){cursor--;this.state=entries[cursor].state;location.search=entries[cursor].url;vm.runInContext('restoreNavigation(window.history.state)',ctx)}}};
 const ctx=vm.createContext({URL,URLSearchParams,Intl,Date,console,location,window:{location,history,scrollY:0,scrollTo(x,y){this.scrollY=y}},document:{querySelectorAll(){return []},getElementById:node,addEventListener(){}},localStorage:{getItem(){return null}},fetch:async url=>{
  const name=url.split('/').pop().split('?')[0];
  if(defer)await defer(name);
  if(fail.includes(name))return {ok:false,status:503};
  return {ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,'site/data',name),'utf8'))};
 }});
 vm.runInContext(boot,ctx);
 return {ctx,node,run:s=>vm.runInContext(s,ctx)};
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
test('overview renders before heavier registry; all existing routes remain renderable',async()=>{
 let release;const blocker=new Promise(r=>release=r);
 const {run,node}=setup({defer:name=>name==='models.json'?blocker:Promise.resolve()});
 const done=run('loadData()');
 for(let i=0;i<20&&!run('state.overviewReady');i++)await new Promise(r=>setTimeout(r,0));
 assert.equal(run('state.overviewReady'),true);assert.equal(run('state.dataReady'),false);
 assert.match(node('content').innerHTML,/今日概览/);
 run("setView('models')");assert.match(node('content').innerHTML,/正在加载模型库/);
 release();await done;
 assert.equal(run('state.dataReady'),true);
 for(const view of ['overview','today','feeds','social','models','rankings','topics','practice','platforms']){
  run("setView("+JSON.stringify(view)+")");
  assert.ok(node('content').innerHTML.includes('<h1'),view);
 }
 run("state.briefingTab='selected';setView('feeds')");assert.match(node('content').innerHTML,/AIHOT 精选/);
});
test('failed source does not block other modules and missing data is explicit',async()=>{
 const {run,node}=setup({fail:['model-releases-30d.json','models.json']});await run('loadData()');
 assert.equal(run('state.dataReady'),true);assert.match(node('content').innerHTML,/部分概览数据未加载/);
 assert.match(node('content').innerHTML,/发布数据暂不可用/);
 run("setView('models')");assert.match(node('content').innerHTML,/部分数据未加载/);
 run("setView('feeds')");assert.match(node('content').innerHTML,/行业简报/);
});

test('overview jumps to distinct confirmed and pending release views',async()=>{
 const {run,node}=setup();await run('loadData()');
 assert.match(node('content').innerHTML,/data-release-mode-target="pending"/);
 run("state.releaseMode='pending';setView('today')");assert.match(node('content').innerHTML,/aria-pressed="true" data-release-mode="pending"/);assert.doesNotMatch(node('content').innerHTML,/class="release-company"/);
 run("state.releaseMode='confirmed';render()");assert.match(node('content').innerHTML,/aria-pressed="true" data-release-mode="confirmed"/);assert.doesNotMatch(node('content').innerHTML,/<h2>官方动态 · 待复核<\/h2>/);
});

test('global index finds exact versions and cross-module records',async()=>{
 const {run}=setup();await run('loadData()');
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
 await run('loadData()');assert.equal(run('state.modelCategory'),'image');assert.equal(run('state.regionFilter'),'海外');assert.equal(run('state.query'),'Nano');
 run("window.scrollY=250;openModelDetails('seedance','seedance-2-0')");
 assert.match(run('window.location.search'),/model=seedance&version=seedance-2-0/);
 assert.match(node('content').innerHTML,/model-detail-version-selected" data-version-id="seedance-2-0"/);
 run('closeModelDetails()');assert.equal(run('state.selectedModelId'),null);assert.equal(run('state.modelCategory'),'image');assert.equal(run('state.query'),'Nano');assert.equal(run('window.scrollY'),250);
});
test('direct version links survive reload, unknown version degrades to family',async()=>{
 const a=setup({query:'?view=models&model=seedance&version=seedance-2-0'});await a.run('loadData()');assert.equal(a.run('state.selectedVersionId'),'seedance-2-0');
 const b=setup({query:'?view=models&model=seedance&version=unknown'});await b.run('loadData()');assert.equal(b.run('state.selectedVersionId'),null);assert.match(b.node('content').innerHTML,/具体型号不存在/);
});
test('page filters and deep links survive browser back',async()=>{
 const {run}=setup();await run('loadData()');run("setView('today',{releaseMode:'pending'});state.releaseCategory='video';state.query='Seed';render();window.scrollY=380;setView('feeds',{briefingTab:'selected'});window.history.back()");
 assert.equal(run('state.view'),'today');assert.equal(run('state.releaseMode'),'pending');assert.equal(run('state.releaseCategory'),'video');assert.equal(run('state.query'),'Seed');assert.equal(run('window.scrollY'),380);
});
