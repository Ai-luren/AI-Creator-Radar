import copy
import unittest
from datetime import date

from scripts.collect_verify_model_releases import reconcile, release_name, automatic_evidence_valid
from scripts.collect_chronicle_updates import sync_automatic_confirmations, PENDING_STATUS
from unittest.mock import patch
from scripts.collect_models import rss_items, html_page_items


class AutoReleaseVerificationTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 27)
        self.stamp = "2026-11-27T00:00:00Z"
        self.models = [{"id": "seedance", "name": "Seedance", "vendor": "Vendor",
                        "category": "video", "versions": [{"id": "seedance-2", "name": "Seedance 2"}]}]
        self.sources = [{"id": sid, "name": sid, "vendor": "Vendor", "active": True, "official": True,
                         "url": f"https://{sid}.example/news", "modelMatches": {"seedance": ["seedance"]}}
                        for sid in ("a", "b")]
        self.status = {"sources": [{"id": sid, "checkedAt": self.stamp, "error": None} for sid in ("a", "b")]}
        self.updates = [{"id": sid, "sourceId": sid, "official": True, "updateType": "release",
                         "modelId": "seedance", "title": "Seedance 3 officially released",
                         "url": f"https://{sid}.example/news/{sid}-model-3", "publishedAt": "2026-11-26T00:00:00Z",
                         "publicationDateKind": "feed-published", "publicationObservedAt": self.stamp}
                        for sid in ("a", "b")]

    def run_gate(self):
        return reconcile(self.models, self.updates, self.sources, self.status, {"vendor": ["Vendor"]}, self.today)

    def test_dual_source_new_model_and_idempotence(self):
        result = self.run_gate()
        self.assertEqual(len(result["confirmed"]), 1)
        version = self.models[0]["versions"][-1]
        self.assertEqual(version["name"], "Seedance 3")
        self.assertEqual(version["releaseDate"], "2026-11-26")
        self.assertEqual(len(version["releaseEvidence"]["corroboratingSources"]), 2)
        self.assertNotIn("license", version)
        snapshot = copy.deepcopy(self.models)
        self.assertEqual(self.run_gate()["confirmed"], [])
        self.assertEqual(self.models, snapshot)

    def test_conflicts_untrusted_stale_and_stage_cannot_promote(self):
        for field, bad in [("publishedAt", "2026-11-25T00:00:00Z"),
                           ("publicationDateKind", "modified"), ("publicationObservedAt", "old"),
                           ("url", "https://evil.example/news/model-3"),
                           ("summary", "Limited access preview"), ("official", False),
                           ("updateType", "api")]:
            old = self.updates[1].get(field)
            self.updates[1][field] = bad
            self.assertEqual(self.run_gate()["confirmed"], [], field)
            self.updates[1][field] = old
        self.assertEqual(len(self.models[0]["versions"]), 1)

    def test_same_host_is_not_two_independent_official_sites(self):
        self.sources[1]["url"] = "https://a.example/other"
        self.updates[1]["url"] = "https://a.example/other/model-3"
        self.assertEqual(self.run_gate()["confirmed"], [])

    def test_existing_evidence_and_stage_are_protected(self):
        version = self.models[0]["versions"][0]
        version["name"] = "Seedance 3"
        version["historicalMilestones"] = [{"stage": "preview"}]
        self.assertEqual(self.run_gate()["confirmed"], [])
        self.assertNotIn("releaseEvidence", version)

    def test_title_does_not_treat_introduction_api_or_preview_as_release(self):
        for title in ("Introducing Seedance 3", "Seedance 3 API released", "Seedance 3 Preview released"):
            self.assertIsNone(release_name(title))

    def test_atom_updated_is_not_publication_evidence(self):
        source = self.sources[0]
        feed = b'<feed><entry><title>Seedance 3 officially released</title><link href="https://a.example/news/model-3"/><updated>2026-11-26T00:00:00Z</updated></entry></feed>'
        self.assertNotIn("publicationDateKind", rss_items(feed, source)[0])

    def test_glm_dated_button_is_candidate_only(self):
        source = {"type": "dated-headings", "dateButtons": True, "url": "https://docs.z.ai/release-notes/new-released",
                  "modelMatches": {"glm": ["glm-5"]}}
        items = html_page_items("<h2>Models</h2><button>2026-08-26</button><h3>GLM-5.3-Flash</h3>", source)
        self.assertEqual(items[0]["publishedAt"][:10], "2026-08-26")
        self.assertNotIn("publicationDateKind", items[0])

    def test_existing_short_numeric_identity_is_not_duplicated(self):
        self.models[0]["versions"][0]["name"] = "3"
        self.assertEqual(self.run_gate()["confirmed"], [])

    def test_stored_evidence_audit_rejects_tampering(self):
        self.run_gate()
        family = self.models[0]
        version = family["versions"][-1]
        self.assertTrue(automatic_evidence_valid(family, version))
        version["releaseEvidence"]["corroboratingSources"][1]["publishedAt"] = "2026-11-24"
        self.assertFalse(automatic_evidence_valid(family, version))

    def test_chronicle_promotes_only_matching_pending_nodes(self):
        self.run_gate()
        def event(sid):
            return {"sourceUpdateId": sid, "sourceModelId": "seedance", "date": "2026-11-26",
                    "url": f"https://{sid}.example/news/model-3", "autoCollected": True,
                    "verificationStatus": PENDING_STATUS}
        historical = dict(event("other"), auditId="manual", verificationStatus="人工核验")
        topic = {"id": "vendor", "group": "公司与模型", "milestones": [event("a"), event("b"), historical]}
        with patch("scripts.collect_chronicle_updates.vendor_topics", return_value={"vendor": "vendor"}):
            self.assertEqual(sync_automatic_confirmations([topic], self.models), 1)
            self.assertEqual(len(topic["milestones"]), 2)
            self.assertIn(historical, topic["milestones"])
            topic["milestones"].append(event("b"))
            self.assertEqual(sync_automatic_confirmations([topic], self.models), 0)
            self.assertEqual(len(topic["milestones"]), 2)


    def test_same_article_path_and_www_alias_are_not_independent(self):
        self.updates[1]["url"]="https://b.example/news/a-model-3"
        self.assertEqual(self.run_gate()["confirmed"],[])
        self.updates[1]["url"]="https://www.a.example/news/b-model-3"
        self.sources[1]["url"]="https://www.a.example/news"
        self.assertEqual(self.run_gate()["confirmed"],[])

    def test_cached_structured_date_requires_actual_raw_observation(self):
        self.status["sources"][0]["publicationObservations"]=[]
        self.assertEqual(self.run_gate()["confirmed"],[])


    def raw_status(self, active, stamp):
        return {"checkedAt":stamp,"sources":[{"id":s["id"],"checkedAt":stamp,
                "error":None if s["id"] in active else "403",
                "publicationObservations":[{k:u[k] for k in ("modelId","title","url","publishedAt")}
                                           for u in self.updates if u["sourceId"]==s["id"] and s["id"] in active]}
                for s in self.sources]}

    def test_cross_run_proofs_can_confirm_without_simultaneous_source_success(self):
        first = reconcile(self.models,self.updates,self.sources,self.raw_status({"a"},self.stamp),
                          {"vendor":["Vendor"]},self.today,{})
        self.assertEqual(first["confirmed"],[])
        self.assertEqual(first["proofLedgerSummary"]["records"],1)
        next_stamp="2026-11-27T03:00:00Z"
        self.updates[1]["publicationObservedAt"]=next_stamp
        second=reconcile(self.models,self.updates,self.sources,self.raw_status({"b"},next_stamp),
                         {"vendor":["Vendor"]},self.today,first)
        self.assertEqual(len(second["confirmed"]),1)
        self.assertEqual(second["proofLedgerSummary"]["records"],2)
        v=self.models[0]["versions"][-1]
        self.assertTrue(automatic_evidence_valid(self.models[0],v))
        self.assertEqual({p["observedAt"] for p in v["releaseEvidence"]["corroboratingSources"]},{self.stamp,next_stamp})

    def test_retained_proof_not_used_without_current_observation(self):
        first=reconcile(self.models,self.updates,self.sources,self.raw_status({"a"},self.stamp),
                        {"vendor":["Vendor"]},self.today,{})
        second=reconcile(self.models,self.updates,self.sources,self.raw_status(set(),self.stamp),
                         {"vendor":["Vendor"]},self.today,first)
        self.assertEqual(second["confirmed"],[])
        self.assertEqual(second["proofLedger"],first["proofLedger"])

    def test_new_publisher_conflict_quarantines_historical_proof(self):
        first=reconcile(self.models,self.updates,self.sources,self.raw_status({"a"},self.stamp),
                        {"vendor":["Vendor"]},self.today,{})
        next_stamp="2026-11-27T03:00:00Z"
        self.updates[0]["title"]="Seedance 3 available in preview"
        self.updates[0]["publicationObservedAt"]=next_stamp
        self.updates[1]["publicationObservedAt"]=next_stamp
        second=reconcile(self.models,self.updates,self.sources,self.raw_status({"a","b"},next_stamp),
                         {"vendor":["Vendor"]},self.today,first)
        self.assertEqual(second["confirmed"],[])
        self.assertEqual(second["proofLedgerSummary"]["quarantined"],1)

    def test_source_configuration_change_does_not_reuse_old_proof(self):
        first=reconcile(self.models,self.updates,self.sources,self.raw_status({"a"},self.stamp),
                        {"vendor":["Vendor"]},self.today,{})
        self.sources[0]["active"]=False
        next_stamp="2026-11-27T03:00:00Z"
        self.updates[1]["publicationObservedAt"]=next_stamp
        second=reconcile(self.models,self.updates,self.sources,self.raw_status({"b"},next_stamp),
                         {"vendor":["Vendor"]},self.today,first)
        self.assertEqual(second["confirmed"],[])

    def test_tampered_ledger_rejected(self):
        first=reconcile(self.models,self.updates,self.sources,self.raw_status({"a"},self.stamp),
                        {"vendor":["Vendor"]},self.today,{})
        first["proofLedger"][0]["proof"]["publishedAt"]="2026-11-25"
        with self.assertRaises(ValueError):
            reconcile(self.models,self.updates,self.sources,self.raw_status({"b"},self.stamp),
                      {"vendor":["Vendor"]},self.today,first)

    def test_legacy_cached_proof_is_not_persisted_for_future_use(self):
        self.status["sources"][1]["error"]="403"
        result=reconcile(self.models,self.updates,self.sources,self.status,
                         {"vendor":["Vendor"]},self.today,{})
        self.assertEqual(result["proofLedger"],[])
        self.assertEqual(result["confirmed"],[])
