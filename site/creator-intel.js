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
function innovationOpportunityRows(snapshot,now){
 var signals=[],seen=new Set(),dateNow=new Date(now),app=snapshot.app||{},repos=snapshot.repos||{};
 function add(type,title,detail,url,day,origin){
  var link=creatorOriginalUrl(url);
  if(!title||!link||!day||!withinDays(day,7,dateNow))return;
  var key=[type,newsUrlKey(link),String(title).trim().toLowerCase()].join('|');
  if(seen.has(key))return;seen.add(key);
  signals.push({type:type,title:String(title),detail:String(detail||''),url:link,day:chinaDay(day),origin:String(origin||'')});
 }
 (snapshot.releases||[]).forEach(function(x){
  if(!x||!x.modelFamilyId||!x.modelVersionId||!x.verifiedAt||!x.evidenceType||releaseCategoryOrder(x.category)>=99||x.verificationStatus==='pending')return;
  add('model',x.modelName,x.summary,x.url,x.publishedAt,x.vendor);
 });
 (app.events||[]).forEach(function(x){
  if(!x||x.claimType!=='first-party-product-changelog'||!x.publisherCalendarDay)return;
  var source=(app.sources||[]).find(function(s){return s.id===x.sourceId});
  if(!source||!(source.role==='competitor'||source.id==='higgsfield-changelog'))return;
  if(/discount|coupon|pricing|credits|折扣|积分|价格|促销/i.test(x.featureName||''))return;
  add('product',x.featureName,x.productArea,x.sourceUrl,x.publisherCalendarDay,source.vendor||source.name);
 });
 (snapshot.batches||[]).forEach(function(batch){
  (batch.items||[]).forEach(function(x){
   if(!x||x.selected!==true||!x.publishedAt||!['tip','opinion'].includes(x.category)||x.links&&x.links.story)return;
   if(/折扣|积分|促销|优惠|discount|coupon|black friday/i.test(x.title||''))return;
   add('case',x.title,'',x.links&&x.links.original,x.publishedAt,batch.name);
  })
 });
 var typeOrder={model:0,product:1,case:2};
 return innovationThemes.map(function(theme){
  var found=signals.filter(function(s){return theme.pattern.test(s.title+' '+s.detail)}).sort(function(a,b){return b.day.localeCompare(a.day)||typeOrder[a.type]-typeOrder[b.type]});
  // Reviewed repositories are reference context only, never a recent product claim.
  var references=[],repoSeen=new Set();
  function repoRef(x){
   if(!x||x.archived===true||!x.research||!['readme-reviewed','metadata-reviewed'].includes(x.research.review))return;
   var link=creatorOriginalUrl(x.url),u;try{u=new URL(link)}catch(e){return}
   if(u.hostname!=='github.com'||u.pathname.replace(/\/$/,'').toLowerCase()!=='/'+String(x.repo||'').toLowerCase()||repoSeen.has(x.repo.toLowerCase()))return;
   if(!theme.pattern.test([x.name,x.description,x.research.idea].join(' ')))return;
   repoSeen.add(x.repo.toLowerCase());references.push({title:x.name||x.repo,url:link,review:x.research.review,caution:x.research.caution||''});
  }
  (repos.items||[]).forEach(repoRef);
  var shown=[],counts={};
  found.forEach(function(s){counts[s.type]=(counts[s.type]||0)+1;if(counts[s.type]<=2)shown.push(s)});
  return {id:theme.id,title:theme.title,form:theme.form,pain:theme.pain,idea:theme.idea,test:theme.test,signals:shown,signalCount:found.length,references:references.slice(0,3),latest:found[0]&&found[0].day||'',types:Object.keys(counts).length};
 }).filter(function(row){return row.signalCount>0}).sort(function(a,b){return b.latest.localeCompare(a.latest)||b.types-a.types||a.id.localeCompare(b.id)});
}
function innovationPage(tabs){
 var rows=innovationOpportunityRows({releases:state.modelReleases,app:state.appUpdates,repos:state.repoRadar,batches:[{name:'AIHOT',items:state.aihot.items},{name:'AIPick',items:(state.aipick||{}).items}]},Date.now());
 var filtered=rows.filter(function(row){return matches([row.title,row.idea,row.form].concat(row.signals.map(function(s){return s.title+' '+s.origin})).join(' '))});
 var labels={model:'已核实模型发布',product:'官方产品日志',case:'创作者精选线索'};
 var body=filtered.map(function(row){
  var evidence=row.signals.map(function(s){return '<div class="overview-row"><span><span class="overview-row-meta">'+esc(labels[s.type]+' · '+s.day+' · '+s.origin)+'</span><br><strong>'+esc(s.title)+'</strong></span><span>'+creatorLink(s.url,'原始证据')+'</span></div>'}).join('');
  var refs=row.references.map(function(x){return '<div class="overview-row"><span><strong>'+esc(x.title)+'</strong> · '+esc(x.review==='readme-reviewed'?'README 已阅读':'仅元数据核查')+'<br><span class="overview-row-meta">'+esc(x.caution)+'</span></span>'+creatorLink(x.url,'仓库')+'</div>'}).join('');
  return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(row.latest+' · '+row.form+' · 产品机会假设')+'</span><strong>'+esc(row.title)+'</strong><span>'+esc(row.idea)+'</span></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><p><strong>待验证的痛点：</strong>'+esc(row.pain)+'</p><p><strong>最小验证：</strong>'+esc(row.test)+'</p><h3>近七天主题信号 · '+row.signalCount+' 条（每类最多展示两条）</h3>'+evidence+'<h3>开源研究参考 · 不代表可直接采用</h3>'+(refs||'<p class="page-desc">当前快照暂无已核查的匹配仓库。</p>')+'</div></details></article>'
 }).join('');
 return pageHead('行业简报','将近期模型、竞品功能和创作者实验关联为可验证的产品机会。','创新机会 · 近7天')+'<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div><p class="page-desc">规则匹配 · 按最近信号日期排序；主题相近不代表技术已兼容或竞品采用该仓库。所有产品构想均为假设，不是发布事实，不使用模型推理 API。</p><section class="briefing-digest-section"><div class="section-head"><h2>值得原型验证</h2><span class="head-meta">'+filtered.length+' 个方向</span></div><div class="briefing-list">'+(body||empty('当前七天快照暂无符合规则的主题信号；不代表没有创新机会。'))+'</div></section>'
}
