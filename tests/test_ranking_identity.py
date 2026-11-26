import unittest
from scripts.ranking_identity import attach_rankings


class RankingIdentityTests(unittest.TestCase):
    def test_exact_identity_and_ambiguous_are_distinct(self):
        families = [{"id":"magi-2","vendor":"Sand.ai","category":"video","versions":[{"id":"full","name":"MAGI-2"},{"id":"preview","name":"MAGI-2 Preview"}]}]
        rows = [{"name":"MAGI-2","provider":"Sand.ai","rank":1,"score":1163},{"name":"MAGI-2 Preview","provider":"Sand.ai"},{"name":"MAGI-2","provider":"Other"},{"name":"MAGI-2 Ultra","provider":"Sand.ai"}]
        doc = {"categories":[{"primaryLeaderboard":{"rows":rows}}]}
        self.assertEqual(attach_rankings(doc,families,{}),{"exact":2,"unmatched":2,"ambiguous":0})
        self.assertEqual(rows[0]["modelVersionId"],"full")
        self.assertEqual(rows[1]["modelVersionId"],"preview")
        self.assertEqual(rows[0]["score"],1163)
        self.assertNotIn("modelVersionId",rows[2])
        families[0]["versions"].append({"id":"duplicate","name":"MAGI-2"})
        attach_rankings(doc,families,{})
        self.assertEqual(rows[0]["modelLinkStatus"],"ambiguous")
        self.assertNotIn("modelVersionId",rows[0])

    def test_board_alias_provider_evidence(self):
        families = [{"id":"wan","vendor":"阿里巴巴","category":"video","versions":[{"id":"v3","name":"Wan 3.0","leaderboardAliases":[{"source":"reference","boardId":"video","name":"Wan 3.0"}]}]}]
        rows = [{"name":"Wan 3.0","provider":"Alibaba"},{"name":"Wan 3.0","provider":"Unrelated"}]
        doc = {"categories":[{"primaryLeaderboard":{"rows":rows}}]}
        ref = {"boards":[{"id":"video","rows":[{"name":"Wan 3.0","provider":"Alibaba"}]}]}
        attach_rankings(doc,families,{},ref)
        self.assertEqual(rows[0]["modelVersionId"],"v3")
        self.assertEqual(rows[1]["modelLinkStatus"],"unmatched")
