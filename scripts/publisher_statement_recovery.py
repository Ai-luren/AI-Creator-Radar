"""Independent, bounded official availability statements. No benchmark inputs."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
import hashlib
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin,urlencode
from urllib.request import Request,build_opener
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser

try:
    from scripts.collect_models import BlockParser, SameHostRedirect, USER_AGENT, article_publication_date, parse_date
    from scripts.event_identity import model_index, identify, day
except ModuleNotFoundError:
    from collect_models import BlockParser, SameHostRedirect, USER_AGENT, article_publication_date, parse_date
    from event_identity import model_index, identify, day

ARCHIVE="https://launcharchive.ai/browse/launches/1"
ARCHIVE_FALLBACK="https://launcharchive.ai/launches/this-week"
ACCOUNTS={"midjourney":"midjourney","nijijourney":"midjourney"}
SOCIAL_HOSTS={"x.com","twitter.com","www.x.com","www.twitter.com"}
MAX_BYTES=2*1024*1024

def read(url,accept="text/html"):
    with build_opener(SameHostRedirect()).open(Request(url,headers={"User-Agent":USER_AGENT,"Accept":accept}),timeout=12) as response:
        data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:
        raise ValueError("Response too large")
    return data.decode("utf-8")

def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def blocks(page):
    p=BlockParser()
    p.feed(page);p.close()
    return sorted(p.blocks,key=lambda b:b["sequence"])

def post_url(raw):
    try:
        u=urlsplit(raw)
        m=re.fullmatch(r"/([A-Za-z0-9_]{1,15})/status/([0-9]{10,25})/?",u.path)
        if u.scheme!="https" or u.hostname not in SOCIAL_HOSTS or u.username or u.password or u.port not in (None,443) or not m:
            return None
        author=m[1].casefold()
        return ("https://x.com/"+author+"/status/"+m[2],author) if author in ACCOUNTS else None
    except (ValueError,TypeError):
        return None

def exact_niji(index,text):
    # V is the publisher's conventional prefix, not a different model.
    match=re.fullmatch(r"Niji\s+V?(\d+(?:\.\d+)*)",text.strip(),re.I)
    if not match:
        return None
    return identify(index,"Niji "+match[1],family_id="midjourney")

def archive_candidates(page,index):
    result={}
    for b in blocks(page):
        if b["tag"]!="a":
            continue
        url=urljoin(ARCHIVE,b["attrs"].get("href",""))
        p=urlsplit(url)
        if p.scheme!="https" or p.hostname!="launcharchive.ai" or p.username or p.password or p.port not in (None,443):
            continue
        # The directory may render the title, vendor and view count without
        # spaces, or provide an image-only link. A strict actual link slug is
        # a discovery hint only. The original publisher still proves identity.
        m=re.fullmatch(r"/launches/(?:midjourney|niji-journey)-niji-v?(\d+(?:-\d+)*)-launch--x_[0-9]{10,25}/?",p.path,re.I)
        if not m:
            continue
        ident=exact_niji(index,"Niji "+m[1].replace("-","."))
        if ident:
            result["https://launcharchive.ai"+p.path.rstrip("/")]=ident
    return result

def archive_post(page,pointer):
    # Require a link whose exact status ID matches the directory's detail URL.
    post_id=urlsplit(pointer).path.rsplit("_",1)[1]
    urls={p for b in blocks(page) if b["tag"]=="a" for p in [post_url(b["attrs"].get("href",""))]
          if p and p[0].endswith("/"+post_id)}
    return next(iter(urls)) if len(urls)==1 else None

class EmbedParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.count=0;self.active=False;self.p=0;self.body=[];self.links=[];self.anchor=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="blockquote":
            self.count+=1
            self.active="twitter-tweet" in a.get("class","").split()
        if self.active and tag=="p":
            self.p+=1
        if self.active and tag=="a":
            self.anchor=[a.get("href",""),""]
    def handle_endtag(self,tag):
        if self.active and tag=="a" and self.anchor:
            self.links.append(self.anchor);self.anchor=None
        if self.active and tag=="p":
            self.p=max(0,self.p-1)
        if tag=="blockquote":
            self.active=False
    def handle_data(self,data):
        if self.active and self.p:
            self.body.append(data)
        if self.anchor is not None:
            self.anchor[1]+=data

def parse_embed(raw,post,expected,index,now):
    canonical,author=post
    obj=json.loads(raw)
    provider=urlsplit(obj.get("provider_url",""));publisher=urlsplit(obj.get("author_url",""))
    if provider.scheme!="https" or provider.hostname not in SOCIAL_HOSTS or publisher.scheme!="https" or publisher.hostname not in SOCIAL_HOSTS or publisher.path.rstrip("/").casefold()!="/"+author:
        raise ValueError("Publisher identity mismatch")
    p=EmbedParser();p.feed(obj["html"]);p.close()
    dates={day(parse_date(text.strip())) for url,text in p.links if post_url(url)==post}
    if p.count!=1 or len(dates)!=1 or None in dates:
        raise ValueError("Missing or ambiguous official post date")
    date_value=next(iter(dates))
    if not (now-timedelta(days=45)).date().isoformat()<=date_value<=now.date().isoformat():
        raise ValueError("Outside recent observation window")
    body=" ".join("".join(p.body).split())
    m=re.match(r"^(Niji\s+V?\d+(?:\.\d+)*)\s+is now live[!.](?:\s|$)",body,re.I)
    if not m or exact_niji(index,m[1])!=expected:
        raise ValueError("No exact affirmative model availability statement")
    return {"modelFamilyId":expected[0],"modelVersionId":expected[1],"claimType":"service-availability-statement",
            "publisherAccount":author,"sourceUrl":canonical,"publisherCalendarDay":date_value,
            "datePrecision":"day","eventDate":None,"statementSha256":sha(m[0].strip()),"contentSha256":sha(raw),
            "evidenceGrade":"official-dated-social-statement","service":"Midjourney / Niji Journey"}

def parse_zhipu(page,url,expected,index,now):
    b=blocks(page)
    headings=[r for r in b if r["tag"]=="h1" and identify(index,r["text"],family_id="glm")==expected]
    if len(headings)!=1:
        raise ValueError("Article identity ambiguous")
    h=headings[0]
    stamp=article_publication_date(page,h["text"],leading_date=True,publisher_host="www.zhipuai.cn")
    d=day(stamp)
    if not d or not (now-timedelta(days=45)).date().isoformat()<=d<=now.date().isoformat():
        raise ValueError("Article date unresolved")
    # Publisher uses div/span-rich article bodies; capture the actual visible
    # opening section rather than relying on a paragraph at a sentence start.
    class IntroParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.heading=None
            self.active=False
            self.finished=False
            self.hidden=0
            self.parts=[]
        def handle_starttag(self,tag,attrs):
            if tag in {"script","style","template","noscript"}:
                self.hidden+=1
                return
            if self.hidden or self.finished:
                return
            if tag in {"h1","h2","h3","h4","h5","h6"}:
                if self.active:
                    self.finished=True
                else:
                    self.heading=[]
            elif self.active and tag in {"p","div","br","li","section"}:
                self.parts.append("\n")
        def handle_endtag(self,tag):
            if tag in {"script","style","template","noscript"}:
                self.hidden=max(0,self.hidden-1)
                return
            if self.hidden or self.finished:
                return
            if tag in {"h1","h2","h3","h4","h5","h6"} and self.heading is not None:
                self.active=" ".join("".join(self.heading).split())==h["text"]
                self.heading=None
            elif self.active and tag in {"p","div","li","section"}:
                self.parts.append("\n")
        def handle_data(self,data):
            if self.hidden or self.finished:
                return
            if self.heading is not None:
                self.heading.append(data)
            elif self.active:
                self.parts.append(data)
    intro=IntroParser();intro.feed(page);intro.close()
    body=re.sub(r"[\t \u00a0]+"," ","".join(intro.parts))[:18000]
    for m in re.finditer(r"(?:^|[。！？\n])\s*(即日起[，,]\s*(GLM[- ]\d+(?:\.\d+)*)\s*向\s*GLM\s*Coding\s*Plan\s*全量用户开放[，,。])",body,re.I):

        if identify(index,m[2],family_id="glm")==expected:
            return {"modelFamilyId":expected[0],"modelVersionId":expected[1],
                    "claimType":"service-availability-statement","sourceUrl":url,
                    "publisherCalendarDay":d,"datePrecision":"day","eventDate":None,
                    "statementSha256":sha(m[1]),"contentSha256":sha(page),
                    "evidenceGrade":"official-dated-article-statement","service":"GLM Coding Plan"}
    raise ValueError("No explicit same-model Coding Plan availability statement")

def archive_allowed(read_page, urls):
    try:
        text=read_page("https://launcharchive.ai/robots.txt","text/plain")
    except HTTPError as e:
        if e.code==404:
            return True
        raise
    if re.search(r"<(?:html|!doctype)",text,re.I):
        raise ValueError("Invalid robots response")
    rp=RobotFileParser()
    rp.parse(text.splitlines())
    return all(rp.can_fetch(USER_AGENT,u) for u in urls)

def collect_statements(claims,families,previous,now,read_page=read):
    stamp=now.isoformat(timespec="seconds")
    index=model_index(families)
    records={r["id"]:r for r in previous.get("records",[])}
    sources=dict(previous.get("sources",{}))
    attempts=0
    def due(key):
        return not sources.get(key,{}).get("nextAttemptAt") or sources[key]["nextAttemptAt"]<=stamp
    def remember(fact,discovery):
        # Content changes alone do not create a duplicate semantic event.
        basis={k:v for k,v in fact.items() if k!="contentSha256"}
        key="publisher-"+sha(json.dumps(basis,sort_keys=True,ensure_ascii=False))
        old=records.get(key,{})
        records[key]={"id":key,"fact":fact,"discovery":discovery,
                      "firstObservedAt":old.get("firstObservedAt") or stamp,"lastSuccessfulObservationAt":stamp}
    def result(key,error=None):
        old=sources.get(key,{})
        failures=int(old.get("consecutiveFailures",0))+1 if error else 0
        delay=min(48,6*2**min(failures-1,3)) if error else 6
        sources[key]={**old,"lastAttemptAt":stamp,"lastSuccessAt":old.get("lastSuccessAt") if error else stamp,
                      "error":str(error)[:180] if error else None,"consecutiveFailures":failures,
                      "nextAttemptAt":(now+timedelta(hours=delay)).isoformat(timespec="seconds")}
    # Read actual automatically discovered Chinese articles, not a hand-seeded URL.
    candidates={}
    for row in claims:
        fact=row.get("fact",{})
        url=fact.get("sourceUrlKey") or ""
        u=urlsplit(url)
        d=fact.get("publisherCalendarDay")
        if fact.get("modelFamilyId")=="glm" and u.scheme=="https" and u.hostname=="www.zhipuai.cn" and not u.username and not u.password and u.port in (None,443) and re.fullmatch(r"/zh/(?:news|research)/\d+",u.path) and d and (now-timedelta(days=45)).date().isoformat()<=d<=now.date().isoformat():
            candidates[url]=(fact["modelFamilyId"],fact["modelVersionId"],d)
    if due("zhipu"):
        # Prioritize not-yet-proven URLs, then latest publisher day.
        available=sorted(candidates,key=lambda u:(any(r["fact"]["sourceUrl"]==u for r in records.values()),-int(candidates[u][2].replace("-","")),u))
        if available:
            url=available[0];attempts+=1
            try:
                proof=parse_zhipu(read_page(url),url,candidates[url][:2],index,now)
                remember(proof,{"channel":"official-article-collector","sourceUrl":url})
                result("zhipu")
            except (OSError,ValueError,TypeError,KeyError) as e:
                result("zhipu",e)
    if due("social"):
        attempts+=1
        try:
            if not archive_allowed(read_page,[ARCHIVE]):
                raise ValueError("Archive robots policy disallows discovery")
            found=archive_candidates(read_page(ARCHIVE),index)
            if not found and archive_allowed(read_page,[ARCHIVE_FALLBACK]):
                found=archive_candidates(read_page(ARCHIVE_FALLBACK),index)
            if not found:
                raise ValueError("No matching dynamic archive links")
            pending=[u for u in found if not any(r.get("discovery",{}).get("sourceUrl")==u for r in records.values())]
            # At most one detail and one documented official embed request.
            if pending:
                pointer=pending[0]
                if not archive_allowed(read_page,[pointer]):
                    raise ValueError("Archive robots policy disallows detail")
                post=archive_post(read_page(pointer),pointer)
                if not post:
                    raise ValueError("No exact official post pointer")
                url="https://publish.x.com/oembed?"+urlencode({"url":post[0],"omit_script":"true","hide_thread":"true","hide_media":"true","lang":"en","dnt":"true"})
                proof=parse_embed(read_page(url,"application/json"),post,found[pointer],index,now)
                remember(proof,{"channel":"public-launch-index-pointer","sourceUrl":pointer})
            result("social")
            sources["social"]["candidateCount"]=len(found)
        except (OSError,ValueError,TypeError,KeyError) as e:
            result("social",e)
    conflicts=[]
    for identity in {(r["fact"]["sourceUrl"],r["fact"]["modelFamilyId"],r["fact"]["modelVersionId"]) for r in records.values()}:
        dates=sorted({r["fact"]["publisherCalendarDay"] for r in records.values() if (r["fact"]["sourceUrl"],r["fact"]["modelFamilyId"],r["fact"]["modelVersionId"])==identity})
        if len(dates)>1:
            conflicts.append({"sourceUrl":identity[0],"modelFamilyId":identity[1],"modelVersionId":identity[2],"dates":dates})
    return {"checkedAt":stamp,"records":sorted(records.values(),key=lambda r:r["id"]),"sources":sources,
            "conflicts":conflicts,"summary":{"verifiedStatements":len(records),"attemptedSources":attempts,"dateConflicts":len(conflicts)},
            "policy":"Explicit dated availability claims only; eventDate and first-release date remain unknown. No fixed benchmark pointers, no third-party text retained."}
