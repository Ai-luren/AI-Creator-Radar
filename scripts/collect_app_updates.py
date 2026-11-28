#!/usr/bin/env python3
"""Observe first-party creative app surfaces; never infer formal model launch."""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from urllib.robotparser import RobotFileParser
from html.parser import HTMLParser
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
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
MAX_CHANGELOG_ROWS=400
HIGGS_CHANGELOG="https://higgsfield.ai/creator-hub/changelog"
DATED_CHANGELOGS={"flova-changelog":"https://www.flova.ai/en/docs/changelog/",
                  "tapnow-changelog":"https://docs.tapnow.ai/en/docs/changelog",
                  "oiioii-changelog-entry":"https://www.oiioii.ai/zh/changelog"}
PRODUCT_SURFACES={"higgsfield-home":"https://higgsfield.ai/","libtv-home":"https://www.liblib.tv/",
                  "oiioii-model-directory":"https://www.oiioii.ai/zh/explore/models",
                  "tapnow-agent-docs":"https://docs.tapnow.ai/en/docs/mcp/use-tapnow-in-other-agents",
                  "flova-agent-docs":"https://www.flova.ai/en/agent-mcp/",
                  "oiioii-agent-home":"https://www.oiioii.ai/"}
PRODUCT_SURFACE_PARSER_VERSION=2
LIBTV_PLUGIN_REPO="https://github.com/liblib-ai/marketplace"
LIBTV_PLUGIN_API="https://api.github.com/repos/liblib-ai/marketplace/commits?sha=main&per_page=30"
HIGGS_SKILLS_REPO="https://github.com/higgsfield-ai/skills"
HIGGS_SKILLS_API="https://api.github.com/repos/higgsfield-ai/skills/pulls?state=closed&base=main&sort=updated&direction=desc&per_page=30"
GITHUB_PRODUCT_APIS={"libtv-codex-plugin":(LIBTV_PLUGIN_REPO,LIBTV_PLUGIN_API),"higgsfield-skills-features":(HIGGS_SKILLS_REPO,HIGGS_SKILLS_API)}
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
    elif source["id"]=="tapnow-agent-docs":
        if not all(x in text for x in ("Use TapNow in other Agents","TapNow","MCP")):
            raise ValueError("TapNow official MCP guide not readable")
        if "TapNow runs its own MCP service" in text:
            add("TapNow MCP 外部 Agent 创作入口","公开开发生态",source["url"])
        if "Hand over the whole brief" in text and "TapNow Agent" in text:
            add("外部 Agent 委托完整创作任务","公开开发生态",source["url"])
        if "Connect an Agent from the canvas" in text:
            add("从画布连接外部 Agent","公开开发生态",source["url"])
    elif source["id"]=="flova-agent-docs":
        if not all(x in text for x in ("Flova MCP","Flova","Agent")):
            raise ValueError("Flova official MCP guide not readable")
        if "github.com/FlovaAI/flova-plugin" in text and "Skills" in text:
            add("Flova 官方 Agent 插件 / MCP / Skills","公开开发生态",source["url"])
        if "Flova CLI" in text and "cli.flova.ai" in text:
            add("Flova CLI","公开开发生态",source["url"])
    elif source["id"]=="oiioii-agent-home":
        if "OiiOii" not in text or "Oii Studio" not in text:
            raise ValueError("OiiOii public product homepage not readable")
        for pattern,name in ((r"\bOii CLI is live!", "Oii CLI"),(r"\bOii Plugin is live!", "Oii Plugin"),(r"\bDownload Desktop\b","OiiOii 桌面端")):
            if re.search(pattern,text,re.I):
                add(name,"公开开发生态",source["url"])
    elif source["id"]=="oiioii-model-directory":
        # Public model directory only; this is a catalogue listing, not
        # proof of authenticated generation or a dated integration.
        if not ("OiiOii" in text and re.search(r"创作模型|模型介绍|AI Models",text,re.I)):
            raise ValueError("OiiOii model directory heading missing")
        label_pattern=re.compile(r"^(?:使用\s+)?((?:GPT[- ]Image|Seedance|Seedream|SeedAudio|MAGI|Kling|可灵|Vidu|Wan|HappyHorse|Veo|Gemini(?:\s+Omni)?|Grok Imagine|Midjourney|MiniMax(?:\s+H)?|Niji|Nano Banana|Sora)\s*[- ]?\s*V?\d+(?:\.\d+)*(?:\s+(?:Pro|Fast|Lite|Flash|Mini|Max|Turbo|Ultra|Preview|Plus))?)(?![A-Za-z0-9.]|[-_][A-Za-z0-9])",re.I)
        for link in parser.links:
            try:
                u=urlsplit(urljoin(source["url"],link["href"]))
                if u.scheme!="https" or u.hostname!="www.oiioii.ai" or u.username or u.password or u.port not in (None,443):
                    continue
            except ValueError:
                continue
            if not re.fullmatch(r"/zh/(?:[a-z0-9]+(?:[-_/][a-z0-9]+)*)/?",u.path):
                continue
            # Exclude tutorial/blog/navigation and non-model links.
            if re.search(r"/(?:blog|articles|features|campaigns|pricing|price|explore|changelog|faq)(?:/|$)",u.path):
                continue
            label=" ".join(" ".join(link["parts"]).split())
            if re.search(r"已停用|已下线|即将|预告|discontinued|coming soon|deprecated|tutorial|教程|价格",label,re.I):
                continue
            match=label_pattern.match(label)
            if match:
                name=" ".join(match[1].split())
                add(name,"官方模型目录","https://www.oiioii.ai"+u.path.rstrip("/"),"catalog-listed",identity="model-directory|"+re.sub(r"[\s_-]+","",name.casefold()))
        if len(rows)<2:
            raise ValueError("OiiOii model directory cards not readable")
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
    output={}
    # Same bounded page already fetched for recent intelligence. Retain older
    # explicit publisher records too; only presentation applies recent windows.
    for row in sorted(valid,key=lambda r:r["day"],reverse=True):
        title=row["title"]
        stage=row["tags"][0]
        if not title or len(title)>180 or stage not in {"Release","Feature","Improvement"}:
            continue
        # Suppress price/credit-only announcements, not mixed technical updates.
        if re.search(r"black friday|(?:^|\b)(?:pricing|discount|sale|credits?|subscription|bonus|deal|unlimited)(?:\b|$)|refund|promo",title,re.I):
            continue
        product=row["tags"][1] if len(row["tags"])>1 and len(row["tags"][1])<=45 else ""
        # The Models area also contains improvements to already integrated
        # models. Publisher stage takes precedence over the area for these.
        body=" ".join(row["tags"][2:])
        # A model-area tag alone cannot turn an explicit version improvement
        # into a new integration. Audio/Supercomputer can also announce models.
        improvement=stage=="Improvement" or bool(re.search(r"\b(?:update|upgrades?|improvements?|now supports|new build)\b",title,re.I)) or bool(re.search(r"\breplaced the previous version\b",body,re.I))
        explicit_model=bool(re.search(r"\bmodel\b.{0,180}\bnow (?:available|on|in)\b",body,re.I))
        integration=stage=="Feature" and (product=="Models" or (product in {"Audio","Supercomputer","Video Tools","Image Tools"} and explicit_model))
        kind="product-improvement" if improvement else "model-integration" if integration else "product-feature" if stage=="Feature" else "product-release"
        key=hashlib.sha256((row["day"]+"|"+title).encode()).hexdigest()
        output[key]={"featureName":title,"publisherCalendarDay":row["day"],"updateType":kind,
                     "productArea":product,"publisherLabel":stage,"category":"app",
                     "claimType":"first-party-product-changelog"}
    if not output:
        raise ValueError("No relevant dated product changelog entries")
    return dict(list(output.items())[:MAX_CHANGELOG_ROWS])


