import copy
import json
import unittest
from pathlib import Path

from scripts.report_acceptance import acceptance, render_acceptance
from scripts.ci_changed_scopes import scopes

ROOT = Path(__file__).resolve().parents[1]


class AcceptanceContractTests(unittest.TestCase):
    def setUp(self):
        self.report=json.loads((ROOT/"site/data/system-audit.json").read_text(encoding="utf-8"))

    def test_actual_persisted_snapshot_has_consistent_gate_denominators(self):
        result=acceptance(self.report)
        gates=self.report["p1Readiness"]["gates"]
        self.assertEqual(result["sameStageEventRecall"]["matched"],gates["sameStageEventRecall"]["matched"])
        self.assertEqual(result["fixedArticleRecall"]["matched"],gates["fixedArticleRecall"]["matched"])
        self.assertNotIn("fixedArticleRecall",result["blockingGates"])
        self.assertIn("pre-publication",render_acceptance(self.report))

    def test_article_only_gaps_do_not_become_event_misses(self):
        rows=[{"id":str(i),"matched":True,"originalArticleMatched":i<6,
               "alternateStatementMatched":i>=6,"alternateEvidenceIds":["verified-"+str(i)] if i>=6 else [],
               "dateConflict":False} for i in range(8)]
        stage={"status":"pass","events":8,"matched":8,"missingIds":[],"rows":rows,
               "originalArticleMatches":6,"alternateOnlyMatches":2}
        self.report["sameStageRecall"]=stage
        gates=self.report["p1Readiness"]["gates"]
        gates["sameStageEventRecall"]=copy.deepcopy(stage)
        gates["fixedArticleRecall"]={"status":"incomplete","events":8,"matched":6,"missingIds":["6","7"]}
        self.report["p1Readiness"]["blockingGates"]=[k for k,v in gates.items()
             if v["status"]!="pass" and k not in {"fixedArticleRecall","sevenDayProduction"}]
        result=acceptance(self.report)
        self.assertEqual(result["sameStageEventRecall"]["missingIds"],[])
        self.assertEqual(result["fixedArticleRecall"]["articleOnlyGapIds"],["6","7"])
        self.assertNotIn("sameStageEventRecall",result["blockingGates"])
        # A real stage regression must still block and must not be hidden.
        stage["rows"][7].update(matched=False,alternateStatementMatched=False,alternateEvidenceIds=[])
        stage.update(status="incomplete",matched=7,missingIds=["7"],alternateOnlyMatches=1)
        gates["sameStageEventRecall"]=copy.deepcopy(stage)
        self.report["p1Readiness"]["blockingGates"].append("sameStageEventRecall")
        result=acceptance(self.report)
        self.assertEqual(result["sameStageEventRecall"]["missingIds"],["7"])
        self.assertEqual(result["fixedArticleRecall"]["articleOnlyGapIds"],["6"])

    def test_inconsistent_readiness_and_false_hit_are_rejected(self):
        changed=copy.deepcopy(self.report)
        changed["sameStageRecall"]["matched"]=-1
        with self.assertRaises(ValueError):
            acceptance(changed)
        changed=copy.deepcopy(self.report)
        stage=changed["sameStageRecall"]
        stage["rows"][0].update(matched=True,dateConflict=True)
        changed["p1Readiness"]["gates"]["sameStageEventRecall"]=copy.deepcopy(stage)
        with self.assertRaises(ValueError):
            acceptance(changed)

    def test_unknown_stage_is_not_zero_or_pass(self):
        stage={"status":"not-measured","reason":"missing review"}
        self.report["sameStageRecall"]=stage
        self.report["p1Readiness"]["gates"]["sameStageEventRecall"]=copy.deepcopy(stage)
        blockers=self.report["p1Readiness"]["blockingGates"]
        if "sameStageEventRecall" not in blockers:
            blockers.append("sameStageEventRecall")
        result=acceptance(self.report)
        self.assertIsNone(result["sameStageEventRecall"]["matched"])
        self.assertIsNone(result["fixedArticleRecall"]["articleOnlyGapIds"])

    def test_audit_and_benchmark_changes_select_actual_source_diagnostics(self):
        for path in ("config/same-stage-event-benchmark.json","config/independent-fact-reviews.json",
                     "scripts/audit_same_stage_recall.py","scripts/report_acceptance.py"):
            self.assertTrue(scopes([path])["models"],path)
        self.assertFalse(scopes(["docs/reliability-retrospective-2026-11-28.md"])["models"])
