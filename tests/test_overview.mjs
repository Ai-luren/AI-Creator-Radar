
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
 const location={search:query,protocol:'https:'};
 const ctx=vm.createContext({URL,URLSearchParams,Intl,Date,console,location,window:{location,scrollTo(){}},document:{querySelectorAll(){return []},getElementById:node,addEventListener(){}},localStorage:{getItem(){return null}},fetch:async url=>{
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