def parse_month_changelog(page,source):
    """Official month-precision product versions; never invent a day or new model launch."""
    if source.get("id")!="oiioii-changelog-entry":
        raise ValueError("Unapproved month changelog")
    parser=ChangelogText()
    parser.feed(page)
    parser.close()
    if not any(v in {"更新日志","OiiOii 的新版本"} for _,v in parser.tokens):
        raise ValueError("Expected OiiOii changelog marker absent")
    rows=[]
    current=None
    for kind,value in parser.tokens:
        if kind=="heading":
            current=None
            match=re.fullmatch(r"(v\d+(?:\.\d+)+)\s*[—–-]\s*(.{2,120}?)\s*[（(](\d{4}-\d{2})[）)]",value)
            if match:
                version,title,month=match.groups()
                try:
                    datetime.strptime(month,"%Y-%m")
                except ValueError:
                    continue
                current={"version":version,"title":title,"month":month,"body":[]}
                rows.append(current)
        elif current is not None and len(current["body"])<8:
            current["body"].append(value)
    output={}
    for row in rows:
        if len(" ".join(row["body"]))<12 or re.search(r"优惠|价格|促销|积分|宣传片",row["title"]):
            continue
        key=hashlib.sha256((row["month"]+"|"+row["version"]+"|"+row["title"]).encode()).hexdigest()
        output[key]={"featureName":row["title"],"productVersion":row["version"],
                     "publisherCalendarMonth":row["month"],"datePrecision":"month",
                     "updateType":"product-release","productArea":"平台版本","publisherLabel":"Changelog",
                     "category":"app","claimType":"first-party-product-milestone"}
        # Preserve individually named new render backends in this version's
        # explicitly dated paragraph. The month is not a precise launch date.
        for paragraph in row["body"]:
            match=re.fullmatch(r"新增[：:]\s*(.{3,100}?)\s*作为渲染后端[。.]?",paragraph)
            if not match:
                continue
            names=re.split(r"\s*(?:、|和|及|与|，|,)\s*",match[1])
            if not 1<=len(names)<=5 or not all(re.fullmatch(r"(?:Sora|Veo|Seedance|Kling|Vidu|Wan|MiniMax H|MAGI)[ -]?\d+(?:\.\d+)*(?:\s+(?:Pro|Fast|Flash|Mini|Max))?",n,re.I) for n in names):
                continue
            for name in names:
                ident=hashlib.sha256((row["month"]+"|"+row["version"]+"|render-backend|"+name.casefold()).encode()).hexdigest()
                output[ident]={"featureName":name,"productVersion":row["version"],
                               "publisherCalendarMonth":row["month"],"datePrecision":"month",
                               "updateType":"model-integration","productArea":"新增渲染后端",
                               "publisherLabel":"Changelog","category":"app","claimType":"first-party-product-milestone"}
    if not output:
        raise ValueError("No explicit monthly product versions")
    return dict(list(output.items())[:MAX_CHANGELOG_ROWS])


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
    month=None
    version=None
    rows=[]
    current=None
    for kind,value in tokens:
        if value.casefold()==marker.casefold():
            day=None
            month=None
            current=None
            continue
        if re.fullmatch(r"v\d+(?:\.\d+)+",value):
            version=value
            continue
        month_match=re.fullmatch(r"(\d{4}-\d{2})(?:\s*·\s*Flova\s+(\d+(?:\.\d+)+))?",value)
        if source["id"]=="flova-changelog" and month_match:
            try:
                datetime.strptime(month_match[1],"%Y-%m")
            except ValueError:
                day=None
                month=None
                current=None
                continue
            day=None
            month=month_match[1]
            version="v"+month_match[2] if month_match[2] else None
            current=None
            continue
        try:
            fmt="%Y-%m-%d" if re.fullmatch(r"\d{4}-\d{2}-\d{2}",value) else "%B %d, %Y"
            parsed=datetime.strptime(value,fmt).date().isoformat()
        except ValueError:
            parsed=None
        if parsed:
            day=parsed
            month=None
            current=None
            continue
        if kind=="heading":
            current={"day":day,"month":month,"title":value,"version":version,"body":[]} if day or month else None
            if current:
                rows.append(current)
        elif current is not None and len(current["body"])<8:
            current["body"].append(value)
    # A real entry must have explanatory text, not just a menu or date anchor.
    valid=[row for row in rows if row["body"] and len(" ".join(row["body"]))>=35 and
           row["title"].casefold() not in {"on this page","latest updates","changelog","tapnow changelog"}]
    if not valid:
        raise ValueError("No dated product feature records")
    output={}
    for row in sorted(valid,key=lambda r:r["day"] or r["month"],reverse=True):
        title=row["title"]
        if not 3<=len(title)<=180:
            continue
        if re.search(r"\b(?:pricing|discount|credit estimates?|refund|invoic\w*|billing|coupons?|promotions?|black friday|spending|payment|plan renewal)\b",title,re.I):
            continue
        # Only explicit generation-model integration wording; ambiguous titles
        # remain product updates. No model catalog mutations.
        kind="product-update"
        if re.search(r"\b(?:now supports|adds?|upgrades?|update|improvements?)\b",title,re.I):
            kind="product-improvement"
        if re.search(r"\b(?:generate (?:images?|videos?|audio|music) with|generate with\s+(?:seedance|seedream|seed audio|gpt image|kling|wan|nano banana|magi|vidu|gemini|minimax|veo|sora)\s+[\d]|(?:seedance|seedream|seed audio|gpt image|kling|wan|nano banana|magi|vidu|gemini|minimax|veo|sora)\s+[\w. -]+(?:is here|is live|is available))\b",title,re.I) and kind!="product-improvement":
            kind="model-integration"
        key=hashlib.sha256(((row["day"] or row["month"])+"|"+title).encode()).hexdigest()
        output[key]={"featureName":title,"updateType":kind,"productArea":"","publisherLabel":"Changelog","category":"app",
                     **({"publisherCalendarDay":row["day"],"claimType":"first-party-product-changelog"} if row["day"] else
                        {"publisherCalendarMonth":row["month"],"datePrecision":"month","claimType":"first-party-product-milestone"})}
        if row["version"]:
            output[key]["productVersion"]=row["version"]
    if not output:
        raise ValueError("No relevant dated product updates")
    return dict(list(output.items())[:MAX_CHANGELOG_ROWS])


