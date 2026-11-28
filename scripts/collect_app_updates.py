#!/usr/bin/env python3
"""Observe first-party creative app surfaces; never infer formal model launch."""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from urllib.robotparser import RobotFileParser
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import urllib.error
from urllib.parse import urlencode, urlsplit, urljoin, parse_qs
from collections import Counter

try:
    from scripts.collect_models import SameHostRedirect, USER_AGENT, write_json
    from scripts.collect_product_state import parse_stamp
except ModuleNotFoundError:
    from collect_models import SameHostRedirect, USER_AGENT, write_json
    from collect_product_state import parse_stamp

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"site/data/app-updates.json"
MAX_BYTES=6*1024*1024
HIGGS_CHANGELOG="https://higgsfield.ai/creator-hub/changelog"
DATED_CHANGELOGS={"flova-changelog":"https://www.flova.ai/en/docs/changelog/",
                  "tapnow-changelog":"https://docs.tapnow.ai/en/docs/changelog"}
PRODUCT_SURFACES={"higgsfield-home":"https://higgsfield.ai/","libtv-home":"https://www.liblib.tv/"}
PRODUCT_SURFACE_PARSER_VERSION=2
ALLOWED={"https://jimeng.jianying.com/ai-tool/home",HIGGS_CHANGELOG,*DATED_CHANGELOGS.values(),*PRODUCT_SURFACES.values()}
VOID={"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}

class VisibleText(HTMLParser):
    """Conservative server-rendered text only, not bundled JS or hidden fields."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        hidden=(tag in {"script","style","template","noscript","head","svg"} or "hidden" in attrs
                or attrs.get("aria-hidden")=="true" or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden",attrs.get("style") or "",re.I)))
        if tag not in VOID:
            self.stack.append((tag,hidden or any(v for _,v in self.stack)))
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:
            self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:]
                break
    def handle_data(self,data):
        if not any(v for _,v in self.stack):
            self.parts.append(data)

def parse_surface(page,source):
    p=VisibleText()
    p.feed(page)
    p.close()
    text=" ".join(" ".join(p.parts).split())
    if not all(a in text for a in source["anchors"]):
        raise ValueError("Expected app navigation absent; login, client-rendered shell or changed template")
    prefixes="|".join(re.escape(p) for p in source["modelPrefixes"])
    pattern=rf"(?<![A-Za-z0-9_.-])({prefixes})\s*(\d+(?:\.\d+)+)(?![\d.]|[-_][A-Za-z0-9])"
    labels={}
    for m in re.finditer(pattern,text,re.I):
        tail=text[m.end():]
        # Variant suffixes must not be silently reduced to a base model.
        if re.match(r"\s+(?:pro|lite|fast|mini|plus|preview|turbo|ultra|vip)\b",tail,re.I):
            continue
        prefix=next(x for x in source["modelPrefixes"] if x.casefold()==m[1].casefold())
        name=prefix+" "+m[2]
        key=name.casefold().replace(" ","")
        labels[key]={"modelName":name,"category":"audio" if prefix.casefold()=="seedaudio" else "video" if prefix.casefold()=="seedance" else "image",
                     "claimType":"first-party-visible-label"}
    if not labels:
        raise ValueError("No explicit model labels in readable app surface")
    return labels


class ProductLinks(VisibleText):
    """Visible same-host navigation labels; never execute the page or follow links."""
    def __init__(self):
        super().__init__()
        self.links=[]
        self.active=None

    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs)
        if tag=="a" and not any(hidden for _,hidden in self.stack):
            a=dict(attrs)
            self.active={"href":a.get("href",""),"label":a.get("aria-label",""),"parts":[]}

    def handle_data(self,data):
        super().handle_data(data)
        if self.active is not None and not any(hidden for _,hidden in self.stack):
            self.active["parts"].append(data)

    def handle_endtag(self,tag):
        if tag=="a" and self.active is not None:
            self.links.append(self.active)
            self.active=None
        super().handle_endtag(tag)


def parse_product_surface(page,source):
    """Observe named public product surfaces, not the authenticated editor or changelog."""
    if PRODUCT_SURFACES.get(source["id"])!=source["url"]:
        raise ValueError("Unapproved public product surface")
    parser=ProductLinks()
    parser.feed(page)
    parser.close()
    text=" ".join(" ".join(parser.parts).split())
    rows={}
    def add(name,area,url,stage=None,identity=None):
        name=" ".join(name.split()).strip()
        if not 2<=len(name)<=100 or re.search(r"discount|coupon|pricing|black friday|% off|credits?|促销|折扣|积分|会员|低至|大赛|挑战赛",name,re.I):
            return
        if name in {"独家首发","模型上新","新增","上新","上线","升级","更新","优化","支持","New"}:
            return
        key=hashlib.sha256((identity or (area+"|"+name.casefold()+"|"+url)).encode()).hexdigest()
        rows[key]={"featureName":name,"productArea":area,"featureUrl":url,"category":"app",
                   "claimType":"first-party-product-surface","updateType":"surface-observation"}
        if stage:
            rows[key]["surfaceStage"]=stage
    if source["id"]=="libtv-home":
        if not all(x in text for x in ("LibTV","版本更新记录","新建画布创作")):
            raise ValueError("LibTV public product surface not readable")
        for name in ("LibTV 画布","LibTV Agent BETA","LibTV 3D-BOX","视频生成","图片生成","音频生成","剧本生成","智能剪辑"):
            if name in text:
                add(name,"公开功能入口",source["url"])
        # Project, asset and plugin are public navigation entries, not promises
        # of specific features inside a logged-in workspace.
        nav=text.split("创作",1)[0]
        if "首页" in nav and all(x in nav for x in ("项目","资产","插件")):
            for name in ("项目","资产","插件"):
                add(name,"公开导航入口",source["url"])
        # Read feature updates across the whole platform, not just canvas nodes.
        # Restrict to the publisher's bounded recent-update section.
        if "最近上新" in text and "创作精选" in text.split("最近上新",1)[1]:
            # Use positions, rather than substring membership in the concatenated
            # section: a repeated label outside the section is not new evidence.
            active=False
            model_parts=[]
            for part in parser.parts:
                label=" ".join(part.split()).strip()
                if label=="最近上新":
                    active=True
                    continue
                if active and label=="创作精选":
                    break
                if not active or not label or len(label)>100:
                    continue
                if re.fullmatch(r"(?:独家首发|模型上新)",label):
                    # Adjacent model-name fragments often occupy separate spans.
                    candidate=" ".join(model_parts[-3:])
                    match=re.search(r"([A-Za-z][A-Za-z0-9-]*(?:\s+\d+(?:\.\d+)*|-[0-9]+(?:\.[0-9]+)*)(?:\s+(?:Flash|Pro|Fast|Lite|Mini|Max|Turbo))?)$",candidate,re.I)
                    if match:
                        add(match[1]+label,"首页近期推荐",source["url"])
                    model_parts=[]
                    continue
                if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .+-]{0,60}",label):
                    model_parts.append(label)
                    model_parts=model_parts[-3:]
                else:
                    model_parts=[]
                if len(label)<2:
                    continue
                if re.search(r"教程|课程|视频课|电影节|展评|比赛|挑战赛|活动|直播|获奖|作品精选|用户案例|tutorial|course|contest|festival|webinar",label,re.I):
                    continue
                if (re.search(r"新增|上新|上线|接入|升级|更新|优化|支持|已开放|正式开放|全新|功能发布|独家首发|\bnew\b|(?<=[\u4e00-\u9fff])New$|\b(?:launch(?:ed)?|introducing|now supports|now available)\b",label,re.I)):
                    # Mixed promo and product headlines are retained only if the
                    # explicit feature/model clause can be separated cleanly.
                    label=re.split(r"[·|｜，,；;]",label,maxsplit=1)[0].strip()
                    if re.search(r"新增|上新|上线|接入|升级|更新|优化|支持|已开放|正式开放|全新|功能发布|独家首发|\bnew\b|(?<=[\u4e00-\u9fff])New$|\b(?:launch(?:ed)?|introducing|now supports|now available)\b",label,re.I):
                        add(label,"首页近期推荐",source["url"])
    else:
        if not all(x in text for x in ("Higgsfield","New drops","Cinema Studio")):
            raise ValueError("Higgsfield public product surface not readable")
        # One identity per product route, not one per marketing CTA.
        known={"/short-drama":"Short Drama","/shorts-studio":"Shorts Studio","/gpu":"GPU",
               "/supercomputer":"Supercomputer","/editing-room":"Higgsfield Editing Room",
               "/miracle":"Miracle","/mcp":"MCP","/plugins/after-effects":"Plugins for Premiere Pro / After Effects",
               "/mangaka":"Mangaka"}
        candidates={}
        for link in parser.links:
            try:
                u=urlsplit(urljoin(source["url"],link["href"]))
                if u.scheme!="https" or u.hostname!="higgsfield.ai" or u.username or u.password or u.port not in (None,443):
                    continue
            except ValueError:
                continue
            path=u.path.rstrip("/")
            label=" ".join(" ".join(link["parts"]).split())
            aria=" ".join(link["label"].split())
            named=bool(re.fullmatch(r"/(?:[a-z0-9-]+-studio|editing-room|mangaka|canvas|supercomputer|playable|gpu|shorts|short-drama|miracle|mcp|plugins/after-effects)",path))
            explicit=bool(re.fullmatch(r"/[a-z0-9-]{3,60}",path) and aria.startswith("Open ") and
                          re.search(r"\b(?:studio|editor|editing|tool|agent|canvas|computer)\b",aria,re.I))
            genjutsu=path=="/ai/video" and parse_qs(u.query).get("model")==["genjutsu"]
            if not (named or explicit or genjutsu):
                continue
            raw=re.sub(r"^Open\s+","",aria or label,flags=re.I)
            stage="coming-soon" if re.search(r"\b(?:coming soon|soon)\s*$",raw,re.I) else None
            if re.search(r"^(?:view all|learn more|start generating|try now|see all|get started)\b",raw,re.I):
                continue
            name=known.get(path) or ("Genjutsu" if genjutsu else re.sub(r"\s+(?:New|Top|Soon)$","",raw,flags=re.I))
            if not name or len(name)>100 or re.search(r"^(?:view all|learn more|start generating|try now|see all|get started)\b",name,re.I):
                continue
            url="https://higgsfield.ai"+path+("?model=genjutsu" if genjutsu else "")
            old=candidates.get(url)
            # Prefer the explicit preview label if any link has it; otherwise
            # retain the concise observed product name, not a sentence.
            if not old or len(name)<len(old[0]):
                candidates[url]=(name,stage or (old[1] if old else None))
            elif stage:
                candidates[url]=(old[0],stage)
        for url,(name,stage) in candidates.items():
            add(name,"公开产品入口",url,stage,identity="product-route|"+url)
    if not rows:
        raise ValueError("No explicit named public product capabilities")
    return dict(list(rows.items())[:40])


class ChangelogText(VisibleText):
    def __init__(self):
        super().__init__()
        self.tokens=[]
        self.heading=None
    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs)
        if tag=="h2" and not any(v for _,v in self.stack):
            self.heading=[]
    def handle_endtag(self,tag):
        if tag=="h2" and self.heading is not None:
            self.tokens.append(("heading"," ".join(" ".join(self.heading).split())))
            self.heading=None
        super().handle_endtag(tag)
    def handle_data(self,data):
        if any(v for _,v in self.stack):
            return
        value=" ".join(data.split())
        if not value:
            return
        if self.heading is not None:
            self.heading.append(value)
        else:
            self.tokens.append(("text",value))

def parse_higgs_changelog(page,source):
    p=ChangelogText()
    p.feed(page)
    p.close()
    tokens=p.tokens
    if not any(kind=="text" and value in {"What's new","What’s new"} for kind,value in tokens):
        raise ValueError("Missing changelog heading")
    day=None
    rows=[]
    current=None
    for kind,value in tokens:
        if kind=="text":
            try:
                parsed=datetime.strptime(value,"%B %d, %Y").date().isoformat()
            except ValueError:
                parsed=None
            if parsed:
                day=parsed
                current=None
                continue
        if kind=="heading":
            current={"day":day,"title":value,"tags":[]} if day else None
            if current:
                rows.append(current)
            continue
        if current is not None and len(current["tags"])<8:
            current["tags"].append(value)
    # Require an actual dated changelog structure, not generic homepage navigation.
    valid=[r for r in rows if r["tags"] and r["tags"][0] in {"Release","Feature","Improvement","Fix","Announcement"}]
    if not valid:
        raise ValueError("No dated product changelog entries")
    newest=max(r["day"] for r in valid)
    cutoff=(datetime.fromisoformat(newest)-timedelta(days=30)).date().isoformat()
    output={}
    for row in valid:
        title=row["title"]
        stage=row["tags"][0]
        if row["day"]<cutoff or not title or len(title)>180 or stage not in {"Release","Feature","Improvement"}:
            continue
        # Suppress price/credit-only announcements, not mixed technical updates.
        if re.search(r"black friday|(?:^|\b)(?:pricing|discount|sale|credits?|subscription|bonus|deal|unlimited)(?:\b|$)|refund|promo",title,re.I):
            continue
        product=row["tags"][1] if len(row["tags"])>1 and len(row["tags"][1])<=45 else ""
        # The Models area also contains improvements to already integrated
        # models. Publisher stage takes precedence over the area for these.
        kind="product-improvement" if stage=="Improvement" else "model-integration" if product=="Models" else "product-feature" if stage=="Feature" else "product-release"
        key=hashlib.sha256((row["day"]+"|"+title).encode()).hexdigest()
        output[key]={"featureName":title,"publisherCalendarDay":row["day"],"updateType":kind,
                     "productArea":product,"publisherLabel":stage,"category":"app",
                     "claimType":"first-party-product-changelog"}
    if not output:
        raise ValueError("No relevant recent product changelog entries")
    return output


def parse_dated_changelog(page,source):
    """Dated first-party feature headings; keep source dates, not release guesses."""
    parser=ChangelogText()
    parser.feed(page)
    parser.close()
    tokens=parser.tokens
    marker={"flova-changelog":"Latest Updates","tapnow-changelog":"TapNow changelog"}[source["id"]]
    if not any(value.casefold()==marker.casefold() for _,value in tokens):
        raise ValueError("Expected official changelog heading absent")
    day=None
    version=None
    rows=[]
    current=None
    for kind,value in tokens:
        if value.casefold()==marker.casefold():
            day=None
            current=None
            continue
        if re.fullmatch(r"v\d+(?:\.\d+)+",value):
            version=value
            continue
        try:
            fmt="%Y-%m-%d" if re.fullmatch(r"\d{4}-\d{2}-\d{2}",value) else "%B %d, %Y"
            parsed=datetime.strptime(value,fmt).date().isoformat()
        except ValueError:
            parsed=None
        if parsed:
            day=parsed
            current=None
            continue
        if kind=="heading":
            current={"day":day,"title":value,"version":version,"body":[]} if day else None
            if current:
                rows.append(current)
        elif current is not None and len(current["body"])<8:
            current["body"].append(value)
    # A real entry must have explanatory text, not just a menu or date anchor.
    valid=[row for row in rows if row["body"] and len(" ".join(row["body"]))>=35 and
           row["title"].casefold() not in {"on this page","latest updates","changelog","tapnow changelog"}]
    if not valid:
        raise ValueError("No dated product feature records")
    newest=max(row["day"] for row in valid)
    cutoff=(datetime.fromisoformat(newest)-timedelta(days=30)).date().isoformat()
    output={}
    for row in valid:
        title=row["title"]
        if row["day"]<cutoff or not 3<=len(title)<=180:
            continue
        if re.search(r"\b(?:pricing|discount|credit estimates?|refund|invoic\w*|billing|coupons?|promotions?|black friday|spending|payment|plan renewal)\b",title,re.I):
            continue
        # Only explicit generation-model integration wording; ambiguous titles
        # remain product updates. No model catalog mutations.
        kind="product-update"
        if re.search(r"\b(?:generate (?:images?|videos?|audio|music) with|(?:seedance|seedream|gpt image|kling|wan|nano banana|magi|vidu|gemini)\s+[\w. -]+(?:is here|is live|is available))\b",title,re.I):
            kind="model-integration"
        key=hashlib.sha256((row["day"]+"|"+title).encode()).hexdigest()
        output[key]={"featureName":title,"publisherCalendarDay":row["day"],"updateType":kind,
                     "productArea":"","publisherLabel":"Changelog","category":"app",
                     "claimType":"first-party-product-changelog"}
        if row["version"]:
            output[key]["productVersion"]=row["version"]
    if not output:
        raise ValueError("No relevant dated product updates")
    return output


APPLE_LOOKUP="https://itunes.apple.com/lookup?id=6503676563&country=cn&entity=software"
AIPICK_QUERIES={
    ("即梦","ai-products"),("SeedAudio",None),("可灵","ai-products"),
    ("海螺","ai-products"),("Vidu","ai-products"),("PixVerse","ai-products"),("Sand.ai","ai-models"),
    ("Higgsfield",None),("Flova",None),("TapNow",None),("LibTV",None),
    ("OiiOii",None),("Lovart",None),("Updream",None),("ShotLab",None),("Renoise",None),("Liblib",None),
    ("MiniMax",None),("Midjourney",None),("ElevenLabs",None),("Dreamina",None)
}


def parse_store(payload,source):
    if not isinstance(payload,dict) or payload.get("resultCount")!=1 or not isinstance(payload.get("results"),list) or len(payload["results"])!=1:
        raise ValueError("Store lookup did not return exactly one result")
    row=payload["results"][0]
    if not isinstance(row,dict) or row.get("trackId")!=source["trackId"] or source["expectedName"] not in str(row.get("trackName") or ""):
        raise ValueError("Store app identity mismatch")
    version=row.get("version")
    stamp=parse_stamp(row.get("currentVersionReleaseDate"))
    if not isinstance(version,str) or not re.fullmatch(r"\d+(?:\.\d+){1,4}",version) or not stamp:
        raise ValueError("Store version/date missing or invalid")
    notes=row.get("releaseNotes")
    notes=notes if isinstance(notes,str) else ""
    # Do not republish version-note text. A changed hash signals review of
    # the official store page, not a model release or specific feature.
    digest=hashlib.sha256(notes.encode()).hexdigest() if notes else None
    key="ios-"+version+"-"+(digest or "no-notes")
    return {key:{"storeVersion":version,"storeVersionReleasedAt":stamp.isoformat(),
                 "notesSha256":digest,"hasReleaseNotes":bool(notes),"category":"app",
                 "claimType":"first-party-store-version"}}


def fetch_target(spec,etag):
    term,category=spec["term"],spec.get("category")
    if (term,category) not in AIPICK_QUERIES:
        raise ValueError("Unapproved targeted query")
    params={"mode":"all","window":"7d","by":"published","q":term,"limit":30}
    if category:
        params["category"]=category
    headers={"Accept":"application/json","User-Agent":USER_AGENT}
    if etag:
        headers["If-None-Match"]=etag
    provider=spec.get("provider","AIPick")
    hosts={"AIHOT":"https://aihot.news","AIPick":"https://aipick.news"}
    if provider not in hosts:
        raise ValueError("Unapproved aggregate provider")
    if provider=="AIHOT": headers["User-Agent"]="aihot-api/2.0.0 "+USER_AGENT
    request=urllib.request.Request(hosts[provider]+"/api/v1/items?"+urlencode(params),headers=headers)
    try:
        with urllib.request.build_opener(SameHostRedirect()).open(request,timeout=15) as response:
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:
                raise ValueError("Targeted query response too large")
            payload=json.loads(raw)
            if not isinstance(payload,dict) or not isinstance(payload.get("items"),list) or len(payload["items"])>30:
                raise ValueError("Unexpected targeted query schema")
            rows=payload["items"]
            domains=Counter()
            exact=0
            selected_updates=Counter()
            selected_originals=set()
            for row in rows:
                if not isinstance(row,dict):
                    raise ValueError("Invalid targeted query row")
                links=row.get("links") or {}
                if not isinstance(links,dict):
                    raise ValueError("Invalid targeted query links")
                original=links.get("original")
                host=urlsplit(original).hostname if isinstance(original,str) else None
                domains["wechat" if host=="mp.weixin.qq.com" else "other" if host else "missing"]+=1
                title=str(row.get("title") or "")
                exact+=term.casefold() in (title+" "+str(row.get("originalTitle") or "")).casefold()
                if row.get("selected") is not True or not host or not isinstance(original,str):
                    continue
                u=urlsplit(original)
                if u.username or u.password or u.port not in (None,443):
                    continue
                if u.scheme!="https" and not (u.scheme=="http" and host=="mp.weixin.qq.com" and u.port is None and re.match(r"^/s(?:/|$)",u.path)):
                    continue
                if not re.match(r"^"+re.escape(term)+r"(?![A-Za-z0-9])",title.strip(),re.I):
                    continue
                if re.search(r"测评|实测|教程|提示词|折扣|优惠|黑五|discount|coupon|black friday|review|tutorial",title,re.I):
                    continue
                if re.search(r"上线|接入|上架|支持|integrat|now live|available",title,re.I) and re.search(r"模型|MAGI[- ]?\d|Seedance|Seedream|Kling|GPT[- ]?\d|Gemini|Vidu|Wan\s*\d",title,re.I):
                    lane="modelIntegration"
                elif re.search(r"新功能|新增|更新|推出|发布|上线|升级|功能|工作流|画布|编辑|feature|launch|introduc|release|update|workflow",title,re.I):
                    lane="productFeature"
                else:
                    continue
                key=(lane,u.hostname.lower(),u.path,u.query)
                if key not in selected_originals:
                    selected_originals.add(key)
                    selected_updates[lane]+=1
            # Persist aggregate observation counts only, never article content,
            # URLs, IDs, summaries or original titles from the query results.
            return {"items":len(rows),"wechatOriginalLinks":domains["wechat"],
                    "otherOriginalLinks":domains["other"],"missingOriginalLinks":domains["missing"],
                    "exactTitleMatches":exact,"hasNextCursor":bool(payload.get("nextCursor") or (payload.get("page") or {}).get("nextCursor")),
                    "selectedProductFeatures":selected_updates["productFeature"],"selectedModelIntegrations":selected_updates["modelIntegration"]},response.headers.get("ETag","")
    except urllib.error.HTTPError as exc:
        if exc.code==304 and etag:
            return None,etag
        raise


def collect_targeted(config,previous,now,fetcher=fetch_target):
    if not config:
        return {}
    stamp=now.isoformat(timespec="seconds")
    old={q["id"]:q for q in previous.get("queries",[])}
    rows=[]
    for spec in config["queries"]:
        prior=old.get(spec["id"],{})
        if prior.get("term")!=spec["term"] or prior.get("category")!=spec.get("category") or prior.get("provider","AIPick")!=spec.get("provider","AIPick"):
            prior={}
        rows.append({**prior,**spec})
    service=dict(previous.get("service",{}))
    provider_services={k:dict(v) for k,v in previous.get("providerServices",{}).items()}
    if not provider_services and service.get("error"):
        provider_services["AIPick"]=dict(service)
    cooldown=parse_stamp(service.get("nextAttemptAt")) if not service.get("error") else None
    def provider_due(row):
        wait=parse_stamp(provider_services.get(row.get("provider","AIPick"),{}).get("nextAttemptAt"))
        return not wait or wait<=now
    due=[r for r in rows if provider_due(r) and (not parse_stamp(r.get("nextAttemptAt")) or parse_stamp(r["nextAttemptAt"])<=now)]
    due.sort(key=lambda r:(bool(r.get("lastAttemptAt")),r.get("nextAttemptAt") or "",r.get("priority",50),r["id"]))
    attempted=0
    budget=min(2,max(1,int(config.get("maxProvidersPerRun",1))))
    chosen=[]
    if budget==1 and cooldown and cooldown>now:
        due=[]
    for candidate in due:
        provider=candidate.get("provider","AIPick")
        if provider not in {x.get("provider","AIPick") for x in chosen}:
            chosen.append(candidate)
        if len(chosen)>=budget:
            break
    for row in chosen:
        attempted+=1
        row["lastAttemptAt"]=stamp
        provider_state=provider_services.setdefault(row.get("provider","AIPick"),{})
        try:
            result,etag=fetcher(row,row.get("etag",""))
            if result is None and "counts" not in row:
                raise ValueError("304 without prior counts")
        except (OSError,ValueError,TypeError) as exc:
            failures=int(provider_state.get("consecutiveFailures",0))+1
            delay=min(1440,60*2**min(failures-1,4))
            if isinstance(exc,urllib.error.HTTPError):
                if exc.code in (403,429,503):
                    delay=max(delay,360)
                retry=exc.headers.get("Retry-After","") if exc.headers else ""
                if str(retry).isdigit():
                    delay=max(delay,(int(retry)+59)//60)
            retry_at=(now+timedelta(minutes=delay)).isoformat()
            row.update(status="unavailable",error=type(exc).__name__,nextAttemptAt=retry_at)
            provider_state.update(consecutiveFailures=failures,error=type(exc).__name__,nextAttemptAt=retry_at)
            service.update(consecutiveFailures=failures,error=type(exc).__name__,nextAttemptAt=retry_at)
        else:
            if result is not None:
                row["counts"]=result
                row["countsObservedAt"]=stamp
            row.update(status="unchanged" if result is None else "observed",etag=etag,lastSuccessAt=stamp,error=None,
                       nextAttemptAt=(now+timedelta(minutes=config["intervalMinutes"])).isoformat())
            provider_state.update(consecutiveFailures=0,error=None,lastSuccessAt=stamp,
                           nextAttemptAt=(now+timedelta(minutes=config["globalIntervalMinutes"])).isoformat())
            service.update(consecutiveFailures=0,error=None,lastSuccessAt=stamp,
                           nextAttemptAt=(now+timedelta(minutes=config["globalIntervalMinutes"])).isoformat())
    return {"source":"AIHOT + AIPick" if any(r.get("provider")=="AIHOT" for r in rows) else "AIPick","checkedAt":stamp,"queries":rows,"service":service,"providerServices":provider_services,
            "attemptedThisRun":attempted,
            "policy":"Aggregate query diagnostics only; zero results do not prove absence of product updates. No article redistribution."}


def fetch(source):
    is_store=source.get("type")=="apple-store-version"
    if is_store:
        if source.get("lookupUrl")!=APPLE_LOOKUP or source.get("trackId")!=6503676563:
            raise ValueError("Unapproved store lookup")
        url=APPLE_LOOKUP
    else:
        if source["url"] not in ALLOWED:
            raise ValueError("Unapproved app surface")
        url=source["url"]
    if source.get("type") in {"higgs-changelog","dated-changelog","product-surface"}:
        if source.get("type")=="product-surface" and PRODUCT_SURFACES.get(source["id"])!=url:
            raise ValueError("Unapproved public product surface")
        if source.get("type")=="dated-changelog" and DATED_CHANGELOGS.get(source["id"])!=url:
            raise ValueError("Unapproved dated changelog")
        # Same-host fixed endpoints and robots policy, no alternate identity.
        robots=urllib.request.Request("https://"+urlsplit(url).hostname+"/robots.txt",headers={"User-Agent":USER_AGENT,"Accept":"text/plain"})
        with urllib.request.build_opener(SameHostRedirect()).open(robots,timeout=8) as response:
            raw=response.read(256*1024+1)
        if len(raw)>256*1024 or b"<html" in raw.lower():
            raise ValueError("Invalid robots response")
        rules=RobotFileParser()
        rules.parse(raw.decode("utf-8").splitlines())
        if not rules.can_fetch(USER_AGENT,url):
            raise ValueError("Changelog robots policy disallows access")
    req=urllib.request.Request(url,headers={"Accept":"application/json" if is_store else "text/html","User-Agent":USER_AGENT})
    with urllib.request.build_opener(SameHostRedirect()).open(req,timeout=18) as response:
        data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:
        raise ValueError("App surface exceeds byte limit")
    if source.get("type")=="higgs-changelog":
        return parse_higgs_changelog(data.decode("utf-8"),source)
    if source.get("type")=="dated-changelog":
        return parse_dated_changelog(data.decode("utf-8"),source)
    if source.get("type")=="product-surface":
        return parse_product_surface(data.decode("utf-8"),source)
    return parse_store(json.loads(data),source) if is_store else parse_surface(data.decode("utf-8"),source)

def aggregate_coverage(spec,targeted,now):
    """Selected-report coverage, not a proof of completeness or release facts."""
    ids=spec.get("aggregateQueryIds")
    if not ids:
        return None
    observed={q["id"]:q for q in targeted.get("queries",[])}
    rows=[observed.get(qid,{}) for qid in ids]
    if len(rows)!=2 or {r.get("provider","AIPick") for r in rows}!={"AIHOT","AIPick"}:
        return {"status":"awaiting-aggregate","missingLanes":[]}
    limit=now-timedelta(hours=12)
    fresh=[]
    for r in rows:
        last=parse_stamp(r.get("lastAttemptAt"))
        if not last or last<limit or last>now:
            return {"status":"awaiting-aggregate","missingLanes":[]}
        success=parse_stamp(r.get("lastSuccessAt"))
        counts=r.get("counts") or {}
        if r.get("status") in {"observed","unchanged"} and success and limit<=success<=now and all(k in counts for k in ("selectedProductFeatures","selectedModelIntegrations")):
            fresh.append(counts)
    missing=[lane for lane in ("selectedProductFeatures","selectedModelIntegrations") if not any(c.get(lane,0)>0 for c in fresh)]
    return {"status":"aggregate-gap" if missing else "aggregate-covered-sample","missingLanes":missing,
            "successfulProviders":len(fresh),"policy":"Observed selected-report lanes, not exhaustive event coverage."}



# Recognize content permalinks, not merely an approved domain. Opaque
# redirect links are deliberately not treated as resolved post identities.
PLATFORM_CONTENT_PATHS={
    "douyin":r"/(?:video|note)/[0-9]+",
    "xiaohongshu":r"/(?:explore|discovery/item)/[A-Za-z0-9]+",
    "kuaishou":r"/(?:short-video|photo)/[A-Za-z0-9_-]+",
    "bilibili":r"/(?:video/(?:BV[A-Za-z0-9]+|av[0-9]+)|read/cv[0-9]+|opus/[0-9]+)",
    "weibo":r"/(?:[0-9]+/[A-Za-z0-9]+|detail/[A-Za-z0-9]+|status/[A-Za-z0-9]+)",
    "zhihu":r"/(?:question/[0-9]+/answer/[0-9]+|p/[0-9]+)",
    "wechat-video":r"/(?:web/)?(?:video|feed)/[A-Za-z0-9_-]+",
    "tiktok":r"/@[^/]+/(?:video|photo)/[0-9]+",
    "instagram":r"/(?:p|reel|tv)/[A-Za-z0-9_-]+",
    "youtube":r"/(?:shorts|live|embed)/[A-Za-z0-9_-]{11}",
    "x":r"/(?:[^/]+/status|i/web/status)/[0-9]+",
    "reddit":r"/r/[^/]+/comments/[A-Za-z0-9]+(?:/[^/]+){0,2}",
    "linkedin":r"/(?:posts/[^/]+|feed/update/urn:li:[^/]+|pulse/[^/]+)",
    "facebook":r"/(?:[^/]+/(?:posts|videos)/[^/]+|reel/[0-9]+|groups/[^/]+/posts/[^/]+)",
    "grokipedia":r"/page/[^/]+"
}


def platform_key(original,platforms):
    """Conservative content-pointer recognition; no request or redirect resolution."""
    if not isinstance(original,str):
        return None
    try:
        u=urlsplit(original)
        host=(u.hostname or "").lower().rstrip(".")
        if u.username or u.password or u.scheme not in ("http","https"):
            return None
        if u.port not in (None,443 if u.scheme=="https" else 80):
            return None
    except ValueError:
        return None
    if u.scheme=="http" and host!="mp.weixin.qq.com":
        return None
    from urllib.parse import parse_qs
    path=u.path.rstrip("/")
    query=parse_qs(u.query)
    for spec in platforms:
        if not any(host==domain or host.endswith("."+domain) for domain in spec["domains"]):
            continue
        key=spec["id"]
        if key=="wechat-article":
            valid=host=="mp.weixin.qq.com" and (
                bool(re.fullmatch(r"/s/[A-Za-z0-9_-]+",path)) or
                path=="/s" and bool(query.get("mid")))
        elif key=="wechat-search":
            valid=host=="weixin.sogou.com" and path=="/weixin" and bool(query.get("query"))
        elif key=="youtube":
            valid=(host=="youtu.be" and bool(re.fullmatch(r"/[A-Za-z0-9_-]{11}",path))) or (
                host!="youtu.be" and (path=="/watch" and bool(re.fullmatch(r"[A-Za-z0-9_-]{11}",query.get("v",[""])[0])) or
                bool(re.fullmatch(PLATFORM_CONTENT_PATHS[key],path))))
        elif key=="facebook":
            valid=bool(re.fullmatch(PLATFORM_CONTENT_PATHS[key],path)) or (
                path in ("/story.php","/permalink.php") and bool(query.get("story_fbid")))
        else:
            valid=bool(re.fullmatch(PLATFORM_CONTENT_PATHS.get(key,r"(?!)"),path))
        return key if valid else None
    return None


def snapshot_platform_coverage(platforms,snapshots,now):
    """Recent distinct original pointers in existing selected snapshots only."""
    rows={s["id"]:{"id":s["id"],"label":s["label"],"role":s["role"],"originals":set(),"providers":set(),"hotMentions":set()} for s in platforms}
    source_states=[]
    for provider,payload in snapshots.items():
        if not isinstance(payload,dict):
            continue
        stamp=parse_stamp(payload.get("fetchedAt"))
        source_states.append({"provider":provider,"fetchedAt":payload.get("fetchedAt"),
                              "selectedItems":len(payload.get("items",[])),
                              "hotTopics":len(payload.get("hotTopics",[])),
                              "errors":payload.get("errors",[]),
                              "stale":not stamp or stamp>now or now-stamp>timedelta(hours=12)})
        for item in payload.get("items",[]):
            if not isinstance(item,dict) or item.get("selected") is not True:
                continue
            date=parse_stamp(item.get("publishedAt") or item.get("discoveredAt"))
            if not date or not now-timedelta(days=7)<=date<=now:
                continue
            links=item.get("links") or {}
            if not isinstance(links,dict) or links.get("story"):
                continue
            original=links.get("original")
            key=platform_key(original,platforms)
            if not key:
                continue
            u=urlsplit(original)
            host=(u.hostname or "").lower()
            if host.startswith("www."):
                host=host[4:]
            if host=="twitter.com":
                host="x.com"
            # Preserve meaningful query parameters, remove tracking and fragment.
            from urllib.parse import parse_qsl
            query=urlencode(sorted((k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if not k.lower().startswith("utm_") and k.lower() not in {"fbclid","gclid"}))
            rows[key]["originals"].add((host,u.path.rstrip("/"),query))
            rows[key]["providers"].add(provider)
        # Names in a topic are reported channel mentions, not original links.
        for topic in payload.get("hotTopics",[]):
            if not isinstance(topic,dict):
                continue
            date=parse_stamp(topic.get("latestAt"))
            if not date or not now-timedelta(hours=48)<=date<=now:
                continue
            for name in topic.get("sourceNames",[]):
                if not isinstance(name,str):
                    continue
                for spec in platforms:
                    label=spec["label"]
                    aliases=[label]
                    if spec["id"]=="wechat-article":
                        aliases+=["公众号"]
                    if spec["id"]=="x":
                        aliases+=["Twitter"]
                    if any(name==alias or name.startswith(alias+" ") or name.startswith(alias+" ·") or name.startswith(alias+"：") for alias in aliases):
                        rows[spec["id"]]["hotMentions"].add((provider,name))
    result=[]
    for row in rows.values():
        count=len(row["originals"])
        result.append({"id":row["id"],"label":row["label"],"role":row["role"],
                       "originalCount":count,"providers":sorted(row["providers"]),
                       "hotSourceMentionCount":len(row["hotMentions"]),
                       "status":"original-observed" if count else "hot-mention-only" if row["hotMentions"] else "not-observed"})
    return {"checkedAt":now.isoformat(timespec="seconds"),"window":"7d","sources":source_states,"platforms":result,
            "policy":"Distinct recent selected original-link pointers in available snapshots, not direct platform access, verified update facts or exhaustive coverage. Hot source-name mentions are separate; zero is no sample observation, not an outage."}


def correct_model_improvement(row):
    """Correct a derived label using existing first-party tags, without re-observing."""
    if (row.get("claimType")=="first-party-product-changelog"
            and row.get("publisherLabel")=="Improvement"
            and row.get("productArea")=="Models"
            and row.get("updateType")=="model-integration"):
        return {**row,"updateType":"product-improvement"}
    return row


def collect(config,previous,now,fetcher=fetch,target_fetcher=fetch_target):
    if previous and previous.get("schema")!="app-updates/v1":
        raise ValueError("Unexpected app updates schema")
    stamp=now.isoformat(timespec="seconds")
    prior={s["id"]:s for s in previous.get("sources",[])}
    events={e["id"]:correct_model_improvement(e) if e.get("sourceId")=="higgsfield-changelog" else e
            for e in previous.get("events",[])}
    targeted=collect_targeted(config.get("targetedDiscovery"),previous.get("targetedDiscovery",{}),now,target_fetcher)
    sources=[]
    for spec in config["sources"]:
        old=prior.get(spec["id"],{})
        row={**old,**{k:spec[k] for k in ("id","name","vendor","url","links")}}
        row["type"]=spec.get("type","visible-model-labels")
        if spec.get("role"): row["role"]=spec["role"]
        if spec.get("type")=="navigation-only":
            sources.append({**row,"status":"navigation-only","entries":{},"lastSuccessAt":None,"error":None,"deferred":True})
            continue
        entries=old.get("entries",{})
        if spec["id"]=="higgsfield-changelog" and spec.get("type")=="higgs-changelog":
            entries={k:correct_model_improvement(v) for k,v in entries.items()}
            row["entries"]=entries
        coverage=aggregate_coverage(spec,targeted,now)
        if coverage is not None:
            row["aggregateCoverage"]=coverage
            if coverage["status"]!="aggregate-gap":
                sources.append({**row,"entries":entries,"status":old.get("status","awaiting-aggregate"),"deferred":True,"skipReason":coverage["status"]})
                continue
        row.pop("skipReason",None)
        next_at=parse_stamp(old.get("nextAttemptAt"))
        if next_at and next_at>now:
            sources.append({**row,"deferred":True})
            continue
        try:
            fresh=fetcher(spec)
            if not fresh:
                raise ValueError("Empty app observations")
        except (OSError,ValueError,TypeError) as exc:
            count=int(old.get("consecutiveFailures",0))+1
            sources.append({**row,"entries":entries,"checkedAt":stamp,"lastSuccessAt":old.get("lastSuccessAt"),
                            "status":"probe-unavailable","error":f"{type(exc).__name__}: {str(exc)[:160]}","deferred":False,
                            "consecutiveFailures":count,"nextAttemptAt":(now+timedelta(minutes=min(720,60*2**min(count-1,3)))).isoformat()})
            continue
        surface_migration=(spec.get("type")=="product-surface" and old.get("surfaceParserVersion")!=PRODUCT_SURFACE_PARSER_VERSION)
        if spec.get("type")=="product-surface":
            row["surfaceParserVersion"]=PRODUCT_SURFACE_PARSER_VERSION
        # Absence from home marketing/navigation is NOT a withdrawal or
        # delisting; preserve historical observations, track only current view.
        merged={k:{**v,"visibleInLatestRead":False} for k,v in entries.items()}
        for k,value in fresh.items():
            prev=entries.get(k,{})
            merged[k]={**value,"firstObservedAt":prev.get("firstObservedAt") or stamp,"lastObservedAt":stamp,"visibleInLatestRead":True}
            if k not in entries:
                if value.get("claimType")=="first-party-store-version":
                    kind="store-version-or-notes-changed" if old.get("lastSuccessAt") else "baseline-store-version"
                elif value.get("claimType")=="first-party-product-changelog":
                    kind="new-changelog-entry" if old.get("lastSuccessAt") else "baseline-changelog-entry"
                elif value.get("claimType")=="first-party-product-surface":
                    kind="new-product-surface" if old.get("lastSuccessAt") and not surface_migration else "baseline-product-surface"
                else:
                    kind="new-visible-label" if old.get("lastSuccessAt") else "baseline-visible-label"
                eid=hashlib.sha256((spec["id"]+"|"+k+"|"+stamp).encode()).hexdigest()
                events[eid]={"id":eid,"sourceId":spec["id"],"sourceUrl":spec["url"],"kind":kind,
                             "observedAt":stamp,"releaseDate":None,**value}
        sources.append({**row,"entries":merged,"checkedAt":stamp,"lastSuccessAt":stamp,"status":"observed",
                        "error":None,"deferred":False,"consecutiveFailures":0,
                        "nextAttemptAt":(now+timedelta(minutes=spec["minIntervalMinutes"])).isoformat()})
    return {"schema":"app-updates/v1","checkedAt":stamp,"sources":sources,"targetedDiscovery":targeted,
            "reviewedObservations":config.get("reviewedObservations",[]),
            "events":sorted(events.values(),key=lambda e:(e["observedAt"],e["id"]),reverse=True),
            "summary":{"configuredSources":len(config["sources"]),"successfulThisRun":sum(not s.get("deferred") and s["status"]=="observed" for s in sources),
                       "baselineSources":sum(bool(s.get("lastSuccessAt")) for s in sources),
                       "listedModels":sum(sum(v.get("visibleInLatestRead",False) and v.get("claimType")=="first-party-visible-label" for v in s["entries"].values()) for s in sources),
                       "reviewedObservations":len(config.get("reviewedObservations",[]))},
            "policy":"App visible model label or public feature entry is a product observation, not launch date, availability guarantee or withdrawal. Manual observations separate from automated counts. Private notice and guide links are navigation only."}

def refresh_platform_coverage(config, result, data_dir, now):
    """Rebuild derived coverage from the final on-disk snapshots, without network IO."""
    if result.get("schema")!="app-updates/v1":
        raise ValueError("Unexpected app updates schema")
    snapshots={}
    for provider,filename in (("AIHOT","aihot-items.json"),("AIPick","aipick-data.json")):
        try:
            snapshots[provider]=json.loads((data_dir/filename).read_text(encoding="utf-8"))
        except (OSError,ValueError):
            pass
    return {**result,"platformCoverage":snapshot_platform_coverage(config.get("monitoredPlatforms",[]),snapshots,now)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--report",type=Path)
    p.add_argument("--coverage-only",action="store_true",help="Rebuild coverage after all upstream snapshot writes, without fetching")
    a=p.parse_args()
    read=lambda path:json.loads(path.read_text(encoding="utf-8"))
    config=read(ROOT/"config/app-update-sources.json")
    previous=read(OUTPUT) if OUTPUT.exists() else {}
    if a.coverage_only:
        # No source probe, query budget use or mutation of collector timestamps.
        result=previous
    else:
        result=collect(config,previous,datetime.now(timezone.utc))
    result=refresh_platform_coverage(config,result,ROOT/"site/data",datetime.now(timezone.utc))
    print("Platform coverage:",json.dumps(result["platformCoverage"],ensure_ascii=False))
    if not a.coverage_only:
        print("App updates:",json.dumps(result["summary"],ensure_ascii=False))
        for source in result["sources"]:
            print("[APP]",source["id"],source["status"],"error=",source.get("error"))
        print("AIPick targeted coverage:",json.dumps({"attempted":result["targetedDiscovery"].get("attemptedThisRun"),"queries":[{k:q.get(k) for k in ("id","status","counts","lastSuccessAt","error")} for q in result["targetedDiscovery"].get("queries",[])]},ensure_ascii=False))
    if a.report:
        write_json(a.report,result)
    if not a.dry_run:
        write_json(OUTPUT,result)
    return 0
if __name__=="__main__":
    raise SystemExit(main())
