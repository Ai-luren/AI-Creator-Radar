import unittest
from copy import deepcopy
from datetime import datetime,timezone
from scripts.audit_publisher_statements import inspect_statements,statement_id
from scripts.collect_event_reconciliation import reconcile

class StatementAuditTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,27,12,tzinfo=timezone.utc)
        self.stamp=self.now.isoformat()
        self.families=[{"id":"glm","versions":[{"id":"5-4","name":"GLM-5.4"}]}]
        fact={"modelFamilyId":"glm","modelVersionId":"5-4","claimType":"service-availability-statement",
              "sourceUrl":"https://www.zhipuai.cn/zh/research/123","publisherCalendarDay":"2026-11-22",
              "datePrecision":"day","eventDate":None,"statementSha256":"a"*64,"contentSha256":"b"*64,
              "evidenceGrade":"official-dated-article-statement","service":"GLM Coding Plan"}
        self.record={"id":statement_id(fact),"fact":fact,"discovery":{"channel":"official-article-collector","sourceUrl":fact["sourceUrl"]},
                     "firstObservedAt":self.stamp,"lastSuccessfulObservationAt":self.stamp}
        self.snapshot={"checkedAt":self.stamp,"records":[self.record]}
    def test_stage_sample_is_separate_and_exact(self):
        sample={"events":[{"id":"test",**self.record["fact"]}]}
        usable,report=inspect_statements(self.snapshot,self.families,self.now,sample)
        self.assertEqual(len(usable),1)
        self.assertEqual(report["availabilitySample"]["matched"],1)
        sample["events"][0]["publisherCalendarDay"]="2026-11-23"
        self.assertEqual(inspect_statements(self.snapshot,self.families,self.now,sample)[1]["availabilitySample"]["matched"],0)
    def test_tamper_and_fabricated_release_fail(self):
        for field,value in [("eventDate","2026-11-22"),("sourceUrl","https://evil.example/zh/research/123"),("contentSha256","bad")]:
            bad=deepcopy(self.snapshot)
            fact=bad["records"][0]["fact"]
            fact[field]=value
            bad["records"][0]["id"]=statement_id(fact)
            self.assertTrue(inspect_statements(bad,self.families,self.now)[1]["errors"])
    def test_conflict_excluded_and_never_closes_release_gap(self):
        bad=deepcopy(self.record)
        bad["fact"]["publisherCalendarDay"]="2026-11-23"
        bad["id"]=statement_id(bad["fact"])
        usable,report=inspect_statements(dict(self.snapshot,records=[self.record,bad]),self.families,self.now)
        self.assertEqual(usable,[])
        self.assertEqual(report["summary"]["dateConflicts"],1)
        gap={"reviewKind":"release-source-review","modelFamilyId":"glm","modelVersionId":"5-4"}
        result=reconcile(self.families,{}, {}, [gap], {}, self.now,publisher_statements=self.snapshot)
        self.assertEqual(result["tasks"][0]["state"],"needs-release-evidence")
        self.assertEqual(len(result["tasks"][0]["relatedPublisherStatementEvidenceIds"]),1)
        self.assertEqual(result["evidence"][0]["claimType"],"publisher-service-availability-statement")
        self.assertEqual(result["evidence"][0]["datePrecision"],"publisher-calendar-day")