APPLE_LOOKUP="https://itunes.apple.com/lookup?id=6503676563&country=cn&entity=software"
# Fixed app identities and store regions; never accept arbitrary lookup URLs.
APPLE_STORES={
    "jimeng-ios-cn":(6503676563,"cn","即梦"),
    "xiaoyunque-ios-cn":(6746231056,"cn","小云雀"),
    "pippit-ios-sg":(6756709583,"sg","Pippit"),
    "dreamina-ios-sg":(6749606485,"sg","Dreamina"),
    "gemini-ios-us":(6477489729,"us","Google Gemini"),
}

def approved_store_url(source):
    identity=APPLE_STORES.get(source.get("id"))
    if not identity:
        raise ValueError("Unapproved store lookup")
    track,country,name=identity
    url="https://itunes.apple.com/lookup?"+urlencode({"id":track,"country":country,"entity":"software"})
    if source.get("trackId")!=track or source.get("expectedName")!=name or source.get("lookupUrl")!=url or source.get("url")!=f"https://apps.apple.com/{country}/app/id{track}":
        raise ValueError("Unapproved store lookup")
    return url

AIPICK_QUERIES={
    ("即梦","ai-products"),("SeedAudio",None),("可灵","ai-products"),
    ("海螺","ai-products"),("Vidu","ai-products"),("PixVerse","ai-products"),("Sand.ai","ai-models"),
    ("Higgsfield",None),("Flova",None),("TapNow",None),("LibTV",None),
    ("OiiOii",None),("Lovart",None),("Updream",None),("ShotLab",None),("Renoise",None),("Liblib",None),
    ("MiniMax",None),("Midjourney",None),("ElevenLabs",None),("Dreamina",None),
    ("小云雀",None),("Pippit",None),("Gemini","ai-products")
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


# Exact model names are derived only from verified release rows, not arbitrary
# article text or external instructions. No URL/host is supplied by a model.
PRIMARY_CALENDAR_DAYS=3
FOLLOWUP_CALENDAR_DAYS=7
REVIEW_CALENDAR_DAYS=30
def china_calendar_day(now):
    return now.astimezone(timezone(timedelta(hours=8))).date()

def release_calendar_age(day, now):
    try:
        return (china_calendar_day(now)-datetime.strptime(day,"%Y-%m-%d").date()).days
    except (TypeError,ValueError):
        return None

MODEL_WATCH_BRANDS=("Higgsfield","LibTV","TapNow","OiiOii","Flova","小云雀","Pippit","即梦","Dreamina","Gemini")
MODEL_WATCH_NAME=re.compile(r"^(?:Seedance|Seedream|SeedAudio|MAGI|Kling|可灵|Vidu|Wan|HappyHorse|Veo|Gemini|GPT[- ]Image|Nano Banana|Hailuo|海螺|PixVerse|MiniMax|Niji|Midjourney|Suno|ElevenLabs|Scribe|Eleven|HY[- ]?3D)(?:[ -]|\d|$)",re.I)
def valid_watch_term(term):
    return isinstance(term,str) and len(term)<=80 and bool(MODEL_WATCH_NAME.match(term)) and bool(re.fullmatch(r"[\w .+\-]+",term)) and bool(re.search(r"\d",term))

def model_watch_queries(releases,now):
    candidates=[]
    seen=set()
    for row in releases or []:
        if not isinstance(row,dict):
            continue
        name=row.get("modelName")
        day=row.get("publishedAt")
        try:
            published=datetime.strptime(day,"%Y-%m-%d").replace(tzinfo=timezone.utc)
            url=urlsplit(row.get("url") or "")
        except (TypeError,ValueError):
            continue
        age=release_calendar_age(day,now)
        if not (age is not None and 0<=age<FOLLOWUP_CALENDAR_DAYS and
                row.get("category") in {"video","image","audio","music","tts","speech","audio-other","llm"} and
                row.get("modelFamilyId") and row.get("modelVersionId") and row.get("verifiedAt") and
                row.get("evidenceType") in {"official-release","official-model-card"} and
                row.get("verificationStatus")!="pending" and url.scheme=="https" and url.hostname and
                not url.username and not url.password and valid_watch_term(name)):
            continue
        key=(row["modelFamilyId"],row["modelVersionId"])
        if key in seen:
            continue
        seen.add(key)
        candidates.append((row,name,day))
    candidates.sort(key=lambda x:(release_calendar_age(x[2],now)<PRIMARY_CALENDAR_DAYS,x[0].get("category") in {"video","image","audio","music","tts","speech","audio-other"},x[2],x[0].get("category")=="video",x[1]),reverse=True)
    # At most three active model watches. Two provider slots remain the same.
    out=[]
    for row,name,day in candidates[:3]:
        key=hashlib.sha256((row["modelFamilyId"]+"|"+row["modelVersionId"]+"|"+day).encode()).hexdigest()[:20]
        primary=release_calendar_age(day,now)<PRIMARY_CALENDAR_DAYS
        for provider in ("AIHOT","AIPick"):
            out.append({"id":"model-watch-"+key+"-"+provider.lower(),"term":name,"label":name,"provider":provider,
                        "priority":-10 if primary else 10,"intervalMinutes":360 if primary else 720,"watchWindow":"primary-3d" if primary else "followup-7d","modelWatch":True,"modelFamilyId":row["modelFamilyId"],
                        "modelVersionId":row["modelVersionId"],"publisherCalendarDay":day})
    return out

def model_watch_pattern(term):
    # Accept spaces/hyphens between canonical name components, not another
    # numeric version or a named variant of the base model.
    parts=re.split(r"[\s_-]+",term.strip())
    core=r"[\s_-]*".join(re.escape(part) for part in parts)
    return re.compile(r"(?<![A-Za-z0-9])"+core+r"(?![A-Za-z0-9.]|[-_][A-Za-z0-9]|\s+(?:pro|fast|lite|flash|mini|max|turbo|ultra|preview|plus)\b)",re.I)


def model_watch_counts(rows,term):
    # Metadata only. Counts are discovery signals, not published launch claims.
    pattern=model_watch_pattern(term)
    by_brand={b:0 for b in MODEL_WATCH_BRANDS}
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or row.get("selected") is not True:
            continue
        title=str(row.get("title") or "")
        if not pattern.search(title) or re.search(r"折扣|优惠券|黑五|discount|coupon|black friday",title,re.I):
            continue
        links=row.get("links") or {}
        original=links.get("original") if isinstance(links,dict) else None
        if not isinstance(original,str) or links.get("story"):
            continue
        try:
            u=urlsplit(original)
            if not u.hostname or u.username or u.password or u.port not in (None,443) or u.scheme!="https":
                continue
        except ValueError:
            continue
        for brand in MODEL_WATCH_BRANDS:
            if not re.search(r"(?<![A-Za-z0-9])"+re.escape(brand)+r"(?![A-Za-z0-9])",title,re.I):
                continue
            k=(brand,u.hostname,u.path,u.query)
            if k not in seen:
                seen.add(k)
                by_brand[brand]+=1
    return by_brand

def creator_launch_signal(title,term):
    """Creator coverage is a discovery lead, not an adoption or sponsorship claim."""
    if not isinstance(title,str) or not isinstance(term,str) or not term.strip():
        return False
    if re.search(r"折扣|优惠|黑五|促销|赠送|抽奖|discount|coupon|black friday|giveaway",title,re.I):
        return False
    return bool(re.search(r"(?<![A-Za-z0-9])"+re.escape(term)+r"(?![A-Za-z0-9])",title,re.I)
                and re.search(r"实测|测评|评测|体验|上手|教程|演示|制作|案例|review|tutorial|demo|hands[- ]on|workflow",title,re.I)
                and re.search(r"新功能|新增|发布|上线|上新|接入|升级|首发|功能|模型|工作流|工作室|画布|feature|model|launch|workflow|studio|canvas",title,re.I))


def fetch_target(spec,etag):
    term,category=spec["term"],spec.get("category")
    if (term,category) not in AIPICK_QUERIES and not (spec.get("modelWatch") is True and category is None and valid_watch_term(term)):
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
                if not links.get("story") and creator_launch_signal(title,term):
                    key=("creatorSignal",u.hostname.lower(),u.path,u.query)
                    if key not in selected_originals:
                        selected_originals.add(key)
                        selected_updates["creatorSignal"]+=1
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
                    "selectedProductFeatures":selected_updates["productFeature"],"selectedModelIntegrations":selected_updates["modelIntegration"],
                    "selectedCreatorSignals":selected_updates["creatorSignal"],
                    **({"modelWatchBrandMentions":model_watch_counts(rows,term)} if spec.get("modelWatch") else {})},response.headers.get("ETag","")
    except urllib.error.HTTPError as exc:
        if exc.code==304 and etag:
            return None,etag
        raise


