import unittest
from copy import deepcopy
from scripts.audit_same_stage_recall import assess_same_stage

class SameStageRecallTests(unittest.TestCase):
    def setUp(self):
        self.families=[{"id":"demo","versions":[{"id":"v"+str(i),"name":"Demo "+str(i)} for i in range(8)]}]
        self.original={"events":[{"id":str(i),"modelFamilyId":"demo","eventDate":"2026-11-23","modelNames":["Demo "+str(i)],
                                  "sourceUrls":["https://official.example/blog/"+str(i)]} for i in range(8)]}
        self.review={"schema":"same-stage-event-benchmark/v1","reviewedAt":"2026-11-28","scope":"test",
                     "events":[{**r,"stage":"announcement-statement","versionIds":["v"+r["id"]],"review":"reviewed article"} for r in self.original["events"]]}
        self.review["events"][7]["alternatives"]=[{"sourceUrl":"https://x.com/demo/status/1234567890123",
            "publisherAccount":"demo","service":None,"reviewUrl":"https://example.org/pointer","review":"same event"}]
        self.recall={"events":[{**r,"endToEndDated":i<7,"dateConflict":False,"currentDated":i<7}
                               for i,r in enumerate(self.original["events"])]}
        self.proof={"id":"publisher-validated","fact":{"modelFamilyId":"demo","modelVersionId":"v7","claimType":"announcement-statement",
                    "publisherCalendarDay":"2026-11-23","sourceUrl":"https://x.com/demo/status/1234567890123",
                    "publisherAccount":"demo","service":None,"eventDate":None}}
    def assess(self,proofs=()):
        return assess_same_stage(self.review,self.original,self.recall,proofs,self.families)
    def test_same_event_original_and_alternate_deduplicate(self):
        self.assertEqual(self.assess()["matched"],7)
        result=self.assess([self.proof])
        self.assertEqual(result["matched"],8)
        self.assertEqual(result["alternateOnlyMatches"],1)
        self.assertEqual(result["originalArticleMatches"],7)
        self.recall["events"][7].update(endToEndDated=True,currentDated=True)
        self.assertEqual(self.assess([self.proof])["matched"],8)
        self.assertEqual(self.assess([self.proof])["alternateOnlyMatches"],0)
    def test_different_stage_date_variant_url_or_account_not_match(self):
        for field,value in [("claimType","service-availability-statement"),("publisherCalendarDay","2026-11-22"),
                            ("modelVersionId","v6"),("sourceUrl","https://x.com/demo/status/1234567890124"),
                            ("publisherAccount","other"),("eventDate","2026-11-23")]:
            proof=deepcopy(self.proof);proof["fact"][field]=value
            self.assertEqual(self.assess([proof])["matched"],7)
    def test_no_canonical_or_cached_status_as_new_recall_and_conflict_blocks(self):
        self.recall["events"][7]["canonicalComplete"]=True
        self.assertEqual(self.assess()["matched"],7)
        self.recall["events"][7]["dateConflict"]=True
        self.assertEqual(self.assess([self.proof])["matched"],7)
    def test_cannot_change_fixed_truth_or_denominator(self):
        self.review["events"][0]["eventDate"]="2026-11-22"
        with self.assertRaises(ValueError): self.assess()
        self.review["events"][0]["eventDate"]="2026-11-23"
        self.review["events"].pop()
        with self.assertRaises(ValueError): self.assess()
    def test_joint_event_requires_all_version_identities(self):
        self.original["events"][7]["modelNames"]=["Demo 7","Demo 6"]
        self.review["events"][7].update(modelNames=["Demo 7","Demo 6"],versionIds=["v7","v6"])
        self.assertEqual(self.assess([self.proof])["matched"],7)
        second=deepcopy(self.proof);second["id"]="publisher-validated-2";second["fact"]["modelVersionId"]="v6"
        self.assertEqual(self.assess([self.proof,second])["matched"],8)

    def test_short_display_name_requires_exact_registered_model_name(self):
        version=self.families[0]["versions"][7]
        version["name"]="7"
        version["releaseEvidence"]={"modelName":"Demo 7"}
        self.assertEqual(self.assess([self.proof])["matched"],8)
        # Canonical evidence alone still does not establish a recall hit.
        self.assertEqual(self.assess()["matched"],7)
        version["releaseEvidence"]["modelName"]="Demo 7 Preview"
        with self.assertRaises(ValueError):
            self.assess([self.proof])
