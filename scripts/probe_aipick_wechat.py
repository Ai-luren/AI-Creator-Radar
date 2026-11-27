"""One-shot personal-use source probe. Do not persist or publish article data."""
import gzip
import json
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

url = "https://aipick.news/api/v1/items?" + urlencode({"mode":"all","window":"7d","q":"即梦","limit":30})
try:
    req = Request(url, headers={"Accept":"application/json","Accept-Encoding":"gzip","User-Agent":"AI-Creator-Radar source-diagnostic/1.0"})
    with urlopen(req, timeout=20) as response:
        raw = response.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:
            raise ValueError("response too large")
        if response.headers.get("Content-Encoding","").lower()=="gzip":
            raw=gzip.decompress(raw)
        if len(raw)>4*1024*1024:
            raise ValueError("decoded response too large")
        rows=json.loads(raw)["items"]
        if not isinstance(rows,list):
            raise ValueError("invalid items array")
        wx=[x for x in rows if urlsplit(x.get("links",{}).get("original") or "").hostname=="mp.weixin.qq.com"]
        exact=[x for x in rows if "即梦" in (str(x.get("title") or "")+" "+str(x.get("originalTitle") or ""))]
        print("AIPick WeChat probe:",json.dumps({"status":response.status,"items":len(rows),"wechatOriginalLinks":len(wx),
             "jimengTitleMatches":len(exact),"wechatDated":sum(bool(x.get("publishedAt")) for x in wx),
             "cacheControl":response.headers.get("Cache-Control"),"hasEtag":bool(response.headers.get("ETag"))},ensure_ascii=False))
except HTTPError as exc:
    print("AIPick WeChat probe:",json.dumps({"status":exc.code,"retryAfter":exc.headers.get("Retry-After")}))
except (URLError,ValueError,TypeError,KeyError,OSError) as exc:
    print("AIPick WeChat probe:",json.dumps({"status":"unavailable","errorType":type(exc).__name__}))