def collect_targeted(config,previous,now,fetcher=fetch_target,releases=None):
    if not config:
        return {}
    stamp=now.isoformat(timespec="seconds")
    old={q["id"]:q for q in previous.get("queries",[])}
    rows=[]
    for spec in [*config["queries"],*model_watch_queries(releases,now)]:
        prior=old.get(spec["id"],{})
        if prior.get("term")!=spec["term"] or prior.get("category")!=spec.get("category") or prior.get("provider","AIPick")!=spec.get("provider","AIPick"):
            prior={}
        rows.append({**prior,**spec,"queuedAt":prior.get("queuedAt") or stamp})
    service=dict(previous.get("service",{}))
    provider_services={k:dict(v) for k,v in previous.get("providerServices",{}).items()}
    if not provider_services and service.get("error"):
        provider_services["AIPick"]=dict(service)
    cooldown=parse_stamp(service.get("nextAttemptAt")) if not service.get("error") else None
    def provider_due(row):
        wait=parse_stamp(provider_services.get(row.get("provider","AIPick"),{}).get("nextAttemptAt"))
        return not wait or wait<=now
    due=[r for r in rows if provider_due(r) and (not parse_stamp(r.get("nextAttemptAt")) or parse_stamp(r["nextAttemptAt"])<=now)]
    def priority_key(row):
        retry=parse_stamp(row.get("nextAttemptAt"))
        last=parse_stamp(row.get("lastAttemptAt"))
        queued=parse_stamp(row.get("queuedAt"))
        overdue=(retry or queued or now)<=now-timedelta(hours=24)
        # New three-day watches are urgent; repeat watches never monopolize
        # provider slots. Ordinary overdue queries retain a bounded fairness
        # escape. Four-to-seven-day watches are follow-up, not launch alerts.
        if row.get("modelWatch"):
            primary=row.get("watchWindow")=="primary-3d"
            tier=(-30 if not last else 5) if primary else (10 if not last else 15)
        else:
            tier=-20 if overdue else int(row.get("priority",50))
        # The first query of a new model must outrank overdue routine work.
        # Within the urgent tier, query the newest published model first,
        # rather than letting its hashed identifier determine launch order.
        launch_age=release_calendar_age(row.get("publisherCalendarDay"),now) if tier==-30 else None
        return (tier,launch_age if launch_age is not None else 0,bool(last),row.get("nextAttemptAt") or "",row.get("lastAttemptAt") or "",row["id"])
    due.sort(key=priority_key)
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
                       nextAttemptAt=(now+timedelta(minutes=max(360,int(row.get("intervalMinutes",config["intervalMinutes"]))))).isoformat())
            provider_state.update(consecutiveFailures=0,error=None,lastSuccessAt=stamp,
                           nextAttemptAt=(now+timedelta(minutes=config["globalIntervalMinutes"])).isoformat())
            service.update(consecutiveFailures=0,error=None,lastSuccessAt=stamp,
                           nextAttemptAt=(now+timedelta(minutes=config["globalIntervalMinutes"])).isoformat())
    return {"source":"AIHOT + AIPick" if any(r.get("provider")=="AIHOT" for r in rows) else "AIPick","checkedAt":stamp,"queries":rows,"service":service,"providerServices":provider_services,
            "attemptedThisRun":attempted,
            "recentPolicy":{"calendarTimezone":"Asia/Shanghai","primaryCalendarDays":PRIMARY_CALENDAR_DAYS,"followupCalendarDays":FOLLOWUP_CALENDAR_DAYS,"reviewCalendarDays":REVIEW_CALENDAR_DAYS},
            "policy":"Aggregate query diagnostics only; zero results do not prove absence of product updates. No article redistribution."}


