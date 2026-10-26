"""End-to-end tests of the engine workflow. Run: python -m unittest discover tests"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import accounts, corridor  # noqa: E402
from engine.db import connect, one, rows  # noqa: E402
from engine.ingest import classify, ingest  # noqa: E402
from engine.pipeline import run_engine  # noqa: E402
from engine.review import review  # noqa: E402
from engine.seed import seed  # noqa: E402

TODAY = date(2026, 10, 23)


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        seed(self.conn, TODAY)
        self.result = run_engine(self.conn, TODAY, use_llm=False)

    def pending(self):
        return rows(self.conn, "SELECT * FROM decisions WHERE status = 'pending' ORDER BY priority DESC")

    def test_every_signal_is_resolved(self):
        self.assertEqual(one(self.conn, "SELECT COUNT(*) n FROM events WHERE resolved = 0")["n"], 0)
        ev = one(self.conn, "SELECT * FROM events WHERE text LIKE 'Call with Tobias Lang%'")
        self.assertEqual((ev["account_id"], ev["stakeholder_id"], ev["competitor_id"]),
                         ("rheinwerk", "lang", "northgate"))

    def test_queue_is_short_and_ranked(self):
        stats = self.result["stats"]
        self.assertLessEqual(stats["surfaced"], 10)
        self.assertGreater(stats["discarded"], 0)
        prios = [d["priority"] for d in self.pending()]
        self.assertEqual(prios, sorted(prios, reverse=True))
        per_account = {}
        for d in self.pending():
            if d["account_id"]:
                per_account[d["account_id"]] = per_account.get(d["account_id"], 0) + 1
        self.assertTrue(all(n <= 2 for n in per_account.values()))

    def test_top_call_challenges_the_weak_commit(self):
        top = self.pending()[0]
        self.assertEqual(top["type"], "forecast_downgrade")
        self.assertEqual(top["opportunity_id"], "opp-rheinwerk")
        self.assertTrue(top["evidence"])
        self.assertTrue(any("Champion" in r for r in top["reasoning"]))

    def test_corridor_agent_flags_diwali_fx_and_data_transfer(self):
        from engine.agents import build_context, corridor_agent
        found = {c["account_id"]: " ".join(c["reasoning"]) for c in corridor_agent(build_context(self.conn, TODAY))}
        self.assertIn("Diwali", found["indus"])
        self.assertIn("EUR/INR", found["indus"])
        self.assertIn("DPDP", found["noordbank"])
        self.assertIn("Works council", found["rheinwerk"])
        self.assertIn("Carbon Border", found["kaveri"])

    def test_approve_writes_back_and_learns(self):
        d = self.pending()[0]
        out = review(self.conn, d["id"], "approve", "cro", "")
        self.assertEqual(out["status"], "approved")
        opp = one(self.conn, "SELECT forecast_category FROM opportunities WHERE id = 'opp-rheinwerk'")
        self.assertEqual(opp["forecast_category"], "best_case")
        self.assertTrue(rows(self.conn, "SELECT * FROM outbox WHERE decision_id = ?", (d["id"],)))
        self.assertGreater(one(self.conn, "SELECT weight FROM agent_weights WHERE agent = 'Forecast'")["weight"], 1.0)

    def test_reject_needs_reason_and_is_not_resurfaced(self):
        d = self.pending()[0]
        with self.assertRaises(ValueError):
            review(self.conn, d["id"], "reject", "cro", "")
        review(self.conn, d["id"], "reject", "cro", "Customer confirmed signature date by phone")
        self.assertLess(one(self.conn, "SELECT weight FROM agent_weights WHERE agent = ?", (d["agent"],))["weight"], 1.0)
        run_engine(self.conn, TODAY, use_llm=False)
        again = rows(self.conn, "SELECT * FROM decisions WHERE key = ? AND status = 'pending'", (d["key"],))
        self.assertEqual(again, [])

    def test_new_signal_flows_through(self):
        ingest(self.conn, "email", "Sabine Krüger asked for a payback model before the steering committee",
               TODAY.isoformat(), {"email": "sabine.krueger@rheinwerk-automation.de"})
        r = run_engine(self.conn, TODAY, use_llm=False)
        self.assertEqual(r["stats"]["events_resolved"], 1)
        cfo = one(self.conn, "SELECT last_engaged FROM stakeholders WHERE id = 'krueger'")
        self.assertEqual(cfo["last_engaged"], TODAY.isoformat())

    def test_icp_and_account_plan(self):
        ranked = accounts.icp_rank(self.conn)
        self.assertTrue(ranked and ranked[0]["score"] >= ranked[-1]["score"])
        plan = accounts.account_plan(self.conn, "rheinwerk")
        roles = {c["role"]: c["status"] for c in plan["committee"]["coverage"]}
        self.assertEqual(roles["works_council"], "missing")
        self.assertEqual(roles["economic_buyer"], "stale")

    def test_helpers(self):
        self.assertEqual(classify("Northgate posts 6 roles", {"id": "northgate"}), "competitor_hiring")
        self.assertAlmostEqual(corridor.to_eur(9800000, "INR", 98.0), 100000)
        self.assertEqual(corridor.slowdown_for(date(2026, 12, 28), "EU")[0], "Christmas and New Year")


if __name__ == "__main__":
    unittest.main()
