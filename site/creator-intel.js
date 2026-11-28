var creatorBrands={competitors:['Higgsfield','LibTV','TapNow','OiiOii','Flova','ShotLab','Updream','Renoise'],vendors:['小云雀','Pippit','Gemini','即梦','Dreamina','可灵','Kling','Seedance','Seedream','Sand.ai','MiniMax','海螺','Vidu','PixVerse','ElevenLabs','ElevenCreative','Midjourney','Niji','OpenAI','Google','Suno']};
var priorityCompetitors=['Higgsfield','LibTV','TapNow','OiiOii','Flova'],firstPartyProducts=['小云雀','Pippit','即梦','Dreamina','Gemini'];
var trackingBrands=creatorBrands.competitors.concat(firstPartyProducts);
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
  var brand=source.vendor||'Higgsfield',all=(app.events||[]).filter(function(e){return productDatedEvent(e)&&e.sourceId===source.id&&e.featureName}),latest=all.map(function(e){return e.publisherCalendarDay}).sort().pop(),rows=all.filter(function(e){return withinDays(e.publisherCalendarDay,7,new Date(now))&&matches([e.featureName,e.productArea].join(' '))}).sort(function(a,b){return String(b.publisherCalendarDay).localeCompare(a.publisherCalendarDay)});
  var stateLabel=source.skipReason==='aggregate-covered-sample'?'聚合样本覆盖 · 暂停重复探测':source.skipReason==='awaiting-aggregate'?'优先等待双源查询':source.status==='navigation-only'?'入口已确认 · 正文未读':source.lastSuccessAt?'最近读取 '+overviewTime(source.lastSuccessAt):'待自动读取';
  return '<section class="briefing-digest-section"><div class="section-head"><h2>'+esc(brand)+' · 官方功能与模型接入</h2><span class="head-meta">'+esc(stateLabel)+'</span></div><div class="briefing-original-links">'+creatorLink(source.url,'官方更新入口')+(source.links||[]).map(function(l){return creatorLink(l.url,l.kind)}).join('')+'</div>'+(latest?'<p class="page-desc">最近公开日志 '+esc(latest)+(withinDays(latest,30,new Date(now))?'':' · 超过30天，不能代表近期无更新')+'</p>':'')+(source.error?'<p class="overview-notice">'+esc(source.error)+'</p>':'')+'<div class="briefing-list">'+(rows.map(function(e){var kind={'model-integration':'模型接入','product-feature':'新功能','product-release':'产品发布','product-improvement':'能力改进'}[e.updateType]||'产品更新';return '<article class="briefing-card"><div class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(e.publisherCalendarDay+' · '+kind+' · '+(e.productArea||'官方更新日志'))+'</span><strong>'+esc(e.featureName)+'</strong></span><div class="briefing-original-links">'+creatorLink(e.sourceUrl,'官方记录')+'</div></div></article>'}).join('')||empty('暂无近7天自动读取的官方条目；查看官方入口或聚合报道。'))+'</div></section>'
 });
 return cards.join('')
}