def parse_libtv_plugin_releases(payload,source):
    """Read only explicit version-release commits on the official production plugin repo."""
    if source.get("id")!="libtv-codex-plugin" or source.get("url")!=LIBTV_PLUGIN_REPO or not isinstance(payload,list):
        raise ValueError("Unexpected LibTV plugin release source")
    rows={}
    for item in payload[:30]:
        if not isinstance(item,dict):
            continue
        sha=item.get("sha","")
        if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{40}",sha):
            continue
        commit=item.get("commit") or {}
        if not isinstance(commit,dict):
            continue
        lines=str(commit.get("message","")).splitlines()
        if not lines:
            continue
        # Merge announcements may carry the release subject as their second
        # paragraph. Prefer the main-branch merge record over its child commit.
        subject=lines[0]
        if re.fullmatch(r"Merge pull request #\d+ from liblib-ai/.+",subject) and len(item.get("parents",[]))>=2:
            subject=next((line for line in lines[1:] if line.strip()),"")
        match=re.fullmatch(r"feat\(plugin\):\s*发布 LibTV (\d+\.\d+\.\d+)(?:[，,]\s*(.{1,100}))?",subject)
        if not match:
            continue
        stamp=parse_stamp((commit.get("committer") or {}).get("date"))
        if stamp is None:
            continue
        version,detail=match.groups()
        key=hashlib.sha256(("libtv-codex-plugin|"+version).encode()).hexdigest()
        url=LIBTV_PLUGIN_REPO+"/commit/"+sha
        if item.get("html_url")!=url:
            continue
        if key in rows:
            continue
        rows[key]={"featureName":"LibTV Codex 插件 "+version+(" · "+detail if detail else ""),
                   "publisherCalendarDay":stamp.date().isoformat(),"publisherCommitAt":stamp.isoformat(),
                   "productVersion":version,"productArea":"Codex / MCP / Skills",
                   "publisherLabel":"官方插件发布提交","updateType":"product-release",
                   "category":"app","claimType":"first-party-plugin-release","sourceUrl":url}
    if not rows:
        raise ValueError("No explicit production plugin version release commits")
    return rows


def parse_higgs_skills_features(payload,source):
    """Only merged, explicitly user-facing Skills features; not website launches."""
    if source.get("id")!="higgsfield-skills-features" or source.get("url")!=HIGGS_SKILLS_REPO or not isinstance(payload,list):
        raise ValueError("Unexpected Higgsfield Skills source")
    rows={}
    for item in payload[:30]:
        if not isinstance(item,dict):
            continue
        number=item.get("number")
        stamp=parse_stamp(item.get("merged_at"))
        url=item.get("html_url")
        title=str(item.get("title") or "").strip()
        body=str(item.get("body") or "").strip()
        base=item.get("base") or {}
        if type(number) is not int or number<1 or not stamp or url!=HIGGS_SKILLS_REPO+"/pull/"+str(number):
            continue
        if base.get("ref")!="main" or (base.get("repo") or {}).get("full_name")!="higgsfield-ai/skills":
            continue
        if not body or len(title)>140 or not re.match(r"^(?:feat(?:\([\w-]+\))?:\s*|Add\s+)",title,re.I):
            continue
        if not re.search(r"\b(?:skill|workflow|generate|generation|model|image|video|audio|GIF|SVG|agent|routing)\b",title,re.I):
            continue
        if re.search(r"\b(?:pricing|discount|credit|docs?|test|install|typo|dependency|readme|fix)\b",title,re.I):
            continue
        name=re.sub(r"^feat(?:\([\w-]+\))?:\s*","",title,flags=re.I)
        key=hashlib.sha256(("higgsfield-skills-features|"+str(number)).encode()).hexdigest()
        rows[key]={"featureName":"Higgsfield Skills · "+name,"publisherCalendarDay":stamp.date().isoformat(),
                   "publisherCommitAt":stamp.isoformat(),"productArea":"Agent / Skills",
                   "publisherLabel":"官方功能合并记录","updateType":"product-feature","category":"app",
                   "claimType":"first-party-developer-change","sourceUrl":url}
    if not rows:
        raise ValueError("No explicit merged user-facing Skills features")
    return rows


class PluginNoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Plugin API redirect rejected", headers, fp)


def plugin_request(source_id="libtv-codex-plugin"):
    """Send optional Actions token only to a fixed approved GitHub API URL."""
    if source_id not in GITHUB_PRODUCT_APIS:
        raise ValueError("Unapproved GitHub product API")
    headers={"Accept":"application/vnd.github+json","User-Agent":USER_AGENT,"X-GitHub-Api-Version":"2022-11-28"}
    token=os.environ.get("RADAR_GITHUB_API_TOKEN","").strip()
    if token:
        headers["Authorization"]="Bearer "+token
    return urllib.request.Request(GITHUB_PRODUCT_APIS[source_id][1],headers=headers)


PRODUCT_DISCOVERY_FEEDS={
    "aiguanchao-featured":"https://aiguanchao.com/feed/featured.xml",
    "kreatorflow-creator-news":"https://kreatorflow.ai/news/rss.xml",
}
DISCOVERY_BRANDS=("Higgsfield","LibTV","TapNow","OiiOii","Flova","即梦","Dreamina","小云雀","Pippit","Gemini")
def parse_product_discovery_feed(raw,source,now):
    """Public RSS titles and source pointers only; report date is not launch."""
    if PRODUCT_DISCOVERY_FEEDS.get(source.get("id"))!=source.get("url"):
        raise ValueError("Unapproved product discovery feed")
    if b"<!doctype" in raw.lower() or b"<!entity" in raw.lower():
        raise ValueError("Unexpected feed document declaration")
    try:
        root=ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("Invalid RSS XML") from exc
    def tag(node):
        return node.tag.rsplit("}",1)[-1].lower()
    if tag(root) not in {"rss","feed","rdf"}:
        raise ValueError("Expected RSS or Atom feed")
    rows={}
    for item in [x for x in root.iter() if tag(x) in {"item","entry"}][:100]:
        fields={tag(x):(x.text or "").strip() for x in item}
        title=" ".join(fields.get("title","").split())
        if not 4<=len(title)<=200 or re.search(r"折扣|优惠|黑五|积分|会员促销|\b(?:pricing|discount|coupon|black friday|giveaway|contest)\b",title,re.I):
            continue
        if not re.search(r"上线|发布|推出|上新|更新|接入|支持|功能|工作流|\b(?:launch(?:es|ed)?|release[sd]?|introduc\w*|update[sd]?|integrat\w*|feature|now available|now supports|workflow)\b",title,re.I):
            continue
        link=fields.get("link","")
        if not link:
            link=next((x.get("href","") for x in item if tag(x)=="link" and x.get("rel","alternate")=="alternate"),"")
        try:
            u=urlsplit(link)
            if u.scheme!="https" or not u.hostname or u.username or u.password or u.port not in (None,443) or not u.path or u.path=="/":
                continue
            value=fields.get("pubdate") or fields.get("published") or fields.get("updated")
            if not value:
                continue
            try:
                published=parsedate_to_datetime(value)
            except (TypeError,ValueError):
                published=datetime.fromisoformat(value.replace("Z","+00:00"))
            if published.tzinfo is None or published>now or published<now-timedelta(days=7):
                continue
        except (ValueError,TypeError,OverflowError):
            continue
        for brand in DISCOVERY_BRANDS:
            if not re.search(r"(?<![A-Za-z0-9])"+re.escape(brand)+r"(?![A-Za-z0-9])",title,re.I):
                continue
            key=hashlib.sha256((brand+"|"+link).encode()).hexdigest()
            rows[key]={"featureName":title,"reportedBrand":brand,"reportPublishedAt":published.isoformat(),"sourceUrl":link,
                       "category":"app","claimType":"external-product-report","updateType":"discovery-report","productArea":"第三方报道"}
    return rows

