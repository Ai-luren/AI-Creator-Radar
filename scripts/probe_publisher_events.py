"""One-shot read-only investigation. Fixed examples are diagnostics, never production input."""
import json
import re
import hashlib
from html.parser import HTMLParser
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,build_opener
from urllib.error import HTTPError
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.collect_models import BlockParser,SameHostRedirect,article_publication_date,USER_AGENT

def read(url,accept):
    req=Request(url,headers={"User-Agent":USER_AGENT,"Accept":accept})
    with build_opener(SameHostRedirect()).open(req,timeout=15) as resp:
        data=resp.read(2*1024*1024+1)
        if len(data)>2*1024*1024:
            raise ValueError("bounded response exceeded")
        return resp.status,data.decode("utf-8")

class EmbedParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.block=0
        self.active=False
        self.links=[]
        self.body=[]
        self.p=0
        self.anchor=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="blockquote":
            self.block+=1
            self.active="twitter-tweet" in a.get("class","").split()
        if self.active and tag=="p":
            self.p+=1
        if self.active and tag=="a":
            self.anchor=[a.get("href",""),""]
    def handle_endtag(self,tag):
        if self.active and tag=="a" and self.anchor:
            self.links.append(self.anchor)
            self.anchor=None
        if self.active and tag=="p":
            self.p=max(0,self.p-1)
        if tag=="blockquote":
            self.active=False
    def handle_data(self,data):
        if self.active and self.p:
            self.body.append(data)
        if self.anchor is not None:
            self.anchor[1]+=data

def report(label,func):
    try:
        print("Publisher evidence probe:",json.dumps({"label":label,**func()},ensure_ascii=False))
    except HTTPError as exc:
        print("Publisher evidence probe:",json.dumps({"label":label,"http":exc.code,"retryAfter":exc.headers.get("Retry-After")}))
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print("Publisher evidence probe:",json.dumps({"label":label,"error":type(exc).__name__}))

def glm():
    status,page=read("https://www.zhipuai.cn/zh/news/164","text/html")
    p=BlockParser()
    p.feed(page);p.close()
    headings=[b["text"] for b in p.blocks if b["tag"]=="h1"]
    exact=[h for h in headings if re.search(r"^GLM[- ]5\.4(?![\d.])",h,re.I)]
    return {"http":status,"headingCount":len(headings),"exactModelHeadingCount":len(exact),
            "localizedDateHeader":bool(re.search(r"2026/11/22(?:\s|&nbsp;|<)",page)),
            "oldParserDate":article_publication_date(page,exact[0],True) if len(exact)==1 else None,
            "contentSha256":hashlib.sha256(page.encode()).hexdigest()}

def niji():
    post="https://x.com/midjourney/status/2125328040624521639"
    status,raw=read("https://publish.x.com/oembed?"+urlencode({"url":post,"omit_script":"true","hide_thread":"true","hide_media":"true","lang":"en","dnt":"true"}),"application/json")
    d=json.loads(raw)
    parser=EmbedParser()
    parser.feed(d["html"]);parser.close()
    author=urlsplit(d.get("author_url",""))
    provider=urlsplit(d.get("provider_url",""))
    exact_links=[label.strip() for url,label in parser.links if urlsplit(url).hostname in {"x.com","twitter.com","www.x.com","www.twitter.com"} and urlsplit(url).path.casefold()=="/midjourney/status/2125328040624521639"]
    body=" ".join("".join(parser.body).split())
    identity=author.scheme=="https" and author.hostname in {"twitter.com","x.com","www.twitter.com","www.x.com"} and author.path.rstrip("/").casefold()=="/midjourney"
    stage=bool(re.search(r"^Niji\s+V?8\s+is now live[!.]",body,re.I))
    return {"http":status,"providerHost":provider.hostname,"authorMatches":identity,
            "blockquoteCount":parser.block,"exactPostDateLabels":exact_links,
            "explicitServiceAvailability":stage,"contentSha256":hashlib.sha256(raw.encode()).hexdigest()}
report("glm-domestic-direct",glm)
report("niji-official-embed",niji)
