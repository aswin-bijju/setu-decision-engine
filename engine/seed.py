"""Demo tenant: a B2B vendor selling across the EU-India corridor.

All companies and people are fictional. Dates are relative to `today`, so the
demo stays current whenever it is reseeded. Events are inserted unresolved and go
through the same ingestion and entity-resolution path as live signals.
"""
from datetime import date, timedelta

from .db import j, now_iso

TABLES = ["outbox", "audit_log", "decisions", "runs", "events", "opportunities",
          "stakeholders", "competitors", "accounts", "agent_weights", "settings"]

AGENTS = ["Forecast", "Pipeline", "Champion", "Competition", "Territory",
          "Expansion", "Corridor", "Manager"]


def _m(**kw):
    """Build a MEDDPICC dict from key=(status, note) pairs."""
    return {k: {"status": s, "note": n} for k, (s, n) in kw.items()}


def seed(conn, today=None):
    today = today or date.today()

    def d(n):
        return (today + timedelta(days=n)).isoformat()

    for t in TABLES:
        conn.execute(f"DELETE FROM {t}")
    conn.execute("DELETE FROM sqlite_sequence")

    accounts = [
        ("rheinwerk", "Rheinwerk Automation GmbH", "rheinwerk-automation.de", "DE", "EU", "DACH",
         "Industrial automation", 2400, 0, 0, 0, "EU→IN", "Setting up a Global Capability Centre in Pune."),
        ("noordbank", "Noordbank N.V.", "noordbank.nl", "NL", "EU", "Benelux", "Banking", 5200,
         0, 0, 0, "EU→IN", "Moving vendor-risk operations to a Bengaluru delivery team."),
        ("kaveri", "Kaveri Mobility Pvt Ltd", "kaverimobility.in", "IN", "IN", "India South",
         "EV components", 1800, 0, 0, 0, "IN→EU", "Exports EV components to German OEMs."),
        ("lumiere", "Lumière Retail SA", "lumiere-retail.fr", "FR", "EU", "France", "Retail", 9000,
         1, 260000, 0.38, "EU→IN", "Customer since 2024. Runs a technology hub in Hyderabad."),
        ("indus", "Indus Pharma Exports Ltd", "induspharma.in", "IN", "IN", "India West",
         "Pharmaceuticals", 3100, 1, 140000, -0.31, "IN→EU", "Customer. Uses the EU dossier module."),
        ("nordlicht", "Nordlicht Energie AG", "nordlicht-energie.de", "DE", "EU", "DACH",
         "Renewable energy", 1300, 0, 0, 0, "EU→IN", "Exploring Indian grid partners."),
        ("saffron", "Saffron Analytics Pvt Ltd", "saffronanalytics.in", "IN", "IN", "India South",
         "Data & analytics", 650, 0, 0, 0, "IN→EU", "Prospect. Expanding into DACH and Benelux."),
        ("vistula", "Vistula Logistics S.A.", "vistula-logistics.pl", "PL", "EU", "CEE", "Logistics",
         2100, 0, 0, 0, "EU→IN", "Prospect. Planning a shared-services centre in India."),
        ("malabar", "Malabar Foods Export Pvt Ltd", "malabarfoods.in", "IN", "IN", "India South",
         "Food processing", 900, 0, 0, 0, "IN→EU", "Prospect from Kochi targeting EU retail chains."),
    ]
    conn.executemany("INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", accounts)

    stakeholders = [
        ("weber", "rheinwerk", "Dr. Matthias Weber", "VP Global Operations", "champion",
         "matthias.weber@rheinwerk-automation.de", 5, d(-24), "active"),
        ("krueger", "rheinwerk", "Sabine Krüger", "CFO", "economic_buyer",
         "sabine.krueger@rheinwerk-automation.de", 5, None, "active"),
        ("lang", "rheinwerk", "Tobias Lang", "Head of IT", "technical",
         "tobias.lang@rheinwerk-automation.de", 4, d(-6), "active"),
        ("devries", "noordbank", "Eva de Vries", "Head of Third-Party Risk", "champion",
         "eva.devries@noordbank.nl", 4, d(-3), "active"),
        ("bakker", "noordbank", "Joost Bakker", "Procurement Lead", "procurement",
         "joost.bakker@noordbank.nl", 3, d(-2), "active"),
        ("jansen", "noordbank", "Marieke Jansen", "COO", "economic_buyer",
         "marieke.jansen@noordbank.nl", 5, d(-40), "active"),
        ("karthik", "kaveri", "Karthik Subramanian", "Head of Exports", "champion",
         "karthik.s@kaverimobility.in", 4, d(-5), "active"),
        ("iyer", "kaveri", "Ramesh Iyer", "Managing Director", "economic_buyer",
         "ramesh.iyer@kaverimobility.in", 5, d(-15), "active"),
        ("dubois", "lumiere", "Claire Dubois", "Director Digital", "champion",
         "claire.dubois@lumiere-retail.fr", 4, d(-4), "active"),
        ("martin", "lumiere", "Antoine Martin", "CFO", "economic_buyer",
         "antoine.martin@lumiere-retail.fr", 5, d(-60), "active"),
        ("ravi", "lumiere", "Ravi Kumar", "Hyderabad Hub Lead", "user",
         "ravi.kumar@lumiere-retail.fr", 3, d(-9), "active"),
        ("shah", "indus", "Neha Shah", "VP Supply Chain", "champion",
         "neha.shah@induspharma.in", 4, d(-30), "departed"),
        ("desai", "indus", "Vikram Desai", "CFO", "economic_buyer",
         "vikram.desai@induspharma.in", 5, d(-11), "active"),
        ("becker", "nordlicht", "Jonas Becker", "Head of Grid Partnerships", "champion",
         "jonas.becker@nordlicht-energie.de", 3, d(-34), "active"),
    ]
    conn.executemany("INSERT INTO stakeholders VALUES (?,?,?,?,?,?,?,?,?)", stakeholders)

    competitors = [
        ("northgate", "Northgate Systems", j(["northgate"]),
         "Strong GCC set-up playbook; weaker on ongoing commercial intelligence."),
        ("qubit", "Qubit Revenue Cloud", j(["qubit"]),
         "Low entry price; limited India data residency options."),
        ("meridian", "Meridian Consulting", j(["meridian"]),
         "Consulting-led, long and expensive implementations."),
    ]
    conn.executemany("INSERT INTO competitors VALUES (?,?,?,?)", competitors)

    opps = [
        ("opp-rheinwerk", "rheinwerk", "Pune GCC enablement platform", 420000, "EUR", None,
         "Negotiation", d(18), d(-6), "commit", "Lena Fischer",
         _m(metrics=("confirmed", "Cut GCC ramp-up time from 9 to 5 months"),
            economic_buyer=("missing", "CFO not met yet"),
            decision_criteria=("confirmed", "Time to productivity, data residency"),
            decision_process=("weak", "Steering committee dates unclear"),
            paper_process=("weak", "MSA redlines pending"),
            identify_pain=("confirmed", "Pune hiring plan at risk"),
            champion=("confirmed", "Dr. Weber"),
            competition=("weak", "Unknown if others are evaluated")), d(-6)),
        ("opp-noordbank", "noordbank", "Vendor risk & DORA reporting rollout", 310000, "EUR", None,
         "Proposal", d(60), d(60), "best_case", "Arjun Menon",
         _m(metrics=("confirmed", "Register of information in 4 weeks, not 4 months"),
            economic_buyer=("weak", "COO sign-off needed above €250k"),
            decision_criteria=("confirmed", "DORA coverage, audit trail"),
            decision_process=("weak", "Legal not engaged"),
            paper_process=("missing", "SCC and DPDP assessment requested"),
            identify_pain=("confirmed", "Supervisory pressure on third-party ICT risk"),
            champion=("confirmed", "Eva de Vries"),
            competition=("confirmed", "Meridian Consulting shortlisted")), d(-1)),
        ("opp-kaveri", "kaveri", "CBAM emissions reporting suite", 16000000, "INR", 94.5,
         "Discovery", d(120), d(120), "pipeline", "Priya Nair",
         _m(metrics=("weak", "Protect EU export revenue"),
            economic_buyer=("confirmed", "Ramesh Iyer, MD"),
            decision_criteria=("missing", ""),
            decision_process=("missing", ""),
            paper_process=("missing", ""),
            identify_pain=("confirmed", "German OEM needs emissions data by Q1"),
            champion=("weak", "Karthik, early"),
            competition=("missing", "")), d(-5)),
        ("opp-indus", "indus", "Annual renewal 2027", 12500000, "INR", 93.0,
         "Renewal", d(16), d(16), "commit", "Arjun Menon",
         _m(metrics=("confirmed", "Dossier turnaround time"),
            economic_buyer=("confirmed", "Vikram Desai"),
            decision_criteria=("confirmed", "Renewal at same scope"),
            decision_process=("confirmed", "CFO approval"),
            paper_process=("confirmed", "Standard renewal"),
            identify_pain=("weak", "Usage falling"),
            champion=("missing", "Neha Shah has left"),
            competition=("weak", "Qubit demo reported")), d(-11)),
        ("opp-nordlicht", "nordlicht", "Grid partner analytics pilot", 95000, "EUR", None,
         "Qualification", d(60), d(45), "pipeline", "Lena Fischer",
         _m(metrics=("weak", ""), economic_buyer=("missing", ""),
            decision_criteria=("weak", ""), decision_process=("missing", ""),
            paper_process=("missing", ""), identify_pain=("weak", "Partner vetting is manual"),
            champion=("weak", "Jonas Becker"), competition=("missing", "")), d(-34)),
    ]
    conn.executemany(
        "INSERT INTO opportunities (id, account_id, name, amount, currency, fx_at_quote, stage, "
        "close_date, original_close_date, forecast_category, owner, meddpicc, last_activity) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [o[:11] + (j(o[11]), o[12]) for o in opps])

    # (days ago, source, text, payload hints, kind or None to auto-classify)
    events = [
        (24, "calendar", "Meeting held: weekly sync with Dr. Matthias Weber and Lena Fischer",
         {"email": "matthias.weber@rheinwerk-automation.de"}, "meeting"),
        (20, "email", "Follow-up on commercial terms sent to Dr. Weber is still unanswered",
         {"email": "matthias.weber@rheinwerk-automation.de"}, "no_reply"),
        (12, "crm", f"Close date for 'Pune GCC enablement platform' moved from {d(-6)} to {d(18)}",
         {"account": "rheinwerk"}, "close_date_pushed"),
        (10, "news", "Rheinwerk Automation confirms 400-seat Global Capability Centre in Pune, opening Q2 2027",
         {}, None),
        (8, "hiring", "Northgate Systems posts 6 roles in Stuttgart, including 'Solution Architect, Rheinwerk account'",
         {}, None),
        (6, "calls", "Call with Tobias Lang: 'We are also looking at Northgate for the Pune set-up. "
         "Their GCC playbook came up in the steering committee.'",
         {"email": "tobias.lang@rheinwerk-automation.de"}, None),
        (3, "email", "Tobias Lang: our Betriebsrat needs to review employee-data handling before sign-off",
         {"email": "tobias.lang@rheinwerk-automation.de"}, None),
        (3, "calendar", "Workshop with Eva de Vries on the DORA register of information",
         {"email": "eva.devries@noordbank.nl"}, "meeting"),
        (2, "email", "Joost Bakker: procurement requires Standard Contractual Clauses and a DPDP Act "
         "assessment for data processed in Bengaluru", {"email": "joost.bakker@noordbank.nl"}, None),
        (1, "slack", "#deal-noordbank: Legal is not looped in on their side yet. Eva says COO sign-off "
         "is needed above €250k", {"account": "noordbank"}, "decision_process"),
        (4, "calls", "Noordbank shortlisted Meridian Consulting as the alternative for the DORA programme",
         {"account": "noordbank"}, None),
        (14, "news", "EU CBAM definitive period in force since January 2026: EU importers of steel, "
         "aluminium and related goods need verified embedded-emissions data from suppliers", {}, None),
        (7, "hiring", "Kaveri Mobility is hiring an 'EU Regulatory Compliance Manager' in Chennai", {}, None),
        (5, "calls", "Discovery call with Karthik Subramanian: their German OEM customer asked for CBAM "
         "emissions data by Q1", {"email": "karthik.s@kaverimobility.in"}, "identify_pain"),
        (4, "buying_signals", "Kaveri Mobility visited the pricing page 5 times and downloaded the CBAM whitepaper",
         {}, None),
        (4, "calendar", "QBR with Claire Dubois: Hyderabad hub rollout going well",
         {"email": "claire.dubois@lumiere-retail.fr"}, "meeting"),
        (6, "hiring", "Lumière Retail is hiring 45 roles at its Hyderabad technology centre", {}, None),
        (2, "product_usage", "Lumière Retail: weekly active users up 38% in 60 days; Hyderabad hub at "
         "120 active seats against 100 licensed", {"account": "lumiere"}, "usage_up"),
        (30, "news", "Neha Shah of Indus Pharma Exports announces a new role at another company (LinkedIn)",
         {}, "champion_departed"),
        (11, "email", "Vikram Desai: please send renewal pricing in INR, the board reviews spend next month",
         {"email": "vikram.desai@induspharma.in"}, "pricing"),
        (9, "calls", "Support call with Indus Pharma: a user mentioned a Qubit demo last week",
         {"account": "indus"}, None),
        (3, "product_usage", "Indus Pharma: active users down 31% quarter on quarter; EU dossier module "
         "unused for 21 days", {"account": "indus"}, "usage_down"),
        (5, "buying_signals", "Three new contacts from Nordlicht Energie joined the India partner-network webinar",
         {}, None),
        (6, "news", "Saffron Analytics raises Series B to expand into Germany and the Netherlands", {}, None),
        (3, "hiring", "Saffron Analytics is hiring a 'Country Manager DACH' in Berlin", {}, None),
        (8, "news", "Vistula Logistics announces a shared-services centre in Pune", {}, None),
        (2, "news", "Malabar Foods Export targets EU retail chains ahead of expected EU-India trade "
         "agreement tariff changes", {}, None),
        (5, "news", "EU-India FTA: negotiators report progress on market access chapters", {}, "trade_news"),
    ]
    for days_ago, source, text, payload, kind in events:
        conn.execute("INSERT INTO events (source, occurred_at, text, payload, kind, ingested_at) "
                     "VALUES (?,?,?,?,?,?)", (source, d(-days_ago), text, j(payload), kind, now_iso()))

    conn.executemany("INSERT INTO agent_weights (agent) VALUES (?)", [(a,) for a in AGENTS])
    defaults = {
        "queue_size": 10,
        "crm_system": "hubspot",
        "strategy": {"focus_territories": ["DACH", "India South"], "focus_corridor": "EU→IN"},
        "icp_industries": ["Industrial automation", "Banking", "EV components", "Retail",
                           "Pharmaceuticals", "Logistics", "Data & analytics"],
    }
    for k, v in defaults.items():
        conn.execute("INSERT INTO settings VALUES (?, ?)", (k, j(v)))
    conn.commit()
