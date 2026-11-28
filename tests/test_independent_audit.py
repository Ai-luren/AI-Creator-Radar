import unittest
from datetime import datetime,timedelta,timezone
from scripts.collect_independent_audit import audit,parse_rows

class IndependentAuditTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,27,tzinfo=timezone.utc)
        self.cfg={"sources":[{"author":"MiniMaxAI","vendorTopic":"minimax"}],"windowDays":45,"minIntervalMinutes":360,"limitPerSource":50}
        self.vendors={"minimax":["MiniMax"]}
        self.families=[{"id":"demo","vendor":"MiniMax","versions":[{"id":"v3","name":"Demo 3"}]}]
        self.raw=[{"id":"MiniMaxAI/Demo-3","createdAt":"2026-11-20T00:00:00Z","pipeline_tag":"text-to-video"},
                  {"id":"MiniMaxAI/Demo-4","createdAt":"2026-11-25T00:00:00Z","pipeline_tag":"text-to-video"},
                  {"id":"MiniMaxAI/Helper","createdAt":"2026-11-25T00:00:00Z","pipeline_tag":"feature-extraction"}]

    def fetch(self,spec,config,now):
        return parse_rows(self.raw,spec["author"],now,config["windowDays"],config["limitPerSource"])

    def run_audit(self,old=None,families=None,hours=0,fetcher=None):
        return audit(self.cfg,self.families if families is None else families,self.vendors,old or {},
                     self.now+timedelta(hours=hours),fetcher or self.fetch)

    def test_samples_independent_of_catalog_and_scoped_pipeline(self):
        first=self.run_audit()
        self.assertEqual(first["summary"]["inScopeRepositorySamples"],2)
        self.assertEqual(first["summary"]["initialStates"],{"exact-catalog-match":1,"unmatched-repository":1})
        self.assertEqual(first["summary"]["unclassifiedPipeline"],1)
        self.assertEqual({r["repositoryId"] for r in first["observations"]},{x["id"] for x in self.raw})

    def test_initial_miss_never_rewritten_after_catalog_repair(self):
        first=self.run_audit()
        newer=[{"id":"demo","vendor":"MiniMax","versions":[{"id":"v3","name":"Demo 3"},{"id":"v4","name":"Demo 4"}]}]
        later=self.run_audit(first,newer,hours=1)
        self.assertEqual(later["summary"]["initialStates"],first["summary"]["initialStates"])
        self.assertEqual(later["summary"]["currentStates"],{"exact-catalog-match":2})
        self.assertEqual(later["summary"]["successfulThisRun"],0)

    def test_failure_keeps_observed_sample_and_real_success_time(self):
        first=self.run_audit()
        def fail(*args):
            raise OSError("403")
        later=self.run_audit(first,hours=7,fetcher=fail)
        self.assertEqual(later["observations"],first["observations"])
        self.assertEqual(later["sources"][0]["lastSuccessAt"],first["sources"][0]["lastSuccessAt"])
        self.assertEqual(later["summary"]["successfulThisRun"],0)

    def test_no_fuzzy_match_or_wrong_vendor(self):
        families=[{"id":"other","vendor":"Other","versions":[{"id":"v4","name":"Demo 4"}]},
                  {"id":"demo","vendor":"MiniMax","versions":[{"id":"v3","name":"Demo 3"},{"id":"v4","name":"Demo 4 Pro"}]}]
        self.assertEqual(self.run_audit(families=families)["summary"]["currentStates"],
                         {"exact-catalog-match":1,"unmatched-repository":1})

    def test_page_limit_and_bad_identity(self):
        self.assertFalse(parse_rows(self.raw,"MiniMaxAI",self.now,45,3)[1])
        self.assertTrue(parse_rows(self.raw,"MiniMaxAI",self.now,45,4)[1])
        with self.assertRaises(ValueError):
            parse_rows([{"id":"other/Demo-4","createdAt":"2026-11-25T00:00:00Z"}],"MiniMaxAI",self.now,45,50)

    def test_repository_date_is_not_release_date(self):
        result=self.run_audit()
        self.assertTrue(all("repositoryCreatedAt" in r and "releaseDate" not in r for r in result["observations"]))


    def test_card_roles_require_explicit_publisher_identity(self):
        from scripts.collect_independent_audit import classify_card,exact_index
        row={"modelName":"Demo-PE","author":"MiniMaxAI"}
        index=exact_index(self.families,{"MiniMax"})
        card="# Demo-PE\nDemo-PE provides prompt expansion (PE) for\n[Demo-3](https://huggingface.co/MiniMaxAI/Demo-3)."
        result=classify_card(row,card,index)
        self.assertEqual(result["role"],"auxiliary-prompt-expander")
        self.assertEqual(result["parentIdentity"]["modelVersionId"],"v3")
        self.assertEqual(classify_card(row,card.replace("MiniMaxAI/","Other/"),index)["role"],"unresolved")
        self.assertEqual(classify_card(row,card.replace("# Demo-PE","# Different"),index)["role"],"unresolved")
        self.assertEqual(classify_card(row,"# Demo-PE\nUnrelated prompt expansion tag",index)["role"],"unresolved")

    def test_role_classification_does_not_change_first_observation(self):
        first=self.run_audit()
        def card(row):
            text="# Demo-4\nDemo-4 provides prompt expansion (PE) for [Demo-3](https://huggingface.co/MiniMaxAI/Demo-3)."
            return text,row["url"]+"/raw/main/README.md"
        later=audit(self.cfg,self.families,self.vendors,first,self.now+timedelta(hours=1),self.fetch,card)
        self.assertEqual(later["summary"]["initialStates"],first["summary"]["initialStates"])
        self.assertEqual(later["summary"]["currentStates"],first["summary"]["currentStates"])
        self.assertEqual(later["summary"]["cardRoles"],{"auxiliary-prompt-expander":1})
        self.assertEqual(later["summary"]["cardRequests"],1)
        row=next(r for r in later["observations"] if r["modelName"]=="Demo-4")
        self.assertEqual(len(row["cardEvidence"]),1)
        self.assertEqual(row["cardReview"]["role"],"auxiliary-prompt-expander")

    def test_old_card_observations_remain_in_independent_denominator_without_requests(self):
        first=self.run_audit()
        later=audit(self.cfg,self.families,self.vendors,first,self.now+timedelta(days=9),self.fetch,
                    lambda row:self.fail("old model card must not be fetched"))
        self.assertEqual(later["summary"]["cardRequests"],0)
        self.assertEqual(later["summary"]["initialStates"],first["summary"]["initialStates"])
        self.assertEqual(later["summary"]["inScopeRepositorySamples"],first["summary"]["inScopeRepositorySamples"])
        self.assertEqual({r["id"] for r in later["observations"]},{r["id"] for r in first["observations"]})

    def test_recent_card_priority_does_not_reduce_sample_denominator(self):
        from unittest.mock import patch
        self.raw.append({"id":"MiniMaxAI/Demo-5","createdAt":"2026-11-22T00:00:00Z","pipeline_tag":"text-to-video"})
        calls=[]
        def card(row):
            calls.append(row["modelName"])
            return "# "+row["modelName"],row["url"]+"/raw/main/README.md"
        with patch("scripts.collect_independent_audit.CARD_BUDGET",1):
            result=audit(self.cfg,self.families,self.vendors,{},self.now,self.fetch,card)
        self.assertEqual(calls,["Demo-4"])
        self.assertEqual(result["summary"]["inScopeRepositorySamples"],3)

    def test_standalone_and_bundle_are_not_auto_closed(self):
        from scripts.collect_independent_audit import classify_card
        row={"modelName":"Demo","author":"MiniMaxAI"}
        self.assertEqual(classify_card(row,"# Demo\nDemo is a continuous-latent language model. The released checkpoint includes weight files.",{})["role"],
                         "standalone-model-candidate")
        self.assertEqual(classify_card(row,"# Demo\nTwo kinds of artifact are published: End-to-end VAEs and Generative priors.",{})["role"],
                         "research-artifact-bundle")
