import json
import unittest
from urllib.error import HTTPError
from scripts import serve_local as reader

class CreatorIntelTests(unittest.TestCase):
    def setUp(self):
        reader._intel_cache.clear()
        reader._intel_cooldown.clear()
        self.calls=[]
    def fake(self,request,timeout):
        self.calls.append(request.full_url)
        class Response:
            headers={"ETag":"demo"}
            def read(self,n):return json.dumps({"items":[{"title":"Demo","links":{"original":"https://example.org"}}]}).encode()
            def __enter__(self):return self
            def __exit__(self,*args):pass
        return Response()
    def test_both_sources_and_bounded_cache(self):
        result=reader.get_intel("hot","",self.fake,lambda:100)
        self.assertEqual(set(result["sources"]),{"AIHOT","AIPick"})
        self.assertEqual(len(self.calls),2)
        reader.get_intel("hot","",self.fake,lambda:200)
        self.assertEqual(len(self.calls),2)
        self.assertTrue(all(url.endswith("/api/v1/hot-topics") for url in self.calls))
    def test_failure_independent_and_preserves_good_snapshot(self):
        first=reader.get_intel("hot","",self.fake,lambda:100)
        def fetch(req,timeout):
            if "aihot.news" in req.full_url:raise HTTPError(req.full_url,429,"limit",{"Retry-After":"7200"},None)
            return self.fake(req,timeout)
        result=reader.get_intel("hot","",fetch,lambda:800)
        self.assertEqual(result["sources"]["AIHOT"]["data"],first["sources"]["AIHOT"]["data"])
        self.assertEqual(result["sources"]["AIHOT"]["error"],"HTTP 429")
        self.assertIn("data",result["sources"]["AIPick"])
        self.assertEqual(reader._intel_cooldown["AIHOT"],8000)
    def test_no_arbitrary_endpoint(self):
        for provider,mode,term in [("evil","hot",""),("AIHOT","unknown",""),("AIHOT","vendors","https://evil.org"),("AIHOT","hot","Renoise")]:
            with self.assertRaises(ValueError):reader.intel_endpoint(provider,mode,term)
        self.assertIn("q=LibTV",reader.intel_endpoint("AIPick","competitors","LibTV"))
