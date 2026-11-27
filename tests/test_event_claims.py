import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from scripts.collect_event_claims import classify, collect_claims

class EventClaimsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 27, tzinfo=timezone.utc)
        self.stamp = self.now.isoformat()
        self.families = [{"id":"demo","versions":[{"id":"v3","name":"Demo v3"},{"id":"live","name":"Demo v3 Live"}]}]
        self.sources = [{"id":"publisher","active":True,"official":True,"url":"https://official.example/news",
                         "modelMatches":{"demo":["Demo"]}}]
        self.item = {"id":"update","modelId":"demo","sourceId":"publisher","official":True,
                     "title":"Demo v3 officially released","publishedAt":"2026-11-22T00:00:00Z",
                     "url":"https://official.example/news/v3","publicationDateKind":"article-explicit-date",
                     "publicationObservedAt":self.stamp}
        self.status = {"checkedAt":self.stamp,"sources":[{"id":"publisher","checkedAt":self.stamp,
                       "publicationObservations":[{k:self.item[k] for k in ("title","url","modelId","publishedAt")}]}]}
        self.allowed = {"official.example":["/news/"]}

    def run_claims(self, items=None, status=None, resolution=None, old=None, days=0):
        return collect_claims(self.families,[self.item] if items is None else items,
                              self.status if status is None else status,self.sources,resolution or {},
                              self.allowed,old or {},self.now+timedelta(days=days))

    def test_explicit_stage_is_distinct_from_release(self):
        for title, expected in [
            ("Introducing Demo v3","announcement-statement"),
            ("Demo v3 now available via API","api-availability-statement"),
            ("Demo v3 now generally available","general-availability-statement"),
            ("Demo v3 available in preview","preview-statement"),
            ("Demo v3 officially released","explicit-release-statement"),
            ("Demo v3 will be released","article-publication"),
            ("Demo v3 Live officially released","article-publication")]:
            self.assertEqual(classify(title,"Demo v3")[0],expected,title)

    def test_service_integration_requires_same_product_affirmative_statement(self):
        title="Meet Demo v3 in AutoClaw."
        summary="Demo v3, the latest flagship model, is now integrated into AutoClaw and supports use."
        self.assertEqual(classify(title,"Demo v3",summary),("service-integration-statement","AutoClaw"))
        self.assertEqual(classify(title,"Demo v3")[0],"article-publication")
        self.assertEqual(classify(title,"Demo v3","Demo v3 is now integrated into Other")[0],"article-publication")

    def test_raw_observation_required_and_no_event_date_inferred(self):
        result=self.run_claims()
        self.assertEqual(result["summary"]["claims"],1)
        fact=result["claims"][0]["fact"]
        self.assertEqual(fact["publisherCalendarDay"],"2026-11-22")
        self.assertIsNone(fact["eventDate"])
        self.assertEqual(len(result["releaseStatementReviewCandidates"]),1)
        self.assertEqual(self.run_claims(status={})["summary"]["claims"],0)
        self.assertEqual(self.run_claims(items=[dict(self.item,publishedAt="2026-11-23")])["summary"]["claims"],0)

    def test_third_party_and_wrong_variant_cannot_be_promoted(self):
        self.assertEqual(self.run_claims(items=[dict(self.item,official=False)])["summary"]["claims"],0)
        bad=dict(self.item,title="Demo v3 Live Medical officially released")
        status=deepcopy(self.status)
        status["sources"][0]["publicationObservations"][0]["title"]=bad["title"]
        self.assertEqual(self.run_claims(items=[bad],status=status)["summary"]["claims"],0)

    def test_same_publisher_claim_recovered_twice_is_one_fact(self):
        proof={"id":"proof","url":self.item["url"],"title":self.item["title"],"modelId":"demo",
               "articlePublishedAt":self.item["publishedAt"],"checkedAt":self.stamp,"status":"article-date-verified"}
        result=self.run_claims(resolution={"checkedAt":self.stamp,"items":[proof]})
        self.assertEqual(result["summary"]["claims"],1)
        self.assertEqual(len(result["claims"][0]["provenance"]),2)

    def test_outage_retains_history_without_new_success(self):
        first=self.run_claims()
        later=self.run_claims(items=[],status={},old=first,days=1)
        self.assertEqual(later["summary"]["claims"],1)
        self.assertEqual(later["summary"]["newClaims"],0)
        self.assertEqual(later["summary"]["currentSuccessfulObservations"],0)
        self.assertEqual(later["claims"][0]["lastSuccessfulObservationAt"],first["claims"][0]["lastSuccessfulObservationAt"])

    def test_conflicting_article_dates_are_quarantined(self):
        first=self.run_claims()
        changed=dict(self.item,publishedAt="2026-11-23T00:00:00Z")
        status=deepcopy(self.status)
        status["sources"][0]["publicationObservations"][0]["publishedAt"]=changed["publishedAt"]
        second=self.run_claims(items=[changed],status=status,old=first)
        self.assertEqual(second["summary"]["articleDateConflicts"],1)
        self.assertEqual(second["releaseStatementReviewCandidates"],[])

    def test_corrupt_claim_is_not_silently_overwritten(self):
        first=self.run_claims()
        first["claims"][0]["fact"]["eventDate"]="2026-11-22"
        with self.assertRaises(ValueError):
            self.run_claims(old=first)
