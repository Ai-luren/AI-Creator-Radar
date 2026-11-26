import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from scripts.collect_cross_platform import sitemap_leads
from scripts.collect_resolve_model_leads import reconcile_candidate_dates, candidate_rows, title_agrees
from scripts.collect_release_recall import article_day_stamp, assess

class EvidenceAdversarialTests(unittest.TestCase):
    def test_publisher_calendar_preserves_original_instant(self):
        row={"id":"r","status":"article-date-verified","url":"https://kling.ai/blog/image-4",
             "title":"Kling Image 4.0","modelId":"kling-image","vendor":"Kling AI","category":"image",
             "articlePublishedAt":"2026-11-17T17:56:46Z","firstVerifiedAt":"2026-11-26T12:00:00Z","checkedAt":"2026-11-26T12:00:00Z"}
        candidate=candidate_rows({"items":[row]})[0]
        self.assertEqual(candidate["publishedAt"][:10],"2026-11-18")
        self.assertEqual(candidate["articlePublishedAt"],row["articlePublishedAt"])
        self.assertEqual(article_day_stamp(row["articlePublishedAt"],"https://openai.com/index/x"),row["articlePublishedAt"])

    def test_historical_proof_corrects_weak_duplicate_but_not_structured_conflict(self):
        u={"id":"u","modelId":"demo","official":True,"url":"https://official.example/blog/x?utm_source=a","title":"Introducing Demo 3","publishedAt":None}
        row={"id":"proof","status":"outside-current-window","url":"https://official.example/blog/x",
             "title":"Introducing Demo 3","articlePublishedAt":"2026-01-01T00:00:00Z","checkedAt":"2026-11-26T12:00:00Z"}
        data={"items":[row]}
        output,changes=reconcile_candidate_dates([u,dict(u,id="strong",publicationDateKind="feed-published",publishedAt="2026-11-25")],data)
        self.assertEqual(len(changes),1)
        self.assertEqual(output[0]["publishedAt"],row["articlePublishedAt"])
        self.assertIsNone(u["publishedAt"])
        self.assertEqual(output[1]["publishedAt"],"2026-11-25")
        self.assertEqual(candidate_rows(data),[])
        output,changes=reconcile_candidate_dates([u,dict(u,id="other",modelId="other")],data)
        self.assertFalse(changes)
        output,changes=reconcile_candidate_dates([u],{"items":[dict(row,articlePublishedAt="2026-12-01")]})
        self.assertFalse(changes)

    def test_fresh_recall_rejects_merged_cache_with_wrong_incoming_date(self):
        day="2026-11-23"; stamp="2026-11-26T12:00:00Z"; url="https://official.example/blog/x"
        item={"id":"u","modelId":"demo","title":"Demo 3","official":True,"sourceId":"s","url":url,"publishedAt":day,"lastSeenAt":stamp}
        benchmark={"reviewedAt":day,"scope":"fixture","events":[{"id":"x","modelFamilyId":"demo","eventDate":day,"sourceUrls":[url],"titlePatterns":["Demo 3"],"modelNames":["Demo 3"]}]}
        status={"checkedAt":stamp,"sources":[{"id":"s","checkedAt":stamp,"error":None,"publicationObservations":[dict(item,publishedAt="2026-11-20")]}]}
        result=assess(benchmark,[item],status,{},date(2026,11,26))
        self.assertEqual(result["allSample"]["currentDated"],0)
        self.assertEqual(result["allSample"]["retainedDated"],1)
        status["sources"][0]["publicationObservations"]=[item]
        self.assertEqual(assess(benchmark,[item],status,{},date(2026,11,26))["allSample"]["currentDated"],1)

    def test_sitemap_never_uses_lastmod_as_release_date(self):
        xml=ET.fromstring('<urlset><url><loc>https://z.ai/blog/glm-5.4</loc><lastmod>2026-11-26</lastmod></url><url><loc>https://z.ai/blog/how-to-use-glm-5</loc></url><url><loc>https://evil.example/blog/glm-5</loc></url></urlset>')
        rows=sitemap_leads({"id":"test","name":"Sitemap","url":"https://z.ai/sitemap.xml"},{"z.ai":["/blog/"],"evil.example":["/blog/"]},lambda u:xml)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["lastModifiedAt"][:10],"2026-11-26")
        self.assertIsNone(rows[0]["reportedAt"])
        self.assertNotIn("publishedAt",rows[0])
        self.assertTrue(title_agrees("GLM-5.4: Toward Generalized Coding","glm 5.4"))

    def test_sitemap_index_only_fetches_same_host_news_children(self):
        root=ET.fromstring('<sitemapindex><sitemap><loc>https://z.ai/blog-sitemap.xml</loc></sitemap><sitemap><loc>https://z.ai/voices-sitemap.xml</loc></sitemap><sitemap><loc>https://evil.example/blog.xml</loc></sitemap></sitemapindex>')
        urls=[]
        def fetch(url):
            urls.append(url)
            return root if len(urls)==1 else ET.fromstring('<urlset/>')
        self.assertEqual(sitemap_leads({"id":"test","name":"test","url":"https://z.ai/sitemap.xml"},{"z.ai":["/blog/"]},fetch),[])
        self.assertEqual(urls,["https://z.ai/sitemap.xml","https://z.ai/blog-sitemap.xml"])

    def test_title_variant_does_not_collapse_identity(self):
        self.assertFalse(title_agrees("Introducing Demo 3 Turbo","Demo 3"))
        self.assertFalse(title_agrees("Introducing Scribe v3 Live Medical","Scribe v3 Live"))
