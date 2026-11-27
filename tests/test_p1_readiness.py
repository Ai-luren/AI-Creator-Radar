import unittest
from datetime import datetime,timezone,timedelta
from scripts.audit_p1_readiness import measure

class P1ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,27,12,tzinfo=timezone.utc)
        self.report={"errors":[],"negativeControls":{"checked":3,"incorrectConfirmed":0},
                     "publisherStatementAudit":{"availabilitySample":{"events":2,"matched":2}}}
    def test_availability_and_article_samples_never_sum_to_eight(self):
        data={"recall":{"allSample":{"events":8,"endToEndDated":6,"dateConflicts":0}},
              "independent":{"summary":{"inScopeRepositorySamples":5,"currentStates":{"exact-catalog-match":2}}}}
        r=measure(data,self.report,self.now)
        self.assertEqual(r["gates"]["fixedArticleRecall"]["matched"],6)
        self.assertEqual(r["gates"]["availabilityStatementPilot"]["status"],"pass")
        self.assertEqual(r["gates"]["sameStageEventRecall"]["status"],"not-measured")
        self.assertEqual(r["gates"]["independentFactAccuracy"]["status"],"not-measured")
        self.assertFalse(r["engineeringReady"])
    def test_queue_age_and_schedule_not_confused_with_resolution(self):
        tasks=[{"id":"a","state":"needs-source","firstDetectedAt":(self.now-timedelta(days=2)).isoformat()},
               {"id":"b","state":"probe-unresolved","firstDetectedAt":self.now.isoformat(),"nextAttemptAt":self.now.isoformat()},
               {"id":"c","state":"article-date-observed","firstDetectedAt":self.now.isoformat()}]
        r=measure({"reconciliation":{"tasks":tasks}},self.report,self.now)
        self.assertEqual(r["queue"]["openTasks"],2)
        self.assertEqual(r["queue"]["oldestHours"],48)
        self.assertEqual(r["queue"]["dueRetryIds"],["b"])
        self.assertEqual(r["queue"]["unscheduledIds"],["a"])
    def test_attempt_timestamp_does_not_prove_source_success_or_deployment(self):
        sources=[{"id":"bad","active":True,"official":True,"checkedAt":self.now.isoformat(),
                  "lastSuccessAt":(self.now-timedelta(hours=5)).isoformat(),"error":"403"},
                 {"id":"good","active":True,"official":True,"lastSuccessAt":self.now.isoformat()}]
        r=measure({"monitor":{"sources":sources},"health":{"sources":{"models-batch":{"consecutiveFailures":3}}}},self.report,self.now)
        self.assertEqual(r["sourceHealth"]["successfulWithinTwoHours"],1)
        self.assertEqual(r["sourceHealth"]["persistentBatchIncidents"],["models-batch"])
        self.assertEqual(r["gates"]["sevenDayProduction"]["status"],"not-started")


    def test_independent_review_retains_initial_errors_after_fix(self):
        row={"id":"demo/v","modelFamilyId":"demo","modelVersionId":"v","expectedName":"Demo v3",
             "expectedDay":"2026-11-17","expectedStage":"preview","sourceUrls":["https://official.example/preview"],
             "initialObserved":{"url":"https://official.example/preview"},
             "initialIdentityDateCorrect":True,"initialStageCorrect":False}
        data={"independent_fact_reviews":{"records":[row]},
              "models":[{"id":"demo","versions":[{"id":"v","historicalMilestones":[{"date":"2026-11-17","stage":"preview","sourceUrl":"https://official.example/preview","verifiedAt":"2026-11-27"}]}]}]}
        result=measure(data,self.report,self.now)
        gate=result["gates"]["independentFactAccuracy"]
        self.assertEqual(gate["status"],"incomplete")
        self.assertEqual(gate["factReview"]["initialStrictAccuracy"],0)
        self.assertEqual(gate["factReview"]["currentAlignedWithReviewedFacts"],1)
        self.assertFalse(result["engineeringReady"])