def app_probe_retry_at(exc, now, count):
    delay=timedelta(minutes=min(720,60*2**min(count-1,3)))
    if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429,503):
        delay=max(delay,timedelta(hours=6))
        headers=exc.headers or {}
        retry=headers.get("Retry-After","")
        if str(retry).isdigit():
            delay=max(delay,timedelta(seconds=int(retry)))
        reset=headers.get("X-RateLimit-Reset","")
        if str(reset).isdigit() and headers.get("X-RateLimit-Remaining")=="0":
            delay=max(delay,datetime.fromtimestamp(int(reset),timezone.utc)-now+timedelta(minutes=1))
    # Repeated inaccessible/changed pages are not a critical path. A third
    # failure opens a seven-day circuit rather than spending every run on it.
    if count>=3:
        delay=max(delay,timedelta(days=7))
    elif isinstance(exc,urllib.error.HTTPError) and exc.code==403 and (exc.headers or {}).get("X-RateLimit-Remaining")!="0":
        delay=max(delay,timedelta(days=1))
    return (now+delay).isoformat()


def fetch(source):
    is_feed=source.get("type")=="product-discovery-feed"
    is_store=source.get("type")=="apple-store-version"
    is_plugin=source.get("type") in {"github-plugin-release","github-feature-merge"}
    if is_plugin:
        approved=GITHUB_PRODUCT_APIS.get(source.get("id"))
        expected={"libtv-codex-plugin":"github-plugin-release","higgsfield-skills-features":"github-feature-merge"}
        if not approved or source.get("url")!=approved[0] or source.get("type")!=expected.get(source.get("id")):
            raise ValueError("Unapproved GitHub product repository")
        url=approved[1]
    elif is_feed:
        if PRODUCT_DISCOVERY_FEEDS.get(source.get("id"))!=source.get("url"):
            raise ValueError("Unapproved discovery feed")
        url=source["url"]
    elif is_store:
        url=approved_store_url(source)
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
    req=plugin_request(source['id']) if is_plugin else urllib.request.Request(url,headers={"Accept":"application/rss+xml, application/atom+xml, application/xml" if is_feed else "application/json" if is_store else "text/html","User-Agent":USER_AGENT})
    with urllib.request.build_opener(PluginNoRedirect() if is_plugin else SameHostRedirect()).open(req,timeout=18) as response:
        data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:
        raise ValueError("App surface exceeds byte limit")
    if is_feed:
        return parse_product_discovery_feed(data,source,datetime.now(timezone.utc))
    if is_plugin:
        return (parse_higgs_skills_features if source['id']=='higgsfield-skills-features' else parse_libtv_plugin_releases)(json.loads(data),source)
    if source.get("type")=="higgs-changelog":
        return parse_higgs_changelog(data.decode("utf-8"),source)
    if source.get("type")=="dated-changelog":
        return (parse_month_changelog if source["id"]=="oiioii-changelog-entry" else parse_dated_changelog)(data.decode("utf-8"),source)
    if source.get("type")=="product-surface":
        return parse_product_surface(data.decode("utf-8"),source)
    return parse_store(json.loads(data),source) if is_store else parse_surface(data.decode("utf-8"),source)

def readable_competitor_lanes(snapshots,term,now):
    """Only recent selected original links actually present in saved reading data."""
    found=set()
    if not term:
        return found
    brand=re.escape(term)
    for payload in (snapshots or {}).values():
        if not isinstance(payload,dict):
            continue
        stamp=parse_stamp(payload.get("fetchedAt"))
        if not stamp or not now-timedelta(hours=12)<=stamp<=now:
            continue
        for item in payload.get("items",[]):
            if not isinstance(item,dict) or item.get("selected") is not True:
                continue
            when=parse_stamp(item.get("publishedAt"))
            links=item.get("links") or {}
            if not when or not now-timedelta(days=7)<=when<=now or not isinstance(links,dict) or links.get("story"):
                continue
            original=links.get("original")
            if not isinstance(original,str):
                continue
            try:
                u=urlsplit(original)
                if not u.hostname or u.username or u.password or u.port not in (None,443) or not (u.scheme=="https" or u.scheme=="http" and u.hostname=="mp.weixin.qq.com" and re.match(r"^/s(?:/|$)",u.path)):
                    continue
            except ValueError:
                continue
            title=str(item.get("title") or "").strip()
            if not (re.match(r"^"+brand+r"(?![A-Za-z0-9])",title,re.I) or re.search(r"(?:接入|上线|上架|登陆|登录)\s*"+brand+r"(?![A-Za-z0-9])",title,re.I)):
                continue
            if re.search(r"测评|实测|教程|提示词|折扣|优惠|黑五|discount|coupon|black friday|review|tutorial",title,re.I):
                continue
            if re.search(r"上线|接入|上架|支持|integrat|now live|available",title,re.I) and re.search(r"模型|MAGI[- ]?\d|Seedance|Seedream|Kling|GPT[- ]?\d|Gemini|Vidu|Wan\s*\d",title,re.I):
                found.add("selectedModelIntegrations")
            elif re.search(r"新功能|新增|更新|推出|发布|上线|升级|功能|工作流|画布|编辑|feature|launch|introduc|release|update|workflow",title,re.I):
                found.add("selectedProductFeatures")
    return found


