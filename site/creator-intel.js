var creatorBrands={competitors:['Higgsfield','LibTV','Liblib','Lovart','OiiOii','TapNow','Renoise','Flova','ShotLab','Updream'],vendors:['即梦','Dreamina','可灵','Kling','Seedance','Seedream','Sand.ai','MiniMax','海螺','Vidu','PixVerse','ElevenLabs','ElevenCreative','Midjourney','Niji','OpenAI','Google','Suno']};
var creatorBrand='',creatorPrivate={},creatorBusy=false,creatorLiveCache={},creatorLiveCooldown={};
function creatorOriginalUrl(value){
 try{var u=new URL(value);if(u.protocol==='http:'&&u.hostname==='mp.weixin.qq.com'&&!u.username&&!u.password&&!u.port&&/^\/s(?:\/|$)/.test(u.pathname))u.protocol='https:';if(u.protocol!=='https:'||u.username||u.password||u.port&&u.port!=='443')return '';return u.href}catch(e){return ''}
}
function creatorLink(url,label){var u=safeUrl(creatorOriginalUrl(url));return u==='#'?'':'<a href="'+esc(u)+'" target="_blank" rel="noopener noreferrer">'+esc(label)+' ↗</a>'}
function creatorRows(batches,now){
 var seen=new Map(),cutoff=now-7*86400000;
 batches.forEach(function(batch){(batch.items||[]).forEach(function(x){
  var links=x.links||{},story=!!x.latestAt&&!!links.story,t=Date.parse(story?x.latestAt:x.publishedAt||x.discoveredAt||''),link=creatorOriginalUrl(story?links.story:links.original),k=newsUrlKey(link);
  if(!k||!x.title||!Number.isFinite(t)||t<cutoff||t>now)return;
  if(!seen.has(k))seen.set(k,{item:x,providers:[],time:t,story:story});
  var row=seen.get(k);if(!row.providers.includes(batch.name))row.providers.push(batch.name)
 })});return Array.from(seen.values()).sort(function(a,b){return b.time-a.time})
}
function creatorSubject(title,brand){var t=String(title||'').normalize('NFKC').toLowerCase().trim(),b=brand.toLowerCase();if(t.slice(0,b.length)!==b)return false;return !/^[a-z0-9]/i.test(t.slice(b.length))}
function creatorIntegrationTarget(title,brand){
 var t=String(title||'').normalize('NFKC').toLowerCase(),b=brand.toLowerCase(),i=t.indexOf(b);
 while(i>=0){if(/(?:上线|上架|接入|登陆|登录)\s*$/.test(t.slice(0,i))&&!/^[a-z0-9]/i.test(t.slice(i+b.length)))return true;i=t.indexOf(b,i+b.length)}
 return false
}
function creatorHotMarkup(rows,name,stamp,now){
 var list=(rows||[]).filter(function(x){var t=Date.parse(x.latestAt||'');return x.title&&Number.isFinite(t)&&t<=now&&t>=now-48*3600000&&matches([x.title,(x.sourceNames||[]).join(' ')].join(' '))});
 return '<section class="briefing-digest-section"><div class="section-head"><h2>'+esc(name)+' 原榜</h2><span class="head-meta">'+esc(stamp?overviewTime(stamp):'未读取')+'</span></div><div class="briefing-list">'+(list.map(function(x){var l=x.links||{},n=Number.isInteger(x.participantCount)?x.participantCount+' 位参与者':'参与者未提供';return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc('原榜 '+(x.rank||'—')+' · '+n+(Number.isInteger(x.sourceCount)?' · '+x.sourceCount+' 个来源':'')+' · '+overviewTime(x.latestAt))+'</span><strong>'+esc(x.title)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><p>'+esc((x.sourceNames||[]).join('、')||'来源名单未提供')+'</p><div class="briefing-original-links">'+creatorLink(l.story,'报道合集')+creatorLink(l.original,'原帖')+creatorLink(l.aihot,'资讯条目')+'</div></div></details></article>'}).join('')||empty('当前48小时暂无可展示快照；请查看上游实时榜。'))+'</div></section>'
}
function creatorOfficialMarkup(now,term){
 var app=state.appUpdates||{},sources=(app.sources||[]).filter(function(s){return (s.role==='competitor'||s.id==='higgsfield-changelog')&&(!term||term===(s.vendor||'Higgsfield'))});
 // Keep the first-party entry available before the first successful probe.
 if((!term||term==='Higgsfield')&&!sources.some(function(s){return s.id==='higgsfield-changelog'}))sources.push({id:'higgsfield-changelog',vendor:'Higgsfield',url:'https://higgsfield.ai/creator-hub/changelog',links:[{url:'https://higgsfield.ai/',kind:'New drops'},{url:'https://higgsfield.ai/blog/editorials',kind:'功能详解'}]});
 if(!sources.length)return '';
 var cards=sources.map(function(source){
  var brand=source.vendor||'Higgsfield',all=(app.events||[]).filter(function(e){return e.claimType==='first-party-product-changelog'&&e.sourceId===source.id&&e.featureName}),latest=all.map(function(e){return e.publisherCalendarDay}).sort().pop(),rows=all.filter(function(e){return withinDays(e.publisherCalendarDay,30,new Date(now))&&matches([e.featureName,e.productArea].join(' '))}).sort(function(a,b){return String(b.publisherCalendarDay).localeCompare(a.publisherCalendarDay)});
  var stateLabel=source.skipReason==='aggregate-covered-sample'?'聚合样本覆盖 · 暂停重复探测':source.skipReason==='awaiting-aggregate'?'优先等待双源查询':source.status==='navigation-only'?'入口已确认 · 正文未读':source.lastSuccessAt?'最近读取 '+overviewTime(source.lastSuccessAt):'待自动读取';
  return '<section class="briefing-digest-section"><div class="section-head"><h2>'+esc(brand)+' · 官方功能与模型接入</h2><span class="head-meta">'+esc(stateLabel)+'</span></div><div class="briefing-original-links">'+creatorLink(source.url,'官方更新入口')+(source.links||[]).map(function(l){return creatorLink(l.url,l.kind)}).join('')+'</div>'+(latest?'<p class="page-desc">最近公开日志 '+esc(latest)+(withinDays(latest,30,new Date(now))?'':' · 超过30天，不能代表近期无更新')+'</p>':'')+(source.error?'<p class="overview-notice">'+esc(source.error)+'</p>':'')+'<div class="briefing-list">'+(rows.map(function(e){var kind={'model-integration':'模型接入','product-feature':'新功能','product-release':'产品发布','product-improvement':'能力改进'}[e.updateType]||'产品更新';return '<article class="briefing-card"><div class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(e.publisherCalendarDay+' · '+kind+' · '+(e.productArea||'官方更新日志'))+'</span><strong>'+esc(e.featureName)+'</strong></span><div class="briefing-original-links">'+creatorLink(e.sourceUrl,'官方记录')+'</div></div></article>'}).join('')||empty('暂无近30天自动读取的官方条目；查看官方入口或聚合报道。'))+'</div></section>'
 });
 return cards.join('')
}
function creatorIntelPage(tabs){
 var mode=state.briefingTab,hot=mode==='hot',cases=mode==='cases',now=Date.now(),a=state.aipick||{},brands=creatorBrands[mode]||[],term=brands.includes(creatorBrand)?creatorBrand:'',priv=creatorPrivate[mode+'|'+term]||{},sources=priv.sources||{},from=function(name,key,fallback){return sources[name]&&sources[name].data?sources[name].data[key]||[]:fallback||[]},stamp=function(name,fallback){return sources[name]&&sources[name].data?sources[name].observedAt:fallback};
 var head=pageHead('行业简报',hot?'最近48小时 · 保留各平台原榜与报道合集':cases?'最近7天 · 创作者精选与原帖，不冒充播放量排名':'最近7天 · '+(mode==='competitors'?'聚合平台与创作工具':'模型厂商及自有产品')+'相关动态','AIHOT + AIPick');
 var links=creatorLink('https://aihot.news/hot','AIHOT 实时热点')+creatorLink('https://aipick.news/hot','AIPick 实时热点');
 if(term)links+=['aihot.news','aipick.news'].map(function(h){return creatorLink('https://'+h+'/api/v1/items?mode=all&window=7d&limit=20&q='+encodeURIComponent(term),h.split('.')[0]+' 查询')}).join('');
 var filters=brands.length?'<div class="filter-row briefing-category-filters" role="group" aria-label="关注厂商">'+['全部'].concat(brands).map(function(b){var v=b==='全部'?'':b;return '<button class="filter-chip '+(v===term?'active':'')+'" aria-pressed="'+(v===term)+'" data-creator-brand="'+esc(v)+'">'+esc(b)+'</button>'}).join('')+'</div>':'';
 var live='<button type="button" class="tab" data-creator-refresh '+(creatorBusy?'disabled':'')+'>'+(creatorBusy?'读取中…':'个人阅读 · 双源最新精选')+'</button>';
 var status=Object.keys(sources).map(function(n){var x=sources[n];return n+' '+(x.error?'读取失败，保留可用记录：'+x.error:x.observedAt?overviewTime(x.observedAt):'未读取')}).join(' · ');
 var toolbar='<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div>'+filters+'<div class="news-toolbar"><p class="page-desc">'+(isLocalAihot()?'个人阅读实时查询，仅内存缓存。':'点击个人阅读，从你的浏览器直连双源，仅本次会话内存读取；不向本站服务器同步。失败可打开上游原站。')+'</p>'+live+'</div><div class="briefing-original-links">'+links+'</div>'+(status?'<p class="overview-notice">'+esc(status)+'</p>':'');
 if(hot)return head+toolbar+creatorHotMarkup(from('AIHOT','items',[]),'AIHOT',stamp('AIHOT',''),now)+creatorHotMarkup(from('AIPick','items',a.hotTopics),'AIPick',stamp('AIPick',a.fetchedAt),now)+'<p class="page-desc">原榜分别展示，不将两个平台的参与者或来源数相加；报道合集包含同一事件的多篇报道。热度不等于事实核实。</p>';
 var rows=creatorRows([{name:'AIHOT',items:from('AIHOT','items',state.aihot.items)},{name:'AIPick',items:from('AIPick','items',(a.items||[]).concat(a.hotTopics||[]))}],now).filter(function(r){var x=r.item;return !/黑五|黑色星期五|折扣|优惠券|限时促销|black friday|discount|coupon/i.test(x.title)&&matches([x.title,x.source&&x.source.name].join(' '))&&(cases?['tip','opinion'].includes(x.category):term?String(x.title).toLowerCase().includes(term.toLowerCase()):brands.some(function(b){return creatorSubject(x.title,b)||mode==='competitors'&&creatorIntegrationTarget(x.title,b)}))});
 var body=rows.map(function(r){var x=r.item,l=x.links||{};return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc([r.story?'讨论 '+overviewDateLabel(x.latestAt):x.publishedAt?overviewDateLabel(x.publishedAt):x.discoveredAt?'发现 '+overviewDateLabel(x.discoveredAt)+' · 发布日未知':'日期待确认',aihotCategoryName(x.category),r.providers.join(' / '),x.source&&x.source.name||''].filter(Boolean).join(' · '))+'</span><strong>'+esc(x.title)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><div class="briefing-original-links">'+creatorLink(l.original,r.story?'代表帖':'原帖')+creatorLink(l.story,'报道合集')+creatorLink(l.aihot,'资讯条目')+'</div><p class="page-desc">相关报道 · 不自动确认为产品已上线或模型首发。</p></div></details></article>'}).join('');
 return head+toolbar+'<section class="briefing-digest-section"><div class="section-head"><h2>'+esc(term|| (cases?'创作线索':mode==='competitors'?'竞品相关报道':'厂商相关报道'))+'</h2><span class="head-meta">'+rows.filter(function(r){return !r.story}).length+' 条原文去重'+(rows.some(function(r){return r.story})?' · '+rows.filter(function(r){return r.story}).length+' 个事件合集':'')+'</span></div><div class="briefing-list">'+(body||empty('当前快照无匹配报道，不代表没有更新。请按厂商打开上游或在本地查询。'))+'</div></section>'+(mode==='competitors'?'<details class="source-health"><summary>官方补缺与历史观察</summary>'+creatorOfficialMarkup(now,term)+'</details>':'')
}
function refreshCreatorIntel(){
 if(creatorBusy)return;
 var mode=state.briefingTab,term=(creatorBrands[mode]||[]).includes(creatorBrand)?creatorBrand:'',key=mode+'|'+term;
 creatorBusy=true;render();
 var task=isLocalAihot()?fetch('/__local/creator-intel?mode='+encodeURIComponent(mode)+'&term='+encodeURIComponent(term),{cache:'no-store'}).then(function(r){if(!r.ok)throw Error('HTTP '+r.status);return r.json()}):readCreatorSources(mode,term);
 return task.then(function(x){creatorPrivate[key]=x;var keys=Object.keys(creatorPrivate);while(keys.length>24)delete creatorPrivate[keys.shift()]}).catch(function(e){var previous=creatorPrivate[key]||{};creatorPrivate[key]={sources:Object.assign({},previous.sources||{},{"个人阅读":{error:String(e.message||e)}})}}).then(function(){creatorBusy=false;render()})
}
function creatorApiUrl(name,mode,term){
 var host={'AIHOT':'https://aihot.news','AIPick':'https://aipick.news'}[name];
 if(!host||!['competitors','vendors','hot','cases'].includes(mode)||term&&!(creatorBrands[mode]||[]).includes(term))throw Error('未知查询');
 if(mode==='hot')return host+'/api/v1/hot-topics';
 var q=new URLSearchParams({mode:'selected',window:'7d',by:'published',limit:'20'});
 if(term)q.set('q',term);
 else if(mode==='competitors'||mode==='vendors')q.set('category',mode==='competitors'?'ai-products':'ai-models');
 return host+'/api/v1/items?'+q.toString()
}
async function readCreatorSources(mode,term,request){
 var results={};request=request||fetch;
 for(var name of ['AIHOT','AIPick']){
  var url=creatorApiUrl(name,mode,term),now=Date.now(),cached=creatorLiveCache[url]||{},prior=cached.entry||{};
  if(now<(creatorLiveCooldown[name]||0)){results[name]=Object.assign({},prior,{error:'上游冷却中'});continue}
  if(cached.checkedAt&&now-cached.checkedAt<600000){results[name]=prior;continue}
  try{
   var headers={Accept:'application/json'};if(cached.etag)headers['If-None-Match']=cached.etag;
   var options={method:'GET',mode:'cors',credentials:'omit',redirect:'error',referrerPolicy:'no-referrer',cache:'no-store',headers:headers};
   if(typeof AbortSignal!=='undefined'&&typeof AbortSignal.timeout==='function')options.signal=AbortSignal.timeout(15000);
   var response=await request(url,options);
   if(response.status===304&&prior.data){results[name]=prior;creatorLiveCache[url]=Object.assign({},cached,{checkedAt:now});continue}
   if(!response.ok){var retry=response.headers&&response.headers.get('Retry-After'),delay=Number(retry),absolute=Date.parse(retry||'');creatorLiveCooldown[name]=now+Math.max(response.status===429||response.status===403||response.status===503?3600000:600000,Number.isFinite(delay)?delay*1000:0,Number.isFinite(absolute)?absolute-now:0);throw Error('HTTP '+response.status)}
   var raw=await response.text();if(raw.length>2097152)throw Error('响应过大');var data=JSON.parse(raw);
   if(!data||!Array.isArray(data.items)||data.items.length>(mode==='hot'?10:20)||data.items.some(function(x){return !x||typeof x!=='object'||Array.isArray(x)}))throw Error('数据格式异常');
   var entry={data:data,observedAt:new Date(now).toISOString()};results[name]=entry;creatorLiveCache[url]={checkedAt:now,etag:response.headers&&response.headers.get('ETag')||'',entry:entry};
  }catch(err){if(!(creatorLiveCooldown[name]>now))creatorLiveCooldown[name]=now+600000;results[name]=Object.assign({},prior,{error:String(err.message||err)})}
 }
 var keys=Object.keys(creatorLiveCache).sort(function(a,b){return creatorLiveCache[a].checkedAt-creatorLiveCache[b].checkedAt});while(keys.length>48)delete creatorLiveCache[keys.shift()];
 return {mode:mode,term:term,sources:results}
}
