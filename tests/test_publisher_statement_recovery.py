import unittest,json
from datetime import datetime,timezone
from scripts.publisher_statement_recovery import archive_candidates,archive_post,parse_embed,parse_zhipu,post_url
from scripts.event_identity import model_index

class PublisherStatementTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,27,tzinfo=timezone.utc)
        self.index=model_index([{"id":"midjourney","versions":[{"id":"niji-8","name":"Niji 8"}]},
                                {"id":"glm","versions":[{"id":"5-4","name":"GLM-5.4"}]}])
        self.pointer="https://launcharchive.ai/launches/midjourney-niji-v8-launch--x_1234567890123"
        self.post=("https://x.com/midjourney/status/1234567890123","midjourney")
    def test_directory_requires_exact_publisher_model_and_original_id(self):
        page=f'<a href="{self.pointer}">Midjourney Niji V8 Launch Midjourney</a><a href="/launches/other--x_1234567890124">Other Niji V8 Launch</a>'
        self.assertEqual(archive_candidates(page,self.index),{self.pointer:("midjourney","niji-8")})
        self.assertEqual(archive_post(f'<a href="{self.post[0]}">View post</a>',self.pointer),self.post)
        self.assertIsNone(archive_post('<a href="https://x.com/midjourney/status/1234567890124">View post</a>',self.pointer))
        self.assertIsNone(post_url("https://x.com.evil.example/midjourney/status/1234567890123"))
    def test_embed_validates_account_date_and_exact_stage(self):
        payload={"provider_url":"https://x.com","author_url":"https://twitter.com/midjourney","html":f'<blockquote class="twitter-tweet"><p>Niji V8 is now live! Test.</p><a href="{self.post[0]}">November 24, 2026</a></blockquote>'}
        result=parse_embed(json.dumps(payload),self.post,("midjourney","niji-8"),self.index,self.now)
        self.assertEqual(result["publisherCalendarDay"],"2026-11-24")
        self.assertIsNone(result["eventDate"])
        self.assertEqual(result["claimType"],"service-availability-statement")
        for bad in [dict(payload,author_url="https://x.com/other"),dict(payload,html=payload["html"].replace("is now live","will be live")),dict(payload,html=payload["html"].replace("V8","V8.1"))]:
            with self.assertRaises(ValueError):
                parse_embed(json.dumps(bad),self.post,("midjourney","niji-8"),self.index,self.now)
    def test_zhipu_requires_actual_availability_not_api_preview(self):
        url="https://www.zhipuai.cn/zh/news/123"
        page="<h1>GLM-5.4：新模型</h1><p>2026年11月22日</p><p>即日起，GLM-5.4向GLM Coding Plan全量用户开放，同步上线平台。API将在完成评估后开放。</p><h2>更多</h2>"
        proof=parse_zhipu(page,url,("glm","5-4"),self.index,self.now)
        self.assertEqual(proof["service"],"GLM Coding Plan")
        self.assertIsNone(proof["eventDate"])
        with self.assertRaises(ValueError):
            parse_zhipu(page.replace("即日起","即将"),url,("glm","5-4"),self.index,self.now)

    def test_directory_no_title_spacing_and_query_tracking(self):
        page=f'<a href="{self.pointer}?ref=directory"><img alt="">MidjourneyNijiV8Launch</a>'
        self.assertEqual(archive_candidates(page,self.index),{self.pointer:("midjourney","niji-8")})
    def test_zhipu_div_opening_statement_and_hidden_script(self):
        url="https://www.zhipuai.cn/zh/research/123"
        page="<h1>GLM-5.4：新模型</h1><div>2026年11月22日</div><div>此前讨论结束。<strong>即日起，GLM-5.4</strong>向GLM Coding Plan全量用户开放，同步上线。</div><h1>泛Coding</h1>"
        proof=parse_zhipu(page,url,("glm","5-4"),self.index,self.now)
        self.assertEqual(proof["publisherCalendarDay"],"2026-11-22")
        hidden=page.replace("<strong>即日起，GLM-5.4</strong>向GLM Coding Plan全量用户开放，同步上线。","<script>即日起，GLM-5.4向GLM Coding Plan全量用户开放，同步上线。</script>")
        with self.assertRaises(ValueError):
            parse_zhipu(hidden,url,("glm","5-4"),self.index,self.now)

class IndependentSocialIndexTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,28,tzinfo=timezone.utc)
        self.families=[{"id":"glm","versions":[{"id":"v3","name":"GLM-3.8"},{"id":"preview","name":"GLM-3.8 Preview"}]}]
        self.index=model_index(self.families)
        self.post=("https://x.com/zai_org/status/1234567890123","zai_org")
        self.pointer="https://www.advanceintelligence.ai/2026-11-23/all"
        self.payload={"provider_url":"https://x.com","author_url":"https://x.com/Zai_org",
                      "html":f'<blockquote class="twitter-tweet"><p>Introducing GLM-3.8: Generalized Coding. API access will open later.</p><a href="{self.post[0]}">November 23, 2026</a></blockquote>'}
        self.discovery={"items":[{"id":"observed-lead","title":"GLM-3.8 released","reportedAt":"2026-11-23","sourceId":"feed"}]}

    def test_independent_index_recovers_announcement_without_inferred_release(self):
        from scripts.publisher_statement_recovery import collect_statements,social_embed_url
        calls=[]
        def read(url,accept="text/html"):
            calls.append(url)
            if url.endswith("/robots.txt"):
                return "User-agent: *\nAllow: /"
            if url==self.pointer:
                return f'<h2><a href="{self.post[0]}">Z.ai Releases GLM 3.8</a></h2>'
            if url==social_embed_url(self.post):
                return json.dumps(self.payload)
            self.fail(url)
        old={"sources":{"zhipu":{"nextAttemptAt":"2026-11-29T00:00:00+00:00"},
                        "social":{"nextAttemptAt":"2026-11-29T00:00:00+00:00"}}}
        result=collect_statements([],self.families,old,self.now,read,discovery=self.discovery)
        self.assertEqual(len(calls),3)
        self.assertEqual(len(result["records"]),1)
        row=result["records"][0]
        self.assertEqual(row["fact"]["claimType"],"announcement-statement")
        self.assertIsNone(row["fact"]["eventDate"])
        self.assertIsNone(row["fact"]["service"])
        self.assertEqual(row["discovery"]["sourceRecordId"],"observed-lead")
        from scripts.audit_publisher_statements import inspect_statements
        usable,report=inspect_statements(result,self.families,self.now)
        self.assertFalse(report["errors"])
        self.assertEqual(len(usable),1)
        self.assertEqual(report["summary"]["byClaimType"],{"announcement-statement":1})

    def test_wrong_account_preview_future_and_robots_disallow(self):
        from scripts.publisher_statement_recovery import daily_index_posts,daily_index_allowed,collect_statements
        self.assertEqual(daily_index_posts(f'<a href="https://x.com/nijijourney/status/1234567890123">GLM 3.8</a>',self.index,{("glm","v3")}),{})
        for body in ["Introducing GLM-3.8 Preview: Test","We will introduce GLM-3.8: Test","Introducing GLM-3.8.1: Test"]:
            obj=dict(self.payload,html=self.payload["html"].replace("Introducing GLM-3.8: Generalized Coding. API access will open later.",body))
            with self.assertRaises(ValueError):
                parse_embed(json.dumps(obj),self.post,("glm","v3"),self.index,self.now)
        self.assertFalse(daily_index_allowed(lambda *args:"User-agent: *\nDisallow: /",self.pointer))
        old={"sources":{"zhipu":{"nextAttemptAt":"2026-11-29T00:00:00+00:00"},"social":{"nextAttemptAt":"2026-11-29T00:00:00+00:00"}}}
        calls=[]
        def deny(url,accept="text/html"):
            calls.append(url)
            self.assertTrue(url.endswith("/robots.txt"))
            return "User-agent: *\nDisallow: /"
        result=collect_statements([],self.families,old,self.now,deny,discovery=self.discovery)
        self.assertEqual(len(calls),1)
        self.assertFalse(result["records"])
        self.assertIsNotNone(result["sources"]["social-index"]["error"])