def read_selected_snapshots(data_dir):
    snapshots={}
    for provider,filename in (("AIHOT","aihot-items.json"),("AIPick","aipick-data.json")):
        try:
            snapshots[provider]=json.loads((data_dir/filename).read_text(encoding="utf-8"))
        except (OSError,ValueError):
            pass
    return snapshots


def aggregate_coverage(spec,targeted,now,snapshots=None):
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
    lanes=("selectedProductFeatures","selectedModelIntegrations")
    queried={lane for lane in lanes if any(c.get(lane,0)>0 for c in fresh)}
    visible=readable_competitor_lanes(snapshots,spec.get("vendor") or rows[0].get("term"),now)
    missing=[lane for lane in lanes if lane not in queried or lane not in visible]
    return {"status":"aggregate-gap" if missing else "aggregate-covered-sample","missingLanes":missing,
            "queryLanes":sorted(queried),"readableLanes":sorted(visible),
            "successfulProviders":len(fresh),"policy":"Require both query and readable selected evidence; not exhaustive coverage."}



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


def model_watch_official_gap(spec,targeted,previous,now):
    """A recent model-specific two-provider attempt authorizes the existing
    official gap probe, even if generic brand-level query counts look covered.
    Do not skip on mention counts or an unattempted model watch."""
    brand=spec.get("vendor")
    if brand not in MODEL_WATCH_BRANDS or spec.get("type") not in {"higgs-changelog","dated-changelog","product-surface"}:
        return []
    groups={}
    for row in targeted.get("queries",[]):
        if row.get("modelWatch") is True:
            groups.setdefault((row.get("modelFamilyId"),row.get("modelVersionId"),row.get("term")),[]).append(row)
    source_ids={s["id"] for s in previous.get("sources",[]) if s.get("vendor")==brand}
    evidence=[]
    for event in previous.get("events",[]):
        if event.get("sourceId") in source_ids and event.get("claimType")=="first-party-product-changelog" and event.get("updateType")=="model-integration":
            evidence.append((event.get("featureName",""),event.get("publisherCalendarDay","")))
    gaps=[]
    for (_,_,term),rows in groups.items():
        if not valid_watch_term(term) or {r.get("provider") for r in rows}!={"AIHOT","AIPick"}:
            continue
        if any(not (now-timedelta(hours=12)<=(parse_stamp(r.get("lastAttemptAt")) or datetime.min.replace(tzinfo=timezone.utc))<=now) for r in rows):
            continue
        pattern=model_watch_pattern(term)
        day=rows[0].get("publisherCalendarDay") or ""
        if not any(d>=day and pattern.search(name) for name,d in evidence if isinstance(name,str) and isinstance(d,str)):
            gaps.append(term)
    return sorted(set(gaps))


def propagation_feature_name(title,brand):
    """Named feature only; ambiguous or generic titles cannot trigger a probe."""
    if not isinstance(title,str) or not isinstance(brand,str) or not brand:
        return None
    if re.search(r"折扣|优惠|黑五|促销|赠送|抽奖|discount|coupon|black friday|giveaway|pricing",title,re.I):
        return None
    match=re.search(r"(?<![A-Za-z0-9])"+re.escape(brand)+r"(?![A-Za-z0-9])",title,re.I)
    if not match or not (creator_launch_signal(title,brand) or re.search(r"发布|推出|上线|上新|新增|接入|首发|更新|升级|launch|release|introduc|now available",title,re.I)):
        return None
    tail=title[match.end():].strip()
    name=(re.match(r"([\u4e00-\u9fff]{2,8}(?:工作室|导演台|造型室|编辑器|工具箱))",tail)
          or re.search(r'(?:新功能|功能|feature)\s*[「『“"]?([A-Za-z][A-Za-z0-9-]{2,35})(?=[」』”"\s，,。:：]|$)',title,re.I)
          or re.search(r'[「『“"]([^」』”"\n]{3,35})[」』”"]\s*(?:功能|工作流|工具)',title))
    if not name or re.fullmatch(r"new|the|and|with|for|model|feature|workflow|studio|canvas|video|image|audio",name[1],re.I):
        return None
    return name[1]


def propagation_official_gap(spec,previous,snapshots,now):
    """Existing fresh snapshots can authorize an existing official probe once.
    No new endpoint, query, author identity, sponsorship or release inference.
    A successful source read newer than the signal satisfies this probe trigger;
    source cooldown and circuit breaker are still enforced by collect().
    """
    brand=spec.get("vendor")
    if not spec.get("aggregateQueryIds") or not brand or spec.get("type") not in {"higgs-changelog","dated-changelog","product-surface"}:
        return []
    groups={}
    for payload in (snapshots or {}).values():
        if not isinstance(payload,dict):
            continue
        stamp=parse_stamp(payload.get("fetchedAt"))
        if not stamp or not now-timedelta(hours=12)<=stamp<=now:
            continue
        for story,items in ((False,payload.get("items",[])),(True,payload.get("hotTopics",[]))):
            for item in items if isinstance(items,list) else []:
                if not isinstance(item,dict) or not story and item.get("selected") is not True:
                    continue
                date=parse_stamp(item.get("latestAt") if story else item.get("publishedAt"))
                if not date or not now-timedelta(days=3)<=date<=now:
                    continue
                name=propagation_feature_name(item.get("title"),brand)
                if not name:
                    continue
                links=item.get("links") or {}
                if not isinstance(links,dict) or not story and links.get("story"):
                    continue
                url=links.get("story" if story else "original")
                if not isinstance(url,str):
                    continue
                try:
                    u=urlsplit(url)
                    host=u.hostname
                    if not host or u.username or u.password or u.port not in (None,443) or not (u.scheme=="https" or u.scheme=="http" and host=="mp.weixin.qq.com" and re.match(r"^/s(?:/|$)",u.path)):
                        continue
                except ValueError:
                    continue
                group=groups.setdefault(name.casefold(),{"name":name,"originals":set(),"story":False,"latest":date})
                if story:
                    labels=item.get("sourceNames")
                    if host not in {"aihot.news","aipick.news"} or not re.fullmatch(r"/story/[A-Za-z0-9-]{1,128}",u.path) or not isinstance(labels,list) or len({x.strip() for x in labels if isinstance(x,str) and x.strip()})<2:
                        continue
                    group["story"]=True
                else:
                    # Drop tracking query parameters; preserve identifiers on
                    # query-addressed WeChat and YouTube permalinks.
                    q=parse_qs(u.query)
                    identity=tuple((k,tuple(q[k])) for k in ("__biz","mid","idx","sn","v") if k in q)
                    group["originals"].add((host.lower(),u.path.rstrip("/"),identity))
                group["latest"]=max(group["latest"],date)
    last=parse_stamp(next((s.get("lastSuccessAt") for s in previous.get("sources",[]) if s.get("id")==spec["id"]),None))
    source_ids={s["id"] for s in previous.get("sources",[]) if s.get("vendor")==brand}|{spec["id"]}
    evidence=[e.get("featureName","") for e in previous.get("events",[]) if e.get("sourceId") in source_ids and e.get("claimType") in {"first-party-product-changelog","first-party-plugin-release","first-party-developer-change"}]
    result=[]
    for g in groups.values():
        if not (g["story"] or len(g["originals"])>=2) or last and last>=g["latest"]:
            continue
        name=g["name"]
        pattern=re.compile((r"(?<![A-Za-z0-9])" if re.match(r"[A-Za-z0-9]",name) else "")+re.escape(name)+(r"(?![A-Za-z0-9])" if re.search(r"[A-Za-z0-9]$",name) else ""),re.I)
        if not any(isinstance(e,str) and pattern.search(e) for e in evidence):
            result.append(name)
    return sorted(result)[:3]


