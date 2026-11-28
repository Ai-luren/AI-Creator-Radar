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
function creatorBrandMatch(title,mode,term){
 var brands=creatorBrands[mode]||[],active=term?[term]:brands;
 var targets=creatorBrands.competitors.filter(function(b){return creatorIntegrationTarget(title,b)});
 if(mode==='vendors'&&targets.length&&!/发布|正式推出|introduc|release/i.test(title))return false;
 return active.some(function(b){return creatorSubject(title,b)||creatorIntegrationTarget(title,b)})
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

function creatorCoverageMarkup(mode,term){
 var app=state.appUpdates||{},cov=app.platformCoverage||{},queries=(app.targetedDiscovery||{}).queries||[],platforms=cov.platforms||[];
 if(!platforms.length&&!queries.length)return '';
 var status={'original-observed':'已发现原文','hot-mention-only':'仅热点来源提及','not-observed':'样本未覆盖'};
 var monitored=platforms.filter(function(x){return x.role==='social'}),hit=monitored.filter(function(x){return x.originalCount>0}).length;
 var platformRows=platforms.map(function(x){return '<div class="overview-row"><span><strong>'+esc(x.label)+'</strong> · '+esc(status[x.status]||'未测量')+'</span><span class="overview-row-meta">'+esc((x.originalCount||0)+' 条原文'+(x.providers&&x.providers.length?' · '+x.providers.join(' / '):'')+(x.hotSourceMentionCount?' · 热点来源提及 '+x.hotSourceMentionCount:'')+(x.role==='reference'?' · 资料参考':x.role==='discovery'?' · 发现入口':''))+'</span></div>'}).join('');
 var relevant=queries.filter(function(q){return term?q.label===term:(creatorBrands[mode]||[]).includes(q.label)});
 var queryRows=relevant.map(function(q){var c=q.counts||{},actual=q.lastAttemptAt?'最近查询 '+overviewTime(q.lastAttemptAt):'尚未执行',provider=q.provider||'AIPick';return '<div class="overview-row"><span><strong>'+esc(q.label)+'</strong> · '+esc(provider)+'</span><span class="overview-row-meta">'+esc(actual+' · '+(q.status==='unavailable'?'读取失败':Number.isInteger(c.items)?c.items+' 条检索结果'+(Number.isInteger(c.selectedProductFeatures)?' · 功能 '+c.selectedProductFeatures+' / 接入 '+c.selectedModelIntegrations:''):'未测量'))+'</span></div>'}).join('');
 return '<details class="source-health"><summary>实际信源覆盖'+(platforms.length?' · 社媒 '+hit+'/'+monitored.length:'')+'</summary><p class="page-desc">当前七天精选快照的独立原文链接；未观察不代表平台不可访问。热点来源提及不算原文覆盖。定向查询结果数量不是已确认事件数。</p><div class="briefing-original-links">'+(cov.sources||[]).map(function(s){return '<span class="head-meta">'+esc(s.provider+' '+(s.fetchedAt?overviewTime(s.fetchedAt):'未读取')+(s.stale?' · 快照较旧':''))+'</span>'}).join('')+'</div>'+platformRows+(queryRows?'<h3>关注厂商查询记录</h3>'+queryRows:'')+'</details>'
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
 if(hot)return head+toolbar+creatorCoverageMarkup(mode,term)+creatorHotMarkup(from('AIHOT','items',[]),'AIHOT',stamp('AIHOT',''),now)+creatorHotMarkup(from('AIPick','items',a.hotTopics),'AIPick',stamp('AIPick',a.fetchedAt),now)+'<p class="page-desc">原榜分别展示，不将两个平台的参与者或来源数相加；报道合集包含同一事件的多篇报道。热度不等于事实核实。</p>';
 var rows=creatorRows([{name:'AIHOT',items:from('AIHOT','items',state.aihot.items)},{name:'AIPick',items:from('AIPick','items',(a.items||[]).concat(a.hotTopics||[]))}],now).filter(function(r){var x=r.item;return !/黑五|黑色星期五|折扣|优惠券|限时促销|black friday|discount|coupon/i.test(x.title)&&matches([x.title,x.source&&x.source.name].join(' '))&&(cases?['tip','opinion'].includes(x.category):creatorBrandMatch(x.title,mode,term))});
 var body=rows.map(function(r){var x=r.item,l=x.links||{};return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc([r.story?'讨论 '+overviewDateLabel(x.latestAt):x.publishedAt?overviewDateLabel(x.publishedAt):x.discoveredAt?'发现 '+overviewDateLabel(x.discoveredAt)+' · 发布日未知':'日期待确认',aihotCategoryName(x.category),r.providers.join(' / '),x.source&&x.source.name||''].filter(Boolean).join(' · '))+'</span><strong>'+esc(x.title)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><div class="briefing-original-links">'+creatorLink(l.original,r.story?'代表帖':'原帖')+creatorLink(l.story,'报道合集')+creatorLink(l.aihot,'资讯条目')+'</div><p class="page-desc">相关报道 · 不自动确认为产品已上线或模型首发。</p></div></details></article>'}).join('');
 return head+toolbar+creatorCoverageMarkup(mode,term)+'<section class="briefing-digest-section"><div class="section-head"><h2>'+esc(term|| (cases?'创作线索':mode==='competitors'?'竞品相关报道':'厂商相关报道'))+'</h2><span class="head-meta">'+rows.filter(function(r){return !r.story}).length+' 条原文去重'+(rows.some(function(r){return r.story})?' · '+rows.filter(function(r){return r.story}).length+' 个事件合集':'')+'</span></div><div class="briefing-list">'+(body||empty('当前快照无匹配报道，不代表没有更新。请按厂商打开上游或在本地查询。'))+'</div></section>'+(mode==='competitors'?'<details class="source-health"><summary>官方补缺与历史观察</summary>'+creatorOfficialMarkup(now,term)+'</details>':'')
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


// Research hypotheses are curated separately from API metadata. A public repo
// or SPDX identifier is not a production adoption decision.
function repositoryRadarPage(tabs){
 var data=state.repoRadar||{},discovery=data.researchDiscovery||{},categories={image:'图像',video:'视频',audio:'音频',workflow:'工作流 / Skills',component:'工程组件',prompt:'提示词',music:'音乐',tts:'语音',skills:'Skills',commercial:'广告', 'image-video':'图像 / 视频'};
 function valid(x){try{var u=new URL(x.url);return u.protocol==='https:'&&u.hostname==='github.com'&&!u.username&&!u.password&&u.pathname.replace(/\/$/,'').toLowerCase()===('/'+x.repo).toLowerCase()&&!x.archived}catch(e){return false}}
 function matched(x){return matches([x.name,x.repo,x.description,x.researchCategory,x.category,x.research&&x.research.idea].join(' '))}
 function license(x){return x.license&&x.license!=='NOASSERTION'?'仓库许可证 '+x.license:'许可证待核验'}
 function row(x,curated){
  var r=x.research||{},delta=x.observedStarChange,change=delta&&Number.isInteger(delta.delta)?' · 观测增量 '+(delta.delta>0?'+':'')+delta.delta+'（'+String(delta.from).slice(0,10)+' 至 '+String(delta.to).slice(0,10)+'）':'';
  return '<article class="creator-row"><div class="creator-when"><strong>'+esc(categories[x.researchCategory||x.category]||'创作参考')+'</strong><small>'+esc(x.pushedAt?'推送 '+String(x.pushedAt).slice(0,10):'推送日期未知')+'</small></div><div class="creator-main"><h3>'+esc(x.name||x.repo)+'</h3><div class="overview-row-meta">'+esc(x.repo+' · '+license(x)+(Number.isInteger(x.stars)?' · '+x.stars.toLocaleString('zh-CN')+' Stars':'')+change)+'</div><p>'+esc(x.description||'')+'</p>'+(r.idea?'<p><strong>产品构想：</strong>'+esc(r.idea)+'</p><small>'+esc(r.caution||'')+'</small>':'')+'<div class="practice-tags"><span class="pill">'+esc(curated?(r.review==='readme-reviewed'?'README 已阅读':r.review==='metadata-reviewed'?'元数据已核对':'既有精选'):'候选 · '+x.provider)+'</span><span class="pill">'+esc(x.metadataStatus==='cached'?'保留缓存 · 未刷新':curated&&x.metadataStatus!=='ok'?'元数据待更新':'不代表可商用集成')+'</span></div></div><div class="creator-actions">'+creatorLink(x.url,'GitHub')+(r.evidenceUrl?creatorLink(r.evidenceUrl,'研究依据'):'')+(x.liveUrl?creatorLink(x.liveUrl,'体验入口'):'')+'</div></article>';
 }
 var curated=(data.items||[]).filter(x=>valid(x)&&matched(x)),focused=curated.filter(x=>x.research),other=curated.filter(x=>!x.research);
 var candidates=(discovery.items||[]).filter(x=>valid(x)&&matched(x)).sort((a,b)=>String(b.metadataCheckedAt||'').localeCompare(String(a.metadataCheckedAt||'')));
 return pageHead('创作工具','开源创新雷达 · 从可用技术到产品功能','研究参考，不是集成结论')+'<div class="platform-tabs">'+tabs+'</div><section class="launch-section"><div class="section-head"><div><h2>产品创新精选</h2><p>按实际创作任务整理的项目、可借鉴方向与采用限制。</p></div><span class="head-meta">'+focused.length+' 项</span></div><div class="creator-list">'+(focused.map(x=>row(x,true)).join('')||empty('研究精选待资源采集上线。'))+'</div></section><section class="launch-section"><div class="section-head"><div><h2>近期发现 · 创作相关 GitHub 项目</h2><p>优先复用 AIHOT / AIPick 已精选的原始链接，否则定向搜索近期有推送的相关仓库。仅元数据发现，非 GitHub 热榜，不自动运行代码。</p></div><span class="head-meta">'+esc(discovery.lastSuccessAt?overviewTime(discovery.lastSuccessAt):'首次发现待运行')+'</span></div>'+(discovery.error?'<p class="creator-note">发现暂不可用，保留旧记录：'+esc(discovery.error)+'</p>':'')+'<div class="creator-list">'+(candidates.map(x=>row(x,false)).join('')||empty('当前没有已获取元数据的匹配候选；不表示没有相关项目。'))+'</div></section><details class="source-health"><summary>既有提示词与创作索引 · '+other.length+' 项</summary><div class="creator-list">'+other.map(x=>row(x,true)).join('')+'</div></details>';
}

// V4 opportunity reading: a deterministic topic match across existing snapshots.
// Never feed hypotheses into canonical model facts, search or product observations.
var innovationThemes=[
 {id:'sound',title:'影视声音工作台',form:'画布节点 / 垂直工作台',pain:'生成视频的对白、环境音与配乐难以独立修订。',idea:'探索音轨拆分、局部声音替换与时间线同步。',test:'先做同一条视频的音轨分离、对白替换和回写对照，检查音画同步与原声损伤。',pattern:/音轨|音视频生成|音频翻译|对白替换|口型同步|音效生成|人声分离|audio processing|track separation|audio separat|audio translation|lip.sync|sound effect|audio.video generation|whisperx/i},
 {id:'character',title:'角色与漫画资产工作台',form:'垂直 Studio / 资产节点',pain:'角色跨画格、分镜和场景的一致性难以维护。',idea:'探索角色档案、参考图复用、画格重绘和可编辑交付。',test:'用同一人物生成多场景画格，再修改单格，检查人物一致性与编辑范围。',pattern:/漫画|漫剧|三视图|角色一致性|角色设定|角色资产|角色多视角|character consistency|character turnaround|character sheet|mangaka|manga workspace|comic panel|comic studio/i},
 {id:'previs',title:'白模导演与镜头预演',form:'独立工具 / 画布节点',pain:'复杂镜头的站位、视角和运动难以通过纯文字控制。',idea:'探索白模调度、结构化分镜、镜头参数与参考帧交付。',test:'用相同镜头分别进行纯提示词与白模辅助测试，比较站位和运镜遵循度。',pattern:/白模|灰模|镜头预演|分镜|运镜控制|镜头控制|camera control|camera movement|storyboard|previs|shot planning/i},
 {id:'graphic',title:'可编辑视觉与动态图形素材',form:'小工具 / 资产节点',pain:'生成的文字、图形和视觉资产难以精确修改或重复利用。',idea:'探索文字校正、矢量或透明素材、动态表情包的可编辑交付。',test:'按原始需求分别验证文字准确度、背景分离与实际导出格式，不假定模型原生支持这些格式。',pattern:/文字.*(?:修正|校正|渲染|编辑)|矢量|透明背景|动态图形|表情包|sprite sheet|vector asset|transparent background|text rendering|text correction|\bsvg\b|\bgif\b/i},
 {id:'workflow',title:'多模型创作与后期编排',form:'画布节点 / 工作流模板',pain:'跨模型切换、生成任务依赖和后期处理耗费重复操作。',idea:'探索可复用节点、并行生成、质量检查与时间线输出。',test:'先跑一条两阶段创作流程，验证输入输出契约、错误重试与结果可编辑性。',pattern:/工作流|多模型串联|并行生成|节点编排|时间线剪辑|画布节点|comfyui|workflow|parallel|timeline edit|video editor|frame.*render/i}
];
function innovationSignals(snapshot,now){
 var signals=[],seen=new Set(),dateNow=new Date(now),app=snapshot.app||{};
 function add(type,title,detail,url,day,origin,meta){
  var link=creatorOriginalUrl(url);
  if(!title||!link||!day||!withinDays(day,7,dateNow))return;
  var key=[type,newsUrlKey(link),String(title).trim().toLowerCase()].join('|');
  if(seen.has(key))return;seen.add(key);
  signals.push(Object.assign({type:type,title:String(title),detail:String(detail||''),url:link,day:chinaDay(day),origin:String(origin||'')},meta||{}));
 }
 (snapshot.releases||[]).forEach(function(x){
  if(!x||!x.modelFamilyId||!x.modelVersionId||!x.verifiedAt||!x.evidenceType||releaseCategoryOrder(x.category)>=99||x.verificationStatus==='pending')return;
  add('model',x.modelName,x.summary,x.url,x.publishedAt,x.vendor,{category:x.category,modelFamilyId:x.modelFamilyId,modelVersionId:x.modelVersionId});
 });
 (app.events||[]).forEach(function(x){
  if(!x||x.claimType!=='first-party-product-changelog'||!x.publisherCalendarDay)return;
  var source=(app.sources||[]).find(function(s){return s.id===x.sourceId});
  if(!source||!(source.role==='competitor'||source.id==='higgsfield-changelog'))return;
  if(/discount|coupon|pricing|credits|折扣|积分|价格|促销/i.test(x.featureName||''))return;
  add('product',x.featureName,x.productArea,x.sourceUrl,x.publisherCalendarDay,source.vendor||source.name,{updateType:x.updateType});
 });
 (snapshot.batches||[]).forEach(function(batch){
  (batch.items||[]).forEach(function(x){
   if(!x||x.selected!==true||!x.publishedAt||!['tip','opinion'].includes(x.category)||x.links&&x.links.story)return;
   if(/折扣|积分|促销|优惠|discount|coupon|black friday/i.test(x.title||''))return;
   add('case',x.title,'',x.links&&x.links.original,x.publishedAt,batch.name);
  })
 });
 return signals;
}
function innovationOpportunityRows(snapshot,now){
 var signals=innovationSignals(snapshot,now),repos=snapshot.repos||{},typeOrder={model:0,product:1,case:2};
 return innovationThemes.map(function(theme){
  var found=signals.filter(function(s){return theme.pattern.test(s.title+' '+s.detail)}).sort(function(a,b){return b.day.localeCompare(a.day)||typeOrder[a.type]-typeOrder[b.type]});
  // Reviewed repositories are reference context only, never a recent product claim.
  var references=[],repoSeen=new Set();
  function repoRef(x){
   if(!x||x.archived===true||!x.research||!['readme-reviewed','metadata-reviewed'].includes(x.research.review))return;
   var link=creatorOriginalUrl(x.url),u;try{u=new URL(link)}catch(e){return}
   if(u.hostname!=='github.com'||u.pathname.replace(/\/$/,'').toLowerCase()!=='/'+String(x.repo||'').toLowerCase()||repoSeen.has(x.repo.toLowerCase()))return;
   if(!theme.pattern.test([x.name,x.description,x.research.idea].join(' ')))return;
   repoSeen.add(x.repo.toLowerCase());references.push({title:x.name||x.repo,url:link,review:x.research.review,caution:x.research.caution||'',idea:x.research.idea||'',license:x.license||''});
  }
  (repos.items||[]).forEach(repoRef);
  var shown=[],counts={};
  found.forEach(function(s){counts[s.type]=(counts[s.type]||0)+1;if(counts[s.type]<=2)shown.push(s)});
  return {id:theme.id,title:theme.title,form:theme.form,pain:theme.pain,idea:theme.idea,test:theme.test,signals:shown,signalCount:found.length,references:references.slice(0,3),latest:found[0]&&found[0].day||'',types:Object.keys(counts).length};
 }).filter(function(row){return row.signalCount>0}).sort(function(a,b){return b.latest.localeCompare(a.latest)||b.types-a.types||a.id.localeCompare(b.id)});
}
// Explore beyond the fixed themes without inventing a capability or declaring novelty.
// Exact normalized names only; punctuation and whitespace may vary, never drop version digits.
function innovationModelKey(title){return String(title||'').normalize('NFKC').trim().toLowerCase().replace(/[\s_-]+/g,'')}
function innovationExplorationRows(snapshot,now){
 var signals=innovationSignals(snapshot,now),models=signals.filter(function(s){return s.type==='model'}),products=signals.filter(function(s){return s.type==='product'}),rows=[];
 products.forEach(function(s){
  var links=s.updateType==='model-integration'?models.filter(function(m){return innovationModelKey(m.title)===innovationModelKey(s.title)}):[];
  rows.push({signal:s,related:links.length===1?links[0]:null,question:s.updateType==='model-integration'?'该型号可用的输入、输出与控制项是什么？能否封装成独立工具，而非只增加模型选项？':'这个功能把哪项创作操作变成了独立入口、节点或可重复流程？是否可用更少操作实现同一交付？'});
 });
 models.forEach(function(s){
  if(!['video','image','audio','music','tts'].includes(s.category)&&!innovationThemes.some(function(t){return t.pattern.test(s.title+' '+s.detail)}))return;
  rows.push({signal:s,related:null,question:'对照上一代，用固定素材分别验证可控性、失败边界及输出；再决定是否值得封装。'});
 });
 signals.filter(function(s){return s.type==='case'&&!innovationThemes.some(function(t){return t.pattern.test(s.title+' '+s.detail)})}).forEach(function(s){
  rows.push({signal:s,related:null,question:'阅读创作者原帖，拆出输入、关键步骤和可复现结果；先判断是否属于创作产品机会。'});
 });
 return rows.sort(function(a,b){return b.signal.day.localeCompare(a.signal.day)||({product:0,model:1,case:2}[a.signal.type]-{product:0,model:1,case:2}[b.signal.type])});
}
function innovationModelTestPlan(signal){
 if(!signal||signal.type!=='model')return null;
 var plans={
  video:['固定参考图、提示词、镜头及可比时长','对比主体一致性、运动轨迹、镜头控制、音画同步（如官方支持）','记录失败样本、重复生成稳定性及输出限制'],
  image:['固定角色参考、文本、布局与编辑区域','对比角色保持、文字准确度、局部编辑范围','检查输出分辨率、透明或矢量格式是否确实可用'],
  audio:['固定视频或音频参考、对白和环境音','对比音质、时间戳、声源保持和同步','检查独立音轨、可编辑输出与授权限制'],
  music:['固定场景、时长、情绪及参考节奏','对比结构、节奏、情绪和重复生成一致性','检查编辑、分轨和授权边界'],
  tts:['固定多语言台词、情绪与发音词表','对比可懂度、发音、停顿与情绪稳定性','核查说话人授权和对齐时间戳'],
  llm:['固定创作任务、输入资料与输出结构','对比指令遵循、素材理解及结构化输出','检查工具调用边界、重复稳定性与可复现性']
 };
 return {status:'待实测',baseline:'上一可用版本；若接口或输入不可比，记录差异，不强行评分',steps:plans[signal.category]||plans.llm};
}
function innovationImplementationPlan(row){
 var lanes={
  sound:['输入：原始视频及授权音频','处理：音轨拆分 → 局部生成或替换 → 对齐时间线','交付：可编辑轨道及回写视频'],
  character:['输入：授权人物参考与剧本','处理：固定角色档案 → 多视图 → 分镜及画格编辑','交付：可复用角色资产与画格'],
  previs:['输入：场景、人物站位与镜头描述','处理：结构化场景 → 灰模预演 → 视频模型参考','交付：参考帧、轨迹及镜头结果'],
  graphic:['输入：构图、文字、透明或矢量资产需求','处理：生成 → 校正 → 独立格式验证','交付：可编辑素材及实际格式'],
  workflow:['输入：统一素材与创作任务','处理：节点输入输出 → 生成编排 → 失败恢复与质检','交付：可重跑工作流与媒体结果']
 };
 return {steps:lanes[row.id]||[],references:row.references||[],status:'实现路径假设 · 未运行第三方代码'};
}
function innovationExplorationMarkup(snapshot,now){
 var rows=innovationExplorationRows(snapshot,now).filter(function(r){return matches([r.signal.title,r.signal.origin,r.signal.detail,r.question].join(' '))}),labels={model:'已核实模型发布',product:'官方产品日志',case:'创作者精选线索'};
 var list=rows.slice(0,12).map(function(r){var s=r.signal,plan=innovationModelTestPlan(s);
  return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(s.day+' · '+labels[s.type]+' · '+s.origin)+'</span><strong>'+esc(s.title)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded">'+(s.detail?'<p>'+esc(s.detail)+'</p>':'')+'<p><strong>探索问题：</strong>' +esc(r.question)+'</p>'+(plan?'<p><strong>能力测试清单 · '+esc(plan.status)+'</strong></p><p>'+esc(plan.baseline)+'</p><ol>'+plan.steps.map(function(x){return '<li>'+esc(x)+'</li>'}).join('')+'</ol>':'')+'<div class="briefing-original-links">'+creatorLink(s.url,'原始记录')+'</div>'+(r.related?'<p><strong>同名型号关联：</strong>'+esc(r.related.origin+' · '+r.related.title+' · '+r.related.day)+' '+creatorLink(r.related.url,'独立模型记录')+'。同名候选，不证明接口、权重或能力完全一致。</p>':'')+'</div></details></article>';
 }).join('');
 return '<section class="briefing-digest-section"><div class="section-head"><h2>新能力与功能探索</h2><span class="head-meta">'+Math.min(rows.length,12)+' / '+rows.length+' 条</span></div><p class="page-desc">保留主题之外的信号；不把既有模型功能认定为新增能力，不把官方日志日期当模型首发日期。</p><div class="briefing-list">'+(list||empty('近七天暂无符合条件的探索信号。'))+'</div></section>';
}
function innovationSurfaceMarkup(app,now){
 var sources=(app||{}).sources||[],rows=((app||{}).events||[]).filter(function(e){
  return e.kind==='new-product-surface'&&e.claimType==='first-party-product-surface'&&e.featureName&&withinDays(e.observedAt,7,new Date(now))&&creatorOriginalUrl(e.featureUrl||e.sourceUrl);
 }).map(function(e){var source=sources.find(function(s){return s.id===e.sourceId&&s.role==='competitor'&&s.type==='product-surface'});return source?{event:e,brand:source.vendor}:null}).filter(Boolean).filter(function(r){return matches([r.brand,r.event.featureName].join(' '))});
 rows.sort(function(a,b){return String(b.event.observedAt).localeCompare(String(a.event.observedAt))});
 return '<section class="briefing-digest-section"><div class="section-head"><h2>产品入口变化 · 观察时间</h2><span class="head-meta">'+rows.length+' 条</span></div><p class="page-desc">仅比较成功读取后的新增可见入口；首次基线不算更新，入口消失不代表下线。</p><div class="briefing-list">'+(rows.slice(0,12).map(function(r){var e=r.event;return '<article class="briefing-card"><div class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(r.brand+' · '+chinaDay(e.observedAt)+' · 首次观察，非发布日期')+'</span><strong>'+esc(e.featureName)+'</strong></span>'+creatorLink(e.featureUrl||e.sourceUrl,'官方入口')+'</div></article>'}).join('')||empty('暂无已成功观察的入口变化；查看功能矩阵中的现有能力。'))+'</div></section>'
}
function innovationPage(tabs){
 var snapshot={releases:state.modelReleases,app:state.appUpdates,repos:state.repoRadar,batches:[{name:'AIHOT',items:state.aihot.items},{name:'AIPick',items:(state.aipick||{}).items}]},now=Date.now();
 var rows=innovationOpportunityRows(snapshot,now);
 var filtered=rows.filter(function(row){return matches([row.title,row.idea,row.form].concat(row.signals.map(function(s){return s.title+' '+s.origin})).join(' '))});
 var labels={model:'已核实模型发布',product:'官方产品日志',case:'创作者精选线索'};
 var body=filtered.map(function(row){
  var implementation=innovationImplementationPlan(row);
  var evidence=row.signals.map(function(s){return '<div class="overview-row"><span><span class="overview-row-meta">'+esc(labels[s.type]+' · '+s.day+' · '+s.origin)+'</span><br><strong>'+esc(s.title)+'</strong></span><span>'+creatorLink(s.url,'原始证据')+'</span></div>'}).join('');
  var refs=row.references.map(function(x){return '<div class="overview-row"><span><strong>'+esc(x.title)+'</strong> · '+esc(x.review==='readme-reviewed'?'README 已阅读':'仅元数据核查')+'<br><span class="overview-row-meta">'+esc([x.idea,x.license?'仓库许可 '+x.license:'许可待核验',x.caution].filter(Boolean).join(' · '))+'</span></span>'+creatorLink(x.url,'仓库')+'</div>'}).join('');
  return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(row.latest+' · '+row.form+' · 产品机会假设')+'</span><strong>'+esc(row.title)+'</strong><span>'+esc(row.idea)+'</span></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><p><strong>待验证的痛点：</strong>'+esc(row.pain)+'</p><p><strong>最小验证：</strong>'+esc(row.test)+'</p><h3>近七天主题信号 · '+row.signalCount+' 条（每类最多展示两条）</h3>'+evidence+'<h3>最小实现路径 · '+esc(implementation.status)+'</h3><ol>'+implementation.steps.map(function(s){return '<li>'+esc(s)+'</li>'}).join('')+'</ol><h3>开源研究参考 · 不代表可直接采用</h3>'+(refs||'<p class="page-desc">当前快照暂无已核查的匹配仓库。</p>')+'</div></details></article>'
 }).join('');
 return pageHead('行业简报','将近期模型、竞品功能和创作者实验关联为可验证的产品机会。','创新机会 · 近7天')+'<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div><p class="page-desc">规则匹配 · 按最近信号日期排序；主题相近不代表技术已兼容或竞品采用该仓库。所有产品构想均为假设，不是发布事实，不使用模型推理 API。</p><section class="briefing-digest-section"><div class="section-head"><h2>值得原型验证</h2><span class="head-meta">'+filtered.length+' 个方向</span></div><div class="briefing-list">'+(body||empty('当前七天快照暂无符合规则的主题信号；不代表没有创新机会。'))+'</div></section>'+innovationExplorationMarkup(snapshot,now)+innovationSurfaceMarkup(snapshot.app,now)+'<details class="source-health"><summary>产品创新研究方法与官方入口</summary><p class="page-desc">研究资料不算近期上线事件。LibTV 官网可见版本更新入口，当前自动采集尚未读到功能级日志。</p><div class="briefing-original-links">'+creatorLink('https://higgsfield.ai/blog/inside-higgsfield','Inside Higgsfield · 产品研发复盘')+creatorLink('https://higgsfield.ai/blog/editorials','Higgsfield · 功能拆解')+creatorLink('https://www.liblib.tv/','LibTV · 官方产品与版本更新')+'</div></details>'
}

// Product signals are a reading priority, not a publication or model fact gate.
function isCoreProductNews(row){
 if(!row||row.category!=='产品')return false;
 var title=String(row.title||'');
 if(/折扣|优惠券|限时促销|黑五|黑色星期五|积分充值|discount|coupon|black friday|pricing/i.test(title))return false;
 return /Higgsfield|LibTV|Liblib|Lovart|OiiOii|TapNow|Renoise|Flova|ShotLab|Updream|即梦|Dreamina|可灵|Kling|海螺|MiniMax|Vidu|PixVerse/i.test(title);
}
function prioritizeProductNews(rows){
 return rows.slice().sort(function(a,b){return Number(isCoreProductNews(b))-Number(isCoreProductNews(a))});
}

// Manually observed official capabilities are context, not recent releases or
// guarantees of access. Existing collector logs remain the only live input.
var competitorMatrixBrands=['Higgsfield','LibTV','Flova','TapNow','Renoise'];
var competitorMatrixDimensions=[
 {id:'canvas',name:'创作画布',pattern:/画布|canvas|workflow|工作流|node|节点/i},
 {id:'studio',name:'垂直 Studio',pattern:/Mangaka|漫画|漫剧|Short Drama Studio|Property Studio|Shorts Studio|Ads Studio|Cinema Studio|studio\b/i},
 {id:'image',name:'图像与角色',pattern:/角色|三视图|character|image edit|图片编辑|图像编辑|reframe.*panel/i},
 {id:'video',name:'视频与预演',pattern:/白模|预演|3D.BOX|Editing Room|video edit|智能剪辑|camera control|运镜|video.*timeline|分镜/i},
 {id:'sound',name:'音频与对白',pattern:/audio|音频|音轨|对白|lip.sync|Intone|配音/i},
 {id:'agent',name:'Agent / Skills',pattern:/agent|Supercomputer|导演分身|TV Director|skills/i},
 {id:'integration',name:'模型接入',pattern:null},
 {id:'other',name:'其他产品功能',pattern:null}
];
var competitorMatrixReviewed=[
 {brand:'Higgsfield',name:'Mangaka · 漫画工作台',dimensions:['studio','image'],url:'https://higgsfield.ai/blog/higgsfield-introduces-mangaka',reviewedOn:'2026-11-28',note:'官方介绍角色、场景、道具复用及画格编辑。'},
 {brand:'Higgsfield',name:'Canvas',dimensions:['canvas'],url:'https://higgsfield.ai/canvas',reviewedOn:'2026-11-28',note:'官网导航显示入口；未实测节点范围。'},
 {brand:'LibTV',name:'LibTV 画布',dimensions:['canvas'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官方首页展示画布入口。'},
 {brand:'LibTV',name:'LibTV 3D-BOX',dimensions:['video'],url:'https://www.liblib.tv/3d-box',reviewedOn:'2026-11-28',note:'官方说明含搭景、站位及手绘运镜；未实测镜头参数。'},
 {brand:'LibTV',name:'LibTV Agent BETA',dimensions:['agent'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官方首页展示 Beta 入口。'},
 {brand:'LibTV',name:'音频生成',dimensions:['sound'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官方首页列出能力；未实测具体音频工具。'},
 {brand:'LibTV',name:'智能剪辑',dimensions:['video'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官方首页列出能力；未实测。'}
];
function competitorMatrixRows(app,now,reviewed){
 app=app||{};var seen=new Set(),rows=[],sources=app.sources||[];
 function add(row){var key=[row.brand,row.name,row.kind,row.day||''].join('|').toLowerCase();if(seen.has(key))return;seen.add(key);rows.push(row)}
 (app.events||[]).forEach(function(e){
  if(!e||e.claimType!=='first-party-product-changelog'||!e.featureName||!e.publisherCalendarDay||!withinDays(e.publisherCalendarDay,30,new Date(now)))return;
  var source=sources.find(function(s){return s.id===e.sourceId&&s.role==='competitor'}),brand=source&&source.vendor,url=creatorOriginalUrl(e.sourceUrl);
  if(!competitorMatrixBrands.includes(brand)||!url||/折扣|促销|积分|价格|discount|coupon|pricing|credits|contest|giveaway|black friday/i.test(e.featureName))return;
  var dimensions=e.updateType==='model-integration'?['integration']:competitorMatrixDimensions.filter(function(x){return x.pattern&&x.pattern.test(e.featureName+' '+(e.productArea||''))}).map(function(x){return x.id});
  add({brand:brand,name:e.featureName,dimensions:dimensions.length?dimensions:['other'],url:url,day:chinaDay(e.publisherCalendarDay),kind:'官方日志',note:'日志记录，不代表当前仍可用。'});
 });
 sources.filter(function(s){return s.type==='product-surface'&&s.role==='competitor'&&competitorMatrixBrands.includes(s.vendor)}).forEach(function(source){
  Object.values(source.entries||{}).filter(function(e){return e.claimType==='first-party-product-surface'&&e.visibleInLatestRead===true&&e.featureName&&e.lastObservedAt}).forEach(function(e){
   var url=creatorOriginalUrl(e.featureUrl||source.url);if(!url)return;
   var dimensions=competitorMatrixDimensions.filter(function(x){return x.pattern&&x.pattern.test(e.featureName)}).map(function(x){return x.id});
   add({brand:source.vendor,name:e.featureName,dimensions:dimensions.length?dimensions:['other'],url:url,day:null,reviewedOn:chinaDay(e.lastObservedAt),kind:'官网自动观察',note:'最近成功读取的公开入口，不代表发布日期或登录后的完整功能。'});
  })
 });
 (reviewed||[]).forEach(function(x){if(competitorMatrixBrands.includes(x.brand)&&creatorOriginalUrl(x.url))add(Object.assign({},x,{kind:'官网观察',day:null}))});
 return rows.sort(function(a,b){return String(b.day||'').localeCompare(String(a.day||''))||a.name.localeCompare(b.name)});
}
function competitorMatrixPage(tabs){
 var app=state.appUpdates||{},rows=competitorMatrixRows(app,Date.now(),competitorMatrixReviewed),sources=app.sources||[];
 var body=competitorMatrixDimensions.map(function(dim){
  return '<tr><th scope="row">'+esc(dim.name)+'</th>'+competitorMatrixBrands.map(function(brand){
   var cell=rows.filter(function(x){return x.brand===brand&&x.dimensions.includes(dim.id)&&matches([brand,dim.name,x.name,x.note].join(' '))});
   function entry(x){return creatorLink(x.url,x.name)+'<small>'+esc(x.kind+(x.day?' · '+x.day:' · 核查 '+x.reviewedOn))+'</small>'}
   return '<td>'+(cell.length?cell.slice(0,2).map(entry).join('')+(cell.length>2?'<details><summary>另 '+(cell.length-2)+' 条</summary>'+cell.slice(2).map(entry).join('')+'</details>':''):'<small>当前未观察</small>')+'</td>'
  }).join('')+'</tr>'
 }).join('');
 var health=competitorMatrixBrands.map(function(brand){var ss=sources.filter(function(s){return s.vendor===brand&&s.role==='competitor'});return '<p>'+esc(brand+' · '+(ss.length?ss.map(function(s){return s.type==='navigation-only'?'官网入口 · 功能日志未读':s.lastSuccessAt?'最近成功 '+overviewTime(s.lastSuccessAt):'尚无成功采集'}).join(' / '):'暂无已配置官方日志'))+'</p>'}).join('');
 return pageHead('行业简报','从官方功能证据横向比较创作平台，发现值得进一步验证的能力。','功能矩阵 · 重点5家')+'<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div><p class="page-desc">近30天官方更新日志 + 已核查官网能力。未观察不等于不支持；官网观察不是发布日期，也不是实际功能测试。功能形态归类仅供研究。</p><div class="competitor-matrix-wrap" tabindex="0" role="region" aria-label="竞品功能矩阵，可横向滚动"><table class="competitor-matrix"><thead><tr><th scope="col">能力维度</th>'+competitorMatrixBrands.map(function(x){return '<th scope="col">'+esc(x)+'</th>'}).join('')+'</tr></thead><tbody>'+body+'</tbody></table></div><details class="source-health"><summary>来源覆盖与局限</summary>'+health+'<p>其他关注平台仍在竞品动态定向发现中；尚未进入本矩阵，不代表不关注。</p></details>'
}
