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
// An explicit brand mention in a creator review is a lead, not launch evidence.
function creatorLaunchSignal(title,brand){
 var t=String(title||''),b=String(brand||'');if(!b||/折扣|优惠|黑五|促销|赠送|抽奖|discount|coupon|black friday|giveaway/i.test(t))return false;
 var pos=t.toLowerCase().indexOf(b.toLowerCase());
 while(pos>=0){if(!/[A-Za-z0-9]$/.test(t.slice(0,pos))&&!/^[A-Za-z0-9]/.test(t.slice(pos+b.length))&&/实测|测评|评测|体验|上手|教程|演示|制作|案例|review|tutorial|demo|hands[- ]on|workflow/i.test(t)&&/新功能|新增|发布|上线|上新|接入|升级|首发|功能|模型|工作流|工作室|画布|feature|model|launch|workflow|studio|canvas/i.test(t))return true;pos=t.toLowerCase().indexOf(b.toLowerCase(),pos+b.length)}
 return false;
}
function creatorBrandMatch(title,mode,term){
 var brands=creatorBrands[mode]||[],active=term?[term]:brands;
 var targets=creatorBrands.competitors.filter(function(b){return creatorIntegrationTarget(title,b)});
 if(mode==='vendors'&&targets.length&&!/发布|正式推出|introduc|release/i.test(title))return false;
 return active.some(function(b){return creatorSubject(title,b)||creatorIntegrationTarget(title,b)})
}
// Upstream rankings are independent observations, not additive traffic metrics.
function creatorHotGroups(batches,now,releases){
 var groups=new Map();
 var canonical=(releases||[]).filter(function(m){return m.modelFamilyId&&m.modelVersionId&&m.verifiedAt&&m.evidenceType&&m.verificationStatus!=='pending'});
 batches.forEach(function(batch){(batch.items||[]).forEach(function(x){
  var t=Date.parse(x.latestAt||''),title=String(x.title||'').trim(),l=x.links||{},story=creatorOriginalUrl(l.story),original=creatorOriginalUrl(l.original);
  if(!title||!Number.isFinite(t)||t>now||!withinDays(x.latestAt,3,new Date(now))||!(story||original)||/黑五|黑色星期五|折扣|优惠券|促销|套餐|积分充值|black friday|discount|coupon|pricing|giveaway/i.test(title))return;
  var normalized=title.normalize('NFKC').toLowerCase().replace(/\s+/g,' ').trim();
  var models=canonical.filter(function(m){return competitorModelPattern(m.modelName).test(title)});
  var platforms=trackingBrands.filter(function(b){return creatorSubject(title,b)||creatorIntegrationTarget(title,b)});
  var stage=/预览|预告|公测|preview|beta|alpha|coming soon/i.test(title)?'preview':/接入|上架|上线|integrat|now available/i.test(title)?'availability':/发布|正式推出|release|introduc/i.test(title)?'release':'discussion';
  // Only a single verified identity and an explicit, single platform are
  // sufficient for an integration key. Launch, adoption and testing differ.
  var key='title|'+normalized;
  if(models.length===1&&platforms.length===1&&stage==='availability'&&!/实测|测评|评测|对比|review|test/i.test(title)){
   key='adoption|'+platforms[0]+'|'+models[0].modelFamilyId+'|'+models[0].modelVersionId;
  }else if(models.length===1&&stage==='release'&&!platforms.length&&!/实测|测评|评测|对比|review|test/i.test(title)){
   // Do not merge an ambiguous media title with a canonical launch.
   var vendor=String(models[0].vendor||'').toLowerCase();
   if(vendor&&normalized.includes(vendor))key='release|'+models[0].modelFamilyId+'|'+models[0].modelVersionId+'|'+models[0].publishedAt;
  }
  var group=groups.get(key);
  if(!group){group={key:key,title:title,latest:t,records:[],sourceLabels:[]};groups.set(key,group)}
  if(t>group.latest){group.latest=t;group.title=title}
  var record={provider:batch.name,rank:Number.isInteger(x.rank)?x.rank:null,sourceCount:Number.isInteger(x.sourceCount)?x.sourceCount:null,participantCount:Number.isInteger(x.participantCount)?x.participantCount:null,url:story||original};
  if(!group.records.some(function(r){return r.provider===record.provider&&newsUrlKey(r.url)===newsUrlKey(record.url)}))group.records.push(record);
  (Array.isArray(x.sourceNames)?x.sourceNames:[]).forEach(function(n){if(typeof n==='string'&&n.trim()&&!group.sourceLabels.includes(n.trim()))group.sourceLabels.push(n.trim())});
 })});
 return Array.from(groups.values()).sort(function(a,b){var providers=function(g){return new Set(g.records.map(function(r){return r.provider})).size};var best=function(g){return Math.min.apply(null,g.records.map(function(r){return r.rank||999}))};return providers(b)-providers(a)||best(a)-best(b)||b.latest-a.latest});
}
function creatorUnifiedHotMarkup(batches,now,releases){
 var rows=creatorHotGroups(batches,now,releases).filter(function(g){return matches([g.title,g.sourceLabels.join(' ')].join(' '))});
 return '<section class="briefing-digest-section"><div class="section-head"><h2>事件热点 · 跨源去重</h2><span class="head-meta">近3天 · '+rows.length+' 个观察事件</span></div><p class="page-desc">双榜共同关注优先，保留各榜排名；来源标签仅按原文名称去重，不等于独立媒体数。事件热度不证明上线或首发，未能可靠关联的报道不强行合并。</p><div class="briefing-list">'+(rows.map(function(g){var n=new Set(g.records.map(function(r){return r.provider})).size;return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc((n>1?'双榜共同关注':'单榜关注')+' · '+g.records.map(function(r){return r.provider+(r.rank?' #'+r.rank:'')}).join(' / '))+'</span><strong>'+esc(g.title)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><p>'+esc(g.sourceLabels.join('、')||'来源名单未提供')+'</p><div class="briefing-original-links">'+g.records.map(function(r){return creatorLink(r.url,r.provider+' 报道合集'+(r.sourceCount===null?'':' · 原榜 '+r.sourceCount+' 个来源'))}).join('')+'</div></div></details></article>'}).join('')||empty('当前近3天无符合条件的榜单事件；请读取上游实时榜。'))+'</div></section>';
}
// A dossier is a reading projection, not an extra release or event database.
function creatorDossiers(releases,batches,app,social,digests,now){
 var models=(releases||[]).filter(function(m){return m.modelFamilyId&&m.modelVersionId&&m.modelName&&m.verifiedAt&&['official-release','official-model-card'].includes(m.evidenceType)&&m.verificationStatus!=='pending'&&creatorOriginalUrl(m.url)&&withinDays(m.publishedAt,30,new Date(now))});
 var reports=creatorRows(batches,now),responses=competitorBriefRows(app,reports,social,now),out=[];
 models.forEach(function(m){
  var pattern=competitorModelPattern(m.modelName),byKey=new Map(),launchDay=chinaDay(m.publishedAt);
  function add(title,when,url,provider,kind,proof,extra){
   var day=chinaDay(when),link=creatorOriginalUrl(url);
   if(!title||!day||day<launchDay||!withinDays(day,7,new Date(now))||!link||!pattern.test(title)||/黑五|黑色星期五|折扣|优惠券|促销|套餐|积分充值|black friday|discount|coupon|pricing|giveaway/i.test(title))return;
   // Distinct features can share a changelog URL; only identical titles on
   // that page merge. An original social/media article has one identity.
   var k=newsUrlKey(link),isOfficial=proof==='官方日志'||proof==='官方开发生态合并'||proof==='官方插件发布提交';
   if(isOfficial)k+='|'+newsTitleKey(title);
   var row=byKey.get(k);
   if(!row){row={title:title,day:day,url:link,providers:[],kind:kind,proof:proof,extra:extra||null};byKey.set(k,row)}
   if(provider)String(provider).split(' / ').forEach(function(p){if(p&&!row.providers.includes(p))row.providers.push(p)});
   if(extra&&extra.brand&&!row.extra){row.extra=extra;row.kind=kind;row.proof=proof}
  }
  responses.forEach(function(r){if(r.kind==='融资 / 公司动态')return;add(r.title,r.day,r.url,(r.providers||[]).join(' / '),r.kind,r.proof,{brand:r.brand,modelName:r.modelName});});
  reports.forEach(function(r){var x=r.item,l=x.links||{},kind=r.story?'上游报道合集':/实测|测评|评测|对比|review|test/i.test(x.title)?'创作者反馈 / 测评':'关联报道';
   (r.providers||[]).forEach(function(provider){add(x.title,r.story?x.latestAt:x.publishedAt||x.discoveredAt,r.story?l.story:l.original,provider,kind,r.story?'专题最近进展 · 非发布日期':x.publishedAt?'报道时间 · 非上线日期':'发现时间 · 非发布日期',null)});
  });
  (digests||[]).forEach(function(d){var day=briefIssueDay(d.data);(d.data&&d.data.items||[]).forEach(function(x){var link=briefArticleLinks(x)[0];if(link)add(x.title,day,link.url,d.name,'日报关联线索','日报刊期 · 非上线日期',null)})});
  var updates=Array.from(byKey.values()).sort(function(a,b){return b.day.localeCompare(a.day)||competitorEvidenceRank(a)-competitorEvidenceRank(b)||a.title.localeCompare(b.title)});
  var latest=updates.reduce(function(day,r){return r.day>day?r.day:day},launchDay);
  if(!withinDays(latest,7,new Date(now)))return;
  // No unrelated old release resurrection just because its catalog was read.
  var currentResponses=responses.filter(function(r){return r.day>=launchDay&&withinDays(r.day,7,new Date(now))&&pattern.test(r.title)&&r.kind!=='融资 / 公司动态'});
  var brands=priorityCompetitors.concat(firstPartyProducts).map(function(brand){var rows=currentResponses.filter(function(r){return r.brand===brand});return {brand:brand,status:competitorResponseStatus(rows)}});
  out.push({id:m.modelFamilyId+'|'+m.modelVersionId,model:m,latestDay:latest,updates:updates,brands:brands});
 });
 return out.sort(function(a,b){return b.latestDay.localeCompare(a.latestDay)||b.updates.length-a.updates.length||b.model.publishedAt.localeCompare(a.model.publishedAt)});
}
// Personal reading only. Never persist upstream Story content to public snapshots.
var creatorStoryCache={},creatorStoryBusy='';
function creatorStoryTarget(link){
 try{var u=new URL(link),m=u.pathname.match(/^\/story\/([A-Za-z0-9-]{1,128})\/?$/),provider={'aihot.news':'AIHOT','aipick.news':'AIPick'}[u.hostname];
 if(!provider||!m||u.protocol!=='https:'||u.username||u.password||u.port||u.search||u.hash)return null;
 return {provider:provider,id:m[1],url:u.origin+'/story/'+m[1],api:u.origin+'/api/v1/stories/'+m[1]};
 }catch(e){return null}
}
function creatorKnownStory(link){
 var target=creatorStoryTarget(link);if(!target)return null;
 var a=state.aipick||{},priv=creatorPrivate['hot|']||{},p=priv.sources||{},rows=target.provider==='AIPick'?(a.hotTopics||[]):[];
 rows=rows.concat(p[target.provider]&&p[target.provider].data&&p[target.provider].data.items||[]);
 return rows.some(function(r){var t=creatorStoryTarget(r.links&&r.links.story);return t&&t.url===target.url})?target:null;
}
async function readCreatorStory(link,request){
 var t=creatorKnownStory(link);if(!t)throw Error('仅允许读取上游已返回的专题');
 var now=Date.now(),cached=creatorStoryCache[t.url]||{},prior=cached.entry||{};
 if(now<(creatorLiveCooldown[t.provider]||0))return Object.assign({},prior,{error:'上游冷却中，仍可打开原专题'});
 if(cached.checkedAt&&now-cached.checkedAt<(cached.ttl||600000))return prior;
 try{
  var headers={Accept:'application/json'};if(cached.etag)headers['If-None-Match']=cached.etag;
  var opts={method:'GET',mode:'cors',credentials:'omit',redirect:'error',referrerPolicy:'no-referrer',cache:'no-store',headers:headers};
  if(typeof AbortSignal!=='undefined'&&typeof AbortSignal.timeout==='function')opts.signal=AbortSignal.timeout(15000);
  var res=await (request||fetch)(t.api,opts);
  if(res.status===304&&prior.story){creatorStoryCache[t.url]=Object.assign({},cached,{checkedAt:now});return prior}
  if(!res.ok){var retry=res.headers&&res.headers.get('Retry-After'),n=Number(retry),d=Date.parse(retry||'');creatorLiveCooldown[t.provider]=now+Math.max(res.status===403?86400000:res.status===429||res.status===503?3600000:600000,Number.isFinite(n)?n*1000:0,Number.isFinite(d)?d-now:0);throw Error('HTTP '+res.status)}
  var raw=await res.text();if(raw.length>2097152)throw Error('响应过大');
  var json=JSON.parse(raw),s=json.story;if(!s||s.publicId!==t.id||typeof s.title!=='string'||!Array.isArray(s.reports)||s.reports.length>500)throw Error('专题数据格式异常');
  var seen=new Set(),rows=[];
  s.reports.forEach(function(r){if(!r||typeof r.title!=='string'||!r.title||!r.links)return;var url=creatorOriginalUrl(r.links.original),k=newsUrlKey(url);if(!k||seen.has(k)||!withinDays(r.publishedAt,7,new Date(now)))return;seen.add(k);rows.push({title:r.title.slice(0,300),url:url,day:chinaDay(r.publishedAt),source:String(r.source&&r.source.name||'').slice(0,120)})});
  rows.sort(function(a,b){return b.day.localeCompare(a.day)});
  var neighbors=[],neighborSeen=new Set();
  // Related stories are navigation pointers, not verified facts or report counts.
  [s.storyline,s.related].forEach(function(list,index){if(!Array.isArray(list))return;list.slice(0,50).forEach(function(n){var v=creatorStoryTarget(n&&n.links&&n.links.aihot);if(!v||v.provider!==t.provider||v.id!==n.publicId||v.id===t.id||neighborSeen.has(v.id)||typeof n.title!=='string')return;neighborSeen.add(v.id);neighbors.push({title:n.title.slice(0,300),url:v.url,relation:String(n.relation||'').slice(0,120),group:index===0?'事件进展':'关联专题'})})});
  var story={digest:typeof s.digest==='string'?s.digest.slice(0,2400):'',latest:typeof s.latest==='string'?s.latest.slice(0,600):'',neighbors:neighbors.slice(0,30),title:s.title,reportCount:Number.isInteger(s.reportCount)&&s.reportCount>=0?s.reportCount:null,sourceCount:Number.isInteger(s.sourceCount)&&s.sourceCount>=0?s.sourceCount:null,latestAt:s.latestAt,rows:rows.slice(0,50)};
  var cc=res.headers&&res.headers.get('Cache-Control')||'',m=cc.match(/(?:s-maxage|max-age)=(\d+)/i),ttl=Math.max(600000,m?Number(m[1])*1000:0),entry={story:story,observedAt:new Date(now).toISOString()};
  creatorStoryCache[t.url]={entry:entry,checkedAt:now,ttl:ttl,etag:res.headers&&res.headers.get('ETag')||''};
  var keys=Object.keys(creatorStoryCache).sort(function(a,b){return creatorStoryCache[a].checkedAt-creatorStoryCache[b].checkedAt});while(keys.length>12)delete creatorStoryCache[keys.shift()];
  return entry
 }catch(e){if(!(creatorLiveCooldown[t.provider]>now))creatorLiveCooldown[t.provider]=now+600000;return Object.assign({},prior,{error:String(e.message||e)})}
}
var creatorStoryDisplay={};
function creatorStoryReadMarkup(link){
 var t=creatorKnownStory(link);if(!t)return '';
 var entry=creatorStoryDisplay[t.url]||{},s=entry.story;
 return '<div class="briefing-expanded"><button type="button" class="tab" data-creator-story="'+esc(t.url)+'" '+(creatorStoryBusy?'disabled':'')+'>'+(creatorStoryBusy===t.url?'读取中…':'个人阅读 · 展开上游报道')+'</button>'+(entry.error?'<p class="page-desc">'+esc(entry.error)+' · 请打开原专题。</p>':'')+(s?'<p class="page-desc">'+esc(t.provider+' 原专题统计：'+(s.reportCount===null?'报道数未知':s.reportCount+' 篇报道')+' · '+(s.sourceCount===null?'来源数未知':s.sourceCount+' 个来源')+'；以下为近7天最多50条去重原文，时间可能为上游采集时间。')+'</p>'+(s.latest?'<p><strong>上游最新进展：</strong>'+esc(s.latest)+'</p>':'')+(s.digest?'<details class="source-health"><summary>上游事件综述 · AI 整理，需核实</summary><p>'+esc(s.digest)+'</p></details>':'')+(s.neighbors.length?'<div class="briefing-original-links">'+s.neighbors.map(function(n){return creatorLink(n.url,n.group+' · '+n.title)}).join('')+'</div>':'')+'<h4>近期报道原文</h4>'+s.rows.map(function(r){return '<div class="vendor-event"><time>'+esc(r.day.slice(5))+'</time><div class="vendor-event-main"><strong>'+esc(r.title)+'</strong><small>'+esc(r.source+' · 上游报道，非接入确认')+'</small></div>'+creatorLink(r.url,'原文')+'</div>'}).join(''):'')+'</div>'
}
async function refreshCreatorStory(link){
 var t=creatorKnownStory(link);if(!t||creatorStoryBusy)return;
 creatorStoryBusy=t.url;render();
 try{creatorStoryDisplay[t.url]=await readCreatorStory(t.url)}catch(e){creatorStoryDisplay[t.url]={error:String(e.message||e)}}
 finally{creatorStoryBusy='';var keys=Object.keys(creatorStoryDisplay);while(keys.length>12)delete creatorStoryDisplay[keys.shift()];render()}
}
function creatorDossierMarkup(dossiers,now){
 function item(r){return '<div class="vendor-event"><time>'+esc(r.day.slice(5))+'</time><div class="vendor-event-main"><strong>'+esc(productReadingTitle(r.title))+'</strong><small>'+esc(r.kind+' · '+r.proof+(r.providers.length?' · '+r.providers.join(' / '):''))+'</small></div>'+creatorLink(r.url,'原文')+'</div>'+creatorStoryReadMarkup(r.url)}
 function card(d){var m=d.model,known=d.brands.filter(function(b){return b.status.level!=='unknown'}).length,primary=d.updates.filter(function(r){return withinDays(r.day,3,new Date(now))}),followup=d.updates.filter(function(r){return !withinDays(r.day,3,new Date(now))});
  return '<article class="briefing-card vendor-model"><details '+(d.updates.some(function(r){return creatorStoryBusy===r.url||creatorStoryDisplay[r.url]})?'open':'')+'><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(m.vendor+' · 最近进展 '+d.latestDay+' · '+known+' 家有相关证据 · '+d.updates.length+' 条关联记录')+'</span><strong>'+esc(m.modelName+' · 事件专题')+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><p>'+esc(m.summary||'')+'</p><p class="page-desc">'+esc('正式发布 '+m.publishedAt+' · 不因新报道改写首发日')+'</p><div class="briefing-original-links">'+creatorLink(m.url,'模型官方发布')+'</div><h3>各平台响应</h3><div class="vendor-response">'+d.brands.map(function(b){return '<span class="vendor-response-item"><span class="vendor-dot '+esc(b.status.level)+'"></span><span><strong>'+esc(b.brand)+'</strong><small>'+esc(b.status.label+(b.status.day?' · '+b.status.day.slice(5):''))+'</small></span></span>'}).join('')+'</div><h3>最近3天进展</h3>'+(primary.map(item).join('')||empty('暂无近3天相关记录。'))+(followup.length?'<details class="source-health" '+(followup.some(function(r){return creatorStoryBusy===r.url||creatorStoryDisplay[r.url]})?'open':'')+'><summary>第4–7天进展 · '+followup.length+' 条</summary>'+followup.map(item).join('')+'</details>':'')+'<div class="briefing-original-links">'+creatorLink(m.url,'首发证据')+'</div><p class="page-desc">关联记录按已读原文和明确模型名称归拢，不等于新增发布次数；报道、演示和官网观察不是实际接入确认。上游报道全集请打开对应 Story。</p></div></details></article>'
 }
 var filtered=dossiers.filter(function(d){return matches([d.model.modelName,d.model.vendor,d.updates.map(function(r){return r.title}).join(' ')].join(' '))}),primary=filtered.filter(function(d){return withinDays(d.latestDay,3,new Date(now))}),followup=filtered.filter(function(d){return !withinDays(d.latestDay,3,new Date(now))});
 return '<section class="briefing-digest-section"><div class="section-head"><h2>事件专题</h2><span class="head-meta">近3天 '+primary.length+' 个 · 近7天 '+filtered.length+' 个</span></div><p class="page-desc">一个已核实模型版本，一个专题；按最近关联进展排序，近期有新进展的较早发布仍可回到前面。</p><div class="briefing-list">'+(primary.map(card).join('')||empty('近3天暂无可核实的模型专题进展。'))+'</div>'+(followup.length?'<details class="source-health" '+(followup.some(function(d){return d.updates.some(function(r){return creatorStoryBusy===r.url||creatorStoryDisplay[r.url]})})?'open':'')+'><summary>第4–7天专题 · '+followup.length+' 个</summary><div class="briefing-list">'+followup.map(card).join('')+'</div></details>':'')+'</section>';
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
function creatorSourceLearningMarkup(app,mode,term){
 var rows=((app||{}).propagationSources||{}).candidates||[],brands=mode==='competitors'?trackingBrands:creatorBrands.vendors;
 var relevant=rows.filter(function(r){return (r.brands||[]).some(function(b){return term?b===term:brands.includes(b)})});
 if(!relevant.length)return '';
 return '<details class="source-health"><summary>高价值传播信源候选 · 近30天</summary><p class="page-desc">按不同命名产品事件数观察，重复报道同一事件不加分。来源名称或原帖账号不代表已验证作者、官方身份或合作关系；不自动订阅。</p>'+relevant.slice(0,12).map(function(r){var proof=r.identity==='account-in-post-url'?'原帖账号路径':r.identity==='publisher-id-in-post-url'?'公众号发布主体标识':'上游归属名称 · 未核实';return '<div class="overview-row"><span><strong>'+esc(r.label)+'</strong> · '+esc(r.platform+' · '+proof)+'<small class="overview-row-meta"> · '+esc((r.brands||[]).join('、'))+'</small></span><span class="overview-row-meta">'+esc(r.distinctEvents+' 个不同事件 · '+r.lastPublishedDay)+(r.profileUrl?' · '+creatorLink(r.profileUrl,'主页'):'')+'</span></div>'}).join('')+'</details>';
}
function creatorCoverageMarkup(mode,term){
 var app=state.appUpdates||{},cov=app.platformCoverage||{},queries=(app.targetedDiscovery||{}).queries||[],platforms=cov.platforms||[];
 if(!platforms.length&&!queries.length)return '';
 var status={'original-observed':'已发现原文','hot-mention-only':'仅热点来源提及','not-observed':'样本未覆盖'};
 var monitored=platforms.filter(function(x){return x.role==='social'}),hit=monitored.filter(function(x){return x.originalCount>0}).length;
 var platformRows=platforms.map(function(x){return '<div class="overview-row"><span><strong>'+esc(x.label)+'</strong> · '+esc(status[x.status]||'未测量')+'</span><span class="overview-row-meta">'+esc((x.originalCount||0)+' 条原文'+(x.providers&&x.providers.length?' · '+x.providers.join(' / '):'')+(x.hotSourceMentionCount?' · 热点来源提及 '+x.hotSourceMentionCount:'')+(x.role==='reference'?' · 资料参考':x.role==='discovery'?' · 发现入口':''))+'</span></div>'}).join('');
 var relevant=queries.filter(function(q){return term?q.label===term:(creatorBrands[mode]||[]).includes(q.label)});
 var queryRows=relevant.map(function(q){var c=q.counts||{},actual=q.lastAttemptAt?'最近查询 '+overviewTime(q.lastAttemptAt):'尚未执行',provider=q.provider||'AIPick';return '<div class="overview-row"><span><strong>'+esc(q.label)+'</strong> · '+esc(provider)+'</span><span class="overview-row-meta">'+esc(actual+' · '+(q.status==='unavailable'?'读取失败':Number.isInteger(c.items)?c.items+' 条检索结果'+(Number.isInteger(c.selectedProductFeatures)?' · 功能 '+c.selectedProductFeatures+' / 接入 '+c.selectedModelIntegrations:'')+(Number.isInteger(c.selectedCreatorSignals)?' / 创作者线索 '+c.selectedCreatorSignals:''):'未测量'))+'</span></div>'}).join('');
 return ((mode==='competitors'||mode==='vendors')?creatorSourceLearningMarkup(app,mode,term):'')+(mode==='competitors'?coreCompetitorChannelMarkup(app,state.social,term):'')+'<details class="source-health"><summary>实际信源覆盖'+(platforms.length?' · 社媒 '+hit+'/'+monitored.length:'')+'</summary><p class="page-desc">当前七天精选快照的独立原文链接；未观察不代表平台不可访问。热点来源提及不算原文覆盖。定向查询结果数量不是已确认事件数。</p><div class="briefing-original-links">'+(cov.sources||[]).map(function(s){return '<span class="head-meta">'+esc(s.provider+' '+(s.fetchedAt?overviewTime(s.fetchedAt):'未读取')+(s.stale?' · 快照较旧':''))+'</span>'}).join('')+'</div>'+platformRows+(queryRows?'<h3>关注厂商查询记录</h3>'+queryRows:'')+'</details>'
}
// Vendor-first reading projection: no new data store or inferred publication.
var competitorSites={Higgsfield:'https://higgsfield.ai/',LibTV:'https://www.liblib.tv/',TapNow:'https://tapnow.ai/',OiiOii:'https://www.oiioii.ai/zh/',Flova:'https://www.flova.ai/',ShotLab:'https://aigc.xinpianchang.com/',Updream:'https://www.updream.cn/',Renoise:'https://renoise.tv/'};
function productDatedEvent(e){return !!e&&['first-party-product-changelog','first-party-plugin-release','first-party-developer-change'].includes(e.claimType)}
function productEventProof(e){return e.claimType==='first-party-developer-change'?'官方开发生态合并':e.claimType==='first-party-plugin-release'?'官方插件发布提交':'官方日志'}
function competitorEventType(title){
 var v=String(title||'');
 if(/融资|投资轮|募资|funding|raises?|series [a-f]\b/i.test(v))return '融资 / 公司动态';
 if(/宣传片|官方演示|宣传|预告|showcase|trailer|demo/i.test(v))return '宣发 / 演示';
 if(/实测|测评|评测|教程|案例|使用心得|上手|\breview\b|\btutorial\b|\bhands[- ]on\b/i.test(v))return '实测 / 创作案例';
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
  if(e.claimType==='external-product-report'){
   if(s&&s.role==='discovery'&&withinDays(e.reportPublishedAt,7,new Date(now)))add(e.reportedBrand,e.featureName,e.reportPublishedAt,'第三方产品线索',e.sourceUrl,'第三方报道日期 · 非上线日期',{note:'独立来源补缺，需交叉确认事件实际日期。'});
  }else if(productDatedEvent(e)){
   var kinds={'model-integration':'模型接入','product-feature':'新功能','product-release':'产品发布','product-improvement':'能力改进','product-update':'功能更新'};
   add(brand,e.featureName,e.publisherCalendarDay,kinds[e.updateType]||'官方产品更新',e.sourceUrl,productEventProof(e),{modelName:e.updateType==='model-integration'?e.featureName:''});
  }else if(e.claimType==='first-party-store-version'&&firstPartyProducts.includes(brand)){
   // Store release timestamps refer to the client version, not model or feature launch.
   if(/^\d+(?:\.\d+){1,4}$/.test(String(e.storeVersion||''))&&withinDays(e.storeVersionReleasedAt,7,new Date(now)))add(brand,'iOS 客户端 '+e.storeVersion,e.storeVersionReleasedAt,'客户端版本',e.sourceUrl,'App Store 版本日期 · 非模型发布日期',{note:'仅确认客户端版本记录，不推断功能或模型首次上线。'});
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
    if(e.surfaceStage==='catalog-listed'?innovationModelKey(label)!==innovationModelKey(name):!pattern.test(label))return;
    add(brand,label,e.firstObservedAt||e.lastObservedAt,e.surfaceStage==='catalog-listed'?'模型目录展示':'模型可见 / 官网推荐',e.featureUrl||s.url,'官网可见 · 非发布日期',{modelName:name,note:platformSpecLabel(e.platformSpecs)});
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
  trackingBrands.filter(function(brand){return creatorSubject(x.title,brand)||creatorIntegrationTarget(x.title,brand)||(!r.story&&creatorLaunchSignal(x.title,brand))}).forEach(function(brand){
   add(brand,x.title,x.publishedAt||x.latestAt||x.discoveredAt,(!r.story&&creatorLaunchSignal(x.title,brand)&&!creatorSubject(x.title,brand)&&!creatorIntegrationTarget(x.title,brand)?'创作者发现线索':competitorEventType(x.title)),r.story?l.story:l.original,r.story?'讨论合集 · 非官方确认':x.publishedAt?'相关报道 · 非官方确认':'发现时间 · 非发布日期',{providers:r.providers||[]});
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
  var related=rows.filter(function(r){return withinDays(r.day,7,new Date(now))&&(r.kind==='模型目录展示'?innovationModelKey(r.modelName||r.title)===needle:((r.modelName&&innovationModelKey(r.modelName)===needle)||(!r.modelName||r.modelName===r.title)&&pattern.test(r.title)))&&r.kind!=='融资 / 公司动态'});
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
// Reuse already-loaded daily editions as attributed discovery, never release evidence.
function curatedCreativeLeads(digests,now,term,existingUrls){
 var seen=new Map(),existing=new Set((existingUrls||[]).map(newsUrlKey).filter(Boolean));
 (digests||[]).forEach(function(d){
  var day=briefIssueDay(d.data);
  if(!withinDays(day,3,new Date(now)))return;
  (d.data&&d.data.items||[]).forEach(function(x){
   var title=String(x.title||'').trim();
   if(!title||/折扣|优惠|黑五|积分充值|免费赠送|支持计划|限免|discount|coupon|pricing|giveaway|black friday/i.test(title))return;
   var brand=trackingBrands.concat(creatorBrands.vendors).find(function(b){return creatorSubject(title,b)||creatorIntegrationTarget(title,b)});
   // Adjacent creator capabilities matter even when no canonical model category exists.
   var adjacent=/^(?:腾讯混元|混元|豆包工作)\b/i.test(title)||/^(?:腾讯混元|混元|豆包工作)/.test(title);
   if(adjacent&&!/3D|三维|建模|剪映|剪辑|视频|图像|音频|创作|PBR/i.test(title))adjacent=false;
   if(!brand&&!adjacent||term&&brand!==term&&!creatorSubject(title,term))return;
   if(!/发布|推出|上线|上新|接入|更新|升级|开放|支持|新功能|新增|launch|release|introduc|update|integrat|now available/i.test(title))return;
   var links=briefArticleLinks(x).map(function(l){return creatorOriginalUrl(l.url)}).filter(function(url){
    if(!url)return false;var u=new URL(url);
    return !(u.hostname==='daily.juya.uk'&&u.pathname.startsWith('/issues/')||u.hostname==='aihot.news'&&/^\/(?:daily|topics|leaderboard)(?:\/|$)/.test(u.pathname));
   });
   var url=links[0],key=newsUrlKey(url);
   if(!key||existing.has(key))return;
   var old=seen.get(key);
   if(old){if(!old.providers.includes(d.name))old.providers.push(d.name);return}
   seen.set(key,{title:title,day:day,url:url,providers:[d.name],brand:brand||'',proof:'日报刊期 · 非发布日期'});
  });
 });
 return Array.from(seen.values()).sort(function(a,b){return b.day.localeCompare(a.day)||a.title.localeCompare(b.title)});
}
function curatedCreativeMarkup(now,term,reports){
 var rows=curatedCreativeLeads([{name:'AIHOT 日报',data:state.aihotDaily},{name:'橘鸦 AI 早报',data:state.juyaDaily}],now,term,(reports||[]).map(function(r){return r.url||r.item&&r.item.links&&r.item.links.original}));
 rows=rows.filter(function(r){return matches([r.title,r.brand,r.providers.join(' ')].join(' '))});
 if(!rows.length)return '';
 return '<section class="briefing-digest-section"><div class="section-head"><h2>近3天 · 创作产品与模型线索</h2><span class="head-meta">'+rows.length+' 条日报补缺</span></div><p class="page-desc">复用精选日报的原始链接；日期为刊期，不代表模型发布或平台接入日期。未核实线索不写入正式模型库。</p><div class="briefing-list">'+rows.map(function(r){return '<article class="briefing-card"><div class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(r.day+' · '+r.providers.join(' / ')+' · '+r.proof)+'</span><strong>'+esc(r.title)+'</strong></span>'+creatorLink(r.url,'来源')+'</div></article>'}).join('')+'</div></section>';
}
// Reuse upstream story pointers and exact named feature/model anchors.
// Never add upstream counts to local original counts or infer creator identity/sponsorship.
function creatorPropagationGroups(reports,releases,events,now,term,scope){
 var groups=new Map(),brands=term?[term]:scope==='vendors'?creatorBrands.vendors:priorityCompetitors.concat(firstPartyProducts);
 var models=(releases||[]).filter(function(m){return m.modelName&&m.modelFamilyId&&m.modelVersionId&&m.verifiedAt&&['official-release','official-model-card'].includes(m.evidenceType)&&m.verificationStatus!=='pending'});
 function identity(title,brand){
  var hits=models.filter(function(m){return competitorModelPattern(m.modelName).test(title)});
  if(hits.length===1)return {name:hits[0].modelName,key:'model:'+hits[0].modelFamilyId+'|'+hits[0].modelVersionId,pattern:competitorModelPattern(hits[0].modelName)};
  if(hits.length>1)return null;
  var i=title.toLowerCase().indexOf(brand.toLowerCase()),tail=i<0?'':title.slice(i+brand.length).trim();
  // Only explicit names, not generic words such as "new feature" or "AI".
  var m=tail.match(/^([\u4e00-\u9fff]{2,8}(?:工作室|导演台|造型室|编辑器|工具箱))/)||title.match(/(?:新功能|功能|feature)\s*[「『“"]?([A-Za-z][A-Za-z0-9-]{2,35})(?=[」』”"\s，,。:：]|$)/i)||title.match(/[「『“"]([^」』”"\n]{3,35})[」』”"]\s*(?:功能|工作流|工具)/);
  if(!m||/^(?:new|the|and|with|for|model|feature|workflow|studio|canvas|video|image|audio)$/i.test(m[1]))return null;
  var name=m[1],escaped=Array.from(name).map(function(c){return /[.*+?^$\x7b\x7d()|[\]\\]/.test(c)?'\\'+c:c}).join(''),pattern=new RegExp((/^[A-Za-z0-9]/.test(name)?'(?<![A-Za-z0-9])':'')+escaped+(/[A-Za-z0-9]$/.test(name)?'(?![A-Za-z0-9])':''),'i');
  return {name:name,key:'feature:'+name.normalize('NFKC').toLowerCase(),pattern:pattern};
 }
 (reports||[]).forEach(function(r){
  var x=r.item||{},title=String(x.title||''),links=x.links||{},date=r.story?x.latestAt:x.publishedAt;
  if(!title||!date||!withinDays(date,3,new Date(now))||/黑五|折扣|优惠|促销|抽奖|discount|coupon|black friday|pricing|giveaway/i.test(title))return;
  var bs=brands.filter(function(b){return creatorSubject(title,b)||creatorIntegrationTarget(title,b)});
  if(!bs.length&&!r.story)bs=brands.filter(function(b){return creatorLaunchSignal(title,b)});
  if(bs.length!==1)return;
  var brand=bs[0],id=identity(title,brand),url=creatorOriginalUrl(r.story?links.story:links.original),story=r.story&&creatorStoryTarget(url);
  if(!url||r.story&&!story)return;
  var labels=r.story?Array.from(new Set((Array.isArray(x.sourceNames)?x.sourceNames:[]).filter(function(n){return typeof n==='string'&&n.trim()}))):[];
  var productReport=creatorLaunchSignal(title,brand)||((creatorSubject(title,brand)||creatorIntegrationTarget(title,brand))&&/发布|推出|上线|上新|接入|首发|更新|升级|launch|release|introduc|now available|integrat/i.test(title));
  if(r.story&&labels.length<2||!r.story&&(!id||!productReport))return;
  var key=brand+'|'+(id?id.key:'story:'+newsUrlKey(url)),g=groups.get(key);
  if(!g){g={brand:brand,name:id?id.name:title,pattern:id?id.pattern:null,originals:[],stories:[],latest:0,official:[]};groups.set(key,g)}
  g.latest=Math.max(g.latest,Date.parse(date));
  var lane=r.story?g.stories:g.originals;
  if(!lane.some(function(z){return newsUrlKey(z.url)===newsUrlKey(url)}))lane.push({url:url,title:title,day:chinaDay(date),source:String(x.source&&x.source.name||''),labels:labels,providers:r.providers||[]});
 });
 return Array.from(groups.values()).filter(function(g){return g.originals.length>=2||g.stories.length}).map(function(g){
  if(g.pattern){g.official=(events||[]).filter(function(e){return e.brand===g.brand&&g.pattern.test(e.title)&&['官方日志','官方插件发布提交','官方开发生态合并'].includes(e.proof)&&e.kind!=='下架 / 停服通知'});
   if(scope==='vendors')models.filter(function(m){return String(m.vendor||'').toLowerCase()===g.brand.toLowerCase()&&m.modelName===g.name&&creatorOriginalUrl(m.url)&&m.publishedAt&&Date.parse(m.publishedAt)<=now}).forEach(function(m){g.official.push({day:m.publishedAt,kind:'模型发布记录',title:m.modelName,url:m.url})});
  }
  return g;
 }).sort(function(a,b){return b.latest-a.latest||b.originals.length-a.originals.length}).slice(0,12);
}
function creatorPropagationMarkup(reports,releases,events,now,term,scope){
 var groups=creatorPropagationGroups(reports,releases,events,now,term,scope);
 if(!groups.length)return '';
 return '<section class="briefing-digest-section"><div class="section-head"><h2>近期新品传播信号</h2><span class="head-meta">近3天 · '+groups.length+' 个线索</span></div><p class="page-desc">复用聚合专题与同名功能原文；集中传播不等于商业合作或新品上线。上游来源标签与本站原文数分开记录，不相加。</p><div class="briefing-list">'+groups.map(function(g){return '<article class="briefing-card"><details '+(g.stories.some(function(r){return creatorStoryBusy===r.url||creatorStoryDisplay[r.url]})?'open':'')+'><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(chinaDay(new Date(g.latest).toISOString())+' · '+(g.official.length?'有官方相关记录':'待官方核验')+' · '+g.originals.length+' 条去重原文 / '+g.stories.length+' 个上游合集')+'</span><strong>'+esc(g.brand+' · '+g.name)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded">'+g.official.map(function(r){return '<p>'+esc(r.day+' · '+r.kind+' · '+r.title)+' '+creatorLink(r.url,'官方记录')+'</p>'}).join('')+g.stories.map(function(r){return '<p>'+esc((r.providers||[]).join(' / ')+' · '+r.labels.join('、'))+' '+creatorLink(r.url,'报道合集')+'</p>'+creatorStoryReadMarkup(r.url)}).join('')+g.originals.map(function(r){return '<div class="vendor-event"><time>'+esc(r.day.slice(5))+'</time><div class="vendor-event-main"><strong>'+esc(r.title)+'</strong><small>'+esc(r.source+' · 创作者线索')+'</small></div>'+creatorLink(r.url,'原文')+'</div>'}).join('')+'<div class="briefing-original-links">'+creatorLink('https://aipick.news/api/v1/items?mode=all&window=7d&limit=20&q='+encodeURIComponent(g.brand+' '+g.name),'专项寻源')+'</div></div></details></article>'}).join('')+'</div></section>';
}
// Decision aid, not a popularity score or a claim of missing integration.
function modelAdoptionOpportunities(releases,reports,app,social,now){
 var models=(releases||[]).filter(function(m){return m.modelName&&m.modelFamilyId&&m.modelVersionId&&m.verifiedAt&&['official-release','official-model-card'].includes(m.evidenceType)&&m.verificationStatus!=='pending'&&['video','image','audio','music','tts','speech','audio-other'].includes(m.category)&&creatorOriginalUrl(m.url)&&withinDays(m.publishedAt,30,new Date(now))});
 var rows=competitorBriefRows(app,reports,social,now),out=[],seen=new Set();
 models.forEach(function(m){
  var key=m.modelFamilyId+'|'+m.modelVersionId;if(seen.has(key))return;seen.add(key);
  var pattern=competitorModelPattern(m.modelName),launch=chinaDay(m.publishedAt),originals=new Map(),stories=new Map();
  (reports||[]).forEach(function(r){
   var x=r.item||{},l=x.links||{},when=r.story?x.latestAt:x.publishedAt,day=chinaDay(when),title=String(x.title||'');
   if(!when||!day||day<launch||!withinDays(when,3,new Date(now))||Date.parse(when)>now||!pattern.test(title)||/黑五|折扣|优惠|促销|抽奖|discount|coupon|black friday|giveaway/i.test(title))return;
   var url=creatorOriginalUrl(r.story?l.story:l.original);if(!url)return;
   var k=newsUrlKey(url);if(!k)return;
   if(r.story){
    if(!creatorStoryTarget(url))return;
    var labels=Array.from(new Set((Array.isArray(x.sourceNames)?x.sourceNames:[]).filter(function(n){return typeof n==='string'&&n.trim()})));
    if(labels.length>=2)stories.set(k,{url:url,title:title,labels:labels,day:day});
   }else if(x.selected===true||innovationCreativeCase(x)){
    originals.set(k,{url:url,title:title,day:day,source:x.source&&x.source.name||''});
   }
  });
  var related=rows.filter(function(r){return r.day>=launch&&pattern.test(r.modelName||r.title)&&r.kind!=='融资 / 公司动态'});
  var official=related.filter(function(r){return r.brand!=='Renoise'&&r.kind==='模型接入'&&r.proof==='官方日志'});
  var confirmed=Array.from(new Set(official.map(function(r){return r.brand})));
  var observed=Array.from(new Set(related.filter(function(r){return r.brand!=='Renoise'&&!confirmed.includes(r.brand)&&competitorEvidenceRank(r)<4}).map(function(r){return r.brand})));
  var own=related.filter(function(r){return r.brand==='Renoise'&&competitorEvidenceRank(r)<4});
  var strong=originals.size>=2||stories.size>0||confirmed.length>=2;
  var fresh=withinDays(m.publishedAt,3,new Date(now));
  if(!strong&&!fresh&&!confirmed.length)return;
  var watches=((app||{}).targetedDiscovery||{}).queries||[];
  var queryCounts=watches.filter(function(q){return q.modelWatch&&q.modelFamilyId===m.modelFamilyId&&q.modelVersionId===m.modelVersionId&&q.lastSuccessAt&&withinDays(q.lastSuccessAt,3,new Date(now))&&q.counts&&Number.isInteger(q.counts.exactTitleMatches)}).map(function(q){return {provider:q.provider,count:q.counts.exactTitleMatches,truncated:!!q.counts.hasNextCursor}});
  var priority=strong?'优先评估':confirmed.length?'竞品已接入 · 核对价值':'新模型 · 观察';
  out.push({model:m,priority:priority,strong:strong,confirmed:confirmed,observed:observed,official:official,own:own,originals:Array.from(originals.values()),stories:Array.from(stories.values()),queryCounts:queryCounts});
 });
 return out.sort(function(a,b){return Number(b.strong)-Number(a.strong)||b.confirmed.length-a.confirmed.length||String(b.model.publishedAt).localeCompare(String(a.model.publishedAt))}).slice(0,8);
}
function modelAdoptionOpportunityMarkup(releases,reports,app,social,now){
 var rows=modelAdoptionOpportunities(releases,reports,app,social,now).filter(function(r){return matches([r.model.modelName,r.model.vendor,r.model.summary].join(' '))});
 if(!rows.length)return '';
 return '<section class="briefing-digest-section"><div class="section-head"><h2>模型接入机会</h2><span class="head-meta">近3天传播 · 近30天正式模型</span></div><p class="page-desc">传播证据、接入证据和本方证据分别呈现。优先评估不代表必须接入；暂无证据不等于未接入。原榜、查询命中及原文数不相加。</p><div class="briefing-list">'+rows.map(function(r){return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(r.priority+' · '+r.model.publishedAt+' · '+r.model.vendor)+'</span><strong>'+esc(r.model.modelName)+'</strong><span>'+esc(r.confirmed.length+' 家官方日志确认接入 · '+r.originals.length+' 条近3天原文 · '+r.stories.length+' 个上游专题')+'</span></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><p>'+esc(r.model.summary||'模型能力详见官方发布')+' '+creatorLink(r.model.url,'官方发布')+'</p>'+modelCapabilityReviewMarkup(r.model)+'<p><strong>竞品接入：</strong>'+esc(r.confirmed.join('、')||'当前无官方日志确认')+'</p><p><strong>其他官方线索：</strong>'+esc(r.observed.join('、')||'暂无')+'</p>'+r.official.map(function(e){return '<p>'+esc(e.brand+' · '+e.day)+' '+creatorLink(e.url,'官方日志')+'</p>'}).join('')+'<p><strong>Renoise：</strong>'+esc(r.own.length?'已有官方相关记录；需核对具体地区及实际可用性':'暂无可核实记录；先核对内部实际状态')+'</p>'+r.own.slice(0,3).map(function(e){return '<p>'+esc(e.title+' · '+(e.note||e.proof))+' '+creatorLink(e.url,'原始证据')+'</p>'}).join('')+'<p><strong>需求传播：</strong>'+esc(r.queryCounts.map(function(q){return q.provider+' '+q.count+' 条精确命中'+(q.truncated?'（未翻页）':'')}).join(' / ')||'尚无近期定向查询统计')+'</p>'+r.stories.slice(0,3).map(function(e){return '<p>'+esc(e.labels.join('、'))+' '+creatorLink(e.url,'报道合集')+'</p>'}).join('')+r.originals.slice(0,4).map(function(e){return '<p>'+esc(e.title)+' '+creatorLink(e.url,'原文')+'</p>'}).join('')+'<p><strong>下一步：</strong>核实官方接入条件、商业使用权限和本方可用性，用相同输入对比目标创作场景；已有接入则研究能力差异和工作流，而非重复接入。</p></div></details></article>'}).join('')+'</div></section>';
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
 return head+toolbar+(!term?modelAdoptionOpportunityMarkup(state.modelReleases||[],creatorRows([{name:'AIHOT',items:state.aihot.items||[]},{name:'AIPick',items:((state.aipick||{}).items||[]).concat((state.aipick||{}).hotTopics||[])}],now).concat(reports),app,state.social||{},now):'')+creatorPropagationMarkup(reports,state.modelReleases||[],all,now,term)+'<div class="vendor-overview-summary"><span><strong>'+primaryActive+'/'+brands.length+'</strong> 家有近3天记录</span><span><strong>'+active+'/'+brands.length+'</strong> 家有近7天记录</span><span><strong>'+traceRows.length+'</strong> 个模型响应追踪</span></div>'+(traces?'<section class="briefing-digest-section"><div class="section-head"><h2>重点模型 · 各平台接入与宣发</h2></div>'+traces+'</section>':'')+'<div class="briefing-original-links"><a href="?view=feeds&amp;briefing=hot">查看事件专题与报道合集 ↗</a></div><div class="section-head"><h2>近3天优先 · 近7天厂商动态</h2><span class="head-meta">'+originalCount+' 条原文去重</span></div><div class="vendor-grid">'+cards+'</div>'+firstParty+curatedCreativeMarkup(now,term,filtered)+'<p class="page-desc">近3天为重点，4–7天补缺；更早的已核实历史在厂商发展史自然沉淀。暂无记录不等于没有更新；现有能力不计作近期上新。模型响应仅统计可关联记录，不代表全部平台已接入。</p><details class="source-health"><summary>数据与信源诊断</summary>'+diagnostics+creatorCoverageMarkup('competitors',term)+'<details><summary>官方来源与历史观察</summary>'+creatorOfficialMarkup(now,term)+'</details></details>';
}
// A private refresh supplements persisted evidence; an empty or failed
// upstream read must never erase the working production snapshot.
function competitorReadItems(base,privateItems){
 return (Array.isArray(base)?base:[]).concat(Array.isArray(privateItems)?privateItems:[]);
}
// Creative-demand signals are separate from product release facts and upstream hot ranks.
function creativeOriginalPlatform(url){
 try{var u=new URL(creatorOriginalUrl(url)),h=u.hostname.toLowerCase().replace(/^www\./,'');
  if(['x.com','twitter.com'].includes(h)&&/^\/(?:[A-Za-z0-9_]+\/status|i\/web\/status)\/\d+\/?$/.test(u.pathname))return 'X';
  if(h==='instagram.com'&&/^\/(?:reel|reels|p|tv)\/[A-Za-z0-9_-]+\/?$/.test(u.pathname))return 'Instagram';
  if(h==='youtube.com'&&((u.pathname==='/watch'&&/^[A-Za-z0-9_-]{11}$/.test(u.searchParams.get('v')||''))||/^\/shorts\/[A-Za-z0-9_-]{11}\/?$/.test(u.pathname))||h==='youtu.be'&&/^\/[A-Za-z0-9_-]{11}\/?$/.test(u.pathname))return 'YouTube';
  if(h==='tiktok.com'&&/^\/@[^/]+\/(?:video|photo)\/\d+\/?$/.test(u.pathname))return 'TikTok';
  if(h==='douyin.com'&&/^\/video\/\d+\/?$/.test(u.pathname))return '抖音';
  if(h==='xiaohongshu.com'&&/^\/(?:explore|discovery\/item)\/[a-f0-9]+\/?$/i.test(u.pathname))return '小红书';
  if(h==='bilibili.com'&&/^\/video\/(?:BV[A-Za-z0-9]+|av\d+)\/?$/.test(u.pathname))return 'B站';
 }catch(e){}
 return '';
}
// Calendar context alone is not a viral signal. Keep explicit creative artifacts
// while rejecting the software subscription/deal advertisements on the same dates.
function seasonalCreativeCase(item){
 var title=String(item&&item.title||'');
 if(!/黑五|黑色星期五|感恩节|圣诞|万圣节|春节|元旦|跨年|情人节|开斋节|斋月|black friday|cyber monday|thanksgiving|christmas|halloween|lunar new year|new year|valentine|ramadan|eid al-fitr/i.test(title))return false;
 if(/折扣|优惠|优惠券|套餐|积分|充值|限时免费|限免|赠送|抽奖|会员|discount|coupon|subscription|credits?|pricing|giveaway|\d+\s*%\s*off|\b(?:sale|deal)\b/i.test(title))return false;
 return /品牌短片|广告片|创意广告|节日广告|商业广告|商品广告|广告视频|视觉特效|创意视频|短片|动画|漫剧|镜头拆解|分镜|模板制作|brand film|short film|creative ad|holiday ad|product commercial|product reveal|ad creative|commercial video|animation|VFX|visual effects|motion graphics/i.test(title);
}
function creativeDemandRows(batches,now){
 var rows=creatorRows(batches,now),out=[];
 rows.forEach(function(r){
  var x=r.item||{},title=String(x.title||''),url=creatorOriginalUrl((x.links||{}).original),platform=creativeOriginalPlatform(url),published=Date.parse(x.publishedAt||'');
  if(r.story||x.selected!==true||!platform||!Number.isFinite(published)||published>now||!withinDays(x.publishedAt,3,new Date(now))||/折扣|优惠券|限时促销|积分充值|discount|coupon|giveaway/i.test(title))return;
  var demand=/爆款|爆火|走红|刷屏|病毒式|热播|热门视频|viral|went viral|trending video|\d[\d.,]*\s*(?:万|亿|million|billion|[mk])?\s*(?:播放|观看|views)/i.test(title);
  var craft=/复刻|模仿|还原|风格|变身|视觉特效|创意视频|短片|动画|漫剧|镜头|分镜|提示词|remake|recreat|style|transformation|VFX|short film|animation|cinematic|prompt/i.test(title);
  var media=/AI|视频|电影|影视|游戏|角色|动画|影像|video|film|game|character|animation|VFX/i.test(title);
  var seasonal=seasonalCreativeCase(x);
  if(!seasonal&&(!media||!(demand&&craft||craft&&(innovationCreativeCase(x)||/(?:照片|图片|图像|photo|image).{0,36}(?:风格|style)|(?:风格|style).{0,36}(?:照片|图片|图像|photo|image)/i.test(title))&&/复刻|模仿|还原|风格|变身|VFX|remake|recreat|style|transformation/i.test(title))))return;
  out.push({title:title,url:url,platform:platform,day:chinaDay(x.publishedAt),time:published,providers:r.providers,reportedTrend:demand,seasonal:seasonal});
 });
 return out.sort(function(a,b){return Number(b.reportedTrend)-Number(a.reportedTrend)||b.time-a.time}).slice(0,8);
}
function creativeDemandMarkup(batches,now){
 var rows=creativeDemandRows(batches,now).filter(function(r){return matches([r.title,r.platform].join(' '))});
 return '<section class="briefing-digest-section"><div class="section-head"><h2>创作爆点与复刻线索</h2><span class="head-meta">近3天 · '+rows.length+' 条原帖入口</span></div><p class="page-desc">来自已有精选原帖，不是社媒实时播放量榜。标题中的走红或播放量说法仅为报道线索；当前快照没有可核实播放量，不以精选分数代替。热门 IP、人物和音乐优先提炼可授权或原创的风格、镜头、创意与工作流。</p><div class="briefing-list">'+(rows.map(function(r){return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(r.day+' · '+r.platform+' · '+(r.reportedTrend?'传播线索 · 播放量待核实':r.seasonal?'节日创意参考 · 非爆款认证':'创作玩法参考 · 非爆款认证'))+'</span><strong>'+esc(r.title)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><p><strong>快速研究：</strong>打开原帖核对发布时间与公开播放量；拆解开头、视觉钩子、叙事、镜头和声音；用自有或授权素材复现关键手法；验证是否可封装模板、Skill 或 Agent 工作流。</p><p><strong>活动判断：</strong>核实需求、品牌适配及权利限制，再决定是否制作演示或发起创作者活动。</p>'+creatorLink(r.url,'原帖 / 核对指标')+'</div></details></article>'}).join('')||empty('当前快照暂无匹配创作爆点；未测量 Instagram / X 实际传播，不代表没有热点。'))+'</div><div class="briefing-original-links">'+creatorLink('https://www.instagram.com/explore/','Instagram 探索')+creatorLink('https://x.com/search?q=AI%20video%20viral&src=typed_query&f=live','X 创作热点搜索')+'</div></section>';
}
// A deterministic planning calendar, not a claim that a company has scheduled a campaign.
// Date offsets are planning deadlines, not evidence of completion.
function campaignMilestones(day,days){
 var start=Date.parse(day+'T00:00:00Z');
 if(!Number.isFinite(start)||!Number.isInteger(days))return [];
 return [
  {offset:-30,title:'机会与能力研究',owner:'产品研究',deliverable:'目标市场、用户创作场景、竞品功能、候选模型及工作流、素材授权边界'},
  {offset:-14,title:'产品与工作流准备',owner:'产品 / Agent 工程',deliverable:'可复用模板或 Skill、模型与工具契约、同素材基线及候选方案、异常恢复'},
  {offset:-7,title:'成片与功能验收',owner:'创作 / 工程',deliverable:'示范作品、生成质量及耗时对照、失败样本、局部修改和操作验证'},
  {offset:-3,title:'上线与传播准备',owner:'产品 / 创作者运营',deliverable:'已验证入口、发布素材、官方演示与候选 KOL；地区、授权和时间确认'},
  {offset:0,title:'发布与观察',owner:'产品 / 运营',deliverable:'实际发布状态、用户反馈、有效交付及异常记录；未授权不自动执行活动'},
  {offset:7,title:'复盘与沉淀',owner:'产品 / Agent 工程',deliverable:'经授权的使用数据、成片质量与返工记录、可复用资产/Skills、下一轮修正'}
 ].map(function(m){var until=days+m.offset;return Object.assign({},m,{day:new Date(start+m.offset*86400000).toISOString().slice(0,10),status:until<0?'计划日已过 · 完成未知':until===0?'今日计划 · 待确认':'计划节点'})});
}
function campaignPreparationStage(days){
 if(days<0)return 'D+'+(-days)+' · 复盘与沉淀';
 if(days===0)return 'D-Day · 发布与观察';
 if(days<=3)return 'D-3 · 上线与传播准备';
 if(days<=7)return 'D-7 · 成片与功能验收';
 if(days<=14)return 'D-14 · 产品与工作流准备';
 if(days<=30)return 'D-30 · 机会与能力研究';
 return '提前规划';
}
function campaignResearchHandoff(r){
 return ['# 营销创作研究任务｜'+r.title,'状态：策划候选，非已立项或发布。','日期：'+(r.approx?'预计 ':'')+r.day+'｜市场：'+r.market,'创作机会：'+r.idea,'研究重点：候选模型优势、竞品同类入口、可复用 Agent 工具/Skill、原创或授权素材及创作需求。','当前计划阶段：'+r.stage,'计划节点（日期不表示完成）：'].concat(r.milestones.map(function(m){return '- '+m.day+'｜'+m.title+'｜'+m.owner+'（建议协作）｜'+m.deliverable+'｜'+m.status}),['验收：同素材对照，记录作品质量、可用交付、操作与返工成本；只有取得经授权的实际使用数据才判断用户增长和留存。',r.days<0?'复盘：先确认是否实际开展及取得授权的记录；未开展则只做同类案例研究，不虚构活动或用户数据。':'逾期：先核对已完成事项与可交付范围；时间不足时使用已验证能力或暂缓，不强行上线。',r.approx?'预计日期须按当地公告重算。':'日期和市场活动须按当地公告复核。']).join('\n');
}
function creativeCampaignCalendar(now){
 var today=chinaDay(new Date(now).toISOString()),start=Date.parse(today+'T00:00:00Z'),year=Number(today.slice(0,4)),rows=[];
 function add(day,title,market,idea,source,priority,approx){
  var left=Math.round((Date.parse(day+'T00:00:00Z')-start)/86400000);if(!Number.isInteger(left)||left<-7||left>90)return;
  rows.push({day:day,title:title,market:market,idea:idea,source:source||'',priority:priority||(/中国电商|^中国$|^国内及适用市场$/.test(market)?'domestic':'global'),approx:!!approx,days:left,stage:campaignPreparationStage(left),milestones:campaignMilestones(day,left)});
 }
 for(var y=year-1;y<=year+1;y++){
  [['01-01','元旦 / New Year','国内外','跨年与新年主题宣传、年度回顾'],
   ['02-14','情人节','国内外','情感故事、礼品广告及个性化祝福'],
   ['03-17','St. Patrick’s Day','爱尔兰及相关海外市场','绿色主题、原创节庆视觉'],
   ['07-04','Independence Day','美国','美国市场夏季主题及品牌活动'],
   ['05-01','劳动节','国内及适用市场','职业人物与品牌故事'],
   ['06-18','618 营销节点','中国电商','商品广告、批量短视频、促销创意素材'],
   ['10-01','国庆节','中国','旅行、品牌及节日主题内容'],
   ['10-31','Halloween','适用海外市场','奇幻角色、变装、氛围特效模板'],
   ['11-11','双11营销节点','中国电商','商品卖点短片、批量创意广告'],
   ['12-25','Christmas','适用国内外市场','节日广告、礼品故事、冬季风格模板']].forEach(function(e){add(y+'-'+e[0],e[1],e[2],e[3])});
  var first=new Date(Date.UTC(y,10,1)),thanks=1+((4-first.getUTCDay()+7)%7)+21;
  var friday=new Date(Date.UTC(y,10,thanks+1)).toISOString().slice(0,10),monday=new Date(Date.UTC(y,10,thanks+4)).toISOString().slice(0,10);
  add(new Date(Date.UTC(y,10,thanks)).toISOString().slice(0,10),'Thanksgiving','美国','感恩节品牌故事、家庭主题及假日广告');
  var mayFirst=new Date(Date.UTC(y,4,1)),juneFirst=new Date(Date.UTC(y,5,1));
  add(new Date(Date.UTC(y,4,1+(7-mayFirst.getUTCDay())%7+7)).toISOString().slice(0,10),'Mother’s Day','美国及采用同日的市场','礼品、家庭与情感故事');
  add(new Date(Date.UTC(y,5,1+(7-juneFirst.getUTCDay())%7+14)).toISOString().slice(0,10),'Father’s Day','美国及采用同日的市场','家庭故事、礼品及品牌创意');
  add(friday,'Black Friday 营销节点','适用海外市场','商品广告、品牌活动视频及创作者演示');
  add(monday,'Cyber Monday 营销节点','适用海外市场','数码产品宣传、网页与交互动效素材');
 }
 var lunarSource='https://www.info.gov.hk/gia/general/202605/15/P2026051400300p.htm';
 [['2027-02-06','春节 / Lunar New Year','春节祝福、国风角色、品牌团圆故事'],['2027-04-05','清明','尊重文化语境的春季创作'],['2027-06-09','端午节','传统文化、节令产品与视觉风格'],['2027-09-15','中秋节','团圆、礼品广告、月夜主题']].forEach(function(e){add(e[0],e[1],'中国及适用市场',e[2],lunarSource)});
 add('2027-02-08','Ramadan 预计开始','中东及全球穆斯林社群','尊重文化习俗的家庭、餐饮和节期内容；当地日期待确认','https://www.islamic-relief.org.uk/giving/islamic-giving/ramadan/ramadan-timetable/','global',true);
 add('2027-03-10','Eid al-Fitr 预计日期','中东及全球穆斯林社群','尊重文化习俗的祝福、家庭及节日视觉；当地日期待确认','https://www.islamic-relief.org.uk/giving/islamic-giving/ramadan/ramadan-timetable/','global',true);
 add('2027-03-28','Easter Sunday','采用西方教会历法的市场','春季主题、节日创意与品牌故事','https://www.info.gov.hk/gia/general/202605/15/P2026051400300p.htm','global');
 return rows.sort(function(a,b){return Number(a.days<0)-Number(b.days<0)||Number(a.priority==='domestic')-Number(b.priority==='domestic')||(a.days<0&&b.days<0?b.day.localeCompare(a.day):a.day.localeCompare(b.day))||a.title.localeCompare(b.title)});
}
function creativeCampaignMarkup(now){
 var rows=creativeCampaignCalendar(now).filter(function(r){return matches([r.title,r.market,r.idea].join(' '))});
 if(!rows.length)return '';
 var upcoming=rows.filter(function(r){return r.days>=0}),recent=rows.filter(function(r){return r.days<0});
 function cards(items){
  return '<div class="briefing-list">'+items.map(function(r){return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc((r.priority==='domestic'?'国内补充':'海外 / 跨市场')+' · '+(r.approx?'预计 ':'')+r.day+' · '+(r.days===0?'今天':r.days<0?'节点已过 '+(-r.days)+' 天':'还有 '+r.days+' 天')+' · '+r.stage+' · '+r.market)+'</span><strong>'+esc(r.title)+'</strong><span>'+esc(r.idea)+'</span></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded">'+(r.days<0?'<p><strong>复盘候选：</strong>先核实是否实际开展；记录可访问的公开案例、有效手法与经授权的实际反馈。无活动记录时只做创作案例研究，不虚构业绩。</p>':'<p><strong>候选准备：</strong>确定主题与授权素材，制作 Agent 可复用模板、同素材测试、示范视频和活动创意；核对上线资源、用户交付与传播时间。不是已立项活动。</p>')+(r.source?creatorLink(r.source,r.approx?'预计日期参考':'已核对日期依据'):'')+researchHandoffMarkup(campaignResearchHandoff(r))+'</div></details></article>'}).join('')+'</div>';
 }
 return '<section class="briefing-digest-section"><div class="section-head"><h2>节日与营销创作机会</h2><span class="head-meta">海外优先 · 未来90天 + 近7天复盘</span></div><p class="page-desc">海外及跨市场节点优先，国内电商与本地节日补充。日历不代表已安排活动；各地区庆祝日期与文化语境须核对，预计日期以当地公告为准。</p>'+(upcoming.length?cards(upcoming):'')+(recent.length?'<details class="source-health"><summary>最近7天 · 复盘候选 '+recent.length+' 个节点</summary>'+cards(recent)+'</details>':'')+'</section>';
}
// Personal session only: no network, localStorage, upload, or shared data store.
var revidSessionRows=[],revidSessionStatus='';
var revidTopicLabels={'visual-transformation':'视觉特效','cinematic':'电影级影像','character-ip':'热门 IP','advertising':'商业广告','storytelling':'剧情叙事','seasonal':'海外节日'};
function revidPersonalRows(raw,now){
 var parsed=JSON.parse(raw);if(!parsed||!Array.isArray(parsed.candidates)||parsed.candidates.length>48)throw Error('无效的个人研究结果');
 var unique=new Map();
 parsed.candidates.forEach(function(x){
  if(!x||x.source!=='revid'||x.verification!=='provider-reported'||typeof x.url!=='string')return;
  var patterns={youtube:/^https:\/\/www\.youtube\.com\/watch\?v=[\w-]{11}$/,tiktok:/^https:\/\/www\.tiktok\.com\/@[\w.-]+\/video\/\d+$/,instagram:/^https:\/\/www\.instagram\.com\/p\/[\w-]+\/$/,x:/^https:\/\/x\.com\/i\/web\/status\/\d+$/};
  if(!Object.prototype.hasOwnProperty.call(patterns,x.platform)||!patterns[x.platform].test(x.url))return;
  var published=Date.parse(x.postedAt),observed=Date.parse(x.observedAt);
  if(!Number.isFinite(published)||!Number.isFinite(observed)||published>observed||observed>now||published<now-3*86400000)return;
  function metric(v){return Number.isSafeInteger(v)&&v>=0?v:null}
  var views=metric(x.views);if(views===null||views<10000)return;
  var topics=Array.isArray(x.creativeTopics)?Array.from(new Set(x.creativeTopics.filter(function(t){return Object.prototype.hasOwnProperty.call(revidTopicLabels,t)}))):[];
  if(!topics.length||unique.has(x.url))return;
  unique.set(x.url,{url:x.url,platform:x.platform,postedAt:new Date(published).toISOString(),observedAt:new Date(observed).toISOString(),views:views,likes:metric(x.likes),shares:metric(x.shares),topics:topics});
 });
 return Array.from(unique.values()).sort(function(a,b){return b.views-a.views});
}
function revidPersonalMarkup(now){
 var rows=revidSessionRows.filter(function(x){return Date.parse(x.postedAt)>=now-3*86400000&&Date.parse(x.observedAt)<=now});
 var names={youtube:'YouTube',tiktok:'TikTok',instagram:'Instagram',x:'X'};
 function metric(v){return v===null?'未知':v.toLocaleString('zh-CN')}
 return '<section class="briefing-digest-section"><div class="section-head"><div><h2>海外爆款 · 个人研究</h2><p>近72小时 · 来源报告指标，未独立核验 · 不构成全平台排名</p></div><span class="head-meta">'+rows.length+' 条原帖</span></div><details class="source-health"><summary>导入个人 Revid 查询结果</summary><p>仅本次页面会话内存。粘贴个人研究脚本输出，不粘贴 API Key；刷新后清除，不上传或公开同步。</p><label for="revidPersonalInput">个人研究 JSON</label><textarea id="revidPersonalInput" rows="4" maxlength="262144" style="display:block;width:100%;max-width:100%;margin:8px 0" autocomplete="off" spellcheck="false"></textarea><button type="button" class="tab" data-revid-personal="import">导入</button> <button type="button" class="tab" data-revid-personal="clear">清除</button></details>'+(revidSessionStatus?'<p role="status" class="page-desc">'+esc(revidSessionStatus)+'</p>':'')+'<div class="briefing-list">'+(rows.map(function(x){return '<article class="briefing-card"><div class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(names[x.platform]+' · 发布 '+overviewDateLabel(x.postedAt))+'</span><strong>'+esc(x.topics.map(function(t){return revidTopicLabels[t]}).join(' / '))+'</strong></span></div><p class="page-desc">'+esc('来源报告浏览/播放 '+metric(x.views)+' · 点赞 '+metric(x.likes)+' · 分享 '+metric(x.shares)+' · 观测 '+overviewTime(x.observedAt))+'</p><div class="briefing-original-links">'+creatorLink(x.url,'查看原帖')+'</div></article>'}).join('')||empty('尚无本次会话的有效爆款数据；现有精选不冒充播放量榜。'))+'</div></section>';
}
document.addEventListener('click',function(e){
 var b=e.target.closest('[data-revid-personal]');if(!b)return;
 if(b.dataset.revidPersonal==='clear'){revidSessionRows=[];revidSessionStatus='个人数据已清除';render();return}
 var input=document.getElementById('revidPersonalInput');
 if(!input)return;
 try{if(input.value.length>262144)throw Error('oversized');revidSessionRows=revidPersonalRows(input.value,Date.now());revidSessionStatus='已读取 '+revidSessionRows.length+' 条符合条件的原帖';input.value=''}catch(err){revidSessionStatus='导入失败：请提供有效的个人研究 JSON，保留上次有效结果'}
 render();
});

function creatorIntelPage(tabs){
 var mode=state.briefingTab,hot=mode==='hot',cases=mode==='cases',now=Date.now(),a=state.aipick||{},brands=creatorBrands[mode]||[],term=brands.includes(creatorBrand)?creatorBrand:'',priv=creatorPrivate[mode+'|'+term]||{},sources=priv.sources||{},from=function(name,key,fallback){return sources[name]&&sources[name].data?sources[name].data[key]||[]:fallback||[]},stamp=function(name,fallback){return sources[name]&&sources[name].data?sources[name].observedAt:fallback};
 var head=pageHead('行业简报',hot?'近3天优先 · 按事件最近进展聚合发布、接入、功能与实测':cases?'最近7天 · 创作者精选与原帖，不冒充播放量排名':'最近7天 · '+(mode==='competitors'?'聚合平台与创作工具':'模型厂商及自有产品')+'相关动态','AIHOT + AIPick');
 var links=creatorLink('https://aihot.news/hot','AIHOT 实时热点')+creatorLink('https://aipick.news/hot','AIPick 实时热点');
 if(cases||hot)links+=creatorLink('https://www.revid.ai/search','Revid · 原站爆款搜索（个人阅读）');
 if(term)links+=['aihot.news','aipick.news'].map(function(h){return creatorLink('https://'+h+'/api/v1/items?mode=all&window=7d&limit=20&q='+encodeURIComponent(term),h.split('.')[0]+' 查询')}).join('');
 var filters=brands.length?'<div class="filter-row briefing-category-filters" role="group" aria-label="关注厂商">'+['全部'].concat(brands).map(function(b){var v=b==='全部'?'':b;return '<button class="filter-chip '+(v===term?'active':'')+'" aria-pressed="'+(v===term)+'" data-creator-brand="'+esc(v)+'">'+esc(b)+'</button>'}).join('')+'</div>':'';
 var live='<button type="button" class="tab" data-creator-refresh '+(creatorBusy?'disabled':'')+'>'+(creatorBusy?'读取中…':hot?'个人阅读 · 双源实时热点':'个人阅读 · 双源最新精选')+'</button>';
 var status=Object.keys(sources).map(function(n){var x=sources[n];return n+' '+(x.error?'读取失败，保留可用记录：'+x.error:x.observedAt?overviewTime(x.observedAt):'未读取')}).join(' · ');
 var toolbar='<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div>'+filters+'<div class="news-toolbar"><p class="page-desc">'+(isLocalAihot()?'个人阅读实时查询，仅内存缓存。':'点击个人阅读，从你的浏览器直连双源，仅本次会话内存读取；不向本站服务器同步。失败可打开上游原站。')+'</p>'+live+'</div><div class="briefing-original-links">'+links+'</div>'+(status?'<p class="overview-notice">'+esc(status)+'</p>':'');
 if(hot){var dossierBatches=[{name:'AIHOT',items:(state.aihot.items||[]).concat(from('AIHOT','items',[]))},{name:'AIPick',items:(a.items||[]).concat(a.hotTopics||[],from('AIPick','items',[]))}];return head+toolbar+revidPersonalMarkup(now)+creativeDemandMarkup(dossierBatches,now)+creativeCampaignMarkup(now)+creatorDossierMarkup(creatorDossiers(state.modelReleases,dossierBatches,state.appUpdates||{},state.social||{},[{name:'AIHOT 日报',data:state.aihotDaily},{name:'橘鸦',data:state.juyaDaily}],now),now)+creatorUnifiedHotMarkup([{name:'AIHOT',items:from('AIHOT','items',[])},{name:'AIPick',items:from('AIPick','items',a.hotTopics)}],now,state.modelReleases)+creatorHotMarkup(from('AIHOT','items',[]),'AIHOT',stamp('AIHOT',''),now)+creatorHotMarkup(from('AIPick','items',a.hotTopics),'AIPick',stamp('AIPick',a.fetchedAt),now)+'<p class="page-desc">原榜分别展示，不将两个平台的参与者或来源数相加；报道合集包含同一事件的多篇报道。热度不等于事实核实。</p>'+creatorCoverageMarkup(mode,term);}
 var rows=creatorRows([{name:'AIHOT',items:competitorReadItems(state.aihot.items,from('AIHOT','items',[]))},{name:'AIPick',items:competitorReadItems((a.items||[]).concat(a.hotTopics||[]),from('AIPick','items',[]))}],now).filter(function(r){var x=r.item;return (cases||!/黑五|黑色星期五|折扣|优惠券|限时促销|black friday|discount|coupon/i.test(x.title))&&matches([x.title,x.source&&x.source.name].join(' '))&&(cases?innovationCreativeCase(x):mode==='competitors'?(term?[term]:trackingBrands).some(function(b){return creatorSubject(x.title,b)||creatorIntegrationTarget(x.title,b)||(!r.story&&creatorLaunchSignal(x.title,b))}):(creatorBrandMatch(x.title,mode,term)||mode==='vendors'&&!r.story&&(term?[term]:creatorBrands.vendors).some(function(b){return creatorLaunchSignal(x.title,b)})))});
 if(mode==='competitors')return competitorBriefPage(head,'<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div>'+filters+'<div class="briefing-original-links"><button type="button" class="tab" data-creator-refresh '+(creatorBusy?'disabled':'')+'>'+(creatorBusy?'读取中…':term?'补充读取 '+esc(term)+' 最新精选':'个人阅读 · 近7天双源精选')+'</button></div>',rows,now,term,toolbar.replace('<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div>'+filters,''));
 var body=rows.map(function(r){var x=r.item,l=x.links||{};return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc([r.story?'讨论 '+overviewDateLabel(x.latestAt):x.publishedAt?overviewDateLabel(x.publishedAt):x.discoveredAt?'发现 '+overviewDateLabel(x.discoveredAt)+' · 发布日未知':'日期待确认',aihotCategoryName(x.category),r.providers.join(' / '),x.source&&x.source.name||''].filter(Boolean).join(' · '))+'</span><strong>'+esc(x.title)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><div class="briefing-original-links">'+creatorLink(l.original,r.story?'代表帖':'原帖')+creatorLink(l.story,'报道合集')+creatorLink(l.aihot,'资讯条目')+'</div><p class="page-desc">相关报道 · 不自动确认为产品已上线或模型首发。</p></div></details></article>'}).join('');
 return head+toolbar+(cases?revidPersonalMarkup(now)+creativeDemandMarkup([{name:'AIHOT',items:competitorReadItems(state.aihot.items,from('AIHOT','items',[]))},{name:'AIPick',items:competitorReadItems(a.items,from('AIPick','items',[]))}],now)+creativeCampaignMarkup(now):'')+(mode==='vendors'?creatorPropagationMarkup(rows,state.modelReleases||[],competitorBriefRows(state.appUpdates||{},rows,state.social||{},now),now,term,'vendors')+curatedCreativeMarkup(now,term,rows):'')+'<section class="briefing-digest-section"><div class="section-head"><h2>'+esc(term|| (cases?'创作线索':mode==='competitors'?'竞品相关报道':'厂商相关报道'))+'</h2><span class="head-meta">'+rows.filter(function(r){return !r.story}).length+' 条原文去重'+(rows.some(function(r){return r.story})?' · '+rows.filter(function(r){return r.story}).length+' 个事件合集':'')+'</span></div><div class="briefing-list">'+(body||empty('当前快照无匹配报道，不代表没有更新。请按厂商打开上游或在本地查询。'))+'</div></section>'+(cases?'':creatorCoverageMarkup(mode,term))
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
 if(seasonalCreativeCase(item))return true;
 if(!title||/折扣|积分|促销|优惠|discount|coupon|黑五|黑色星期五|black friday/i.test(title))return false;
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
  add('model',x.modelName,x.summary,x.url,x.publishedAt,x.vendor,{category:x.category,modelFamilyId:x.modelFamilyId,modelVersionId:x.modelVersionId,evidenceType:x.evidenceType,access:x.access||''});
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
  if(!['video','image','audio','music','tts','speech','audio-other'].includes(s.category)&&!innovationThemes.some(function(t){return t.pattern.test(s.title+' '+s.detail)})&&!(s.category==='llm'&&modelCreativeLlmCandidate(s.detail)))return;
  rows.push({signal:s,related:null,question:'对照上一代，用固定素材分别验证可控性、失败边界及输出；再决定是否值得封装。'});
 });
 signals.filter(function(s){return s.type==='case'&&!innovationThemes.some(function(t){return t.pattern.test(s.title+' '+s.detail)})}).forEach(function(s){
  rows.push({signal:s,related:null,question:'阅读创作者原帖，拆出输入、关键步骤和可复现结果；先判断是否属于创作产品机会。'});
 });
 return rows.sort(function(a,b){return b.signal.day.localeCompare(a.signal.day)||({product:0,model:1,case:2}[a.signal.type]-{product:0,model:1,case:2}[b.signal.type])});
}
// Research axes are prompts for verification, not structured claims of model support.
function modelCreativeLlmCandidate(text){
 return /视频理解|视频分析|视频剪辑|剪辑决策|镜头理解|分镜规划|创作规划|工具调用|多模态.{0,18}(?:视频|图像|音频)|video understanding|video analysis|video edit|shot planning|storyboard|tool.calling|multimodal.{0,24}(?:video|image|audio)|编程|编码|软件工程|代码生成|网页|前端|游戏|3D|三维|脚本|coding|software engineering|code generation|web development|front.end|game development|scripting/i.test(String(text||''));
}
function modelCapabilityReview(model){
 if(!model||!['official-release','official-model-card'].includes(model.evidenceType)||!creatorOriginalUrl(model.url))return null;
 var detail=String(model.summary||model.detail||''),category=model.category||'',axes=[];
 var rules=[
  {id:'resolution',label:'画质与输出规格',pattern:/(?:\b(?:4K|8K|1080p|720p|768p|2160p|4320p)\b|高清生成|超分辨率|分辨率|native resolution|upscal)/i,check:'确认原生生成还是后置超分、各模式的实际像素及压缩；同素材比较细节与交付可用性。'},
  {id:'duration',label:'时长与连续叙事',pattern:/\d+\s*(?:秒|分钟|seconds?|minutes?)|多镜头|多场景|连续叙事|multi.shot|multi.scene/i,check:'逐档测试最长可用时长、动作和镜头连续性；核对时长与分辨率、参考控制是否可同时使用。'},
  {id:'control',label:'空间、运镜与白模控制',pattern:/3D\s*运镜|三维运镜|白模|灰模|相机轨迹|镜头控制|运镜|3D camera|camera path|camera control|previs|depth map|深度图|姿态控制/i,check:'验证相机轨迹、几何布局、遮挡与白模参考遵循；明确需要何种输入，不默认支持白模渲染。'},
  {id:'reference',label:'参考资产与局部编辑',pattern:/首尾帧|参考图|参考生成|图像编辑|角色一致性|角色保持|人物一致性|多参考|reference image|keyframe|image edit|character consistency|identity preservation/i,check:'固定产品或角色参考，测试身份、Logo、姿态、风格保持及局部编辑边界。'},
  {id:'audio',label:'声音与音画联动',pattern:/原生音频|原生音视频|音视频生成|音画同步|音频生成|配音|口型同步|native audio|audio.video generation|lip.sync/i,check:'核对可用音轨、对白声线、同步、音质与分轨输出，区分原生生成和后期合成。'},
  {id:'repair',label:'视觉自检与修复',pattern:/自我修正|自我纠错|画面文字|文字校正|self.correct|self.repair|text rendering|text correction/i,check:'提供带准确品牌文案的失败样本，测试错误检测、局部修复、误改率及人工审美。'},
  {id:'agent',label:'Agent 理解、规划与剪辑',pattern:/视频理解|视频分析|视频剪辑|剪辑决策|镜头理解|分镜规划|创作规划|工具调用|video understanding|video analysis|video edit|shot planning|storyboard|tool.calling/i,check:'固定原片及创作 brief，要求结构化镜头表、剪辑点、工具参数及可执行时间线；验证实际工具执行，不把视频理解等同于剪辑能力。'},
  {id:'creative-code',label:'创意编程、网页、游戏与三维工具',pattern:/编程|编码|软件工程|代码生成|网页|前端|游戏|3D|三维|脚本|coding|software engineering|code generation|web development|front.end|game development|scripting/i,check:'用同一交互网页、游戏小样或三维场景 brief 比较代码可运行性、视觉还原、交互、动画、性能及可编辑交付；验证实际渲染器和工具执行，不把编码能力等同于原生渲染。'},
  {id:'economy',label:'推理效率与生成经济性',pattern:/低成本|高性价比|推理成本|低延迟|推理加速|生成速度|吞吐|cost.efficien|inference cost|low.latency|throughput|faster inference/i,check:'同模式、同输出规格、同质量门槛记录实际生成成本和等待时间；计入失败、重试及后期，不拿套餐折扣当推理成本。'}
 ];
 rules.forEach(function(r){if((r.id!=='creative-code'||category==='llm')&&r.pattern.test(detail))axes.push({id:r.id,label:r.label,check:r.check})});
 if(category==='llm'&&modelCreativeLlmCandidate(detail)&&!axes.some(function(r){return r.id==='agent'||r.id==='creative-code'}))axes.push({id:'agent',label:'Agent 多模态创作研究',check:'固定素材，验证理解准确性、结构化规划和真实工具执行；不预设支持视频编辑。'});
 return {axes:axes,access:String(model.access||''),detail:detail,source:model.url};
}
function copyResearchOrTemplate(target){
 var b=target.closest('[data-copy-research-brief],[data-copy-template]');
 if(!b)return false;
 var brief=b.parentElement.querySelector('[data-research-brief]'),item=b.hasAttribute('data-copy-template')?(state.promptTemplates.items||[]).find(function(x){return x.id===b.dataset.copyTemplate}):null,value=brief?brief.textContent:item&&item.body;
 if(value&&navigator.clipboard)navigator.clipboard.writeText(value).then(function(){b.textContent='已复制'}).catch(function(){b.textContent='复制失败，请手动选择'});else b.textContent='请手动选择文本';
 return true;
}
function researchHandoffMarkup(text){
 return '<div class="prompt-row"><h3>研发任务单 · 可复制</h3><p class="page-desc">复制后可粘贴到研发讨论或任务文档；不自动立项。</p><pre data-research-brief>'+esc(text)+'</pre><button type="button" class="filter-chip" data-copy-research-brief>复制研发任务单</button></div>';
}
function modelResearchHandoff(model,review){
 return ['# 模型能力验证｜'+(model.modelName||model.title),'状态：待实测；非已立项或已接入。','官方来源：'+review.source,'官方摘要：'+(review.detail||'现有摘要不足，先查官方模型卡及规格。'),'访问条件：'+(review.access||'待核实 API、权限及商用许可。'),'目标：改善 Renoise Agent 创作质量、效率或可控性。','实验：固定授权素材、创作 brief、输出规格和当前产品基线；记录精确模型版本、接口模式、参数及重复样本。','专项验证：'].concat(review.axes.length?review.axes.map(function(a){return '- '+a.label+'：'+a.check}):['- 先核实输入输出契约、能力边界及可执行接口。'],['统一验收：人工盲评与技术检查分开；记录失败、返工、耗时、生成/重试/后期总成本及可用交付数。','交付：最小可复现工作流/Skill 或工具契约、输入输出样例、失败样本、对比结果及接入/暂缓建议。','决策：未实测不得填入效果提升；先核对内部现状和授权。']).join('\n');
}
function agentResearchHandoff(r){
 return ['# Agent 研发任务｜'+r.title,'状态：待实测；非已立项或已实现。','目标：提升创作者的有效交付质量与操作效率。','固定输入：'+r.brief,'候选流程：'+r.plan,'当前基线：同素材、同约束使用现有流程，记录版本及失败样本。','验收：'+r.checks,'体验指标：首次可用作品时间、人工操作、干预、返工、有效交付；指标待测。','工具契约：明确输入、输出、模型版本、异常与重试、可编辑中间产物。','交付：可复现工作流/Skill、对照样片、失败记录和是否产品化的建议。','近期研究证据：'].concat(r.signals.map(function(s){return '- '+s.day+'｜'+s.origin+'｜'+s.title+'｜'+s.url}),['注意：关联记录不等于独立验证或真实用户需求；用户留存需实际授权数据。']).join('\n');
}
function modelCapabilityReviewMarkup(model){
 var r=modelCapabilityReview(model);if(!r)return '';
 return '<h3>能力上限与产品化研究 · 待实测</h3><p class="page-desc">以下按已有官方来源摘要匹配研究维度；提及不等于已支持，未提及不等于不支持。上限与模式组合仍需查官方规格及实测。</p>'+(r.access?'<p><strong>已记录访问方式：</strong>'+esc(r.access)+'</p>':'')+(r.axes.length?'<div class="briefing-list">'+r.axes.map(function(a){return '<p><strong>'+esc(a.label)+'：</strong>'+esc(a.check)+'</p>'}).join('')+'</div>':'<p>现有摘要不足以识别明确的特殊能力，先检查官方模型卡与接口规格。</p>')+'<p><strong>统一经济性验证：</strong>同质量门槛下记录总生成、重试、后期成本与可用交付数，计算每个可用作品成本；未取得实际数据前不判断便宜程度。</p><p><strong>产品化判断：</strong>将可重复验证的能力封装成工具、Skill 或画布节点，再验证 Agent 是否可以稳定调用。 '+creatorLink(r.source,'官方能力证据')+'</p>'+researchHandoffMarkup(modelResearchHandoff(model,r));
}
function innovationModelTestPlan(signal){
 if(!signal||signal.type!=='model')return null;
 var plans={
  video:['固定参考图、提示词、镜头及可比时长','对比主体一致性、运动轨迹、镜头控制、音画同步（如官方支持）','记录失败样本、重复生成稳定性及输出限制'],
  image:['固定角色参考、文本、布局与编辑区域','对比角色保持、文字准确度、局部编辑范围','检查输出分辨率、透明或矢量格式是否确实可用'],
  audio:['固定视频或音频参考、对白和环境音','对比音质、时间戳、声源保持和同步','检查独立音轨、可编辑输出与授权限制'],
  music:['固定场景、时长、情绪及参考节奏','对比结构、节奏、情绪和重复生成一致性','检查编辑、分轨和授权边界'],
  tts:['固定多语言台词、情绪与发音词表','对比可懂度、发音、停顿与情绪稳定性','核查说话人授权和对齐时间戳'],
  llm:['固定同一创作 brief、素材、可用工具与交付规格，比较不同模型作为 Agent 主脑','对比剧本分镜、镜头与剪辑决策、视觉理解、网页/游戏原型或三维脚本（按任务选用），实际执行后评价作品','核对工具调用、代码运行、渲染输出、错误恢复、人工干预与可复现性；区别模型推理与工具完成的结果']
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
  return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(s.day+' · '+labels[s.type]+' · '+s.origin)+'</span><strong>'+esc(s.title)+'</strong></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded">'+(s.detail?'<p>'+esc(s.detail)+'</p>':'')+(s.type==='model'?modelCapabilityReviewMarkup(s):'')+'<p><strong>探索问题：</strong>' +esc(r.question)+'</p>'+(plan?'<p><strong>能力测试清单 · '+esc(plan.status)+'</strong></p><p>'+esc(plan.baseline)+'</p><ol>'+plan.steps.map(function(x){return '<li>'+esc(x)+'</li>'}).join('')+'</ol>':'')+'<div class="briefing-original-links">'+creatorLink(s.url,'原始记录')+'</div>'+(r.related?'<p><strong>同名型号关联：</strong>'+esc(r.related.origin+' · '+r.related.title+' · '+r.related.day)+' '+creatorLink(r.related.url,'独立模型记录')+'。同名候选，不证明接口、权重或能力完全一致。</p>':'')+'</div></details></article>';
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
// Reuse the existing evidence pipeline; these are test hypotheses, not tested capabilities.
var agentCreativeTasks=[
 {id:'product-ad',title:'产品广告 / 宣传片',brief:'授权产品参考图、品牌卖点、目标受众与交付规格。',pattern:/产品广告|产品宣传|产品一致性|商品一致性|商品图|产品摄影|商业摄影|品牌广告|产品展示|产品保真|product (?:advertis|commercial|photograph|showcase|consistency|preserv)|brand commercial|\bTVC\b/i,plan:'理解卖点与产品真值 → 创意分镜 → 产品参考资产 → 镜头生成 → 声音与落版。',checks:'产品外形、Logo、材质和卖点表达；镜头节奏、品牌信息准确度。'},
 {id:'story',title:'短片 / 短剧连续叙事',brief:'剧本、角色参考、场景约束、镜头时长与叙事目标。',pattern:/短片|短剧|漫剧|分镜|多场景|多镜头|storyboard|short film|multi.scene|multi.shot|character consistency/i,plan:'结构化剧本 → 角色场景资产 → 分镜与镜头依赖 → 镜头生成 → 连贯性检查。',checks:'人物、场景、道具连续性；叙事清楚、镜头衔接、局部重做影响范围。'},
 {id:'character-assets',title:'人物三视图与风格资产',brief:'固定授权人物参考、身份与服装描述、正侧背视角、目标风格及场景。',pattern:/人物三视图|角色三视图|角色一致性|角色设定|角色多视角|角色资产|角色.{0,8}LoRA|身份一致性|character consistency|character turnaround|character sheet|character asset|identity preservation/i,plan:'结构化角色档案 → 三视图与风格变体 → 复用角色参考生成不同场景 → 检测一致性与局部修正。',checks:'身份、体型、服装和视角正确性；跨镜头保持、风格差异与资产复用。'},
 {id:'visual-qa',title:'视觉质量与广告文字校验',brief:'固定授权品牌/产品图、必须正确的文字和 Logo、目标构图及交付分辨率。',pattern:/画面文字|文字.{0,8}(?:修正|校正|准确|渲染)|字体动画|文字编辑|Logo.{0,8}(?:准确|保真|一致)|4K (?:输出|生成)|supports 4K|text (?:rendering|correction|accuracy)|typography|logo preservation/i,plan:'锁定品牌资产与文案 → 图像生成/编辑 → 检查文字、构图和材质 → 定向修正 → 验证实际交付分辨率。',checks:'文字与品牌信息准确、产品保真、细节质感、修改范围；人工审美和技术检查分别记录。'},
 {id:'agent-workflow',title:'Agent 自动编排与可编辑交付',brief:'明确创作任务、素材、可用模型工具与期望输出。',pattern:/(?:创作|creation|creative|模型|model).{0,20}(?:Agent|路由|routing|编排|orchestrat)|(?:Agent|路由|routing|编排|orchestrat).{0,24}(?:创作|creation|creative|模型|model)|\blibtv-use\b|多模型串联|并行生成|parallel.*generat|generat.*parallel|生成.*并行|并行.*生成/i,plan:'结构化需求 → 任务拆解 → 工具与模型路由 → 保存中间结果 → 失败恢复及局部修改。',checks:'任务完成率、用户操作步骤、人工干预、失败恢复及交付可编辑性。'},
 {id:'sound',title:'声音设计与音画交付',brief:'同一授权视频、台词、声线、情绪、音乐和音效要求。',pattern:/音轨|音频翻译|配音|声线|音画同步|口型同步|原生音视频|audio processing|track separation|audio translation|voiceover|lip.sync|audio.video generation/i,plan:'对白与音乐规划 → 角色声线 → 音轨生成/拆分 → 时间线对齐 → 局部替换。',checks:'发音、情绪、音质、原声保护、音画同步和分轨可编辑性。'}
];
function agentTaskResearchRows(snapshot,now){
 var signals=innovationSignals(snapshot,now);
 return agentCreativeTasks.map(function(task){
  var found=signals.filter(function(s){return task.pattern.test(s.title+' '+s.detail)}).sort(function(a,b){return b.day.localeCompare(a.day)||({product:0,model:1,case:2}[a.type]-{product:0,model:1,case:2}[b.type])});
  var unique=[],keys=new Set();
  // Distinct dated product entries can share a changelog URL. Keep their event identities;
  // other originals are deduplicated across providers, not treated as independent confirmations.
  found.forEach(function(s){var url=newsUrlKey(s.url);if(!url)return;var k=s.type==='product'?url+'|'+newsTitleKey(s.title)+'|'+s.day:url;if(!keys.has(k)){keys.add(k);unique.push(s)}});
  var selected=[],selectedKeys=new Set(),types=new Set();
  // Prefer diverse evidence: latest record, then one example of each other type,
  // then fill the remaining slots without changing the actual evidence count.
  unique.forEach(function(s){if(selected.length<3&&!types.has(s.type)){selected.push(s);selectedKeys.add(s);types.add(s.type)}});
  unique.forEach(function(s){if(selected.length<3&&!selectedKeys.has(s)){selected.push(s);selectedKeys.add(s)}});
  return {id:task.id,title:task.title,brief:task.brief,plan:task.plan,checks:task.checks,signals:selected,signalCount:unique.length,latest:unique[0]&&unique[0].day||''};
 }).filter(function(r){return r.signalCount>0}).sort(function(a,b){return b.latest.localeCompare(a.latest)||b.signalCount-a.signalCount||a.id.localeCompare(b.id)});
}
function agentTaskResearchMarkup(snapshot,now){
 var rows=agentTaskResearchRows(snapshot,now).filter(function(r){return matches([r.title,r.brief,r.plan,r.checks,r.signals.map(function(s){return s.title+' '+s.origin}).join(' ')].join(' '))});
 if(!rows.length)return '';
 var labels={model:'已核实模型发布',product:'官方产品日志',case:'创作者精选线索'};
 return '<section class="briefing-digest-section"><div class="section-head"><h2>Agent 创作任务验证</h2><span class="head-meta">近7天 · '+rows.length+' 个有证据的研究方向</span></div><p class="page-desc">把近期信号转成可与工程师讨论的商业创作任务。以下是候选测试方案，不代表已实现或已取得效果提升。</p><div class="briefing-list">'+rows.map(function(r){return '<article class="briefing-card"><details><summary class="briefing-headline"><span class="briefing-headline-copy"><span class="overview-row-meta">'+esc(r.latest+' · '+r.signalCount+' 条关联记录 · 待实测')+'</span><strong>'+esc(r.title)+'</strong><span>'+esc(r.checks)+'</span></span><span class="briefing-disclosure">'+icon('chevron')+'</span></summary><div class="briefing-expanded"><p><strong>固定输入：</strong>'+esc(r.brief)+'</p><p><strong>Agent 方案假设：</strong>'+esc(r.plan)+'</p><p><strong>对照实验：</strong>先用当前产品流程建立基线，再用候选 Agent 流程处理同一素材和约束；记录模型及工作流版本、失败样本与人工评审。</p><p><strong>质量验收：</strong>'+esc(r.checks)+'</p><p><strong>体验验收：</strong>记录有效交付、首次可用作品所需时间、人工操作与返工；后续用经授权的实际使用数据验证用户是否更愿意持续使用。不填造指标值。</p><h3>近期研究证据</h3>'+r.signals.map(function(s){return '<div class="overview-row"><span>'+esc(labels[s.type]+' · '+s.day+' · '+s.origin)+'<br><strong>'+esc(s.title)+'</strong></span>'+creatorLink(s.url,'原始证据')+'</div>'}).join('')+researchHandoffMarkup(agentResearchHandoff(r))+'</div></details></article>'}).join('')+'</div></section>';
}
function agentResearchCharterMarkup(){
 return '<details class="source-health"><summary>Renoise Agent · 产品研究与质量标准</summary><p class="page-desc">研究目标：让用户更轻松、可控地创作高质量商业作品；以下为研究清单与待验证标准，不是现有能力或已测效果。</p><h3>五项工作职责</h3><p>产品体验优化 · 工作流封装 · 新功能研发 · 竞品差异化 · 创作质量提升</p><h3>与 Agent 工程师协作</h3><p>理解用户简报 → 创意与分镜规划 → 模型路由 → 可复用工具及资产 → 质量检查 → 局部修改 → 可编辑交付。</p><h3>创作环节与验证</h3><p>创意与品牌卖点；人物三视图、角色/产品/场景一致性与风格；分镜及白模；图像、视频动作与镜头连续性；声线、配音、音乐、音效与音画同步；剪辑、落版及交付。</p><p><strong>最小实验：</strong>同素材、同约束、记录模型和工作流版本，比较生成质量、操作效率、可控性及返工成本。无实测不宣称改进。</p><p><strong>研发讨论：</strong>原始证据 → 用户痛点 → 竞品做法 → Agent / 工具 / 节点方案 → 最小实验 → 决策。优先产品广告、产品发布宣传、品牌短片及其他实际创作场景。</p>'+creatorLink('https://github.com/Ai-luren/AI-Creator-Radar/blob/main/docs/renoise-agent-research.md','完整研究纲领')+'</details>';
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
 return pageHead('行业简报','将近期模型、竞品功能和创作者实验关联为可验证的产品机会。','创新机会 · 近7天')+'<div class="tabs briefing-tabs" role="group" aria-label="简报来源">'+tabs+'</div>'+agentTaskResearchMarkup(snapshot,now)+'<p class="page-desc">规则匹配 · 按最近信号日期排序；主题相近不代表技术已兼容或竞品采用该仓库。所有产品构想均为假设，不是发布事实，不使用模型推理 API。</p><section class="briefing-digest-section"><div class="section-head"><h2>值得原型验证</h2><span class="head-meta">'+filtered.length+' 个方向</span></div><div class="briefing-list">'+(body||empty('当前七天快照暂无符合规则的主题信号；不代表没有创新机会。'))+'</div></section>'+innovationExplorationMarkup(snapshot,now)+innovationSurfaceMarkup(snapshot.app,now)+agentResearchCharterMarkup()+'<details class="source-health"><summary>产品创新研究方法与官方入口</summary><p class="page-desc">研究资料不算近期上线事件。LibTV 官网可见版本更新入口，当前自动采集尚未读到功能级日志。</p><div class="briefing-original-links">'+creatorLink('https://higgsfield.ai/blog/inside-higgsfield','Inside Higgsfield · 产品研发复盘')+creatorLink('https://higgsfield.ai/blog/editorials','Higgsfield · 功能拆解')+creatorLink('https://www.liblib.tv/','LibTV · 官方产品与版本更新')+'</div></details>'
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
function platformSpecLabel(spec){
 if(!spec||typeof spec!=='object')return '';
 var parts=[];
 var resolutions=Array.isArray(spec.resolutions)?spec.resolutions.filter(function(x){return typeof x==='string'&&/^(?:\d{3,4}p|1(?:\.5)?K|2K|4K)$/.test(x)}).slice(0,8):[];
 if(resolutions.length)parts.push('输出 '+resolutions.join('/'));
 if(typeof spec.durationSeconds==='string'&&/^\d{1,3}(?:[-/]\d{1,3})*$/.test(spec.durationSeconds))parts.push(spec.durationSeconds.replace(/-/g,'–')+' 秒');
 [['omniReferenceMax','混合参考最多'],['imageReferenceMax','图像参考最多'],['referenceMax','参考最多']].forEach(function(pair){var n=spec[pair[0]];if(Number.isInteger(n)&&n>0&&n<=100)parts.push(pair[1]+n+' 个')});
 if(spec.nativeAudio===true)parts.push('标注原生音频');
 if(Array.isArray(spec.projectRestrictions)&&spec.projectRestrictions.includes('new-projects'))parts.push('含新项目限制');
 if(Array.isArray(spec.projectRestrictions)&&spec.projectRestrictions.includes('old-projects'))parts.push('含旧项目限制');
 return parts.length?'平台文档 · '+parts.join(' · '):'';
}
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
   add({brand:source.vendor,name:e.featureName,dimensions:dimensions.length?dimensions:['other'],url:url,day:null,reviewedOn:chinaDay(e.lastObservedAt),kind:e.surfaceStage==='coming-soon'?'官方预告 · 未上线':'官网自动观察',platformSpec:platformSpecLabel(e.platformSpecs),note:'最近成功读取的公开入口，不代表发布日期或登录后的完整功能。'});
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
   function entry(x){return '<div class="matrix-feature">'+creatorLink(x.url,productReadingTitle(x.name))+'<small>'+esc(x.day?x.kind+' · '+x.day.slice(5):x.kind==='官方预告 · 未上线'?'官方预告 · 未上线':'官网观察 · 非上新')+'</small>'+(x.platformSpec?'<small>'+esc(x.platformSpec)+'</small>':'')+(x.alternates.length?'<details class="matrix-evidence"><summary>补充证据 '+x.alternates.length+' 条</summary>'+x.alternates.map(function(e){return creatorLink(e.url,e.kind+' · '+(e.day||'日期未确认'))}).join('')+'</details>':'')+'</div>'}
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
