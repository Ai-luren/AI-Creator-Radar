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

    def test_same_stage_result_is_separate_from_fixed_article_recall(self):
        report={**self.report,"sameStageRecall":{"status":"pass","events":8,"matched":8}}
        data={"recall":{"allSample":{"events":8,"endToEndDated":6,"dateConflicts":0}}}
        r=measure(data,report,self.now)
        self.assertEqual(r["gates"]["fixedArticleRecall"]["matched"],6)
        self.assertEqual(r["gates"]["sameStageEventRecall"]["matched"],8)
        self.assertNotIn("sameStageEventRecall",r["blockingGates"])
        self.assertFalse(r["engineeringReady"])

    def test_latency_diagnostic_never_promotes_sla_and_deduplicates(self):
        from scripts.audit_p1_readiness import retained_feed_latency
        source={"id":"official","active":True,"official":True,"type":"rss"}
        row={"id":"one","sourceId":"official","official":True,"modelId":"demo",
             "url":"https://official.example/blog/one","updateType":"release","publicationDateKind":"feed-published",
             "publishedAt":"2026-11-27T10:00:00Z","firstSeenAt":"2026-11-27T11:30:00Z",
             "publicationObservedAt":"2026-11-27T11:30:00Z"}
        duplicate={**row,"id":"two","url":row["url"]+"?utm_source=demo","firstSeenAt":"2026-11-27T11:45:00Z","publicationObservedAt":"2026-11-27T11:45:00Z"}
        midnight={**row,"id":"day","url":"https://official.example/blog/day","publishedAt":"2026-11-27T00:00:00Z"}
        corrected={**row,"id":"corrected","previousSourceDates":["2026-11-26T10:00:00Z"]}
        future={**row,"id":"future","url":"https://official.example/blog/future","firstSeenAt":"2026-11-27T09:00:00Z"}
        data={"model_source_config":[source],"updates":{"items":[row,duplicate,midnight,corrected,future]}}
        result=measure(data,self.report,self.now)
        gate=result["gates"]["priorityDiscoveryLatency"]
        self.assertEqual(gate["status"],"not-measured")
        d=gate["retainedFeedDiagnostic"]
        self.assertEqual(d["observedArticles"],1)
        self.assertEqual(d["withinTwoHours"],1)
        self.assertEqual(d["medianSeconds"],5400)
        self.assertEqual(d["rows"][0]["recordIds"],["one","two"])
        self.assertEqual(d["excluded"]["midnight-ambiguous-precision"],1)
        self.assertEqual(d["excluded"]["invalid-chronology"],1)
        self.assertEqual(d["excluded"]["unverified-precision-or-corrected-date"],1)
        data["updates"]["items"].append({**row,"id":"conflict","publishedAt":"2026-11-27T10:01:00Z"})
        conflict=retained_feed_latency(data,self.now)
        self.assertEqual(conflict["observedArticles"],0)
        self.assertIsNone(conflict["medianSeconds"])
        self.assertEqual(conflict["excluded"]["conflicting-publication-timestamps"],1)

    def test_incident_denominator_not_equated_to_automatic_repair(self):
        empty=measure({},self.report,self.now)["gates"]["automaticRepairRate"]
        self.assertEqual(empty["status"],"not-measured")
        self.assertEqual(empty["observedBatchIncidentDiagnostic"]["observedIncidents"],0)
        self.assertIsNone(empty["observedBatchIncidentDiagnostic"]["scheduledRecoveryShareOfClosed"])
        rows=[{"origin":"observed-failure","openedAt":"2026-11-27T10:00:00+00:00",
               "closedAt":"2026-11-27T11:00:00+00:00","recoveryTrigger":"schedule"}]
        result=measure({"health":{"incidents":rows}},self.report,self.now)["gates"]["automaticRepairRate"]
        self.assertEqual(result["status"],"not-measured")
        self.assertEqual(result["observedBatchIncidentDiagnostic"]["scheduledRecoveries"],1)
        self.assertEqual(result["observedBatchIncidentDiagnostic"]["maxRecoverySeconds"],3600)
