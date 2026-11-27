"""One-off personal source diagnostic. Counts only, no republication."""
import gzip
import json
from collections import Counter
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

queries = [("即梦","ai-products"),("可灵","ai-products"),("海螺 AI","ai-products"),("Vidu","ai-products"),("PixVerse","ai-products"),("Sand.ai","ai-models")]
for term, category in queries:
    params = {"mode":"all","window":"7d","by":"published","q":term,"limit":30}
    if category:
        params["category"] = category
    try:
        req = Request("https://aipick.news/api/v1/items?"+urlencode(params),
                      headers={"Accept":"application/json","Accept-Encoding":"gzip","User-Agent":"AI-Creator-Radar source-diagnostic/1.0"})
        with urlopen(req, timeout=20) as response:
            raw = response.read(4*1024*1024+1)
            if len(raw)>4*1024*1024:
                raise ValueError("response too large")
            if response.headers.get("Content-Encoding","").lower()=="gzip":
                raw=gzip.decompress(raw)
            if len(raw)>8*1024*1024:
                raise ValueError("decoded response too large")
            payload=json.loads(raw)
            rows=payload["items"]
            if not isinstance(rows,list):
                raise ValueError("invalid items array")
            wx=[x for x in rows if urlsplit(x.get("links",{}).get("original") or "").hostname=="mp.weixin.qq.com"]
            exact=[x for x in rows if term.casefold() in (str(x.get("title") or "")+" "+str(x.get("originalTitle") or "")).casefold()]
            print("AIPick targeted probe:",json.dumps({"term":term,"category":category,"status":response.status,
                  "items":len(rows),"wechatOriginalLinks":len(wx),"exactTitleMatches":len(exact),
                  "wechatDated":sum(bool(x.get("publishedAt")) for x in wx),
                  "sourceDomains":dict(Counter(urlsplit(x.get("links",{}).get("original") or "").hostname or "missing" for x in rows)),
                  "cacheControl":response.headers.get("Cache-Control"),"hasEtag":bool(response.headers.get("ETag")),
                  "hasNextCursor":bool(payload.get("nextCursor"))},ensure_ascii=False))
    except HTTPError as exc:
        print("AIPick targeted probe:",json.dumps({"term":term,"category":category,"status":exc.code,"retryAfter":exc.headers.get("Retry-After")},ensure_ascii=False))
        if exc.code in (403,429,503):
            break
    except (URLError,ValueError,TypeError,KeyError,OSError) as exc:
        print("AIPick targeted probe:",json.dumps({"term":term,"category":category,"status":"unavailable","errorType":type(exc).__name__},ensure_ascii=False))
        break