function coreCompetitorChannelCoverage(app,social){
 app=app||{};social=social||{};
 return priorityCompetitors.map(function(brand){
  var record=(social.brands||[]).find(function(b){return String(b.name||'').replace(/\s+AI$/i,'').toLowerCase()===brand.toLowerCase()}),accounts=(record&&record.accounts||[]).filter(function(a){return a.status==='verified'&&creatorOriginalUrl(a.url)});
  var posts=(social.posts||[]).filter(function(p){return record&&p.brandId===record.id&&p.verificationStatus==='verified-direct-link'&&creatorOriginalUrl(p.url)});
  var sources=(app.sources||[]).filter(function(s){return s.vendor===brand&&s.role==='competitor'});
  return {brand:brand,accounts:accounts,postCount:new Set(posts.map(function(p){return newsUrlKey(p.url)})).size,sources:sources,officialReads:sources.filter(function(s){return s.type!=='navigation-only'&&s.lastSuccessAt}).length};
 });
}
function coreCompetitorChannelMarkup(app,social,term){
 var rows=coreCompetitorChannelCoverage(app,social).filter(function(r){return !term||r.brand===term});
 return '<details class="source-health"><summary>五大竞品 · 多渠道真实覆盖</summary><p class="page-desc">官方账号、原帖快照、可读官网、开发生态证据分别核算。零原帖不代表没有更新；账号登记不计原帖成功。微信公号与视频号仅在取得原文时计证据。</p>'+rows.map(function(r){return '<section class="briefing-digest-section"><div class="section-head"><h3>'+esc(r.brand)+'</h3><span class="head-meta">'+r.accounts.length+' 个已登记账号 · '+r.postCount+' 条已核验原帖 · '+r.officialReads+' 个有成功记录的官方源</span></div><div class="briefing-original-links">'+r.accounts.map(function(a){return creatorLink(a.url,a.platform)}).join('')+'</div><div class="briefing-original-links">'+r.sources.map(function(s){return creatorLink(s.url,s.name||s.id)}).join('')+'</div></section>'}).join('')+'</details>';
}
function creatorCoverageMarkup(mode,term){
 var app=state.appUpdates||{},cov=app.platformCoverage||{},queries=(app.targetedDiscovery||{}).queries||[],platforms=cov.platforms||[];
 if(!platforms.length&&!queries.length)return '';
 var status={'original-observed':'已发现原文','hot-mention-only':'仅热点来源提及','not-observed':'样本未覆盖'};
 var monitored=platforms.filter(function(x){return x.role==='social'}),hit=monitored.filter(function(x){return x.originalCount>0}).length;
 var platformRows=platforms.map(function(x){return '<div class="overview-row"><span><strong>'+esc(x.label)+'</strong> · '+esc(status[x.status]||'未测量')+'</span><span class="overview-row-meta">'+esc((x.originalCount||0)+' 条原文'+(x.providers&&x.providers.length?' · '+x.providers.join(' / '):'')+(x.hotSourceMentionCount?' · 热点来源提及 '+x.hotSourceMentionCount:'')+(x.role==='reference'?' · 资料参考':x.role==='discovery'?' · 发现入口':''))+'</span></div>'}).join('');
 var relevant=queries.filter(function(q){return term?q.label===term:(creatorBrands[mode]||[]).includes(q.label)});
 var queryRows=relevant.map(function(q){var c=q.counts||{},actual=q.lastAttemptAt?'最近查询 '+overviewTime(q.lastAttemptAt):'尚未执行',provider=q.provider||'AIPick';return '<div class="overview-row"><span><strong>'+esc(q.label)+'</strong> · '+esc(provider)+'</span><span class="overview-row-meta">'+esc(actual+' · '+(q.status==='unavailable'?'读取失败':Number.isInteger(c.items)?c.items+' 条检索结果'+(Number.isInteger(c.selectedProductFeatures)?' · 功能 '+c.selectedProductFeatures+' / 接入 '+c.selectedModelIntegrations:''):'未测量'))+'</span></div>'}).join('');
 return (mode==='competitors'?coreCompetitorChannelMarkup(app,state.social,term):'')+'<details class="source-health"><summary>实际信源覆盖'+(platforms.length?' · 社媒 '+hit+'/'+monitored.length:'')+'</summary><p class="page-desc">当前七天精选快照的独立原文链接；未观察不代表平台不可访问。热点来源提及不算原文覆盖。定向查询结果数量不是已确认事件数。</p><div class="briefing-original-links">'+(cov.sources||[]).map(function(s){return '<span class="head-meta">'+esc(s.provider+' '+(s.fetchedAt?overviewTime(s.fetchedAt):'未读取')+(s.stale?' · 快照较旧':''))+'</span>'}).join('')+'</div>'+platformRows+(queryRows?'<h3>关注厂商查询记录</h3>'+queryRows:'')+'</details>'
}
// Vendor-first reading projection: no new data store or inferred publication.
var competitorSites={Higgsfield:'https://higgsfield.ai/',LibTV:'https://www.liblib.tv/',TapNow:'https://tapnow.ai/',OiiOii:'https://www.oiioii.ai/zh/',Flova:'https://www.flova.ai/',ShotLab:'https://aigc.xinpianchang.com/',Updream:'https://www.updream.cn/',Renoise:'https://renoise.tv/'};
function productDatedEvent(e){return !!e&&['first-party-product-changelog','first-party-plugin-release','first-party-developer-change'].includes(e.claimType)}
function productEventProof(e){return e.claimType==='first-party-developer-change'?'官方开发生态合并':e.claimType==='first-party-plugin-release'?'官方插件发布提交':'官方日志'}
function competitorEventType(title){
 var v=String(title||'');
 if(/融资|投资轮|募资|funding|raises?|series [a-f]\b/i.test(v))return '融资 / 公司动态';
 if(/宣传片|官方演示|宣传|预告|showcase|trailer|demo/i.test(v))return '宣发 / 演示';
 if(/接入|上架|独家首发|模型上新|model integration/i.test(v))return '模型接入';
 if(/发布|上线|推出|launch|introduc/i.test(v))return '产品 / 功能';
 return '相关报道';
}
function competitorEvidenceRank(row){
 return ['官方日志','官方插件发布提交','官方开发生态合并'].includes(row.proof)?0:row.proof==='官方社媒原帖'?1:row.proof==='官方文档所述日期'||row.proof==='官方文章'?2:/官网/.test(row.proof)?3:4;
}
function competitorResponseStatus(rows){
 var official=rows.filter(function(r){return r.kind==='模型接入'&&r.proof==='官方日志'}).sort(function(a,b){return a.day.localeCompare(b.day)})[0];
 if(official)return {label:'官方接入',day:official.day,level:'confirmed'};
 var promo=rows.find(function(r){return r.kind.indexOf('宣发')>=0&&competitorEvidenceRank(r)<4});
 if(promo)return {label:'官方宣发记录',day:promo.day,level:'observed'};
 var observed=rows.find(function(r){return competitorEvidenceRank(r)<4});
 if(observed)return {label:'官方相关记录',day:observed.day,level:'observed'};
 if(rows.length)return {label:'相关报道',day:rows[0].day,level:'reported'};
 return {label:'暂无记录',day:'',level:'unknown'};
}
function competitorBriefRows(app,reports,social,now){
 app=app||{};social=social||{};var rows=[],seen=new Map(),sources=app.sources||[];
 function add(brand,title,day,kind,url,proof,meta){
  url=creatorOriginalUrl(url);if(!trackingBrands.includes(brand)||!title||!url||!withinDays(day,30,new Date(now)))return;
  if(/黑五|黑色星期五|优惠券|限时促销|discount|coupon|black friday|积分充值/i.test(title))return;
  // The same dated original with the same title is one reading item.
  // Distinct claims, dates and model versions stay separate.
  var row=Object.assign({brand:brand,title:title,day:chinaDay(day),kind:kind,url:url,proof:proof,alternates:[]},meta||{});
  var key=[brand,newsUrlKey(url),title.normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase(),row.day].join('|'),old=seen.get(key);
  if(old){
   if(competitorEvidenceRank(row)<competitorEvidenceRank(old)){row.alternates=old.alternates.concat([{proof:old.proof,url:old.url}]);rows[rows.indexOf(old)]=row;seen.set(key,row)}
   else if(old.proof!==proof&&!old.alternates.some(function(x){return x.proof===proof&&x.url===url}))old.alternates.push({proof:proof,url:url});
   return;
  }
  seen.set(key,row);rows.push(row);
 }
 (app.events||[]).forEach(function(e){
  var s=sources.find(function(x){return x.id===e.sourceId}),brand=s&&(s.vendor==='字节跳动'&&/^jimeng/.test(s.id)?'即梦':s.vendor||(s.id==='higgsfield-changelog'?'Higgsfield':''));
  if(productDatedEvent(e)){
   var kinds={'model-integration':'模型接入','product-feature':'新功能','product-release':'产品发布','product-improvement':'能力改进','product-update':'功能更新'};
   add(brand,e.featureName,e.publisherCalendarDay,kinds[e.updateType]||'官方产品更新',e.sourceUrl,productEventProof(e),{modelName:e.updateType==='model-integration'?e.featureName:''});
  }else if(e.claimType==='first-party-visible-label'&&e.kind==='new-visible-label'&&firstPartyProducts.includes(brand)){
   add(brand,e.modelName,e.observedAt,'模型可见',e.sourceUrl,'官网入口变化 · 非发布日期',{modelName:e.modelName});
  }else if(e.claimType==='first-party-product-surface'&&e.kind==='new-product-surface'){
   if(e.surfaceStage!=='catalog-listed')add(brand,e.featureName,e.observedAt,competitorEventType(e.featureName),e.featureUrl||e.sourceUrl,'官网入口变化 · 非发布日期');
  }
 });
 // Public model labels from a migration/baseline are not a product launch.
 // They are useful availability observations only when an exact active watch
 // matches an explicit model label or recent recommendation.
 var watches=((app.targetedDiscovery||{}).queries||[]).filter(function(q){return q.modelWatch&&withinDays(q.publisherCalendarDay,7,new Date(now))});
 sources.forEach(function(s){
  var brand=s.vendor==='字节跳动'&&/^jimeng/.test(s.id)?'即梦':s.vendor;
  if(!trackingBrands.includes(brand))return;
  Object.values(s.entries||{}).forEach(function(e){
   if(!e.visibleInLatestRead||!e.lastObservedAt||e.surfaceStage==='coming-soon')return;
   var label=e.modelName||e.featureName||'';
   if(e.claimType!=='first-party-visible-label'&&!(e.claimType==='first-party-product-surface'&&(e.surfaceStage==='catalog-listed'||/独家首发|模型上新|模型接入|模型上线/i.test(label))))return;
   watches.forEach(function(q){
    var name=String(q.term||'');if(!name)return;
    var pattern=competitorModelPattern(name);
    if(!pattern.test(label))return;
    add(brand,label,e.firstObservedAt||e.lastObservedAt,e.surfaceStage==='catalog-listed'?'模型目录展示':'模型可见 / 官网推荐',e.featureUrl||s.url,'官网可见 · 非发布日期',{modelName:name});
   });
  });
 });
 (app.reviewedObservations||[]).forEach(function(e){
  if(reviewedProductHistoryClaim(e))return;
  var s=sources.find(function(x){return x.id===e.sourceId}),brand=e.brand||(s&&s.vendor==='字节跳动'&&/^jimeng/.test(s.id)?'即梦':s&&s.vendor);
  if(!brand)return;
  add(brand,e.title,e.releaseDate||e.observedOn,e.kind,e.sourceUrl,e.releaseDate?(e.observationMethod==='官方文章发布日期'?'官方文章':'官方文档所述日期'):'官网人工观察 · 非发布日期',{modelName:e.modelName||'',note:e.note||''});
 });
 (reports||[]).forEach(function(r){
  var x=r.item||{},l=x.links||{};
  trackingBrands.filter(function(brand){return creatorSubject(x.title,brand)||creatorIntegrationTarget(x.title,brand)}).forEach(function(brand){
   add(brand,x.title,x.publishedAt||x.latestAt||x.discoveredAt,competitorEventType(x.title),r.story?l.story:l.original,r.story?'讨论合集 · 非官方确认':x.publishedAt?'相关报道 · 非官方确认':'发现时间 · 非发布日期',{providers:r.providers||[]});
  });
 });
 (social.posts||[]).forEach(function(x){
  if(x.verificationStatus!=='verified-direct-link')return;
  var brand=(social.brands||[]).find(function(b){return b.id===x.brandId}),name=trackingBrands.find(function(b){return b.toLowerCase()===String(brand&&brand.name||x.brand||'').replace(/\s+AI$/i,'').toLowerCase()});
  add(name,x.title,x.sortKey||x.publishedLabel,competitorEventType(x.type+' '+x.title),x.url,'官方社媒原帖');
 });
 return rows.sort(function(a,b){return b.day.localeCompare(a.day)||competitorEvidenceRank(a)-competitorEvidenceRank(b)||a.brand.localeCompare(b.brand)});
}
function competitorModelPattern(name){
 var core=String(name||'').trim().split(/[\s_-]+/).map(function(s){return s.replace(/[.*+?^$()|[\]\\]/g,function(c){return '\\'+c})}).join('[\\s_-]*');
 return new RegExp('(^|[^a-z0-9])'+core+'(?![a-z0-9.]|[-_][a-z0-9]|\\s+(?:pro|fast|lite|flash|mini|max|turbo|ultra|preview|plus)\\b)','i');
}
function competitorModelTrace(rows,releases,now){
 return (releases||[]).filter(function(m){return m.modelFamilyId&&m.modelVersionId&&m.verifiedAt&&m.evidenceType&&m.verificationStatus!=='pending'&&withinDays(m.publishedAt,7,new Date(now))&&creatorOriginalUrl(m.url)}).map(function(m){
  var name=String(m.modelName||''),needle=innovationModelKey(name);
  if(!needle)return null;
  var pattern=competitorModelPattern(name);
  var related=rows.filter(function(r){return withinDays(r.day,7,new Date(now))&&((r.modelName&&innovationModelKey(r.modelName)===needle)||(!r.modelName||r.modelName===r.title)&&pattern.test(r.title))&&r.kind!=='融资 / 公司动态'});
  var brands=priorityCompetitors.concat(trackingBrands.filter(function(b){return !priorityCompetitors.includes(b)})).filter(function(brand){return related.some(function(r){return r.brand===brand})});
  if(!brands.length)return null;
  return {model:m,brands:brands,rows:related};
 }).filter(Boolean).sort(function(a,b){return b.brands.length-a.brands.length||String(b.model.publishedAt).localeCompare(String(a.model.publishedAt))});
}
// Compact Chinese labels for known first-party changelog titles. Original evidence stays intact.
function productReadingTitle(title){
 var v=String(title||''),map={'Seedream 5.5 now supports 4K':'Seedream 5.5 支持 4K 输出','Video and timeline audio translation':'视频与时间线音频翻译','Submit generation and upscale tasks in parallel':'并行提交生成与超分任务','Audio processing and track separation':'音频处理与音轨分离'};
 return map[v]||v;
}
function competitorRecentBuckets(rows,now){
 var primary=[],followup=[],review=[];
 rows.forEach(function(r){if(withinDays(r.day,3,new Date(now)))primary.push(r);else if(withinDays(r.day,7,new Date(now)))followup.push(r);else if(withinDays(r.day,30,new Date(now)))review.push(r)});
 return {primary:primary,followup:followup,review:review};
}
function competitorBriefPage(head,toolbar,reports,now,term,diagnostics){
 var app=state.appUpdates||{},all=competitorBriefRows(app,reports,state.social||{},now),brands=term?[term]:creatorBrands.competitors;
 var filtered=all.filter(function(r){return brands.includes(r.brand)&&matches([r.brand,r.title,productReadingTitle(r.title),r.kind,r.note].join(' '))});
 function event(r){return '<div class="vendor-event"><time>'+esc(r.day.slice(5))+'</time><div class="vendor-event-main"><strong>'+esc(productReadingTitle(r.title))+'</strong><small>'+esc(r.kind+' · '+r.proof)+'</small>'+(r.note?'<details class="vendor-note"><summary>说明</summary>'+esc(r.note)+'</details>':'')+((r.alternates||[]).length?'<details class="vendor-note"><summary>补充证据</summary>'+r.alternates.map(function(a){return creatorLink(a.url,a.proof)}).join(' · ')+'</details>':'')+'</div>'+creatorLink(r.url,'原文')+'</div>'}
 function recentFor(brand){return filtered.filter(function(r){return r.brand===brand&&withinDays(r.day,7,new Date(now))})}
 var traceRows=competitorModelTrace(term?filtered:all.filter(function(r){return matches([r.brand,r.title,r.kind,r.note].join(' '))}),state.modelReleases||[],now);
 // A watch remains visible even when no original evidence has arrived yet.
 // Targeted queries publish counts only, never claims of actual integration.
 if(!term){
  var watches=((app.targetedDiscovery||{}).queries||[]).filter(function(q){return q.modelWatch&&withinDays(q.publisherCalendarDay,7,new Date(now))});
  watches.forEach(function(q){
   var model=(state.modelReleases||[]).find(function(m){return m.modelFamilyId===q.modelFamilyId&&m.modelVersionId===q.modelVersionId&&m.publishedAt===q.publisherCalendarDay});
   if(!model||!matches([model.modelName,model.vendor].join(' ')))return;
   var trace=traceRows.find(function(x){return x.model.modelFamilyId===q.modelFamilyId&&x.model.modelVersionId===q.modelVersionId});
   if(!trace){trace={model:model,brands:[],rows:[]};traceRows.push(trace)}
   (trace.watchQueries||(trace.watchQueries=[])).push(q);
  });
 }
 var traces=traceRows.map(function(x){return '<article class="briefing-card vendor-model"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(x.model.publishedAt+' · '+x.model.vendor+' · '+x.brands.length+' 家有相关证据')+'</span><strong>'+esc(x.model.modelName+' · 接入与宣发')+'</strong><span class="vendor-response">'+(x.brands.length?x.brands:[]).map(function(brand){var rs=x.rows.filter(function(r){return r.brand===brand}),status=competitorResponseStatus(rs);return '<span class="vendor-response-item"><span class="vendor-dot '+esc(status.level)+'"></span><span><strong>'+esc(brand)+'</strong><small>'+esc(status.label+(status.day?' · '+status.day.slice(5):''))+'</small></span></span>'}).join('')+'</span></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded">'+creatorLink(x.model.url,'模型官方发布')+(x.watchQueries?'<p class="page-desc">专项定向发现：'+esc(x.watchQueries.map(function(q){return q.provider+' · '+(q.status==='unavailable'?'最近查询未成功':q.lastSuccessAt?'已查询':q.lastAttemptAt?'查询未成功':'待查询')}).join(' / '))+'。命中数量不等于接入证据。</p>':'')+x.brands.map(function(brand){return '<h3>'+esc(brand)+'</h3>'+x.rows.filter(function(r){return r.brand===brand}).map(event).join('')}).join('')+(!term?'<p class="page-desc">重点平台尚无相关证据：'+esc(priorityCompetitors.concat(firstPartyProducts).filter(function(b){return !x.brands.includes(b)}).join('、')||'无')+'</p>':'')+'</div></details></article>'}).join('');
 var matrix=competitorMatrixRows(app,now,competitorMatrixReviewed);
 // Recent dated facts before reports on the same day; observed signals remain separate.
 var orderedBrands=brands.slice().sort(function(a,b){var ar=recentFor(a),br=recentFor(b);var pa=priorityCompetitors.indexOf(a),pb=priorityCompetitors.indexOf(b);return (pa<0?99:pa)-(pb<0?99:pb)||String(br[0]&&br[0].day||'').localeCompare(String(ar[0]&&ar[0].day||''))||Number(br.length>0)-Number(ar.length>0)||brands.indexOf(a)-brands.indexOf(b)});
 var cards=orderedBrands.map(function(brand){
  var buckets=competitorRecentBuckets(filtered.filter(function(r){return r.brand===brand}),now),recent=buckets.primary,followup=buckets.followup;
  var evidence=matrix.filter(function(r){return r.brand===brand&&!r.day}),highlights=evidence.slice(0,3).map(function(r){return creatorLink(r.url,r.name)}).join(' · ');
  return '<section class="competitor-brand-section overview-panel"><div class="section-head"><h2>'+esc(brand)+'</h2><span class="head-meta">'+recent.length+' 条近3天 / '+(recent.length+followup.length)+' 条近7天 · '+creatorLink(competitorSites[brand],'官网')+'</span></div>'+(recent.slice(0,3).map(event).join('')||'<p class="overview-empty">近3天暂无记录</p>')+(recent.length>3?'<details class="source-health vendor-more"><summary>其余 '+(recent.length-3)+' 条近3天动态</summary>'+recent.slice(3).map(event).join('')+'</details>':'')+(highlights?'<p class="vendor-highlights"><strong>现有能力</strong> '+highlights+'</p>':'')+(followup.length?'<details class="source-health vendor-more"><summary>第4–7天补缺 · '+followup.length+' 条</summary>'+followup.map(event).join('')+'</details>':'')+'</section>'
 }).join('');
 var firstParty=term?'':'<section class="briefing-digest-section"><div class="section-head"><h2>一手产品动态</h2></div><div class="vendor-grid">'+firstPartyProducts.map(function(brand){var rs=all.filter(function(r){return r.brand===brand&&withinDays(r.day,7,new Date(now))&&matches([r.brand,r.title,r.kind].join(' '))}),buckets=competitorRecentBuckets(rs,now),source=(app.sources||[]).find(function(s){return s.vendor===brand||brand==='即梦'&&s.id==='jimeng'}),url=source&&source.url||(brand==='Dreamina'?'https://dreamina.capcut.com/':'');return '<section class="overview-panel"><div class="section-head"><h2>'+esc(brand)+'</h2>'+creatorLink(url,'官网')+'</div>'+(buckets.primary.slice(0,3).map(event).join('')||'<p class="overview-empty">近3天暂无记录</p>')+(buckets.primary.length>3?'<details class="source-health"><summary>其余 '+(buckets.primary.length-3)+' 条近3天记录</summary>'+buckets.primary.slice(3).map(event).join('')+'</details>':'')+(buckets.followup.length?'<details class="source-health"><summary>第4–7天补缺 · '+buckets.followup.length+' 条</summary>'+buckets.followup.map(event).join('')+'</details>':'')+'</section>'}).join('')+'</div></section>';
 var originalCount=reports.filter(function(r){return !r.story&&creatorBrandMatch(r.item.title,'competitors',term)}).length;
 var active=brands.filter(function(b){return recentFor(b).length>0}).length,primaryActive=brands.filter(function(b){return recentFor(b).some(function(r){return withinDays(r.day,3,new Date(now))})}).length;
 return head+toolbar+'<div class="vendor-overview-summary"><span><strong>'+primaryActive+'/'+brands.length+'</strong> 家有近3天记录</span><span><strong>'+active+'/'+brands.length+'</strong> 家有近7天记录</span><span><strong>'+traceRows.length+'</strong> 个模型响应追踪</span></div>'+(traces?'<section class="briefing-digest-section"><div class="section-head"><h2>重点模型 · 各平台接入与宣发</h2></div>'+traces+'</section>':'')+'<div class="section-head"><h2>近3天优先 · 近7天厂商动态</h2><span class="head-meta">'+originalCount+' 条原文去重</span></div><div class="vendor-grid">'+cards+'</div>'+firstParty+'<p class="page-desc">近3天为重点，4–7天补缺；更早的已核实历史在厂商发展史自然沉淀。暂无记录不等于没有更新；现有能力不计作近期上新。模型响应仅统计可关联记录，不代表全部平台已接入。</p><details class="source-health"><summary>数据与信源诊断</summary>'+diagnostics+creatorCoverageMarkup('competitors',term)+'<details><summary>官方来源与历史观察</summary>'+creatorOfficialMarkup(now,term)+'</details></details>';
}
// A private refresh supplements persisted evidence; an empty or failed
// upstream read must never erase the working production snapshot.
function competitorReadItems(base,privateItems){
 return (Array.isArray(base)?base:[]).concat(Array.isArray(privateItems)?privateItems:[]);
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
 if(hot)return head+toolbar+creatorHotMarkup(from('AIHOT','items',[]),'AIHOT',stamp('AIHOT',''),now)+creatorHotMarkup(from('AIPick','items',a.hotTopics),'AIPick',stamp('AIPick',a.fetchedAt),now)+'<p class="page-desc">原榜分别展示，不将两个平台的参与者或来源数相加；报道合集包含同一事件的多篇报道。热度不等于事实核实。</p>'+creatorCoverageMarkup(mode,term);
 var rows=creatorRows([{name:'AIHOT',items:mode==='competitors'?competitorReadItems(state.aihot.items,from('AIHOT','items',[])):from('AIHOT','items',state.aihot.items)},{name:'AIPick',items:mode==='competitors'?competitorReadItems((a.items||[]).concat(a.hotTopics||[]),from('AIPick','items',[])):from('AIPick','items',(a.items||[]).concat(a.hotTopics||[]))}],now).filter(function(r){var x=r.item;return !/黑五|黑色星期五|折扣|优惠券|限时促销|black friday|discount|coupon/i.test(x.title)&&matches([x.title,x.source&&x.source.name].join(' '))&&(cases?innovationCreativeCase(x):mode==='competitors'&&!term?trackingBrands.some(function(b){return creatorSubject(x.title,b)||creatorIntegrationTarget(x.title,b)}):creatorBrandMatch(x.title,mode,term))});
 if(mode==='competitors')return competitorBriefPage(head,'<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div>'+filters+(term?'<div class="briefing-original-links"><button type="button" class="tab" data-creator-refresh '+(creatorBusy?'disabled':'')+'>'+(creatorBusy?'读取中…':'补充读取 '+esc(term)+' 最新精选')+'</button></div>':''),rows,now,term,toolbar.replace('<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div>'+filters,''));
 var body=rows.map(function(r){var x=r.item,l=x.links||{};return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc([r.story?'讨论 '+overviewDateLabel(x.latestAt):x.publishedAt?overviewDateLabel(x.publishedAt):x.discoveredAt?'发现 '+overviewDateLabel(x.discoveredAt)+' · 发布日未知':'日期待确认',aihotCategoryName(x.category),r.providers.join(' / '),x.source&&x.source.name||''].filter(Boolean).join(' · '))+'</span><strong>'+esc(x.title)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><div class="briefing-original-links">'+creatorLink(l.original,r.story?'代表帖':'原帖')+creatorLink(l.story,'报道合集')+creatorLink(l.aihot,'资讯条目')+'</div><p class="page-desc">相关报道 · 不自动确认为产品已上线或模型首发。</p></div></details></article>'}).join('');
 return head+toolbar+'<section class="briefing-digest-section"><div class="section-head"><h2>'+esc(term|| (cases?'创作线索':mode==='competitors'?'竞品相关报道':'厂商相关报道'))+'</h2><span class="head-meta">'+rows.filter(function(r){return !r.story}).length+' 条原文去重'+(rows.some(function(r){return r.story})?' · '+rows.filter(function(r){return r.story}).length+' 个事件合集':'')+'</span></div><div class="briefing-list">'+(body||empty('当前快照无匹配报道，不代表没有更新。请按厂商打开上游或在本地查询。'))+'</div></section>'+(cases?'':creatorCoverageMarkup(mode,term))
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
// Editorial category is a hint, not a creative-relevance guarantee.
// Keep actual creative experiments across categories; leave unrelated reporting
// in its original briefing. Never treat selected reports as official launches.
function innovationCreativeCase(item){
 var title=String(item&&item.title||'');
 if(!title||/折扣|积分|促销|优惠|discount|coupon|black friday/i.test(title))return false;
 var creative=/(?:视频|图像|图片|音频|音乐)(?:生成|模型|编辑)|(?:生成|制作|创作)[^。；，,]{0,32}(?:视频|图像|图片|音频|音乐)|文生图|图生图|图生视频|文生视频|图像模型|文生图模型|AI\s*(?:视频|短片|短剧|动画|漫剧|影像|电影|绘画|广告|音乐)|影视|短片|短剧|漫剧|漫画|动画|分镜|三视图|角色一致性|角色设定|角色资产|音轨|音效|配音|对白|音画同步|字体动画|动效|镜头|运镜|白模|三维作品|3D\s*(?:动画|场景|建模)|落地页|提示词.*(?:视频|图像|角色|场景)|(?:video|image|audio|music)\s+(?:generat|edit|model)|storyboard|cinemat|animation|VFX|LoRA|Blender ID pass|motion capture/i;
 if(!creative.test(title))return false;
 if(['tip','opinion'].includes(item.category))return true;
 // Creative demonstrations and explicit workflow reports may carry the
 // ai-products/ai-models category or no category at all.
 return /实测|实操|对比|盲评|拆解|制作|教程|工作流|用.+(?:生成|创作|做成|制作)|创作者|提示词|演示|开源工具|benchmark|tutorial|demo|workflow|case study/i.test(title);
}
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
  if(!productDatedEvent(x)||!x.publisherCalendarDay)return;
  var source=(app.sources||[]).find(function(s){return s.id===x.sourceId});
  if(!source||!(source.role==='competitor'||source.id==='higgsfield-changelog'))return;
  if(/discount|coupon|pricing|credits|折扣|积分|价格|促销/i.test(x.featureName||''))return;
  add('product',x.featureName,x.productArea,x.sourceUrl,x.publisherCalendarDay,source.vendor||source.name,{updateType:x.updateType});
 });
 (snapshot.batches||[]).forEach(function(batch){
  (batch.items||[]).forEach(function(x){
   if(!x||x.selected!==true||!x.publishedAt||x.links&&x.links.story||!innovationCreativeCase(x))return;
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
 return '<section class="briefing-digest-section"><div class="section-head"><h2>产品入口变化 · 观察时间</h2><span class="head-meta">'+rows.length+' 条</span></div><p class="page-desc">仅比较成功读取后的新增可见入口；首次基线不算更新，入口消失不代表下线。</p><div class="briefing-list">'+(rows.slice(0,12).map(function(r){var e=r.event;return '<article class="briefing-card"><div class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(r.brand+' · '+chinaDay(e.observedAt)+' · '+(e.surfaceStage==='coming-soon'?'官方预告 · ':'')+'首次观察，非发布日期')+'</span><strong>'+esc(e.featureName)+'</strong></span>'+creatorLink(e.featureUrl||e.sourceUrl,'官方入口')+'</div></article>'}).join('')||empty('暂无已成功观察的入口变化；查看功能矩阵中的现有能力。'))+'</div></section>'
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
 return /Higgsfield|LibTV|OiiOii|TapNow|Flova|小云雀|Pippit|即梦|Dreamina|Gemini|可灵|Kling|海螺|MiniMax|Vidu|PixVerse/i.test(title);
}
function prioritizeProductNews(rows){
 return rows.slice().sort(function(a,b){return Number(isCoreProductNews(b))-Number(isCoreProductNews(a))});
}
function overviewProductNews(rows){
 // Explicit promotional headlines do not consume scarce home-page slots;
 // the full briefing remains untouched, including mixed technical reports.
 return prioritizeProductNews(rows.filter(function(x){return !/免费赠送|限免|限时免费|折扣|优惠券|限时促销|黑五|黑色星期五|积分充值|black friday|discount|coupon/i.test(String(x.title||''))}));
}

// Manually observed official capabilities are context, not recent releases or
// guarantees of access. Existing collector logs remain the only live input.
var competitorMatrixBrands=creatorBrands.competitors.slice();
var competitorMatrixDimensions=[
 {id:'canvas',name:'画布与工作流',pattern:/画布|canvas|workflow|工作流|node|节点/i},
 {id:'project',name:'项目与协作',pattern:/项目|协作|团队|共享|权限|project|collaborat|team workspace|sharing/i},
 {id:'asset',name:'资产与素材',pattern:/资产|素材|角色库|资源库|asset|media library|reference library/i},
 {id:'script',name:'剧本与分镜',pattern:/剧本|脚本|分镜|storyboard|screenplay|script writing/i},
 {id:'studio',name:'垂直 Studio',pattern:/Mangaka|漫画|漫剧|Short Drama Studio|Property Studio|Shorts Studio|Ads Studio|Cinema Studio|studio\b/i},
 {id:'image',name:'图像与角色',pattern:/角色|三视图|character|image (?:edit|generat)|图片(?:编辑|生成)|图像(?:编辑|生成)|reframe.*panel/i},
 {id:'video',name:'视频生成与预演',pattern:/白模|预演|3D.BOX|视频生成|video generat|camera control|运镜|镜头控制/i},
 {id:'editing',name:'剪辑与后期',pattern:/Editing Room|video edit|智能剪辑|剪辑|时间线|字幕|调色|修复|去水印|timeline|subtitle|upscal|relight/i},
 {id:'sound',name:'音频与对白',pattern:/audio|音频|音轨|对白|lip.sync|Intone|配音/i},
 {id:'agent',name:'Agent / Skills',pattern:/agent|Supercomputer|导演分身|TV Director|skills/i},
 {id:'plugin',name:'插件与开放生态',pattern:/插件|plugin|extension|MCP|SDK|\bAPI\b|开发者/i},
 {id:'delivery',name:'导出与交付',pattern:/导出|下载|交付|export|render output|download/i},
 {id:'integration',name:'模型接入',pattern:null},
 {id:'other',name:'其他产品功能',pattern:null}
];
var competitorMatrixReviewed=[
 {brand:'OiiOii',name:'画布式镜头编辑器',dimensions:['canvas','editing'],url:'https://www.oiioii.ai/zh/changelog',reviewedOn:'2026-11-28',note:'官方 v4.0 日志明确说明自由画布与单镜头重生成；日志仅标2026年2月，不当作近期上新。'},
 {brand:'TapNow',name:'Agentic Creative Canvas',dimensions:['canvas','agent'],url:'https://docs.tapnow.ai/en/docs/new-canvas/meet-the-new-canvas',reviewedOn:'2026-11-28',note:'官方画布指南；Agent 对话及画布创作。非本周上新。'},
 {brand:'TapNow',name:'画布项目管理',dimensions:['project'],url:'https://docs.tapnow.ai/zh/docs/projects/manage-canvases',reviewedOn:'2026-11-28',note:'官方项目管理指南。'},
 {brand:'Renoise',name:'Canvas · 素材、生成与视频编辑',dimensions:['canvas','asset','editing'],url:'https://renoise.ai/docs/canvas-guide',reviewedOn:'2026-11-28',note:'国际站官方文档；国内站未独立实测。'},
 {brand:'ShotLab',name:'ShotLab 创作画布 / CLI',dimensions:['canvas','plugin'],url:'https://www.xinpianchang.com/open-platform?from=navigator',reviewedOn:'2026-11-28',note:'新片场官方开放平台展示画布 CLI。'},
 {brand:'Updream',name:'画布与 3D 预演台',dimensions:['canvas','video'],url:'https://www.updream.cn/',reviewedOn:'2026-11-28',note:'官网入口；编辑器未实测。'},
 {brand:'Updream',name:'剧本、角色与分镜',dimensions:['script','image'],url:'https://www.updream.cn/',reviewedOn:'2026-11-28',note:'官网展示创作入口。'},
 {brand:'OiiOii',name:'多视角角色设计',dimensions:['image','asset'],url:'https://www.oiioii.ai/zh/features/character-design',reviewedOn:'2026-11-28',note:'官方角色功能说明。'},
 {brand:'OiiOii',name:'动画创作 Agent',dimensions:['agent','studio'],url:'https://www.oiioii.ai/zh/',reviewedOn:'2026-11-28',note:'官方产品说明。'},
 {brand:'Flova',name:'视频 Agent / 分镜与画布编辑',dimensions:['canvas','agent','script','editing'],url:'https://www.flova.ai/en/docs/introduction/understanding-flova/',reviewedOn:'2026-11-28',note:'官方创作流程文档。'},
 {brand:'Higgsfield',name:'Mangaka · 漫画工作台',dimensions:['studio','image'],url:'https://higgsfield.ai/blog/higgsfield-introduces-mangaka',reviewedOn:'2026-11-28',note:'官方介绍角色、场景、道具复用及画格编辑。'},
 {brand:'Higgsfield',name:'Canvas',dimensions:['canvas'],url:'https://higgsfield.ai/canvas',reviewedOn:'2026-11-28',note:'官网导航显示入口；未实测节点范围。'},
 {brand:'LibTV',name:'LibTV 画布',dimensions:['canvas'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官方首页展示画布入口。'},
 {brand:'LibTV',name:'LibTV 3D-BOX',dimensions:['video'],url:'https://www.liblib.tv/3d-box',reviewedOn:'2026-11-28',note:'官方说明含搭景、站位及手绘运镜；未实测镜头参数。'},
 {brand:'LibTV',name:'LibTV Agent BETA',dimensions:['agent'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官方首页展示 Beta 入口。'},
 {brand:'LibTV',name:'音频生成',dimensions:['sound'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官方首页列出能力；未实测具体音频工具。'},
 {brand:'LibTV',name:'智能剪辑',dimensions:['editing'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官方首页列出能力；未实测。'},
 {brand:'LibTV',name:'项目',dimensions:['project'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官网显示入口；未实测内部功能。'},
 {brand:'LibTV',name:'资产',dimensions:['asset'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官网显示入口；未实测内部功能。'},
 {brand:'LibTV',name:'插件',dimensions:['plugin'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官网显示入口；未实测内部功能。'},
 {brand:'LibTV',name:'视频生成',dimensions:['video'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官网显示入口；未实测内部功能。'},
 {brand:'LibTV',name:'图片生成',dimensions:['image'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官网显示入口；未实测内部功能。'},
 {brand:'LibTV',name:'剧本生成',dimensions:['script'],url:'https://www.liblib.tv/',reviewedOn:'2026-11-28',note:'官网显示入口；未实测内部功能。'}
];
function competitorMatrixRows(app,now,reviewed){
 app=app||{};var seen=new Map(),rows=[],sources=app.sources||[];
 function add(row){
  var name=String(row.name||'').normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase();
  var key=[row.brand,name,row.day?'dated':'surface',row.day||''].join('|');
  var old=seen.get(key);
  if(old){
   old.dimensions=Array.from(new Set(old.dimensions.concat(row.dimensions)));
   if(row.url!==old.url&&!old.alternates.some(function(x){return x.url===row.url}))old.alternates.push({url:row.url,kind:row.kind,day:row.day||row.reviewedOn});
   return;
  }
  row.alternates=[];seen.set(key,row);rows.push(row);
 }
 (app.events||[]).forEach(function(e){
  if(!productDatedEvent(e)||!e.featureName||!e.publisherCalendarDay||!withinDays(e.publisherCalendarDay,30,new Date(now)))return;
  var source=sources.find(function(s){return s.id===e.sourceId&&s.role==='competitor'}),brand=source&&source.vendor,url=creatorOriginalUrl(e.sourceUrl);
  if(!competitorMatrixBrands.includes(brand)||!url||/折扣|促销|积分|价格|discount|coupon|pricing|credits|contest|giveaway|black friday/i.test(e.featureName))return;
  var dimensions=e.updateType==='model-integration'?['integration']:competitorMatrixDimensions.filter(function(x){return x.pattern&&x.pattern.test(e.featureName+' '+(e.productArea||''))}).map(function(x){return x.id});
  add({brand:brand,name:e.featureName,dimensions:dimensions.length?dimensions:['other'],url:url,day:chinaDay(e.publisherCalendarDay),kind:productEventProof(e),note:e.claimType==='first-party-developer-change'?'官方功能合并记录，不代表网页上线或模型接入。':e.claimType==='first-party-plugin-release'?'官方插件版本发布记录，不代表网页功能上线日。':'日志记录，不代表当前仍可用。'});
 });
 sources.filter(function(s){return s.type==='product-surface'&&s.role==='competitor'&&competitorMatrixBrands.includes(s.vendor)}).forEach(function(source){
  Object.values(source.entries||{}).filter(function(e){return e.claimType==='first-party-product-surface'&&e.visibleInLatestRead===true&&e.featureName&&e.lastObservedAt}).forEach(function(e){
   var url=creatorOriginalUrl(e.featureUrl||source.url);if(!url||/^(独家首发|模型上新|View all presets)$/i.test(e.featureName))return;
   var dimensions=e.productArea==='官方模型目录'||/模型上新|模型接入|模型上线|已接入|独家首发/i.test(e.featureName)?['integration']:competitorMatrixDimensions.filter(function(x){return x.pattern&&x.pattern.test(e.featureName)}).map(function(x){return x.id});
   add({brand:source.vendor,name:e.featureName,dimensions:dimensions.length?dimensions:['other'],url:url,day:null,reviewedOn:chinaDay(e.lastObservedAt),kind:e.surfaceStage==='coming-soon'?'官方预告 · 未上线':'官网自动观察',note:'最近成功读取的公开入口，不代表发布日期或登录后的完整功能。'});
  })
 });
 (reviewed||[]).forEach(function(x){if(competitorMatrixBrands.includes(x.brand)&&creatorOriginalUrl(x.url))add(Object.assign({},x,{kind:'官网观察',day:null}))});
 return rows.sort(function(a,b){return String(b.day||'').localeCompare(String(a.day||''))||a.name.localeCompare(b.name)});
}
var competitorMatrixFocus='all';
function competitorMatrixPage(tabs){
 var app=state.appUpdates||{},rows=competitorMatrixRows(app,Date.now(),competitorMatrixReviewed),sources=app.sources||[],dimensions=competitorMatrixDimensions.filter(function(dim){return competitorMatrixFocus==='all'||dim.id===competitorMatrixFocus});
 var select='<label class="compact-select">能力筛选<select data-matrix-focus aria-label="筛选能力维度"><option value="all">全部能力</option>'+competitorMatrixDimensions.map(function(dim){return '<option value="'+esc(dim.id)+'" '+(competitorMatrixFocus===dim.id?'selected':'')+'>'+esc(dim.name)+'</option>'}).join('')+'</select></label>';
 var body=dimensions.map(function(dim){
  return '<tr><th scope="row">'+esc(dim.name)+'</th>'+competitorMatrixBrands.map(function(brand){
   var cell=rows.filter(function(x){return x.brand===brand&&x.dimensions.includes(dim.id)&&matches([brand,dim.name,x.name,x.note].join(' '))});
   function entry(x){return '<div class="matrix-feature">'+creatorLink(x.url,productReadingTitle(x.name))+'<small>'+esc(x.day?x.kind+' · '+x.day.slice(5):x.kind==='官方预告 · 未上线'?'官方预告 · 未上线':'官网观察 · 非上新')+'</small>'+(x.alternates.length?'<details class="matrix-evidence"><summary>补充证据 '+x.alternates.length+' 条</summary>'+x.alternates.map(function(e){return creatorLink(e.url,e.kind+' · '+(e.day||'日期未确认'))}).join('')+'</details>':'')+'</div>'}
   return '<td>'+(cell.length?cell.slice(0,2).map(entry).join('')+(cell.length>2?'<details><summary>另 '+(cell.length-2)+' 条</summary>'+cell.slice(2).map(entry).join('')+'</details>':''):'<small class="matrix-unknown" aria-label="当前未观察">—</small>')+'</td>'
  }).join('')+'</tr>'
 }).join('');
 var health=competitorMatrixBrands.map(function(brand){var ss=sources.filter(function(s){return s.vendor===brand&&s.role==='competitor'});return '<p>'+esc(brand+' · '+(ss.length?ss.map(function(s){return s.type==='navigation-only'?'官网入口 · 功能日志未读':s.lastSuccessAt?'最近成功 '+overviewTime(s.lastSuccessAt):'尚无成功采集'}).join(' / '):'暂无已配置官方日志'))+'</p>'}).join('');
 return pageHead('行业简报','从官方功能证据横向比较创作平台，发现值得进一步验证的能力。','功能矩阵 · '+competitorMatrixBrands.length+' 家')+'<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div><p class="page-desc">整个平台的近30天官方功能更新 + 已核查官网能力，不限于画布。新增产品形态无法匹配时仍保留在其他产品功能。未观察不等于不支持；官网观察不是发布日期，也不是实际功能测试。</p><div class="matrix-controls">'+select+'<span class="head-meta">— 暂无证据 · 不代表不支持</span></div><p class="matrix-scroll-hint">左右滑动比较厂商，左侧能力维度保持可见。</p><div class="competitor-matrix-wrap" tabindex="0" role="region" aria-label="竞品功能矩阵，可横向滚动"><table class="competitor-matrix"><thead><tr><th scope="col">能力维度</th>'+competitorMatrixBrands.map(function(x){return '<th scope="col">'+esc(x)+'</th>'}).join('')+'</tr></thead><tbody>'+body+'</tbody></table></div><details class="source-health"><summary>来源覆盖与局限</summary>'+health+'<p>其他关注平台仍在竞品动态定向发现中；尚未进入本矩阵，不代表不关注。</p></details>'
}

// Shared read-only history projection: no duplicate snapshot or copied release facts.
var chronicleVendorAliases={"anthropic":"anthropic","deepseek":"deepseek","elevenlabs":"elevenlabs","google":"google","google deepmind":"google","meta":"meta","meta superintelligence labs":"meta","midjourney":"midjourney","minimax":"minimax","openai":"openai","pixverse / 爱诗科技":"pixverse","suno":"suno","xai":"xai","字节跳动 seed":"bytedance","字节跳动 seed / 即梦":"bytedance","快手":"kuaishou","kling ai":"kuaishou","昆仑万维":"mureka","智谱 / z.ai":"zhipu","月之暗面 / moonshot ai":"kimi","生数科技":"shengshu","腾讯混元":"tencent","阿里巴巴":"qwen","阿里巴巴通义千问":"qwen","阿里巴巴通义万相":"qwen","alibaba cloud model studio":"qwen","sand.ai":"sandai","cursor":"cursor","anysphere":"cursor"};

var productChronicleIds={Higgsfield:'product-higgsfield',LibTV:'product-libtv',TapNow:'product-tapnow',OiiOii:'product-oiioii',Flova:'product-flova',ShotLab:'product-shotlab',Updream:'product-updream',Renoise:'product-renoise','小云雀':'product-xiaoyunque',Pippit:'product-pippit','即梦':'product-jimeng',Dreamina:'product-dreamina',Gemini:'product-gemini'};
var productChronicleCategories=[['all','全部'],['integration','模型接入'],['workflow','Agent / 工作流'],['tools','创作工具'],['delivery','协作 / 交付'],['other','其他重大功能']];
function chronicleModelTopic(family){
 return chronicleVendorAliases[String(family&&family.vendor||'').trim().toLowerCase()]||null;
}
function chronicleDay(day){
 if(typeof day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(day))return false;
 var parsed=new Date(day+'T00:00:00Z');
 return Number.isFinite(parsed.getTime())&&parsed.toISOString().slice(0,10)===day&&day<=chinaDay(Date.now());
}
function chronicleReleaseNode(family,version,topicId){
 var e=version.releaseEvidence||{},day=String(e.publishedAt||'').slice(0,10),url=creatorOriginalUrl(e.sourceUrl);
 if(!family.id||!version.id||!version.name||!e.eventId||!url||!e.verifiedAt||!chronicleDay(String(e.verifiedAt).slice(0,10))||!chronicleDay(day)||version.releaseDate&&String(version.releaseDate).slice(0,10)!==day||e.chronicleTopicId&&e.chronicleTopicId!==topicId||/pending|unverified/i.test(String(e.verificationStatus||'')))return null;
 if(e.verificationMethod==='automatic-dual-official'&&(!Array.isArray(e.corroboratingSources)||e.corroboratingSources.length<2))return null;
 return {date:day,kind:'模型发布',title:(e.modelName||version.name)+' 发布',summary:e.summary||'',url:url,sourceName:e.sourceName,verificationStatus:'已核实：模型库发布证据',verificationDate:e.verifiedAt,canonicalReleaseEventId:e.eventId,modelCategory:[e.category||family.category],modelMentions:[{modelFamilyId:family.id,modelVersionId:version.id,matchedName:e.modelName||version.name}],...(e.verificationMethod==='automatic-dual-official'?{autoCollected:true,verificationMethod:e.verificationMethod,automaticReleaseEventId:e.eventId,corroboratingSources:e.corroboratingSources}:{}),canonicalAuditId:e.chronicleAuditId||''};
}
function chronicleSameRelease(existing,node){
 if(!publishedChronicleNode(existing)||existing.date!==node.date)return false;
 if(node.canonicalAuditId&&existing.auditId===node.canonicalAuditId)return true;
 if(existing.automaticReleaseEventId===node.canonicalReleaseEventId||existing.canonicalReleaseEventId===node.canonicalReleaseEventId)return true;
 var ref=node.modelMentions[0],matchesRef=(existing.modelMentions||[]).some(function(r){return r.modelFamilyId===ref.modelFamilyId&&r.modelVersionId===ref.modelVersionId});
 return matchesRef&&newsUrlKey(existing.url)===newsUrlKey(node.url)&&!/预览|预告|测试|默认|公测|服务开放|API|preview|alpha|beta/i.test(existing.title||'');
}
function productChronicleCategory(e){
 if(e.updateType==='model-integration')return 'integration';
 var name=e.featureName+' '+(e.productArea||'');
 if(/collab|team|export|deliver|sharing|asset library|协作|交付|导出|资产库/i.test(name))return 'delivery';
 if(/agent|canvas|workflow|skill|project|quick chat|画布|工作流|智能体|项目/i.test(name))return 'workflow';
 if(/studio|video|image|audio|music|editing|camera|shot|scene|upscal|relight|generation|frame|漫画|分镜|镜头|剪辑|生成|音频/i.test(name))return 'tools';
 return 'other';
}
function productChronicleDate(e){
 if(!e)return '';
 if(productDatedEvent(e)&&chronicleDay(e.publisherCalendarDay))return e.publisherCalendarDay;
 var month=e.publisherCalendarMonth;
 return e.claimType==='first-party-product-milestone'&&e.datePrecision==='month'&&/^\d{4}-(0[1-9]|1[0-2])$/.test(month||'')&&month<=chinaDay(Date.now()).slice(0,7)?month:'';
}
function productChronicleEligible(e){
 if(!e||!productChronicleDate(e)||!e.featureName||!['model-integration','product-release','product-feature','product-improvement','product-update'].includes(e.updateType))return false;
 if(/pricing|discount|coupon|credits|giveaway|contest|black friday|promotion|trailer|showcase|demo video|tutorial|academy|bug fix|profile management|unread conversation|conversation allowance|next.message suggestions|jump between turns|predict your next message|remember project grid layout|价格|积分|优惠|促销|宣传片|宣传视频|教程|修复bug|修复漏洞/i.test(e.featureName))return false;
 return true;
}
function productChronicleModelRefs(e,models){
 if(e.updateType!=='model-integration')return [];
 var refs=[];
 (models||[]).forEach(function(f){(f.versions||[]).forEach(function(v){if(v.name&&competitorModelPattern(v.name).test(e.featureName))refs.push({modelFamilyId:f.id,modelVersionId:v.id,matchedName:v.name})})});
 return refs.length===1?refs:[];
}
function reviewedProductHistoryClaim(e){return !!e&&['corroborated-product-milestone','corroborated-product-observation'].includes(e.claimType)}
function productChronicleTopics(app,models){
 app=app||{};var sources=app.sources||[],nodes=new Map(),seen=new Set();
 (app.events||[]).forEach(function(e){
  if(!productChronicleEligible(e))return;
  var source=sources.find(function(s){return s.id===e.sourceId}),brand=source&&(source.vendor==='字节跳动'&&/^jimeng/.test(source.id)?'即梦':source.vendor);
  if(!source||!productChronicleIds[brand]||!['competitor','first-party'].includes(source.role))return;
  var url=creatorOriginalUrl(e.sourceUrl),official=creatorOriginalUrl(source.url);
  if(!url||!official||new URL(url).hostname!==new URL(official).hostname)return;
  if(e.claimType==='first-party-developer-change'&&(source.type!=='github-feature-merge'||!url.startsWith(official.replace(/\/$/,'')+'/pull/')||!/\/pull\/[1-9][0-9]*$/.test(url)||e.updateType!=='product-feature'))return;
  if(e.claimType==='first-party-plugin-release'&&(source.type!=='github-plugin-release'||!url.startsWith(official.replace(/\/$/,'')+'/commit/')||!/\/commit\/[a-f0-9]{40}$/.test(url)))return;
  var eventDay=productChronicleDate(e),key=[brand,eventDay,String(e.featureName).normalize('NFKC').trim().toLowerCase(),e.updateType].join('|');
  if(seen.has(key))return;seen.add(key);
  var kinds={'model-integration':'模型接入','product-release':'产品发布','product-feature':'新功能','product-improvement':'能力改进','product-update':'功能更新'};
  var row={date:eventDay,title:productReadingTitle(e.featureName),kind:kinds[e.updateType],url:url,summary:[e.productVersion?'版本 '+e.productVersion:'',e.productArea||'',(e.claimType==='first-party-developer-change'?'官方 Skills 功能合并日期；不代表网页功能上线或模型接入。':e.claimType==='first-party-plugin-release'?'GitHub 官方插件版本发布提交；不代表网页功能上线日。':e.datePrecision==='month'?'官方日志仅标注月份；不推断具体日期。':'官方日志日期；不代表当前仍可用。')].filter(Boolean).join(' · '),verificationStatus:'已核实：'+productEventProof(e),productCategory:productChronicleCategory(e),modelMentions:productChronicleModelRefs(e,models),sourceEventId:e.id||key};
  if(!nodes.has(brand))nodes.set(brand,[]);nodes.get(brand).push(row);
 });
 // Reviewed media milestones use the existing persisted observation lane; they
 // never count as official changelog, integration, or recent observation.
 (app.reviewedObservations||[]).forEach(function(e){
  if(!reviewedProductHistoryClaim(e))return;
  var observed=e.claimType==='corroborated-product-observation',historyDay=observed?e.historicalEvidenceDate:e.releaseDate;
  if((observed?(e.releaseDate!==null||e.observationMethod!=='媒体交叉实测 · 历史可见日期'||e.updateType==='product-release'):e.observationMethod!=='媒体交叉报道 · 原始官方发布页未取得')||!chronicleDay(historyDay)||!chronicleDay(e.observedOn)||e.observedOn<historyDay||!e.id||!e.title||!e.featureName||!e.note||!['product-release','product-feature','product-improvement','product-update'].includes(e.updateType))return;
  var source=sources.find(function(s){return s.id===e.sourceId&&s.vendor===e.brand&&s.role==='competitor'}),url=creatorOriginalUrl(e.sourceUrl),proof=creatorOriginalUrl(e.verificationUrl);
  if(!source||!productChronicleIds[e.brand]||!url||!proof||new URL(url).hostname.replace(/^www\.|^m\./,'')===new URL(proof).hostname.replace(/^www\.|^m\./,''))return;
  if(!productChronicleEligible(Object.assign({},e,{claimType:'first-party-product-changelog',publisherCalendarDay:historyDay})))return;
  var rows=nodes.get(e.brand)||[],key=[e.brand,historyDay,String(e.featureName).normalize('NFKC').trim().toLowerCase(),e.updateType].join('|');
  if(seen.has(key)||rows.some(function(r){return r.date===historyDay&&r.title===e.title}))return;
  seen.add(key);
  rows.push({date:historyDay,title:e.title,kind:observed?'截至该日已实测':e.kind||'产品发布',url:url,verificationUrl:proof,summary:e.note,verificationStatus:observed?'已核实：交叉实测 · 非首发日期':'已核实：媒体交叉报道（非官方日志）',verificationDate:e.observedOn,productCategory:productChronicleCategory(e),sourceEventId:e.id,reviewedProductHistory:true,historicalObservation:observed});
  nodes.set(e.brand,rows);
 });
 return trackingBrands.map(function(brand){
  var own=sources.filter(function(s){return (s.vendor===brand||brand==='即梦'&&s.vendor==='字节跳动'&&/^jimeng/.test(s.id))&&creatorOriginalUrl(s.url)}),url=(own.find(function(s){return /changelog/.test(s.type||'')})||own[0]||{}).url||competitorSites[brand]||'';
  return {id:productChronicleIds[brand],name:brand,group:'创作平台',description:'面向 Renoise 产品设计研究的模型接入、创作工具与工作流演进。仅展示有明确官方日期或经过交叉核对的重大历史节点；未收录不代表没有更新。',topicUrl:url,milestones:nodes.get(brand)||[],productBrand:brand};
 });
}
function chronicleTopics(raw,models,app){
 var topics=(raw||[]).filter(function(t){return t.group==='公司与模型'}).map(function(t){return Object.assign({},t,{milestones:(t.milestones||[]).slice()})}),byId=new Map(topics.map(function(t){return [t.id,t]}));
 (models||[]).forEach(function(f){
  var id=chronicleModelTopic(f),topic=byId.get(id);if(!topic)return;
  (f.versions||[]).forEach(function(v){
   var node=chronicleReleaseNode(f,v,id);
   if(!node)return;
   var at=topic.milestones.findIndex(function(x){return chronicleSameRelease(x,node)});
   if(at<0){topic.milestones.push(node);return}
   var existing=topic.milestones[at],refs=(existing.modelMentions||[]).slice();
   node.modelMentions.forEach(function(ref){if(!refs.some(function(r){return r.modelFamilyId===ref.modelFamilyId&&r.modelVersionId===ref.modelVersionId}))refs.push(ref)});
   topic.milestones[at]=Object.assign({},existing,{modelMentions:refs});
  });
 });
 return topics.concat(productChronicleTopics(app,models));
}
function currentChronicleTopics(){return chronicleTopics(state.topics,state.models,state.appUpdates);}