def collect(config,previous,now,fetcher=fetch,target_fetcher=fetch_target,releases=None,snapshots=None):
    if previous and previous.get("schema")!="app-updates/v1":
        raise ValueError("Unexpected app updates schema")
    stamp=now.isoformat(timespec="seconds")
    prior={s["id"]:s for s in previous.get("sources",[])}
    events={e["id"]:correct_model_improvement(e) if e.get("sourceId")=="higgsfield-changelog" else e
            for e in previous.get("events",[]) if e.get("claimType")!="external-product-report" or (parse_stamp(e.get("reportPublishedAt")) or datetime.min.replace(tzinfo=timezone.utc))>=now-timedelta(days=7)}
    targeted=collect_targeted(config.get("targetedDiscovery"),previous.get("targetedDiscovery",{}),now,target_fetcher,releases)
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
        is_feed=spec.get("type")=="product-discovery-feed"
        if is_feed:
            entries={k:v for k,v in entries.items() if (parse_stamp(v.get("reportPublishedAt")) or datetime.min.replace(tzinfo=timezone.utc))>=now-timedelta(days=7)}
        if spec["id"]=="higgsfield-changelog" and spec.get("type")=="higgs-changelog":
            entries={k:correct_model_improvement(v) for k,v in entries.items()}
            row["entries"]=entries
        coverage=aggregate_coverage(spec,targeted,now,snapshots)
        model_gaps=model_watch_official_gap(spec,targeted,previous,now)
        if model_gaps:
            row["modelWatchGap"]=model_gaps
        else:
            row.pop("modelWatchGap",None)
        propagation_gaps=propagation_official_gap(spec,previous,snapshots,now)
        if propagation_gaps:
            row["propagationGap"]=propagation_gaps
        else:
            row.pop("propagationGap",None)
        if coverage is not None:
            row["aggregateCoverage"]=coverage
            if coverage["status"]!="aggregate-gap" and not model_gaps and not propagation_gaps:
                sources.append({**row,"entries":entries,"status":old.get("status","awaiting-aggregate"),"deferred":True,"skipReason":coverage["status"]})
                continue
        row.pop("skipReason",None)
        next_at=parse_stamp(old.get("nextAttemptAt"))
        if int(old.get("consecutiveFailures",0))>=3 and old.get("status")=="probe-unavailable":
            last_failure=parse_stamp(old.get("checkedAt"))
            if last_failure:
                next_at=max(next_at or now,last_failure+timedelta(days=7))
                row["nextAttemptAt"]=next_at.isoformat()
                if next_at>now:
                    row["skipReason"]="source-circuit-open"
        if next_at and next_at>now:
            sources.append({**row,"entries":entries,"deferred":True})
            continue
        try:
            fresh=fetcher(spec)
            if not fresh and not is_feed:
                raise ValueError("Empty app observations")
        except (OSError,ValueError,TypeError) as exc:
            count=int(old.get("consecutiveFailures",0))+1
            sources.append({**row,"entries":entries,"checkedAt":stamp,"lastSuccessAt":old.get("lastSuccessAt"),
                            "status":"probe-unavailable","error":f"{type(exc).__name__}: {str(exc)[:160]}","deferred":False,
                            "consecutiveFailures":count,"nextAttemptAt":app_probe_retry_at(exc,now,count)})
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
            if k in entries and value.get("claimType") in {"first-party-product-changelog","first-party-product-milestone"}:
                # An improved parser can correct the existing record, without
                # making a duplicate event or resetting the original observation.
                original_stamp=prev.get("firstObservedAt")
                eid=hashlib.sha256((spec["id"]+"|"+k+"|"+str(original_stamp)).encode()).hexdigest()
                old_event=events.get(eid)
                if old_event and old_event.get("sourceId")==spec["id"] and old_event.get("featureName")==value.get("featureName") and old_event.get("publisherCalendarDay")==value.get("publisherCalendarDay") and old_event.get("publisherCalendarMonth")==value.get("publisherCalendarMonth"):
                    events[eid]={**old_event,**value}
            if k not in entries:
                if value.get("claimType")=="external-product-report":
                    kind="external-product-report"
                elif value.get("claimType")=="first-party-store-version":
                    kind="store-version-or-notes-changed" if old.get("lastSuccessAt") else "baseline-store-version"
                elif value.get("claimType")=="first-party-product-milestone":
                    kind="new-product-milestone" if old.get("lastSuccessAt") else "baseline-product-milestone"
                elif value.get("claimType")=="first-party-developer-change":
                    kind="new-developer-change" if old.get("lastSuccessAt") else "baseline-developer-change"
                elif value.get("claimType")=="first-party-plugin-release":
                    kind="new-plugin-release" if old.get("lastSuccessAt") else "baseline-plugin-release"
                elif value.get("claimType")=="first-party-product-changelog":
                    old_day=(china_calendar_day(now)-timedelta(days=REVIEW_CALENDAR_DAYS-1)).isoformat()
                    kind=("historical-changelog-backfill" if value.get("publisherCalendarDay","")<old_day else
                          "new-changelog-entry" if old.get("lastSuccessAt") else "baseline-changelog-entry")
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
        release_path=ROOT/"site/data/model-releases-30d.json"
        releases=read(release_path).get("items",[]) if release_path.exists() else []
        result=collect(config,previous,datetime.now(timezone.utc),releases=releases,snapshots=read_selected_snapshots(ROOT/"site/data"))
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
